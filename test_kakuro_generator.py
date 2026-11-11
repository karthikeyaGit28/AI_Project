"""Checks for rectangular benchmark layouts and their constructive solutions."""

import unittest

from generate_and_solve import parse_puzzle
from kakuro_generator import _generate_with_witness, generate_rectangular_puzzle


REQUESTED_SIZES = (
    (4, 4), (5, 5), (6, 6), (8, 8), (10, 10), (12, 12),
    (15, 15), (16, 16), (11, 17), (13, 17), (14, 14), (14, 17),
)


class RectangularGeneratorTests(unittest.TestCase):
    def test_requested_dimensions_both_conventions_have_valid_witnesses(self):
        for extra_border in (0, 1):
            for requested_rows, requested_columns in REQUESTED_SIZES:
                rows = requested_rows + extra_border
                columns = requested_columns + extra_border
                for seed in (42, 43, 44):
                    with self.subTest(rows=rows, columns=columns, seed=seed):
                        puzzle, witness = _generate_with_witness(rows, columns, seed)
                        self.assertEqual(len(puzzle["grid"]), rows)
                        self.assertEqual({len(row) for row in puzzle["grid"]}, {columns})
                        _, whites, runs = parse_puzzle(puzzle)
                        self.assertEqual(set(whites), set(witness))
                        for run in runs:
                            values = [witness[cell] for cell in run["cells"]]
                            self.assertTrue(2 <= len(values) <= 9)
                            self.assertTrue(all(type(value) is int and 1 <= value <= 9 for value in values))
                            self.assertEqual(len(values), len(set(values)))
                            self.assertEqual(sum(values), run["sum"])
                        self.assertEqual({r for r, _ in whites}, set(range(1, rows)))
                        self.assertEqual({c for _, c in whites}, set(range(1, columns)))
                        unseen = set(whites)
                        frontier = [unseen.pop()]
                        while frontier:
                            r, c = frontier.pop()
                            for neighbor in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                                if neighbor in unseen:
                                    unseen.remove(neighbor)
                                    frontier.append(neighbor)
                        self.assertFalse(unseen, "White region must be connected for benchmark grids")

    def test_seed_is_reproducible_and_changes_puzzle(self):
        for rows, columns in REQUESTED_SIZES:
            self.assertEqual(generate_rectangular_puzzle(rows, columns, 42),
                             generate_rectangular_puzzle(rows, columns, 42))
            self.assertNotEqual(generate_rectangular_puzzle(rows, columns, 42)["grid"],
                                generate_rectangular_puzzle(rows, columns, 43)["grid"])

    def test_invalid_dimensions(self):
        for rows, columns in ((2, 3), (3, 2), (True, 4), (4, False), (3.5, 4), (4, "5")):
            with self.subTest(rows=rows, columns=columns), self.assertRaises(ValueError):
                generate_rectangular_puzzle(rows, columns, 42)


if __name__ == "__main__":
    unittest.main()
