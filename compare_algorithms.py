"""Run paired Kakuro algorithm comparisons on identical full-board puzzles."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import generate_and_solve as kakuro
from benchmark_kakuro import SIZES, independent_validation
from kakuro_generator import generate_rectangular_puzzle
from kakuro_variants import baseline_search
from kakuro_memetic import memetic_search
from kakuro_exact import constraint_search, cp_sat_search, ensure_cp_sat_available
from kakuro_roundingsat import roundingsat_search, ensure_roundingsat_available


PROJECT = Path(__file__).resolve().parent
GA_ALGORITHMS = ("basic", "domain_filtering", "dynamic_mutation", "ours")
MEMETIC_ALGORITHMS = ("memetic",)
# Population-based searches that report GA-phase quality and evaluations.
EVOLUTIONARY_ALGORITHMS = GA_ALGORITHMS + MEMETIC_ALGORITHMS
EXACT_ALGORITHMS = ("constraint_search", "cp_sat", "roundingsat")
ALGORITHMS = GA_ALGORITHMS + MEMETIC_ALGORITHMS + EXACT_ALGORITHMS
# Algorithms that stop cooperatively at the budget and get an outer cleanup grace.
GRACE_ALGORITHMS = ("memetic", "roundingsat")
DEFAULT_ALGORITHMS = GA_ALGORITHMS + ("constraint_search", "cp_sat")


def roundingsat_environment():
    """Identify the actual executable; never attach pinned provenance to a different binary."""
    binary = ensure_roundingsat_available().resolve()
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    manifest_path = PROJECT / "tools" / "roundingsat" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if manifest.get("binary_sha256") == digest:
        metadata = dict(manifest)
    else:
        default_binary = PROJECT / "tools" / "roundingsat" / "roundingsat.exe"
        if binary == default_binary.resolve():
            raise ValueError("RoundingSat binary does not match its pinned manifest; restore the verified executable")
        metadata = {"version": "custom binary; see per-trial banner", "source_url": None}
    metadata.update(binary_path=str(binary), binary_sha256=digest, lp_enabled=True,
                    seed_applied=False)
    return metadata


def candidate_quality(candidate, whites, runs):
    """Score exact run constraints, without comparing to a nonunique witness."""
    if candidate is None:
        return {"fitness": None, "satisfied_runs": None, "satisfied_runs_percent": None,
                "valid": False}
    if set(candidate) != set(whites) or any(
        type(value) is not int or not 1 <= value <= 9 for value in candidate.values()
    ):
        raise ValueError("candidate does not assign a legal digit to every white cell")
    score = satisfied = 0
    for run in runs:
        values = [candidate[cell] for cell in run["cells"]]
        error = abs(sum(values) - run["sum"])
        duplicates = len(values) - len(set(values))
        score += error + 9 * duplicates
        satisfied += error == 0 and duplicates == 0
    return {"fitness": score, "satisfied_runs": satisfied,
            "satisfied_runs_percent": 100.0 * satisfied / len(runs),
            "valid": satisfied == len(runs)}


def filled_grid(grid, candidate):
    if candidate is None:
        return None
    return [[candidate[(r, c)] if cell is None else cell for c, cell in enumerate(row)]
            for r, row in enumerate(grid)]


def solve_exact_case(grid, whites, runs, algorithm, seed, time_limit, artifact_dir=None):
    """Run a standalone exact solver; GA-specific measurements do not apply."""
    search = {"constraint_search": constraint_search, "cp_sat": cp_sat_search,
              "roundingsat": roundingsat_search}[algorithm]
    options = {"seed": seed, "time_limit": time_limit}
    if algorithm == "roundingsat":
        options["artifact_dir"] = artifact_dir
    candidate, diagnostics = search(whites, runs, **options)
    quality = candidate_quality(candidate, whites, runs)
    status = diagnostics["status"]
    if status == "MODEL_INVALID":
        raise ValueError("CP-SAT rejected the generated constraint model")
    if quality["valid"] != (status in ("SOLVED", "OPTIMAL", "FEASIBLE")):
        raise ValueError("exact solver status and returned assignment disagree")
    metrics = {
        "execution_time_seconds": round(diagnostics["execution_time_seconds"], 6),
        "preprocessing_time_seconds": round(diagnostics["preprocessing_time_seconds"], 6),
        "model_build_time_seconds": round(diagnostics["model_build_time_seconds"], 6),
        "search_time_seconds": round(diagnostics["search_time_seconds"], 6),
        "ga_time_seconds": None, "fallback_time_seconds": 0.0,
        "genetic_fitness_evaluations": None, "generations_evaluated": None,
        "backtracking_count": diagnostics["backtracking_count"],
        "search_branches": diagnostics["branches"],
        "search_nodes": diagnostics["nodes_visited"],
        "cp_sat_conflicts": diagnostics["conflicts"] if algorithm == "cp_sat" else None,
        "roundingsat_decisions": diagnostics.get("native_decisions") if algorithm == "roundingsat" else None,
        "roundingsat_conflicts": diagnostics.get("native_conflicts") if algorithm == "roundingsat" else None,
        "roundingsat_propagations": diagnostics.get("native_propagations") if algorithm == "roundingsat" else None,
        "native_solver_time_seconds": diagnostics.get("native_time_seconds") if algorithm == "roundingsat" else None,
        "opb_variables": diagnostics.get("opb_variables"),
        "opb_constraints": diagnostics.get("opb_constraints"),
        "solver_status": status,
        "solution_valid": quality["valid"], "ga_solution_valid": None,
        "fallback_used": False, "best_ga_fitness": None,
        "final_fitness": quality["fitness"], "ga_satisfied_runs_percent": None,
        "final_satisfied_runs_percent": quality["satisfied_runs_percent"],
        "white_cells_solved": len(whites) if quality["valid"] else 0,
        "white_cells_total": len(whites), "run_count": len(runs),
        "domain_reduction_percent": diagnostics["domain_reduction_percent"],
        "solution_validity_rate_percent": 100.0 if quality["valid"] else 0.0,
    }
    return {
        "algorithm": algorithm, "seed": seed,
        "status": "solved" if quality["valid"] else status.lower(),
        "metrics": metrics, "ga_diagnostics": None, "solver_diagnostics": diagnostics,
        "solved_grid": filled_grid(grid, candidate) if quality["valid"] else None,
        "ga_best_grid": None, "best_candidate_grid": filled_grid(grid, candidate),
    }


def solve_case(puzzle, algorithm, seed=42, population_size=160, generations=1500,
               time_limit=120, artifact_dir=None):
    if algorithm not in ALGORITHMS:
        raise ValueError("unknown algorithm")
    grid, whites, runs = kakuro.parse_puzzle(puzzle)
    if algorithm in EXACT_ALGORITHMS:
        if algorithm == "cp_sat":
            ensure_cp_sat_available()
        elif algorithm == "roundingsat":
            ensure_roundingsat_available()
        return solve_exact_case(grid, whites, runs, algorithm, seed, time_limit, artifact_dir)
    start = time.perf_counter()
    if algorithm in ("domain_filtering", "ours", "memetic"):
        domains = kakuro.propagate(whites, runs)
    else:
        domains = {cell: set(range(1, 10)) for cell in whites}
    after_preprocessing = time.perf_counter()
    if algorithm == "ours":
        diagnostics = {}
        ga_solution, _ = kakuro.genetic_search(
            whites, [run for run in runs if run["direction"] == "across"],
            [run for run in runs if run["direction"] == "down"], domains, seed,
            population_size=population_size, generations=generations,
            diagnostics=diagnostics,
        )
        ga_candidate = diagnostics.pop("best_candidate")
    elif algorithm == "memetic":
        # Same representation and operators as "ours", plus local search and no
        # exact fallback. It stops itself at the remaining solving budget.
        ga_solution, diagnostics = memetic_search(
            whites, [run for run in runs if run["direction"] == "across"],
            [run for run in runs if run["direction"] == "down"], domains, seed,
            population_size=population_size, generations=generations,
            time_limit=max(0.0, time_limit - (after_preprocessing - start)),
        )
        ga_candidate = diagnostics.pop("best_candidate")
    else:
        ga_candidate, diagnostics = baseline_search(
            whites, runs, domains, seed, population_size=population_size,
            generations=generations, dynamic_mutation=algorithm == "dynamic_mutation",
        )
        ga_solution = ga_candidate
    after_ga = time.perf_counter()
    # Baselines return their best candidate even when it is not a solution.
    fallback_used = algorithm == "ours" and ga_solution is None
    backtracks = 0
    final_candidate = ga_candidate
    if fallback_used:
        final_candidate, backtracks = kakuro.backtracking_search(whites, runs, domains)
    after_fallback = time.perf_counter()
    ga_quality = candidate_quality(ga_candidate, whites, runs)
    final_quality = candidate_quality(final_candidate, whites, runs)
    if diagnostics["best_fitness"] != ga_quality["fitness"]:
        raise ValueError("GA diagnostics do not match the independently recomputed fitness")
    valid = final_quality["valid"]
    metrics = {
        "execution_time_seconds": round(after_fallback - start, 6),
        "preprocessing_time_seconds": round(after_preprocessing - start, 6),
        "ga_time_seconds": round(after_ga - after_preprocessing, 6),
        "fallback_time_seconds": round(after_fallback - after_ga, 6) if fallback_used else 0.0,
        "genetic_fitness_evaluations": diagnostics["evaluations"],
        "generations_evaluated": diagnostics["generations_evaluated"],
        "backtracking_count": backtracks,
        "solution_valid": valid,
        "ga_solution_valid": ga_quality["valid"],
        "fallback_used": fallback_used,
        "best_ga_fitness": ga_quality["fitness"],
        "final_fitness": final_quality["fitness"],
        "ga_satisfied_runs_percent": ga_quality["satisfied_runs_percent"],
        "final_satisfied_runs_percent": final_quality["satisfied_runs_percent"],
        "white_cells_solved": len(whites) if valid else 0,
        "white_cells_total": len(whites),
        "run_count": len(runs),
        "domain_reduction_percent": 100.0 * (1 - sum(map(len, domains.values())) / (9 * len(whites))),
        "solution_validity_rate_percent": 100.0 if valid else 0.0,
        "search_time_seconds": None, "search_branches": None, "search_nodes": None,
        "cp_sat_conflicts": None,
        "solver_status": "SOLVED" if valid else "BUDGET_EXHAUSTED",
    }
    if algorithm == "memetic":
        metrics.update({
            "memetic_stop_reason": diagnostics["stop_reason"],
            "memetic_restarts": diagnostics["restarts"],
            "local_search_calls": diagnostics["local_search_calls"],
            "local_search_steps": diagnostics["local_search_steps"],
            "local_search_neighbours": diagnostics["local_search_neighbours"],
            "local_search_improving_moves": diagnostics["local_search_improving_moves"],
            "local_search_sideways_moves": diagnostics["local_search_sideways_moves"],
            "local_search_fitness_reduction": diagnostics["local_search_fitness_reduction"],
            "local_search_time_seconds": round(diagnostics["local_search_time_seconds"], 6),
        })
    return {
        "algorithm": algorithm, "seed": seed,
        "status": "solved" if valid else "budget_exhausted",
        "metrics": metrics, "ga_diagnostics": diagnostics,
        "solved_grid": filled_grid(grid, final_candidate) if valid else None,
        "ga_best_grid": filled_grid(grid, ga_candidate),
        "best_candidate_grid": filled_grid(grid, final_candidate),
    }


def verify_result(puzzle, result):
    """Check both search outcomes and measurements without treating N/A as zero."""
    _, whites, runs = kakuro.parse_puzzle(puzzle)
    metrics = result["metrics"]
    if independent_validation(puzzle, result) != metrics["solution_valid"]:
        raise ValueError("final solution validity mismatch")
    for grid_key, prefix in (("ga_best_grid", "ga"), ("best_candidate_grid", "final")):
        candidate_grid = result[grid_key]
        if prefix == "ga" and result["algorithm"] in EXACT_ALGORITHMS:
            if candidate_grid is not None or result.get("ga_diagnostics") is not None or any(
                metrics[key] is not None for key in (
                    "genetic_fitness_evaluations", "generations_evaluated", "ga_solution_valid",
                    "best_ga_fitness", "ga_satisfied_runs_percent", "ga_time_seconds")
            ):
                raise ValueError("GA metrics must be N/A for an exact solver")
            continue
        candidate = None if candidate_grid is None else {
            cell: candidate_grid[cell[0]][cell[1]] for cell in whites
        }
        quality = candidate_quality(candidate, whites, runs)
        score_key = "best_ga_fitness" if prefix == "ga" else "final_fitness"
        if quality["fitness"] != metrics[score_key]:
            raise ValueError(f"{prefix} fitness mismatch")
        if quality["satisfied_runs_percent"] != metrics[prefix + "_satisfied_runs_percent"]:
            raise ValueError(f"{prefix} satisfied-run percentage mismatch")
        valid_key = "ga_solution_valid" if prefix == "ga" else "solution_valid"
        if quality["valid"] != metrics[valid_key]:
            raise ValueError(f"{prefix} validity mismatch")
    expected_solved = len(whites) if metrics["solution_valid"] else 0
    if metrics["white_cells_total"] != len(whites) or metrics["white_cells_solved"] != expected_solved:
        raise ValueError("solved cell count mismatch")
    if result["algorithm"] in EXACT_ALGORITHMS:
        if metrics["fallback_used"]:
            raise ValueError("standalone exact search is not a GA fallback")
        if metrics["solution_valid"] != (metrics["solver_status"] in ("SOLVED", "OPTIMAL", "FEASIBLE")):
            raise ValueError("solver status and final validity disagree")
        if result["algorithm"] == "cp_sat" and metrics["backtracking_count"] is not None:
            raise ValueError("CP-SAT conflicts must not be labeled as backtracks")
        if result["algorithm"] == "roundingsat" and any(
            metrics[key] is not None for key in ("backtracking_count", "search_branches", "search_nodes", "cp_sat_conflicts")
        ):
            raise ValueError("RoundingSat native decisions/conflicts need separate counter fields")
    return True


def run_trial(puzzle, input_path, output_path, algorithm, seed, args):
    rows, columns = len(puzzle["grid"]), len(puzzle["grid"][0])
    record = {
        "size": f"{rows}x{columns}", "seed": seed, "algorithm": algorithm,
        "puzzle_file": str(input_path), "result_file": str(output_path),
        "puzzle_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "status": "pending",
    }
    # A repeated run must not leave an old solution next to a new timeout.
    if output_path.exists():
        output_path.unlink()
    command = [sys.executable, "-E", "-s", str(Path(__file__).resolve()), "--worker",
               "--input", str(input_path), "--output", str(output_path),
               "--algorithm", algorithm, "--seed", str(seed),
               "--population-size", str(args.population_size), "--generations", str(args.generations),
               "--timeout", str(args.timeout)]
    start = time.perf_counter()
    process_timeout = args.timeout + 5 if algorithm in GRACE_ALGORITHMS else args.timeout
    record["process_timeout_seconds"] = process_timeout
    try:
        process = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True,
                                 timeout=process_timeout)
    except subprocess.TimeoutExpired:
        record.update(status="timeout", wall_time_seconds=time.perf_counter() - start,
                      error=f"Exceeded {process_timeout:g}-second outer-process wall-clock limit")
        return record
    record["wall_time_seconds"] = time.perf_counter() - start
    if process.returncode != 0:
        record.update(status="error", error=process.stderr.strip())
        return record
    try:
        result = json.loads(output_path.read_text(encoding="utf-8"))
        verify_result(puzzle, result)
        if result["algorithm"] != algorithm or result["seed"] != seed:
            raise ValueError("result algorithm/seed mismatch")
        record.update(status="completed", result=result)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        record.update(status="error", error=f"Output verification failed: {error}")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--population-size", type=int, default=160)
    parser.add_argument("--generations", type=int, default=1500)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output-dir", type=Path, default=Path("algorithm_comparison_six"))
    parser.add_argument("--algorithms", nargs="+", choices=ALGORITHMS, default=list(DEFAULT_ALGORITHMS))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--input", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--algorithm", choices=ALGORITHMS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.trials < 1 or args.population_size < 1 or args.generations < 0 or args.timeout <= 0:
        parser.error("trials, population, timeout must be positive; generations nonnegative")
    if len(args.algorithms) != len(set(args.algorithms)):
        parser.error("algorithm selections must not contain duplicates")
    if args.worker:
        if args.input is None or args.output is None or args.algorithm is None:
            parser.error("worker requires input, output, and algorithm")
        if args.input.resolve() == args.output.resolve():
            parser.error("input and output must differ")
        puzzle = json.loads(args.input.read_text(encoding="utf-8-sig"))
        artifact_dir = args.output.parent / "roundingsat_artifacts" if args.algorithm == "roundingsat" else None
        result = solve_case(puzzle, args.algorithm, args.seed, args.population_size, args.generations,
                            time_limit=args.timeout, artifact_dir=artifact_dir)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return

    from algorithm_study_report import render_markdown, summarize

    if "cp_sat" in args.algorithms:
        try:
            ensure_cp_sat_available()
        except ImportError as error:
            parser.error(str(error))
    native_environment = None
    if "roundingsat" in args.algorithms:
        try:
            native_environment = roundingsat_environment()
        except (OSError, ValueError, RuntimeError) as error:
            parser.error(str(error))

    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "sizes": [list(size) for size in SIZES], "seeds": list(range(args.seed, args.seed + args.trials)),
        "population_size": args.population_size, "generations": args.generations,
        "timeout_seconds": args.timeout, "dimension_convention": "board",
        "algorithms": args.algorithms, "cp_sat_workers": 1 if "cp_sat" in args.algorithms else None,
        "native_cleanup_grace_seconds": 5 if "roundingsat" in args.algorithms else 0,
        "algorithm_order": "rotated by size/trial; sequential fresh processes",
    }
    if "memetic" in args.algorithms:
        settings["memetic_cleanup_grace_seconds"] = 5
    hashes = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()
        for name in ("generate_and_solve.py", "kakuro_variants.py", "kakuro_generator.py",
                     "compare_algorithms.py", "benchmark_kakuro.py", "algorithm_study_report.py",
                     "kakuro_exact.py", "requirements.txt", "requirements-lock.txt",
                     "kakuro_roundingsat.py", "kakuro_memetic.py", "tools/roundingsat/manifest.json")
    }
    report_path = args.output_dir / "study.json"
    if args.resume and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["settings"] != settings or report["source_sha256"] != hashes:
            parser.error("resume requires matching settings and source files")
        if report["environment"].get("roundingsat") != native_environment:
            parser.error("resume requires the same RoundingSat executable and metadata")
    else:
        try:
            ortools_version = version("ortools")
        except PackageNotFoundError:
            ortools_version = None
        report = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "settings": settings,
            "source_sha256": hashes,
            "environment": {"python": sys.version, "platform": platform.platform(),
                            "processor": platform.processor(), "executable": sys.executable,
                            "ortools_version": ortools_version, "roundingsat": native_environment},
            "records": [], "summary": [],
        }
    case_index = 0
    for rows, columns in SIZES:
        for seed in settings["seeds"]:
            case_dir = args.output_dir / f"{rows}x{columns}" / f"seed_{seed}"
            case_dir.mkdir(parents=True, exist_ok=True)
            input_path = case_dir / "puzzle.json"
            source = PROJECT / "benchmark_results" / f"{rows}x{columns}" / f"seed_{seed}" / "puzzle.json"
            puzzle = (json.loads(source.read_text(encoding="utf-8")) if source.exists()
                      else generate_rectangular_puzzle(rows, columns, seed))
            if len(puzzle["grid"]) != rows or any(len(row) != columns for row in puzzle["grid"]):
                parser.error(f"stored puzzle {source} has incorrect full-board dimensions")
            input_path.write_text(json.dumps(puzzle, indent=2) + "\n", encoding="utf-8")
            puzzle_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
            rotation = case_index % len(args.algorithms)
            order = args.algorithms[rotation:] + args.algorithms[:rotation]
            case_index += 1
            for algorithm in order:
                previous = [record for record in report["records"]
                            if (record["size"], record["seed"], record["algorithm"])
                            == (f"{rows}x{columns}", seed, algorithm)]
                if previous and previous[0]["puzzle_sha256"] != puzzle_hash:
                    parser.error("resume puzzle differs from the recorded trial")
                if previous and previous[0]["status"] == "completed":
                    continue
                report["records"] = [record for record in report["records"] if record not in previous]
                print(f"Running {rows}x{columns}, seed {seed}, {algorithm}...", flush=True)
                record = run_trial(puzzle, input_path, case_dir / f"{algorithm}.json", algorithm, seed, args)
                report["records"].append(record)
                report["summary"] = summarize(report)
                report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                (args.output_dir / "study.md").write_text(render_markdown(report), encoding="utf-8")
                metrics = record.get("result", {}).get("metrics", {})
                detail = (f"GA fitness={metrics.get('best_ga_fitness', 'N/A')}"
                          if algorithm in EVOLUTIONARY_ALGORITHMS else
                          f"status={metrics.get('solver_status', 'N/A')}, branches={metrics.get('search_branches', 'N/A')}")
                print(f"  {record['status']}: valid={metrics.get('solution_valid', 'N/A')}, "
                      f"{detail}, "
                      f"time={metrics.get('execution_time_seconds', 'N/A')} s", flush=True)
    print(f"Study saved to {args.output_dir / 'study.md'}", flush=True)
    if any(record["status"] != "completed" for record in report["records"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
