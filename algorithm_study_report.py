"""Tables and descriptive findings for GA and exact Kakuro solver studies."""

from statistics import mean


GA_ALGORITHMS = ("basic", "domain_filtering", "dynamic_mutation", "ours")
DEFAULT_ALGORITHMS = GA_ALGORITHMS + ("constraint_search", "cp_sat")
EXACT_ALGORITHMS = ("constraint_search", "cp_sat", "roundingsat")
ALGORITHMS = GA_ALGORITHMS + EXACT_ALGORITHMS
ALGORITHM_NAMES = {
    "basic": "Basic GA",
    "domain_filtering": "GA + domain filtering",
    "dynamic_mutation": "GA + dynamic mutation",
    "ours": "Our hybrid algorithm",
    "constraint_search": "Constraint Search",
    "cp_sat": "CP-SAT",
    "roundingsat": "RoundingSat",
}


def _algorithms(report):
    selected = report.get("settings", {}).get("algorithms")
    if selected is not None:
        if len(selected) != len(set(selected)) or any(item not in ALGORITHMS for item in selected):
            raise ValueError("report algorithms must be distinct supported names")
        return tuple(selected)
    # Preserve the original four-algorithm layout for historical reports.
    has_exact = any(record["algorithm"] in EXACT_ALGORITHMS for record in report.get("records", []))
    if any(record["algorithm"] == "roundingsat" for record in report.get("records", [])):
        return ALGORITHMS
    return DEFAULT_ALGORITHMS if has_exact else GA_ALGORITHMS


def _mean(values):
    observed = [value for value in values if value is not None]
    return mean(observed) if observed else None


def _sum_observed(values):
    observed = [value for value in values if value is not None]
    return sum(observed) if observed else None


def _completed(records):
    return [record for record in records
            if record.get("status") == "completed"
            and isinstance(record.get("result", {}).get("metrics"), dict)]


def summarize(report):
    """Aggregate all completed trials, including unsuccessful GA searches.

    Timeouts/errors remain in trial denominators but do not receive invented
    runtimes, fitness values, or search counts. Empty means are returned as None.
    """
    rows = []
    records = report.get("records", [])
    for algorithm in _algorithms(report):
        trials = [record for record in records if record["algorithm"] == algorithm]
        completed = _completed(trials)
        metrics = [record["result"]["metrics"] for record in completed]
        rows.append({
            "algorithm": algorithm,
            "trials": len(trials),
            "completed": len(completed),
            "solved": sum(bool(item.get("solution_valid")) for item in metrics),
            "ga_solved": (sum(bool(item.get("ga_solution_valid")) for item in metrics)
                          if algorithm in GA_ALGORITHMS else None),
            "fallback_solved": sum(bool(item.get("fallback_used")) and bool(item.get("solution_valid"))
                                   for item in metrics) if algorithm in GA_ALGORITHMS else None,
            "mean_time_seconds": _mean(item.get("execution_time_seconds") for item in metrics),
            "mean_evaluations": _mean(item.get("genetic_fitness_evaluations") for item in metrics),
            "mean_ga_run_satisfaction_percent": _mean(item.get("ga_satisfied_runs_percent") for item in metrics),
            "mean_final_run_satisfaction_percent": _mean(item.get("final_satisfied_runs_percent") for item in metrics),
            "total_backtracks": (_sum_observed(item.get("backtracking_count") for item in metrics)
                                 if algorithm in ("cp_sat", "roundingsat") else
                                 sum(item.get("backtracking_count") or 0 for item in metrics)),
            "mean_backtracks": _mean(item.get("backtracking_count") for item in metrics),
            "total_branches": _sum_observed(item.get("search_branches") for item in metrics),
            "total_cp_sat_conflicts": _sum_observed(item.get("cp_sat_conflicts") for item in metrics),
            "total_roundingsat_decisions": _sum_observed(item.get("roundingsat_decisions") for item in metrics),
            "total_roundingsat_conflicts": _sum_observed(item.get("roundingsat_conflicts") for item in metrics),
            "total_roundingsat_propagations": _sum_observed(item.get("roundingsat_propagations") for item in metrics),
            "mean_native_solver_time_seconds": _mean(item.get("native_solver_time_seconds") for item in metrics),
            "native_timeouts": (sum(bool((record.get("result", {}).get("solver_diagnostics") or {})
                                         .get("timed_out")) for record in completed)
                                if algorithm == "roundingsat" else None),
            "timeouts": sum(record.get("status") == "timeout" for record in trials),
            "errors": sum(record.get("status") == "error" for record in trials),
        })
    return rows


