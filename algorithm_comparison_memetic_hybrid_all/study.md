# Kakuro: eight-algorithm evaluation study

Recorded trials: 96 of 96 planned. Puzzle/GA seeds: 42. Population: 160. GA generation limit: 1,500. Maximum population fitness evaluations per GA: 240,000.

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
| Basic GA | 1 / 12 | 1 | 0 | 12 | 19.7421 | 220,200.00 | 54.38 | 54.38 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| GA + domain filtering | 3 / 12 | 3 | 0 | 12 | 19.3489 | 186,013.33 | 69.27 | 69.27 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| GA + dynamic mutation | 2 / 12 | 2 | 0 | 12 | 18.9775 | 203,880.00 | 58.87 | 58.87 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| Our hybrid algorithm | 11 / 12 | 10 | 1 | 11 | 28.6742 | 13,454.55 | 99.68 | 100.00 | 5 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 1 / 0 |
| Memetic algorithm | 11 / 12 | 11 | 0 | 12 | 28.8914 | 13,213.33 | 99.70 | 99.70 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| Constraint Search | 12 / 12 | N/A | N/A | 12 | 6.3101 | N/A | N/A | 100.00 | 20,359 | 20,940 | N/A | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| CP-SAT | 12 / 12 | N/A | N/A | 12 | 2.2874 | N/A | N/A | 100.00 | N/A | 797,388 | 182,537 | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| RoundingSat | 12 / 12 | N/A | N/A | 12 | 19.1676 | N/A | N/A | 100.00 | N/A | N/A | N/A | 1,685,383 | 432,217 | 14,149,378 | 18.916667 | 0 | 0 / 0 |

## Per-grid execution time and validity

Each entry is **mean seconds; valid/attempted trials**. With one seed it is the actual single-run measurement. An unsuccessful GA run's elapsed time is a budget-exhaustion time, not a time to solve. For exact solvers, the status distinguishes infeasibility from an inconclusive limit.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm | Memetic algorithm | Constraint Search | CP-SAT | RoundingSat |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4x4 | 0.0160; 1/1 | 0.0222; 1/1 | 0.0148; 1/1 | 0.0023; 1/1 | 0.0014; 1/1 | 0.0026; 1/1 | 0.0328; 1/1 | 0.0633; 1/1 |
| 5x5 | 2.2231; 0/1 | 0.3426; 1/1 | 2.4882; 0/1 | 0.0116; 1/1 | 0.0097; 1/1 | 0.0133; 1/1 | 0.0354; 1/1 | 0.0753; 1/1 |
| 6x6 | 4.1002; 0/1 | 0.5406; 1/1 | 0.5251; 1/1 | 0.0094; 1/1 | 0.0096; 1/1 | 0.0309; 1/1 | 0.0331; 1/1 | 0.1292; 1/1 |
| 8x8 | 8.4132; 0/1 | 9.0119; 0/1 | 9.6071; 0/1 | 0.0868; 1/1 | 0.0375; 1/1 | 0.0879; 1/1 | 0.0737; 1/1 | 0.1699; 1/1 |
| 10x10 | 16.7960; 0/1 | 16.3931; 0/1 | 15.9660; 0/1 | 0.6348; 1/1 | 0.9638; 1/1 | 0.3883; 1/1 | 0.1476; 1/1 | 0.2602; 1/1 |
| 12x12 | 23.0101; 0/1 | 22.8893; 0/1 | 23.5678; 0/1 | 26.7259; 1/1 | 34.0348; 1/1 | 1.1268; 1/1 | 0.1886; 1/1 | 0.3178; 1/1 |
| 15x15 | 43.1982; 0/1 | 44.3245; 0/1 | 44.1782; 0/1 | 91.8099; 1/1 | 90.0341; 0/1 | 0.7180; 1/1 | 18.2286; 1/1 | 78.4052; 1/1 |
| 16x16 | 50.0755; 0/1 | 49.7908; 0/1 | 50.5223; 0/1 | N/A; 0/1 | 23.1774; 1/1 | 30.6627; 1/1 | 1.1546; 1/1 | 66.1985; 1/1 |
| 11x17 | 35.7095; 0/1 | 34.8823; 0/1 | 20.3240; 0/1 | 55.8782; 1/1 | 59.9965; 1/1 | 3.7204; 1/1 | 1.1867; 1/1 | 2.5204; 1/1 |
| 13x17 | 18.5154; 0/1 | 18.2140; 0/1 | 25.4500; 0/1 | 71.6161; 1/1 | 70.4264; 1/1 | 36.6791; 1/1 | 0.7142; 1/1 | 42.0738; 1/1 |
| 14x14 | 16.2640; 0/1 | 16.9421; 0/1 | 15.9362; 0/1 | 18.0394; 1/1 | 18.8003; 1/1 | 1.3665; 1/1 | 0.2191; 1/1 | 2.1062; 1/1 |
| 14x17 | 18.5840; 0/1 | 18.8330; 0/1 | 19.1507; 0/1 | 50.6018; 1/1 | 49.2052; 1/1 | 0.9250; 1/1 | 5.4347; 1/1 | 37.6916; 1/1 |

## Per-grid outer process wall time

