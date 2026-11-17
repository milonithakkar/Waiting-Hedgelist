"""Small, reproducible baseline model for interacting waitlist decisions.

Model choices are deliberately explicit and provisional; see README.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import random
from typing import Any


@dataclass(frozen=True)
class TravellerType:
    name: str
    count: int
    value: float
    hedge_fee: float
    missed_trip_cost: float
    hedge_probability: float

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError(f"{self.name}: count must be nonnegative")
        if not 0 <= self.hedge_probability <= 1:
            raise ValueError(f"{self.name}: hedge_probability must be in [0, 1]")
        if min(self.value, self.hedge_fee, self.missed_trip_cost) < 0:
            raise ValueError(f"{self.name}: monetary parameters must be nonnegative")


@dataclass(frozen=True)
class Config:
    capacity: int
    types: tuple[TravellerType, ...]
    refund_if_unconfirmed: float = 0.0
    fare: float = 0.0

    def __post_init__(self) -> None:
        if self.capacity < 0:
            raise ValueError("capacity must be nonnegative")
        if min(self.refund_if_unconfirmed, self.fare) < 0:
            raise ValueError("refund and fare must be nonnegative")


AllocationPolicy = Callable[[list[dict[str, Any]], int, random.Random], None]


def hedgers_first(agents: list[dict[str, Any]], capacity: int, rng: random.Random) -> None:
    """Confirm hedgers first, sampling uniformly within each priority class."""
    hedged = [a for a in agents if a["hedged"]]
    unhedged = [a for a in agents if not a["hedged"]]
    rng.shuffle(hedged)
    rng.shuffle(unhedged)
    confirmed_hedged = min(capacity, len(hedged))
    for agent in hedged[:confirmed_hedged]:
        agent["confirmed"] = True
    for agent in unhedged[: capacity - confirmed_hedged]:
        agent["confirmed"] = True


def lottery(agents: list[dict[str, Any]], capacity: int, rng: random.Random) -> None:
    """Confirm uniformly from all travellers, regardless of hedge choice."""
    order = list(agents)
    rng.shuffle(order)
    for agent in order[:capacity]:
        agent["confirmed"] = True


POLICIES: dict[str, AllocationPolicy] = {
    "hedgers_first": hedgers_first,
    "lottery": lottery,
}


def simulate(
    config: Config,
    seed: int = 0,
    policy: str = "hedgers_first",
) -> dict[str, Any]:
    """Run one capacity-constrained instance and return outcomes and accounts.

    Hedged agents are prioritized, but within each priority group seats are
    sampled uniformly. Hedges are independent private choices conditional on
    each type's configured probability; confirmations are coupled by capacity.
    """
    rng = random.Random(seed)
    agents: list[dict[str, Any]] = []
    for traveller_type in config.types:
        for _ in range(traveller_type.count):
            hedged = rng.random() < traveller_type.hedge_probability
            agents.append({"type": traveller_type, "hedged": hedged, "confirmed": False})

    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; choose from {', '.join(POLICIES)}")
    POLICIES[policy](agents, config.capacity, rng)

    type_results: dict[str, dict[str, float | int]] = {}
    traveller_value = total_hedge_fees = missed_trip_cost = 0.0
    fare_revenue = 0.0
    refunds = 0.0
    confirmed_count = hedge_count = 0
    confirmed_hedged = hedged_count = 0
    confirmed_unhedged = unhedged_count = 0
    for traveller_type in config.types:
        group = [a for a in agents if a["type"].name == traveller_type.name]
        confirmed = sum(a["confirmed"] for a in group)
        hedged_count = sum(a["hedged"] for a in group)
        confirmed_hedge = sum(a["confirmed"] and a["hedged"] for a in group)
        confirmed_no_hedge = sum(a["confirmed"] and not a["hedged"] for a in group)
        unhedge_count = len(group) - hedged_count
        unconfirmed = len(group) - confirmed
        fees = hedged_count * traveller_type.hedge_fee
        refund = unconfirmed * config.refund_if_unconfirmed
        group_missed_cost = unconfirmed * traveller_type.missed_trip_cost
        type_results[traveller_type.name] = {
            "population": len(group),
            "hedged": hedged_count,
            "confirmed": confirmed,
            "unconfirmed": unconfirmed,
            "confirmation_rate": confirmed / len(group) if group else 0.0,
            "hedge_rate": hedged_count / len(group) if group else 0.0,
            "confirmed_hedged": confirmed_hedge,
            "unconfirmed_hedged": hedged_count - confirmed_hedge,
            "confirmed_unhedged": confirmed_no_hedge,
            "unconfirmed_unhedged": unhedge_count - confirmed_no_hedge,
            "hedge_fees_paid": fees,
            "refunds_received": refund,
            "missed_trip_cost": group_missed_cost,
        }
        traveller_value += confirmed * traveller_type.value
        total_hedge_fees += fees
        missed_trip_cost += group_missed_cost
        refunds += refund
        confirmed_count += confirmed
        hedge_count += hedged_count
        confirmed_hedged += confirmed_hedge
        confirmed_unhedged += confirmed_no_hedge
        # Keep denominators for pooled conditional confirmation rates.
        unhedged_count += unhedge_count
        fare_revenue += confirmed * config.fare

    return {
        "seed": seed,
        "policy": policy,
        "capacity": config.capacity,
        "population": len(agents),
        "hedged": hedge_count,
        "unhedged": unhedged_count,
        "confirmed": confirmed_count,
        "confirmed_hedged": confirmed_hedged,
        "confirmed_unhedged": confirmed_unhedged,
        "unconfirmed": len(agents) - confirmed_count,
        "confirmation_rate": confirmed_count / len(agents) if agents else 0.0,
        "hedge_rate": hedge_count / len(agents) if agents else 0.0,
        "confirmation_rate_given_hedging": confirmed_hedged / hedge_count if hedge_count else 0.0,
        "confirmation_rate_without_hedging": confirmed_unhedged / unhedged_count if unhedged_count else 0.0,
        "traveller_value_of_confirmed_trips": traveller_value,
        "hedge_fees_paid": total_hedge_fees,
        "fare_revenue": fare_revenue,
        "railway_gross_receipts": fare_revenue + total_hedge_fees,
        "refunds_transferred_to_travellers": refunds,
        "railway_net_cash_flow": fare_revenue + total_hedge_fees - refunds,
        "missed_trip_resource_cost": missed_trip_cost,
        "social_resource_cost": missed_trip_cost,
        "types": type_results,
        "assumptions": [
            f"allocation policy: {policy}",
            "refunds are transfers, excluded from social_resource_cost",
        ],
    }