def _number(value, digits=2):
    return "N/A" if value is None else f"{value:,.{digits}f}"


def _integer(value):
    return "N/A" if value is None else f"{value:,}"


def _yes(value):
    return "N/A" if value is None else "Yes" if value else "No"


def _size_labels(report):
    sizes = report.get("settings", {}).get("sizes")
    if sizes:
        return [size if isinstance(size, str) else f"{size[0]}x{size[1]}" for size in sizes]
    return list(dict.fromkeys(record["size"] for record in report.get("records", [])))


def _group(report, size, algorithm):
    return [record for record in report.get("records", [])
            if record["size"] == size and record["algorithm"] == algorithm]


def render_markdown(report):
    """Render a self-contained study, suitable for one or multiple seeds."""
    settings = report.get("settings", {})
    population = settings.get("population_size", 160)
    generations = settings.get("generations", 1500)
    seeds = settings.get("seeds", [])
    algorithms = _algorithms(report)
    records = [record for record in report.get("records", []) if record["algorithm"] in algorithms]
    ga_algorithms = [algorithm for algorithm in algorithms if algorithm in GA_ALGORITHMS]
    exact_algorithms = [algorithm for algorithm in algorithms if algorithm in ("constraint_search", "cp_sat")]
    has_roundingsat = "roundingsat" in algorithms
    summary = summarize(report)
    rows_by_algorithm = {row["algorithm"]: row for row in summary}
    planned_trials = len(_size_labels(report)) * len(seeds) * len(algorithms)
    count_name = {2: "two", 4: "four", 6: "six", 7: "seven"}.get(len(algorithms), str(len(algorithms)))
    lines = [
        f"# Kakuro: {count_name}-algorithm evaluation study", "",
        f"Recorded trials: {len(records)} of {planned_trials} planned. "
        f"Puzzle/GA seeds: {', '.join(map(str, seeds)) or 'not recorded'}. "
        f"Population: {population}. GA generation limit: {generations:,}. "
        f"Maximum population fitness evaluations per GA: {population * generations:,}.", "",
        "Grid sizes count the complete board, including clue borders and internal blocks. "
        "For each size and seed, all selected algorithms receive the same puzzle; a puzzle hash "
        "is recorded for checking this pairing. Each trial runs sequentially in a fresh Python "
        "process. The synthetic generator creates solvable instances but does not guarantee uniqueness.", "",
        f"Configured per-trial solving budget: {settings.get('timeout_seconds', 'not recorded')} seconds. "
        "A timeout means the configured limit was reached, not that the puzzle is unsatisfiable. "
        "Completed unsuccessful searches retain their best candidate and measured metrics.", "",
        "## Algorithm definitions", "",
        "| Algorithm | Domains | Search mechanism | Restarts / exact fallback |",
        "|---|---|---|---|",
    ]
    definitions = {
        "basic": "| Basic GA | Digits 1 through 9 for every cell | Uniform cell crossover; fixed 0.25 "
        "probability of mutating one randomly selected cell | Neither |",
        "domain_filtering": "| GA + domain filtering | Iterative clue-based constraint propagation before GA | "
        "Same crossover and fixed mutation as Basic GA | Neither |",
        "dynamic_mutation": "| GA + dynamic mutation | Digits 1 through 9; no domain filtering | Same crossover as "
        "Basic GA; mutation rises from 0.25 toward 0.90 with stagnation | Neither |",
        "ours": "| Our hybrid algorithm | Iterative propagation and domain-indexed genes | Valid across-run "
        "sampling, run-based crossover, conflict-focused mutation with adaptive probability | "
        "Restart after 100 stagnant generations; exact backtracking if GA fails |",
        "constraint_search": "| Constraint Search | Digits 1-9 narrowed by iterative run propagation | Standalone "
        "minimum-remaining-values (MRV) backtracking with propagation after decisions | No GA; "
        "the constraint search runs directly |",
        "cp_sat": "| CP-SAT | One integer variable with domain 1-9 per white cell | OR-Tools CP-SAT; "
        "each run has an exact-sum constraint and AllDifferent | No GA or custom fallback; "
        "one search worker, recorded random seed |",
        "roundingsat": "| RoundingSat | Nine Boolean variables per white cell, one per digit | "
        "Native pseudo-Boolean solver on an OPB feasibility model: exactly one digit per cell, "
        "weighted clue sums, at most one occurrence of each digit per run | No GA or custom fallback; "
        "native process with recorded binary and options |",
    }
    lines.extend(definitions[algorithm] for algorithm in algorithms)
    if any(algorithm in algorithms for algorithm in GA_ALGORITHMS[:3]):
        lines.extend(["", "The three GA baselines share top-third parent selection and at most eight elites "
        "(`min(8, population_size // 10)`). Mutation replaces one selected cell's value with a "
        "different allowed digit when one is available. Filtering and dynamic mutation are "
        "independent additions to Basic GA, not cumulative variants. Adaptive probability is "
        "`min(0.90, 0.25 + 0.65 * stagnant_generations / 100)`."])
    lines.extend(["",
        "## Metric definitions", "",
        "- **Valid solution:** every white cell has a digit 1-9, and every across/down run has "
        "the required sum and no repeated digit. An independent validator checks this.",
        "- **Fitness (lower is better):** sum over all runs of `abs(actual_sum - clue_sum) + "
        "9 * (run_length - distinct_digits)`. Zero is a complete valid solution. Our GA preserves "
        "across constraints, so its down-only search score equals this common all-run score.",
        "- **Satisfied runs (%):** percentage of runs meeting both the exact sum and no-repeat "
        "requirements. This is partial constraint satisfaction, not puzzle validity or cell accuracy.",
        "- **Execution time:** preprocessing/model construction plus the applicable search, "
        "including any hybrid fallback. It excludes puzzle generation, parsing, final output "
        "validation, library import, and Python process startup. For in-process algorithms it also "
        "excludes JSON file I/O. Native RoundingSat process timing is detailed below when selected.",
        "- **Fitness evaluations:** evaluated population members. Auxiliary conflict checks and "
        "constraint-propagation work are not included in this count. This metric is N/A for "
        "exact solvers, which do not use a GA.",
        "- **Backtracks:** failed branches in Python constraint search or the hybrid's exact "
        "fallback. Zero can also occur when exact search succeeds without rejecting a branch. "
        "CP-SAT and RoundingSat do not expose an equivalent count here, so their backtracks are N/A.",
        "- **Search counters:** Python backtracks, attempted cell-value branches, and native "
        "solver decisions, branches, conflicts, and propagations are reported separately when "
        "available. They are diagnostic counts, not directly interchangeable units of effort.",
        "- **Solved white cells:** the complete white-cell count only when the whole solution "
        "validates; an unsolved full candidate is not counted as a partially correct solution.", "",
        "Averages include all completed trials, including unsolved GA runs and native solver "
        "UNKNOWN results with recorded measurements. Outer process timeouts/errors remain "
        "in the attempted-trial denominator but are excluded from numerical means. Missing "
        "measurements are shown as N/A. Means of run satisfaction give each trial equal weight.",
    ])
    if exact_algorithms:
        lines.extend(["", "Exact-solver statuses distinguish a found solution from a proof of "
                      "infeasibility and an inconclusive limit. CP-SAT FEASIBLE/OPTIMAL indicate a "
                      "valid solution, INFEASIBLE indicates proved infeasibility, UNKNOWN indicates "
                      "no conclusion within the limit, and MODEL_INVALID indicates a model error. "
                      "Constraint Search uses SOLVED, INFEASIBLE, or UNKNOWN. This is a feasibility "
                      "model with no optimization objective: CP-SAT OPTIMAL does not establish "
                      "solution uniqueness or human difficulty."])
    if has_roundingsat:
        lines.extend(["", "**RoundingSat timing and statuses:** total execution time includes OPB "
                      "encoding, temporary file I/O, native binary startup, search, and model decoding. "
                      "The binary startup cost is included, making this a conservative comparison "
                      "with the in-process hybrid timer. The native statistic labelled `cpu time` "
                      "is recorded separately. This Windows build uses a coarse, whole-second "
                      "clock() statistic; it is not a precise CPU measurement and is not substituted "
                      "for total wall-clock execution time. Each trial's outer process wall time "
                      "is also reported below. "
                      f"RoundingSat has a {settings.get('native_cleanup_grace_seconds', 5)}-second "
                      "outer cleanup guard beyond the solving budget so that a native time limit "
                      "can be recorded; the hybrid's outer timeout uses the configured budget.", "",
                      "RoundingSat statuses are normalized to SOLVED, INFEASIBLE, or UNKNOWN; "
                      "native SAT/UNSAT statuses are retained in solver diagnostics. UNKNOWN means "
                      "no conclusion within the limit. The OPB model has no optimization objective. "
                      "Finding a model does not establish uniqueness. Native decisions and conflicts "
                      "are not hybrid backtracks, and propagations are not GA fitness evaluations. "
                      "The recorded seed selects the puzzle and GA randomness; RoundingSat uses "
                      "its deterministic native defaults rather than a supplied random seed."])
        native_environment = report.get("environment", {}).get("roundingsat") or {}
        if native_environment:
            lines.extend(["", "### Recorded RoundingSat binary", "",
                          f"- Version: {native_environment.get('version', 'not recorded')}.",
                          f"- Platform: {native_environment.get('platform', 'not recorded')}.",
                          f"- Source commit: `{native_environment.get('commit', 'not recorded')}`.",
                          f"- Binary SHA-256: `{native_environment.get('binary_sha256', 'not recorded')}`.",
                          f"- Native LP enabled: {_yes(native_environment.get('lp_enabled'))}."])
            if native_environment.get("source_url"):
                lines.extend(["", f"Source: [official RoundingSat repository]({native_environment['source_url']})."])
            if native_environment.get("download_url"):
                lines.append(f"Binary: [recorded download]({native_environment['download_url']}).")
    aggregate_columns = ["Algorithm", "Valid / trials", "GA-only valid", "Fallback valid", "Completed",
                         "Mean time (s)", "Mean evaluations", "Mean GA runs satisfied (%)",
                         "Mean final runs satisfied (%)", "Total backtracks"]
    if exact_algorithms:
        aggregate_columns.append("Branches")
    if "cp_sat" in algorithms:
        aggregate_columns.append("CP-SAT conflicts")
    if has_roundingsat:
        aggregate_columns.extend(["RoundingSat decisions", "RoundingSat conflicts",
                                  "RoundingSat propagations", "Mean native reported time (s)",
                                  "Native time limits"])
    aggregate_columns.append("Timeouts / errors")
    lines.extend(["", "## Aggregate results", "",
                  "| " + " | ".join(aggregate_columns) + " |",
                  "|---|" + "---:|" * (len(aggregate_columns) - 1)])
    for row in summary:
        values = [ALGORITHM_NAMES[row["algorithm"]], f"{row['solved']} / {row['trials']}",
                  _integer(row["ga_solved"]), _integer(row["fallback_solved"]), str(row["completed"]),
                  _number(row["mean_time_seconds"], 4), _number(row["mean_evaluations"]),
                  _number(row["mean_ga_run_satisfaction_percent"]),
                  _number(row["mean_final_run_satisfaction_percent"]), _integer(row["total_backtracks"])]
        if exact_algorithms:
            values.append(_integer(row["total_branches"]))
        if "cp_sat" in algorithms:
            values.append(_integer(row["total_cp_sat_conflicts"]))
        if has_roundingsat:
            values.extend([_integer(row["total_roundingsat_decisions"]),
                           _integer(row["total_roundingsat_conflicts"]),
                           _integer(row["total_roundingsat_propagations"]),
                           _number(row["mean_native_solver_time_seconds"], 6),
                           _integer(row["native_timeouts"])])
        values.append(f"{row['timeouts']} / {row['errors']}")
        lines.append("| " + " | ".join(values) + " |")
    lines.extend([
        "", "## Per-grid execution time and validity", "",
        "Each entry is **mean seconds; valid/attempted trials**. With one seed it is the actual "
        "single-run measurement. An unsuccessful GA run's elapsed time is a budget-exhaustion "
        "time, not a time to solve. For exact solvers, the status distinguishes infeasibility "
        "from an inconclusive limit.", "",
        "| Grid | " + " | ".join(ALGORITHM_NAMES[algorithm] for algorithm in algorithms) + " |",
        "|---|" + "---:|" * len(algorithms),
    ])
    for size in _size_labels(report):
        cells = []
        for algorithm in algorithms:
            trials = _group(report, size, algorithm)
            completed = _completed(trials)
            metrics = [record["result"]["metrics"] for record in completed]
            if not trials:
                cells.append("Pending")
                continue
            time_mean = _mean(item.get("execution_time_seconds") for item in metrics)
            solved = sum(bool(item.get("solution_valid")) for item in metrics)
            cells.append(f"{_number(time_mean, 4)}; {solved}/{len(trials)}")
        lines.append(f"| {size} | " + " | ".join(cells) + " |")
    if has_roundingsat:
        lines.extend([
            "", "## Per-grid outer process wall time", "",
            "Each entry is mean elapsed seconds for the complete worker process, including "
            "Python startup, library loading, puzzle parsing, search, validation, and result "
            "serialization. RoundingSat additionally starts its native process. This secondary "
            "measurement compares the full invocation costs of both implementations. Every "
            "recorded wall time is included, including outer timeouts; pair it with the validity "
            "table above before interpreting performance.", "",
            "| Grid | " + " | ".join(ALGORITHM_NAMES[algorithm] for algorithm in algorithms) + " |",
            "|---|" + "---:|" * len(algorithms),
        ])
        for size in _size_labels(report):
            cells = []
            for algorithm in algorithms:
                trials = _group(report, size, algorithm)
                value = _mean(record.get("wall_time_seconds") for record in trials)
                cells.append("Pending" if not trials else _number(value, 6))
            lines.append(f"| {size} | " + " | ".join(cells) + " |")
    if ga_algorithms:
        lines.extend([
            "", "## Per-grid best GA fitness before fallback", "",
            "Lower is better; zero means the GA phase solved the puzzle. These values are the "
            "best candidate encountered within the GA budget, including candidates retained across "
            "restarts. Our fallback cannot improve the values in this table. Multiple seeds are averaged.", "",
            "Exact solvers have no GA phase; they are omitted from this table.", "",
            "| Grid | " + " | ".join(ALGORITHM_NAMES[algorithm] for algorithm in ga_algorithms) + " |",
            "|---|" + "---:|" * len(ga_algorithms),
        ])
        for size in _size_labels(report):
            cells = []
            for algorithm in ga_algorithms:
                trials = _group(report, size, algorithm)
                metrics = [record["result"]["metrics"] for record in _completed(trials)]
                value = _mean(item.get("best_ga_fitness") for item in metrics)
                cells.append("Pending" if not trials else _number(value))
            lines.append(f"| {size} | " + " | ".join(cells) + " |")
    if exact_algorithms:
        lines.extend([
            "", "## Standalone exact-solver diagnostics", "",
            "Times include model/preprocessing and search. CP-SAT conflicts and Python failed "
            "backtracking branches are different diagnostics; neither is substituted for the other. "
            "GA evaluations and generations are N/A for these algorithms.", "",
            "| Grid | Seed | Algorithm | Trial status | Solver status | Total (s) | "
            "Model / preprocess (s) | Search (s) | Branches | Backtracks | CP-SAT conflicts | "
            "Valid | Solved / white cells |",
            "|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|",
        ])
        for record in records:
            if record["algorithm"] not in exact_algorithms:
                continue
            prefix = [record["size"], str(record["seed"]), ALGORITHM_NAMES[record["algorithm"]],
                      record["status"]]
            metrics = record.get("result", {}).get("metrics")
            if record["status"] != "completed" or not metrics:
                values = ["N/A"] * 9
            else:
                values = [
                    str(metrics.get("solver_status") or "N/A"),
                    *[_number(metrics.get(key), 6) for key in
                      ("execution_time_seconds", "preprocessing_time_seconds", "search_time_seconds")],
                    _integer(metrics.get("search_branches")), _integer(metrics.get("backtracking_count")),
                    _integer(metrics.get("cp_sat_conflicts")), _yes(metrics.get("solution_valid")),
                    f"{metrics.get('white_cells_solved', 'N/A')} / {metrics.get('white_cells_total', 'N/A')}",
                ]
            lines.append("| " + " | ".join(prefix + values) + " |")
    if has_roundingsat:
        lines.extend([
            "", "## RoundingSat native diagnostics", "",
            "Total time includes the native process overhead; native reported time is the "
            "solver's coarse clock statistic, labelled cpu time upstream. Outer wall time additionally includes Python "
            "startup, parsing, validation, and result serialization. Native limits are recorded "
            "separately from an outer process timeout. Missing native counters remain N/A.", "",
            "| Grid | Seed | Trial status | Solver status | Native status | Total (s) | "
            "Native reported (s) | Outer wall (s) | Decisions | Conflicts | Propagations | OPB variables | "
            "OPB constraints | Native limit | Valid |",
            "|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ])
        for record in records:
            if record["algorithm"] != "roundingsat":
                continue
            prefix = [record["size"], str(record["seed"]), record["status"]]
            metrics = record.get("result", {}).get("metrics")
            diagnostics = record.get("result", {}).get("solver_diagnostics") or {}
            if record["status"] != "completed" or not metrics:
                values = ["N/A"] * 12
                values[4] = _number(record.get("wall_time_seconds"), 6)
            else:
                values = [str(metrics.get("solver_status") or "N/A"),
                          str(diagnostics.get("native_status") or "N/A"),
                          _number(metrics.get("execution_time_seconds"), 6),
                          _number(metrics.get("native_solver_time_seconds"), 6),
                          _number(record.get("wall_time_seconds"), 6),
                          *[_integer(metrics.get(key)) for key in
                            ("roundingsat_decisions", "roundingsat_conflicts", "roundingsat_propagations",
                             "opb_variables", "opb_constraints")],
                          _yes(diagnostics.get("timed_out")), _yes(metrics.get("solution_valid"))]
            lines.append("| " + " | ".join(prefix + values) + " |")
    lines.extend([
        "", "## Every measured trial", "",
        "All times are seconds. A completed status includes unsuccessful searches. GA fitness "
        "and GA run satisfaction describe the best pre-fallback candidate; final columns describe "
        "the returned candidate or solution.", "",
        "| Grid | Seed | Algorithm | Status | Time | Preprocess | GA time | Fallback time | "
        "Evaluations | Generations | GA fitness | Final fitness | GA valid | Final valid | "
        "Fallback used | Backtracks | GA runs (%) | Final runs (%) | Solved/white cells | Domain reduction (%) |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for record in records:
        prefix = [record["size"], str(record["seed"]),
                  ALGORITHM_NAMES.get(record["algorithm"], record["algorithm"]), record["status"]]
        metrics = record.get("result", {}).get("metrics")
        if record.get("status") != "completed" or not metrics:
            lines.append("| " + " | ".join(prefix + ["N/A"] * 16) + " |")
            continue
        values = [
            *[_number(metrics.get(key), 4) for key in
              ("execution_time_seconds", "preprocessing_time_seconds", "ga_time_seconds", "fallback_time_seconds")],
            _integer(metrics.get("genetic_fitness_evaluations")),
            _integer(metrics.get("generations_evaluated")),
            _integer(metrics.get("best_ga_fitness")),
            _integer(metrics.get("final_fitness")),
            _yes(metrics.get("ga_solution_valid")), _yes(metrics.get("solution_valid")),
            _yes(metrics.get("fallback_used")), _integer(metrics.get("backtracking_count")),
            _number(metrics.get("ga_satisfied_runs_percent")),
            _number(metrics.get("final_satisfied_runs_percent")),
            f"{metrics.get('white_cells_solved', 'N/A')}/{metrics.get('white_cells_total', 'N/A')}",
            _number(metrics.get("domain_reduction_percent")),
        ]
        lines.append("| " + " | ".join(prefix + values) + " |")
    lines.extend(["", "## Findings and interpretation", ""])
    if records:
        outcomes = "; ".join(
            f"{ALGORITHM_NAMES[row['algorithm']]} {row['solved']}/{row['trials']}"
            for row in summary if row["trials"]
        )
        lines.append(f"Observed complete-solution counts: {outcomes}.")
        ours = rows_by_algorithm.get("ours")
        if ours and ours["trials"]:
            lines.extend(["", f"Our GA phase solved {ours['ga_solved']} of {ours['trials']} attempted "
                          f"trials; the exact fallback supplied {ours['fallback_solved']} additional "
                          "valid solutions. These two contributions must be distinguished when "
                          "judging the hybrid's complete-solution rate."])
        exhausted = []
        for algorithm in ga_algorithms:
            completed = _completed([record for record in records if record["algorithm"] == algorithm])
            count = sum(record["result"]["metrics"].get("genetic_fitness_evaluations") == population * generations
                        and not record["result"]["metrics"].get("ga_solution_valid")
                        for record in completed)
            exhausted.append(f"{ALGORITHM_NAMES[algorithm]}: {count}")
        if exhausted:
            lines.extend(["", "Completed trials exhausting the full GA budget without a GA solution: "
                          + "; ".join(exhausted) + "."])
    else:
        lines.append("No trials have been recorded yet; no performance conclusions are available.")
    if any(algorithm in algorithms for algorithm in GA_ALGORITHMS[:3]):
        lines.extend(["", "Domain filtering versus Basic GA isolates the tested preprocessing change; "
                      "dynamic mutation versus Basic GA isolates the tested mutation schedule. Our "
                      "algorithm changes several mechanisms together, so its difference cannot be "
                      "attributed to domain filtering or adaptive mutation alone."])
    if "ours" in algorithms:
        lines.extend(["", "Our hybrid may perform additional exact search after the GA budget. "
                      "Its final validity and total runtime include this work; its pre-fallback "
                      "fitness, GA-only validity, and separately reported fallback time show the "
                      "contribution of each stage."])
    if "constraint_search" in algorithms:
        lines.extend(["", "Constraint Search directly applies propagation and exact backtracking "
                      "without a preceding GA phase."])
    if "cp_sat" in algorithms:
        lines.extend(["", "CP-SAT solves a declarative sum/AllDifferent model with one search "
                      "worker and no supplied solution hints."])
    if has_roundingsat:
        lines.extend(["", "RoundingSat solves the encoded pseudo-Boolean constraints directly, "
                      "without a supplied solution witness or hybrid GA phase. Its native decisions "
                      "and conflicts measure different operations from the hybrid's fitness "
                      "evaluations and failed backtracking branches. This comparison measures "
                      "these complete implementations on the recorded instances; it does not "
                      "isolate a single algorithmic improvement or programming-language effect."])
    if exact_algorithms or has_roundingsat:
        lines.extend(["", "Exact solvers are not subject to the GA-generation limit; the recorded "
                      "time limit applies instead."])
    lines.extend([
        "",
        "Do not infer a speedup from an unsolved algorithm stopping sooner. Compare time to a "
        "valid solution only on paired instances that both algorithms solve. Constraint satisfaction "
        "and residual fitness help describe failed searches, but cannot replace full solution validity.", "",
        "With one seed per size, these results are descriptive observations, not statistical proof "
        "of superiority. Increasing to five seeds supplies repeated observations but still requires "
        "reporting variability and failed trials. Grid size, clue tightness, run structure, and white-cell "
        "count all affect difficulty. These regular generated puzzles are not a calibrated human "
        "difficulty dataset.", "",
        "Solutions are not guaranteed unique. Comparing digits to the generator's hidden witness "
        "would incorrectly label other valid solutions as wrong, so this study reports constraint "
        "validity rather than witness-based cell accuracy. Machine load and Python implementation "
        "also affect wall-clock measurements.", "",
    ])
    return "\n".join(lines)
