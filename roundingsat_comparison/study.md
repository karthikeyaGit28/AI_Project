# Kakuro: two-algorithm evaluation study

Recorded trials: 24 of 24 planned. Puzzle/GA seeds: 42. Population: 160. GA generation limit: 1,500. Maximum population fitness evaluations per GA: 240,000.

Grid sizes count the complete board, including clue borders and internal blocks. For each size and seed, all selected algorithms receive the same puzzle; a puzzle hash is recorded for checking this pairing. Each trial runs sequentially in a fresh Python process. The synthetic generator creates solvable instances but does not guarantee uniqueness.

Configured per-trial solving budget: 120 seconds. A timeout means the configured limit was reached, not that the puzzle is unsatisfiable. Completed unsuccessful searches retain their best candidate and measured metrics.

## Algorithm definitions

| Algorithm | Domains | Search mechanism | Restarts / exact fallback |
|---|---|---|---|
| Our hybrid algorithm | Iterative propagation and domain-indexed genes | Valid across-run sampling, run-based crossover, conflict-focused mutation with adaptive probability | Restart after 100 stagnant generations; exact backtracking if GA fails |
| RoundingSat | Nine Boolean variables per white cell, one per digit | Native pseudo-Boolean solver on an OPB feasibility model: exactly one digit per cell, weighted clue sums, at most one occurrence of each digit per run | No GA or custom fallback; native process with recorded binary and options |

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

**RoundingSat timing and statuses:** total execution time includes OPB encoding, temporary file I/O, native binary startup, search, and model decoding. The binary startup cost is included, making this a conservative comparison with the in-process hybrid timer. The native statistic labelled `cpu time` is recorded separately. This Windows build uses a coarse, whole-second clock() statistic; it is not a precise CPU measurement and is not substituted for total wall-clock execution time. Each trial's outer process wall time is also reported below. RoundingSat has a 5-second outer cleanup guard beyond the solving budget so that a native time limit can be recorded; the hybrid's outer timeout uses the configured budget.

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

| Algorithm | Valid / trials | GA-only valid | Fallback valid | Completed | Mean time (s) | Mean evaluations | Mean GA runs satisfied (%) | Mean final runs satisfied (%) | Total backtracks | RoundingSat decisions | RoundingSat conflicts | RoundingSat propagations | Mean native reported time (s) | Native time limits | Timeouts / errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Our hybrid algorithm | 12 / 12 | 3 | 9 | 12 | 18.7962 | 181,013.33 | 80.66 | 100.00 | 20,359 | N/A | N/A | N/A | N/A | N/A | 0 / 0 |
| RoundingSat | 12 / 12 | N/A | N/A | 12 | 10.5743 | N/A | N/A | 100.00 | N/A | 1,685,383 | 432,217 | 14,149,378 | 10.250000 | 0 | 0 / 0 |

## Per-grid execution time and validity

Each entry is **mean seconds; valid/attempted trials**. With one seed it is the actual single-run measurement. An unsuccessful GA run's elapsed time is a budget-exhaustion time, not a time to solve. For exact solvers, the status distinguishes infeasibility from an inconclusive limit.

| Grid | Our hybrid algorithm | RoundingSat |
|---|---:|---:|
| 4x4 | 0.0028; 1/1 | 0.0680; 1/1 |
| 5x5 | 0.0070; 1/1 | 0.0782; 1/1 |
| 6x6 | 0.1376; 1/1 | 0.1517; 1/1 |
| 8x8 | 6.4562; 1/1 | 0.1289; 1/1 |
| 10x10 | 8.8979; 1/1 | 0.1419; 1/1 |
| 12x12 | 18.5958; 1/1 | 0.1980; 1/1 |
| 15x15 | 38.6053; 1/1 | 40.6122; 1/1 |
| 16x16 | 43.6960; 1/1 | 34.6893; 1/1 |
| 11x17 | 19.4986; 1/1 | 1.4269; 1/1 |
| 13x17 | 50.3018; 1/1 | 26.7408; 1/1 |
| 14x14 | 18.7246; 1/1 | 1.1275; 1/1 |
| 14x17 | 20.6304; 1/1 | 21.5290; 1/1 |