Each entry is mean elapsed seconds for the complete worker process, including Python startup, library loading, puzzle parsing, search, validation, and result serialization. RoundingSat additionally starts its native process. This secondary measurement compares the full invocation costs of both implementations. Every recorded wall time is included, including outer timeouts; pair it with the validity table above before interpreting performance.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm | Memetic algorithm | Constraint Search | CP-SAT | RoundingSat |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4x4 | 0.317710 | 0.486043 | 0.424504 | 0.262357 | 0.363431 | 0.356995 | 1.146409 | 0.505584 |
| 5x5 | 2.632443 | 0.681889 | 2.877067 | 0.388470 | 0.418602 | 0.500487 | 1.752866 | 0.521995 |
| 6x6 | 4.447972 | 0.898544 | 0.881714 | 0.372710 | 0.345101 | 0.439727 | 1.352437 | 0.514939 |
| 8x8 | 8.862882 | 9.386684 | 10.093294 | 0.624355 | 0.677234 | 0.480950 | 1.586303 | 0.525696 |
| 10x10 | 17.241508 | 16.848165 | 16.320844 | 1.063274 | 1.431031 | 0.765608 | 1.833943 | 0.654455 |
| 12x12 | 23.520462 | 23.363235 | 23.977862 | 27.156122 | 34.502292 | 1.438031 | 1.911134 | 0.774547 |
| 15x15 | 43.604216 | 44.888612 | 44.672454 | 92.373780 | 90.528953 | 1.135739 | 20.182138 | 78.954919 |
| 16x16 | 50.549591 | 50.265116 | 51.003348 | 13,001.972618 | 23.864820 | 31.116729 | 3.357149 | 66.646889 |
| 11x17 | 36.158800 | 35.523379 | 20.732540 | 56.291134 | 60.408847 | 4.141900 | 2.662699 | 2.894722 |
| 13x17 | 18.971894 | 18.551455 | 25.934258 | 71.958397 | 70.965889 | 37.268220 | 2.579600 | 42.445888 |
| 14x14 | 16.706079 | 17.291263 | 16.367045 | 18.548180 | 19.334494 | 1.851371 | 1.632700 | 2.443122 |
| 14x17 | 18.946973 | 19.205436 | 19.538554 | 51.092209 | 49.799578 | 1.296180 | 6.928773 | 38.044982 |

## Per-grid best search fitness before fallback

Lower is better; zero means the evolutionary/local-search phase solved the puzzle. These values are the best candidate encountered within the search budget, including candidates retained across restarts. Our fallback cannot improve the values in this table. Multiple seeds are averaged.

Exact solvers have no evolutionary phase; they are omitted from this table.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm | Memetic algorithm |
|---|---:|---:|---:|---:|---:|
| 4x4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 5x5 | 2.00 | 0.00 | 2.00 | 0.00 | 0.00 |
| 6x6 | 2.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 8x8 | 14.00 | 4.00 | 12.00 | 0.00 | 0.00 |
| 10x10 | 24.00 | 33.00 | 36.00 | 0.00 | 0.00 |
| 12x12 | 41.00 | 45.00 | 24.00 | 0.00 | 0.00 |
| 15x15 | 73.00 | 122.00 | 54.00 | 2.00 | 2.00 |
| 16x16 | 136.00 | 78.00 | 82.00 | N/A | 0.00 |
| 11x17 | 51.00 | 93.00 | 48.00 | 0.00 | 0.00 |
| 13x17 | 87.00 | 79.00 | 52.00 | 0.00 | 0.00 |
| 14x14 | 90.00 | 69.00 | 48.00 | 0.00 | 0.00 |
| 14x17 | 87.00 | 120.00 | 71.00 | 0.00 | 0.00 |

## Standalone exact-solver diagnostics

Times include model/preprocessing and search. CP-SAT conflicts and Python failed backtracking branches are different diagnostics; neither is substituted for the other. GA evaluations and generations are N/A for these algorithms.

