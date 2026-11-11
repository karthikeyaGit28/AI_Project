"""Observation must preserve the original GA and retain failed-search evidence."""

import unittest
from unittest.mock import patch

import generate_and_solve as kakuro


def search_arguments(size=3, seed=42):
    _, whites, runs = kakuro.parse_puzzle(kakuro.generate_puzzle(size, seed))
    domains = kakuro.propagate(whites, runs)
    across = [run for run in runs if run["direction"] == "across"]
    down = [run for run in runs if run["direction"] == "down"]
    return (whites, across, down, domains, seed), runs


class GeneticDiagnosticsTests(unittest.TestCase):
    def test_observation_preserves_seeded_search(self):
        for size, seed in ((3, 42), (3, 43), (3, 44), (5, 42)):
            with self.subTest(size=size, seed=seed):
                arguments, runs = search_arguments(size, seed)
                expected = kakuro.genetic_search(*arguments, population_size=16, generations=30)
                stats = {}
                actual = kakuro.genetic_search(
                    *arguments, population_size=16, generations=30, diagnostics=stats,
                )
                self.assertEqual(actual, expected)
                self.assertEqual(stats["evaluations"], actual[1])
                self.assertEqual(stats["evaluations"], 16 * stats["generations_evaluated"])
                self.assertEqual(len(stats["fitness_history"]), stats["generations_evaluated"])
                self.assertEqual(stats["fitness_history"], sorted(stats["fitness_history"], reverse=True))
                self.assertEqual(kakuro.fitness(stats["best_candidate"], runs), stats["best_fitness"])
                self.assertEqual(stats["best_fitness"], stats["fitness_history"][-1])
                if actual[0] is not None:
                    self.assertEqual(stats["best_fitness"], 0)
                    self.assertTrue(kakuro.validate_solution(stats["best_candidate"], arguments[0], runs))

    def test_zero_budget_initializes_empty_diagnostics(self):
        arguments, _ = search_arguments()
        stats = {"stale": "data"}
        self.assertEqual(kakuro.genetic_search(*arguments, generations=0, diagnostics=stats), (None, 0))
        self.assertEqual(stats, {
            "evaluations": 0, "generations_evaluated": 0, "best_fitness": None,
            "best_candidate": None, "fitness_history": [], "restarts": 0,
            "mutation_rate_min": None, "mutation_rate_max": None,
        })

    def test_exhausted_budget_retains_unsolved_best_candidate(self):
        arguments, runs = search_arguments(5, 42)
        stats = {}
        solution, evaluations = kakuro.genetic_search(
            *arguments, population_size=1, generations=1, diagnostics=stats,
        )
        self.assertIsNone(solution)
        self.assertEqual(evaluations, 1)
        self.assertIsNotNone(stats["best_candidate"])
        self.assertGreater(stats["best_fitness"], 0)
        self.assertEqual(kakuro.fitness(stats["best_candidate"], runs), stats["best_fitness"])
        self.assertFalse(kakuro.validate_solution(stats["best_candidate"], arguments[0], runs))

    def test_restart_history_and_adaptive_rates_are_observed_without_rng_changes(self):
        arguments, _ = search_arguments(3, 42)
        with patch.object(kakuro, "fitness", return_value=5):
            expected = kakuro.genetic_search(*arguments, population_size=1, generations=205)
            stats = {}
            actual = kakuro.genetic_search(
                *arguments, population_size=1, generations=205, diagnostics=stats,
            )
        self.assertEqual(actual, expected)
        self.assertEqual(stats["restarts"], 2)
        self.assertEqual(stats["fitness_history"], [5] * 205)
        self.assertEqual(stats["mutation_rate_min"], 0.25)
        self.assertAlmostEqual(stats["mutation_rate_max"], 0.25 + 0.65 * 99 / 100)


if __name__ == "__main__":
    unittest.main()
