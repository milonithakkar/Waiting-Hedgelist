"""Small type-based mean-field equilibrium approximation for C3.

This is intentionally a compact benchmark, not a claim that the full
dynamic, private-information proposal has been solved exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from statistics import mean
from typing import Any

from .network import NetworkConfig, Train, Traveller, simulate_network


@dataclass(frozen=True)
class EquilibriumTrain:
    name: str
    capacity: int
    fare: float


@dataclass(frozen=True)
class TravellerType:
    name: str
    count: int
    values: dict[str, float]
    outside_option: float
    expected_ticket_costs: dict[str, float]


@dataclass(frozen=True)
class TypeEquilibriumConfig:
    trains: tuple[EquilibriumTrain, ...]
    types: tuple[TravellerType, ...]

    def __post_init__(self) -> None:
        train_names = {train.name for train in self.trains}
        if not self.trains or not self.types:
            raise ValueError("at least one train and one traveller type are required")
        if len(train_names) != len(self.trains):
            raise ValueError("train names must be unique")
        if len({traveller_type.name for traveller_type in self.types}) != len(self.types):
            raise ValueError("type names must be unique")
        for train in self.trains:
            if train.capacity < 0 or train.fare < 0:
                raise ValueError("train capacity and fare must be nonnegative")
        for traveller_type in self.types:
            if traveller_type.count < 1 or traveller_type.outside_option < 0:
                raise ValueError("type count must be positive and outside option nonnegative")
            if set(traveller_type.values) != train_names:
                raise ValueError(f"{traveller_type.name}: values must cover every train")
            if set(traveller_type.expected_ticket_costs) != train_names:
                raise ValueError(f"{traveller_type.name}: costs must cover every train")


def _actions(train_names: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """All booking sets, ordered deterministically for reproducible ties."""
    return tuple(
        tuple(name for index, name in enumerate(train_names) if mask & (1 << index))
        for mask in range(1 << len(train_names))
    )


def _probabilities(
    config: TypeEquilibriumConfig,
    action_profile: dict[str, tuple[str, ...]],
) -> dict[str, float]:
    demand = {train.name: 0 for train in config.trains}
    for traveller_type in config.types:
        for train in action_profile[traveller_type.name]:
            demand[train] += traveller_type.count
    return {
        train.name: min(1.0, train.capacity / demand[train.name]) if demand[train.name] else 1.0
        for train in config.trains
    }


def _expected_utility(
    traveller_type: TravellerType,
    action: tuple[str, ...],
    probabilities: dict[str, float],
    fares: dict[str, float],
) -> float:
    """Independent-confirmation expected payoff used for the C3 approximation."""
    expected_best = 0.0
    for outcome_mask in range(1 << len(action)):
        probability = 1.0
        confirmed_surpluses = []
        for index, train in enumerate(action):
            confirmed = bool(outcome_mask & (1 << index))
            probability *= probabilities[train] if confirmed else 1.0 - probabilities[train]
            if confirmed:
                confirmed_surpluses.append(traveller_type.values[train] - fares[train])
        expected_best += probability * max([traveller_type.outside_option] + confirmed_surpluses)
    return expected_best - sum(traveller_type.expected_ticket_costs[train] for train in action)


def solve_type_equilibria(config: TypeEquilibriumConfig) -> dict[str, Any]:
    """Enumerate pure type-action profiles and return every mutual best response.

    For a deviation by one type, all members of that type use the same
    candidate action. This is a finite, mean-field approximation: it treats
    confirmation events as independent conditional on type-level demand.
    """
    train_names = tuple(train.name for train in config.trains)
    fares = {train.name: train.fare for train in config.trains}
    actions = _actions(train_names)
    equilibria = []
    checked = 0
    for choices in product(actions, repeat=len(config.types)):
        profile = {traveller_type.name: action
                   for traveller_type, action in zip(config.types, choices)}
        probabilities = _probabilities(config, profile)
        best_responses: dict[str, list[tuple[str, ...]]] = {}
        profile_utilities: dict[str, float] = {}
        is_equilibrium = True
        for traveller_type in config.types:
            utilities = {}
            for candidate in actions:
                candidate_profile = dict(profile)
                candidate_profile[traveller_type.name] = candidate
                candidate_probabilities = _probabilities(config, candidate_profile)
                utilities[candidate] = _expected_utility(
                    traveller_type, candidate, candidate_probabilities, fares
                )
            max_utility = max(utilities.values())
            responses = [action for action in actions if abs(utilities[action] - max_utility) < 1e-12]
            best_responses[traveller_type.name] = responses
            profile_utilities[traveller_type.name] = utilities[profile[traveller_type.name]]
            if profile[traveller_type.name] not in responses:
                is_equilibrium = False
        checked += 1
        if is_equilibrium:
            equilibria.append({
                "actions_by_type": {name: list(action) for name, action in profile.items()},
                "confirmation_probabilities": probabilities,
                "utility_per_traveller_by_type": profile_utilities,
                "best_responses_by_type": {
                    name: [list(action) for action in actions]
                    for name, actions in best_responses.items()
                },
            })
    return {
        "profiles_checked": checked,
        "pure_equilibria_found": len(equilibria),
        "equilibria": equilibria,
        "assumptions": [
            "travellers are grouped into homogeneous types",
            "all members of a type use the same booking set",
            "type-level confirmation probability is min(1, capacity / expected demand)",
            "confirmations across trains are independent in the equilibrium approximation",
            "expected unused-ticket costs are supplied constants",
            "release timing, plan changes, and learning are omitted from this C3 booking equilibrium",
        ],
    }


def compare_equilibrium_with_event_simulation(
    config: TypeEquilibriumConfig,
    equilibrium_index: int = 0,
    runs: int = 1_000,
    seed: int = 7,
) -> dict[str, Any]:
    """Replay a type equilibrium in the event model and compare confirmation.

    The replay intentionally has no plan changes, releases, resale, or refunds.
    It isolates the static capacity approximation used by the type equilibrium.
    """
    solution = solve_type_equilibria(config)
    equilibria = solution["equilibria"]
    if not equilibria:
        raise ValueError("no pure equilibrium exists for this configuration")
    if not 0 <= equilibrium_index < len(equilibria):
        raise ValueError(f"equilibrium_index must be between 0 and {len(equilibria) - 1}")
    selected = equilibria[equilibrium_index]
    action_by_type = selected["actions_by_type"]
    network_travellers = []
    for traveller_type in config.types:
        for index in range(traveller_type.count):
            network_travellers.append(Traveller(
                name=f"{traveller_type.name}_{index}",
                values=traveller_type.values,
                outside_option=traveller_type.outside_option,
                booking_time=0,
                trains_to_book=tuple(action_by_type[traveller_type.name]),
                release_times={},
            ))
    network = NetworkConfig(
        trains=tuple(Train(train.name, train.capacity, 1000, train.fare)
                     for train in config.trains),
        travellers=tuple(network_travellers),
        time_steps=(0,),
        chart_time=1,
        departure_time=1,
        refund_start_time=0,
        refund_bonus=0.0,
        release_friction=0.0,
        waitlist_cancellation_cost=0.0,
        confirmed_cancellation_fee=0.0,
        confirmed_cancellation_fee_schedule=None,
        post_chart_resale_probability=0.0,
        empty_berth_cost=0.0,
    )
    rows = [simulate_network(network, seed=seed + index) for index in range(runs)]
    observed = {
        train.name: mean(row["trains"][train.name]["confirmation_probability_excluding_censored"]
                         for row in rows)
        for train in config.trains
    }
    type_rates = {}
    for traveller_type in config.types:
        action = tuple(action_by_type[traveller_type.name])
        type_rates[traveller_type.name] = {
            train: sum(
                row["tickets"][f"{traveller_type.name}_{index}/{train}"]["ever_confirmed"]
                for row in rows for index in range(traveller_type.count)
            ) / (runs * traveller_type.count)
            for train in action
        }
    pair_results = {}
    for traveller_type in config.types:
        action = tuple(action_by_type[traveller_type.name])
        if len(action) != 2:
            continue
        first, second = sorted(action)
        total = traveller_type.count * runs
        joint = sum(
            row["tickets"][f"{traveller_type.name}_{index}/{first}"]["ever_confirmed"]
            and row["tickets"][f"{traveller_type.name}_{index}/{second}"]["ever_confirmed"]
            for row in rows for index in range(traveller_type.count)
        ) / total
        first_rate = sum(
            row["tickets"][f"{traveller_type.name}_{index}/{first}"]["ever_confirmed"]
            for row in rows for index in range(traveller_type.count)
        ) / total
        second_rate = sum(
            row["tickets"][f"{traveller_type.name}_{index}/{second}"]["ever_confirmed"]
            for row in rows for index in range(traveller_type.count)
        ) / total
        pair_results[traveller_type.name] = {
            "trains": [first, second],
            "observed_joint_confirmation": joint,
            "observed_product_of_marginals": first_rate * second_rate,
            "joint_minus_product": joint - first_rate * second_rate,
        }
    return {
        "equilibrium_index": equilibrium_index,
        "equilibrium_actions_by_type": action_by_type,
        "mean_field_confirmation_probabilities": selected["confirmation_probabilities"],
        "event_simulator_confirmation_probabilities": observed,
        "event_minus_mean_field_probability": {
            train: observed[train] - selected["confirmation_probabilities"][train]
            for train in observed
        },
        "event_simulator_confirmation_by_type": type_rates,
        "event_minus_mean_field_probability_by_type": {
            traveller_type.name: {
                train: rate - selected["confirmation_probabilities"][train]
                for train, rate in type_rates[traveller_type.name].items()
            }
            for traveller_type in config.types
        },
        "event_simulator_joint_checks": pair_results,
        "runs": runs,
        "replay_assumptions": [
            "equilibrium actions are fixed during replay",
            "no plan changes, releases, refunds, resale, or unused-ticket costs",
            "FIFO and input order remain active in the event simulator",
        ],
    }


def config_from_dict(raw: dict[str, Any]) -> TypeEquilibriumConfig:
    return TypeEquilibriumConfig(
        trains=tuple(EquilibriumTrain(**item) for item in raw["trains"]),
        types=tuple(TravellerType(**item) for item in raw["types"]),
    )
