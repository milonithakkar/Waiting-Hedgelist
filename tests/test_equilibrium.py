import unittest

from waitlist_sim.equilibrium import (
    compare_equilibrium_with_event_simulation,
    EquilibriumTrain,
    TravellerType,
    TypeEquilibriumConfig,
    solve_type_equilibria,
)


class TypeEquilibriumTests(unittest.TestCase):
    def test_single_type_books_one_high_value_train_at_equilibrium(self):
        config = TypeEquilibriumConfig(
            trains=(EquilibriumTrain("A", 2, 10), EquilibriumTrain("B", 2, 10)),
            types=(TravellerType(
                "high", 2, {"A": 30, "B": 11}, 0,
                {"A": 1, "B": 5},
            ),),
        )
        result = solve_type_equilibria(config)
        self.assertEqual(result["profiles_checked"], 4)
        self.assertEqual(result["pure_equilibria_found"], 1)
        self.assertEqual(result["equilibria"][0]["actions_by_type"]["high"], ["A"])
        self.assertEqual(result["equilibria"][0]["confirmation_probabilities"]["A"], 1.0)

    def test_replay_reports_joint_independence_gap(self):
        config = TypeEquilibriumConfig(
            trains=(EquilibriumTrain("A", 1, 10), EquilibriumTrain("B", 1, 10)),
            types=(TravellerType(
                "hedgers", 2, {"A": 30, "B": 30}, 0,
                {"A": 1, "B": 1},
            ),),
        )
        comparison = compare_equilibrium_with_event_simulation(config, runs=2)
        joint = comparison["event_simulator_joint_checks"]["hedgers"]
        self.assertGreater(joint["joint_minus_product"], 0)
        self.assertEqual(
            comparison["event_simulator_confirmation_by_type"]["hedgers"]["A"],
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