## Per-grid outer process wall time

Each entry is mean elapsed seconds for the complete worker process, including Python startup, library loading, puzzle parsing, search, validation, and result serialization. RoundingSat additionally starts its native process. This secondary measurement compares the full invocation costs of both implementations. Every recorded wall time is included, including outer timeouts; pair it with the validity table above before interpreting performance.

| Grid | Our hybrid algorithm | RoundingSat |
|---|---:|---:|
| 4x4 | 0.199900 | 0.290662 |
| 5x5 | 0.212706 | 0.327184 |
| 6x6 | 0.370938 | 0.386291 |
| 8x8 | 6.710534 | 0.342586 |
| 10x10 | 9.200816 | 0.379458 |
| 12x12 | 18.854556 | 0.434779 |
| 15x15 | 38.897445 | 40.966898 |
| 16x16 | 43.981604 | 34.966811 |
| 11x17 | 19.745061 | 1.688446 |
| 13x17 | 50.654388 | 27.007075 |
| 14x14 | 18.989030 | 1.408649 |
| 14x17 | 20.903698 | 21.760856 |

## Per-grid best GA fitness before fallback

Lower is better; zero means the GA phase solved the puzzle. These values are the best candidate encountered within the GA budget, including candidates retained across restarts. Our fallback cannot improve the values in this table. Multiple seeds are averaged.

Exact solvers have no GA phase; they are omitted from this table.

| Grid | Our hybrid algorithm |
|---|---:|
| 4x4 | 0.00 |
| 5x5 | 0.00 |
| 6x6 | 0.00 |
| 8x8 | 2.00 |
| 10x10 | 10.00 |
| 12x12 | 33.00 |
| 15x15 | 47.00 |
| 16x16 | 98.00 |
| 11x17 | 48.00 |
| 13x17 | 52.00 |
| 14x14 | 55.00 |
| 14x17 | 70.00 |

## RoundingSat native diagnostics

Total time includes the native process overhead; native reported time is the solver's coarse clock statistic, labelled cpu time upstream. Outer wall time additionally includes Python startup, parsing, validation, and result serialization. Native limits are recorded separately from an outer process timeout. Missing native counters remain N/A.

| Grid | Seed | Trial status | Solver status | Native status | Total (s) | Native reported (s) | Outer wall (s) | Decisions | Conflicts | Propagations | OPB variables | OPB constraints | Native limit | Valid |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 4x4 | 42 | completed | SOLVED | SATISFIABLE | 0.067960 | 0.000000 | 0.290662 | 34 | 1 | 54 | 81 | 69 | No | Yes |
| 5x5 | 42 | completed | SOLVED | SATISFIABLE | 0.078233 | 0.000000 | 0.327184 | 100 | 19 | 252 | 108 | 92 | No | Yes |
| 6x6 | 42 | completed | SOLVED | SATISFIABLE | 0.151657 | 0.000000 | 0.386291 | 140 | 28 | 483 | 189 | 121 | No | Yes |
| 8x8 | 42 | completed | SOLVED | SATISFIABLE | 0.128852 | 0.000000 | 0.342586 | 554 | 78 | 2,153 | 351 | 209 | No | Yes |
| 10x10 | 42 | completed | SOLVED | SATISFIABLE | 0.141910 | 0.000000 | 0.379458 | 1,395 | 294 | 7,649 | 603 | 307 | No | Yes |
| 12x12 | 42 | completed | SOLVED | SATISFIABLE | 0.197956 | 0.000000 | 0.434779 | 8,316 | 1,486 | 49,844 | 873 | 437 | No | Yes |
| 15x15 | 42 | completed | SOLVED | SATISFIABLE | 40.612204 | 40.000000 | 40.966898 | 382,386 | 102,066 | 3,190,435 | 1,404 | 716 | No | Yes |
| 16x16 | 42 | completed | SOLVED | SATISFIABLE | 34.689267 | 34.000000 | 34.966811 | 354,199 | 82,380 | 2,954,355 | 1,629 | 781 | No | Yes |
| 11x17 | 42 | completed | SOLVED | SATISFIABLE | 1.426858 | 1.000000 | 1.688446 | 25,230 | 7,888 | 197,095 | 1,152 | 608 | No | Yes |
| 13x17 | 42 | completed | SOLVED | SATISFIABLE | 26.740779 | 26.000000 | 27.007075 | 389,108 | 114,642 | 3,568,749 | 1,368 | 692 | No | Yes |
| 14x14 | 42 | completed | SOLVED | SATISFIABLE | 1.127510 | 1.000000 | 1.408649 | 20,213 | 5,798 | 161,064 | 1,233 | 617 | No | Yes |
| 14x17 | 42 | completed | SOLVED | SATISFIABLE | 21.529006 | 21.000000 | 21.760856 | 503,708 | 117,537 | 4,017,245 | 1,476 | 724 | No | Yes |

