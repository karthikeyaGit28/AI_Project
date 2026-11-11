"""Memetic algorithm for Kakuro: the hybrid's GA plus Lamarckian local search.

The genetic part deliberately matches the GA phase of ``genetic_search`` in
``generate_and_solve.py``: propagated cell domains, individuals built from valid
across-run assignments (so every across clue always holds), down-run fitness,
top-third parent selection, at most eight elites, run-based crossover,
conflict-focused mutation with the same adaptive probability, and a restart after
100 stagnant generations. The only added mechanism is local search, so a
comparison with the hybrid isolates "local search" versus "exact fallback".

Local search repeatedly picks a violated down run, then one across run that
crosses it, and replaces that across run's assignment with the best neighbour
(steepest descent, random tie-breaking). Neighbours always satisfy the across
clue and the propagated domains:

* every valid assignment of the run when it has at most ``neighbourhood_limit``
  assignments (an exact best response for that run), otherwise
* every sum-preserving change of two cells (including swaps), plus a few freshly
  sampled valid assignments of the whole run.

Improving moves are always accepted, equal-fitness moves are accepted to cross
plateaus, and the same run is not moved twice in a row. Improved genes are written
back to the individual (Lamarckian learning). There is no exact backtracking
fallback: an unsolved search returns its best candidate only for diagnostics.
"""

import random
import time

from generate_and_solve import _model_for, fitness


DEFAULT_LOCAL_SEARCH_RATE = 0.15
DEFAULT_LOCAL_SEARCH_STEPS = 150
DEFAULT_LOCAL_SEARCH_PATIENCE = 25
DEFAULT_NEIGHBOURHOOD_LIMIT = 128
DEFAULT_RANDOM_NEIGHBOURS = 8


def _penalty(total, length, sum_, distinct):
    return abs(sum_ - total) + 9 * (length - distinct)


class _RunNeighbourhood:
    """Precomputed move generator for one across run under fixed domains."""

    def __init__(self, run, domains, limit):
        self.cells = tuple(run["cells"])
        self.domains = tuple(frozenset(domains[cell]) for cell in self.cells)
        order, _, moves = _model_for(run, domains)
        self.order, self.moves = order, moves
        length = len(self.cells)
        counts = {}

        def completions(used):
            if used in counts:
                return counts[used]
            if used.bit_count() == length:
                result = 1
            else:
                result = sum(completions(used | bit) for bit in moves.get(used, ()))
            counts[used] = result
            return result

        self.assignment_count = completions(0)
        self.assignments = None
        if self.assignment_count <= limit:
            assignments = []
            values = [0] * length

            def visit(position, used):
                if position == length:
                    assignments.append(tuple(values))
                    return
                for bit in moves[used]:
                    values[order[position]] = bit.bit_length()
                    visit(position + 1, used | bit)

            visit(0, 0)
            self.assignments = tuple(assignments)

    def sample(self, rng):
        values = [0] * len(self.cells)
        used = 0
        for position in self.order:
            bit = rng.choice(self.moves[used])
            used |= bit
            values[position] = bit.bit_length()
        return values

    def candidates(self, current, rng, random_neighbours):
        """Yield lists of ``(position, new_value)`` changes; all keep the run valid."""
        if self.assignments is not None:
            for assignment in self.assignments:
                changes = [(i, value) for i, value in enumerate(assignment) if value != current[i]]
                if changes:
                    yield changes
            return
        present = set(current)
        length = len(current)
        for i in range(length):
            for j in range(i + 1, length):
                pair_sum = current[i] + current[j]
                for value in self.domains[i]:
                    other = pair_sum - value
                    if value == current[i] or other not in self.domains[j]:
                        continue
                    if value != current[j] and value in present:
                        continue
                    if other != current[i] and other in present:
                        continue
                    if value == other:
                        continue
                    yield [(i, value), (j, other)]
        for _ in range(random_neighbours):
            sample = self.sample(rng)
            changes = [(i, value) for i, value in enumerate(sample) if value != current[i]]
            if changes:
                yield changes


