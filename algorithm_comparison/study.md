# Kakuro: four-algorithm evaluation study

Recorded trials: 48 of 48 planned. Seeds: 42. Population: 160. GA generation limit: 1,500. Maximum population fitness evaluations per GA: 240,000.

Grid sizes count the complete board, including clue borders and internal blocks. For each size and seed, all four algorithms receive the same puzzle; a puzzle hash is recorded for checking this pairing. Each trial runs sequentially in a fresh Python process. The synthetic generator creates solvable instances but does not guarantee uniqueness.

Per-trial wall-clock limit: 120 seconds. A timeout means the configured limit was reached, not that the puzzle is unsatisfiable. Completed unsuccessful searches retain their best candidate and measured metrics.

## Algorithm definitions

| Algorithm | Domains | Crossover and mutation | Restarts / exact fallback |
|---|---|---|---|
| Basic GA | Digits 1 through 9 for every cell | Uniform cell crossover; fixed 0.25 probability of mutating one randomly selected cell | Neither |
| GA + domain filtering | Iterative clue-based constraint propagation before GA | Same crossover and fixed mutation as Basic GA | Neither |
| GA + dynamic mutation | Digits 1 through 9; no domain filtering | Same crossover as Basic GA; mutation rises from 0.25 toward 0.90 with stagnation | Neither |
| Our hybrid algorithm | Iterative propagation and domain-indexed genes | Valid across-run sampling, run-based crossover, conflict-focused mutation with adaptive probability | Restart after 100 stagnant generations; exact backtracking if GA fails |

The three baselines share top-third parent selection and at most eight elites (`min(8, population_size // 10)`). Mutation replaces one selected cell's value with a different allowed digit when one is available. Filtering and dynamic mutation are independent additions to Basic GA, not cumulative variants. Adaptive probability is `min(0.90, 0.25 + 0.65 * stagnant_generations / 100)`.

## Metric definitions

- **Valid solution:** every white cell has a digit 1-9, and every across/down run has the required sum and no repeated digit. An independent validator checks this.
- **Fitness (lower is better):** sum over all runs of `abs(actual_sum - clue_sum) + 9 * (run_length - distinct_digits)`. Zero is a complete valid solution. Our GA preserves across constraints, so its down-only search score equals this common all-run score.
- **Satisfied runs (%):** percentage of runs meeting both the exact sum and no-repeat requirements. This is partial constraint satisfaction, not puzzle validity or cell accuracy.
- **Execution time:** propagation/preprocessing plus GA plus any exact fallback. It excludes puzzle generation, parsing, final output validation, file I/O, and process startup.
- **Fitness evaluations:** evaluated population members. Auxiliary conflict checks and constraint-propagation work are not included in this count.
- **Backtracks:** failed branches in the exact fallback. Zero can also occur when fallback succeeds without rejecting a branch; use the fallback indicator to identify its use.
- **Solved white cells:** the complete white-cell count only when the whole solution validates; an unsolved full candidate is not counted as a partially correct solution.

Averages include all completed trials, including unsolved GA runs. Timeouts/errors remain in the attempted-trial denominator but are excluded from numerical means. Missing measurements are shown as N/A. Means of run satisfaction give each trial equal weight.

## Aggregate results

| Algorithm | Valid / trials | GA-only valid | Fallback valid | Completed | Mean time (s) | Mean evaluations | Mean GA runs satisfied (%) | Mean final runs satisfied (%) | Total backtracks | Timeouts / errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Basic GA | 1 / 12 | 1 | 0 | 12 | 11.6679 | 220,200.00 | 54.38 | 54.38 | 0 | 0 / 0 |
| GA + domain filtering | 3 / 12 | 3 | 0 | 12 | 11.2560 | 186,013.33 | 69.27 | 69.27 | 0 | 0 / 0 |
| GA + dynamic mutation | 2 / 12 | 2 | 0 | 12 | 11.5065 | 203,880.00 | 58.87 | 58.87 | 0 | 0 / 0 |
| Our hybrid algorithm | 12 / 12 | 3 | 9 | 12 | 27.9642 | 181,013.33 | 80.66 | 100.00 | 20,359 | 0 / 0 |