## Every measured trial

All times are seconds. A completed status includes unsuccessful searches. GA fitness and GA run satisfaction describe the best pre-fallback candidate; final columns describe the returned candidate or solution.

| Grid | Seed | Algorithm | Status | Time | Preprocess | GA time | Fallback time | Evaluations | Generations | GA fitness | Final fitness | GA valid | Final valid | Fallback used | Backtracks | GA runs (%) | Final runs (%) | Solved/white cells | Domain reduction (%) |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| 4x4 | 42 | Our hybrid algorithm | completed | 0.0028 | 0.0005 | 0.0024 | 0.0000 | 320 | 2 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 9/9 | 0.00 |
| 4x4 | 42 | RoundingSat | completed | 0.0680 | 0.0016 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 9/9 | N/A |
| 5x5 | 42 | RoundingSat | completed | 0.0782 | 0.0034 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 12/12 | N/A |
| 5x5 | 42 | Our hybrid algorithm | completed | 0.0070 | 0.0020 | 0.0050 | 0.0000 | 480 | 3 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 12/12 | 21.30 |
| 6x6 | 42 | Our hybrid algorithm | completed | 0.1376 | 0.0048 | 0.1328 | 0.0000 | 11,360 | 71 | 0 | 0 | Yes | Yes | No | 0 | 100.00 | 100.00 | 21/21 | 6.35 |
| 6x6 | 42 | RoundingSat | completed | 0.1517 | 0.0064 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 21/21 | N/A |
| 8x8 | 42 | RoundingSat | completed | 0.1289 | 0.0049 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 39/39 | N/A |
| 8x8 | 42 | Our hybrid algorithm | completed | 6.4562 | 0.0136 | 6.3909 | 0.0517 | 240,000 | 1,500 | 2 | 0 | No | Yes | Yes | 0 | 88.24 | 100.00 | 39/39 | 17.38 |
| 10x10 | 42 | Our hybrid algorithm | completed | 8.8979 | 0.0215 | 8.7202 | 0.1563 | 240,000 | 1,500 | 10 | 0 | No | Yes | Yes | 1 | 70.83 | 100.00 | 67/67 | 6.30 |
| 10x10 | 42 | RoundingSat | completed | 0.1419 | 0.0025 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 67/67 | N/A |
| 12x12 | 42 | RoundingSat | completed | 0.1980 | 0.0072 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 97/97 | N/A |
| 12x12 | 42 | Our hybrid algorithm | completed | 18.5958 | 0.0190 | 16.7059 | 1.8709 | 240,000 | 1,500 | 33 | 0 | No | Yes | Yes | 370 | 76.47 | 100.00 | 97/97 | 10.19 |
| 15x15 | 42 | Our hybrid algorithm | completed | 38.6053 | 0.0581 | 37.6361 | 0.9111 | 240,000 | 1,500 | 47 | 0 | No | Yes | Yes | 5 | 76.79 | 100.00 | 156/156 | 17.52 |
| 15x15 | 42 | RoundingSat | completed | 40.6122 | 0.0043 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 156/156 | N/A |
| 16x16 | 42 | RoundingSat | completed | 34.6893 | 0.0063 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 181/181 | N/A |
| 16x16 | 42 | Our hybrid algorithm | completed | 43.6960 | 0.0473 | 26.7890 | 16.8597 | 240,000 | 1,500 | 98 | 0 | No | Yes | Yes | 7,774 | 66.67 | 100.00 | 181/181 | 9.70 |
| 11x17 | 42 | Our hybrid algorithm | completed | 19.4986 | 0.0508 | 17.2539 | 2.1939 | 240,000 | 1,500 | 48 | 0 | No | Yes | Yes | 995 | 68.75 | 100.00 | 128/128 | 16.58 |
| 11x17 | 42 | RoundingSat | completed | 1.4269 | 0.0035 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 128/128 | N/A |
| 13x17 | 42 | RoundingSat | completed | 26.7408 | 0.0049 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 152/152 | N/A |
| 13x17 | 42 | Our hybrid algorithm | completed | 50.3018 | 0.0714 | 28.7460 | 21.4845 | 240,000 | 1,500 | 52 | 0 | No | Yes | Yes | 11,139 | 74.07 | 100.00 | 152/152 | 17.91 |
| 14x14 | 42 | Our hybrid algorithm | completed | 18.7246 | 0.0456 | 18.0033 | 0.6757 | 240,000 | 1,500 | 55 | 0 | No | Yes | Yes | 72 | 72.92 | 100.00 | 137/137 | 12.25 |
| 14x14 | 42 | RoundingSat | completed | 1.1275 | 0.0054 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 137/137 | N/A |
| 14x17 | 42 | RoundingSat | completed | 21.5290 | 0.0045 | N/A | 0.0000 | N/A | N/A | N/A | 0 | N/A | Yes | No | N/A | N/A | 100.00 | 164/164 | N/A |
| 14x17 | 42 | Our hybrid algorithm | completed | 20.6304 | 0.0664 | 20.1116 | 0.4524 | 240,000 | 1,500 | 70 | 0 | No | Yes | Yes | 3 | 73.21 | 100.00 | 164/164 | 14.36 |

