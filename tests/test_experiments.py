import unittest

from waitlist_sim.experiments import (
    run_c2_congestion_experiments,
    run_c2_release_timing_experiment,
    run_refund_policy_sweep,
    run_refund_eta_sensitivity,
)


class C2ExperimentTests(unittest.TestCase):
    def test_congestion_changes_fixed_belief_gap_and_joint_outcome(self):
        results = run_c2_congestion_experiments(runs=2, seed=1)["profiles"]
        self.assertEqual(results["light"]["observed_confirmation_rates"]["A"], 1.0)
        self.assertEqual(results["balanced"]["observed_confirmation_rates"]["A"], 0.4)
        self.assertLess(results["congested"]["observed_confirmation_rates"]["A"], 0.7)
        balanced_joint = results["balanced"]["joint_confirmation"]["A|B"]
        self.assertGreater(
            balanced_joint["observed_joint"],
            balanced_joint["independent_product"],
        )

    def test_observed_q1_changes_the_eq3_release_decision(self):
        result = run_c2_release_timing_experiment(runs=2_000, seed=1)
        self.assertAlmostEqual(
            result["observed_kept_ticket_outcomes"]["q1_confirm_before_chart"],
            1 - 0.75 ** 2,
            delta=0.04,
        )
        self.assertFalse(result["eq3_with_fixed_belief"]["release"])
        self.assertTrue(result["eq3_with_observed_rates"]["release"])

    def test_beta_sweep_changes_the_eq3_release_policy(self):
        results = run_refund_policy_sweep(runs=20, seed=1)["results_by_beta"]
        self.assertFalse(results["0"]["eq3_release_decision"])
        self.assertTrue(results["1"]["eq3_release_decision"])
        self.assertGreater(results["1"]["mean_release_count"], 0)

    def test_refund_effect_uses_plan_change_opportunity(self):
        results = run_refund_eta_sensitivity(runs=50, seed=1)["results_by_eta"]
        self.assertLess(
            results["0.10"]["beta_1_minus_beta_0"]["mean_empty_berths"],
            0,
        )
        self.assertLess(
            results["0.50"]["beta_1_minus_beta_0"]["mean_empty_berths"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
