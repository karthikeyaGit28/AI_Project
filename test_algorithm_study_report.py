"""Report regressions for exact metrics and selected algorithm subsets."""

import unittest

import algorithm_study_report as report_module


def record(algorithm, solved=True, time=0.1, **overrides):
    exact = algorithm in report_module.EXACT_ALGORITHMS
    metrics = {
        "solution_valid": solved,
        "ga_solution_valid": None if exact else solved,
        "fallback_used": False,
        "execution_time_seconds": time,
        "genetic_fitness_evaluations": None if exact else 160,
        "ga_satisfied_runs_percent": None if exact else 100.0 if solved else 50.0,
        "final_satisfied_runs_percent": 100.0 if solved else None if exact else 50.0,
        "backtracking_count": None if algorithm in ("cp_sat", "roundingsat") else 0,
        "search_branches": 8 if algorithm in ("constraint_search", "cp_sat") else None,
        "cp_sat_conflicts": 2 if algorithm == "cp_sat" else None,
        "solver_status": "OPTIMAL" if algorithm == "cp_sat" else "SOLVED" if exact else None,
        "white_cells_solved": 9 if solved else 0,
        "white_cells_total": 9,
        "roundingsat_decisions": 11 if algorithm == "roundingsat" else None,
        "roundingsat_conflicts": 3 if algorithm == "roundingsat" else None,
        "roundingsat_propagations": 120 if algorithm == "roundingsat" else None,
        "native_solver_time_seconds": 0.02 if algorithm == "roundingsat" else None,
        "opb_variables": 81 if algorithm == "roundingsat" else None,
        "opb_constraints": 69 if algorithm == "roundingsat" else None,
    }
    metrics.update(overrides)
    return {"size": "4x4", "seed": 42, "algorithm": algorithm,
            "status": "completed", "result": {"metrics": metrics}}


