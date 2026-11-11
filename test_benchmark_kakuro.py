"""Fast checks of benchmark verification, subprocess handling, and averages."""

import copy
import json
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import benchmark_kakuro as benchmark


def puzzle_and_result():
    puzzle = {"grid": [
        ["#", {"down": 3}, {"down": 5}, {"down": 7}],
        [{"across": 6}, None, None, None],
        [{"across": 9}, None, None, None],
    ]}
    result = {
        "algorithm": "genetic algorithm",
        "solved_grid": [
            ["#", {"down": 3}, {"down": 5}, {"down": 7}],
            [{"across": 6}, 1, 2, 3],
            [{"across": 9}, 2, 3, 4],
        ],
        "metrics": {
            "execution_time_seconds": 0.2,
            "backtracking_count": 0,
            "genetic_fitness_evaluations": 160,
            "solution_valid": True,
            "white_cells_solved": 6,
            "white_cells_total": 6,
            "solution_validity_rate_percent": 100.0,
        },
    }
    return puzzle, result


class IndependentValidationTests(unittest.TestCase):
    def test_correct_solution_and_corrupt_outputs(self):
        puzzle, result = puzzle_and_result()
        self.assertTrue(benchmark.independent_validation(puzzle, result))
        invalid = []
        for value in (True, 0, 10, "1", 2):
            changed = copy.deepcopy(result)
            changed["solved_grid"][1][1] = value
            invalid.append(changed)
        changed = copy.deepcopy(result)
        changed["solved_grid"][0][1] = {"down": 99}
        invalid.append(changed)
        changed = copy.deepcopy(result)
        changed["solved_grid"][1].pop()
        invalid.append(changed)
        changed = copy.deepcopy(result)
        changed["solved_grid"].pop()
        invalid.extend((changed, {"solved_grid": None}, {}))
        for changed in invalid:
            with self.subTest(result=changed):
                self.assertFalse(benchmark.independent_validation(puzzle, changed))

    def test_missing_direction_is_rejected(self):
        puzzle, result = puzzle_and_result()
        puzzle["grid"][0][1] = "#"
        result["solved_grid"][0][1] = "#"
        self.assertFalse(benchmark.independent_validation(puzzle, result))


class TrialTests(unittest.TestCase):
    def args(self, directory, convention="inner"):
        return Namespace(output_dir=Path(directory), size_convention=convention,
                         population_size=160, generations=1500, timeout=120)

    def fake_process(self, result, returncode=0):
        def run(command, **kwargs):
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(json.dumps(result), encoding="utf-8")
            self.assertEqual(kwargs["timeout"], 120)
            return subprocess.CompletedProcess(command, returncode, "", "mock error")
        return run

    def test_completed_trial_passes_correct_settings_and_dimensions(self):
        puzzle, result = puzzle_and_result()
        for convention, expected in (("inner", (5, 7)), ("board", (4, 6))):
            with tempfile.TemporaryDirectory() as directory, \
                    patch.object(benchmark, "generate_rectangular_puzzle", return_value=puzzle) as generate, \
                    patch.object(benchmark.subprocess, "run", side_effect=self.fake_process(result)) as process:
                record = benchmark.run_trial(4, 6, 42, self.args(directory, convention))
                generate.assert_called_once_with(*expected, 42)
                self.assertEqual(record["status"], "completed")
                self.assertTrue(record["independently_valid"])
                self.assertEqual(record["white_cells_total"], 6)
                self.assertEqual(record["clue_runs"], 5)
                command = process.call_args.args[0]
                self.assertEqual(command[command.index("--seed") + 1], "42")
                self.assertEqual(command[command.index("--generations") + 1], "1500")
                self.assertEqual(json.loads(Path(record["puzzle_file"]).read_text()), puzzle)

    def test_timeout_and_nonzero_exit_are_retained_without_invented_metrics(self):
        puzzle, result = puzzle_and_result()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(benchmark, "generate_rectangular_puzzle", return_value=puzzle):
            with patch.object(benchmark.subprocess, "run", side_effect=subprocess.TimeoutExpired("solver", 120)):
                record = benchmark.run_trial(4, 4, 42, self.args(directory))
            self.assertEqual(record["status"], "timeout")
            self.assertFalse(record["independently_valid"])
            self.assertNotIn("metrics", record)
            with patch.object(benchmark.subprocess, "run", side_effect=self.fake_process(result, returncode=1)):
                record = benchmark.run_trial(4, 4, 42, self.args(directory))
            self.assertEqual(record["status"], "error")
            self.assertEqual(record["error"], "mock error")
            self.assertNotIn("metrics", record)

    def test_incorrect_reported_counts_are_invalid(self):
        puzzle, result = puzzle_and_result()
        result["metrics"]["white_cells_solved"] = 5
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(benchmark, "generate_rectangular_puzzle", return_value=puzzle), \
                patch.object(benchmark.subprocess, "run", side_effect=self.fake_process(result)):
            record = benchmark.run_trial(4, 4, 42, self.args(directory))
        self.assertEqual(record["status"], "invalid")


class SummaryTests(unittest.TestCase):
    def test_averages_exclude_failures_but_validity_includes_all_trials(self):
        _, result = puzzle_and_result()
        first = {"size": "4x4", "status": "completed", "white_cells_total": 6,
                 "clue_runs": 5, "algorithm": "genetic algorithm", "metrics": result["metrics"]}
        second = copy.deepcopy(first)
        second["algorithm"] = "backtracking fallback"
        second["metrics"].update(execution_time_seconds=0.4, backtracking_count=2,
                                 genetic_fitness_evaluations=240000)
        timeout = {"size": "4x4", "status": "timeout", "white_cells_total": 8, "clue_runs": 6}
        rows = benchmark.summarize([first, second, timeout], [(4, 4)])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["trials"], row["valid_trials"], row["timeouts"]), (3, 2, 1))
        self.assertAlmostEqual(row["validity_rate_percent"], 200 / 3)
        self.assertAlmostEqual(row["execution_time_seconds_mean"], 0.3)
        self.assertEqual(row["backtracking_count_mean"], 1)
        self.assertEqual(row["genetic_fitness_evaluations_mean"], 120080)
        self.assertEqual((row["ga_successes"], row["fallback_successes"]), (1, 1))
        self.assertEqual((row["white_cells_min"], row["white_cells_max"]), (6, 8))
        row = benchmark.summarize([timeout], [(4, 4)])[0]
        self.assertIsNone(row["execution_time_seconds_mean"])
        self.assertIsNone(row["backtracking_count_mean"])
        self.assertEqual(row["validity_rate_percent"], 0)


if __name__ == "__main__":
    unittest.main()
