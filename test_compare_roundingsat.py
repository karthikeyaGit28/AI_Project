"""Integration checks for the native RoundingSat comparison backend."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import compare_algorithms as study
import kakuro_roundingsat


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


def native_diagnostics(status="SOLVED"):
    return {
        "status": status,
        "native_status": {"SOLVED": "SATISFIABLE", "INFEASIBLE": "UNSATISFIABLE",
                          "UNKNOWN": "UNKNOWN"}[status],
        "execution_time_seconds": 0.2, "preprocessing_time_seconds": 0.02,
        "model_build_time_seconds": 0.02, "search_time_seconds": 0.18,
        "backtracking_count": None, "branches": None, "nodes_visited": None,
        "conflicts": None, "domain_reduction_percent": None,
        "native_decisions": 13, "native_conflicts": 3,
        "native_propagations": 41, "native_restarts": 0,
        "native_time_seconds": 0.12,
        "opb_variables": 36, "opb_constraints": 44,
        "timed_out": False, "solver_version": "test-version",
        "binary_sha256": "a" * 64, "seed_applied": False,
    }


class RoundingSatDriverTests(unittest.TestCase):
    def test_native_dispatch_has_separate_counters_and_no_ga_or_fallback(self):
        with patch.object(study, "ensure_roundingsat_available"), \
                patch.object(study, "roundingsat_search", return_value=(VALID, native_diagnostics())) as solve, \
                patch.object(study, "cp_sat_search", side_effect=AssertionError("wrong solver")), \
                patch.object(study, "constraint_search", side_effect=AssertionError("wrong solver")), \
                patch.object(study, "baseline_search", side_effect=AssertionError("GA must not run")), \
                patch.object(study.kakuro, "genetic_search", side_effect=AssertionError("GA must not run")), \
                patch.object(study.kakuro, "backtracking_search", side_effect=AssertionError("no fallback")):
            result = study.solve_case(PUZZLE, "roundingsat", seed=19, time_limit=2.5,
                                      population_size=1, generations=0)
        metrics = result["metrics"]
        self.assertTrue(study.verify_result(PUZZLE, result))
        self.assertTrue(metrics["solution_valid"])
        self.assertEqual(metrics["final_fitness"], 0)
        self.assertEqual(metrics["final_satisfied_runs_percent"], 100)
        self.assertEqual(metrics["roundingsat_decisions"], 13)
        self.assertEqual(metrics["roundingsat_conflicts"], 3)
        self.assertEqual(metrics["roundingsat_propagations"], 41)
        self.assertEqual(metrics["native_solver_time_seconds"], 0.12)
        self.assertEqual(metrics["opb_variables"], 36)
        self.assertEqual(metrics["opb_constraints"], 44)
        for key in GA_ONLY_METRICS + ("backtracking_count", "search_branches", "search_nodes",
                                      "cp_sat_conflicts", "domain_reduction_percent"):
            self.assertIsNone(metrics[key], key)
        self.assertFalse(metrics["fallback_used"])
        self.assertIsNone(result["ga_diagnostics"])
        self.assertEqual(solve.call_args.kwargs["seed"], 19)
        self.assertEqual(solve.call_args.kwargs["time_limit"], 2.5)

    def test_unknown_and_proven_infeasible_remain_distinct_without_fake_metrics(self):
        for status in ("UNKNOWN", "INFEASIBLE"):
            diagnostics = native_diagnostics(status)
            for key in ("native_decisions", "native_conflicts", "native_propagations",
                        "native_time_seconds"):
                diagnostics[key] = None
            with self.subTest(status=status), \
                    patch.object(study, "ensure_roundingsat_available"), \
                    patch.object(study, "roundingsat_search", return_value=(None, diagnostics)):
                result = study.solve_case(PUZZLE, "roundingsat")
            self.assertTrue(study.verify_result(PUZZLE, result))
            self.assertEqual(result["status"], status.lower())
            self.assertEqual(result["metrics"]["solver_status"], status)
            self.assertFalse(result["metrics"]["solution_valid"])
            self.assertEqual(result["metrics"]["white_cells_solved"], 0)
            self.assertIsNone(result["solved_grid"])
            self.assertIsNone(result["best_candidate_grid"])
            for key in ("final_fitness", "final_satisfied_runs_percent", "roundingsat_decisions",
                        "roundingsat_conflicts", "roundingsat_propagations", "native_solver_time_seconds"):
                self.assertIsNone(result["metrics"][key], key)

    def test_requested_artifact_directory_is_forwarded_to_native_backend(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(study, "ensure_roundingsat_available"), \
                patch.object(study, "roundingsat_search", return_value=(VALID, native_diagnostics())) as solve:
            artifact_dir = Path(directory) / "roundingsat_artifacts"
            study.solve_case(PUZZLE, "roundingsat", artifact_dir=artifact_dir)
        self.assertEqual(solve.call_args.kwargs["artifact_dir"], artifact_dir)

    def test_status_and_assignment_disagreement_or_invalid_model_fails(self):
        bad_candidates = (
            (None, "SOLVED"), (VALID, "UNKNOWN"), (VALID, "INFEASIBLE"),
            ({cell: 1 for cell in VALID}, "SOLVED"),
            ({(1, 1): 1}, "SOLVED"),
        )
        for candidate, status in bad_candidates:
            with self.subTest(candidate=candidate, status=status), \
                    patch.object(study, "ensure_roundingsat_available"), \
                    patch.object(study, "roundingsat_search", return_value=(candidate, native_diagnostics(status))):
                with self.assertRaises(ValueError):
                    study.solve_case(PUZZLE, "roundingsat")

    def test_native_search_counts_cannot_be_reported_as_ga_or_backtracks(self):
        with patch.object(study, "ensure_roundingsat_available"), \
                patch.object(study, "roundingsat_search", return_value=(VALID, native_diagnostics())):
            result = study.solve_case(PUZZLE, "roundingsat")
        for key in ("genetic_fitness_evaluations", "backtracking_count", "cp_sat_conflicts",
                    "search_branches", "search_nodes"):
            with self.subTest(metric=key):
                corrupt = copy.deepcopy(result)
                corrupt["metrics"][key] = 13
                with self.assertRaises(ValueError):
                    study.verify_result(PUZZLE, corrupt)

    def test_native_timeout_has_cleanup_grace_without_increasing_solver_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "puzzle.json"
            output_path = Path(directory) / "result.json"
            input_path.write_text(json.dumps(PUZZLE), encoding="utf-8")
            output_path.write_text("stale solution", encoding="utf-8")
            args = Namespace(population_size=160, generations=1500, timeout=19.5)

            def timeout(command, **kwargs):
                self.assertEqual(float(command[command.index("--timeout") + 1]), 19.5)
                self.assertEqual(kwargs["timeout"], 24.5)
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])

            with patch.object(study.subprocess, "run", side_effect=timeout):
                record = study.run_trial(PUZZLE, input_path, output_path, "roundingsat", 42, args)
            self.assertEqual(record["status"], "timeout")
            self.assertNotIn("result", record)
            self.assertFalse(output_path.exists())
            self.assertGreaterEqual(record["wall_time_seconds"], 0)

    def test_default_selection_does_not_require_optional_native_solver(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(study, "SIZES", []), \
                patch.object(study, "ensure_cp_sat_available"), \
                patch.object(study, "ensure_roundingsat_available", side_effect=AssertionError("optional solver")):
            study.main(["--output-dir", directory])

    @unittest.skipUnless(kakuro_roundingsat.DEFAULT_BINARY.is_file(),
                         "RoundingSat binary for this platform is optional outside the benchmark environment")
    def test_real_native_worker_returns_independently_valid_assignment_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "puzzle.json"
            output_path = Path(directory) / "roundingsat.json"
            input_path.write_text(json.dumps(PUZZLE), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, "-E", "-s", str(Path(study.__file__).resolve()), "--worker",
                 "--algorithm", "roundingsat", "--input", str(input_path), "--output", str(output_path),
                 "--generations", "0", "--timeout", "5"],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(study.verify_result(PUZZLE, result))
            self.assertTrue(result["metrics"]["solution_valid"])
            self.assertEqual(result["metrics"]["solver_status"], "SOLVED")
            self.assertEqual(result["metrics"]["opb_variables"], 36)
            self.assertEqual(result["metrics"]["opb_constraints"], 44)
            self.assertEqual(result["solver_diagnostics"]["native_status"], "SATISFIABLE")
            self.assertEqual(len(result["solver_diagnostics"]["binary_sha256"]), 64)
            opb_paths = list(Path(directory).rglob("kakuro.opb"))
            self.assertEqual(len(opb_paths), 1)
            for name in ("stdout.txt", "stderr.txt", "command.json"):
                self.assertTrue((opb_paths[0].parent / name).is_file(), name)
            command = json.loads((opb_paths[0].parent / "command.json").read_text(encoding="utf-8"))
            self.assertFalse(command["timed_out"])
            self.assertIn(command["returncode"], (0, 10))


if __name__ == "__main__":
    unittest.main()
