# Kakuro: eight-algorithm evaluation study

Recorded trials: 24 of 24 planned. Puzzle/GA seeds: 42. Population: 160. GA generation limit: 1,500. Maximum population fitness evaluations per GA: 240,000.

Grid sizes count the complete board, including clue borders and internal blocks. For each size and seed, all selected algorithms receive the same puzzle; a puzzle hash is recorded for checking this pairing. Each trial runs sequentially in a fresh Python process. The synthetic generator creates solvable instances but does not guarantee uniqueness.

Configured per-trial solving budget: 120.0 seconds. A timeout means the configured limit was reached, not that the puzzle is unsatisfiable. Completed unsuccessful searches retain their best candidate and measured metrics.

## Algorithm definitions

| Algorithm | Domains | Search mechanism | Restarts / exact fallback |
|---|---|---|---|
| Basic GA | Digits 1 through 9 for every cell | Uniform cell crossover; fixed 0.25 probability of mutating one randomly selected cell | Neither |
| GA + domain filtering | Iterative clue-based constraint propagation before GA | Same crossover and fixed mutation as Basic GA | Neither |
| GA + dynamic mutation | Digits 1 through 9; no domain filtering | Same crossover as Basic GA; mutation rises from 0.25 toward 0.90 with stagnation | Neither |
| Our hybrid algorithm | Iterative propagation and domain-indexed genes | Valid across-run sampling, run-based crossover, conflict-focused adaptive mutation, and Lamarckian local search on selected individuals (probability 0.15) | Preserve distinct elites on restart; exact backtracking if memetic search fails |
| Memetic algorithm | Same propagated domains and domain-restricted genes as our hybrid | Our hybrid's evolutionary operators plus Lamarckian local search on individuals (probability 0.15): steepest-descent reassignment of an across run crossing a violated down run | Preserve distinct elites on restart; no exact fallback (stops at the generation or time budget) |
| Constraint Search | Digits 1-9 narrowed by iterative run propagation | Standalone minimum-remaining-values (MRV) backtracking with propagation after decisions | No GA; the constraint search runs directly |
| CP-SAT | One integer variable with domain 1-9 per white cell | OR-Tools CP-SAT; each run has an exact-sum constraint and AllDifferent | No GA or custom fallback; one search worker, recorded random seed |
| RoundingSat | Nine Boolean variables per white cell, one per digit | Native pseudo-Boolean solver on an OPB feasibility model: exactly one digit per cell, weighted clue sums, at most one occurrence of each digit per run | No GA or custom fallback; native process with recorded binary and options |

The three GA baselines share top-third parent selection and at most eight elites (`min(8, population_size // 10)`). Mutation replaces one selected cell's value with a different allowed digit when one is available. Filtering and dynamic mutation are independent additions to Basic GA, not cumulative variants. Adaptive probability is `min(0.90, 0.25 + 0.65 * stagnant_generations / 100)`.

The memetic algorithm and our hybrid share initial valid across-run sampling, run-based crossover, conflict-focused adaptive mutation, elitism, and restarts, and apply local search to each new individual with probability 0.15. One local-search step picks a violated down run and an across run crossing it, then moves that across run to its best neighbour: every valid assignment when the run has at most 128, otherwise every sum-preserving two-cell change plus eight freshly sampled valid assignments. Improving and equal-fitness moves are accepted, the same run is not moved twice in a row, and search stops after 150 steps or 25 consecutive non-improving steps. Improved genes replace the individual (Lamarckian). Every neighbour keeps the across clues and propagated domains satisfied. Restarts retain up to ten percent of the best distinct candidates and fill the remaining population with fresh individuals. The hybrid then uses exact fallback if needed; standalone memetic has no exact fallback, so its solutions come from evolution and local search alone. It checks the solving budget cooperatively and reports its best candidate when the budget ends; its outer process limit adds the same five-second cleanup grace as RoundingSat.