| Grid | Seed | Algorithm | Trial status | Solver status | Total (s) | Model / preprocess (s) | Search (s) | Branches | Backtracks | CP-SAT conflicts | Valid | Solved / white cells |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 4x4 | 42 | Constraint Search | completed | SOLVED | 0.002609 | 0.001164 | 0.001445 | 4 | 0 | N/A | Yes | 9 / 9 |
| 4x4 | 42 | CP-SAT | completed | OPTIMAL | 0.032757 | 0.001980 | 0.030777 | 797 | N/A | 0 | Yes | 9 / 9 |
| 5x5 | 42 | Constraint Search | completed | SOLVED | 0.013323 | 0.005086 | 0.008237 | 4 | 0 | N/A | Yes | 12 / 12 |
| 5x5 | 42 | CP-SAT | completed | OPTIMAL | 0.035369 | 0.002392 | 0.032976 | 621 | N/A | 4 | Yes | 12 / 12 |
| 6x6 | 42 | Constraint Search | completed | SOLVED | 0.030894 | 0.007010 | 0.023884 | 8 | 0 | N/A | Yes | 21 / 21 |
| 6x6 | 42 | CP-SAT | completed | OPTIMAL | 0.033078 | 0.001102 | 0.031976 | 1,727 | N/A | 6 | Yes | 21 / 21 |
| 8x8 | 42 | Constraint Search | completed | SOLVED | 0.087935 | 0.025362 | 0.062573 | 15 | 0 | N/A | Yes | 39 / 39 |
| 8x8 | 42 | CP-SAT | completed | OPTIMAL | 0.073712 | 0.002467 | 0.071245 | 2,892 | N/A | 1 | Yes | 39 / 39 |
| 10x10 | 42 | Constraint Search | completed | SOLVED | 0.388281 | 0.042455 | 0.345826 | 40 | 1 | N/A | Yes | 67 / 67 |
| 10x10 | 42 | CP-SAT | completed | OPTIMAL | 0.147552 | 0.002838 | 0.144714 | 6,129 | N/A | 84 | Yes | 67 / 67 |
| 12x12 | 42 | Constraint Search | completed | SOLVED | 1.126754 | 0.027483 | 1.099272 | 423 | 370 | N/A | Yes | 97 / 97 |
| 12x12 | 42 | CP-SAT | completed | OPTIMAL | 0.188581 | 0.002482 | 0.186099 | 8,722 | N/A | 83 | Yes | 97 / 97 |
| 15x15 | 42 | CP-SAT | completed | OPTIMAL | 18.228556 | 0.003251 | 18.225305 | 401,043 | N/A | 96,112 | Yes | 156 / 156 |
| 15x15 | 42 | Constraint Search | completed | SOLVED | 0.717992 | 0.103147 | 0.614845 | 73 | 5 | N/A | Yes | 156 / 156 |
| 16x16 | 42 | Constraint Search | completed | SOLVED | 30.662727 | 0.081285 | 30.581442 | 7,872 | 7,774 | N/A | Yes | 181 / 181 |
| 16x16 | 42 | CP-SAT | completed | OPTIMAL | 1.154579 | 0.020981 | 1.133598 | 55,189 | N/A | 8,301 | Yes | 181 / 181 |
| 11x17 | 42 | Constraint Search | completed | SOLVED | 3.720444 | 0.111499 | 3.608944 | 1,057 | 995 | N/A | Yes | 128 / 128 |
| 11x17 | 42 | CP-SAT | completed | OPTIMAL | 1.186704 | 0.003675 | 1.183029 | 57,851 | N/A | 17,473 | Yes | 128 / 128 |
| 13x17 | 42 | Constraint Search | completed | SOLVED | 36.679082 | 0.156751 | 36.522331 | 11,214 | 11,139 | N/A | Yes | 152 / 152 |
| 13x17 | 42 | CP-SAT | completed | OPTIMAL | 0.714207 | 0.008250 | 0.705958 | 37,392 | N/A | 5,688 | Yes | 152 / 152 |
| 14x14 | 42 | Constraint Search | completed | SOLVED | 1.366493 | 0.105836 | 1.260657 | 147 | 72 | N/A | Yes | 137 / 137 |
| 14x14 | 42 | CP-SAT | completed | OPTIMAL | 0.219079 | 0.004961 | 0.214118 | 12,930 | N/A | 401 | Yes | 137 / 137 |
| 14x17 | 42 | Constraint Search | completed | SOLVED | 0.925041 | 0.116531 | 0.808510 | 83 | 3 | N/A | Yes | 164 / 164 |
| 14x17 | 42 | CP-SAT | completed | OPTIMAL | 5.434712 | 0.003993 | 5.430719 | 212,095 | N/A | 54,384 | Yes | 164 / 164 |

## RoundingSat native diagnostics

Total time includes the native process overhead; native reported time is the solver's coarse clock statistic, labelled cpu time upstream. Outer wall time additionally includes Python startup, parsing, validation, and result serialization. Native limits are recorded separately from an outer process timeout. Missing native counters remain N/A.

| Grid | Seed | Trial status | Solver status | Native status | Total (s) | Native reported (s) | Outer wall (s) | Decisions | Conflicts | Propagations | OPB variables | OPB constraints | Native limit | Valid |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 4x4 | 42 | completed | SOLVED | SATISFIABLE | 0.063301 | 0.000000 | 0.505584 | 34 | 1 | 54 | 81 | 69 | No | Yes |
| 5x5 | 42 | completed | SOLVED | SATISFIABLE | 0.075340 | 0.000000 | 0.521995 | 100 | 19 | 252 | 108 | 92 | No | Yes |
| 6x6 | 42 | completed | SOLVED | SATISFIABLE | 0.129204 | 0.000000 | 0.514939 | 140 | 28 | 483 | 189 | 121 | No | Yes |
| 8x8 | 42 | completed | SOLVED | SATISFIABLE | 0.169917 | 0.000000 | 0.525696 | 554 | 78 | 2,153 | 351 | 209 | No | Yes |
| 10x10 | 42 | completed | SOLVED | SATISFIABLE | 0.260192 | 0.000000 | 0.654455 | 1,395 | 294 | 7,649 | 603 | 307 | No | Yes |
| 12x12 | 42 | completed | SOLVED | SATISFIABLE | 0.317761 | 0.000000 | 0.774547 | 8,316 | 1,486 | 49,844 | 873 | 437 | No | Yes |
| 15x15 | 42 | completed | SOLVED | SATISFIABLE | 78.405171 | 78.000000 | 78.954919 | 382,386 | 102,066 | 3,190,435 | 1,404 | 716 | No | Yes |
| 16x16 | 42 | completed | SOLVED | SATISFIABLE | 66.198510 | 66.000000 | 66.646889 | 354,199 | 82,380 | 2,954,355 | 1,629 | 781 | No | Yes |
| 11x17 | 42 | completed | SOLVED | SATISFIABLE | 2.520366 | 2.000000 | 2.894722 | 25,230 | 7,888 | 197,095 | 1,152 | 608 | No | Yes |
| 13x17 | 42 | completed | SOLVED | SATISFIABLE | 42.073810 | 42.000000 | 42.445888 | 389,108 | 114,642 | 3,568,749 | 1,368 | 692 | No | Yes |
| 14x14 | 42 | completed | SOLVED | SATISFIABLE | 2.106155 | 2.000000 | 2.443122 | 20,213 | 5,798 | 161,064 | 1,233 | 617 | No | Yes |
| 14x17 | 42 | completed | SOLVED | SATISFIABLE | 37.691569 | 37.000000 | 38.044982 | 503,708 | 117,537 | 4,017,245 | 1,476 | 724 | No | Yes |

