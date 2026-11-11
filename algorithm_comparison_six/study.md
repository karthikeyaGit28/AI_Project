# Kakuro: six-algorithm evaluation study

Recorded trials: 72 of 72 planned. Seeds: 42. Population: 160. GA generation limit: 1,500. Maximum population fitness evaluations per GA: 240,000.

Grid sizes count the complete board, including clue borders and internal blocks. For each size and seed, all selected algorithms receive the same puzzle; a puzzle hash is recorded for checking this pairing. Each trial runs sequentially in a fresh Python process. The synthetic generator creates solvable instances but does not guarantee uniqueness.

Per-trial wall-clock limit: 120 seconds. A timeout means the configured limit was reached, not that the puzzle is unsatisfiable. Completed unsuccessful searches retain their best candidate and measured metrics.

## Algorithm definitions

| Algorithm | Domains | Search mechanism | Restarts / exact fallback |
|---|---|---|---|
| Basic GA | Digits 1 through 9 for every cell | Uniform cell crossover; fixed 0.25 probability of mutating one randomly selected cell | Neither |
| GA + domain filtering | Iterative clue-based constraint propagation before GA | Same crossover and fixed mutation as Basic GA | Neither |
| GA + dynamic mutation | Digits 1 through 9; no domain filtering | Same crossover as Basic GA; mutation rises from 0.25 toward 0.90 with stagnation | Neither |
| Our hybrid algorithm | Iterative propagation and domain-indexed genes | Valid across-run sampling, run-based crossover, conflict-focused mutation with adaptive probability | Restart after 100 stagnant generations; exact backtracking if GA fails |
| Constraint Search | Digits 1-9 narrowed by iterative run propagation | Standalone minimum-remaining-values (MRV) backtracking with propagation after decisions | No GA; the constraint search runs directly |
| CP-SAT | One integer variable with domain 1-9 per white cell | OR-Tools CP-SAT; each run has an exact-sum constraint and AllDifferent | No GA or custom fallback; one search worker, recorded random seed |

The three baselines share top-third parent selection and at most eight elites (`min(8, population_size // 10)`). Mutation replaces one selected cell's value with a different allowed digit when one is available. Filtering and dynamic mutation are independent additions to Basic GA, not cumulative variants. Adaptive probability is `min(0.90, 0.25 + 0.65 * stagnant_generations / 100)`.

## Metric definitions

- **Valid solution:** every white cell has a digit 1-9, and every across/down run has the required sum and no repeated digit. An independent validator checks this.
- **Fitness (lower is better):** sum over all runs of `abs(actual_sum - clue_sum) + 9 * (run_length - distinct_digits)`. Zero is a complete valid solution. Our GA preserves across constraints, so its down-only search score equals this common all-run score.
- **Satisfied runs (%):** percentage of runs meeting both the exact sum and no-repeat requirements. This is partial constraint satisfaction, not puzzle validity or cell accuracy.
- **Execution time:** preprocessing/model construction plus the applicable GA, constraint, or CP-SAT search, including any hybrid fallback. It excludes puzzle generation, parsing, final output validation, file I/O, library import, and process startup. CP-SAT model construction is included; its library import is not.
- **Fitness evaluations:** evaluated population members. Auxiliary conflict checks and constraint-propagation work are not included in this count. This metric is N/A for Constraint Search and CP-SAT, which do not use a GA.
- **Backtracks:** failed branches in Python constraint search or the hybrid's exact fallback. Zero can also occur when exact search succeeds without rejecting a branch. CP-SAT does not expose an equivalent count here, so its backtracks are N/A.
- **Branches and CP-SAT conflicts:** native search diagnostics reported separately. A CP-SAT conflict is not a Python backtrack. Constraint Search counts attempted cell-value assignments; CP-SAT counts its internal search branches. These are diagnostic counts, not directly interchangeable units of effort.
- **Solved white cells:** the complete white-cell count only when the whole solution validates; an unsolved full candidate is not counted as a partially correct solution.

Averages include all completed trials, including unsolved GA runs. Timeouts/errors remain in the attempted-trial denominator but are excluded from numerical means. Missing measurements are shown as N/A. Means of run satisfaction give each trial equal weight.

