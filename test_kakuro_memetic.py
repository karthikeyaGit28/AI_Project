"""Checks for the memetic algorithm (hybrid GA plus local search)."""

import random
import unittest

import generate_and_solve as kakuro
from kakuro_generator import generate_rectangular_puzzle
from kakuro_memetic import _RunNeighbourhood, memetic_search


def arguments(puzzle):
    _, whites, runs = kakuro.parse_puzzle(puzzle)
    domains = kakuro.propagate(whites, runs)
    across = [run for run in runs if run["direction"] == "across"]
    down = [run for run in runs if run["direction"] == "down"]
    return (whites, across, down, domains), runs


class NeighbourhoodTests(unittest.TestCase):
    def check_candidates(self, run, domains, limit):
        neighbourhood = _RunNeighbourhood(run, domains, limit)
        rng = random.Random(7)
        current = neighbourhood.sample(rng)
        seen = 0
        for changes in neighbourhood.candidates(current, rng, random_neighbours=4):
            values = list(current)
            for position, value in changes:
                self.assertNotEqual(values[position], value)
                values[position] = value
            self.assertEqual(sum(values), run["sum"])
            self.assertEqual(len(set(values)), len(values))
            for cell, value in zip(run["cells"], values):
                self.assertIn(value, domains[cell])
            seen += 1
        return neighbourhood, seen

    def test_every_neighbour_keeps_the_across_run_valid(self):
        (_, across, _, domains), _ = arguments(generate_rectangular_puzzle(12, 12, 42))
        for run in across:
            with self.subTest(cells=run["cells"]):
                full, _ = self.check_candidates(run, domains, limit=10 ** 6)
                self.assertEqual(len(full.assignments), full.assignment_count)
                self.assertEqual(sorted(full.assignments),
                                 sorted(kakuro.run_combinations(run, domains)))
                pairs, _ = self.check_candidates(run, domains, limit=0)
                self.assertIsNone(pairs.assignments)

    def test_unconstrained_long_run_uses_pair_moves(self):
        run = {"direction": "across", "sum": 45, "cells": [(0, c) for c in range(9)]}
        domains = {cell: set(range(1, 10)) for cell in run["cells"]}
        neighbourhood, seen = self.check_candidates(run, domains, limit=128)
        self.assertEqual(neighbourhood.assignment_count, 362880)
        self.assertIsNone(neighbourhood.assignments)
        self.assertGreaterEqual(seen, 36)  # at least every swap


class MemeticSearchTests(unittest.TestCase):
    def test_solves_small_and_medium_puzzles_without_fallback(self):
        for puzzle in (kakuro.generate_puzzle(3, 42), generate_rectangular_puzzle(6, 6, 42),
                       generate_rectangular_puzzle(8, 8, 42)):
            with self.subTest(rows=len(puzzle["grid"])):
                (whites, across, down, domains), runs = arguments(puzzle)
                solution, stats = memetic_search(whites, across, down, domains, 42,
                                                 population_size=40, generations=200)
                self.assertTrue(kakuro.validate_solution(solution, whites, runs))
                self.assertEqual(stats["best_fitness"], 0)
                self.assertEqual(stats["best_candidate"], solution)
                self.assertIn(stats["stop_reason"], ("solved", "solved_by_local_search"))

    def test_seeded_search_is_reproducible(self):
        (whites, across, down, domains), _ = arguments(generate_rectangular_puzzle(10, 10, 43))
        first = memetic_search(whites, across, down, domains, 5, population_size=20, generations=15)
        second = memetic_search(whites, across, down, domains, 5, population_size=20, generations=15)
        for stats in (first[1], second[1]):
            stats.pop("local_search_time_seconds")
            stats.pop("execution_time_seconds")
        self.assertEqual(first, second)

    def test_unsolved_search_reports_consistent_best_candidate(self):
        (whites, across, down, domains), runs = arguments(generate_rectangular_puzzle(12, 12, 42))
        solution, stats = memetic_search(whites, across, down, domains, 42, population_size=4,
                                         generations=3, local_search_rate=0.0)
        self.assertIsNone(solution)
        self.assertEqual(stats["stop_reason"], "generation_limit")
        self.assertEqual(stats["local_search_calls"], 0)
        self.assertEqual(stats["evaluations"], 12)
        self.assertEqual(stats["generations_evaluated"], 3)
        self.assertEqual(len(stats["fitness_history"]), 3)
        self.assertEqual(stats["fitness_history"], sorted(stats["fitness_history"], reverse=True))
        # Across clues always hold, so the down-run score equals the all-run score.
        self.assertEqual(kakuro.fitness(stats["best_candidate"], runs), stats["best_fitness"])
        self.assertGreater(stats["best_fitness"], 0)

    def test_local_search_never_worsens_and_is_counted(self):
        (whites, across, down, domains), _ = arguments(generate_rectangular_puzzle(15, 15, 42))
        _, stats = memetic_search(whites, across, down, domains, 1, population_size=10,
                                  generations=2, local_search_rate=1.0)
        self.assertGreater(stats["local_search_calls"], 0)
        self.assertGreater(stats["local_search_neighbours"], 0)
        self.assertGreaterEqual(stats["local_search_fitness_reduction"], 0)
        self.assertLessEqual(stats["local_search_improving_moves"] + stats["local_search_sideways_moves"],
                             stats["local_search_steps"])

    def test_zero_budget_and_time_limit(self):
        (whites, across, down, domains), _ = arguments(generate_rectangular_puzzle(8, 8, 42))
        solution, stats = memetic_search(whites, across, down, domains, 42, generations=0)
        self.assertIsNone(solution)
        self.assertIsNone(stats["best_candidate"])
        self.assertEqual(stats["evaluations"], 0)
        solution, stats = memetic_search(whites, across, down, domains, 42, time_limit=0)
        self.assertIsNone(solution)
        self.assertEqual(stats["stop_reason"], "time_limit")
        self.assertEqual(stats["evaluations"], 0)

    def test_invalid_options_are_rejected(self):
        (whites, across, down, domains), _ = arguments(kakuro.generate_puzzle(3, 42))
        for options in ({"population_size": 0}, {"generations": -1}, {"local_search_rate": 1.5},
                        {"local_search_rate": True}, {"local_search_steps": -1},
                        {"neighbourhood_limit": 2.0}, {"time_limit": -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                memetic_search(whites, across, down, domains, 42, **options)


if __name__ == "__main__":
    unittest.main()