## Memetic algorithm versus our hybrid

Both receive the same puzzle, propagated domains, population, generation limit, and memetic operators. Entries are mean seconds over completed trials; `memetic`/`fallback` says how our hybrid finished. The ratio is hybrid time divided by memetic time and is shown only when every trial of both methods for that grid produced a valid solution.

| Grid | Our hybrid (s) | Hybrid solved by | Memetic only (s) | Memetic valid | Memetic generations | Hybrid / memetic time |
|---|---:|---|---:|---|---:|---:|
| 4x4 | 0.0023 | memetic 1, fallback 0 of 1 | 0.0014 | 1/1 | 0.0 | 1.7x |
| 5x5 | 0.0116 | memetic 1, fallback 0 of 1 | 0.0097 | 1/1 | 0.0 | 1.2x |
| 6x6 | 0.0094 | memetic 1, fallback 0 of 1 | 0.0096 | 1/1 | 0.0 | 1.0x |
| 8x8 | 0.0868 | memetic 1, fallback 0 of 1 | 0.0375 | 1/1 | 0.0 | 2.3x |
| 10x10 | 0.6348 | memetic 1, fallback 0 of 1 | 0.9638 | 1/1 | 2.0 | 0.7x |
| 12x12 | 26.7259 | memetic 1, fallback 0 of 1 | 34.0348 | 1/1 | 53.0 | 0.8x |
| 15x15 | 91.8099 | memetic 0, fallback 1 of 1 | 90.0341 | 0/1 | 150.0 | N/A |
| 16x16 | N/A | memetic 0, fallback 0 of 1 | 23.1774 | 1/1 | 65.0 | N/A |
| 11x17 | 55.8782 | memetic 1, fallback 0 of 1 | 59.9965 | 1/1 | 172.0 | 0.9x |
| 13x17 | 71.6161 | memetic 1, fallback 0 of 1 | 70.4264 | 1/1 | 282.0 | 1.0x |
| 14x14 | 18.0394 | memetic 1, fallback 0 of 1 | 18.8003 | 1/1 | 58.0 | 1.0x |
| 14x17 | 50.6018 | memetic 1, fallback 0 of 1 | 49.2052 | 1/1 | 209.0 | 1.0x |

Grids fully solved by both: 10; memetic mean time lower on 5 of them. Single-trial timings on a loaded machine vary, so treat small differences as ties.

## Memetic local-search diagnostics

Calls are individuals passed to local search; steps are run reassignment attempts; neighbours are scored candidate assignments (incremental down-run evaluations, not full fitness evaluations). Fitness reduction sums the improvement achieved inside local search.

| Grid | Seed | Algorithm | Status | Stop reason | Time (s) | Local-search time (s) | Generations | Restarts | Calls | Steps | Neighbours | Improving moves | Sideways moves | Fitness reduction | Best fitness | Valid |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 4x4 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.0023 | 0.0003 | 0 | 0 | 1 | 2 | 82 | 2 | 0 | 38 | 0 | Yes |
| 4x4 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.0014 | 0.0002 | 0 | 0 | 1 | 2 | 82 | 2 | 0 | 38 | 0 | Yes |
| 5x5 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.0116 | 0.0039 | 0 | 0 | 2 | 38 | 1,349 | 7 | 12 | 52 | 0 | Yes |
| 5x5 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.0097 | 0.0043 | 0 | 0 | 2 | 38 | 1,349 | 7 | 12 | 52 | 0 | Yes |
| 6x6 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.0094 | 0.0013 | 0 | 0 | 1 | 18 | 541 | 6 | 3 | 45 | 0 | Yes |
| 6x6 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.0096 | 0.0013 | 0 | 0 | 1 | 18 | 541 | 6 | 3 | 45 | 0 | Yes |
| 8x8 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.0868 | 0.0172 | 0 | 0 | 2 | 67 | 1,552 | 19 | 13 | 177 | 0 | Yes |
| 8x8 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.0375 | 0.0049 | 0 | 0 | 2 | 67 | 1,552 | 19 | 13 | 177 | 0 | Yes |
| 10x10 | 42 | Memetic algorithm | completed | solved_by_local_search | 0.9638 | 0.8754 | 2 | 0 | 71 | 4,951 | 170,367 | 1,218 | 1,252 | 11,737 | 0 | Yes |
| 10x10 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 0.6348 | 0.5782 | 2 | 0 | 71 | 4,951 | 170,367 | 1,218 | 1,252 | 11,737 | 0 | Yes |
| 12x12 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 26.7259 | 25.4774 | 53 | 0 | 1,196 | 95,062 | 2,839,756 | 22,425 | 24,355 | 199,990 | 0 | Yes |
| 12x12 | 42 | Memetic algorithm | completed | solved_by_local_search | 34.0348 | 32.4559 | 53 | 0 | 1,196 | 95,062 | 2,839,756 | 22,425 | 24,355 | 199,990 | 0 | Yes |
| 15x15 | 42 | Our hybrid algorithm | completed | time_limit | 91.8099 | 82.4622 | 149 | 0 | 3,347 | 225,693 | 7,459,993 | 45,519 | 55,291 | 398,504 | 2 | Yes |
| 15x15 | 42 | Memetic algorithm | completed | time_limit | 90.0341 | 82.4750 | 150 | 0 | 3,373 | 227,535 | 7,519,876 | 45,770 | 55,727 | 400,483 | 2 | No |
| 16x16 | 42 | Our hybrid algorithm | timeout | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| 16x16 | 42 | Memetic algorithm | completed | solved_by_local_search | 23.1774 | 21.7373 | 65 | 0 | 1,440 | 135,954 | 4,269,341 | 34,865 | 33,928 | 306,481 | 0 | Yes |
| 11x17 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 55.8782 | 51.3048 | 172 | 1 | 3,981 | 216,045 | 7,639,364 | 33,831 | 52,867 | 284,429 | 0 | Yes |
| 11x17 | 42 | Memetic algorithm | completed | solved_by_local_search | 59.9965 | 55.1749 | 172 | 1 | 3,981 | 216,045 | 7,639,364 | 33,831 | 52,867 | 284,429 | 0 | Yes |
| 13x17 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 71.6161 | 66.1432 | 282 | 2 | 6,488 | 384,155 | 14,275,177 | 63,777 | 98,027 | 551,897 | 0 | Yes |
| 13x17 | 42 | Memetic algorithm | completed | solved_by_local_search | 70.4264 | 64.7780 | 282 | 2 | 6,488 | 384,155 | 14,275,177 | 63,777 | 98,027 | 551,897 | 0 | Yes |
| 14x14 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 18.0394 | 16.9819 | 58 | 0 | 1,375 | 102,276 | 3,475,724 | 23,245 | 29,246 | 205,822 | 0 | Yes |
| 14x14 | 42 | Memetic algorithm | completed | solved_by_local_search | 18.8003 | 17.6843 | 58 | 0 | 1,375 | 102,276 | 3,475,724 | 23,245 | 29,246 | 205,822 | 0 | Yes |
| 14x17 | 42 | Our hybrid algorithm | completed | solved_by_local_search | 50.6018 | 46.2860 | 209 | 1 | 4,791 | 294,620 | 9,055,445 | 54,436 | 79,740 | 468,023 | 0 | Yes |
| 14x17 | 42 | Memetic algorithm | completed | solved_by_local_search | 49.2052 | 45.0049 | 209 | 1 | 4,791 | 294,620 | 9,055,445 | 54,436 | 79,740 | 468,023 | 0 | Yes |

