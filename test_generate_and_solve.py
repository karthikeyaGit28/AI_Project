"""Regression checks for Kakuro rules, search, and file handling.

Run with: python -m unittest -v
"""

import copy
import itertools
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import generate_and_solve as kakuro


PROJECT = Path(__file__).resolve().parent
SCRIPT = PROJECT / "generate_and_solve.py"


def rectangular_puzzle():
    # One valid filling is [1, 2, 3] / [2, 3, 4].
    return {
        "format": "kakuro-grid-v1",
        "grid": [
            ["#", {"down": 3}, {"down": 5}, {"down": 7}],
            [{"across": 6}, None, None, None],
            [{"across": 9}, None, None, None],
        ],
    }


def blocked_puzzle():
    # Two independent 2-by-2 regions separated by blocks and clue cells.
    return {
        "format": "kakuro-grid-v1",
        "grid": [
            ["#", {"down": 3}, {"down": 5}, "#", "#", {"down": 7}, {"down": 9}],
            [{"across": 3}, None, None, "#", {"across": 7}, None, None],
            [{"across": 5}, None, None, "#", {"across": 9}, None, None],
        ],
    }


class KakuroAssertions(unittest.TestCase):
    def assertKakuroSolution(self, solution, whites, runs):
        self.assertIsNotNone(solution)
        self.assertEqual(set(solution), set(whites))
        for value in solution.values():
            self.assertIs(type(value), int)
            self.assertIn(value, range(1, 10))
        for run in runs:
            values = [solution[cell] for cell in run["cells"]]
            self.assertEqual(sum(values), run["sum"])
            self.assertEqual(len(values), len(set(values)))
        self.assertTrue(kakuro.validate_solution(solution, whites, runs))


class ParserTests(unittest.TestCase):
    def test_rectangular_and_blocked_grids(self):
        for puzzle in (rectangular_puzzle(), blocked_puzzle()):
            with self.subTest(grid=puzzle["grid"]):
                grid, whites, runs = kakuro.parse_puzzle(puzzle)
                self.assertEqual(grid, puzzle["grid"])
                for cell in whites:
                    for direction in ("across", "down"):
                        self.assertEqual(
                            sum(cell in run["cells"] for run in runs
                                if run["direction"] == direction),
                            1,
                        )

    def test_format_is_optional_but_must_be_supported(self):
        puzzle = rectangular_puzzle()
        del puzzle["format"]
        kakuro.parse_puzzle(puzzle)
        puzzle["format"] = "unknown-format"
        with self.assertRaises(ValueError):
            kakuro.parse_puzzle(puzzle)

    def test_rejects_invalid_structure_and_cell_types(self):
        malformed = [
            None,
            [],
            {},
            {"grid": None},
            {"grid": []},
            {"grid": [[]]},
            {"grid": [None]},
            {"grid": "not a grid"},
            {"grid": [["#"], ["#", None]]},
            {"grid": [["#"]]},
        ]
        for cell in (0, 1, True, "?", [], {}, {"sideways": 6}, {"down": 3, "typo": 1}):
            puzzle = rectangular_puzzle()
            puzzle["grid"][0][1] = cell
            malformed.append(puzzle)
        for puzzle in malformed:
            with self.subTest(puzzle=puzzle), self.assertRaises(ValueError):
                kakuro.parse_puzzle(puzzle)

    def test_every_white_cell_needs_both_directions(self):
        malformed = [
            {"grid": [[{"across": 3}, None, None]]},
            {"grid": [[{"down": 3}], [None], [None]]},
        ]
        missing_across = rectangular_puzzle()
        missing_across["grid"][1][0] = "#"
        malformed.append(missing_across)
        missing_down = rectangular_puzzle()
        missing_down["grid"][0][1] = "#"
        malformed.append(missing_down)
        for puzzle in malformed:
            with self.subTest(puzzle=puzzle), self.assertRaises(ValueError):
                kakuro.parse_puzzle(puzzle)

    def test_clue_types_and_length_specific_sum_bounds(self):
        # A run of two distinct digits must total between 3 and 17.
        for clue in (True, False, 3.0, "3", None, 0, 2, 18, 46):
            puzzle = rectangular_puzzle()
            puzzle["grid"][0][1] = {"down": clue}
            with self.subTest(clue=clue), self.assertRaises(ValueError):
                kakuro.parse_puzzle(puzzle)

    def test_rejects_empty_one_cell_and_overlong_runs(self):
        malformed = [
            {"grid": [[{"across": 3}, "#"]]},
            {"grid": [["#", {"down": 1}], [{"across": 1}, None]]},
            {"grid": [
                ["#"] + [{"down": 3} for _ in range(10)],
                [{"across": 45}] + [None] * 10,
                [{"across": 45}] + [None] * 10,
            ]},
        ]
        for puzzle in malformed:
            with self.subTest(puzzle=puzzle), self.assertRaises(ValueError):
                kakuro.parse_puzzle(puzzle)


