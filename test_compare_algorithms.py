"""Checks that the study separates GA quality, solved output, and fallback."""

import json
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import compare_algorithms as study
import generate_and_solve as kakuro


PUZZLE = {"grid": [
    ["#", {"down": 3}, {"down": 5}],
    [{"across": 3}, None, None],
    [{"across": 5}, None, None],
]}
VALID = {(1, 1): 1, (1, 2): 2, (2, 1): 2, (2, 2): 3}
INVALID = {cell: 1 for cell in VALID}


def diagnostics(score):
    return {"evaluations": 8, "generations_evaluated": 1, "best_fitness": score,
            "fitness_history": [score], "mutation_rate_min": None, "mutation_rate_max": None}


class AlgorithmStudyTests(unittest.TestCase):
    def test_run_quality_requires_sum_and_distinct_digits(self):
        whites = [(1, 1), (1, 2)]
        runs = [{"cells": whites, "sum": 4}]
        result = study.candidate_quality(dict(zip(whites, [2, 2])), whites, runs)
        self.assertEqual(result["fitness"], 9)
        self.assertEqual(result["satisfied_runs_percent"], 0)
        self.assertFalse(result["valid"])
        self.assertIsNone(study.candidate_quality(None, whites, runs)["fitness"])

    def test_baselines_only_use_their_intended_enhancements(self):
        _, whites, runs = kakuro.parse_puzzle(PUZZLE)
        score = study.candidate_quality(INVALID, whites, runs)["fitness"]
        for algorithm in study.ALGORITHMS[:3]:
            with self.subTest(algorithm=algorithm), \
                    patch.object(study.kakuro, "propagate", wraps=kakuro.propagate) as propagate, \
                    patch.object(study.kakuro, "backtracking_search") as fallback, \
                    patch.object(study, "baseline_search", return_value=(INVALID, diagnostics(score))) as search:
                result = study.solve_case(PUZZLE, algorithm, population_size=8, generations=1)
                self.assertEqual(propagate.call_count, int(algorithm == "domain_filtering"))
                fallback.assert_not_called()
                self.assertEqual(search.call_args.kwargs["dynamic_mutation"], algorithm == "dynamic_mutation")
                self.assertFalse(result["metrics"]["solution_valid"])
                self.assertEqual(result["metrics"]["white_cells_solved"], 0)
                self.assertIsNone(result["solved_grid"])
                self.assertEqual(result["status"], "budget_exhausted")
                study.verify_result(PUZZLE, result)

    def test_ours_keeps_ga_failure_distinct_from_fallback_success(self):
        _, whites, runs = kakuro.parse_puzzle(PUZZLE)
        score = study.candidate_quality(INVALID, whites, runs)["fitness"]
        def failed_ga(*args, **kwargs):
            kwargs["diagnostics"].update(diagnostics(score), best_candidate=INVALID)
            return None, 8
        with patch.object(study.kakuro, "genetic_search", side_effect=failed_ga), \
                patch.object(study.kakuro, "backtracking_search", return_value=(VALID, 7)):
            result = study.solve_case(PUZZLE, "ours", population_size=8, generations=1)
        metrics = result["metrics"]
        self.assertTrue(metrics["fallback_used"])
        self.assertFalse(metrics["ga_solution_valid"])
        self.assertTrue(metrics["solution_valid"])
        self.assertEqual(metrics["backtracking_count"], 7)
        self.assertEqual(metrics["best_ga_fitness"], score)
        self.assertEqual(metrics["final_fitness"], 0)
        self.assertNotEqual(result["ga_best_grid"], result["solved_grid"])
        study.verify_result(PUZZLE, result)

    def test_all_variants_run_and_preserve_correct_metrics(self):
        for algorithm in study.GA_ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                result = study.solve_case(PUZZLE, algorithm, population_size=8, generations=5)
                self.assertTrue(study.verify_result(PUZZLE, result))
                self.assertLessEqual(result["metrics"]["genetic_fitness_evaluations"], 40)
                if algorithm != "ours":
                    self.assertFalse(result["metrics"]["fallback_used"])

    def test_corrupt_metrics_are_rejected(self):
        result = study.solve_case(PUZZLE, "ours", population_size=8, generations=0)
        self.assertTrue(result["metrics"]["solution_valid"])
        result["metrics"]["white_cells_solved"] = 0
        with self.assertRaises(ValueError):
            study.verify_result(PUZZLE, result)

    def test_timeout_preserves_unknown_metrics_and_removes_stale_result(self):
        with tempfile.TemporaryDirectory() as directory:
            puzzle_path = Path(directory) / "puzzle.json"
            result_path = Path(directory) / "result.json"
            puzzle_path.write_text(json.dumps(PUZZLE), encoding="utf-8")
            result_path.write_text("stale", encoding="utf-8")
            args = Namespace(population_size=160, generations=1500, timeout=120)
            with patch.object(study.subprocess, "run", side_effect=subprocess.TimeoutExpired("solver", 120)):
                record = study.run_trial(PUZZLE, puzzle_path, result_path, "basic", 42, args)
            self.assertEqual(record["status"], "timeout")
            self.assertNotIn("result", record)
            self.assertFalse(result_path.exists())


if __name__ == "__main__":
    unittest.main()