def memetic_search(whites, across_runs, down_runs, domains, seed,
                   population_size=160, generations=1500,
                   local_search_rate=DEFAULT_LOCAL_SEARCH_RATE,
                   local_search_steps=DEFAULT_LOCAL_SEARCH_STEPS,
                   local_search_patience=DEFAULT_LOCAL_SEARCH_PATIENCE,
                   neighbourhood_limit=DEFAULT_NEIGHBOURHOOD_LIMIT,
                   random_neighbours=DEFAULT_RANDOM_NEIGHBOURS,
                   time_limit=None):
    """Return ``(solution_or_None, diagnostics)``.

    ``domains`` must be the propagated domains used by the hybrid. Local search
    is applied to each initial and offspring individual with probability
    ``local_search_rate``, for at most ``local_search_steps`` moves, stopping
    after ``local_search_patience`` consecutive moves without improvement.

    ``evaluations`` counts full population fitness evaluations, exactly as for
    the hybrid and baselines. Local-search work is reported separately:
    ``local_search_neighbours`` counts scored neighbour assignments (each an
    incremental evaluation of the down runs it changes), not full evaluations.
    ``best_fitness``/``best_candidate`` cover evaluated populations and any
    individual solved by local search during breeding.

    ``time_limit`` (seconds, optional) is checked cooperatively before every
    generation and offspring; reaching it returns the best candidate found with
    ``stop_reason`` set to ``"time_limit"``.
    """
    if type(population_size) is not int or population_size < 1:
        raise ValueError("population_size must be a positive integer")
    if type(generations) is not int or generations < 0:
        raise ValueError("generations must be a nonnegative integer")
    if isinstance(local_search_rate, bool) or not 0 <= local_search_rate <= 1:
        raise ValueError("local_search_rate must be between 0 and 1")
    for name, value in (("local_search_steps", local_search_steps),
                        ("local_search_patience", local_search_patience),
                        ("neighbourhood_limit", neighbourhood_limit),
                        ("random_neighbours", random_neighbours)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if time_limit is not None and (isinstance(time_limit, bool) or time_limit < 0):
        raise ValueError("time_limit must be nonnegative or None")

    started = time.perf_counter()
    deadline = None if time_limit is None else started + time_limit
    diagnostics = {
        "evaluations": 0, "generations_evaluated": 0, "best_fitness": None,
        "best_candidate": None, "fitness_history": [], "restarts": 0,
        "mutation_rate_min": None, "mutation_rate_max": None,
        "local_search_calls": 0, "local_search_steps": 0,
        "local_search_neighbours": 0, "local_search_improving_moves": 0,
        "local_search_sideways_moves": 0, "local_search_fitness_reduction": 0,
        "local_search_solutions": 0, "local_search_time_seconds": 0.0,
        "stop_reason": "generation_limit",
        "settings": {
            "local_search_rate": local_search_rate, "local_search_steps": local_search_steps,
            "local_search_patience": local_search_patience,
            "neighbourhood_limit": neighbourhood_limit, "random_neighbours": random_neighbours,
            "time_limit_seconds": time_limit,
        },
    }
    if generations == 0:
        return None, diagnostics
    rng = random.Random(seed)
    neighbourhoods = [_RunNeighbourhood(run, domains, neighbourhood_limit) for run in across_runs]
    down_index = {cell: index for index, run in enumerate(down_runs) for cell in run["cells"]}
    across_index = {cell: index for index, run in enumerate(across_runs) for cell in run["cells"]}
    crossing = [tuple(sorted({across_index[cell] for cell in run["cells"]})) for run in down_runs]
    down_totals = [run["sum"] for run in down_runs]
    down_lengths = [len(run["cells"]) for run in down_runs]

    def timed_out():
        return deadline is not None and time.perf_counter() >= deadline

    def sample_run(index):
        neighbourhood = neighbourhoods[index]
        return dict(zip(neighbourhood.cells, neighbourhood.sample(rng)))

    def make_individual():
        genes = {}
        for index in range(len(across_runs)):
            genes.update(sample_run(index))
        return genes

    def local_search(genes):
        """Improve ``genes`` in place; return its final down-run fitness."""
        ls_started = time.perf_counter()
        diagnostics["local_search_calls"] += 1
        sums = [0] * len(down_runs)
        counts = [[0] * 10 for _ in down_runs]
        for cell, value in genes.items():
            d = down_index[cell]
            sums[d] += value
            counts[d][value] += 1
        distinct = [sum(1 for count in row if count) for row in counts]
        penalties = [_penalty(down_totals[d], down_lengths[d], sums[d], distinct[d])
                     for d in range(len(down_runs))]
        initial = total = sum(penalties)
        last_moved = None
        idle = 0
        for _ in range(local_search_steps):
            if total == 0 or idle >= local_search_patience:
                break
            diagnostics["local_search_steps"] += 1
            violated = [d for d, penalty in enumerate(penalties) if penalty]
            down = rng.choice(violated)
            options = [a for a in crossing[down] if a != last_moved] or list(crossing[down])
            index = rng.choice(options)
            neighbourhood = neighbourhoods[index]
            cells = neighbourhood.cells
            current = [genes[cell] for cell in cells]
            best_delta = None
            best_changes = None
            ties = 0
            for changes in neighbourhood.candidates(current, rng, random_neighbours):
                diagnostics["local_search_neighbours"] += 1
                delta = 0
                for position, value in changes:
                    d = down_index[cells[position]]
                    old = current[position]
                    row = counts[d]
                    new_distinct = distinct[d] - (row[old] == 1) + (row[value] == 0)
                    delta += _penalty(down_totals[d], down_lengths[d],
                                      sums[d] - old + value, new_distinct) - penalties[d]
                if best_delta is None or delta < best_delta:
                    best_delta, best_changes, ties = delta, changes, 1
                elif delta == best_delta:
                    ties += 1
                    if rng.randrange(ties) == 0:
                        best_changes = changes
            if best_delta is None or best_delta > 0:
                idle += 1
                last_moved = index
                continue
            for position, value in best_changes:
                cell = cells[position]
                d = down_index[cell]
                old = genes[cell]
                row = counts[d]
                row[old] -= 1
                distinct[d] -= row[old] == 0
                distinct[d] += row[value] == 0
                row[value] += 1
                sums[d] += value - old
                penalties[d] = _penalty(down_totals[d], down_lengths[d], sums[d], distinct[d])
                genes[cell] = value
            total += best_delta
            last_moved = index
            if best_delta < 0:
                diagnostics["local_search_improving_moves"] += 1
                idle = 0
            else:
                diagnostics["local_search_sideways_moves"] += 1
                idle += 1
        diagnostics["local_search_fitness_reduction"] += initial - total
        diagnostics["local_search_time_seconds"] += time.perf_counter() - ls_started
        return total

    def improve(genes):
        """Apply local search with the configured probability; return a solution or None."""
        if rng.random() < local_search_rate and local_search(genes) == 0:
            diagnostics["local_search_solutions"] += 1
            diagnostics["best_fitness"] = 0
            diagnostics["best_candidate"] = dict(genes)
            return dict(genes)
        return None

    def new_population():
        population = []
        for _ in range(population_size):
            if timed_out():
                return population, None
            genes = make_individual()
            solved = improve(genes)
            if solved is not None:
                return population, solved
            population.append(genes)
        return population, None

    def finish(solution, reason):
        diagnostics["stop_reason"] = reason
        diagnostics["execution_time_seconds"] = time.perf_counter() - started
        return solution, diagnostics

    population, solved = new_population()
    if solved is not None:
        return finish(solved, "solved_by_local_search")
    best_score = float("inf")
    stagnant = 0
    elite_count = min(8, population_size // 10)
    parent_count = max(1, population_size // 3)
    for generation in range(generations):
        if timed_out() or len(population) < population_size:
            return finish(None, "time_limit")
        scored = [(fitness(candidate, down_runs), candidate) for candidate in population]
        scored.sort(key=lambda item: item[0])
        diagnostics["evaluations"] += len(scored)
        diagnostics["generations_evaluated"] += 1
        if diagnostics["best_fitness"] is None or scored[0][0] < diagnostics["best_fitness"]:
            diagnostics["best_fitness"] = scored[0][0]
            diagnostics["best_candidate"] = dict(scored[0][1])
        diagnostics["fitness_history"].append(diagnostics["best_fitness"])
        if scored[0][0] == 0:
            return finish(dict(scored[0][1]), "solved")
        if generation + 1 == generations:
            break
        if scored[0][0] < best_score:
            best_score = scored[0][0]
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= 100:
            diagnostics["restarts"] += 1
            best_score = float("inf")
            stagnant = 0
            population, solved = new_population()
            if solved is not None:
                return finish(solved, "solved_by_local_search")
            continue

        mutation_rate = min(0.9, 0.25 + 0.65 * stagnant / 100)
        previous_min = diagnostics["mutation_rate_min"]
        previous_max = diagnostics["mutation_rate_max"]
        diagnostics["mutation_rate_min"] = mutation_rate if previous_min is None else min(previous_min, mutation_rate)
        diagnostics["mutation_rate_max"] = mutation_rate if previous_max is None else max(previous_max, mutation_rate)
        next_population = [dict(candidate) for _, candidate in scored[:elite_count]]
        parents = scored[:parent_count]
        while len(next_population) < population_size:
            if timed_out():
                return finish(None, "time_limit")
            parent_a = rng.choice(parents)[1]
            parent_b = rng.choice(parents)[1]
            child = {}
            for run in across_runs:
                parent = parent_a if rng.random() < 0.5 else parent_b
                child.update({cell: parent[cell] for cell in run["cells"]})
            if rng.random() < mutation_rate:
                conflicted = {cell for run in down_runs if fitness(child, [run])
                              for cell in run["cells"]}
                indices = [i for i, run in enumerate(across_runs)
                           if any(cell in conflicted for cell in run["cells"])]
                if indices:
                    child.update(sample_run(rng.choice(indices)))
            solved = improve(child)
            if solved is not None:
                return finish(solved, "solved_by_local_search")
            next_population.append(child)
        population = next_population
    return finish(None, "generation_limit")
