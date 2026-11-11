"""Encoding, native-protocol and subprocess-budget checks for RoundingSat."""

import copy
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import kakuro_roundingsat as rounding
from generate_and_solve import validate_solution


def tiny_case():
    cells = [(1, 1), (1, 2), (2, 1), (2, 2)]
    runs = [
        {"direction": "across", "cells": cells[:2], "sum": 3},
        {"direction": "across", "cells": cells[2:], "sum": 7},
        {"direction": "down", "cells": [cells[0], cells[2]], "sum": 4},
        {"direction": "down", "cells": [cells[1], cells[3]], "sum": 6},
    ]
    return cells, runs, dict(zip(cells, (1, 2, 3, 4)))


def model_line(candidate):
    tokens = []
    for index, cell in enumerate(sorted(candidate)):
        for digit in range(1, 10):
            tokens.append(("" if candidate[cell] == digit else "-") + f"x{9 * index + digit}")
    return "v " + " ".join(tokens) + "\n"


def read_constraints(opb):
    """A tiny independent OPB evaluator, used only in exhaustive model tests."""
    constraints = []
    for line in opb.splitlines():
        if line.startswith("*"):
            continue
        left, comparator, right = re.fullmatch(r"(.+?)\s+(>=|=)\s+(-?\d+);", line).groups()
        terms = [(int(coefficient), int(variable)) for coefficient, variable
                 in re.findall(r"([+-]?\d+) x(\d+)", left)]
        constraints.append((terms, comparator, int(right)))
    return constraints


def satisfies(constraints, assignment):
    for terms, comparator, right in constraints:
        total = sum(coefficient * assignment[variable] for coefficient, variable in terms)
        if (total != right if comparator == "=" else total < right):
            return False
    return True


class EncodingTests(unittest.TestCase):
    def test_all_6561_digit_assignments_agree_with_kakuro_rules(self):
        whites, runs, _ = tiny_case()
        opb = rounding.encode_kakuro_opb(whites, runs)
        constraints = read_constraints(opb)
        self.assertEqual(opb.splitlines()[0], "* #variable= 36 #constraint= 44")
        self.assertEqual(len(constraints), 44)
        count = 0
        for digits in itertools.product(range(1, 10), repeat=4):
            assignment = {9 * index + digit: int(digits[index] == digit)
                          for index in range(4) for digit in range(1, 10)}
            expected = all(sum(digits[whites.index(cell)] for cell in run["cells"]) == run["sum"]
                           and len({digits[whites.index(cell)] for cell in run["cells"]}) == len(run["cells"])
                           for run in runs)
            actual = satisfies(constraints, assignment)
            self.assertEqual(actual, expected, digits)
            count += actual
        self.assertEqual(count, 1)

    def test_duplicate_digits_fail_even_when_sum_matches(self):
        whites = [(1, 1), (1, 2)]
        constraints = read_constraints(rounding.encode_kakuro_opb(whites, [{"cells": whites, "sum": 4}]))
        for digits, expected in [((1, 3), True), ((3, 1), True), ((2, 2), False)]:
            assignment = {9 * index + digit: int(digits[index] == digit)
                          for index in range(2) for digit in range(1, 10)}
            self.assertEqual(satisfies(constraints, assignment), expected)

    def test_one_hot_and_coordinate_order(self):
        whites, runs, _ = tiny_case()
        opb = rounding.encode_kakuro_opb(whites, runs)
        self.assertEqual(opb, rounding.encode_kakuro_opb(list(reversed(whites)), runs))
        constraints = read_constraints(opb)
        assignment = {variable: 0 for variable in range(1, 37)}
        self.assertFalse(satisfies(constraints, assignment))
        assignment.update({1: 1, 2: 1, 11: 1, 21: 1, 31: 1})
        self.assertFalse(satisfies(constraints, assignment))


class NativeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.binary = self.directory / "roundingsat.exe"
        self.binary.write_bytes(b"fake binary for subprocess protocol tests")
        self.availability = patch.object(rounding, "ensure_roundingsat_available", return_value=self.binary)
        self.availability.start()
        self.whites, self.runs, self.solution = tiny_case()

    def tearDown(self):
        self.availability.stop()
        self.temporary.cleanup()

    def solve_output(self, stdout, code=0, **kwargs):
        result = subprocess.CompletedProcess([], code, stdout, "diagnostic stderr")
        with patch.object(rounding.subprocess, "run", return_value=result) as run:
            candidate, stats = rounding.roundingsat_search(self.whites, self.runs, **kwargs)
        return candidate, stats, run

    def test_sat_full_assignment_stats_and_saved_artifacts(self):
        output = ("c RoundingSat 2\nc commit abcdef\nc cpu time 0.125 s\n"
                  "c decisions 3\nc conflicts 2\nc propagations 40\nc restarts 1\n"
                  "c LP calls 2\ns SATISFIABLE\n" + model_line(self.solution))
        artifact_dir = self.directory / "artifacts"
        candidate, stats, run = self.solve_output(output, artifact_dir=artifact_dir)
        self.assertEqual(candidate, self.solution)
        self.assertEqual(stats["status"], "SOLVED")
        self.assertEqual(stats["native_status"], "SATISFIABLE")
        self.assertEqual(stats["native_decisions"], 3)
        self.assertEqual(stats["native_conflicts"], 2)
        self.assertEqual(stats["native_propagations"], 40)
        self.assertEqual(stats["native_restarts"], 1)
        self.assertEqual(stats["native_time_seconds"], 0.125)
        self.assertEqual(stats["solver_version"], "RoundingSat 2")
        self.assertEqual(stats["solver_commit"], "abcdef")
        self.assertTrue(stats["lp_used"])
        for key in ("branches", "conflicts", "nodes_visited", "backtracking_count"):
            self.assertIsNone(stats[key])
        self.assertFalse(stats["seed_applied"])
        argv = run.call_args.args[0]
        self.assertIn("--print-sol=1", argv)
        self.assertIn("--lp=1", argv)
        self.assertFalse(any("seed" in argument for argument in argv))
        self.assertGreater(run.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 120)
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual((artifact_dir / "stdout.txt").read_text(), output)
        self.assertEqual((artifact_dir / "stderr.txt").read_text(), "diagnostic stderr")
        record = json.loads((artifact_dir / "command.json").read_text())
        self.assertEqual(record["argv"], argv)
        self.assertEqual(record["returncode"], 0)
        self.assertEqual(record["binary_sha256"], stats["binary_sha256"])
        self.assertEqual(len(stats["binary_sha256"]), 64)
        self.assertTrue((artifact_dir / "kakuro.opb").exists())

    def test_sat_competition_exit_10_and_missing_stats(self):
        candidate, stats, _ = self.solve_output("s SATISFIABLE\n" + model_line(self.solution), 10)
        self.assertEqual(candidate, self.solution)
        self.assertIsNone(stats["native_conflicts"])
        self.assertIsNone(stats["native_time_seconds"])

    def test_unsat_and_unknown_native_exit_conventions(self):
        for output, code, expected in [("UNSATISFIABLE", 0, "INFEASIBLE"),
                                       ("UNSATISFIABLE", 20, "INFEASIBLE"),
                                       ("UNKNOWN", 0, "UNKNOWN"),
                                       ("TIMELIMIT", 0, "UNKNOWN"),
                                       ("TIMELIMIT", 4, "UNKNOWN")]:
            with self.subTest(status=output, code=code):
                candidate, stats, _ = self.solve_output(f"s {output}\n", code)
                self.assertIsNone(candidate)
                self.assertEqual(stats["status"], expected)
                self.assertEqual(stats["timed_out"], output == "TIMELIMIT")

    def test_crashes_and_status_exit_mismatches_are_errors(self):
        for output, code in [("s SATISFIABLE\n" + model_line(self.solution), 20),
                             ("s UNSATISFIABLE\n", 10), ("s UNSATISFIABLE\n", 1),
                             ("s UNKNOWN\n", 20), ("s TIMELIMIT\n", 3),
                             ("", 0), ("Error: invalid option\n", 1),
                             ("s SATISFIABLE\ns UNSATISFIABLE\n", 0),
                             ("s OPTIMUM FOUND\n", 0),
                             ("s UNSATISFIABLE\n" + model_line(self.solution), 0)]:
            with self.subTest(output=output, code=code), self.assertRaises(RuntimeError):
                self.solve_output(output, code)

    def test_bad_sat_models_are_errors(self):
        valid = model_line(self.solution)
        invalid = ["", "v x1\n", valid + "v -x1\n", valid.replace("-x2", "x2", 1),
                   valid.replace("x1", "-x1", 1), valid.replace("-x36", "-x37"),
                   valid.replace("-x36", "-36"), valid.replace("-x36", "x0")]
        incorrect = dict(self.solution)
        incorrect[(1, 1)] = 3
        invalid.append(model_line(incorrect))
        for model in invalid:
            with self.subTest(model=model), self.assertRaises(RuntimeError):
                self.solve_output("s SATISFIABLE\n" + model)

    def test_timeout_preserves_partial_logs_and_never_claims_infeasibility(self):
        artifact_dir = self.directory / "timeout"
        timeout = subprocess.TimeoutExpired([str(self.binary)], .1,
                                            output=b"c RoundingSat 2\nc decisions 7\n", stderr=b"partial")
        with patch.object(rounding.subprocess, "run", side_effect=timeout):
            candidate, stats = rounding.roundingsat_search(self.whites, self.runs, artifact_dir=artifact_dir)
        self.assertIsNone(candidate)
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertTrue(stats["timed_out"])
        self.assertIsNone(stats["native_status"])
        self.assertIsNone(stats["native_returncode"])
        self.assertEqual(stats["native_decisions"], 7)
        self.assertEqual((artifact_dir / "stderr.txt").read_text(), "partial")

    def test_zero_budget_never_launches(self):
        with patch.object(rounding.subprocess, "run") as run:
            candidate, stats = rounding.roundingsat_search(self.whites, self.runs, time_limit=0)
        run.assert_not_called()
        self.assertIsNone(candidate)
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertTrue(stats["timed_out"])

    def test_budget_includes_model_encoding(self):
        with patch.object(rounding.time, "perf_counter", side_effect=[10.0, 11.1, 11.2]), \
                patch.object(rounding.subprocess, "run") as run:
            candidate, stats = rounding.roundingsat_search(self.whites, self.runs, time_limit=1)
        run.assert_not_called()
        self.assertIsNone(candidate)
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertAlmostEqual(stats["execution_time_seconds"], 1.2)

    def test_late_native_verdict_does_not_escape_total_budget(self):
        with patch.object(rounding.time, "perf_counter", side_effect=[10.0, 10.1, 11.2]):
            candidate, stats, _ = self.solve_output("s UNSATISFIABLE\n", time_limit=1)
        self.assertIsNone(candidate)
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertEqual(stats["native_status"], "UNSATISFIABLE")
        self.assertTrue(stats["timed_out"])