Exact-solver statuses distinguish a found solution from a proof of infeasibility and an inconclusive limit. CP-SAT FEASIBLE/OPTIMAL indicate a valid solution, INFEASIBLE indicates proved infeasibility, UNKNOWN indicates no conclusion within the limit, and MODEL_INVALID indicates a model error. Constraint Search uses SOLVED, INFEASIBLE, or UNKNOWN. This is a feasibility model with no optimization objective: CP-SAT OPTIMAL does not establish solution uniqueness or human difficulty.

## Aggregate results

| Algorithm | Valid / trials | GA-only valid | Fallback valid | Completed | Mean time (s) | Mean evaluations | Mean GA runs satisfied (%) | Mean final runs satisfied (%) | Total backtracks | Branches | CP-SAT conflicts | Timeouts / errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Basic GA | 1 / 12 | 1 | 0 | 12 | 12.4450 | 220,200.00 | 54.38 | 54.38 | 0 | N/A | N/A | 0 / 0 |
| GA + domain filtering | 3 / 12 | 3 | 0 | 12 | 12.3503 | 186,013.33 | 69.27 | 69.27 | 0 | N/A | N/A | 0 / 0 |
| GA + dynamic mutation | 2 / 12 | 2 | 0 | 12 | 12.4991 | 203,880.00 | 58.87 | 58.87 | 0 | N/A | N/A | 0 / 0 |
| Our hybrid algorithm | 12 / 12 | 3 | 9 | 12 | 35.9379 | 181,013.33 | 80.66 | 100.00 | 20,359 | N/A | N/A | 0 / 0 |
| Constraint Search | 12 / 12 | N/A | N/A | 12 | 7.4852 | N/A | N/A | 100.00 | 20,359 | 20,940 | N/A | 0 / 0 |
| CP-SAT | 12 / 12 | N/A | N/A | 12 | 1.0631 | N/A | N/A | 100.00 | N/A | 797,388 | 182,537 | 0 / 0 |

## Per-grid execution time and validity

Each entry is **mean seconds; valid/attempted trials**. With one seed it is the actual single-run measurement. An unsuccessful GA run's elapsed time is a budget-exhaustion time, not a time to solve. For exact solvers, the status distinguishes infeasibility from an inconclusive limit.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm | Constraint Search | CP-SAT |
|---|---:|---:|---:|---:|---:|---:|
| 4x4 | 0.0095; 1/1 | 0.0100; 1/1 | 0.0097; 1/1 | 0.0027; 1/1 | 0.0012; 1/1 | 0.0264; 1/1 |
| 5x5 | 1.1433; 0/1 | 0.1545; 1/1 | 1.2499; 0/1 | 0.0069; 1/1 | 0.0064; 1/1 | 0.0151; 1/1 |
| 6x6 | 1.6313; 0/1 | 0.2670; 1/1 | 0.3154; 1/1 | 0.1367; 1/1 | 0.0185; 1/1 | 0.0273; 1/1 |
| 8x8 | 2.6885; 0/1 | 2.7336; 0/1 | 2.8381; 0/1 | 10.5318; 1/1 | 0.0548; 1/1 | 0.0402; 1/1 |
| 10x10 | 7.7012; 0/1 | 6.9095; 0/1 | 7.3705; 0/1 | 18.8211; 1/1 | 0.1805; 1/1 | 0.0720; 1/1 |
| 12x12 | 11.6284; 0/1 | 11.6267; 0/1 | 11.4191; 0/1 | 27.0578; 1/1 | 0.8329; 1/1 | 0.0887; 1/1 |
| 15x15 | 25.0045; 0/1 | 21.3112; 0/1 | 21.7212; 0/1 | 46.7556; 1/1 | 0.3917; 1/1 | 6.7318; 1/1 |
| 16x16 | 25.2271; 0/1 | 24.7702; 0/1 | 25.0976; 0/1 | 94.5487; 1/1 | 36.9786; 1/1 | 0.5310; 1/1 |
| 11x17 | 15.8856; 0/1 | 17.1111; 0/1 | 16.8567; 0/1 | 41.3192; 1/1 | 1.8879; 1/1 | 0.6147; 1/1 |
| 13x17 | 20.4371; 0/1 | 20.9954; 0/1 | 21.3997; 0/1 | 98.5864; 1/1 | 48.2886; 1/1 | 0.3439; 1/1 |
| 14x14 | 18.4179; 0/1 | 19.3140; 0/1 | 18.9366; 0/1 | 42.9300; 1/1 | 0.6769; 1/1 | 0.1469; 1/1 |
| 14x17 | 19.5660; 0/1 | 23.0003; 0/1 | 22.7752; 0/1 | 50.5576; 1/1 | 0.5042; 1/1 | 4.1197; 1/1 |

