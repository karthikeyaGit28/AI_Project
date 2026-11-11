"""Benchmark generated Kakuro grids in separate, sequential solver processes."""

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from kakuro_generator import generate_rectangular_puzzle


SIZES = [(4, 4), (5, 5), (6, 6), (8, 8), (10, 10), (12, 12),
         (15, 15), (16, 16), (11, 17), (13, 17), (14, 14), (14, 17)]
PROJECT = Path(__file__).resolve().parent


def independent_validation(puzzle, result):
    """Validate every output digit and clue without using the solver's validator."""
    grid = puzzle["grid"]
    solved = result.get("solved_grid")
    if not isinstance(solved, list) or len(solved) != len(grid):
        return False
    coverage = {}
    for r, row in enumerate(grid):
        if not isinstance(solved[r], list) or len(solved[r]) != len(row):
            return False
        for c, cell in enumerate(row):
            value = solved[r][c]
            if cell is None:
                if type(value) is not int or not 1 <= value <= 9:
                    return False
                coverage[(r, c)] = {"across": 0, "down": 0}
            elif cell != value:
                return False
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if not isinstance(cell, dict):
                continue
            for direction, dr, dc in (("across", 0, 1), ("down", 1, 0)):
                if direction not in cell:
                    continue
                values = []
                rr, cc = r + dr, c + dc
                while rr < len(grid) and cc < len(row) and grid[rr][cc] is None:
                    values.append(solved[rr][cc])
                    coverage[(rr, cc)][direction] += 1
                    rr += dr
                    cc += dc
                if not 2 <= len(values) <= 9 or len(values) != len(set(values)):
                    return False
                if sum(values) != cell[direction]:
                    return False
    return bool(coverage) and all(
        counts == {"across": 1, "down": 1} for counts in coverage.values()
    )


def run_trial(rows, columns, seed, args):
    border = 1 if args.size_convention == "inner" else 0
    puzzle = generate_rectangular_puzzle(rows + border, columns + border, seed)
    case_dir = args.output_dir / f"{rows}x{columns}" / f"seed_{seed}"
    case_dir.mkdir(parents=True, exist_ok=True)
    input_path = case_dir / "puzzle.json"
    output_path = case_dir / "solution.json"
    input_path.write_text(json.dumps(puzzle, indent=2) + "\n", encoding="utf-8")
    grid = puzzle["grid"]
    record = {
        "size": f"{rows}x{columns}", "seed": seed,
        "board_rows": len(grid), "board_columns": len(grid[0]),
        "white_cells_total": sum(cell is None for row in grid for cell in row),
        "clue_runs": sum(len(cell) for row in grid for cell in row if isinstance(cell, dict)),
        "puzzle_file": str(input_path), "solution_file": str(output_path),
        "status": "pending", "independently_valid": False,
    }
    command = [sys.executable, str(PROJECT / "generate_and_solve.py"),
               "--input", str(input_path), "--output", str(output_path),
               "--seed", str(seed), "--population-size", str(args.population_size),
               "--generations", str(args.generations)]
    start = time.perf_counter()
    try:
        process = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True,
                                 timeout=args.timeout)
    except subprocess.TimeoutExpired:
        record.update(status="timeout", wall_time_seconds=time.perf_counter() - start,
                      error=f"Exceeded {args.timeout:g}-second wall-clock limit")
        return record
    record["wall_time_seconds"] = time.perf_counter() - start
    record["returncode"] = process.returncode
    if process.returncode != 0:
        record.update(status="error", error=process.stderr.strip())
        return record
    try:
        result = json.loads(output_path.read_text(encoding="utf-8"))
        valid = independent_validation(puzzle, result)
        metrics = result["metrics"]
        consistent = (metrics["solution_valid"] is valid
                      and metrics["white_cells_total"] == record["white_cells_total"]
                      and metrics["white_cells_solved"] == record["white_cells_total"])
        record.update(status="completed" if valid and consistent else "invalid",
                      independently_valid=valid, algorithm=result["algorithm"],
                      metrics=metrics)
    except (OSError, ValueError, KeyError, TypeError) as error:
        record.update(status="error", error=f"Invalid solver output: {error}")
    return record


