"""Independent checks for comparable cell-based genetic baselines."""

import copy
import random
import unittest

import generate_and_solve as kakuro
from kakuro_variants import _indexed_fitness, baseline_search


def small_puzzle():
    return {"grid": [
        ["#", {"down": 3}, {"down": 5}],
        [{"across": 3}, None, None],
        [{"across": 5}, None, None],
    ]}


class BaselineTests(unittest.TestCase):
    def setUp(self):
        _, self.whites, self.runs = kakuro.parse_puzzle(small_puzzle())

    def test_indexed_fitness_matches_independent_constraint_penalty(self):
        rng = random.Random(228)
        for size in (2, 3, 5):
            _, whites, runs = kakuro.parse_puzzle(kakuro.generate_puzzle(size, 42))
            indices = {cell: i for i, cell in enumerate(whites)}
            indexed_runs = [(tuple(indices[cell] for cell in run["cells"]), run["sum"])
                            for run in runs]
            for _ in range(20):
                values = tuple(rng.randint(1, 9) for cell in whites)
                assignment = dict(zip(whites, values))
                expected = 0
                for run in runs:
                    digits = [assignment[cell] for cell in run["cells"]]
                    expected += abs(sum(digits) - run["sum"])
                    expected += 9 * sum(digits.count(digit) - 1 for digit in set(digits))
                self.assertEqual(_indexed_fitness(values, indexed_runs), expected)
                self.assertEqual(expected, kakuro.fitness(assignment, runs))

    def test_reproducible_search_preserves_domains_and_budget(self):
        domains = {cell: set(range(1, 10)) for cell in self.whites}
        original = copy.deepcopy(domains)
        first = baseline_search(self.whites, self.runs, domains, 42,
                                population_size=20, generations=30)
        self.assertEqual(first, baseline_search(self.whites, self.runs, domains, 42,
                                               population_size=20, generations=30))
        candidate, stats = first
        self.assertEqual(domains, original)
        self.assertEqual(set(candidate), set(self.whites))
        self.assertTrue(all(candidate[cell] in domains[cell] for cell in self.whites))
        self.assertEqual(stats["best_fitness"], kakuro.fitness(candidate, self.runs))
        self.assertEqual(stats["evaluations"], 20 * stats["generations_evaluated"])
        self.assertLessEqual(stats["generations_evaluated"], 30)
        self.assertEqual(len(stats["fitness_history"]), stats["generations_evaluated"])
        self.assertEqual(stats["fitness_history"], sorted(stats["fitness_history"], reverse=True))
        if stats["generations_evaluated"] > 1:
            self.assertEqual(stats["mutation_rate_min"], 0.25)
            self.assertEqual(stats["mutation_rate_max"], 0.25)

    def test_propagated_domains_and_solved_singletons(self):
        domains = kakuro.propagate(self.whites, self.runs)
        candidate, stats = baseline_search(self.whites, self.runs, domains, 42,
                                          population_size=20, generations=100)
        self.assertTrue(kakuro.validate_solution(candidate, self.whites, self.runs))
        self.assertEqual(stats["best_fitness"], 0)
        singleton = {cell: {value} for cell, value in candidate.items()}
        candidate, stats = baseline_search(self.whites, self.runs, singleton, 42)
        self.assertTrue(kakuro.validate_solution(candidate, self.whites, self.runs))
        self.assertEqual(stats["evaluations"], 160)
        self.assertEqual(stats["generations_evaluated"], 1)
        self.assertIsNone(stats["mutation_rate_min"])
        self.assertIsNone(stats["mutation_rate_max"])

    def test_dynamic_mutation_increases_with_stagnation_and_caps(self):
        # All candidates are identical and invalid, giving guaranteed stagnation.
        domains = {cell: {1} for cell in self.whites}
        candidate, stats = baseline_search(self.whites, self.runs, domains, 42,
                                          population_size=10, generations=105,
                                          dynamic_mutation=True)
        self.assertFalse(kakuro.validate_solution(candidate, self.whites, self.runs))
        self.assertEqual(stats["evaluations"], 1050)
        self.assertEqual(stats["generations_evaluated"], 105)
        self.assertEqual(stats["mutation_rate_min"], 0.25)
        self.assertEqual(stats["mutation_rate_max"], 0.9)
        self.assertEqual(len(set(stats["fitness_history"])), 1)

    def test_zero_budget_returns_no_candidate_or_fabricated_score(self):
        domains = {cell: set(range(1, 10)) for cell in self.whites}
        candidate, stats = baseline_search(self.whites, self.runs, domains, 42, generations=0)
        self.assertIsNone(candidate)
        self.assertEqual(stats["evaluations"], 0)
        self.assertEqual(stats["generations_evaluated"], 0)
        self.assertEqual(stats["fitness_history"], [])
        self.assertIsNone(stats["best_fitness"])

    def test_invalid_parameters_and_domains(self):
        domains = {cell: set(range(1, 10)) for cell in self.whites}
        for kwargs in ({"population_size": 0}, {"population_size": True},
                       {"generations": -1}, {"generations": 1.5},
                       {"dynamic_mutation": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                baseline_search(self.whites, self.runs, domains, 42, **kwargs)
        for invalid in (set(), {True}, {0}, {10}, {"1"}):
            malformed = copy.deepcopy(domains)
            malformed[self.whites[0]] = invalid
            with self.subTest(domain=invalid), self.assertRaises(ValueError):
                baseline_search(self.whites, self.runs, malformed, 42)


if __name__ == "__main__":
    unittest.main()
