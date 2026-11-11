# RoundingSat and our hybrid: measured comparison

Both implementations solved all 12 puzzles. RoundingSat was faster on seven
sizes, while our hybrid was faster on five. Across the full set, RoundingSat
used 126.892 seconds and the hybrid used 225.554 seconds: a 1.78x ratio of total
solver times, or 43.74% less elapsed solver time for RoundingSat. This is an
observation for these instances, not a claim of general superiority.

## Experimental setup

- One trial per size, with puzzle/GA seed 42; sizes include the complete board,
  clue borders, and internal blocks.
- Both methods received identical saved puzzles, verified by hashes. The trials
  ran sequentially in fresh processes, with order rotated between sizes.
- Our hybrid used population 160, a maximum of 1,500 GA generations, propagation,
  run-preserving genetic operators, adaptive mutation, restarts, and exact fallback.
- The genuine [RoundingSat](https://gitlab.com/MIAOresearch/software/roundingsat)
  Windows x64 executable, commit `d4edbf7908a9bb951fd181940919e0f3ac7ab1ee`,
  solved an OPB feasibility encoding with LP ratio 1. It received no solution hints
  and has no explicit random-seed option. Binary provenance is in
  [manifest.json](../tools/roundingsat/manifest.json).
- The solving budget was 120 seconds per trial, with five additional seconds for
  native cleanup. No trial reached a limit or produced an error.

## Per-grid results

Times are measured seconds, including preprocessing and search. RoundingSat time
also includes OPB file I/O, native startup, and decoding. The hybrid includes both
GA and fallback time. Python startup and final report writing are excluded from
this table; complete worker wall times are provided in [study.md](study.md).

| Complete grid | White cells | Our hybrid (s) | RoundingSat (s) | Faster in this run | Valid solutions |
|---|---:|---:|---:|---|---|
| 4x4 | 9 | 0.002830 | 0.067960 | Our hybrid | Both |
| 5x5 | 12 | 0.006988 | 0.078233 | Our hybrid | Both |
| 6x6 | 21 | 0.137556 | 0.151657 | Our hybrid | Both |
| 8x8 | 39 | 6.456195 | 0.128852 | RoundingSat | Both |
| 10x10 | 67 | 8.897943 | 0.141910 | RoundingSat | Both |
| 12x12 | 97 | 18.595845 | 0.197956 | RoundingSat | Both |
| 15x15 | 156 | 38.605272 | 40.612204 | Our hybrid | Both |
| 16x16 | 181 | 43.696038 | 34.689267 | RoundingSat | Both |
| 11x17 | 128 | 19.498593 | 1.426858 | RoundingSat | Both |
| 13x17 | 152 | 50.301847 | 26.740779 | RoundingSat | Both |
| 14x14 | 137 | 18.724613 | 1.127510 | RoundingSat | Both |
| 14x17 | 164 | 20.630444 | 21.529006 | Our hybrid | Both |

## Evaluation metrics

| Metric across the 12 trials | Our hybrid | RoundingSat |
|---|---:|---:|
| Valid solutions | 12/12 (100%) | 12/12 (100%) |
| Final fitness on every puzzle | 0 | 0 |
| Final clue runs satisfied | 100% | 100% |
| Mean solver time (s) | 18.796180 | 10.574349 |
| Total solver time (s) | 225.554164 | 126.892192 |
| Total complete worker wall time (s) | 228.720676 | 129.959696 |
| Sizes with lower solver time | 5 | 7 |
| Solutions found during GA phase | 3/12 | N/A |
| Additional solutions from exact fallback | 9/12 | N/A |
| Mean best GA clue runs satisfied | 80.66% | N/A |
| Total GA fitness evaluations | 2,172,160 | N/A |
| Total failed backtracking branches | 20,359 | N/A |
| Total native decisions | N/A | 1,685,383 |
| Total native conflicts | N/A | 432,217 |
| Total native propagations | N/A | 14,149,378 |
| Timeouts / errors | 0 / 0 | 0 / 0 |

Native decisions, conflicts, and propagations count different operations from
GA evaluations and hybrid backtracks; their magnitudes are not directly comparable.
RoundingSat's native statistic labelled `cpu time` is coarse on Windows and is
not used for the primary speed comparison. No memory measurement was collected.

## Interpretation

Our GA solved 4x4, 5x5, and 6x6 directly. The other nine cases exhausted all
240,000 population fitness evaluations before exact fallback produced a valid
solution. The GA therefore achieved 25% complete-solution success in this run;
the full hybrid achieved 100%. Across all sizes, preprocessing took 0.401 seconds,
the GA took 180.497 seconds, and fallback took 44.656 seconds. Approximately 80%
of total hybrid solver time was spent in its GA phase. The fallback begins from
propagated domains without using the best GA candidate.

RoundingSat obtained its largest timing advantages on several middle-sized
instances, but its runtime did not increase monotonically with dimensions. For
example, 14x14 took 1.128 seconds, while 15x15 took 40.612 seconds. Our hybrid was
slightly faster on 15x15 and 14x17. White-cell count, run structure, and clue
constraints help determine search difficulty; dimensions alone do not predict it.

Including the complete Python worker invocation preserves the overall result:
total wall time was 228.721 versus 129.960 seconds, a ratio of 1.76x. These timings
compare the complete Python hybrid and native RoundingSat implementations, so they
do not isolate an algorithmic advantage from language or implementation effects.

One seed per size provides no estimate of run-to-run variability or statistical
significance. Five seeds per size should be the next study, with success counts,
means, dispersion, and all timeouts retained. The current generated puzzles are
solvable but are not guaranteed unique or calibrated for human difficulty.
Correctness is measured against the Kakuro constraints, not a hidden generator
solution. Native proof logging and proof checking were not enabled.

## Verification and reproducibility

All 24 returned solutions passed the independent validator. Every native model
was also evaluated directly against its saved OPB file: 5,373 constraints passed.
The audit checked paired puzzle hashes, source and binary fingerprints, native
counters against stdout, and agreement between per-trial files and the study.
All 12 hybrid outcomes and deterministic search counts matched the earlier
seed-42 study; these runtimes were freshly measured.

The 97-test suite was checked, including the separately enabled native SAT/UNSAT
smoke test, an exhaustive 6,561-assignment encoding check, timeout behavior,
malformed native outputs, and report integration.

- [Detailed tables and metric definitions](study.md)
- [Machine-readable results and settings](study.json)
- [Audit record](verification.json)
- Per-size `seed_42/roundingsat_artifacts/` folders contain the OPB model,
  stdout, stderr, and command; `ours.json` and `roundingsat.json` contain solutions.

To run five seeds later:

```powershell
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py --algorithms ours roundingsat --trials 5 --output-dir roundingsat_comparison_5_runs
```
