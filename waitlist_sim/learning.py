"""Repeated-experience learning benchmark for Eq. (2) traveller agents."""

from __future__ import annotations

from statistics import mean
from typing import Any

from .network import NetworkConfig, Train, Traveller, simulate_network
from .proposal_rules import build_independent_probability_strategy


def run_belief_learning_experiment(episodes: int = 30, seed: int = 7) -> dict[str, Any]:
    """Let homogeneous agents update Beta confirmation beliefs after episodes.

    This is a deliberately simple learning rule: each agent retains independent
    Beta(alpha, beta) posteriors per train and uses posterior means as Eq. (2)
    input probabilities in the next episode. A chart cancellation is a failed
    confirmation observation. Agents do not observe other agents' tickets.
    """
    if episodes < 1:
        raise ValueError("episodes must be positive")
    train_names = ("A", "B")
    fares = {"A": 10.0, "B": 10.0}
    values = {"A": 40.0, "B": 32.0}
    costs = {"A": 2.0, "B": 1.0}
    agent_names = [f"learner_{index}" for index in range(8)]
    posterior = {
        agent: {train: [4.0, 1.0] for train in train_names}
        for agent in agent_names
    }
    trajectory = []
    for episode in range(episodes):
        strategies = {}
        travellers = []
        beliefs_before = {train: [] for train in train_names}
        for agent in agent_names:
            beliefs = {
                train: posterior[agent][train][0] / sum(posterior[agent][train])
                for train in train_names
            }
            for train in train_names:
                beliefs_before[train].append(beliefs[train])
            strategy = build_independent_probability_strategy(
                values=values,
                fares=fares,
                confirmation_probabilities=beliefs,
                expected_ticket_costs=costs,
                outside_option=0.0,
            )
            strategies[agent] = strategy
            travellers.append(Traveller(
                name=agent,
                values=values,
                outside_option=0.0,
                booking_time=0,
                trains_to_book=tuple(strategy["trains_to_book"]),
                release_times={},
                strategy_decisions=strategy,
            ))
        market = NetworkConfig(
            trains=(Train("A", 3, 20, fares["A"]), Train("B", 3, 20, fares["B"])),
            travellers=tuple(travellers),
            time_steps=(0,),
            chart_time=1,
            departure_time=1,
            refund_start_time=0,
            refund_bonus=0.0,
            release_friction=0.0,
            waitlist_cancellation_cost=1.0,
            confirmed_cancellation_fee=4.0,
            confirmed_cancellation_fee_schedule=None,
            post_chart_resale_probability=0.0,
            empty_berth_cost=3.0,
        )
        result = simulate_network(market, seed=seed + episode)
        observed = {train: [] for train in train_names}
        for agent in agent_names:
            for train in strategies[agent]["trains_to_book"]:
                ticket = result["tickets"][f"{agent}/{train}"]
                success = ticket["ever_confirmed"]
                posterior[agent][train][0 if success else 1] += 1.0
                observed[train].append(float(success))
        trajectory.append({
            "episode": episode + 1,
            "mean_beliefs_before_booking": {
                train: mean(beliefs_before[train]) for train in train_names
            },
            "bookings_by_train": {
                train: sum(train in strategies[agent]["trains_to_book"] for agent in agent_names)
                for train in train_names
            },
            "observed_confirmation_rate": {
                train: mean(observed[train]) if observed[train] else None
                for train in train_names
            },
            "mean_beliefs_after_update": {
                train: mean(posterior[agent][train][0] / sum(posterior[agent][train])
                            for agent in agent_names)
                for train in train_names
            },
        })
    return {
        "purpose": "Repeated agents learn train confirmation beliefs from their own outcomes.",
        "design": {
            "agents": len(agent_names),
            "capacity_per_train": 3,
            "initial_beta_posterior": {"alpha": 4, "beta": 1},
            "update": "add one to alpha for ever-confirmed ticket; add one to beta otherwise",
            "private_observation": True,
            "rule": "posterior means enter Eq. (2) each episode",
        },
        "episodes": episodes,
        "trajectory": trajectory,
        "final_mean_beliefs": trajectory[-1]["mean_beliefs_after_update"],
        "limitations": [
            "agents update only from tickets they booked",
            "the posterior treats ticket outcomes as independent observations",
            "release learning and q1/q2 learning are not included",
        ],
    }
