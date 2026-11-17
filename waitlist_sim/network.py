"""Discrete-event, multi-train waitlist model for proposal mechanics.

The paper does not specify tie-breaking, within-tick event order, or how often
the plan-change hazard is sampled. This module makes those choices explicit:
bookings are processed in input order, then plan changes, then scheduled
releases, and plan changes are sampled once on each configured time step.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

from .proposal_rules import build_independent_probability_strategy


@dataclass(frozen=True)
class Train:
    name: str
    capacity: int
    waitlist_cap: int
    fare: float

    def __post_init__(self) -> None:
        if self.capacity < 0 or self.waitlist_cap < 0:
            raise ValueError("train capacity and waitlist_cap must be nonnegative")
        if self.fare < 0:
            raise ValueError("train fare must be nonnegative")


@dataclass(frozen=True)
class Traveller:
    name: str
    values: dict[str, float]
    outside_option: float
    booking_time: int
    trains_to_book: tuple[str, ...]
    release_times: dict[str, int | None]
    plan_change_probability: float = 0.0
    release_waitlisted_only: bool = False
    strategy_decisions: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.plan_change_probability <= 1:
            raise ValueError("plan_change_probability must be in [0, 1]")
        if self.outside_option < 0 or any(v < 0 for v in self.values.values()):
            raise ValueError("outside option and train values must be nonnegative")
        if len(set(self.trains_to_book)) != len(self.trains_to_book):
            raise ValueError(f"{self.name}: duplicate train in booking set")
        if any(t not in self.trains_to_book for t in self.release_times):
            raise ValueError(f"{self.name}: release time supplied for a train not booked")


@dataclass(frozen=True)
class NetworkConfig:
    trains: tuple[Train, ...]
    travellers: tuple[Traveller, ...]
    time_steps: tuple[int, ...]
    chart_time: int
    departure_time: int
    refund_start_time: int
    refund_bonus: float
    release_friction: float
    waitlist_cancellation_cost: float
    confirmed_cancellation_fee: float
    confirmed_cancellation_fee_schedule: dict[int, float] | None
    post_chart_resale_probability: float
    empty_berth_cost: float

    def __post_init__(self) -> None:
        if not self.trains:
            raise ValueError("at least one train is required")
        if not self.time_steps or tuple(sorted(set(self.time_steps))) != self.time_steps:
            raise ValueError("time_steps must be nonempty, unique, and increasing")
        if self.chart_time > self.departure_time:
            raise ValueError("chart_time cannot be after departure_time")
        if any(time > self.departure_time for time in self.time_steps):
            raise ValueError("time_steps cannot extend past departure_time")
        if self.refund_start_time > self.departure_time:
            raise ValueError("refund_start_time cannot be after departure_time")
        if not 0 <= self.post_chart_resale_probability <= 1:
            raise ValueError("post_chart_resale_probability must be in [0, 1]")
        if min(self.refund_bonus, self.release_friction,
               self.waitlist_cancellation_cost, self.confirmed_cancellation_fee,
               self.empty_berth_cost) < 0:
            raise ValueError("costs and refund bonus must be nonnegative")
        if self.confirmed_cancellation_fee_schedule and min(
            self.confirmed_cancellation_fee_schedule.values()
        ) < 0:
            raise ValueError("scheduled cancellation fees must be nonnegative")
        train_names = [train.name for train in self.trains]
        traveller_names = [traveller.name for traveller in self.travellers]
        if len(set(train_names)) != len(train_names):
            raise ValueError("train names must be unique")
        if len(set(traveller_names)) != len(traveller_names):
            raise ValueError("traveller names must be unique")
        known = set(train_names)
        for traveller in self.travellers:
            if set(traveller.values) != known:
                raise ValueError(f"{traveller.name}: values must be provided for every train")
            if not set(traveller.trains_to_book) <= known:
                raise ValueError(f"{traveller.name}: booking set contains an unknown train")
            if traveller.booking_time > self.chart_time:
                raise ValueError(f"{traveller.name}: bookings after chart time are unsupported")
            if any(t is not None and not traveller.booking_time <= t <= self.departure_time
                   for t in traveller.release_times.values()):
                raise ValueError(f"{traveller.name}: release time must be between booking and departure")


def _confirmed_cancel_fee(time: int, config: NetworkConfig) -> float:
    """Use f_C(t) when supplied, with the flat fee as the default schedule."""
    schedule = config.confirmed_cancellation_fee_schedule or {}
    return schedule.get(time, config.confirmed_cancellation_fee)


def simulate_network(config: NetworkConfig, seed: int = 0) -> dict[str, Any]:
    """Simulate bookings, waitlists, plan changes, releases, and charting once."""
    rng = random.Random(seed)
    train_by_name = {train.name: train for train in config.trains}
    traveller_by_name = {traveller.name: traveller for traveller in config.travellers}
    # status values: confirmed, waitlisted, refused, cancelled_waitlist,
    # cancelled_confirmed, released_waitlist, released_confirmed.
    tickets: dict[tuple[str, str], dict[str, Any]] = {}
    queues = {train.name: [] for train in config.trains}
    confirmed = {train.name: set() for train in config.trains}
    resold = {train.name: 0 for train in config.trains}
    cancelled_travellers: set[str] = set()
    release_events: list[dict[str, Any]] = []
    ticket_costs = {traveller.name: 0.0 for traveller in config.travellers}
    chart_processed = False

    event_times = set(config.time_steps) | {config.chart_time, config.departure_time}
    for traveller in config.travellers:
        event_times.add(traveller.booking_time)
        event_times.update(t for t in traveller.release_times.values() if t is not None)

    def promote(train_name: str, time: int) -> None:
        """Assign a newly free pre-chart berth to the first live waitlister."""
        while queues[train_name]:
            next_traveller = queues[train_name].pop(0)
            ticket = tickets[(next_traveller, train_name)]
            if ticket["status"] != "waitlisted" or next_traveller in cancelled_travellers:
                continue
            ticket["status"] = "confirmed"
            ticket["ever_confirmed"] = True
            ticket["confirmed_at"] = time
            confirmed[train_name].add(next_traveller)
            break

    def cancel_ticket(traveller_name: str, train_name: str, time: int,
                      voluntary_release: bool = False,
                      cancellation_reason: str = "plan_change") -> None:
        key = (traveller_name, train_name)
        ticket = tickets.get(key)
        if ticket is None or ticket["status"] not in ("confirmed", "waitlisted"):
            return
        old_status = ticket["status"]
        if old_status == "waitlisted":
            ticket["status"] = "released_waitlist" if voluntary_release else "cancelled_waitlist"
            ticket["cancellation_reason"] = "scheduled_release" if voluntary_release else cancellation_reason
            if traveller_name in queues[train_name]:
                queues[train_name].remove(traveller_name)
            ticket_costs[traveller_name] += config.waitlist_cancellation_cost
        else:
            ticket["status"] = "released_confirmed" if voluntary_release else "cancelled_confirmed"
            ticket["cancellation_reason"] = "scheduled_release" if voluntary_release else cancellation_reason
            confirmed[train_name].discard(traveller_name)
            ticket_costs[traveller_name] += _confirmed_cancel_fee(time, config)
            if time <= config.chart_time:
                promote(train_name, time)
            elif rng.random() < config.post_chart_resale_probability:
                resold[train_name] += 1
        if voluntary_release:
            eligible = time >= config.refund_start_time
            release_events.append({"traveller": traveller_name, "train": train_name,
                                   "time": time, "refund_eligible": eligible})

    def is_redundant(traveller_name: str, train_name: str) -> bool:
        current = tickets[(traveller_name, train_name)]
        if current["status"] not in ("confirmed", "waitlisted"):
            return False
        traveller = traveller_by_name[traveller_name]
        current_surplus = traveller.values[train_name] - train_by_name[train_name].fare
        other_surpluses = [
            traveller.values[other] - train_by_name[other].fare
            for (owner, other), ticket in tickets.items()
            if owner == traveller_name and other != train_name
            and ticket["status"] == "confirmed"
        ]
        return any(surplus > current_surplus for surplus in other_surpluses)

    for time in sorted(event_times):
        # 1. Process bookings at this time in declared traveller/train order.
        for traveller in config.travellers:
            if traveller.booking_time != time or traveller.name in cancelled_travellers:
                continue
            for train_name in traveller.trains_to_book:
                key = (traveller.name, train_name)
                if key in tickets:
                    continue
                spec = train_by_name[train_name]
                occupied = len(confirmed[train_name]) + resold[train_name]
                if occupied < spec.capacity:
                    status = "confirmed"
                    confirmed[train_name].add(traveller.name)
                elif len(queues[train_name]) < spec.waitlist_cap:
                    status = "waitlisted"
                    queues[train_name].append(traveller.name)
                else:
                    status = "refused"
                tickets[key] = {
                    "status": status,
                    "booked_at": time,
                    "initial_status": status,
                    "ever_confirmed": status == "confirmed",
                    "confirmed_at": time if status == "confirmed" else None,
                }

        # 2. Plan changes cancel all active tickets for that traveller.
        if time in config.time_steps:
            for traveller in config.travellers:
                if traveller.name in cancelled_travellers:
                    continue
                if not any(owner == traveller.name and ticket["status"] in ("confirmed", "waitlisted")
                           for (owner, _), ticket in tickets.items()):
                    continue
                if rng.random() < traveller.plan_change_probability:
                    cancelled_travellers.add(traveller.name)
                    for (owner, train_name), ticket in list(tickets.items()):
                        if owner == traveller.name:
                            cancel_ticket(owner, train_name, time)

        # 3. Execute scheduled releases only when a better confirmed option exists.
        for traveller in config.travellers:
            if traveller.name in cancelled_travellers:
                continue
            for train_name, release_time in traveller.release_times.items():
                if release_time != time or (traveller.name, train_name) not in tickets:
                    continue
                if (traveller.release_waitlisted_only
                        and tickets[(traveller.name, train_name)]["status"] != "waitlisted"):
                    continue
                if is_redundant(traveller.name, train_name):
                    cancel_ticket(traveller.name, train_name, time, voluntary_release=True)

        # 4. The chart cancels all remaining waitlisted tickets; they no longer
        # receive a berth released later.
        if time == config.chart_time and not chart_processed:
            chart_processed = True
            for train_name in queues:
                for traveller_name in list(queues[train_name]):
                    ticket = tickets[(traveller_name, train_name)]
                    if ticket["status"] == "waitlisted":
                        ticket["status"] = "cancelled_waitlist"
                        ticket["cancellation_reason"] = "chart"
                        ticket_costs[traveller_name] += config.waitlist_cancellation_cost
                queues[train_name].clear()

    # Select at most one trip per traveller, comparing net trip surplus with
    # their outside option. Ties favor the outside option, matching max().
    traveller_results: dict[str, dict[str, Any]] = {}
    used: dict[str, str | None] = {}
    traveler_value_total = outside_value_total = 0.0
    for traveller in config.travellers:
        candidates = [
            (traveller.values[train_name] - train_by_name[train_name].fare, train_name)
            for (owner, train_name), ticket in tickets.items()
            if owner == traveller.name and ticket["status"] == "confirmed"
        ]
        best_surplus, best_train = max(candidates, default=(None, None), key=lambda x: float("-inf") if x[0] is None else x[0])
        if traveller.name in cancelled_travellers or best_surplus is None or best_surplus <= traveller.outside_option:
            used_train = None
            outside_value_total += traveller.outside_option
        else:
            used_train = best_train
            traveler_value_total += traveller.values[used_train]
        used[traveller.name] = used_train
        for (owner, train_name), ticket in tickets.items():
            if owner != traveller.name:
                continue
            if ticket["status"] == "confirmed" and train_name != used_train:
                ticket_costs[traveller.name] += train_by_name[train_name].fare
        traveller_results[traveller.name] = {
            "travels": used_train is not None,
            "chosen_train": used_train,
            "outside_option": traveller.outside_option,
            "unused_ticket_costs": ticket_costs[traveller.name],
            "plan_changed": traveller.name in cancelled_travellers,
        }

    train_results: dict[str, dict[str, Any]] = {}
    empty_berths = 0
    for train in config.trains:
        travelers_on_train = sum(choice == train.name for choice in used.values())
        empty = train.capacity - travelers_on_train - resold[train.name]
        empty_berths += empty
        train_tickets = [ticket for (owner, name), ticket in tickets.items()
                         if name == train.name and ticket["initial_status"] != "refused"]
        initial_waitlist = [ticket for ticket in train_tickets
                            if ticket["initial_status"] == "waitlisted"]
        q_observations = [
            ticket for ticket in initial_waitlist
            if ticket["ever_confirmed"]
            or ticket.get("cancellation_reason") not in ("plan_change", "scheduled_release")
        ]
        q1_count = sum(ticket["confirmed_at"] is not None
                       and ticket["confirmed_at"] < config.chart_time
                       for ticket in q_observations)
        q2_count = sum(ticket["confirmed_at"] == config.chart_time
                       for ticket in q_observations)
        confirmation_observations = [
            ticket for ticket in train_tickets
            if ticket["ever_confirmed"]
            or ticket.get("cancellation_reason") not in ("plan_change", "scheduled_release")
        ]
        confirmation_successes = sum(ticket["ever_confirmed"]
                                      for ticket in confirmation_observations)
        train_results[train.name] = {
            "capacity": train.capacity,
            "waitlist_cap": train.waitlist_cap,
            "confirmed_at_departure": len(confirmed[train.name]),
            "waitlisted_at_departure": len(queues[train.name]),
            "resold_after_chart": resold[train.name],
            "travellers": travelers_on_train,
            "empty_berths": empty,
            "accepted_tickets": len(train_tickets),
            "ever_confirmed_tickets": sum(ticket["ever_confirmed"] for ticket in train_tickets),
            "accepted_ticket_ever_confirmation_rate": (
                sum(ticket["ever_confirmed"] for ticket in train_tickets) / len(train_tickets)
                if train_tickets else 0.0
            ),
            "confirmation_probability_observations": len(confirmation_observations),
            "confirmation_probability_successes": confirmation_successes,
            "confirmation_probability_excluding_censored": (
                confirmation_successes / len(confirmation_observations)
                if confirmation_observations else 0.0
            ),
            "initial_waitlist_tickets": len(initial_waitlist),
            "q1_q2_observations_excluding_censored": len(q_observations),
            "waitlisted_confirmed_before_chart": q1_count,
            "waitlisted_confirmed_at_chart": q2_count,
            "q1_rate_among_uncensored_initial_waitlist_tickets": (
                q1_count / len(q_observations) if q_observations else 0.0
            ),
            "q2_rate_among_uncensored_initial_waitlist_tickets": (
                q2_count / len(q_observations) if q_observations else 0.0
            ),
        }

    eligible_releases = sum(event["refund_eligible"] for event in release_events)
    refund_paid = eligible_releases * config.refund_bonus
    unused_cost_total = sum(ticket_costs.values())
    total_payoff = sum(
        max(traveller.outside_option,
            traveller.values[used[traveller.name]] - train_by_name[used[traveller.name]].fare)
        if used[traveller.name] is not None else traveller.outside_option
        for traveller in config.travellers
    ) - unused_cost_total + refund_paid - config.release_friction * len(release_events)
    social_welfare = (traveler_value_total + outside_value_total
                      - config.empty_berth_cost * empty_berths - refund_paid)
    return {
        "seed": seed,
        "travellers": traveller_results,
        "strategy_profiles": {
            traveller.name: {
                "trains_to_book": list(traveller.trains_to_book),
                "release_times": traveller.release_times,
                "release_waitlisted_only": traveller.release_waitlisted_only,
                "rule_decisions": traveller.strategy_decisions,
            }
            for traveller in config.travellers
        },
        "trains": train_results,
        "tickets": {f"{traveller}/{train}": ticket for (traveller, train), ticket in tickets.items()},
        "releases": release_events,
        "metrics": {
            "travellers": len(config.travellers),
            "travellers_who_travel": sum(value is not None for value in used.values()),
            "empty_berths": empty_berths,
            "refunds_paid": refund_paid,
            "eligible_releases": eligible_releases,
            "release_count": len(release_events),
            "unused_ticket_costs_paid_by_travellers": unused_cost_total,
            "traveller_payoff_sum": total_payoff,
            "railway_social_welfare_eq4": social_welfare,
        },
        "assumptions": [
            "discrete time; plan-change hazard sampled once on each configured time step",
            "same-time ordering: bookings, plan changes, scheduled releases, then chart cancellations",
            "input order breaks booking ties; waitlists are first-in-first-out",
            "a scheduled release occurs only if another confirmed train makes the ticket redundant",
            "travellers choose the best confirmed train by value minus fare, or their outside option",
            "refunds are transfers and are reported separately; Eq. (4) subtracts refunds as specified",
            "resold berths count as occupied but resale buyers are not modeled as traveller agents",
        ],
    }


def network_config_from_dict(raw: dict[str, Any]) -> NetworkConfig:
    """Build a validated config from a JSON-decoded object."""
    train_specs = tuple(Train(**item) for item in raw["trains"])
    fares = {train.name: train.fare for train in train_specs}

    def make_traveller(item: dict[str, Any]) -> Traveller:
        strategy = item.get("strategy")
        decisions = None
        if strategy is not None:
            decisions = build_independent_probability_strategy(
                values=item["values"],
                fares=fares,
                confirmation_probabilities=strategy["confirmation_probabilities"],
                expected_ticket_costs=strategy["expected_ticket_costs"],
                outside_option=item.get("outside_option", 0.0),
                release_inputs=strategy.get("release_inputs", {}),
                release_friction=raw["release_friction"],
                refund_bonus=raw["refund_bonus"],
                refund_start_time=raw["refund_start_time"],
            )
        return Traveller(
            name=item["name"], values=item["values"],
            outside_option=item.get("outside_option", 0.0),
            booking_time=item["booking_time"],
            trains_to_book=tuple(decisions["trains_to_book"] if decisions is not None
                                 else item["trains_to_book"]),
            release_times=(decisions["release_times"] if decisions is not None
                           else item.get("release_times", {})),
            plan_change_probability=item.get("plan_change_probability", 0.0),
            release_waitlisted_only=(bool(decisions["release_waitlisted_only"])
                                     if decisions is not None
                                     else item.get("release_waitlisted_only", False)),
            strategy_decisions=decisions,
        )

    fee_schedule = raw.get("confirmed_cancellation_fee_schedule")
    if fee_schedule is not None:
        fee_schedule = {int(time): fee for time, fee in fee_schedule.items()}
    return NetworkConfig(
        trains=train_specs,
        travellers=tuple(make_traveller(item) for item in raw["travellers"]),
        time_steps=tuple(raw["time_steps"]),
        chart_time=raw["chart_time"],
        departure_time=raw["departure_time"],
        refund_start_time=raw["refund_start_time"],
        refund_bonus=raw["refund_bonus"],
        release_friction=raw["release_friction"],
        waitlist_cancellation_cost=raw["waitlist_cancellation_cost"],
        confirmed_cancellation_fee=raw["confirmed_cancellation_fee"],
        confirmed_cancellation_fee_schedule=fee_schedule,
        post_chart_resale_probability=raw["post_chart_resale_probability"],
        empty_berth_cost=raw["empty_berth_cost"],
    )
