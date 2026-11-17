import unittest

from waitlist_sim.learning import run_belief_learning_experiment


class LearningTests(unittest.TestCase):
    def test_agents_lower_belief_after_congested_confirmation_failures(self):
        result = run_belief_learning_experiment(episodes=2, seed=1)
        first = result["trajectory"][0]
        self.assertEqual(first["bookings_by_train"]["A"], 8)
        self.assertLess(first["mean_beliefs_after_update"]["A"], 0.8)


if __name__ == "__main__":
    unittest.main()
