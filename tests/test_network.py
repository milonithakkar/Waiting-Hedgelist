"""Hand-calculated checks for the proposal event model and rule equations."""

import unittest

from waitlist_sim.network import (
    NetworkConfig,
    Train,
    Traveller,
    simulate_network,
)
from waitlist_sim.proposal_rules import (
    build_independent_probability_strategy,
    hedge_rule,
    release_rule,
    traveller_payoff,
)


def traveller(name, values, trains, *, outside=0, booking=0, releases=None,
              eta=0, release_waitlisted_only=False):
    return Traveller(
        name=name,
        values=values,
        outside_option=outside,
        booking_time=booking,
        trains_to_book=tuple(trains),
        release_times=releases or {},
        plan_change_probability=eta,
        release_waitlisted_only=release_waitlisted_only,
    )


def config(trains, travellers, *, chart=2, departure=4, refund_start=1,
           beta=2, epsilon=1, c_w=1, f_c=4, psi=0, kappa=3,
           steps=(0, 1, 2, 3, 4), fee_schedule=None):
    return NetworkConfig(
        trains=tuple(trains),
        travellers=tuple(travellers),
        time_steps=steps,
        chart_time=chart,
        departure_time=departure,
        refund_start_time=refund_start,
        refund_bonus=beta,
        release_friction=epsilon,
        waitlist_cancellation_cost=c_w,
        confirmed_cancellation_fee=f_c,
        confirmed_cancellation_fee_schedule=fee_schedule,
        post_chart_resale_probability=psi,
        empty_berth_cost=kappa,
    )


class NetworkEventTests(unittest.TestCase):
    def test_booking_confirmation_waitlist_and_refusal_cap(self):
        result = simulate_network(config(
            [Train("A", 1, 1, 10)],
            [traveller("first", {"A": 30}, ["A"]),
             traveller("queued", {"A": 20}, ["A"]),
             traveller("refused", {"A": 15}, ["A"])],
        ), seed=1)
        self.assertEqual(result["tickets"]["first/A"]["initial_status"], "confirmed")
        self.assertEqual(result["tickets"]["queued/A"]["initial_status"], "waitlisted")
        self.assertEqual(result["tickets"]["refused/A"]["initial_status"], "refused")
        self.assertEqual(result["trains"]["A"]["accepted_tickets"], 2)

    def test_pre_chart_confirmed_release_promotes_fifo_waitlister(self):
        result = simulate_network(config(
            [Train("A", 1, 3, 10), Train("B", 1, 2, 10)],
            [traveller("releaser", {"A": 20, "B": 50}, ["A", "B"], releases={"A": 1}),
             traveller("first_waiter", {"A": 40, "B": 5}, ["A"]),
             traveller("second_waiter", {"A": 30, "B": 5}, ["A"])],
        ), seed=2)
        self.assertEqual(result["tickets"]["releaser/A"]["status"], "released_confirmed")
        self.assertEqual(result["tickets"]["first_waiter/A"]["confirmed_at"], 1)
        self.assertEqual(result["tickets"]["second_waiter/A"]["status"], "cancelled_waitlist")
        self.assertEqual(result["metrics"]["refunds_paid"], 2)
        self.assertEqual(result["metrics"]["empty_berths"], 0)
        self.assertEqual(result["metrics"]["railway_social_welfare_eq4"], 88)
        self.assertEqual(result["metrics"]["traveller_payoff_sum"], 66)

    def test_chart_cancels_queue_and_post_chart_release_resale(self):
        market = config(
            [Train("A", 1, 2, 10), Train("B", 1, 1, 10)],
            [traveller("holder", {"A": 20, "B": 50}, ["A", "B"], releases={"A": 3}),
             traveller("waiter", {"A": 30, "B": 0}, ["A"])],
            psi=1,
        )
        result = simulate_network(market, seed=3)
        self.assertEqual(result["tickets"]["waiter/A"]["status"], "cancelled_waitlist")
        self.assertEqual(result["tickets"]["holder/A"]["status"], "released_confirmed")
        self.assertEqual(result["trains"]["A"]["resold_after_chart"], 1)
        self.assertEqual(result["trains"]["A"]["travellers"], 0)
        self.assertEqual(result["trains"]["A"]["empty_berths"], 0)
        self.assertEqual(result["trains"]["A"]["confirmation_probability_observations"], 2)
        self.assertEqual(result["trains"]["A"]["confirmation_probability_successes"], 1)

        no_resale = simulate_network(config(
            [Train("A", 1, 2, 10), Train("B", 1, 1, 10)],
            [traveller("holder", {"A": 20, "B": 50}, ["A", "B"], releases={"A": 3}),
             traveller("waiter", {"A": 30, "B": 0}, ["A"])],
            psi=0,
        ), seed=3)
        self.assertEqual(no_resale["trains"]["A"]["resold_after_chart"], 0)
        self.assertEqual(no_resale["trains"]["A"]["empty_berths"], 1)

    def test_release_at_chart_promotes_before_waitlist_cancellation(self):
        result = simulate_network(config(
            [Train("A", 1, 2, 10), Train("B", 1, 1, 10)],
            [traveller("holder", {"A": 20, "B": 50}, ["A", "B"], releases={"A": 2}),
             traveller("waiter", {"A": 30, "B": 0}, ["A"])],
            chart=2,
        ), seed=6)
        self.assertEqual(result["tickets"]["waiter/A"]["confirmed_at"], 2)
        self.assertEqual(result["trains"]["A"]["q2_rate_among_uncensored_initial_waitlist_tickets"], 1)

    def test_voluntary_release_is_censored_from_confirmation_probability(self):
        result = simulate_network(config(
            [Train("A", 1, 3, 10), Train("B", 1, 1, 10)],
            [traveller("holder", {"A": 20, "B": 5}, ["A"]),
             traveller("releaser", {"A": 30, "B": 40}, ["A", "B"],
                       releases={"A": 1}, release_waitlisted_only=True),
             traveller("waiter", {"A": 25, "B": 5}, ["A"])],
        ), seed=8)
        result_a = result["trains"]["A"]
        self.assertEqual(result["tickets"]["releaser/A"]["cancellation_reason"], "scheduled_release")
        self.assertEqual(result_a["accepted_tickets"], 3)
        self.assertEqual(result_a["confirmation_probability_observations"], 2)
        self.assertEqual(result_a["confirmation_probability_successes"], 1)
        self.assertEqual(result_a["q1_q2_observations_excluding_censored"], 1)

    def test_plan_change_cancels_all_and_uses_time_specific_fee(self):
        result = simulate_network(config(
            [Train("A", 1, 2, 10)],
            [traveller("changes", {"A": 20}, ["A"], outside=5, eta=1),
             traveller("waiter", {"A": 30}, ["A"])],
            steps=(1, 2, 3, 4),
            fee_schedule={1: 7},
        ), seed=4)
        self.assertEqual(result["tickets"]["changes/A"]["status"], "cancelled_confirmed")
        self.assertEqual(result["tickets"]["waiter/A"]["confirmed_at"], 1)
        self.assertEqual(result["travellers"]["changes"]["unused_ticket_costs"], 7)
        self.assertEqual(result["metrics"]["traveller_payoff_sum"], 18)

    def test_eq4_counts_outside_option_and_empty_berth(self):
        result = simulate_network(config(
            [Train("A", 2, 1, 10)],
            [traveller("travels", {"A": 20}, ["A"]),
             traveller("stays", {"A": 5}, [], outside=5)],
            beta=0,
        ), seed=5)
        self.assertEqual(result["metrics"]["empty_berths"], 1)
        self.assertEqual(result["metrics"]["railway_social_welfare_eq4"], 22)