def summarize(records, sizes):
    rows = []
    for height, width in sizes:
        label = f"{height}x{width}"
        trials = [record for record in records if record["size"] == label]
        if not trials:
            continue
        completed = [record for record in trials if record["status"] == "completed"]
        metrics = [record["metrics"] for record in completed]
        row = {
            "size": label, "trials": len(trials), "completed_trials": len(completed),
            "valid_trials": len(completed),
            "validity_rate_percent": 100.0 * len(completed) / len(trials),
            "ga_successes": sum(record.get("algorithm") == "genetic algorithm" for record in completed),
            "fallback_successes": sum(record.get("algorithm") == "backtracking fallback" for record in completed),
            "timeouts": sum(record["status"] == "timeout" for record in trials),
            "white_cells_mean": statistics.mean(record["white_cells_total"] for record in trials),
            "white_cells_min": min(record["white_cells_total"] for record in trials),
            "white_cells_max": max(record["white_cells_total"] for record in trials),
            "clue_runs_mean": statistics.mean(record["clue_runs"] for record in trials),
        }
        for key in ("execution_time_seconds", "backtracking_count", "genetic_fitness_evaluations",
                    "white_cells_solved"):
            row[key + "_mean"] = statistics.mean(metric[key] for metric in metrics) if metrics else None
        timings = [metric["execution_time_seconds"] for metric in metrics]
        row["execution_time_seconds_min"] = min(timings) if timings else None
        row["execution_time_seconds_max"] = max(timings) if timings else None
        rows.append(row)
    return rows


def markdown_report(report):
    settings = report["settings"]
    lines = ["# Kakuro grid-size comparison", "",
             f"Seeds: {', '.join(map(str, settings['seeds']))}. Population: {settings['population_size']}. "
             f"GA budget: {settings['generations']} generations, then exact backtracking fallback.", "",
             "Dimensions are rows x columns; " + (
                 "they exclude the top and left clue borders and include internal blocks/clues. "
                 "A listed 4x4 puzzle therefore occupies a 5x5 JSON board."
                 if settings["size_convention"] == "inner" else
                 "they include all clue borders and internal blocks. A listed 4x4 puzzle is a 4x4 JSON board."
             ), "",
             "Each seed generates a separate solvable puzzle. Trials run sequentially in fresh Python "
             "processes. Times are solver-reported and exclude generation, parsing, validation, file I/O, "
             "and process startup. Means below cover completed, independently validated trials only; "
             "Valid/Trials shows their coverage. Timeouts and errors are retained in the JSON.", "",
             "| Grid | White cells (mean) | Time (s, mean) | Backtracks (mean) | GA evaluations (mean) | "
             "GA / fallback | Valid / trials | Validity |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    def number(value, digits=2):
        return "N/A" if value is None else f"{value:,.{digits}f}"
    for row in report["summary"]:
        lines.append(
            f"| {row['size']} | {number(row['white_cells_mean'])} | "
            f"{number(row['execution_time_seconds_mean'], 4)} | "
            f"{number(row['backtracking_count_mean'])} | "
            f"{number(row['genetic_fitness_evaluations_mean'])} | "
            f"{row['ga_successes']} / {row['fallback_successes']} | "
            f"{row['valid_trials']} / {row['trials']} | {row['validity_rate_percent']:.1f}% |"
        )
    lines.extend(["", "GA / fallback counts how many trials each method solved. A zero backtracking "
                  "count means no failed branches, and can still occur when fallback was used.", "",
                  "These are measurements of generated examples, not a calibrated difficulty benchmark. "
                  "Layout, run lengths, and clue tightness affect runtime; size alone does not determine "
                  "difficulty. Unique solutions are not guaranteed. Raw trial metrics, white-cell ranges, "
                  "time ranges, environment, and source hashes are recorded in comparison.json.", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42, help="first seed; incremented for each trial")
    parser.add_argument("--size-convention", choices=("inner", "board"), default="board")
    parser.add_argument("--population-size", type=int, default=160)
    parser.add_argument("--generations", type=int, default=1500)
    parser.add_argument("--timeout", type=float, default=120, help="wall-clock seconds per trial")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_results"))
    args = parser.parse_args(argv)
    if args.trials < 1 or args.population_size < 1 or args.generations < 0 or args.timeout <= 0:
        parser.error("trials, population size, and timeout must be positive; generations nonnegative")
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": {"seeds": list(range(args.seed, args.seed + args.trials)),
                     "sizes": SIZES, "size_convention": args.size_convention,
                     "population_size": args.population_size, "generations": args.generations,
                     "timeout_seconds": args.timeout, "processes": "sequential, fresh per trial"},
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "processor": platform.processor(), "executable": sys.executable},
        "source_sha256": {name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()
                          for name in ("generate_and_solve.py", "kakuro_generator.py", "benchmark_kakuro.py")},
        "trials": [], "summary": [],
    }
    for rows, columns in SIZES:
        for seed in report["settings"]["seeds"]:
            print(f"Running {rows}x{columns}, seed {seed}...", flush=True)
            record = run_trial(rows, columns, seed, args)
            report["trials"].append(record)
            report["summary"] = summarize(report["trials"], SIZES)
            (args.output_dir / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            (args.output_dir / "comparison.md").write_text(markdown_report(report), encoding="utf-8")
            metrics = record.get("metrics", {})
            print(f"  {record['status']}: {metrics.get('execution_time_seconds', 'N/A')} s, "
                  f"{record.get('algorithm', record.get('error', ''))}", flush=True)
    print(markdown_report(report), flush=True)
    if any(record["status"] != "completed" for record in report["trials"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