## Per-grid best GA fitness before fallback

Lower is better; zero means the GA phase solved the puzzle. These values are the best candidate encountered within the GA budget, including candidates retained across restarts. Our fallback cannot improve the values in this table. Multiple seeds are averaged.

Constraint Search and CP-SAT have no GA phase; they are omitted from this table.

| Grid | Basic GA | GA + domain filtering | GA + dynamic mutation | Our hybrid algorithm |
|---|---:|---:|---:|---:|
| 4x4 | 0.00 | 0.00 | 0.00 | 0.00 |
| 5x5 | 2.00 | 0.00 | 2.00 | 0.00 |
| 6x6 | 2.00 | 0.00 | 0.00 | 0.00 |
| 8x8 | 14.00 | 4.00 | 12.00 | 2.00 |
| 10x10 | 24.00 | 33.00 | 36.00 | 10.00 |
| 12x12 | 41.00 | 45.00 | 24.00 | 33.00 |
| 15x15 | 73.00 | 122.00 | 54.00 | 47.00 |
| 16x16 | 136.00 | 78.00 | 82.00 | 98.00 |
| 11x17 | 51.00 | 93.00 | 48.00 | 48.00 |
| 13x17 | 87.00 | 79.00 | 52.00 | 52.00 |
| 14x14 | 90.00 | 69.00 | 48.00 | 55.00 |
| 14x17 | 87.00 | 120.00 | 71.00 | 70.00 |

## Standalone exact-solver diagnostics

Times include model/preprocessing and search. CP-SAT conflicts and Python failed backtracking branches are different diagnostics; neither is substituted for the other. GA evaluations and generations are N/A for these algorithms.

