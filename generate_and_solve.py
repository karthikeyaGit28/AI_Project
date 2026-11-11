"""Generate demo Kakuro puzzles or solve JSON grids using a hybrid GA/CSP solver."""

import argparse
import json
import random
import time
from functools import lru_cache
from pathlib import Path


DIGIT_SUMS = tuple(
    sum(digit for digit in range(1, 10) if mask & (1 << (digit - 1)))
    for mask in range(1 << 9)
)


def generate_puzzle(size, seed):
    """Create a solvable square demo; uniqueness is not guaranteed."""
    if type(size) is not int or not 2 <= size <= 9:
        raise ValueError("size must be between 2 and 9")
    rng = random.Random(seed)
    digits = list(range(1, 10))
    rows = list(range(9))
    columns = list(range(9))
    rng.shuffle(digits)
    rng.shuffle(rows)
    rng.shuffle(columns)
    witness = [
        [digits[(rows[r] + columns[c]) % 9] for c in range(size)]
        for r in range(size)
    ]
    grid = [["#" for _ in range(size + 1)] for _ in range(size + 1)]
    for c in range(1, size + 1):
        grid[0][c] = {"down": sum(row[c - 1] for row in witness)}
    for r in range(1, size + 1):
        grid[r][0] = {"across": sum(witness[r - 1])}
        for c in range(1, size + 1):
            grid[r][c] = None
    return {"format": "kakuro-grid-v1", "size": size, "seed": seed, "grid": grid}


def parse_puzzle(puzzle):
    if not isinstance(puzzle, dict):
        raise ValueError("puzzle must be a JSON object")
    if puzzle.get("format", "kakuro-grid-v1") != "kakuro-grid-v1":
        raise ValueError("unsupported puzzle format")
    grid = puzzle.get("grid")
    if not isinstance(grid, list) or not grid or not all(
        isinstance(row, list) and row for row in grid
    ):
        raise ValueError("grid must be a nonempty list of nonempty rows")
    height, width = len(grid), len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("grid rows must have equal width")
    whites = []
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell is None:
                whites.append((r, c))
            elif cell == "#":
                continue
            elif not isinstance(cell, dict) or not cell or not set(cell) <= {"across", "down"}:
                raise ValueError(f"invalid cell at ({r}, {c})")
    if not whites:
        raise ValueError("puzzle has no white cells")

    membership = {cell: {"across": 0, "down": 0} for cell in whites}
    runs = []
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if not isinstance(cell, dict):
                continue
            for direction, dr, dc in (("across", 0, 1), ("down", 1, 0)):
                if direction not in cell:
                    continue
                total = cell[direction]
                if type(total) is not int:
                    raise ValueError(f"invalid {direction} clue at ({r}, {c}): expected integer")
                cells = []
                rr, cc = r + dr, c + dc
                while rr < height and cc < width and grid[rr][cc] is None:
                    cells.append((rr, cc))
                    rr += dr
                    cc += dc
                length = len(cells)
                if not 2 <= length <= 9:
                    raise ValueError(f"{direction} clue at ({r}, {c}) must cover 2 to 9 cells")
                minimum = length * (length + 1) // 2
                maximum = length * (19 - length) // 2
                if not minimum <= total <= maximum:
                    raise ValueError(f"impossible {direction} sum at ({r}, {c}) for {length} cells")
                for white in cells:
                    membership[white][direction] += 1
                runs.append({"direction": direction, "sum": total, "cells": cells})
    if any(counts != {"across": 1, "down": 1} for counts in membership.values()):
        raise ValueError("every white cell must belong to exactly one across and one down run")
    return grid, whites, runs