## Per-grid execution time and validity

Each entry is **mean seconds; valid/attempted trials**. With one seed it is the actual single-run measurement. An unsuccessful run's elapsed time is a budget-exhaustion time, not a time to solve.

| Grid | Basic GA | Domain filtering | Dynamic mutation | Our hybrid |
|---|---:|---:|---:|---:|
| 4x4 | 0.0201; 1/1 | 0.0188; 1/1 | 0.0240; 1/1 | 0.0057; 1/1 |
| 5x5 | 2.1583; 0/1 | 0.3145; 1/1 | 2.6740; 0/1 | 0.0100; 1/1 |
| 6x6 | 3.3523; 0/1 | 0.6089; 1/1 | 0.6862; 1/1 | 0.2646; 1/1 |
| 8x8 | 5.6033; 0/1 | 5.4752; 0/1 | 5.7618; 0/1 | 10.2283; 1/1 |
| 10x10 | 8.6851; 0/1 | 8.4624; 0/1 | 8.9541; 0/1 | 16.3319; 1/1 |
| 12x12 | 11.4190; 0/1 | 11.3377; 0/1 | 11.7678; 0/1 | 22.9660; 1/1 |
| 15x15 | 19.0737; 0/1 | 18.7682; 0/1 | 18.5524; 0/1 | 35.8284; 1/1 |
| 16x16 | 20.7741; 0/1 | 20.3997; 0/1 | 20.0344; 0/1 | 69.3748; 1/1 |
| 11x17 | 15.7361; 0/1 | 15.3650; 0/1 | 16.1754; 0/1 | 33.8834; 1/1 |
| 13x17 | 17.5020; 0/1 | 18.2240; 0/1 | 18.3865; 0/1 | 79.1408; 1/1 |
| 14x14 | 16.6729; 0/1 | 16.8374; 0/1 | 16.0140; 0/1 | 31.1270; 1/1 |
| 14x17 | 19.0177; 0/1 | 19.2609; 0/1 | 19.0471; 0/1 | 36.4098; 1/1 |

## Per-grid best GA fitness before fallback

Lower is better; zero means the GA phase solved the puzzle. These values are the best candidate encountered within the GA budget, including candidates retained across restarts. Our fallback cannot improve the values in this table. Multiple seeds are averaged.

| Grid | Basic GA | Domain filtering | Dynamic mutation | Our GA phase |
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

## Every measured trial

All times are seconds. A completed status includes unsuccessful searches. GA fitness and GA run satisfaction describe the best pre-fallback candidate; final columns describe the returned candidate or solution.