class AvailabilityTests(unittest.TestCase):
    def test_environment_path_and_missing_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "solver.exe"
            with patch.dict(os.environ, {"ROUNDINGSAT_BIN": str(path)}):
                with self.assertRaises(FileNotFoundError):
                    rounding.ensure_roundingsat_available()
                path.write_bytes(b"test")
                self.assertEqual(rounding.ensure_roundingsat_available(), path.resolve())

    def test_bad_options_and_run_references(self):
        whites, runs, _ = tiny_case()
        for kwargs in ({"seed": True}, {"seed": -1}, {"time_limit": -1},
                       {"time_limit": float("inf")}, {"time_limit": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                rounding.roundingsat_search(whites, runs, **kwargs)
        with self.assertRaises(ValueError):
            rounding.encode_kakuro_opb(whites, [{"cells": [(1, 1), (9, 9)], "sum": 3}])


@unittest.skipUnless(os.environ.get("KAKURO_NATIVE_ROUNDINGSAT_TESTS") == "1",
                     "set KAKURO_NATIVE_ROUNDINGSAT_TESTS=1 for native integration smoke tests")
class NativeIntegrationTests(unittest.TestCase):
    def test_real_binary_sat_and_unsat(self):
        whites, runs, solution = tiny_case()
        candidate, stats = rounding.roundingsat_search(whites, runs, time_limit=10)
        self.assertEqual(candidate, solution)
        self.assertTrue(validate_solution(candidate, whites, runs))
        self.assertEqual(stats["status"], "SOLVED")
        self.assertEqual(stats["solver_version"], "RoundingSat 2")
        impossible = copy.deepcopy(runs)
        impossible[0]["sum"] = 2
        candidate, stats = rounding.roundingsat_search(whites, impossible, time_limit=10)
        self.assertIsNone(candidate)
        self.assertEqual(stats["status"], "INFEASIBLE")


if __name__ == "__main__":
    unittest.main()