class SearchTests(KakuroAssertions):
    def test_run_assignments_and_supports_match_brute_force(self):
        rng = random.Random(412)
        for case in range(60):
            length = rng.randint(2, 5)
            cells = [(0, i) for i in range(length)]
            domains = {cell: set(rng.sample(range(1, 10), rng.randint(1, 5)))
                       for cell in cells}
            total = rng.randint(length * (length + 1) // 2, length * (19 - length) // 2)
            run = {"direction": "across", "sum": total, "cells": cells}
            expected = {
                values for values in itertools.product(*(domains[cell] for cell in cells))
                if sum(values) == total and len(set(values)) == length
            }
            with self.subTest(case=case, run=run, domains=domains):
                actual = kakuro.run_combinations(run, domains)
                self.assertEqual(set(actual), expected)
                self.assertEqual(len(actual), len(set(actual)))
                if expected:
                    propagated = kakuro._propagate([run], copy.deepcopy(domains))
                    self.assertEqual(propagated, {
                        cell: {values[i] for values in expected}
                        for i, cell in enumerate(cells)
                    })
                else:
                    with self.assertRaises(ValueError):
                        kakuro._propagate([run], copy.deepcopy(domains))

    def test_two_by_two_solver_feasibility_matches_brute_force(self):
        # Enumerate the complete solution space independently of solver helpers.
        solutions_by_clues = {}
        for a, b, c, d in itertools.product(range(1, 10), repeat=4):
            if a == b or a == c or b == d or c == d:
                continue
            clues = (a + b, c + d, a + c, b + d)
            solutions_by_clues.setdefault(clues, []).append((a, b, c, d))
        rng = random.Random(914)
        cases = rng.sample(list(solutions_by_clues), 20)
        cases.extend(tuple(rng.randint(3, 17) for _ in range(4)) for _ in range(20))
        for clues in cases:
            row1, row2, col1, col2 = clues
            puzzle = {"grid": [
                ["#", {"down": col1}, {"down": col2}],
                [{"across": row1}, None, None],
                [{"across": row2}, None, None],
            ]}
            _, whites, runs = kakuro.parse_puzzle(puzzle)
            expected = solutions_by_clues.get(clues, [])
            with self.subTest(clues=clues):
                try:
                    domains = kakuro.propagate(whites, runs)
                except ValueError:
                    self.assertFalse(expected, "Propagation incorrectly removed a valid solution")
                    continue
                for values in expected:
                    for cell, value in zip(whites, values):
                        self.assertIn(value, domains[cell])
                solution, _ = kakuro.backtracking_search(whites, runs, domains)
                if expected:
                    self.assertKakuroSolution(solution, whites, runs)
                    self.assertIn(tuple(solution[cell] for cell in whites), expected)
                else:
                    self.assertIsNone(solution)

    def test_generator_reproducibility_and_seed_variation(self):
        for size in range(2, 9):
            with self.subTest(size=size):
                generated = [kakuro.generate_puzzle(size, seed) for seed in range(4)]
                self.assertEqual(generated[0], kakuro.generate_puzzle(size, 0))
                self.assertGreater(len({json.dumps(p["grid"]) for p in generated}), 1)
                for puzzle in generated:
                    _, whites, _ = kakuro.parse_puzzle(puzzle)
                    self.assertEqual(len(whites), size * size)

    def test_generator_rejects_invalid_size(self):
        for size in (-1, 0, 1, 10, True, 3.5, "3"):
            with self.subTest(size=size), self.assertRaises(ValueError):
                kakuro.generate_puzzle(size, 42)

    def test_backtracking_solves_small_and_maximum_supported_sizes(self):
        for size in (2, 3, 5, 9):
            with self.subTest(size=size):
                _, whites, runs = kakuro.parse_puzzle(kakuro.generate_puzzle(size, 42))
                domains = kakuro.propagate(whites, runs)
                before = copy.deepcopy(domains)
                solution, backtracks = kakuro.backtracking_search(whites, runs, domains)
                self.assertKakuroSolution(solution, whites, runs)
                self.assertGreaterEqual(backtracks, 0)
                self.assertEqual(domains, before)

    def test_genetic_search_and_zero_generation_fallback(self):
        _, whites, runs = kakuro.parse_puzzle(kakuro.generate_puzzle(2, 42))
        domains = kakuro.propagate(whites, runs)
        across = [run for run in runs if run["direction"] == "across"]
        down = [run for run in runs if run["direction"] == "down"]
        solution, evaluations = kakuro.genetic_search(
            whites, across, down, domains, seed=42,
        )
        self.assertKakuroSolution(solution, whites, runs)
        self.assertGreater(evaluations, 0)
        solution, evaluations = kakuro.genetic_search(
            whites, across, down, domains, seed=42, generations=0,
        )
        self.assertIsNone(solution)
        self.assertEqual(evaluations, 0)

    def test_unsatisfiable_puzzle_is_detected(self):
        # Row sums total 6; column sums total 7. Every individual clue is feasible.
        puzzle = {"grid": [
            ["#", {"down": 3}, {"down": 4}],
            [{"across": 3}, None, None],
            [{"across": 3}, None, None],
        ]}
        _, whites, runs = kakuro.parse_puzzle(puzzle)
        with self.assertRaises(ValueError):
            kakuro.propagate(whites, runs)
        domains = {cell: set(range(1, 10)) for cell in whites}
        solution, _ = kakuro.backtracking_search(whites, runs, domains)
        self.assertIsNone(solution)

    def test_validation_rejects_bool_wrong_digits_and_incomplete_assignments(self):
        _, whites, runs = kakuro.parse_puzzle(rectangular_puzzle())
        valid = {(1, 1): 1, (1, 2): 2, (1, 3): 3,
                 (2, 1): 2, (2, 2): 3, (2, 3): 4}
        self.assertKakuroSolution(valid, whites, runs)
        for value in (True, 0, 10, 1.0, "1", 2):
            invalid = dict(valid)
            invalid[(1, 1)] = value
            with self.subTest(value=value):
                self.assertFalse(kakuro.validate_solution(invalid, whites, runs))
        incomplete = dict(valid)
        del incomplete[(1, 1)]
        self.assertFalse(kakuro.validate_solution(incomplete, whites, runs))
        self.assertFalse(kakuro.validate_solution({**valid, (0, 0): 1}, whites, runs))
        self.assertFalse(kakuro.validate_solution(None, whites, runs))

    def test_checked_in_solution_satisfies_checked_in_puzzle(self):
        puzzle = json.loads((PROJECT / "kakuro_puzzle.json").read_text(encoding="utf-8"))
        result = json.loads((PROJECT / "kakuro_solution.json").read_text(encoding="utf-8"))
        _, whites, runs = kakuro.parse_puzzle(puzzle)
        if "solved_grid" in result:
            solution = {cell: result["solved_grid"][cell[0]][cell[1]] for cell in whites}
        else:
            solution = {cell: result["solution"][cell[0] - 1][cell[1] - 1] for cell in whites}
        self.assertKakuroSolution(solution, whites, runs)
        self.assertTrue(result["metrics"]["solution_valid"])


class CommandLineTests(KakuroAssertions):
    def run_cli(self, directory, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)],
            cwd=directory, text=True, capture_output=True, timeout=60,
        )

    def test_solves_input_without_overwriting_and_preserves_shape(self):
        for puzzle in (rectangular_puzzle(), blocked_puzzle()):
            with self.subTest(puzzle=puzzle), tempfile.TemporaryDirectory() as directory:
                input_path = Path(directory) / "custom.json"
                output_path = Path(directory) / "answer.json"
                original = json.dumps(puzzle, indent=4).encode("utf-8")
                input_path.write_bytes(original)
                process = self.run_cli(
                    directory, "--input", input_path, "--output", output_path,
                    "--generations", 0,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(input_path.read_bytes(), original)
                result = json.loads(output_path.read_text(encoding="utf-8"))
                grid, whites, runs = kakuro.parse_puzzle(puzzle)
                solved_grid = result["solved_grid"]
                self.assertEqual(len(solved_grid), len(grid))
                self.assertEqual([len(row) for row in solved_grid], [len(row) for row in grid])
                solution = {cell: solved_grid[cell[0]][cell[1]] for cell in whites}
                self.assertKakuroSolution(solution, whites, runs)
                for r, row in enumerate(grid):
                    for c, cell in enumerate(row):
                        if cell is not None:
                            self.assertEqual(solved_grid[r][c], cell)
                self.assertEqual(result["solution"], [
                    [solution.get((r, c)) for c in range(1, len(grid[0]))]
                    for r in range(1, len(grid))
                ])
                self.assertEqual(result["metrics"]["genetic_fitness_evaluations"], 0)
                self.assertTrue(result["metrics"]["solution_valid"])

    def test_explicit_missing_input_fails_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "missing.json"
            output_path = Path(directory) / "answer.json"
            process = self.run_cli(directory, "--input", input_path, "--output", output_path)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(input_path.exists())
            self.assertFalse(output_path.exists())
            self.assertNotIn("Traceback", process.stderr)

    def test_default_generates_when_missing_then_reads_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            process = self.run_cli(directory, "--size", 2, "--generations", 0)
            self.assertEqual(process.returncode, 0, process.stderr)
            input_path = Path(directory) / "kakuro_puzzle.json"
            self.assertTrue(input_path.exists())
            input_path.write_text(json.dumps(rectangular_puzzle()), encoding="utf-8")
            original = input_path.read_bytes()
            process = self.run_cli(directory, "--generations", 0)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(input_path.read_bytes(), original)

    def test_explicit_generation_uses_requested_size(self):
        with tempfile.TemporaryDirectory() as directory:
            process = self.run_cli(directory, "--generate", "--size", 2, "--generations", 0)
            self.assertEqual(process.returncode, 0, process.stderr)
            puzzle = json.loads((Path(directory) / "kakuro_puzzle.json").read_text(encoding="utf-8"))
            _, whites, _ = kakuro.parse_puzzle(puzzle)
            self.assertEqual(len(whites), 4)

    def test_invalid_input_reports_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "invalid.json"
            input_path.write_text('{"grid": []}', encoding="utf-8")
            original = input_path.read_bytes()
            process = self.run_cli(directory, "--input", input_path)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(input_path.read_bytes(), original)
            self.assertNotIn("Traceback", process.stderr)

    def test_same_input_and_output_path_does_not_destroy_puzzle(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "puzzle.json"
            input_path.write_text(json.dumps(rectangular_puzzle()), encoding="utf-8")
            original = input_path.read_bytes()
            process = self.run_cli(
                directory, "--input", input_path, "--output", input_path,
                "--generations", 0,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(input_path.read_bytes(), original)
            self.assertNotIn("Traceback", process.stderr)

    def test_unsatisfiable_input_writes_failed_result(self):
        puzzle = {"grid": [
            ["#", {"down": 3}, {"down": 4}],
            [{"across": 3}, None, None],
            [{"across": 3}, None, None],
        ]}
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "impossible.json"
            output_path = Path(directory) / "answer.json"
            input_path.write_text(json.dumps(puzzle), encoding="utf-8")
            original = input_path.read_bytes()
            process = self.run_cli(
                directory, "--input", input_path, "--output", output_path,
                "--generations", 0,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(input_path.read_bytes(), original)
            self.assertNotIn("Traceback", process.stderr)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIsNone(result["solution"])
            self.assertIsNone(result["solved_grid"])
            self.assertIsNone(result["board"])
            self.assertFalse(result["metrics"]["solution_valid"])
            self.assertEqual(result["metrics"]["white_cells_solved"], 0)
            self.assertEqual(result["metrics"]["white_cells_total"], 4)
            self.assertEqual(result["metrics"]["solution_validity_rate_percent"], 0.0)
            self.assertTrue(result["error"])


if __name__ == "__main__":
    unittest.main()