| Grid | Seed | Algorithm | Status | Time | Preprocess | GA time | Fallback time | Evaluations | Generations | GA fitness | Final fitness | GA valid | Final valid | Fallback used | Backtracks | GA runs (%) | Final runs (%) | Solved/white cells | Domain reduction (%) |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| 4x4 | 42 | Basic GA | completed | 0.0201 | 0.0000 | 0.0200 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + domain filtering | completed | 0.0188 | 0.0009 | 0.0179 | 0.0000 | 2,400 | 15 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | GA + dynamic mutation | completed | 0.0240 | 0.0000 | 0.0239 | 0.0000 | 2,240 | 14 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | Our hybrid algorithm | completed | 0.0057 | 0.0010 | 0.0047 | 0.0000 | 320 | 2 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 5x5 | 42 | GA + domain filtering | completed | 0.3145 | 0.0043 | 0.3102 | 0.0000 | 31,040 | 194 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | GA + dynamic mutation | completed | 2.6740 | 0.0000 | 2.6740 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 5x5 | 42 | Our hybrid algorithm | completed | 0.0100 | 0.0035 | 0.0066 | 0.0000 | 480 | 3 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 5x5 | 42 | Basic GA | completed | 2.1583 | 0.0000 | 2.1583 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 75.00 | 75.00 | 0/12 | 0.00 |
| 6x6 | 42 | GA + dynamic mutation | completed | 0.6862 | 0.0001 | 0.6861 | 0.0000 | 44,320 | 277 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 0.00 |
| 6x6 | 42 | Our hybrid algorithm | completed | 0.2646 | 0.0074 | 0.2572 | 0.0000 | 11,360 | 71 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | Basic GA | completed | 3.3523 | 0.0000 | 3.3522 | 0.0000 | 240,000 | 1,500 | 2 | 2 | No | No | No | 0 | 80.00 | 80.00 | 0/21 | 0.00 |
| 6x6 | 42 | GA + domain filtering | completed | 0.6089 | 0.0077 | 0.6012 | 0.0000 | 38,720 | 242 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 8x8 | 42 | Our hybrid algorithm | completed | 10.2283 | 0.0289 | 10.1139 | 0.0855 | 240,000 | 1,500 | 2 | 0 | No | Yes | Yes | 0 | 88.24 | 100.00 | 39/39 | 17.38 |
| 8x8 | 42 | Basic GA | completed | 5.6033 | 0.0000 | 5.6032 | 0.0000 | 240,000 | 1,500 | 14 | 14 | No | No | No | 0 | 58.82 | 58.82 | 0/39 | 0.00 |
| 8x8 | 42 | GA + domain filtering | completed | 5.4752 | 0.0245 | 5.4507 | 0.0000 | 240,000 | 1,500 | 4 | 4 | No | No | No | 0 | 82.35 | 82.35 | 0/39 | 17.38 |
| 8x8 | 42 | GA + dynamic mutation | completed | 5.7618 | 0.0000 | 5.7617 | 0.0000 | 240,000 | 1,500 | 12 | 12 | No | No | No | 0 | 52.94 | 52.94 | 0/39 | 0.00 |
| 10x10 | 42 | Basic GA | completed | 8.6851 | 0.0001 | 8.6851 | 0.0000 | 240,000 | 1,500 | 24 | 24 | No | No | No | 0 | 41.67 | 41.67 | 0/67 | 0.00 |
| 10x10 | 42 | GA + domain filtering | completed | 8.4624 | 0.0348 | 8.4276 | 0.0000 | 240,000 | 1,500 | 33 | 33 | No | No | No | 0 | 45.83 | 45.83 | 0/67 | 6.30 |
| 10x10 | 42 | GA + dynamic mutation | completed | 8.9541 | 0.0001 | 8.9541 | 0.0000 | 240,000 | 1,500 | 36 | 36 | No | No | No | 0 | 54.17 | 54.17 | 0/67 | 0.00 |
| 10x10 | 42 | Our hybrid algorithm | completed | 16.3319 | 0.0422 | 15.9698 | 0.3198 | 240,000 | 1,500 | 10 | 0 | No | Yes | Yes | 1 | 70.83 | 100.00 | 67/67 | 6.30 |
| 12x12 | 42 | GA + domain filtering | completed | 11.3377 | 0.0344 | 11.3033 | 0.0000 | 240,000 | 1,500 | 45 | 45 | No | No | No | 0 | 61.76 | 61.76 | 0/97 | 10.19 |
| 12x12 | 42 | GA + dynamic mutation | completed | 11.7678 | 0.0001 | 11.7677 | 0.0000 | 240,000 | 1,500 | 24 | 24 | No | No | No | 0 | 55.88 | 55.88 | 0/97 | 0.00 |
| 12x12 | 42 | Our hybrid algorithm | completed | 22.9660 | 0.0469 | 21.7883 | 1.1308 | 240,000 | 1,500 | 33 | 0 | No | Yes | Yes | 370 | 76.47 | 100.00 | 97/97 | 10.19 |
| 12x12 | 42 | Basic GA | completed | 11.4190 | 0.0001 | 11.4189 | 0.0000 | 240,000 | 1,500 | 41 | 41 | No | No | No | 0 | 58.82 | 58.82 | 0/97 | 0.00 |
| 15x15 | 42 | GA + dynamic mutation | completed | 18.5524 | 0.0002 | 18.5521 | 0.0000 | 240,000 | 1,500 | 54 | 54 | No | No | No | 0 | 42.86 | 42.86 | 0/156 | 0.00 |
| 15x15 | 42 | Our hybrid algorithm | completed | 35.8284 | 0.1161 | 35.0082 | 0.7041 | 240,000 | 1,500 | 47 | 0 | No | Yes | Yes | 5 | 76.79 | 100.00 | 156/156 | 17.52 |
| 15x15 | 42 | Basic GA | completed | 19.0737 | 0.0001 | 19.0736 | 0.0000 | 240,000 | 1,500 | 73 | 73 | No | No | No | 0 | 32.14 | 32.14 | 0/156 | 0.00 |
| 15x15 | 42 | GA + domain filtering | completed | 18.7682 | 0.1125 | 18.6557 | 0.0000 | 240,000 | 1,500 | 122 | 122 | No | No | No | 0 | 46.43 | 46.43 | 0/156 | 17.52 |
| 16x16 | 42 | Our hybrid algorithm | completed | 69.3748 | 0.0829 | 38.9605 | 30.3314 | 240,000 | 1,500 | 98 | 0 | No | Yes | Yes | 7,774 | 66.67 | 100.00 | 181/181 | 9.70 |
| 16x16 | 42 | Basic GA | completed | 20.7741 | 0.0002 | 20.7739 | 0.0000 | 240,000 | 1,500 | 136 | 136 | No | No | No | 0 | 45.00 | 45.00 | 0/181 | 0.00 |
| 16x16 | 42 | GA + domain filtering | completed | 20.3997 | 0.1164 | 20.2833 | 0.0000 | 240,000 | 1,500 | 78 | 78 | No | No | No | 0 | 66.67 | 66.67 | 0/181 | 9.70 |
| 16x16 | 42 | GA + dynamic mutation | completed | 20.0344 | 0.0001 | 20.0343 | 0.0000 | 240,000 | 1,500 | 82 | 82 | No | No | No | 0 | 50.00 | 50.00 | 0/181 | 0.00 |
| 11x17 | 42 | Basic GA | completed | 15.7361 | 0.0001 | 15.7360 | 0.0000 | 240,000 | 1,500 | 51 | 51 | No | No | No | 0 | 41.67 | 41.67 | 0/128 | 0.00 |
| 11x17 | 42 | GA + domain filtering | completed | 15.3650 | 0.1111 | 15.2539 | 0.0000 | 240,000 | 1,500 | 93 | 93 | No | No | No | 0 | 56.25 | 56.25 | 0/128 | 16.58 |
| 11x17 | 42 | GA + dynamic mutation | completed | 16.1754 | 0.0001 | 16.1752 | 0.0000 | 240,000 | 1,500 | 48 | 48 | No | No | No | 0 | 39.58 | 39.58 | 0/128 | 0.00 |
| 11x17 | 42 | Our hybrid algorithm | completed | 33.8834 | 0.1105 | 28.9228 | 4.8501 | 240,000 | 1,500 | 48 | 0 | No | Yes | Yes | 995 | 68.75 | 100.00 | 128/128 | 16.58 |
| 13x17 | 42 | GA + domain filtering | completed | 18.2240 | 0.1084 | 18.1156 | 0.0000 | 240,000 | 1,500 | 79 | 79 | No | No | No | 0 | 57.41 | 57.41 | 0/152 | 17.91 |
| 13x17 | 42 | GA + dynamic mutation | completed | 18.3865 | 0.0001 | 18.3863 | 0.0000 | 240,000 | 1,500 | 52 | 52 | No | No | No | 0 | 40.74 | 40.74 | 0/152 | 0.00 |
| 13x17 | 42 | Our hybrid algorithm | completed | 79.1408 | 0.1026 | 33.2413 | 45.7969 | 240,000 | 1,500 | 52 | 0 | No | Yes | Yes | 11,139 | 74.07 | 100.00 | 152/152 | 17.91 |
| 13x17 | 42 | Basic GA | completed | 17.5020 | 0.0002 | 17.5018 | 0.0000 | 240,000 | 1,500 | 87 | 87 | No | No | No | 0 | 35.19 | 35.19 | 0/152 | 0.00 |
| 14x14 | 42 | GA + dynamic mutation | completed | 16.0140 | 0.0001 | 16.0139 | 0.0000 | 240,000 | 1,500 | 48 | 48 | No | No | No | 0 | 54.17 | 54.17 | 0/137 | 0.00 |
| 14x14 | 42 | Our hybrid algorithm | completed | 31.1270 | 0.0848 | 29.9394 | 1.1027 | 240,000 | 1,500 | 55 | 0 | No | Yes | Yes | 72 | 72.92 | 100.00 | 137/137 | 12.25 |
| 14x14 | 42 | Basic GA | completed | 16.6729 | 0.0001 | 16.6728 | 0.0000 | 240,000 | 1,500 | 90 | 90 | No | No | No | 0 | 39.58 | 39.58 | 0/137 | 0.00 |
| 14x14 | 42 | GA + domain filtering | completed | 16.8374 | 0.0842 | 16.7532 | 0.0000 | 240,000 | 1,500 | 69 | 69 | No | No | No | 0 | 52.08 | 52.08 | 0/137 | 12.25 |
| 14x17 | 42 | Our hybrid algorithm | completed | 36.4098 | 0.1168 | 35.4498 | 0.8432 | 240,000 | 1,500 | 70 | 0 | No | Yes | Yes | 3 | 73.21 | 100.00 | 164/164 | 14.36 |
| 14x17 | 42 | Basic GA | completed | 19.0177 | 0.0001 | 19.0176 | 0.0000 | 240,000 | 1,500 | 87 | 87 | No | No | No | 0 | 44.64 | 44.64 | 0/164 | 0.00 |
| 14x17 | 42 | GA + domain filtering | completed | 19.2609 | 0.1094 | 19.1515 | 0.0000 | 240,000 | 1,500 | 120 | 120 | No | No | No | 0 | 62.50 | 62.50 | 0/164 | 14.36 |
| 14x17 | 42 | GA + dynamic mutation | completed | 19.0471 | 0.0002 | 19.0469 | 0.0000 | 240,000 | 1,500 | 71 | 71 | No | No | No | 0 | 41.07 | 41.07 | 0/164 | 0.00 |