@lru_cache(maxsize=2048)
def _run_model(total, domain_masks):
    """Compact all valid run assignments into at most 512 used-digit states.

    Each state records supported next digits. This avoids storing up to 9!
    permutations per run and allows exact propagation and random sampling.
    """
    order = tuple(sorted(range(len(domain_masks)), key=lambda i: domain_masks[i].bit_count()))
    masks = tuple(domain_masks[i] for i in order)
    length = len(masks)
    moves = {}

    @lru_cache(maxsize=None)
    def feasible(used):
        position = used.bit_count()
        if position == length:
            return DIGIT_SUMS[used] == total
        remaining = length - position
        available = 0
        for mask in masks[position:]:
            available |= mask & ~used
        if available.bit_count() < remaining:
            return False
        digits = [d for d in range(1, 10) if available & (1 << (d - 1))]
        needed = total - DIGIT_SUMS[used]
        if not sum(digits[:remaining]) <= needed <= sum(digits[-remaining:]):
            return False
        options = []
        choices = masks[position] & ~used
        while choices:
            bit = choices & -choices
            choices ^= bit
            if feasible(used | bit):
                options.append(bit)
        moves[used] = tuple(options)
        return bool(options)

    if not feasible(0):
        return None
    supports = [0] * length
    frontier = {0}
    for position in order:
        next_frontier = set()
        for used in frontier:
            for bit in moves[used]:
                supports[position] |= bit
                next_frontier.add(used | bit)
        frontier = next_frontier
    return order, tuple(supports), moves


def _model_for(run, domains):
    masks = tuple(sum(1 << (value - 1) for value in domains[cell]) for cell in run["cells"])
    return _run_model(run["sum"], masks)


def run_combinations(run, domains):
    """Return explicit assignments for callers that need them (potentially 9!).

    The solver itself uses the compact model instead of expanding this list.
    """
    model = _model_for(run, domains)
    if model is None:
        return []
    order, _, moves = model
    values = [0] * len(order)
    candidates = []

    def visit(position, used):
        if position == len(order):
            candidates.append(tuple(values))
            return
        for bit in moves[used]:
            values[order[position]] = bit.bit_length()
            visit(position + 1, used | bit)

    visit(0, 0)
    return candidates


def _propagate(runs, domains):
    changed = True
    while changed:
        changed = False
        for run in runs:
            model = _model_for(run, domains)
            if model is None:
                raise ValueError(f"puzzle has no feasible combinations for {run}")
            for cell, mask in zip(run["cells"], model[1]):
                narrowed = {value for value in domains[cell] if mask & (1 << (value - 1))}
                if narrowed != domains[cell]:
                    domains[cell] = narrowed
                    changed = True
    return domains


def propagate(whites, runs):
    return _propagate(runs, {cell: set(range(1, 10)) for cell in whites})


def fitness(individual, down_runs):
    score = 0
    for run in down_runs:
        values = [individual[cell] for cell in run["cells"]]
        score += abs(sum(values) - run["sum"])
        score += 9 * (len(values) - len(set(values)))
    return score


