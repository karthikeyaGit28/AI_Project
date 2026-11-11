"""Cell-based genetic baselines for the Kakuro comparison study.

The basic and dynamic-mutation variants receive unrestricted digit domains.
The domain-filtering variant receives domains computed by constraint propagation
before this search. Filtering and dynamic mutation are independent additions to
the basic GA, rather than a cumulative sequence of improvements.

All three use uniform cell crossover, top-third parent selection, fixed elitism,
and mutation of one cell. They do not use run-preserving crossover, repair,
restarts, or backtracking. An unsuccessful search returns its best candidate;
the caller must independently check whether that candidate solves the puzzle.
"""

import random


def _indexed_fitness(chromosome, indexed_runs):
    """Sum clue errors and nine times the number of repeated run digits."""
    score = 0
    for indices, total in indexed_runs:
        values = [chromosome[index] for index in indices]
        score += abs(sum(values) - total)
        score += 9 * (len(values) - len(set(values)))
    return score


def baseline_search(whites, runs, domains, seed, population_size=160,
                    generations=1500, dynamic_mutation=False):
    """Return ``(best_candidate, diagnostics)`` for a cell-based genetic search.

    ``domains`` supplies the allowed digits for every white cell. Pass 1..9 for
    the basic/dynamic variants, or propagated domains for domain filtering.
    Mutation selects one cell uniformly and, when possible, replaces its digit
    with a different allowed digit. A fixed probability of 0.25 is used unless
    ``dynamic_mutation`` is true; then the probability rises with stagnation as
    ``min(0.9, 0.25 + 0.65 * stagnant_generations / 100)``.

    Diagnostics count only evaluated populations. ``fitness_history`` records
    the best fitness seen by the end of each evaluated generation. Mutation-rate
    bounds describe rates actually used to breed a new population; they remain
    null if search stops before breeding. No supplied domain is modified.
    """
    if type(population_size) is not int or population_size < 1:
        raise ValueError("population_size must be a positive integer")
    if type(generations) is not int or generations < 0:
        raise ValueError("generations must be a nonnegative integer")
    if type(dynamic_mutation) is not bool:
        raise ValueError("dynamic_mutation must be a boolean")
    cells = tuple(whites)
    if not cells or len(set(cells)) != len(cells):
        raise ValueError("whites must contain distinct cells and cannot be empty")
    allowed = []
    for cell in cells:
        values = domains.get(cell)
        if not values or any(type(value) is not int or not 1 <= value <= 9 for value in values):
            raise ValueError(f"invalid domain for cell {cell}")
        allowed.append(tuple(sorted(set(values))))
    indices = {cell: index for index, cell in enumerate(cells)}
    indexed_runs = tuple((tuple(indices[cell] for cell in run["cells"]), run["sum"])
                         for run in runs)
    diagnostics = {
        "evaluations": 0,
        "generations_evaluated": 0,
        "best_fitness": None,
        "fitness_history": [],
        "mutation_rate_min": None,
        "mutation_rate_max": None,
    }
    if generations == 0:
        return None, diagnostics

    rng = random.Random(seed)
    population = [tuple(rng.choice(values) for values in allowed)
                  for _ in range(population_size)]
    alternatives = [{value: tuple(other for other in values if other != value)
                     for value in values} for values in allowed]
    best_candidate = None
    best_score = float("inf")
    stagnant = 0
    elite_count = min(8, population_size // 10)
    parent_count = max(1, population_size // 3)
    for generation in range(generations):
        scored = [(_indexed_fitness(candidate, indexed_runs), candidate)
                  for candidate in population]
        scored.sort(key=lambda item: item[0])
        diagnostics["evaluations"] += len(scored)
        diagnostics["generations_evaluated"] += 1
        if scored[0][0] < best_score:
            best_score, best_candidate = scored[0]
            stagnant = 0
        else:
            stagnant += 1
        diagnostics["best_fitness"] = best_score
        diagnostics["fitness_history"].append(best_score)
        if best_score == 0 or generation + 1 == generations:
            break

        mutation_rate = min(0.9, 0.25 + 0.65 * stagnant / 100) if dynamic_mutation else 0.25
        previous_min = diagnostics["mutation_rate_min"]
        previous_max = diagnostics["mutation_rate_max"]
        diagnostics["mutation_rate_min"] = mutation_rate if previous_min is None else min(previous_min, mutation_rate)
        diagnostics["mutation_rate_max"] = mutation_rate if previous_max is None else max(previous_max, mutation_rate)
        next_population = [candidate for _, candidate in scored[:elite_count]]
        parents = [candidate for _, candidate in scored[:parent_count]]
        while len(next_population) < population_size:
            parent_a = rng.choice(parents)
            parent_b = rng.choice(parents)
            child = [a if rng.random() < 0.5 else b for a, b in zip(parent_a, parent_b)]
            if rng.random() < mutation_rate:
                index = rng.randrange(len(cells))
                replacements = alternatives[index][child[index]]
                if replacements:
                    child[index] = rng.choice(replacements)
            next_population.append(tuple(child))
        population = next_population

    return dict(zip(cells, best_candidate)), diagnostics