## Findings and interpretation

Observed complete-solution counts: Basic GA 1/12; GA + domain filtering 3/12; GA + dynamic mutation 2/12; Our hybrid algorithm 12/12.

Our GA phase solved 3 of 12 attempted trials; the exact fallback supplied 9 additional valid solutions. These two contributions must be distinguished when judging the hybrid's complete-solution rate.

Completed trials exhausting the full GA budget without a GA solution: Basic GA: 11; GA + domain filtering: 9; GA + dynamic mutation: 10; Our hybrid algorithm: 9.

Domain filtering versus Basic GA isolates the tested preprocessing change; dynamic mutation versus Basic GA isolates the tested mutation schedule. Our algorithm changes several mechanisms together, so its difference cannot be attributed to domain filtering or adaptive mutation alone.

All GA phases have the same population/evaluation limit, but our hybrid may perform additional exact search after that budget. The hybrid's final validity and total runtime therefore measure a different computational workload. Its pre-fallback fitness, GA-only validity, and separately reported fallback time make that distinction visible.

Do not infer a speedup from an unsolved algorithm stopping sooner. Compare time to a valid solution only on paired instances that both algorithms solve. Constraint satisfaction and residual fitness help describe failed searches, but cannot replace full solution validity.

With one seed per size, these results are descriptive observations, not statistical proof of superiority. Increasing to five seeds supplies repeated observations but still requires reporting variability and failed trials. Grid size, clue tightness, run structure, and white-cell count all affect difficulty. These regular generated puzzles are not a calibrated human difficulty dataset.

Solutions are not guaranteed unique. Comparing digits to the generator's hidden witness would incorrectly label other valid solutions as wrong, so this study reports constraint validity rather than witness-based cell accuracy. Machine load and Python implementation also affect wall-clock measurements.