## Findings and interpretation

Observed complete-solution counts: Our hybrid algorithm 12/12; RoundingSat 12/12.

Our GA phase solved 3 of 12 attempted trials; the exact fallback supplied 9 additional valid solutions. These two contributions must be distinguished when judging the hybrid's complete-solution rate.

Completed trials exhausting the full GA budget without a GA solution: Our hybrid algorithm: 9.

Our hybrid may perform additional exact search after the GA budget. Its final validity and total runtime include this work; its pre-fallback fitness, GA-only validity, and separately reported fallback time show the contribution of each stage.

RoundingSat solves the encoded pseudo-Boolean constraints directly, without a supplied solution witness or hybrid GA phase. Its native decisions and conflicts measure different operations from the hybrid's fitness evaluations and failed backtracking branches. This comparison measures these complete implementations on the recorded instances; it does not isolate a single algorithmic improvement or programming-language effect.

Exact solvers are not subject to the GA-generation limit; the recorded time limit applies instead.

Do not infer a speedup from an unsolved algorithm stopping sooner. Compare time to a valid solution only on paired instances that both algorithms solve. Constraint satisfaction and residual fitness help describe failed searches, but cannot replace full solution validity.

With one seed per size, these results are descriptive observations, not statistical proof of superiority. Increasing to five seeds supplies repeated observations but still requires reporting variability and failed trials. Grid size, clue tightness, run structure, and white-cell count all affect difficulty. These regular generated puzzles are not a calibrated human difficulty dataset.

Solutions are not guaranteed unique. Comparing digits to the generator's hidden witness would incorrectly label other valid solutions as wrong, so this study reports constraint validity rather than witness-based cell accuracy. Machine load and Python implementation also affect wall-clock measurements.