| Grid | Seed | Algorithm | Trial status | Solver status | Total (s) | Model / preprocess (s) | Search (s) | Branches | Backtracks | CP-SAT conflicts | Valid | Solved / white cells |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 4x4 | 42 | Constraint Search | completed | SOLVED | 0.001236 | 0.000485 | 0.000751 | 4 | 0 | N/A | Yes | 9 / 9 |
| 4x4 | 42 | CP-SAT | completed | OPTIMAL | 0.026433 | 0.001759 | 0.024674 | 797 | N/A | 0 | Yes | 9 / 9 |
| 5x5 | 42 | Constraint Search | completed | SOLVED | 0.006380 | 0.002823 | 0.003557 | 4 | 0 | N/A | Yes | 12 / 12 |
| 5x5 | 42 | CP-SAT | completed | OPTIMAL | 0.015108 | 0.000734 | 0.014374 | 621 | N/A | 4 | Yes | 12 / 12 |
| 6x6 | 42 | Constraint Search | completed | SOLVED | 0.018455 | 0.004831 | 0.013624 | 8 | 0 | N/A | Yes | 21 / 21 |
| 6x6 | 42 | CP-SAT | completed | OPTIMAL | 0.027278 | 0.000810 | 0.026468 | 1,727 | N/A | 6 | Yes | 21 / 21 |
| 8x8 | 42 | Constraint Search | completed | SOLVED | 0.054781 | 0.013544 | 0.041237 | 15 | 0 | N/A | Yes | 39 / 39 |
| 8x8 | 42 | CP-SAT | completed | OPTIMAL | 0.040184 | 0.000946 | 0.039238 | 2,892 | N/A | 1 | Yes | 39 / 39 |
| 10x10 | 42 | Constraint Search | completed | SOLVED | 0.180550 | 0.016477 | 0.164073 | 40 | 1 | N/A | Yes | 67 / 67 |
| 10x10 | 42 | CP-SAT | completed | OPTIMAL | 0.071958 | 0.001185 | 0.070774 | 6,129 | N/A | 84 | Yes | 67 / 67 |
| 12x12 | 42 | CP-SAT | completed | OPTIMAL | 0.088712 | 0.001420 | 0.087292 | 8,722 | N/A | 83 | Yes | 97 / 97 |
| 12x12 | 42 | Constraint Search | completed | SOLVED | 0.832864 | 0.024729 | 0.808135 | 423 | 370 | N/A | Yes | 97 / 97 |
| 15x15 | 42 | Constraint Search | completed | SOLVED | 0.391657 | 0.057623 | 0.334034 | 73 | 5 | N/A | Yes | 156 / 156 |
| 15x15 | 42 | CP-SAT | completed | OPTIMAL | 6.731841 | 0.010576 | 6.721265 | 401,043 | N/A | 96,112 | Yes | 156 / 156 |
| 16x16 | 42 | Constraint Search | completed | SOLVED | 36.978578 | 0.047720 | 36.930859 | 7,872 | 7,774 | N/A | Yes | 181 / 181 |
| 16x16 | 42 | CP-SAT | completed | OPTIMAL | 0.531002 | 0.002123 | 0.528879 | 55,189 | N/A | 8,301 | Yes | 181 / 181 |
| 11x17 | 42 | Constraint Search | completed | SOLVED | 1.887899 | 0.049707 | 1.838193 | 1,057 | 995 | N/A | Yes | 128 / 128 |
| 11x17 | 42 | CP-SAT | completed | OPTIMAL | 0.614710 | 0.001727 | 0.612983 | 57,851 | N/A | 17,473 | Yes | 128 / 128 |
| 13x17 | 42 | Constraint Search | completed | SOLVED | 48.288605 | 0.059499 | 48.229106 | 11,214 | 11,139 | N/A | Yes | 152 / 152 |
| 13x17 | 42 | CP-SAT | completed | OPTIMAL | 0.343941 | 0.001872 | 0.342069 | 37,392 | N/A | 5,688 | Yes | 152 / 152 |
| 14x14 | 42 | Constraint Search | completed | SOLVED | 0.676871 | 0.040622 | 0.636248 | 147 | 72 | N/A | Yes | 137 / 137 |
| 14x14 | 42 | CP-SAT | completed | OPTIMAL | 0.146915 | 0.002060 | 0.144855 | 12,930 | N/A | 401 | Yes | 137 / 137 |
| 14x17 | 42 | CP-SAT | completed | OPTIMAL | 4.119675 | 0.001994 | 4.117681 | 212,095 | N/A | 54,384 | Yes | 164 / 164 |
| 14x17 | 42 | Constraint Search | completed | SOLVED | 0.504201 | 0.060236 | 0.443966 | 83 | 3 | N/A | Yes | 164 / 164 |

## Every measured trial

All times are seconds. A completed status includes unsuccessful searches. GA fitness and GA run satisfaction describe the best pre-fallback candidate; final columns describe the returned candidate or solution.

