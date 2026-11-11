"""Standalone constraint search and a genuine OR-Tools CP-SAT Kakuro model.

Both solvers receive parsed white cells and runs, never a generator witness.
CP-SAT's conflict/branch counters are native statistics and are deliberately not
reported as the custom constraint search's failed-branch (backtrack) count.

CP-SAT API references:
https://developers.google.com/optimization/cp/cp_solver
https://developers.google.com/optimization/cp/cp_tasks
https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html
"""

import math
import time

from generate_and_solve import _propagate, validate_solution


def _validate_options(whites, seed, time_limit):
    if not whites or len(set(whites)) != len(whites):
        raise ValueError("whites must contain distinct cells and cannot be empty")
    if type(seed) is not int or not 0 <= seed < 2 ** 31:
        raise ValueError("seed must be an integer from 0 through 2**31 - 1")
    if isinstance(time_limit, bool) or not isinstance(time_limit, (int, float)):
        raise ValueError("time_limit must be a finite nonnegative number")
    if not math.isfinite(time_limit) or time_limit < 0:
        raise ValueError("time_limit must be a finite nonnegative number")


def _diagnostics():
    return {
        "status": "UNKNOWN", "branches": 0, "backtracking_count": 0,
        "conflicts": None, "nodes_visited": 0,
        "execution_time_seconds": 0.0, "preprocessing_time_seconds": 0.0,
        "model_build_time_seconds": 0.0, "search_time_seconds": 0.0,
        "domain_reduction_percent": None,
        "cp_sat_status": None, "cp_sat_wall_time_seconds": None,
        "deterministic_time": None, "ortools_version": None,
    }


class _SearchTimedOut(Exception):
    pass


def constraint_search(whites, runs, seed=42, time_limit=120):
    """Solve directly with propagation and minimum-remaining-values decisions.

    Values and tied cells are visited in deterministic order; ``seed`` is kept
    for the common comparison interface and does not randomize this solver.
    A branch is one attempted value assignment. A backtrack is a branch proved
    unsuccessful, not a branch interrupted by the cooperative time limit.
    Deadline checks surround propagation and every decision; the benchmark's
    parent process supplies an additional hard wall-clock limit.
    """
    _validate_options(whites, seed, time_limit)
    stats = _diagnostics()
    started = time.perf_counter()
    deadline = started + time_limit
    preprocessing_finished = None
    solution = None

    def check_time():
        if time.perf_counter() >= deadline:
            raise _SearchTimedOut

    def search(current, already_propagated=False):
        check_time()
        stats["nodes_visited"] += 1
        if not already_propagated:
            try:
                _propagate(runs, current)
            except ValueError:
                check_time()
                return None
            check_time()
        unassigned = [cell for cell in whites if len(current[cell]) > 1]
        if not unassigned:
            candidate = {cell: next(iter(current[cell])) for cell in whites}
            return candidate if validate_solution(candidate, whites, runs) else None
        cell = min(unassigned, key=lambda item: len(current[item]))
        for value in sorted(current[cell]):
            check_time()
            branch = {item: set(values) for item, values in current.items()}
            branch[cell] = {value}
            stats["branches"] += 1
            candidate = search(branch)
            if candidate is not None:
                return candidate
            stats["backtracking_count"] += 1
        return None

    try:
        check_time()
        domains = {cell: set(range(1, 10)) for cell in whites}
        try:
            _propagate(runs, domains)
        except ValueError:
            check_time()
            stats["status"] = "INFEASIBLE"
        else:
            check_time()
            stats["domain_reduction_percent"] = 100.0 * (
                1 - sum(map(len, domains.values())) / (9 * len(whites))
            )
            preprocessing_finished = time.perf_counter()
            solution = search(domains, already_propagated=True)
            stats["status"] = "SOLVED" if solution is not None else "INFEASIBLE"
    except _SearchTimedOut:
        stats["status"] = "UNKNOWN"
    finished = time.perf_counter()
    if preprocessing_finished is None:
        preprocessing_finished = finished
    stats.update(
        execution_time_seconds=finished - started,
        preprocessing_time_seconds=preprocessing_finished - started,
        search_time_seconds=finished - preprocessing_finished,
    )
    return solution, stats


def ensure_cp_sat_available():
    """Load OR-Tools explicitly, allowing imports before benchmark timing."""
    try:
        from ortools.sat.python import cp_model
    except ImportError as error:
        raise ImportError(
            "CP-SAT requires OR-Tools. Install the project dependency with "
            ".venv\\Scripts\\python.exe -I -m pip install -r requirements.txt."
        ) from error
    return cp_model


def cp_sat_search(whites, runs, seed=42, time_limit=120):
    """Model each white cell as an integer 1..9 and enforce every Kakuro run.

    A run contributes a sum equality and an AllDifferent constraint. No custom
    domain propagation, solution hint, objective, or hidden witness is used.
    One search worker and the supplied random seed are set explicitly. The
    reported execution time includes model construction and solve/extraction,
    but excludes loading the library. Native wall time measures solve alone.
    """
    _validate_options(whites, seed, time_limit)
    cp_model = ensure_cp_sat_available()
    import ortools

    stats = _diagnostics()
    stats.update(backtracking_count=None, nodes_visited=None,
                 ortools_version=ortools.__version__)
    started = time.perf_counter()
    model = cp_model.CpModel()
    variables = {cell: model.new_int_var(1, 9, f"cell_{cell[0]}_{cell[1]}") for cell in whites}
    for run in runs:
        run_variables = [variables[cell] for cell in run["cells"]]
        model.add(sum(run_variables) == run["sum"])
        model.add_all_different(run_variables)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.stop_after_first_solution = True
    model_finished = time.perf_counter()
    solver.parameters.max_time_in_seconds = max(0.0, time_limit - (model_finished - started))
    status = solver.solve(model)
    solution = None
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = {cell: int(solver.value(variable)) for cell, variable in variables.items()}
    finished = time.perf_counter()
    if solution is not None and not validate_solution(solution, whites, runs):
        raise RuntimeError("CP-SAT returned an assignment that failed Kakuro validation")
    response = solver.response_proto
    status_name = solver.status_name(status)
    stats.update(
        status=status_name, cp_sat_status=status_name,
        branches=int(solver.num_branches), conflicts=int(solver.num_conflicts),
        execution_time_seconds=finished - started,
        preprocessing_time_seconds=model_finished - started,
        model_build_time_seconds=model_finished - started,
        search_time_seconds=finished - model_finished,
        cp_sat_wall_time_seconds=float(solver.wall_time),
        deterministic_time=float(response.deterministic_time),
    )
    return solution, stats
