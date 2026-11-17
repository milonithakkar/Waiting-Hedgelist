"""Reproducible C2 experiments for fixed-belief versus endogenous outcomes."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from statistics import mean, pstdev
from typing import Any

from .network import NetworkConfig, Train, Traveller, simulate_network
from .proposal_rules import build_independent_probability_strategy, release_rule


FIXED_BELIEF = 0.70


def _strategy(values: dict[str, float], fares: dict[str, float]) -> dict[str, object]:
    """Common Eq. (2) benchmark belief used in all C2 congestion profiles."""
    return build_independent_probability_strategy(
        values=values,
        fares=fares,
        confirmation_probabilities={name: FIXED_BELIEF for name in values},
        expected_ticket_costs={name: 1.0 for name in values},
        outside_option=0.0,
    )


def congestion_profile(name: str) -> NetworkConfig:
    """Return one controlled market profile for the C2 independence check.

    Every strategic traveller has identical Eq. (2) beliefs and values. Only
    capacity changes across profiles, isolating the impact of congestion on
    confirmation and joint-confirmation outcomes.
    """
    settings = {
        "light": {"capacity": 8, "strategic_agents": 6},
        "balanced": {"capacity": 4, "strategic_agents": 10},
        "congested": {"capacity": 2, "strategic_agents": 14},
    }
    if name not in settings:
        raise ValueError(f"unknown C2 profile {name!r}")
    setting = settings[name]
    fares = {"A": 10.0, "B": 10.0}
    values = {"A": 40.0, "B": 35.0}
    strategy = _strategy(values, fares)
    travellers = tuple(
        Traveller(
            name=f"strategic_{index}",
            values=values,
            outside_option=0.0,
            booking_time=0,
            trains_to_book=tuple(strategy["trains_to_book"]),
            release_times={},
            strategy_decisions=strategy,
        )
        for index in range(setting["strategic_agents"])
    )
    return NetworkConfig(
        trains=(
            Train("A", setting["capacity"], 30, fares["A"]),
            Train("B", setting["capacity"], 30, fares["B"]),
        ),
        travellers=travellers,
        time_steps=(0, 1, 2),
        chart_time=2,
        departure_time=2,
        refund_start_time=1,
        refund_bonus=0.0,
        release_friction=0.0,
        waitlist_cancellation_cost=1.0,
        confirmed_cancellation_fee=4.0,
        confirmed_cancellation_fee_schedule=None,
        post_chart_resale_probability=0.0,
        empty_berth_cost=3.0,
    )


def _summarize(config: NetworkConfig, runs: int, seed: int) -> dict[str, Any]:
    rows = [simulate_network(config, seed=seed + index) for index in range(runs)]
    train_trials: Counter[str] = Counter()
    train_successes: Counter[str] = Counter()
    pair_trials: Counter[tuple[str, str]] = Counter()
    pair_successes: Counter[tuple[str, str]] = Counter()
    pair_marginals: Counter[tuple[tuple[str, str], str]] = Counter()
    for row in rows:
        for ticket_key, ticket in row["tickets"].items():
            _, train = ticket_key.split("/", 1)
            if ticket["initial_status"] != "refused":
                train_trials[train] += 1
                train_successes[train] += int(ticket["ever_confirmed"])
        for traveller in config.travellers:
            pair = tuple(sorted(traveller.trains_to_book))
            if len(pair) != 2:
                continue
            statuses = [row["tickets"][f"{traveller.name}/{train}"] for train in pair]
            if any(ticket["initial_status"] == "refused" for ticket in statuses):
                continue
            pair_trials[pair] += 1
            pair_successes[pair] += int(all(ticket["ever_confirmed"] for ticket in statuses))
            for train, ticket in zip(pair, statuses):
                pair_marginals[(pair, train)] += int(ticket["ever_confirmed"])
    rates = {
        train.name: train_successes[train.name] / train_trials[train.name]
        for train in config.trains
    }
    pair_results = {}
    for pair, count in pair_trials.items():
        first, second = pair
        first_rate = pair_marginals[(pair, first)] / count
        second_rate = pair_marginals[(pair, second)] / count
        joint = pair_successes[pair] / count
        pair_results[f"{first}|{second}"] = {
            "observations": count,
            "first_marginal": first_rate,
            "second_marginal": second_rate,
            "observed_joint": joint,
            "independent_product": first_rate * second_rate,
            "joint_minus_independent_product": joint - first_rate * second_rate,
        }
    return {
        "runs": runs,
        "strategic_travellers": len(config.travellers),
        "capacity_per_train": config.trains[0].capacity,
        "fixed_belief": FIXED_BELIEF,
        "observed_confirmation_rates": rates,
        "observed_minus_fixed_belief": {
            train: rate - FIXED_BELIEF for train, rate in rates.items()
        },
        "joint_confirmation": pair_results,
        "mean_social_welfare_eq4": mean(row["metrics"]["railway_social_welfare_eq4"] for row in rows),
        "social_welfare_population_sd": pstdev(
            row["metrics"]["railway_social_welfare_eq4"] for row in rows
        ),
    }


def run_c2_congestion_experiments(runs: int = 1_000, seed: int = 7) -> dict[str, Any]:
    """Run controlled low-to-high congestion C2 profiles."""
    if runs < 1:
        raise ValueError("runs must be positive")
    return {
        "purpose": (
            "Compare a constant fixed confirmation belief used by Eq. (2) with "
            "confirmation rates and joint outcomes produced by shared capacity."
        ),
        "design": {
            "fixed_belief_for_each_train": FIXED_BELIEF,
            "all_agents_share_values_and_booking_strategy": True,
            "only_capacity_and_number_of_strategic_agents_change": True,
            "no_plan_changes_or_releases": True,
        },
        "profiles": {
            name: _summarize(congestion_profile(name), runs, seed)
            for name in ("light", "balanced", "congested")
        },
    }


def _release_timing_profile() -> NetworkConfig:
    """Market used to estimate q1/q2 for a kept redundant waitlist ticket."""
    return NetworkConfig(
        trains=(Train("A", 1, 5, 10.0), Train("B", 1, 2, 10.0)),
        travellers=(
            Traveller("holder", {"A": 30.0, "B": 0.0}, 0.0, 0, ("A",), {},
                      plan_change_probability=0.25),
            Traveller("redundant_waiter", {"A": 20.0, "B": 40.0}, 0.0, 0,
                      ("A", "B"), {}),
        ),
        time_steps=(1, 2),
        chart_time=3,
        departure_time=3,
        refund_start_time=1,
        refund_bonus=0.0,
        release_friction=1.0,
        waitlist_cancellation_cost=1.0,
        confirmed_cancellation_fee=4.0,
        confirmed_cancellation_fee_schedule=None,
        post_chart_resale_probability=0.0,
        empty_berth_cost=3.0,
    )


def run_c2_release_timing_experiment(runs: int = 10_000, seed: int = 7) -> dict[str, Any]:
    """Compare Eq. (3)'s fixed q beliefs with observed q1/q2 in a kept-ticket run.

    The waiter deliberately does not release. This provides an outcome sample
    for the counterfactual behind Eq. (3): what would happen if the redundant
    ticket were kept until chart time.
    """
    if runs < 1:
        raise ValueError("runs must be positive")
    config = _release_timing_profile()
    rows = [simulate_network(config, seed=seed + index) for index in range(runs)]
    ticket_rows = [row["tickets"]["redundant_waiter/A"] for row in rows]
    q1 = mean(ticket["confirmed_at"] in (1, 2) for ticket in ticket_rows)
    q2 = mean(ticket["confirmed_at"] == 3 for ticket in ticket_rows)
    fixed_inputs = {
        "epsilon": 1.0,
        "q1": 0.10,
        "q2": 0.0,
        "confirmed_cancellation_cost": 4.0,
        "waitlist_cancellation_cost": 1.0,
        "fare": 10.0,
        "beta": 0.0,
        "refund_eligible": True,
    }
    observed_inputs = dict(fixed_inputs, q1=q1, q2=q2)
    return {
        "purpose": (
            "Estimate the kept-ticket q1/q2 quantities used in Eq. (3), then "
            "compare a fixed release belief with the observed-rate decision."
        ),
        "design": {
            "holder_plan_change_probability_per_step": 0.25,
            "plan_change_steps": [1, 2],
            "chart_time": 3,
            "redundant_waiter_keeps_ticket_for_measurement": True,
            "refund_bonus": 0.0,
            "release_friction": 1.0,
        },
        "observed_kept_ticket_outcomes": {
            "runs": runs,
            "q1_confirm_before_chart": q1,
            "q2_confirm_at_chart": q2,
            "chart_cancellation_rate": mean(
                ticket["status"] == "cancelled_waitlist" for ticket in ticket_rows
            ),
        },
        "eq3_with_fixed_belief": release_rule(**fixed_inputs),
        "eq3_with_observed_rates": release_rule(**observed_inputs),
        "note": (
            "The observed rates are a deliberate keep-ticket counterfactual for "
            "this controlled profile; they are not a general railway estimate."
        ),
    }


def _refund_policy_profile(beta: float, eta: float = 0.25) -> NetworkConfig:
    """One redundant waitlister and one follower, for a beta policy sweep."""
    values = {"A": 35.0, "B": 40.0}
    fares = {"A": 10.0, "B": 10.0}
    strategy = build_independent_probability_strategy(
        values=values,
        fares=fares,
        confirmation_probabilities={"A": 0.10, "B": 0.20},
        expected_ticket_costs={"A": 0.10, "B": 1.0},
        outside_option=0.0,
        release_inputs={"A": {
            "q1": 0.10,
            "q2": 0.0,
            "confirmed_cancellation_cost": 4.0,
            "waitlist_cancellation_cost": 1.0,
            "planned_release_time": 1,
        }},
        release_friction=1.0,
        refund_bonus=beta,
        refund_start_time=1,
    )
    return NetworkConfig(
        trains=(Train("A", 1, 5, 10.0), Train("B", 1, 2, 10.0)),
        travellers=(
            Traveller("holder", {"A": 30.0, "B": 0.0}, 0.0, 0, ("A",), {},
                      plan_change_probability=eta),
            Traveller("redundant_waiter", values, 0.0, 0,
                      tuple(strategy["trains_to_book"]), strategy["release_times"],
                      release_waitlisted_only=bool(strategy["release_waitlisted_only"]),
                      strategy_decisions=strategy),
            Traveller("follower", {"A": 25.0, "B": 0.0}, 0.0, 0, ("A",), {}),
        ),
        time_steps=(1, 2),
        chart_time=3,
        departure_time=3,
        refund_start_time=1,
        refund_bonus=beta,
        release_friction=1.0,
        waitlist_cancellation_cost=1.0,
        confirmed_cancellation_fee=4.0,
        confirmed_cancellation_fee_schedule=None,
        post_chart_resale_probability=0.0,
        empty_berth_cost=3.0,
    )


def run_refund_policy_sweep(runs: int = 10_000, seed: int = 7) -> dict[str, Any]:
    """Compare a few beta values under a fixed Eq. (3) belief profile."""
    if runs < 1:
        raise ValueError("runs must be positive")
    results = {}
    for beta in (0.0, 1.0, 2.0):
        config = _refund_policy_profile(beta)
        rows = [simulate_network(config, seed=seed + index) for index in range(runs)]
        release_decision = config.travellers[1].strategy_decisions["release_rule_decisions"]["A"]
        results[str(int(beta))] = {
            "beta": beta,
            "eq3_release_decision": release_decision["release"],
            "eq3_release_gain": release_decision["release_gain"],
            "mean_release_count": mean(row["metrics"]["release_count"] for row in rows),
            "mean_refunds_paid": mean(row["metrics"]["refunds_paid"] for row in rows),
            "mean_empty_berths": mean(row["metrics"]["empty_berths"] for row in rows),
            "mean_travellers_who_travel": mean(row["metrics"]["travellers_who_travel"] for row in rows),
            "mean_traveller_payoff": mean(row["metrics"]["traveller_payoff_sum"] for row in rows),
            "mean_railway_social_welfare_eq4": mean(
                row["metrics"]["railway_social_welfare_eq4"] for row in rows
            ),
            "population_sd_traveller_payoff": pstdev(
                row["metrics"]["traveller_payoff_sum"] for row in rows
            ),
            "population_sd_railway_social_welfare_eq4": pstdev(
                row["metrics"]["railway_social_welfare_eq4"] for row in rows
            ),
        }
    return {
        "purpose": "Sweep refund bonus beta under an Eq. (3) rule-based release policy.",
        "design": {
            "release_belief_q1": 0.10,
            "release_belief_q2": 0.0,
            "release_friction_epsilon": 1.0,
            "holder_plan_change_probability_per_step": 0.25,
            "plan_change_steps": [1, 2],
            "follower_waits_behind_redundant_ticket": True,
            "beta_values": [0.0, 1.0, 2.0],
        },
        "runs": runs,
        "results_by_beta": results,
        "note": (
            "Refunds are transfers in traveller accounting. Eq. (4) nevertheless "
            "subtracts refunds as written, so both traveller payoff and railway "
            "objective are reported."
        ),
    }


def run_refund_eta_sensitivity(runs: int = 10_000, seed: int = 7) -> dict[str, Any]:
    """Test whether the beta=1 allocation effect holds across cancellation rates."""
    if runs < 1:
        raise ValueError("runs must be positive")
    results = {}
    for eta in (0.10, 0.25, 0.50):
        policies = {}
        for beta in (0.0, 1.0):
            config = _refund_policy_profile(beta, eta)
            rows = [simulate_network(config, seed=seed + index) for index in range(runs)]
            policies[str(int(beta))] = {
                "mean_empty_berths": mean(row["metrics"]["empty_berths"] for row in rows),
                "mean_travellers_who_travel": mean(
                    row["metrics"]["travellers_who_travel"] for row in rows
                ),
                "mean_railway_social_welfare_eq4": mean(
                    row["metrics"]["railway_social_welfare_eq4"] for row in rows
                ),
                "population_sd_railway_social_welfare_eq4": pstdev(
                    row["metrics"]["railway_social_welfare_eq4"] for row in rows
                ),
            }
        results[f"{eta:.2f}"] = {
            "eta_per_step": eta,
            "beta_0": policies["0"],
            "beta_1": policies["1"],
            "beta_1_minus_beta_0": {
                metric: policies["1"][metric] - policies["0"][metric]
                for metric in ("mean_empty_berths", "mean_travellers_who_travel",
                               "mean_railway_social_welfare_eq4")
            },
        }
    return {
        "purpose": "Sensitivity of the beta release incentive to plan-change probability eta.",
        "design": {
            "eta_values_per_step": [0.10, 0.25, 0.50],
            "beta_values": [0.0, 1.0],
            "all_other_refund_sweep_assumptions_unchanged": True,
        },
        "runs": runs,
        "results_by_eta": results,
    }
