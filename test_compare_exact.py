"""Integration checks for standalone exact solvers in the comparison driver."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import compare_algorithms as study


PUZZLE = {"grid": [
    ["#", {"down": 3}, {"down": 5}],
    [{"across": 3}, None, None],
    [{"across": 5}, None, None],
]}
VALID = {(1, 1): 1, (1, 2): 2, (2, 1): 2, (2, 2): 3}
GA_ONLY_METRICS = (
    "genetic_fitness_evaluations", "generations_evaluated", "ga_time_seconds",
    "ga_solution_valid", "best_ga_fitness", "ga_satisfied_runs_percent",
)


def exact_diagnostics(status, cp_sat=True):
    return {
        "status": status, "branches": 11, "backtracking_count": None if cp_sat else 3,
        "conflicts": 7 if cp_sat else None, "nodes_visited": None if cp_sat else 12,
        "execution_time_seconds": 0.2, "preprocessing_time_seconds": 0.02,
        "model_build_time_seconds": 0.02 if cp_sat else 0.0,
        "search_time_seconds": 0.18, "domain_reduction_percent": None if cp_sat else 12.5,
        "cp_sat_status": status if cp_sat else None,
    }


class ExactDriverTests(unittest.TestCase):
    def test_constraint_search_ignores_ga_budget_and_never_invokes_ga(self):
        with patch.object(study, "baseline_search", side_effect=AssertionError("GA must not run")), \
                patch.object(study.kakuro, "genetic_search", side_effect=AssertionError("GA must not run")):
            result = study.solve_case(PUZZLE, "constraint_search", population_size=1, generations=0)
        self.assertTrue(result["metrics"]["solution_valid"])
        self.assertTrue(study.verify_result(PUZZLE, result))
        for key in GA_ONLY_METRICS:
            self.assertIsNone(result["metrics"][key], key)
        self.assertFalse(result["metrics"]["fallback_used"])
        self.assertIsNone(result["ga_best_grid"])
        self.assertIsInstance(result["metrics"]["backtracking_count"], int)

    def test_cp_sat_statuses_preserve_unknown_vs_proven_infeasible(self):
        for status in ("UNKNOWN", "INFEASIBLE"):
            with self.subTest(status=status), \
                    patch.object(study, "ensure_cp_sat_available"), \
                    patch.object(study, "cp_sat_search", return_value=(None, exact_diagnostics(status))) as solve:
                result = study.solve_case(PUZZLE, "cp_sat", seed=19, time_limit=2.5)
                self.assertEqual(result["status"], status.lower())
                self.assertEqual(result["metrics"]["solver_status"], status)
                self.assertIsNone(result["metrics"]["final_fitness"])
                self.assertIsNone(result["metrics"]["final_satisfied_runs_percent"])
                self.assertFalse(result["metrics"]["solution_valid"])
                self.assertEqual(result["metrics"]["white_cells_solved"], 0)
                self.assertIsNone(result["solved_grid"])
                self.assertTrue(study.verify_result(PUZZLE, result))
                self.assertEqual(solve.call_args.kwargs, {"seed": 19, "time_limit": 2.5})

    def test_cp_sat_conflicts_are_not_backtracks_and_invalid_metrics_fail(self):
        calls = []
        def load_library():
            calls.append("import")
        def solve(*args, **kwargs):
            calls.append("solve")
            return VALID, exact_diagnostics("OPTIMAL")
        with patch.object(study, "ensure_cp_sat_available", side_effect=load_library), \
                patch.object(study, "cp_sat_search", side_effect=solve):
            result = study.solve_case(PUZZLE, "cp_sat")
        self.assertEqual(calls, ["import", "solve"])
        metrics = result["metrics"]
        self.assertEqual(metrics["search_branches"], 11)
        self.assertEqual(metrics["cp_sat_conflicts"], 7)
        self.assertIsNone(metrics["backtracking_count"])
        self.assertTrue(study.verify_result(PUZZLE, result))
        metrics["backtracking_count"] = 7
        with self.assertRaises(ValueError):
            study.verify_result(PUZZLE, result)
        metrics["backtracking_count"] = None
        metrics["genetic_fitness_evaluations"] = 0
        with self.assertRaises(ValueError):
            study.verify_result(PUZZLE, result)

    def test_model_invalid_or_status_assignment_mismatch_is_an_error(self):
        for candidate, status in ((None, "MODEL_INVALID"), (None, "OPTIMAL"), (VALID, "INFEASIBLE")):
            with self.subTest(status=status), \
                    patch.object(study, "ensure_cp_sat_available"), \
                    patch.object(study, "cp_sat_search", return_value=(candidate, exact_diagnostics(status))):
                with self.assertRaises(ValueError):
                    study.solve_case(PUZZLE, "cp_sat")

    def test_inner_solver_receives_same_timeout_as_outer_process(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "puzzle.json"
            output_path = Path(directory) / "result.json"
            input_path.write_text(json.dumps(PUZZLE), encoding="utf-8")
            args = Namespace(population_size=160, generations=1500, timeout=19.5)
            def timeout(command, **kwargs):
                self.assertIn("--timeout", command)
                self.assertEqual(float(command[command.index("--timeout") + 1]), 19.5)
                self.assertEqual(kwargs["timeout"], 19.5)
                raise subprocess.TimeoutExpired(command, 19.5)
            with patch.object(study.subprocess, "run", side_effect=timeout):
                record = study.run_trial(PUZZLE, input_path, output_path, "cp_sat", 42, args)
            self.assertEqual(record["status"], "timeout")
            self.assertNotIn("result", record)
            self.assertFalse(output_path.exists())

    @unittest.skipUnless(importlib.util.find_spec("ortools"), "OR-Tools is optional outside the study environment")
    def test_real_cp_sat_worker_produces_valid_result_with_native_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "puzzle.json"
            output_path = Path(directory) / "result.json"
            input_path.write_text(json.dumps(PUZZLE), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, "-E", "-s", str(Path(study.__file__).resolve()), "--worker", "--algorithm", "cp_sat",
                 "--input", str(input_path), "--output", str(output_path), "--generations", "0",
                 "--timeout", "5"], capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(study.verify_result(PUZZLE, result))
            metrics = result["metrics"]
            self.assertTrue(metrics["solution_valid"])
            self.assertIn(metrics["solver_status"], ("OPTIMAL", "FEASIBLE"))
            self.assertIsNone(metrics["backtracking_count"])
            self.assertIsInstance(metrics["search_branches"], int)
            self.assertIsInstance(metrics["cp_sat_conflicts"], int)
            for key in GA_ONLY_METRICS:
                self.assertIsNone(metrics[key], key)


if __name__ == "__main__":
    unittest.main()