| Grid | Seed | Algorithm | Status | Time | Preprocess | GA time | Fallback time | Evaluations | Generations | GA fitness | Final fitness | GA valid | Final valid | Fallback used | Backtracks | GA runs (%) | Final runs (%) | Solved/white cells | Domain reduction (%) |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| 4x4 | 42 | Basic GA | completed | 0.0095 | 0.0000 | 0.0095 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + domain filtering | completed | 0.0100 | 0.0005 | 0.0095 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + dynamic mutation | completed | 0.0097 | 0.0000 | 0.0096 | 0.0000 | 2,240 | 14 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Our hybrid algorithm | completed | 0.0027 | 0.0005 | 0.0022 | 0.0000 | 320 | 2 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Constraint Search | completed | 0.0012 | 0.0005 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | CP-SAT | completed | 0.0264 | 0.0018 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 9/9 | N/A |
| 5x5 | 42 | GA + domain filtering | completed | 0.1545 | 0.0029 | 0.1516 | 0.0000 | 31,040 | 194 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | GA + dynamic mutation | completed | 1.2499 | 0.0000 | 1.2499 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 5x5 | 42 | Our hybrid algorithm | completed | 0.0069 | 0.0020 | 0.0049 | 0.0000 | 480 | 3 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | Constraint Search | completed | 0.0064 | 0.0028 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | CP-SAT | completed | 0.0151 | 0.0007 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 12/12 | N/A |
| 5x5 | 42 | Basic GA | completed | 1.1433 | 0.0000 | 1.1433 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 6x6 | 42 | GA + dynamic mutation | completed | 0.3154 | 0.0000 | 0.3154 | 0.0000 | 44,320 | 277 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 0.00 |
| 6x6 | 42 | Our hybrid algorithm | completed | 0.1367 | 0.0050 | 0.1317 | 0.0000 | 11,360 | 71 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | Constraint Search | completed | 0.0185 | 0.0048 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | CP-SAT | completed | 0.0273 | 0.0008 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 21/21 | N/A |
| 6x6 | 42 | Basic GA | completed | 1.6313 | 0.0000 | 1.6313 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 80.00 | 80.00 | 0/21 | 0.00 |
| 6x6 | 42 | GA + domain filtering | completed | 0.2670 | 0.0057 | 0.2613 | 0.0000 | 38,720 | 242 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 8x8 | 42 | Our hybrid algorithm | completed | 10.5318 | 0.0135 | 10.3941 | 0.1242 | 240,000 | 1,500 | 2 | 0 | No | Yes | Yes | 0 | 88.24 | 100.00 | 39/39 | 17.38 |
| 8x8 | 42 | Constraint Search | completed | 0.0548 | 0.0135 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 0 | N/A | 100.00 | 39/39 | 17.38 |
| 8x8 | 42 | CP-SAT | completed | 0.0402 | 0.0009 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 39/39 | N/A |
| 8x8 | 42 | Basic GA | completed | 2.6885 | 0.0000 | 2.6884 | 0.0000 | 240,000 | 1,500 | 14 | 14 | No | No | No | 0 | 58.82 | 58.82 | 0/39 | 0.00 |
| 8x8 | 42 | GA + domain filtering | completed | 2.7336 | 0.0139 | 2.7197 | 0.0000 | 240,000 | 1,500 | 4 | 4 | No | No | No | 0 | 82.35 | 82.35 | 0/39 | 17.38 |
| 8x8 | 42 | GA + dynamic mutation | completed | 2.8381 | 0.0000 | 2.8380 | 0.0000 | 240,000 | 1,500 | 12 | 12 | No | No | No | 0 | 52.94 | 52.94 | 0/39 | 0.00 |
| 10x10 | 42 | Constraint Search | completed | 0.1805 | 0.0165 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 1 | N/A | 100.00 | 67/67 | 6.30 |
| 10x10 | 42 | CP-SAT | completed | 0.0720 | 0.0012 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 67/67 | N/A |
| 10x10 | 42 | Basic GA | completed | 7.7012 | 0.0001 | 7.7011 | 0.0000 | 240,000 | 1,500 | 24 | 24 | No | No | No | 0 | 41.67 | 41.67 | 0/67 | 0.00 |
| 10x10 | 42 | GA + domain filtering | completed | 6.9095 | 0.0163 | 6.8933 | 0.0000 | 240,000 | 1,500 | 33 | 33 | No | No | No | 0 | 45.83 | 45.83 | 0/67 | 6.30 |
| 10x10 | 42 | GA + dynamic mutation | completed | 7.3705 | 0.0001 | 7.3704 | 0.0000 | 240,000 | 1,500 | 36 | 36 | No | No | No | 0 | 54.17 | 54.17 | 0/67 | 0.00 |
| 10x10 | 42 | Our hybrid algorithm | completed | 18.8211 | 0.0160 | 18.2902 | 0.5150 | 240,000 | 1,500 | 10 | 0 | No | Yes | Yes | 1 | 70.83 | 100.00 | 67/67 | 6.30 |
| 12x12 | 42 | CP-SAT | completed | 0.0887 | 0.0014 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 97/97 | N/A |
| 12x12 | 42 | Basic GA | completed | 11.6284 | 0.0000 | 11.6283 | 0.0000 | 240,000 | 1,500 | 41 | 41 | No | No | No | 0 | 58.82 | 58.82 | 0/97 | 0.00 |
| 12x12 | 42 | GA + domain filtering | completed | 11.6267 | 0.0191 | 11.6076 | 0.0000 | 240,000 | 1,500 | 45 | 45 | No | No | No | 0 | 61.76 | 61.76 | 0/97 | 10.19 |
| 12x12 | 42 | GA + dynamic mutation | completed | 11.4191 | 0.0001 | 11.4190 | 0.0000 | 240,000 | 1,500 | 24 | 24 | No | No | No | 0 | 55.88 | 55.88 | 0/97 | 0.00 |
| 12x12 | 42 | Our hybrid algorithm | completed | 27.0578 | 0.0290 | 25.6085 | 1.4203 | 240,000 | 1,500 | 33 | 0 | No | Yes | Yes | 370 | 76.47 | 100.00 | 97/97 | 10.19 |
| 12x12 | 42 | Constraint Search | completed | 0.8329 | 0.0247 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 370 | N/A | 100.00 | 97/97 | 10.19 |
| 15x15 | 42 | Basic GA | completed | 25.0045 | 0.0002 | 25.0042 | 0.0000 | 240,000 | 1,500 | 73 | 73 | No | No | No | 0 | 32.14 | 32.14 | 0/156 | 0.00 |
| 15x15 | 42 | GA + domain filtering | completed | 21.3112 | 0.0573 | 21.2539 | 0.0000 | 240,000 | 1,500 | 122 | 122 | No | No | No | 0 | 46.43 | 46.43 | 0/156 | 17.52 |
| 15x15 | 42 | GA + dynamic mutation | completed | 21.7212 | 0.0001 | 21.7211 | 0.0000 | 240,000 | 1,500 | 54 | 54 | No | No | No | 0 | 42.86 | 42.86 | 0/156 | 0.00 |
| 15x15 | 42 | Our hybrid algorithm | completed | 46.7556 | 0.0584 | 45.6889 | 1.0083 | 240,000 | 1,500 | 47 | 0 | No | Yes | Yes | 5 | 76.79 | 100.00 | 156/156 | 17.52 |
| 15x15 | 42 | Constraint Search | completed | 0.3917 | 0.0576 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 5 | N/A | 100.00 | 156/156 | 17.52 |
| 15x15 | 42 | CP-SAT | completed | 6.7318 | 0.0106 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 156/156 | N/A |
| 16x16 | 42 | GA + domain filtering | completed | 24.7702 | 0.0464 | 24.7238 | 0.0000 | 240,000 | 1,500 | 78 | 78 | No | No | No | 0 | 66.67 | 66.67 | 0/181 | 9.70 |
| 16x16 | 42 | Our hybrid algorithm | completed | 94.5487 | 0.0638 | 53.5934 | 40.8916 | 240,000 | 1,500 | 98 | 0 | No | Yes | Yes | 7,774 | 66.67 | 100.00 | 181/181 | 9.70 |
| 16x16 | 42 | Constraint Search | completed | 36.9786 | 0.0477 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 7,774 | N/A | 100.00 | 181/181 | 9.70 |
| 16x16 | 42 | CP-SAT | completed | 0.5310 | 0.0021 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 181/181 | N/A |
| 16x16 | 42 | Basic GA | completed | 25.2271 | 0.0001 | 25.2270 | 0.0000 | 240,000 | 1,500 | 136 | 136 | No | No | No | 0 | 45.00 | 45.00 | 0/181 | 0.00 |
| 11x17 | 42 | GA + dynamic mutation | completed | 16.8567 | 0.0001 | 16.8566 | 0.0000 | 240,000 | 1,500 | 48 | 48 | No | No | No | 0 | 39.58 | 39.58 | 0/128 | 0.00 |
| 11x17 | 42 | Our hybrid algorithm | completed | 41.3192 | 0.0503 | 35.7504 | 5.5186 | 240,000 | 1,500 | 48 | 0 | No | Yes | Yes | 995 | 68.75 | 100.00 | 128/128 | 16.58 |
| 11x17 | 42 | Constraint Search | completed | 1.8879 | 0.0497 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 995 | N/A | 100.00 | 128/128 | 16.58 |
| 11x17 | 42 | CP-SAT | completed | 0.6147 | 0.0017 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 128/128 | N/A |
| 11x17 | 42 | Basic GA | completed | 15.8856 | 0.0001 | 15.8856 | 0.0000 | 240,000 | 1,500 | 51 | 51 | No | No | No | 0 | 41.67 | 41.67 | 0/128 | 0.00 |
| 11x17 | 42 | GA + domain filtering | completed | 17.1111 | 0.0498 | 17.0613 | 0.0000 | 240,000 | 1,500 | 93 | 93 | No | No | No | 0 | 56.25 | 56.25 | 0/128 | 16.58 |
| 13x17 | 42 | Our hybrid algorithm | completed | 98.5864 | 0.0674 | 45.9806 | 52.5383 | 240,000 | 1,500 | 52 | 0 | No | Yes | Yes | 11,139 | 74.07 | 100.00 | 152/152 | 17.91 |
| 13x17 | 42 | Constraint Search | completed | 48.2886 | 0.0595 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 11,139 | N/A | 100.00 | 152/152 | 17.91 |
| 13x17 | 42 | CP-SAT | completed | 0.3439 | 0.0019 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 152/152 | N/A |
| 13x17 | 42 | Basic GA | completed | 20.4371 | 0.0001 | 20.4370 | 0.0000 | 240,000 | 1,500 | 87 | 87 | No | No | No | 0 | 35.19 | 35.19 | 0/152 | 0.00 |
| 13x17 | 42 | GA + domain filtering | completed | 20.9954 | 0.0568 | 20.9386 | 0.0000 | 240,000 | 1,500 | 79 | 79 | No | No | No | 0 | 57.41 | 57.41 | 0/152 | 17.91 |
| 13x17 | 42 | GA + dynamic mutation | completed | 21.3997 | 0.0001 | 21.3997 | 0.0000 | 240,000 | 1,500 | 52 | 52 | No | No | No | 0 | 40.74 | 40.74 | 0/152 | 0.00 |
| 14x14 | 42 | Constraint Search | completed | 0.6769 | 0.0406 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 72 | N/A | 100.00 | 137/137 | 12.25 |
| 14x14 | 42 | CP-SAT | completed | 0.1469 | 0.0021 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 137/137 | N/A |
| 14x14 | 42 | Basic GA | completed | 18.4179 | 0.0001 | 18.4178 | 0.0000 | 240,000 | 1,500 | 90 | 90 | No | No | No | 0 | 39.58 | 39.58 | 0/137 | 0.00 |
| 14x14 | 42 | GA + domain filtering | completed | 19.3140 | 0.0404 | 19.2736 | 0.0000 | 240,000 | 1,500 | 69 | 69 | No | No | No | 0 | 52.08 | 52.08 | 0/137 | 12.25 |
| 14x14 | 42 | GA + dynamic mutation | completed | 18.9366 | 0.0001 | 18.9365 | 0.0000 | 240,000 | 1,500 | 48 | 48 | No | No | No | 0 | 54.17 | 54.17 | 0/137 | 0.00 |
| 14x14 | 42 | Our hybrid algorithm | completed | 42.9300 | 0.0406 | 41.2207 | 1.6687 | 240,000 | 1,500 | 55 | 0 | No | Yes | Yes | 72 | 72.92 | 100.00 | 137/137 | 12.25 |
| 14x17 | 42 | CP-SAT | completed | 4.1197 | 0.0020 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 164/164 | N/A |
| 14x17 | 42 | Basic GA | completed | 19.5660 | 0.0002 | 19.5658 | 0.0000 | 240,000 | 1,500 | 87 | 87 | No | No | No | 0 | 44.64 | 44.64 | 0/164 | 0.00 |
| 14x17 | 42 | GA + domain filtering | completed | 23.0003 | 0.0644 | 22.9359 | 0.0000 | 240,000 | 1,500 | 120 | 120 | No | No | No | 0 | 62.50 | 62.50 | 0/164 | 14.36 |
| 14x17 | 42 | GA + dynamic mutation | completed | 22.7752 | 0.0001 | 22.7751 | 0.0000 | 240,000 | 1,500 | 71 | 71 | No | No | No | 0 | 41.07 | 41.07 | 0/164 | 0.00 |
| 14x17 | 42 | Our hybrid algorithm | completed | 50.5576 | 0.0591 | 49.3058 | 1.1927 | 240,000 | 1,500 | 70 | 0 | No | Yes | Yes | 3 | 73.21 | 100.00 | 164/164 | 14.36 |
| 14x17 | 42 | Constraint Search | completed | 0.5042 | 0.0602 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | 3 | N/A | 100.00 | 164/164 | 14.36 |
| 16x16 | 42 | GA + dynamic mutation | completed | 25.0976 | 0.0001 | 25.0975 | 0.0000 | 240,000 | 1,500 | 82 | 82 | No | No | No | 0 | 50.00 | 50.00 | 0/181 | 0.00 |