## Every measured trial

All times are seconds. A completed status includes unsuccessful searches. Pre-fallback fitness and run satisfaction describe the best evolutionary/local-search candidate; final columns describe the returned candidate or solution.

| Grid | Seed | Algorithm | Status | Time | Preprocess | GA time | Fallback time | Evaluations | Generations | Search fitness | Final fitness | Search valid | Final valid | Fallback used | Backtracks | Search runs (%) | Final runs (%) | Solved/white cells | Domain reduction (%) |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| 4x4 | 42 | Basic GA | completed | 0.0160 | 0.0000 | 0.0160 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + domain filtering | completed | 0.0222 | 0.0010 | 0.0211 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + dynamic mutation | completed | 0.0148 | 0.0000 | 0.0148 | 0.0000 | 2,240 | 14 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Our hybrid algorithm | completed | 0.0023 | 0.0014 | 0.0008 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Memetic algorithm | completed | 0.0014 | 0.0008 | 0.0005 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Constraint Search | completed | 0.0026 | 0.0012 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | CP-SAT | completed | 0.0328 | 0.0020 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 9/9 | N/A |
| 4x4 | 42 | RoundingSat | completed | 0.0633 | 0.0031 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 9/9 | N/A |
| 5x5 | 42 | GA + domain filtering | completed | 0.3426 | 0.0063 | 0.3364 | 0.0000 | 31,040 | 194 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | GA + dynamic mutation | completed | 2.4882 | 0.0000 | 2.4881 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 5x5 | 42 | Our hybrid algorithm | completed | 0.0116 | 0.0057 | 0.0058 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | Memetic algorithm | completed | 0.0097 | 0.0036 | 0.0060 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | Constraint Search | completed | 0.0133 | 0.0051 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | CP-SAT | completed | 0.0354 | 0.0024 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 12/12 | N/A |
| 5x5 | 42 | RoundingSat | completed | 0.0753 | 0.0042 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 12/12 | N/A |
| 5x5 | 42 | Basic GA | completed | 2.2231 | 0.0000 | 2.2231 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 6x6 | 42 | GA + dynamic mutation | completed | 0.5251 | 0.0000 | 0.5251 | 0.0000 | 44,320 | 277 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 0.00 |
| 6x6 | 42 | Our hybrid algorithm | completed | 0.0094 | 0.0071 | 0.0023 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | Memetic algorithm | completed | 0.0096 | 0.0073 | 0.0023 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | Constraint Search | completed | 0.0309 | 0.0070 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | CP-SAT | completed | 0.0331 | 0.0011 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 21/21 | N/A |
| 6x6 | 42 | RoundingSat | completed | 0.1292 | 0.0076 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 21/21 | N/A |
| 6x6 | 42 | Basic GA | completed | 4.1002 | 0.0000 | 4.1002 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 80.00 | 80.00 | 0/21 | 0.00 |
| 6x6 | 42 | GA + domain filtering | completed | 0.5406 | 0.0084 | 0.5323 | 0.0000 | 38,720 | 242 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 8x8 | 42 | Our hybrid algorithm | completed | 0.0868 | 0.0601 | 0.0266 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 39/39 | 17.38 |
| 8x8 | 42 | Memetic algorithm | completed | 0.0375 | 0.0305 | 0.0070 | 0.0000 | 0 | 0 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 39/39 | 17.38 |
| 8x8 | 42 | Constraint Search | completed | 0.0879 | 0.0254 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 39/39 | 17.38 |
| 8x8 | 42 | CP-SAT | completed | 0.0737 | 0.0025 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 39/39 | N/A |
| 8x8 | 42 | RoundingSat | completed | 0.1699 | 0.0038 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 39/39 | N/A |
| 8x8 | 42 | Basic GA | completed | 8.4132 | 0.0000 | 8.4132 | 0.0000 | 240,000 | 1,500 | 14 | 14 | No | No | No | 0 | 58.82 | 58.82 | 0/39 | 0.00 |
| 8x8 | 42 | GA + domain filtering | completed | 9.0119 | 0.0224 | 8.9896 | 0.0000 | 240,000 | 1,500 | 4 | 4 | No | No | No | 0 | 82.35 | 82.35 | 0/39 | 17.38 |
| 8x8 | 42 | GA + dynamic mutation | completed | 9.6071 | 0.0000 | 9.6071 | 0.0000 | 240,000 | 1,500 | 12 | 12 | No | No | No | 0 | 52.94 | 52.94 | 0/39 | 0.00 |
| 10x10 | 42 | Memetic algorithm | completed | 0.9638 | 0.0470 | 0.9168 | 0.0000 | 320 | 2 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 67/67 | 6.30 |
| 10x10 | 42 | Constraint Search | completed | 0.3883 | 0.0425 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 1 | N/A | 100.00 | 67/67 | 6.30 |
| 10x10 | 42 | CP-SAT | completed | 0.1476 | 0.0028 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 67/67 | N/A |
| 10x10 | 42 | RoundingSat | completed | 0.2602 | 0.0042 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 67/67 | N/A |
| 10x10 | 42 | Basic GA | completed | 16.7960 | 0.0001 | 16.7960 | 0.0000 | 240,000 | 1,500 | 24 | 24 | No | No | No | 0 | 41.67 | 41.67 | 0/67 | 0.00 |
| 10x10 | 42 | GA + domain filtering | completed | 16.3931 | 0.0343 | 16.3588 | 0.0000 | 240,000 | 1,500 | 33 | 33 | No | No | No | 0 | 45.83 | 45.83 | 0/67 | 6.30 |
| 10x10 | 42 | GA + dynamic mutation | completed | 15.9660 | 0.0000 | 15.9660 | 0.0000 | 240,000 | 1,500 | 36 | 36 | No | No | No | 0 | 54.17 | 54.17 | 0/67 | 0.00 |
| 10x10 | 42 | Our hybrid algorithm | completed | 0.6348 | 0.0293 | 0.6055 | 0.0000 | 320 | 2 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 67/67 | 6.30 |
| 12x12 | 42 | Constraint Search | completed | 1.1268 | 0.0275 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 370 | N/A | 100.00 | 97/97 | 10.19 |
| 12x12 | 42 | CP-SAT | completed | 0.1886 | 0.0025 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 97/97 | N/A |
| 12x12 | 42 | RoundingSat | completed | 0.3178 | 0.0096 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 97/97 | N/A |
| 12x12 | 42 | Basic GA | completed | 23.0101 | 0.0001 | 23.0100 | 0.0000 | 240,000 | 1,500 | 41 | 41 | No | No | No | 0 | 58.82 | 58.82 | 0/97 | 0.00 |
| 12x12 | 42 | GA + domain filtering | completed | 22.8893 | 0.0348 | 22.8545 | 0.0000 | 240,000 | 1,500 | 45 | 45 | No | No | No | 0 | 61.76 | 61.76 | 0/97 | 10.19 |
| 12x12 | 42 | GA + dynamic mutation | completed | 23.5678 | 0.0001 | 23.5677 | 0.0000 | 240,000 | 1,500 | 24 | 24 | No | No | No | 0 | 55.88 | 55.88 | 0/97 | 0.00 |
| 12x12 | 42 | Our hybrid algorithm | completed | 26.7259 | 0.0344 | 26.6915 | 0.0000 | 8,480 | 53 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 97/97 | 10.19 |
| 12x12 | 42 | Memetic algorithm | completed | 34.0348 | 0.0349 | 34.0000 | 0.0000 | 8,480 | 53 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 97/97 | 10.19 |
| 15x15 | 42 | CP-SAT | completed | 18.2286 | 0.0033 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 156/156 | N/A |
| 15x15 | 42 | RoundingSat | completed | 78.4052 | 0.0102 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 156/156 | N/A |
| 15x15 | 42 | Basic GA | completed | 43.1982 | 0.0001 | 43.1980 | 0.0000 | 240,000 | 1,500 | 73 | 73 | No | No | No | 0 | 32.14 | 32.14 | 0/156 | 0.00 |
| 15x15 | 42 | GA + domain filtering | completed | 44.3245 | 0.1170 | 44.2075 | 0.0000 | 240,000 | 1,500 | 122 | 122 | No | No | No | 0 | 46.43 | 46.43 | 0/156 | 17.52 |
| 15x15 | 42 | GA + dynamic mutation | completed | 44.1782 | 0.0001 | 44.1781 | 0.0000 | 240,000 | 1,500 | 54 | 54 | No | No | No | 0 | 42.86 | 42.86 | 0/156 | 0.00 |
| 15x15 | 42 | Our hybrid algorithm | completed | 91.8099 | 0.1114 | 89.9252 | 1.7734 | 23,840 | 149 | 2 | 0 | No | Yes | Yes | 5 | 96.43 | 100.00 | 156/156 | 17.52 |
| 15x15 | 42 | Memetic algorithm | completed | 90.0341 | 0.1001 | 89.9340 | 0.0000 | 24,000 | 150 | 2 | 2 | No | No | No | 0 | 96.43 | 96.43 | 0/156 | 17.52 |
| 15x15 | 42 | Constraint Search | completed | 0.7180 | 0.1031 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 5 | N/A | 100.00 | 156/156 | 17.52 |
| 16x16 | 42 | RoundingSat | completed | 66.1985 | 0.0116 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 181/181 | N/A |
| 16x16 | 42 | Basic GA | completed | 50.0755 | 0.0013 | 50.0742 | 0.0000 | 240,000 | 1,500 | 136 | 136 | No | No | No | 0 | 45.00 | 45.00 | 0/181 | 0.00 |
| 16x16 | 42 | GA + domain filtering | completed | 49.7908 | 0.0832 | 49.7076 | 0.0000 | 240,000 | 1,500 | 78 | 78 | No | No | No | 0 | 66.67 | 66.67 | 0/181 | 9.70 |
| 16x16 | 42 | GA + dynamic mutation | completed | 50.5223 | 0.0010 | 50.5213 | 0.0000 | 240,000 | 1,500 | 82 | 82 | No | No | No | 0 | 50.00 | 50.00 | 0/181 | 0.00 |
| 16x16 | 42 | Our hybrid algorithm | timeout | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| 16x16 | 42 | Memetic algorithm | completed | 23.1774 | 0.0842 | 23.0933 | 0.0000 | 10,400 | 65 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 181/181 | 9.70 |
| 16x16 | 42 | Constraint Search | completed | 30.6627 | 0.0813 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 7,774 | N/A | 100.00 | 181/181 | 9.70 |
| 16x16 | 42 | CP-SAT | completed | 1.1546 | 0.0210 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 181/181 | N/A |
| 11x17 | 42 | Basic GA | completed | 35.7095 | 0.0002 | 35.7093 | 0.0000 | 240,000 | 1,500 | 51 | 51 | No | No | No | 0 | 41.67 | 41.67 | 0/128 | 0.00 |
| 11x17 | 42 | GA + domain filtering | completed | 34.8823 | 0.1303 | 34.7520 | 0.0000 | 240,000 | 1,500 | 93 | 93 | No | No | No | 0 | 56.25 | 56.25 | 0/128 | 16.58 |
| 11x17 | 42 | GA + dynamic mutation | completed | 20.3240 | 0.0001 | 20.3239 | 0.0000 | 240,000 | 1,500 | 48 | 48 | No | No | No | 0 | 39.58 | 39.58 | 0/128 | 0.00 |
| 11x17 | 42 | Our hybrid algorithm | completed | 55.8782 | 0.1248 | 55.7533 | 0.0000 | 27,520 | 172 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 128/128 | 16.58 |
| 11x17 | 42 | Memetic algorithm | completed | 59.9965 | 0.1034 | 59.8931 | 0.0000 | 27,520 | 172 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 128/128 | 16.58 |
| 11x17 | 42 | Constraint Search | completed | 3.7204 | 0.1115 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 995 | N/A | 100.00 | 128/128 | 16.58 |
| 11x17 | 42 | CP-SAT | completed | 1.1867 | 0.0037 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 128/128 | N/A |
| 11x17 | 42 | RoundingSat | completed | 2.5204 | 0.0082 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 128/128 | N/A |
| 13x17 | 42 | GA + domain filtering | completed | 18.2140 | 0.1166 | 18.0974 | 0.0000 | 240,000 | 1,500 | 79 | 79 | No | No | No | 0 | 57.41 | 57.41 | 0/152 | 17.91 |
| 13x17 | 42 | GA + dynamic mutation | completed | 25.4500 | 0.0003 | 25.4497 | 0.0000 | 240,000 | 1,500 | 52 | 52 | No | No | No | 0 | 40.74 | 40.74 | 0/152 | 0.00 |
| 13x17 | 42 | Our hybrid algorithm | completed | 71.6161 | 0.1056 | 71.5105 | 0.0000 | 45,120 | 282 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 152/152 | 17.91 |
| 13x17 | 42 | Memetic algorithm | completed | 70.4264 | 0.1449 | 70.2815 | 0.0000 | 45,120 | 282 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 152/152 | 17.91 |
| 13x17 | 42 | Constraint Search | completed | 36.6791 | 0.1568 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 11,139 | N/A | 100.00 | 152/152 | 17.91 |
| 13x17 | 42 | CP-SAT | completed | 0.7142 | 0.0083 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 152/152 | N/A |
| 13x17 | 42 | RoundingSat | completed | 42.0738 | 0.0061 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 152/152 | N/A |
| 13x17 | 42 | Basic GA | completed | 18.5154 | 0.0001 | 18.5153 | 0.0000 | 240,000 | 1,500 | 87 | 87 | No | No | No | 0 | 35.19 | 35.19 | 0/152 | 0.00 |
| 14x14 | 42 | GA + dynamic mutation | completed | 15.9362 | 0.0002 | 15.9360 | 0.0000 | 240,000 | 1,500 | 48 | 48 | No | No | No | 0 | 54.17 | 54.17 | 0/137 | 0.00 |
| 14x14 | 42 | Our hybrid algorithm | completed | 18.0394 | 0.1061 | 17.9333 | 0.0000 | 9,280 | 58 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 137/137 | 12.25 |
| 14x14 | 42 | Memetic algorithm | completed | 18.8003 | 0.0768 | 18.7234 | 0.0000 | 9,280 | 58 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 137/137 | 12.25 |
| 14x14 | 42 | Constraint Search | completed | 1.3665 | 0.1058 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 72 | N/A | 100.00 | 137/137 | 12.25 |
| 14x14 | 42 | CP-SAT | completed | 0.2191 | 0.0050 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 137/137 | N/A |
| 14x14 | 42 | RoundingSat | completed | 2.1062 | 0.0101 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 137/137 | N/A |
| 14x14 | 42 | Basic GA | completed | 16.2640 | 0.0001 | 16.2639 | 0.0000 | 240,000 | 1,500 | 90 | 90 | No | No | No | 0 | 39.58 | 39.58 | 0/137 | 0.00 |
| 14x14 | 42 | GA + domain filtering | completed | 16.9421 | 0.0730 | 16.8691 | 0.0000 | 240,000 | 1,500 | 69 | 69 | No | No | No | 0 | 52.08 | 52.08 | 0/137 | 12.25 |
| 14x17 | 42 | Our hybrid algorithm | completed | 50.6018 | 0.1424 | 50.4594 | 0.0000 | 33,440 | 209 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 164/164 | 14.36 |
| 14x17 | 42 | Memetic algorithm | completed | 49.2052 | 0.1730 | 49.0322 | 0.0000 | 33,440 | 209 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 164/164 | 14.36 |
| 14x17 | 42 | Constraint Search | completed | 0.9250 | 0.1165 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 3 | N/A | 100.00 | 164/164 | 14.36 |
| 14x17 | 42 | CP-SAT | completed | 5.4347 | 0.0040 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 164/164 | N/A |
| 14x17 | 42 | RoundingSat | completed | 37.6916 | 0.0069 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 164/164 | N/A |
| 14x17 | 42 | Basic GA | completed | 18.5840 | 0.0001 | 18.5838 | 0.0000 | 240,000 | 1,500 | 87 | 87 | No | No | No | 0 | 44.64 | 44.64 | 0/164 | 0.00 |
| 14x17 | 42 | GA + domain filtering | completed | 18.8330 | 0.1165 | 18.7166 | 0.0000 | 240,000 | 1,500 | 120 | 120 | No | No | No | 0 | 62.50 | 62.50 | 0/164 | 14.36 |
| 14x17 | 42 | GA + dynamic mutation | completed | 19.1507 | 0.0001 | 19.1505 | 0.0000 | 240,000 | 1,500 | 71 | 71 | No | No | No | 0 | 41.07 | 41.07 | 0/164 | 0.00 |