class StudyReportTests(unittest.TestCase):
    def test_exact_metrics_remain_not_applicable_and_failures_are_retained(self):
        report = {"settings": {"algorithms": ["cp_sat"]}, "records": [
            record("cp_sat", time=0.1),
            record("cp_sat", solved=False, time=0.3, solver_status="UNKNOWN", search_branches=4),
            {"size": "4x4", "seed": 44, "algorithm": "cp_sat", "status": "timeout"},
        ]}
        row, = report_module.summarize(report)
        self.assertEqual((row["trials"], row["completed"], row["solved"], row["timeouts"]), (3, 2, 1, 1))
        self.assertAlmostEqual(row["mean_time_seconds"], 0.2)
        self.assertIsNone(row["ga_solved"])
        self.assertIsNone(row["fallback_solved"])
        self.assertIsNone(row["mean_evaluations"])
        self.assertIsNone(row["total_backtracks"])
        self.assertIsNone(row["mean_backtracks"])
        self.assertEqual(row["total_branches"], 12)
        self.assertEqual(row["total_cp_sat_conflicts"], 4)

    def test_constraint_search_backtracks_and_branches_are_distinct(self):
        report = {"settings": {"algorithms": ["constraint_search"]}, "records": [
            record("constraint_search", backtracking_count=3, search_branches=8),
        ]}
        row, = report_module.summarize(report)
        self.assertEqual(row["total_backtracks"], 3)
        self.assertEqual(row["total_branches"], 8)
        self.assertIsNone(row["total_cp_sat_conflicts"])
        self.assertIsNone(row["ga_solved"])

    def test_historical_report_keeps_four_algorithm_selection(self):
        report = {"records": [record("basic", solved=False, time=1.0)]}
        summary = report_module.summarize(report)
        self.assertEqual([row["algorithm"] for row in summary], list(report_module.GA_ALGORITHMS))
        self.assertEqual(summary[0]["solved"], 0)
        self.assertEqual(summary[0]["mean_time_seconds"], 1.0)
        self.assertEqual(summary[0]["ga_solved"], 0)

    def test_historical_exact_report_keeps_six_algorithm_selection(self):
        report = {"records": [record("cp_sat")]}
        summary = report_module.summarize(report)
        self.assertEqual([row["algorithm"] for row in summary], list(report_module.DEFAULT_ALGORITHMS))
        self.assertNotIn("roundingsat", [row["algorithm"] for row in summary])

    def test_selected_subset_renders_without_hybrid_or_empty_ga_table(self):
        report = {"settings": {"algorithms": ["cp_sat"], "sizes": [[4, 4]], "seeds": [42]},
                  "records": [record("cp_sat")]}
        text = report_module.render_markdown(report)
        self.assertIn("Recorded trials: 1 of 1 planned", text)
        self.assertIn("| Grid | CP-SAT |", text)
        self.assertNotIn("## Per-grid best GA fitness", text)
        self.assertIn("| CP-SAT | 1 / 1 | N/A | N/A |", text)
        self.assertIn("OPTIMAL", text)
        self.assertIn("not directly interchangeable units of effort", text)

    def test_six_algorithm_report_has_all_columns_and_exact_diagnostics(self):
        report = {"settings": {"algorithms": list(report_module.DEFAULT_ALGORITHMS),
                               "sizes": [[4, 4]], "seeds": [42]},
                  "records": [record(name) for name in report_module.DEFAULT_ALGORITHMS]}
        text = report_module.render_markdown(report)
        self.assertIn("six-algorithm evaluation", text)
        self.assertIn("Recorded trials: 6 of 6 planned", text)
        self.assertIn("| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | "
                      "Our hybrid algorithm | Constraint Search | CP-SAT |", text)
        self.assertIn("## Standalone exact-solver diagnostics", text)
        self.assertIn("| 4x4 | 42 | Constraint Search | completed | SOLVED |", text)
        self.assertIn("| 4x4 | 42 | CP-SAT | completed | OPTIMAL |", text)

    def test_roundingsat_native_counters_and_internal_timeouts_are_separate(self):
        timed_out = record("roundingsat", solved=False, time=1.0, solver_status="UNKNOWN",
                           roundingsat_decisions=5, roundingsat_conflicts=0,
                           roundingsat_propagations=80, native_solver_time_seconds=0.9)
        timed_out["result"]["solver_diagnostics"] = {"timed_out": True, "native_status": "UNKNOWN"}
        report = {"settings": {"algorithms": ["ours", "roundingsat"]}, "records": [
            record("ours"), record("roundingsat", time=0.1), timed_out,
            {"size": "4x4", "seed": 44, "algorithm": "roundingsat", "status": "timeout"},
        ]}
        ours, native = report_module.summarize(report)
        self.assertEqual((native["trials"], native["completed"], native["solved"]), (3, 2, 1))
        self.assertEqual((native["timeouts"], native["native_timeouts"]), (1, 1))
        self.assertAlmostEqual(native["mean_time_seconds"], 0.55)
        self.assertAlmostEqual(native["mean_native_solver_time_seconds"], 0.46)
        self.assertEqual(native["total_roundingsat_decisions"], 16)
        self.assertEqual(native["total_roundingsat_conflicts"], 3)
        self.assertEqual(native["total_roundingsat_propagations"], 200)
        for key in ("ga_solved", "fallback_solved", "mean_evaluations", "total_backtracks",
                    "mean_backtracks", "total_branches", "total_cp_sat_conflicts"):
            self.assertIsNone(native[key], key)
        for key in ("total_roundingsat_decisions", "total_roundingsat_conflicts",
                    "total_roundingsat_propagations", "mean_native_solver_time_seconds", "native_timeouts"):
            self.assertIsNone(ours[key], key)

    def test_roundingsat_subset_renders_native_metrics_and_binary_provenance(self):
        native = record("roundingsat")
        native["wall_time_seconds"] = 0.15
        native["result"]["solver_diagnostics"] = {"native_status": "SATISFIABLE", "timed_out": False}
        ours = record("ours")
        ours["wall_time_seconds"] = 0.12
        report = {"settings": {"algorithms": ["ours", "roundingsat"], "sizes": [[4, 4]], "seeds": [42]},
                  "environment": {"roundingsat": {"version": "RoundingSat 2", "commit": "abc123",
                                                   "binary_sha256": "hash123", "lp_enabled": True,
                                                   "platform": "Windows x64 static"}},
                  "records": [ours, native]}
        text = report_module.render_markdown(report)
        self.assertIn("two-algorithm evaluation", text)
        self.assertIn("Recorded trials: 2 of 2 planned", text)
        self.assertIn("| Grid | Our hybrid algorithm | RoundingSat |", text)
        self.assertIn("| RoundingSat | 1 / 1 | N/A | N/A |", text)
        self.assertNotIn("## Standalone exact-solver diagnostics", text)
        self.assertNotIn("| CP-SAT |", text)
        self.assertNotIn("| CP-SAT conflicts |", text)
        self.assertIn("## RoundingSat native diagnostics", text)
        self.assertIn("## Per-grid outer process wall time", text)
        self.assertIn("| 4x4 | 0.120000 | 0.150000 |", text)
        self.assertIn("Mean native reported time (s)", text)
        self.assertIn("not a precise CPU measurement", text)
        self.assertIn("5-second outer cleanup guard", text)
        self.assertIn("| 4x4 | 42 | completed | SOLVED | SATISFIABLE | 0.100000 | 0.020000 | "
                      "0.150000 | 11 | 3 | 120 | 81 | 69 | No | Yes |", text)
        self.assertIn("binary startup cost is included", text)
        self.assertIn("Native decisions and conflicts are not hybrid backtracks", text)
        self.assertIn("rather than a supplied random seed", text)
        self.assertIn("Binary SHA-256: `hash123`", text)
        self.assertIn("Source commit: `abc123`", text)

    def test_missing_roundingsat_counters_are_not_reported_as_zero(self):
        native = record("roundingsat", roundingsat_decisions=None, roundingsat_conflicts=None,
                        roundingsat_propagations=None, native_solver_time_seconds=None)
        report = {"settings": {"algorithms": ["roundingsat"]}, "records": [native]}
        row, = report_module.summarize(report)
        for key in ("total_roundingsat_decisions", "total_roundingsat_conflicts",
                    "total_roundingsat_propagations", "mean_native_solver_time_seconds"):
            self.assertIsNone(row[key], key)

    def test_historical_roundingsat_report_does_not_gain_memetic(self):
        summary = report_module.summarize({"records": [record("roundingsat")]})
        self.assertEqual([row["algorithm"] for row in summary],
                         list(report_module.GA_ALGORITHMS + report_module.EXACT_ALGORITHMS))

    def test_memetic_report_pairs_with_hybrid_and_shows_local_search(self):
        ours = record("ours", time=10.0, ga_solution_valid=False, fallback_used=True,
                      generations_evaluated=1500)
        memetic = record("memetic", time=2.5, generations_evaluated=20, memetic_stop_reason="solved_by_local_search",
                         memetic_restarts=0, local_search_calls=40, local_search_steps=300,
                         local_search_neighbours=9000, local_search_improving_moves=120,
                         local_search_sideways_moves=30, local_search_fitness_reduction=400,
                         local_search_time_seconds=2.0, best_ga_fitness=0)
        report = {"settings": {"algorithms": ["ours", "memetic"], "sizes": [[4, 4]], "seeds": [42]},
                  "records": [ours, memetic]}
        ours_row, memetic_row = report_module.summarize(report)
        self.assertEqual((memetic_row["ga_solved"], memetic_row["fallback_solved"]), (1, 0))
        self.assertEqual((ours_row["ga_solved"], ours_row["fallback_solved"]), (0, 1))
        text = report_module.render_markdown(report)
        self.assertIn("two-algorithm evaluation", text)
        self.assertIn("| Memetic algorithm | Same propagated domains", text)
        self.assertIn("## Memetic algorithm versus our hybrid", text)
        self.assertIn("| 4x4 | 10.0000 | GA 0, fallback 1 of 1 | 2.5000 | 1/1 | 20.0 | 4.0x |", text)
        self.assertIn("Grids fully solved by both: 1; memetic mean time lower on 1 of them.", text)
        self.assertIn("## Memetic local-search diagnostics", text)
        self.assertIn("| 4x4 | 42 | completed | solved_by_local_search | 2.5000 | 2.0000 | 20 | 0 | 40 | "
                      "300 | 9,000 | 120 | 30 | 400 | 0 | Yes |", text)
        self.assertIn("| Grid | Our hybrid algorithm | Memetic algorithm |", text)
        self.assertIn("The memetic algorithm solved 1 of 1 attempted trials with no exact fallback", text)

    def test_unknown_or_duplicate_algorithm_selection_is_rejected(self):
        for selected in (["unknown"], ["cp_sat", "cp_sat"]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                report_module.summarize({"settings": {"algorithms": selected}})


if __name__ == "__main__":
    unittest.main()