## Metric definitions

- **Valid solution:** every white cell has a digit 1-9, and every across/down run has the required sum and no repeated digit. An independent validator checks this.
- **Fitness (lower is better):** sum over all runs of `abs(actual_sum - clue_sum) + 9 * (run_length - distinct_digits)`. Zero is a complete valid solution. Our GA preserves across constraints, so its down-only search score equals this common all-run score.
- **Satisfied runs (%):** percentage of runs meeting both the exact sum and no-repeat requirements. This is partial constraint satisfaction, not puzzle validity or cell accuracy.
- **Execution time:** preprocessing/model construction plus the applicable search, including any hybrid fallback. It excludes puzzle generation, parsing, final output validation, library import, and Python process startup. For in-process algorithms it also excludes JSON file I/O. Native RoundingSat process timing is detailed below when selected.
- **Fitness evaluations:** evaluated population members. Auxiliary conflict checks and constraint-propagation work are not included in this count. This metric is N/A for exact solvers, which do not use a GA.
- **Backtracks:** failed branches in Python constraint search or the hybrid's exact fallback. Zero can also occur when exact search succeeds without rejecting a branch. CP-SAT and RoundingSat do not expose an equivalent count here, so their backtracks are N/A.
- **Search counters:** Python backtracks, attempted cell-value branches, and native solver decisions, branches, conflicts, and propagations are reported separately when available. They are diagnostic counts, not directly interchangeable units of effort.
- **Solved white cells:** the complete white-cell count only when the whole solution validates; an unsolved full candidate is not counted as a partially correct solution.

Averages include all completed trials, including unsolved GA runs and native solver UNKNOWN results with recorded measurements. Outer process timeouts/errors remain in the attempted-trial denominator but are excluded from numerical means. Missing measurements are shown as N/A. Means of run satisfaction give each trial equal weight.

Exact-solver statuses distinguish a found solution from a proof of infeasibility and an inconclusive limit. CP-SAT FEASIBLE/OPTIMAL indicate a valid solution, INFEASIBLE indicates proved infeasibility, UNKNOWN indicates no conclusion within the limit, and MODEL_INVALID indicates a model error. Constraint Search uses SOLVED, INFEASIBLE, or UNKNOWN. This is a feasibility model with no optimization objective: CP-SAT OPTIMAL does not establish solution uniqueness or human difficulty.

**RoundingSat timing and statuses:** total execution time includes OPB encoding, temporary file I/O, native binary startup, search, and model decoding. The binary startup cost is included, making this a conservative comparison with the in-process hybrid timer. The native statistic labelled `cpu time` is recorded separately. This Windows build uses a coarse, whole-second clock() statistic; it is not a precise CPU measurement and is not substituted for total wall-clock execution time. Each trial's outer process wall time is also reported below. RoundingSat has a 5-second outer cleanup guard beyond the solving budget so that a native time limit can be recorded; the hybrid and memetic trial workers get a five-second cleanup grace.

RoundingSat statuses are normalized to SOLVED, INFEASIBLE, or UNKNOWN; native SAT/UNSAT statuses are retained in solver diagnostics. UNKNOWN means no conclusion within the limit. The OPB model has no optimization objective. Finding a model does not establish uniqueness. Native decisions and conflicts are not hybrid backtracks, and propagations are not GA fitness evaluations. The recorded seed selects the puzzle and GA randomness; RoundingSat uses its deterministic native defaults rather than a supplied random seed.

### Recorded RoundingSat binary

- Version: RoundingSat 2.
- Platform: Windows x64 static.
- Source commit: `d4edbf7908a9bb951fd181940919e0f3ac7ab1ee`.
- Binary SHA-256: `12a98e4ca9e91cd0fe344e88760fe0eaced3c1e4cf377b5134379ef4fec9fedf`.
- Native LP enabled: Yes.