## Findings and interpretation

Observed complete-solution counts: Basic GA 1/12; GA + domain filtering 3/12; GA + dynamic mutation 2/12; Our hybrid algorithm 11/12; Memetic algorithm 11/12; Constraint Search 12/12; CP-SAT 12/12; RoundingSat 12/12.

Our memetic phase solved 10 of 12 attempted trials; the exact fallback supplied 1 additional valid solutions. These two contributions must be distinguished when judging the hybrid's complete-solution rate.

Completed population searches exhausting the generation budget without a search-stage solution: Basic GA: 11; GA + domain filtering: 9; GA + dynamic mutation: 10; Our hybrid algorithm: 0; Memetic algorithm: 0.

Domain filtering versus Basic GA isolates the tested preprocessing change; dynamic mutation versus Basic GA isolates the tested mutation schedule. Our algorithm changes several mechanisms together, so its difference cannot be attributed to domain filtering or adaptive mutation alone.

Our hybrid performs exact search after its bounded memetic phase fails. Its final validity and total runtime include this work; its pre-fallback fitness, memetic-stage validity, and separately reported fallback time show the contribution of each stage.

The memetic algorithm solved 11 of 12 attempted trials with no exact fallback. Its fitness-evaluation count covers whole-population evaluations only; local-search neighbour scoring is reported separately and its time is included in the GA and total times.

