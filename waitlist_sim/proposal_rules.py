"""Direct implementations of proposal rules (1)--(3).

Probability inputs are supplied by a caller. The independent-probability
benchmark uses fixed values; an interaction-aware caller can estimate them
from simulation histories and pass those instead.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def _probability(value: float, label: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return value


def hedge_rule(
    *,
    p_k: float,
    higher_value_train_probabilities: Iterable[float],
    value_k: float,
    fallback: float,
    expected_cost_k: float,
) -> dict[str, float | bool]:
    """Evaluate Eq. (2): add train k if expected incremental value > cost."""
    p_k = _probability(p_k, "p_k")
    product = 1.0
    for index, probability in enumerate(higher_value_train_probabilities):
        product *= 1.0 - _probability(probability, f"higher-value train probability {index}")
    gain = p_k * product * (value_k - fallback)
    return {"expected_gain": gain, "expected_cost": expected_cost_k,
            "hedge": gain > expected_cost_k}


def release_rule(
    *,
    epsilon: float,
    q1: float,
    q2: float,
    confirmed_cancellation_cost: float,
    waitlist_cancellation_cost: float,
    fare: float,
    beta: float,
    refund_eligible: bool = True,
) -> dict[str, float | bool]:
    """Evaluate Eq. (3); omit beta when the release misses the refund window."""
    q1 = _probability(q1, "q1")
    q2 = _probability(q2, "q2")
    gain = (q1 * (confirmed_cancellation_cost - waitlist_cancellation_cost)
            + q2 * (fare - waitlist_cancellation_cost)
            + (beta if refund_eligible else 0.0))
    return {"release_gain": gain, "release_cost": epsilon,
            "refund_eligible": refund_eligible, "release": epsilon < gain}


def traveller_payoff(
    *,
    outside_option: float,
    best_confirmed_trip_surplus: float | None,
    unused_ticket_costs: Iterable[float] = (),
    eligible_release_count: int = 0,
    release_count: int = 0,
    beta: float = 0.0,
    epsilon: float = 0.0,
) -> float:
    """Evaluate realized Eq. (1); average this over stochastic outcomes for E[U]."""
    trip = (float("-inf") if best_confirmed_trip_surplus is None
            else best_confirmed_trip_surplus)
    trip_or_outside = max(outside_option, trip)
    return (trip_or_outside - sum(unused_ticket_costs)
            + beta * eligible_release_count - epsilon * release_count)


def ticket_cancellation_cost(*, status: str, fare: float, confirmed_cancel_fee: float,
                             waitlist_cost: float) -> float:
    """Return unused-ticket cost from the proposal's status-specific convention."""
    if status == "waitlisted":
        return waitlist_cost
    if status == "confirmed_cancelled":
        return confirmed_cancel_fee
    if status == "confirmed_held":
        return fare
    raise ValueError(f"unknown unused-ticket status: {status}")


def build_independent_probability_strategy(
    *,
    values: Mapping[str, float],
    fares: Mapping[str, float],
    confirmation_probabilities: Mapping[str, float],
    expected_ticket_costs: Mapping[str, float],
    outside_option: float,
    release_inputs: Mapping[str, Mapping[str, object]] | None = None,
    release_friction: float = 0.0,
    refund_bonus: float = 0.0,
    refund_start_time: int = 0,
) -> dict[str, object]:
    """Build a benchmark booking set and release schedule from Eqs. (2)--(3).

    Candidate trains are considered in descending traveller value. The
    fallback for a candidate is the best net surplus among the outside option
    and already selected trains. Release cases must provide q1, q2,
    confirmed_cancellation_cost, waitlist_cancellation_cost, fare, and a
    planned_release_time. The chosen release time executes only if that ticket
    is waitlisted and redundant when the time arrives.
    """
    train_names = set(values)
    if set(fares) != train_names or set(confirmation_probabilities) != train_names:
        raise ValueError("values, fares, and confirmation_probabilities need the same train keys")
    if set(expected_ticket_costs) != train_names:
        raise ValueError("expected_ticket_costs must provide a cost for every candidate train")
    selected: list[str] = []
    hedge_decisions: dict[str, dict[str, float | bool]] = {}
    for train in sorted(train_names, key=lambda name: (-values[name], name)):
        fallback = max([outside_option]
                       + [values[held] - fares[held] for held in selected])
        higher_probabilities = [
            confirmation_probabilities[held]
            for held in selected if values[held] > values[train]
        ]
        decision = hedge_rule(
            p_k=confirmation_probabilities[train],
            higher_value_train_probabilities=higher_probabilities,
            value_k=values[train],
            fallback=fallback,
            expected_cost_k=expected_ticket_costs[train],
        )
        hedge_decisions[train] = decision
        if decision["hedge"]:
            selected.append(train)

    release_times: dict[str, int] = {}
    release_decisions: dict[str, dict[str, float | bool]] = {}
    for train, case in (release_inputs or {}).items():
        if train not in selected:
            continue
        planned_time = int(case["planned_release_time"])
        result = release_rule(
            epsilon=release_friction,
            q1=float(case["q1"]),
            q2=float(case["q2"]),
            confirmed_cancellation_cost=float(case["confirmed_cancellation_cost"]),
            waitlist_cancellation_cost=float(case["waitlist_cancellation_cost"]),
            fare=float(case.get("fare", fares[train])),
            beta=refund_bonus,
            refund_eligible=planned_time >= refund_start_time,
        )
        release_decisions[train] = result
        if result["release"]:
            release_times[train] = planned_time
    return {
        "trains_to_book": selected,
        "release_times": release_times,
        "release_waitlisted_only": True,
        "fixed_confirmation_probabilities": dict(confirmation_probabilities),
        "expected_ticket_costs": dict(expected_ticket_costs),
        "hedge_rule_decisions": hedge_decisions,
        "release_rule_decisions": release_decisions,
    }


def summarize_rule_inputs(
    hedge_cases: Mapping[str, Mapping[str, object]],
    release_cases: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, dict[str, float | bool]]]:
    """Evaluate a JSON-friendly collection of Eq. (2) and Eq. (3) cases."""
    hedges = {name: hedge_rule(**case) for name, case in hedge_cases.items()}
    releases = {name: release_rule(**case) for name, case in release_cases.items()}
    return {"hedge_rule_eq2": hedges, "release_rule_eq3": releases}