Source: [official RoundingSat repository](https://gitlab.com/MIAOresearch/software/roundingsat).
Binary: [recorded download](https://gitlab.com/api/v4/projects/MIAOresearch%2Fsoftware%2Froundingsat/jobs/artifacts/master/raw/build/roundingsat.exe?job=build-windows).

## Aggregate results

| Algorithm | Valid / trials | Memetic-stage valid | Fallback valid | Completed | Mean time (s) | Mean evaluations | Mean search-stage runs satisfied (%) | Mean final runs satisfied (%) | Total backtracks | Branches | CP-SAT conflicts | RoundingSat decisions | RoundingSat conflicts | RoundingSat propagations | Mean native reported time (s) | Native time limits | Timeouts / errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Basic GA | 1 / 3 | 1 | 0 | 3 | 1.9269 | 160,800.00 | 85.00 | 85.00 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| GA + domain filtering | 3 / 3 | 3 | 0 | 3 | 0.2662 | 24,053.33 | 100.00 | 100.00 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| GA + dynamic mutation | 2 / 3 | 2 | 0 | 3 | 0.9672 | 95,520.00 | 91.67 | 91.67 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| Our hybrid algorithm | 3 / 3 | 3 | 0 | 3 | 0.0076 | 0.00 | 100.00 | 100.00 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| Memetic algorithm | 3 / 3 | 3 | 0 | 3 | 0.0072 | 0.00 | 100.00 | 100.00 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| Constraint Search | 3 / 3 | N/A | N/A | 3 | 0.0157 | N/A | N/A | 100.00 | 0 | 16 | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| CP-SAT | 3 / 3 | N/A | N/A | 3 | 0.0335 | N/A | N/A | 100.00 | N/A | 3,145 | 10 | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| RoundingSat | 3 / 3 | N/A | N/A | 3 | 0.1121 | N/A | N/A | 100.00 | N/A | N/A | N/A | 274 | 48 | 789 | 0.000000 | 0 | 0 / 0 |

## Per-grid execution time and validity

Each entry is **mean seconds; valid/attempted trials**. With one seed it is the actual single-run measurement. An unsuccessful GA run's elapsed time is a budget-exhaustion time, not a time to solve. For exact solvers, the status distinguishes infeasibility from an inconclusive limit.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm | Memetic algorithm | Constraint Search | CP-SAT | RoundingSat |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4x4 | 0.0209; 1/1 | 0.0189; 1/1 | 0.0240; 1/1 | 0.0020; 1/1 | 0.0017; 1/1 | 0.0022; 1/1 | 0.0271; 1/1 | 0.0928; 1/1 |
| 5x5 | 2.1667; 0/1 | 0.3028; 1/1 | 2.2658; 0/1 | 0.0091; 1/1 | 0.0091; 1/1 | 0.0117; 1/1 | 0.0231; 1/1 | 0.0771; 1/1 |
| 6x6 | 3.5932; 0/1 | 0.4770; 1/1 | 0.6117; 1/1 | 0.0119; 1/1 | 0.0110; 1/1 | 0.0331; 1/1 | 0.0502; 1/1 | 0.1665; 1/1 |

## Per-grid outer process wall time

Each entry is mean elapsed seconds for the complete worker process, including Python startup, library loading, puzzle parsing, search, validation, and result serialization. RoundingSat additionally starts its native process. This secondary measurement compares the full invocation costs of both implementations. Every recorded wall time is included, including outer timeouts; pair it with the validity table above before interpreting performance.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm | Memetic algorithm | Constraint Search | CP-SAT | RoundingSat |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4x4 | 0.381635 | 0.336999 | 0.552728 | 0.368268 | 0.341392 | 0.339450 | 1.340433 | 0.449471 |
| 5x5 | 2.506163 | 0.684668 | 2.612566 | 0.369935 | 0.334006 | 0.455749 | 1.411011 | 0.452673 |
| 6x6 | 4.011152 | 0.840504 | 0.987189 | 0.406119 | 0.376776 | 0.456452 | 1.338439 | 0.540957 |

## Per-grid best search fitness before fallback

Lower is better; zero means the evolutionary/local-search phase solved the puzzle. These values are the best candidate encountered within the search budget, including candidates retained across restarts. Our fallback cannot improve the values in this table. Multiple seeds are averaged.

Exact solvers have no evolutionary phase; they are omitted from this table.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm | Memetic algorithm |
|---|---:|---:|---:|---:|---:|
| 4x4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 5x5 | 2.00 | 0.00 | 2.00 | 0.00 | 0.00 |
| 6x6 | 2.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Standalone exact-solver diagnostics

Times include model/preprocessing and search. CP-SAT conflicts and Python failed backtracking branches are different diagnostics; neither is substituted for the other. GA evaluations and generations are N/A for these algorithms.

| Grid | Seed | Algorithm | Trial status | Solver status | Total (s) | Model / preprocess (s) | Search (s) | Branches | Backtracks | CP-SAT conflicts | Valid | Solved / white cells |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 4x4 | 42 | Constraint Search | completed | SOLVED | 0.002229 | 0.000984 | 0.001245 | 4 | 0 | N/A | Yes | 9 / 9 |
| 4x4 | 42 | CP-SAT | completed | OPTIMAL | 0.027127 | 0.001113 | 0.026014 | 797 | N/A | 0 | Yes | 9 / 9 |
| 5x5 | 42 | Constraint Search | completed | SOLVED | 0.011746 | 0.005295 | 0.006450 | 4 | 0 | N/A | Yes | 12 / 12 |
| 5x5 | 42 | CP-SAT | completed | OPTIMAL | 0.023088 | 0.001219 | 0.021869 | 621 | N/A | 4 | Yes | 12 / 12 |
| 6x6 | 42 | Constraint Search | completed | SOLVED | 0.033103 | 0.008817 | 0.024286 | 8 | 0 | N/A | Yes | 21 / 21 |
| 6x6 | 42 | CP-SAT | completed | OPTIMAL | 0.050176 | 0.001731 | 0.048445 | 1,727 | N/A | 6 | Yes | 21 / 21 |

## RoundingSat native diagnostics

Total time includes the native process overhead; native reported time is the solver's coarse clock statistic, labelled cpu time upstream. Outer wall time additionally includes Python startup, parsing, validation, and result serialization. Native limits are recorded separately from an outer process timeout. Missing native counters remain N/A.

| Grid | Seed | Trial status | Solver status | Native status | Total (s) | Native reported (s) | Outer wall (s) | Decisions | Conflicts | Propagations | OPB variables | OPB constraints | Native limit | Valid |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 4x4 | 42 | completed | SOLVED | SATISFIABLE | 0.092785 | 0.000000 | 0.449471 | 34 | 1 | 54 | 81 | 69 | No | Yes |
| 5x5 | 42 | completed | SOLVED | SATISFIABLE | 0.077093 | 0.000000 | 0.452673 | 100 | 19 | 252 | 108 | 92 | No | Yes |
| 6x6 | 42 | completed | SOLVED | SATISFIABLE | 0.166503 | 0.000000 | 0.540957 | 140 | 28 | 483 | 189 | 121 | No | Yes |

## Memetic algorithm versus our hybrid

Both receive the same puzzle, propagated domains, population, generation limit, and memetic operators. Entries are mean seconds over completed trials; `memetic`/`fallback` says how our hybrid finished. The ratio is hybrid time divided by memetic time and is shown only when every trial of both methods for that grid produced a valid solution.

| Grid | Our hybrid (s) | Hybrid solved by | Memetic only (s) | Memetic valid | Memetic generations | Hybrid / memetic time |
|---|---:|---|---:|---|---:|---:|
| 4x4 | 0.0020 | memetic 1, fallback 0 of 1 | 0.0017 | 1/1 | 0.0 | 1.2x |
| 5x5 | 0.0091 | memetic 1, fallback 0 of 1 | 0.0091 | 1/1 | 0.0 | 1.0x |
| 6x6 | 0.0119 | memetic 1, fallback 0 of 1 | 0.0110 | 1/1 | 0.0 | 1.1x |

Grids fully solved by both: 3; memetic mean time lower on 3 of them. Single-trial timings on a loaded machine vary, so treat small differences as ties.

## Memetic local-search diagnostics

Calls are individuals passed to local search; steps are run reassignment attempts; neighbours are scored candidate assignments (incremental down-run evaluations, not full fitness evaluations). Fitness reduction sums the improvement achieved inside local search.

| Grid | Seed | Algorithm | Status | Stop reason | Time (s) | Local-search time (s) | Generations | Restarts | Calls | Steps | Neighbours | Improving moves | Sideways moves | Fitness reduction | Best fitness | Valid |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 4x4 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.0020 | 0.0003 | 0 | 0 | 1 | 2 | 82 | 2 | 0 | 38 | 0 | Yes |
| 4x4 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.0017 | 0.0002 | 0 | 0 | 1 | 2 | 82 | 2 | 0 | 38 | 0 | Yes |
| 5x5 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.0091 | 0.0038 | 0 | 0 | 2 | 38 | 1,349 | 7 | 12 | 52 | 0 | Yes |
| 5x5 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.0091 | 0.0037 | 0 | 0 | 2 | 38 | 1,349 | 7 | 12 | 52 | 0 | Yes |
| 6x6 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.0119 | 0.0021 | 0 | 0 | 1 | 18 | 541 | 6 | 3 | 45 | 0 | Yes |
| 6x6 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.0110 | 0.0016 | 0 | 0 | 1 | 18 | 541 | 6 | 3 | 45 | 0 | Yes |

## Every measured trial

All times are seconds. A completed status includes unsuccessful searches. Pre-fallback fitness and run satisfaction describe the best evolutionary/local-search candidate; final columns describe the returned candidate or solution.

| Grid | Seed | Algorithm | Status | Time | Preprocess | GA time | Fallback time | Evaluations | Generations | Search fitness | Final fitness | Search valid | Final valid | Fallback used | Backtracks | Search runs (%) | Final runs (%) | Solved/white cells | Domain reduction (%) |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| 4x4 | 42 | Basic GA | completed | 0.0209 | 0.0000 | 0.0209 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + domain filtering | completed | 0.0189 | 0.0010 | 0.0179 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + dynamic mutation | completed | 0.0240 | 0.0000 | 0.0240 | 0.0000 | 2,240 | 14 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Our hybrid algorithm | completed | 0.0020 | 0.0012 | 0.0008 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Memetic algorithm | completed | 0.0017 | 0.0010 | 0.0006 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Constraint Search | completed | 0.0022 | 0.0010 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | CP-SAT | completed | 0.0271 | 0.0011 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 9/9 | N/A |
| 4x4 | 42 | RoundingSat | completed | 0.0928 | 0.0034 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 9/9 | N/A |
| 5x5 | 42 | GA + domain filtering | completed | 0.3028 | 0.0036 | 0.2992 | 0.0000 | 31,040 | 194 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | GA + dynamic mutation | completed | 2.2658 | 0.0000 | 2.2658 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 5x5 | 42 | Our hybrid algorithm | completed | 0.0091 | 0.0035 | 0.0056 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | Memetic algorithm | completed | 0.0091 | 0.0039 | 0.0051 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | Constraint Search | completed | 0.0117 | 0.0053 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | CP-SAT | completed | 0.0231 | 0.0012 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 12/12 | N/A |
| 5x5 | 42 | RoundingSat | completed | 0.0771 | 0.0029 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 12/12 | N/A |
| 5x5 | 42 | Basic GA | completed | 2.1667 | 0.0000 | 2.1667 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 6x6 | 42 | GA + dynamic mutation | completed | 0.6117 | 0.0000 | 0.6116 | 0.0000 | 44,320 | 277 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 0.00 |
| 6x6 | 42 | Our hybrid algorithm | completed | 0.0119 | 0.0084 | 0.0035 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | Memetic algorithm | completed | 0.0110 | 0.0083 | 0.0027 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | Constraint Search | completed | 0.0331 | 0.0088 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | CP-SAT | completed | 0.0502 | 0.0017 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 21/21 | N/A |
| 6x6 | 42 | RoundingSat | completed | 0.1665 | 0.0034 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 21/21 | N/A |
| 6x6 | 42 | Basic GA | completed | 3.5932 | 0.0000 | 3.5932 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 80.00 | 80.00 | 0/21 | 0.00 |
| 6x6 | 42 | GA + domain filtering | completed | 0.4770 | 0.0095 | 0.4675 | 0.0000 | 38,720 | 242 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |

## Findings and interpretation

Observed complete-solution counts: Basic GA 1/3; GA + domain filtering 3/3; GA + dynamic mutation 2/3; Our hybrid algorithm 3/3; Memetic algorithm 3/3; Constraint Search 3/3; CP-SAT 3/3; RoundingSat 3/3.

Our memetic phase solved 3 of 3 attempted trials; the exact fallback supplied 0 additional valid solutions. These two contributions must be distinguished when judging the hybrid's complete-solution rate.

Completed population searches exhausting the generation budget without a search-stage solution: Basic GA: 2; GA + domain filtering: 0; GA + dynamic mutation: 1; Our hybrid algorithm: 0; Memetic algorithm: 0.

Domain filtering versus Basic GA isolates the tested preprocessing change; dynamic mutation versus Basic GA isolates the tested mutation schedule. Our algorithm changes several mechanisms together, so its difference cannot be attributed to domain filtering or adaptive mutation alone.

Our hybrid performs exact search after its bounded memetic phase fails. Its final validity and total runtime include this work; its pre-fallback fitness, memetic-stage validity, and separately reported fallback time show the contribution of each stage.

The memetic algorithm solved 3 of 3 attempted trials with no exact fallback. Its fitness-evaluation count covers whole-population evaluations only; local-search neighbour scoring is reported separately and its time is included in the GA and total times.

Standalone memetic versus our hybrid compares the shared memetic search with and without exact backtracking fallback. Both receive the same memetic time budget in this study.

Constraint Search directly applies propagation and exact backtracking without a preceding GA phase.

CP-SAT solves a declarative sum/AllDifferent model with one search worker and no supplied solution hints.

RoundingSat solves the encoded pseudo-Boolean constraints directly, without a supplied solution witness or hybrid GA phase. Its native decisions and conflicts measure different operations from the hybrid's fitness evaluations and failed backtracking branches. This comparison measures these complete implementations on the recorded instances; it does not isolate a single algorithmic improvement or programming-language effect.

Exact solvers are not subject to the GA-generation limit; the recorded time limit applies instead.

Do not infer a speedup from an unsolved algorithm stopping sooner. Compare time to a valid solution only on paired instances that both algorithms solve. Constraint satisfaction and residual fitness help describe failed searches, but cannot replace full solution validity.

With one seed per size, these results are descriptive observations, not statistical proof of superiority. Increasing to five seeds supplies repeated observations but still requires reporting variability and failed trials. Grid size, clue tightness, run structure, and white-cell count all affect difficulty. These regular generated puzzles are not a calibrated human difficulty dataset.

Solutions are not guaranteed unique. Comparing digits to the generator's hidden witness would incorrectly label other valid solutions as wrong, so this study reports constraint validity rather than witness-based cell accuracy. Machine load and Python implementation also affect wall-clock measurements.