Standalone memetic versus our hybrid compares the shared memetic search with and without exact backtracking fallback. Both receive the same memetic time budget in this study.

Constraint Search directly applies propagation and exact backtracking without a preceding GA phase.

CP-SAT solves a declarative sum/AllDifferent model with one search worker and no supplied solution hints.

RoundingSat solves the encoded pseudo-Boolean constraints directly, without a supplied solution witness or hybrid GA phase. Its native decisions and conflicts measure different operations from the hybrid's fitness evaluations and failed backtracking branches. This comparison measures these complete implementations on the recorded instances; it does not isolate a single algorithmic improvement or programming-language effect.

Exact solvers are not subject to the GA-generation limit; the recorded time limit applies instead.

Do not infer a speedup from an unsolved algorithm stopping sooner. Compare time to a valid solution only on paired instances that both algorithms solve. Constraint satisfaction and residual fitness help describe failed searches, but cannot replace full solution validity.

With one seed per size, these results are descriptive observations, not statistical proof of superiority. Increasing to five seeds supplies repeated observations but still requires reporting variability and failed trials. Grid size, clue tightness, run structure, and white-cell count all affect difficulty. These regular generated puzzles are not a calibrated human difficulty dataset.

Solutions are not guaranteed unique. Comparing digits to the generator's hidden witness would incorrectly label other valid solutions as wrong, so this study reports constraint validity rather than witness-based cell accuracy. Machine load and Python implementation also affect wall-clock measurements.