class ProposalRuleTests(unittest.TestCase):
    def test_eq2_uses_higher_value_nonconfirmation_product(self):
        result = hedge_rule(
            p_k=0.5,
            higher_value_train_probabilities=[0.4, 0.2],
            value_k=30,
            fallback=10,
            expected_cost_k=4,
        )
        self.assertAlmostEqual(result["expected_gain"], 4.8)
        self.assertTrue(result["hedge"])

    def test_eq3_refund_bonus_only_applies_when_eligible(self):
        inputs = dict(epsilon=4, q1=0.2, q2=0.1,
                      confirmed_cancellation_cost=8,
                      waitlist_cancellation_cost=2, fare=20, beta=2)
        self.assertTrue(release_rule(**inputs, refund_eligible=True)["release"])
        self.assertFalse(release_rule(**inputs, refund_eligible=False)["release"])

    def test_eq1_payoff_includes_unused_cost_bonus_and_friction(self):
        self.assertEqual(traveller_payoff(
            outside_option=5,
            best_confirmed_trip_surplus=20,
            unused_ticket_costs=[4, 2],
            eligible_release_count=1,
            release_count=2,
            beta=3,
            epsilon=1,
        ), 15)

    def test_independent_rule_strategy_generates_booking_and_release_actions(self):
        strategy = build_independent_probability_strategy(
            values={"A": 30, "B": 35},
            fares={"A": 10, "B": 10},
            confirmation_probabilities={"A": 0.7, "B": 0.5},
            expected_ticket_costs={"A": 1, "B": 1},
            outside_option=0,
            release_inputs={"A": {
                "q1": 0.2,
                "q2": 0.1,
                "confirmed_cancellation_cost": 4,
                "waitlist_cancellation_cost": 1,
                "planned_release_time": 1,
            }},
            refund_bonus=2,
            release_friction=0.25,
            refund_start_time=1,
        )
        self.assertEqual(strategy["trains_to_book"], ["B", "A"])
        self.assertEqual(strategy["release_times"], {"A": 1})
        self.assertTrue(strategy["release_waitlisted_only"])


if __name__ == "__main__":
    unittest.main()