## Findings and interpretation

Observed complete-solution counts: Basic GA 1/12; GA + domain filtering 3/12; GA + dynamic mutation 2/12; Our hybrid algorithm 12/12; Constraint Search 12/12; CP-SAT 12/12.

Our GA phase solved 3 of 12 attempted trials; the exact fallback supplied 9 additional valid solutions. These two contributions must be distinguished when judging the hybrid's complete-solution rate.

Completed trials exhausting the full GA budget without a GA solution: Basic GA: 11; GA + domain filtering: 9; GA + dynamic mutation: 10; Our hybrid algorithm: 9.

Domain filtering versus Basic GA isolates the tested preprocessing change; dynamic mutation versus Basic GA isolates the tested mutation schedule. Our algorithm changes several mechanisms together, so its difference cannot be attributed to domain filtering or adaptive mutation alone.

All GA phases have the same population/evaluation limit, but our hybrid may perform additional exact search after that budget. The hybrid's final validity and total runtime therefore measure a different computational workload. Its pre-fallback fitness, GA-only validity, and separately reported fallback time make that distinction visible.

Constraint Search directly applies propagation and exact backtracking without paying for a preceding GA phase. CP-SAT solves a separate declarative sum/AllDifferent model with one search worker and no supplied solution hints. Their comparison with the hybrid tests whether the preceding GA work benefits these particular instances. Neither exact algorithm is subject to a GA-generation limit; the recorded time limit applies instead.

Do not infer a speedup from an unsolved algorithm stopping sooner. Compare time to a valid solution only on paired instances that both algorithms solve. Constraint satisfaction and residual fitness help describe failed searches, but cannot replace full solution validity.

With one seed per size, these results are descriptive observations, not statistical proof of superiority. Increasing to five seeds supplies repeated observations but still requires reporting variability and failed trials. Grid size, clue tightness, run structure, and white-cell count all affect difficulty. These regular generated puzzles are not a calibrated human difficulty dataset.

Solutions are not guaranteed unique. Comparing digits to the generator's hidden witness would incorrectly label other valid solutions as wrong, so this study reports constraint validity rather than witness-based cell accuracy. Machine load and Python implementation also affect wall-clock measurements.

## Measurement interruption

The 16x16 dynamic-mutation trial was repeated once with identical puzzle, seed and budget after an execution interruption: the configured 120-second timeout was delivered after 426.189 seconds. The replacement completed in 25.097574 solver seconds, remained unsolved, and is the measurement used in the tables. The original timeout and replacement are both retained in retry_log.json. The cause of the scheduling delay is not established. There are 72 comparison measurements and 73 total process attempts.
