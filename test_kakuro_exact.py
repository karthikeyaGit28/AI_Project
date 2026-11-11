"""Regression tests for exact Kakuro modeling, feasibility, and search status."""

import copy
import importlib.util
import unittest
from unittest.mock import patch

import kakuro_exact as exact
from generate_and_solve import generate_puzzle, parse_puzzle, validate_solution


PUZZLE = {"grid": [
    ["#", {"down": 3}, {"down": 5}],
    [{"across": 3}, None, None],
    [{"across": 5}, None, None],
]}
IMPOSSIBLE = {"grid": [
    ["#", {"down": 3}, {"down": 4}],
    [{"across": 3}, None, None],
    [{"across": 3}, None, None],
]}


class ConstraintSearchTests(unittest.TestCase):
    def test_solves_and_does_not_modify_parsed_input(self):
        _, whites, runs = parse_puzzle(PUZZLE)
        before = copy.deepcopy((whites, runs))
        solution, stats = exact.constraint_search(whites, runs)
        self.assertTrue(validate_solution(solution, whites, runs))
        self.assertEqual(stats["status"], "SOLVED")
        self.assertGreaterEqual(stats["branches"], stats["backtracking_count"])
        self.assertGreaterEqual(stats["nodes_visited"], 1)
        self.assertIsNone(stats["conflicts"])
        self.assertIsNone(stats["cp_sat_status"])
        self.assertEqual((whites, runs), before)
        self.assertAlmostEqual(stats["execution_time_seconds"],
                               stats["preprocessing_time_seconds"] + stats["search_time_seconds"])

    def test_detects_inconsistent_clues(self):
        _, whites, runs = parse_puzzle(IMPOSSIBLE)
        solution, stats = exact.constraint_search(whites, runs)
        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "INFEASIBLE")

    def test_zero_time_is_unknown_not_infeasible(self):
        _, whites, runs = parse_puzzle(PUZZLE)
        solution, stats = exact.constraint_search(whites, runs, time_limit=0)
        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertEqual(stats["branches"], 0)
        self.assertEqual(stats["backtracking_count"], 0)

    def test_ambiguous_puzzle_uses_decisions_and_seed_does_not_change_csp(self):
        puzzle = {"grid": [
            ["#", {"down": 3}, {"down": 3}],
            [{"across": 3}, None, None],
            [{"across": 3}, None, None],
        ]}
        _, whites, runs = parse_puzzle(puzzle)
        first, stats = exact.constraint_search(whites, runs, seed=42)
        second, _ = exact.constraint_search(whites, runs, seed=43)
        self.assertEqual(first, second)
        self.assertTrue(validate_solution(first, whites, runs))
        self.assertGreater(stats["branches"], 0)
        self.assertEqual(stats["nodes_visited"], stats["branches"] + 1)

    def test_rejects_invalid_limits_and_seed(self):
        _, whites, runs = parse_puzzle(PUZZLE)
        for limit in (-1, float("nan"), float("inf"), True, "1"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                exact.constraint_search(whites, runs, time_limit=limit)
        for seed in (True, -1, 2 ** 31, 1.5):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                exact.constraint_search(whites, runs, seed=seed)

    def test_failed_branches_are_counted_separately_from_decisions(self):
        _, whites, runs = parse_puzzle(generate_puzzle(7, 42))
        solution, stats = exact.constraint_search(whites, runs)
        self.assertTrue(validate_solution(solution, whites, runs))
        self.assertGreater(stats["backtracking_count"], 0)
        self.assertGreater(stats["branches"], stats["backtracking_count"])
        self.assertEqual(stats["nodes_visited"], stats["branches"] + 1)


@unittest.skipUnless(importlib.util.find_spec("ortools") is not None, "requires OR-Tools")
class CpSatTests(unittest.TestCase):
    def test_solves_with_native_statistics(self):
        _, whites, runs = parse_puzzle(PUZZLE)
        solution, stats = exact.cp_sat_search(whites, runs)
        self.assertTrue(validate_solution(solution, whites, runs))
        self.assertIn(stats["status"], ("FEASIBLE", "OPTIMAL"))
        self.assertEqual(stats["status"], stats["cp_sat_status"])
        self.assertGreaterEqual(stats["branches"], 0)
        self.assertGreaterEqual(stats["conflicts"], 0)
        self.assertGreaterEqual(stats["deterministic_time"], 0)
        self.assertIsNone(stats["backtracking_count"])
        self.assertIsNone(stats["domain_reduction_percent"])
        self.assertTrue(stats["ortools_version"])
        self.assertAlmostEqual(stats["execution_time_seconds"],
                               stats["model_build_time_seconds"] + stats["search_time_seconds"])

    def test_sum_inconsistency_is_proven_infeasible(self):
        _, whites, runs = parse_puzzle(IMPOSSIBLE)
        solution, stats = exact.cp_sat_search(whites, runs)
        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "INFEASIBLE")

    def test_all_different_is_required_even_when_repeated_digits_have_correct_sum(self):
        # Each distinct two-digit column summing to4 must use {1,3}. Then every
        # row sum is even, making the odd row clues impossible. Sum constraints
        # alone allow [[1,2],[3,2]], with a repeated2 in the second column.
        puzzle = {"grid": [
            ["#", {"down": 4}, {"down": 4}],
            [{"across": 3}, None, None],
            [{"across": 5}, None, None],
        ]}
        _, whites, runs = parse_puzzle(puzzle)
        solution, stats = exact.cp_sat_search(whites, runs)
        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "INFEASIBLE")

    def test_zero_limit_never_claims_infeasible(self):
        _, whites, runs = parse_puzzle(PUZZLE)
        solution, stats = exact.cp_sat_search(whites, runs, time_limit=0)
        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "UNKNOWN")

    def test_cp_sat_does_not_call_custom_constraint_propagation(self):
        _, whites, runs = parse_puzzle(PUZZLE)
        with patch.object(exact, "_propagate", side_effect=AssertionError("custom propagation used")):
            solution, _ = exact.cp_sat_search(whites, runs)
        self.assertTrue(validate_solution(solution, whites, runs))


if __name__ == "__main__":
    unittest.main()