def genetic_search(whites, across_runs, down_runs, domains, seed,
                   population_size=160, generations=1500, diagnostics=None):
    """Search with optional observation of the GA phase, including failed runs.

    Diagnostics do not affect random choices or the existing return pair. The
    best candidate and fitness history cover all evaluated populations, even
    across restarts; candidates with positive fitness are not solved puzzles.
    Mutation-rate bounds are null when no offspring population was produced.
    """
    if type(population_size) is not int or population_size < 1:
        raise ValueError("population_size must be a positive integer")
    if type(generations) is not int or generations < 0:
        raise ValueError("generations must be a nonnegative integer")
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(
            evaluations=0, generations_evaluated=0, best_fitness=None,
            best_candidate=None, fitness_history=[], restarts=0,
            mutation_rate_min=None, mutation_rate_max=None,
        )
    if generations == 0:
        return None, 0
    rng = random.Random(seed)
    models = [_model_for(run, domains) for run in across_runs]
    if any(model is None for model in models):
        return None, 0

    # Genes index each cell's restricted domain, as in the supplied flowchart.
    domain_values = {cell: tuple(sorted(domains[cell])) for cell in whites}
    domain_indices = {cell: {value: i for i, value in enumerate(values)}
                      for cell, values in domain_values.items()}

    def sample_run(index):
        run = across_runs[index]
        order, _, moves = models[index]
        genes = {}
        used = 0
        for position in order:
            bit = rng.choice(moves[used])
            used |= bit
            cell = run["cells"][position]
            genes[cell] = domain_indices[cell][bit.bit_length()]
        return genes

    def make_individual():
        genes = {}
        for index in range(len(across_runs)):
            genes.update(sample_run(index))
        return genes

    def decode(genes):
        return {cell: domain_values[cell][index] for cell, index in genes.items()}

    population = [make_individual() for _ in range(population_size)]
    best_score = float("inf")
    stagnant = 0
    evaluations = 0
    for _ in range(generations):
        scored = [(fitness(decode(candidate), down_runs), candidate) for candidate in population]
        evaluations += len(scored)
        scored.sort(key=lambda item: item[0])
        if diagnostics is not None:
            diagnostics["evaluations"] = evaluations
            diagnostics["generations_evaluated"] += 1
            if diagnostics["best_fitness"] is None or scored[0][0] < diagnostics["best_fitness"]:
                diagnostics["best_fitness"] = scored[0][0]
                diagnostics["best_candidate"] = decode(scored[0][1])
            diagnostics["fitness_history"].append(diagnostics["best_fitness"])
        if scored[0][0] == 0:
            return decode(scored[0][1]), evaluations
        if scored[0][0] < best_score:
            best_score = scored[0][0]
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= 100:
            population = [make_individual() for _ in range(population_size)]
            best_score = float("inf")
            stagnant = 0
            if diagnostics is not None:
                diagnostics["restarts"] += 1
            continue

        mutation_rate = min(0.9, 0.25 + 0.65 * stagnant / 100)
        if diagnostics is not None:
            previous_min = diagnostics["mutation_rate_min"]
            previous_max = diagnostics["mutation_rate_max"]
            diagnostics["mutation_rate_min"] = min(previous_min, mutation_rate) if previous_min is not None else mutation_rate
            diagnostics["mutation_rate_max"] = max(previous_max, mutation_rate) if previous_max is not None else mutation_rate
        elite_count = min(8, population_size // 10)
        next_population = [candidate for _, candidate in scored[:elite_count]]
        parents = scored[:max(1, population_size // 3)]
        while len(next_population) < population_size:
            parent_a = rng.choice(parents)[1]
            parent_b = rng.choice(parents)[1]
            child = {}
            for run in across_runs:
                parent = parent_a if rng.random() < 0.5 else parent_b
                child.update({cell: parent[cell] for cell in run["cells"]})
            if rng.random() < mutation_rate:
                # Prefer rows crossing violated down clues. Replacements still
                # satisfy the across clue and every restricted cell domain.
                decoded = decode(child)
                conflicted = {cell for run in down_runs if fitness(decoded, [run])
                              for cell in run["cells"]}
                indices = [i for i, run in enumerate(across_runs)
                           if any(cell in conflicted for cell in run["cells"])]
                if indices:
                    child.update(sample_run(rng.choice(indices)))
            next_population.append(child)
        population = next_population
    return None, evaluations


def backtracking_search(whites, runs, domains):
    """Exact fallback with propagation after every minimum-domain decision."""
    backtracking_count = 0

    def search(current):
        nonlocal backtracking_count
        try:
            _propagate(runs, current)
        except ValueError:
            return None
        unassigned = [cell for cell in whites if len(current[cell]) > 1]
        if not unassigned:
            solution = {cell: next(iter(current[cell])) for cell in whites}
            return solution if validate_solution(solution, whites, runs) else None
        cell = min(unassigned, key=lambda item: len(current[item]))
        for value in sorted(current[cell]):
            branch = {item: set(values) for item, values in current.items()}
            branch[cell] = {value}
            solution = search(branch)
            if solution is not None:
                return solution
            backtracking_count += 1
        return None

    solution = search({cell: set(domains[cell]) for cell in whites})
    return solution, backtracking_count


def validate_solution(solution, whites, runs):
    if not isinstance(solution, dict) or set(solution) != set(whites):
        return False
    if any(type(value) is not int or not 1 <= value <= 9 for value in solution.values()):
        return False
    return all(
        sum(solution[cell] for cell in run["cells"]) == run["sum"]
        and len({solution[cell] for cell in run["cells"]}) == len(run["cells"])
        for run in runs
    )


def format_board(grid, solution):
    board = []
    for r, row in enumerate(grid):
        rendered = []
        for c, cell in enumerate(row):
            if cell is None:
                rendered.append(str(solution[(r, c)]))
            elif cell == "#":
                rendered.append("####")
            else:
                rendered.append(f"{cell.get('across', '-')}\\{cell.get('down', '-')}")
        board.append(rendered)
    return board


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=3, help="generated white-cell grid size (2-9)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--input", type=Path, help="existing puzzle to solve; default: kakuro_puzzle.json")
    parser.add_argument("--output", type=Path, default=Path("kakuro_solution.json"))
    parser.add_argument("--generate", action="store_true", help="generate and save a new puzzle at --input")
    parser.add_argument("--population-size", type=int, default=160)
    parser.add_argument("--generations", type=int, default=1500, help="GA budget; 0 uses exact fallback")
    args = parser.parse_args(argv)
    input_path = args.input if args.input is not None else Path("kakuro_puzzle.json")
    if input_path.resolve() == args.output.resolve():
        parser.error("input and output paths must be different")
    if args.population_size < 1 or args.generations < 0:
        parser.error("population size must be positive and generations must be nonnegative")

    try:
        generate = args.generate or (args.input is None and not input_path.exists())
        if generate:
            puzzle = generate_puzzle(args.size, args.seed)
            input_path.write_text(json.dumps(puzzle, indent=2) + "\n", encoding="utf-8")
        else:
            puzzle = json.loads(input_path.read_text(encoding="utf-8-sig"))
        grid, whites, runs = parse_puzzle(puzzle)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    start = time.perf_counter()
    solution = None
    evaluations = backtracking_count = 0
    algorithm = "constraint propagation"
    error_message = None
    try:
        domains = propagate(whites, runs)
    except ValueError as error:
        error_message = str(error)
    else:
        across_runs = [run for run in runs if run["direction"] == "across"]
        down_runs = [run for run in runs if run["direction"] == "down"]
        algorithm = "genetic algorithm"
        solution, evaluations = genetic_search(
            whites, across_runs, down_runs, domains, args.seed,
            population_size=args.population_size, generations=args.generations,
        )
        if solution is None:
            algorithm = "backtracking fallback"
            solution, backtracking_count = backtracking_search(whites, runs, domains)
        if solution is None:
            error_message = "puzzle has no solution"
    elapsed_seconds = time.perf_counter() - start
    valid = validate_solution(solution, whites, runs)
    result = {
        "algorithm": algorithm,
        "input_file": str(input_path),
        "output_file": str(args.output),
        "board": format_board(grid, solution) if valid else None,
        # Retain the original demo's inner-matrix output, with null for blocks.
        "solution": [[solution.get((r, c)) for c in range(1, len(grid[0]))]
                     for r in range(1, len(grid))] if valid else None,
        "solved_grid": [[solution[(r, c)] if cell is None else cell
                         for c, cell in enumerate(row)]
                        for r, row in enumerate(grid)] if valid else None,
        "metrics": {
            "execution_time_seconds": round(elapsed_seconds, 6),
            "backtracking_count": backtracking_count,
            "genetic_fitness_evaluations": evaluations,
            "solution_valid": valid,
            "white_cells_solved": len(solution) if valid else 0,
            "white_cells_total": len(whites),
            "solution_validity_rate_percent": 100.0 if valid else 0.0,
        },
    }
    if error_message:
        result["error"] = error_message
    try:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    if not valid:
        raise SystemExit("No valid Kakuro solution was produced.")


if __name__ == "__main__":
    main()
