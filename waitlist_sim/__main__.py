"""Command line entry point for the baseline simulator."""

import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
from statistics import mean, pstdev

from .model import Config, TravellerType, simulate
from .experiments import (
    run_c2_congestion_experiments,
    run_c2_release_timing_experiment,
    run_refund_policy_sweep,
    run_refund_eta_sensitivity,
)
from .equilibrium import (
    compare_equilibrium_with_event_simulation,
    config_from_dict as equilibrium_config_from_dict,
    solve_type_equilibria,
)
from .learning import run_belief_learning_experiment
from .network import network_config_from_dict, simulate_network
from .proposal_rules import summarize_rule_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the waitlist hedging baseline simulator")
    parser.add_argument("--runs", type=int, default=1000, help="number of seeded runs (default: 1000)")
    parser.add_argument("--seed", type=int, default=7, help="first random seed (default: 7)")
    parser.add_argument("--capacity", type=int, default=50)
    parser.add_argument("--travellers", type=int, default=100)
    parser.add_argument("--hedge-probability", type=float, default=0.4)
    parser.add_argument("--hedge-fee", type=float, default=5.0)
    parser.add_argument("--missed-trip-cost", type=float, default=20.0)
    parser.add_argument("--refund", type=float, default=0.0)
    parser.add_argument("--fare", type=float, default=10.0)
    parser.add_argument("--policy", choices=("hedgers_first", "lottery"), default="hedgers_first")
    parser.add_argument("--config", type=Path, help="JSON config containing capacity and traveller types")
    parser.add_argument("--benchmark-hedged-probability", type=float,
                        help="fixed, independent confirmation probability assumed for hedgers")
    parser.add_argument("--benchmark-unhedged-probability", type=float,
                        help="fixed, independent confirmation probability assumed for others")
    parser.add_argument("--rule-config", type=Path,
                        help="JSON file with proposal Eq. (2) and Eq. (3) decision cases")
    parser.add_argument("--network-config", type=Path,
                        help="JSON config for the multi-train event simulator")
    parser.add_argument("--c2-congestion-experiment", action="store_true",
                        help="run controlled C2 fixed-belief versus congestion profiles")
    parser.add_argument("--c2-release-experiment", action="store_true",
                        help="run controlled C2 Eq. (3) q1/q2 timing experiment")
    parser.add_argument("--equilibrium-config", type=Path,
                        help="JSON config for the C3 type-based booking equilibrium")
    parser.add_argument("--equilibrium-compare", action="store_true",
                        help="replay a type equilibrium in the event simulator")
    parser.add_argument("--equilibrium-index", type=int, default=0,
                        help="zero-based pure equilibrium index for --equilibrium-compare")
    parser.add_argument("--refund-policy-sweep", action="store_true",
                        help="run a beta refund-policy sweep under Eq. (3)")
    parser.add_argument("--learning-experiment", action="store_true",
                        help="run repeated Eq. (2) belief-learning agents")
    parser.add_argument("--refund-eta-sensitivity", action="store_true",
                        help="test refund-policy results across plan-change rates")
    args = parser.parse_args()
    if args.rule_config:
        rule_input = json.loads(args.rule_config.read_text(encoding="utf-8"))
        print(json.dumps(summarize_rule_inputs(
            rule_input.get("hedge_cases", {}), rule_input.get("release_cases", {})
        ), indent=2, sort_keys=True))
        return
    if args.c2_congestion_experiment:
        print(json.dumps(run_c2_congestion_experiments(args.runs, args.seed),
                         indent=2, sort_keys=True))
        return
    if args.c2_release_experiment:
        print(json.dumps(run_c2_release_timing_experiment(args.runs, args.seed),
                         indent=2, sort_keys=True))
        return
    if args.equilibrium_config:
        equilibrium_config = equilibrium_config_from_dict(
            json.loads(args.equilibrium_config.read_text(encoding="utf-8"))
        )
        result = (compare_equilibrium_with_event_simulation(
            equilibrium_config, args.equilibrium_index, args.runs, args.seed
        ) if args.equilibrium_compare else solve_type_equilibria(equilibrium_config))
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if args.refund_policy_sweep:
        print(json.dumps(run_refund_policy_sweep(args.runs, args.seed),
                         indent=2, sort_keys=True))
        return
    if args.learning_experiment:
        print(json.dumps(run_belief_learning_experiment(args.runs, args.seed),
                         indent=2, sort_keys=True))
        return
    if args.refund_eta_sensitivity:
        print(json.dumps(run_refund_eta_sensitivity(args.runs, args.seed),
                         indent=2, sort_keys=True))
        return
    if args.network_config:
        if args.runs < 1:
            parser.error("runs must be positive")
        network_config = network_config_from_dict(
            json.loads(args.network_config.read_text(encoding="utf-8"))
        )
        network_rows = [
            simulate_network(network_config, seed=args.seed + i) for i in range(args.runs)
        ]
        metric_names = tuple(network_rows[0]["metrics"])
        decisions_by_name = {
            traveller.name: traveller.strategy_decisions or {}
            for traveller in network_config.travellers
        }
        train_trials: Counter[str] = Counter()
        train_successes: Counter[str] = Counter()
        waitlist_trials: Counter[str] = Counter()
        q1_successes: Counter[str] = Counter()
        q2_successes: Counter[str] = Counter()
        strategy_train_trials: Counter[str] = Counter()
        strategy_train_successes: Counter[str] = Counter()
        fixed_probability_sum: Counter[str] = Counter()
        fixed_probability_count: Counter[str] = Counter()
        pair_trials: Counter[tuple[str, str]] = Counter()
        pair_successes: Counter[tuple[str, str]] = Counter()
        pair_marginal_successes: Counter[tuple[tuple[str, str], str]] = Counter()
        for row in network_rows:
            for train_name, train_result in row["trains"].items():
                waitlist_trials[train_name] += train_result["q1_q2_observations_excluding_censored"]
                q1_successes[train_name] += train_result["waitlisted_confirmed_before_chart"]
                q2_successes[train_name] += train_result["waitlisted_confirmed_at_chart"]
            for ticket_key, ticket in row["tickets"].items():
                traveller_name, train_name = ticket_key.split("/", 1)
                if ticket["initial_status"] != "refused":
                    censored = (not ticket["ever_confirmed"]
                                and ticket.get("cancellation_reason") in ("plan_change", "scheduled_release"))
                    if not censored:
                        train_trials[train_name] += 1
                        train_successes[train_name] += int(ticket["ever_confirmed"])
                        if (traveller_name in decisions_by_name
                                and train_name in decisions_by_name[traveller_name].get("fixed_confirmation_probabilities", {})):
                            strategy_train_trials[train_name] += 1
                            strategy_train_successes[train_name] += int(ticket["ever_confirmed"])
                            fixed_probability_sum[train_name] += decisions_by_name[traveller_name]["fixed_confirmation_probabilities"][train_name]
                            fixed_probability_count[train_name] += 1
            for traveller in network_config.travellers:
                accepted = [
                    train_name for train_name in traveller.trains_to_book
                    if row["tickets"].get(f"{traveller.name}/{train_name}", {}).get("initial_status") != "refused"
                    and f"{traveller.name}/{train_name}" in row["tickets"]
                    and (row["tickets"][f"{traveller.name}/{train_name}"]["ever_confirmed"]
                         or row["tickets"][f"{traveller.name}/{train_name}"].get("cancellation_reason")
                         not in ("plan_change", "scheduled_release"))
                ]
                for first, second in combinations(sorted(accepted), 2):
                    pair = (first, second)
                    pair_trials[pair] += 1
                    both = all(row["tickets"][f"{traveller.name}/{name}"]["ever_confirmed"]
                               for name in pair)
                    pair_successes[pair] += int(both)
                    for name in pair:
                        pair_marginal_successes[(pair, name)] += int(
                            row["tickets"][f"{traveller.name}/{name}"]["ever_confirmed"]
                        )
        independence_diagnostics = {}
        for (first, second), observations in pair_trials.items():
            p1 = pair_marginal_successes[((first, second), first)] / observations
            p2 = pair_marginal_successes[((first, second), second)] / observations
            observed_joint = pair_successes[(first, second)] / observations if observations else 0.0
            independence_diagnostics[f"{first}|{second}"] = {
                "paired_observations": observations,
                "observed_joint_confirmation_rate": observed_joint,
                "product_of_marginal_rates": p1 * p2,
                "joint_minus_independent_product": observed_joint - p1 * p2,
            }
        print(json.dumps({
            "runs": args.runs,
            "config": str(args.network_config),
            "mean_metrics": {
                name: mean(row["metrics"][name] for row in network_rows)
                for name in metric_names
            },
            "standard_deviation_metrics": {
                name: pstdev(row["metrics"][name] for row in network_rows)
                for name in metric_names
            },
            "fixed_probability_and_independence_diagnostics": {
                "capacity_confirmation_rates_excluding_censored": {
                    train.name: (train_successes[train.name] / train_trials[train.name]
                                 if train_trials[train.name] else None)
                    for train in network_config.trains
                },
                "fixed_assumption_vs_observed": {
                    train.name: {
                        "accepted_rule_agent_observations": fixed_probability_count[train.name],
                        "mean_fixed_probability_assumption": (
                            fixed_probability_sum[train.name] / fixed_probability_count[train.name]
                            if fixed_probability_count[train.name] else None
                        ),
                        "observed_confirmation_rate": (
                            strategy_train_successes[train.name] / strategy_train_trials[train.name]
                            if strategy_train_trials[train.name] else None
                        ),
                        "observed_minus_fixed_assumption": (
                            strategy_train_successes[train.name] / strategy_train_trials[train.name]
                            - fixed_probability_sum[train.name] / fixed_probability_count[train.name]
                            if strategy_train_trials[train.name] and fixed_probability_count[train.name] else None
                        ),
                    }
                    for train in network_config.trains
                },
                "waitlist_confirmation_timing_rates": {
                    train.name: {
                        "uncensored_waitlist_ticket_observations": waitlist_trials[train.name],
                        "q1_before_chart_rate": (
                            q1_successes[train.name] / waitlist_trials[train.name]
                            if waitlist_trials[train.name] else None
                        ),
                        "q2_at_chart_rate": (
                            q2_successes[train.name] / waitlist_trials[train.name]
                            if waitlist_trials[train.name] else None
                        ),
                    }
                    for train in network_config.trains
                },
                "joint_confirmation_checks": independence_diagnostics,
                "conditioning_note": "Confirmation-rate estimates exclude accepted tickets censored by plan-change cancellation or voluntary release before confirmation; chart-time non-confirmations remain failures. Pair rates condition on both accepted, uncensored requests. q1/q2 rates condition on initially waitlisted tickets that were not censored before their outcome.",
            },
            "first_run_detail": network_rows[0],
        }, indent=2, sort_keys=True))
        return
    if args.runs < 1 or args.travellers < 0:
        parser.error("runs must be positive and travellers nonnegative")
    for name in ("benchmark_hedged_probability", "benchmark_unhedged_probability"):
        value = getattr(args, name)
        if value is not None and not 0 <= value <= 1:
            parser.error(f"--{name.replace('_', '-')} must be in [0, 1]")

    if args.config:
        raw = json.loads(args.config.read_text(encoding="utf-8"))
        config = Config(
            capacity=raw["capacity"],
            types=tuple(TravellerType(**item) for item in raw["types"]),
            refund_if_unconfirmed=raw.get("refund_if_unconfirmed", 0.0),
            fare=raw.get("fare", 0.0),
        )
    else:
        config = Config(
            capacity=args.capacity,
            types=(TravellerType("standard", args.travellers, value=20.0,
                                 hedge_fee=args.hedge_fee,
                                 missed_trip_cost=args.missed_trip_cost,
                                 hedge_probability=args.hedge_probability),),
            refund_if_unconfirmed=args.refund,
            fare=args.fare,
        )
    rows = [simulate(config, seed=args.seed + i, policy=args.policy) for i in range(args.runs)]
    metric_names = (
        "hedge_rate", "confirmation_rate", "hedge_fees_paid",
        "refunds_transferred_to_travellers", "railway_net_cash_flow",
        "social_resource_cost",
    )
    summary = {
        "runs": args.runs,
        "parameters": {key: (str(value) if isinstance(value, Path) else value)
                       for key, value in vars(args).items()},
        "type_parameters": [vars(t) for t in config.types],
        "mean": {name: mean(row[name] for row in rows) for name in metric_names},
        "population_standard_deviation": {
            name: pstdev(row[name] for row in rows) for name in metric_names
        },
        "type_mean": {
            traveller_type.name: {
                metric: mean(row["types"][traveller_type.name][metric] for row in rows)
                for metric in ("hedge_rate", "confirmation_rate", "hedge_fees_paid",
                               "refunds_received", "missed_trip_cost")
            }
            for traveller_type in config.types
        },
        "first_run_detail": rows[0],
    }
    bh, bu = args.benchmark_hedged_probability, args.benchmark_unhedged_probability
    if (bh is None) != (bu is None):
        parser.error("provide both benchmark confirmation probabilities, or neither")
    if bh is not None and bu is not None:
        total_hedged = sum(row["hedged"] for row in rows)
        total_unhedged = sum(row["unhedged"] for row in rows)
        observed_h = sum(row["confirmed_hedged"] for row in rows) / total_hedged if total_hedged else 0.0
        observed_u = sum(row["confirmed_unhedged"] for row in rows) / total_unhedged if total_unhedged else 0.0
        summary["fixed_probability_benchmark_check"] = {
            "assumed_confirmation_probability_given_hedging": bh,
            "observed_confirmation_probability_given_hedging": observed_h,
            "hedged_probability_gap_observed_minus_assumed": observed_h - bh,
            "assumed_confirmation_probability_without_hedging": bu,
            "observed_confirmation_probability_without_hedging": observed_u,
            "unhedged_probability_gap_observed_minus_assumed": observed_u - bu,
            "interpretation": "A nonzero gap shows mismatch in this scenario; the fixed benchmark probabilities are supplied by the user and are not inferred from the simulation.",
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
