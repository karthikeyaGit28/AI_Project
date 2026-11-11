# Kakuro generator and solver

Python 3.10 or later. The GA and constraint-search solvers use only the standard
library. CP-SAT additionally requires the pinned OR-Tools dependency described below.

Solve the existing puzzle without changing its contents:

```powershell
python generate_and_solve.py --input kakuro_puzzle.json --output kakuro_solution.json
```

Generate a new puzzle and solve it (`--generate` replaces the specified input file):

```powershell
python generate_and_solve.py --generate --size 5 --seed 42 --input new_puzzle.json --output new_solution.json
```

With no arguments, the script reads `kakuro_puzzle.json` if it exists, or generates
it if it is missing. An explicitly specified missing `--input` is an error.
`--size` only affects generation. Input and output must be different files.

Control the genetic search budget or use the exact solver directly:

```powershell
python generate_and_solve.py --population-size 160 --generations 1500
python generate_and_solve.py --generations 0
python -m unittest -v
```

If `python` is not on PATH, this machine also has an interpreter at
`D:\anaconda3\python.exe`. For example:

```powershell
& 'D:\anaconda3\python.exe' generate_and_solve.py
& 'D:\anaconda3\python.exe' -m unittest -v
```

## Puzzle format

The JSON object contains a rectangular `grid`. `format` is optional; when present,
it must be `"kakuro-grid-v1"`. `size` and `seed` are generator metadata; the solver
uses the actual grid dimensions.

- `null`: an empty white cell.
- `"#"`: a block.
- `{"across": 6}`, `{"down": 7}`, or `{"across": 6, "down": 7}`: a clue cell.

A clue covers consecutive white cells immediately to its right or below. Each
white cell must belong to exactly one run in each direction. Runs contain 2 to 9
distinct digits from 1 through 9, and their digits must sum to the clue. Numeric
givens are not supported by this format.

The generator uses a seeded Latin-square filling to produce solvable square
examples of sizes 2 through 9. It does **not** guarantee a unique solution or
generate internal blocks. In a full 9-by-9 white grid every run necessarily sums
to 45, so changing the seed cannot change those clues. Custom input grids may be
rectangular and contain internal blocks and combined clues.

## Solver and flowchart

1. Parse and validate the grid, clue bounds, and membership in both run directions.
2. Build valid run transitions using cached digit-mask states, then propagate
   supported values until the restricted cell domains stop changing. This avoids
   materializing up to 9! permutations per run.
3. Initialize domain-indexed genes by sampling valid across-run assignments.
4. Score down-clue sum errors and repeated digits. A zero score, together with the
   preserved across constraints, gives a complete solution.
5. Use selection, elitism, run-based crossover, and mutation focused on rows that
   cross violated down clues. Mutation increases with stagnation. Restart after
   100 generations without an improvement and stop at the generation budget.
6. If the genetic search does not find a solution, use exact backtracking with
   minimum-domain selection and propagation after each decision.
7. Independently validate every digit and run before writing a solved board.

These steps implement the supplied flowchart. Its optional repair stage is
omitted; the exact backtracking fallback is an additional completion step.
Sampling valid runs is randomized but is not uniform over all valid assignments.

## Output and metrics

`board` is the display grid; clue strings use `across\down`. `solution` retains
the original inner-matrix format, excluding the first row and column, with `null`
at internal blocks/clues. `solved_grid` is the complete, unambiguous grid with
clues and blocks preserved and white cells replaced by digits.

The metrics report solver time, failed backtracking branches, population fitness
evaluations, solved cell count, and final validity. The legacy
`solution_validity_rate_percent` is 100 or 0 for this single result, **not** an
empirical success rate over multiple puzzles. Search time excludes file I/O and
parsing. The `algorithm` field identifies the stage that produced the result.

An inconsistent puzzle produces an output with null solution fields, an `error`,
and false validity, then exits unsuccessfully. Invalid JSON or malformed grids
are rejected with an error before search. Solving finds one valid solution; it
does not count solutions or verify uniqueness.

## Comparing grid sizes

Run the requested twelve sizes with one reproducible puzzle per size:

```powershell
& 'D:\anaconda3\python.exe' benchmark_kakuro.py
```

The defaults are seed 42, population 160, a 1,500-generation GA
budget followed by exact fallback, and a 120-second wall-clock limit per trial.
Trials run sequentially in fresh Python processes, avoiding reuse of cached
constraints between measurements. The original puzzle and solution files are
not benchmark outputs.

Benchmark sizes count the complete board: `4x4` is exactly a `4x4` JSON grid,
including the top and left clue borders and internal blocks. This differs from
the original demo's `--size` argument, which counts the inner white-cell area.
Use `--size-convention inner` to request that earlier convention instead.

For five puzzles per size later, use seeds 42 through 46 and a separate output
directory to retain the one-run comparison:

```powershell
& 'D:\anaconda3\python.exe' benchmark_kakuro.py --trials 5 --output-dir benchmark_results_5_runs
```

`kakuro_generator.py` provides a separate rectangular generator. Its full-board
API is `generate_rectangular_puzzle(rows, columns, seed)`. It uses connected,
regular blocked layouts for the requested dimensions and a hidden valid filling
to derive clues. Every run has 2 to 9 cells. Generated instances are solvable;
uniqueness and calibrated difficulty are not guaranteed.

Outputs are saved in `benchmark_results/`:

- `comparison.md`: the comparison table, with mean times and search counts.
- `comparison.json`: settings, environment, source hashes, every raw measurement,
  and aggregates including time and white-cell ranges.
- `<size>/seed_<seed>/puzzle.json` and `solution.json`: individual inputs and results.

Each solution is checked independently of the solver's own validator. The table
separates GA successes from fallback successes and reports validated runs divided
by all trials. Timeout/error trials remain in the report; they are not assigned
zero runtimes or treated as proven unsatisfiable. Timing means include completed
valid trials only, with coverage explicitly shown. Solver time excludes puzzle
generation, parsing, output validation, process startup, and file I/O.

Grid dimensions alone do not determine Kakuro difficulty. White-cell counts,
run lengths, and clues vary between generated instances, so these results
describe this generator and solver on this machine.

## Four-algorithm evaluation study

Run Basic GA, GA with domain filtering, GA with dynamic mutation, and the
existing hybrid algorithm on the same twelve full-board sizes:

```powershell
& 'D:\anaconda3\python.exe' compare_algorithms.py --algorithms basic domain_filtering dynamic_mutation ours --output-dir algorithm_comparison_four
```

This defaults to one trial per size at seed 42, population 160, and 1,500 GA
generations. Existing `benchmark_results/<size>/seed_42/puzzle.json` inputs are
reused when present. Every algorithm receives the same puzzle for a size/seed,
and a hash records that pairing. Trials use fresh Python processes sequentially;
the order rotates between sizes. Each trial has a 120-second wall-clock limit.

- **Basic GA:** cell-level genes with digits 1-9, uniform crossover, fixed 0.25
  chance of mutating one cell, selection and elitism; no exact fallback.
- **Domain filtering:** Basic GA with allowed cell digits narrowed by iterative
  constraint propagation before search. Fixed mutation remains unchanged.
- **Dynamic mutation:** Basic GA with mutation probability rising from 0.25 to
  0.90 with stagnation. This variant does not use domain filtering.
- **Our algorithm:** the existing domain-indexed, run-preserving GA with
  propagation, adaptive conflict-focused mutation, restarts, and exact fallback.

The saved original results in `algorithm_comparison/` include `study.md`, `study.json`, paired puzzle
files, and a result per algorithm. Metrics distinguish the best GA candidate
from the final post-fallback result, and include preprocessing/GA/fallback times,
fitness evaluations, failed backtracking branches, domain reduction, and the
percentage of clue runs that satisfy both sum and distinctness requirements.
A fully assigned but invalid board counts as unsolved. Fitness histories are
retained in each result JSON. The original solver's default behavior is unchanged;
its optional `diagnostics` argument observes the search without changing RNG use.

The three baselines are independent comparisons with Basic GA. The hybrid
changes several mechanisms and can spend additional effort on exact search,
so final hybrid success must not be presented as GA-only success. A faster
unsuccessful search is not a faster solution. One instance per size supports a
descriptive study, not statistical claims about general performance.

For five seeds per size later, or to resume an interrupted unchanged study:

```powershell
& 'D:\anaconda3\python.exe' compare_algorithms.py --algorithms basic domain_filtering dynamic_mutation ours --trials 5 --output-dir algorithm_comparison_5_runs
```

Resume checks source hashes, settings, and puzzle hashes before reusing completed
trials. Timeout/error trials are retried; completed unsolved trials are retained.

## Six-algorithm study: Constraint Search and CP-SAT

The comparison now also supports two standalone exact solvers:

- **Constraint Search:** clue-based propagation followed by minimum-remaining-values
  backtracking, deterministic ascending digit choices, and propagation after each
  decision. It starts directly with exact search, without a GA phase.
- **CP-SAT:** a genuine Google OR-Tools model with one integer variable in 1-9 per
  white cell and a sum equality plus `AllDifferent` for every across/down run.
  It uses one search worker and seed 42, with no solution hints or generator witness.

Setup on this machine (the project-local `.venv` is already installed):

```powershell
& 'D:\anaconda3\python.exe' -m venv .venv
& '.\.venv\Scripts\python.exe' -I -m pip install -r requirements-lock.txt
& '.\.venv\Scripts\python.exe' -E -s -m unittest -v
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py
```

`requirements.txt` pins OR-Tools 9.15.6755; `requirements-lock.txt` records all
installed dependency versions for reproducing this study. The Python flags exclude
ambient Python path/user-site settings from the benchmark environment. The global
Anaconda installation is not modified.

The default is all six methods, one trial per size, complete-board dimensions,
population 160 and 1,500 generations for GAs, and a 120-second wall-clock guard
per process. Exact solvers also have an internal time limit. Trials run sequentially
in fresh processes on identical saved puzzles. Results go to
`algorithm_comparison_six/study.md` and `study.json`; previous four-method results
are preserved.

Timing includes constraint preprocessing or CP model construction and actual search,
but excludes library import, puzzle parsing, final output validation, and file I/O.
Exact methods have **N/A**, not invented zero counts, for GA generations and fitness
evaluations. Constraint-search branches count attempted digit assignments; its
backtracks count rejected branches. CP-SAT branches and conflicts are native solver
statistics and are different units. CP-SAT backtracking count is therefore **N/A**.

Only `SOLVED` (custom search) or `FEASIBLE`/`OPTIMAL` (CP-SAT) with a validated
assignment count as solved. `INFEASIBLE` is proof that no solution exists; `UNKNOWN`
or an outer-process timeout is not. CP-SAT has no optimization objective here, and
an `OPTIMAL` status does not prove uniqueness. See the
[official CP-SAT documentation](https://developers.google.com/optimization/cp/cp_solver).

The hybrid's fallback starts from the propagated domains without using its best
GA candidate. Standalone constraint search therefore tests the cost of doing that
exact search directly. Compare final validity along with time; failed GAs ending
their budgets early are not faster solutions.

To run only the two new solvers, use five seeds, or resume an unchanged study:

```powershell
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py --algorithms constraint_search cp_sat --output-dir exact_comparison
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py --trials 5 --output-dir algorithm_comparison_six_5_runs
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py --resume
```

## RoundingSat versus our hybrid

`kakuro_roundingsat.py` runs the actual [RoundingSat solver](https://gitlab.com/MIAOresearch/software/roundingsat)
as a native process. Each white cell has nine Boolean digit indicators. The OPB
model enforces exactly one digit per cell, the clue sum for every run, and at most
one occurrence of each digit in a run. It uses no generator witness or solution hint.

The verified Windows x64 executable is installed at
`tools/roundingsat/roundingsat.exe`. Its source commit, download URL, SHA-256,
native settings, and license information are recorded in
`tools/roundingsat/manifest.json`. For another installation, set `ROUNDINGSAT_BIN`
to the executable path. RoundingSat is optional: the existing default comparison
still selects the previous six algorithms.

```powershell
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py --algorithms ours roundingsat --output-dir roundingsat_comparison
```

This compares one run per size, seed 42, on the same 12 complete-board sizes and
saved puzzles used previously. Our hybrid keeps its population of 160 and limit
of 1,500 GA generations before exact fallback. The solving budget is 120 seconds;
RoundingSat has an additional five-second outer cleanup guard, without increasing
its internal solving budget. Both methods run sequentially in fresh processes.
RoundingSat uses LP ratio 1 and has no random-seed option. Seed 42 selects the
puzzle and the hybrid's random stream.

Results are saved in `roundingsat_comparison/study.md` and `study.json`.
The completed one-seed study is summarized in
[RoundingSat versus our hybrid](roundingsat_comparison/comparison.md).

Each size/seed directory also retains the OPB model, native stdout/stderr, exact command,
decoded solution, and binary fingerprint. Every returned solution is independently
checked against all original Kakuro rules. Native UNSAT is recorded separately from
a timeout; proof logging and proof checking are not enabled in this comparison.

The main time includes OPB construction, file I/O, native process startup, search,
and decoding for RoundingSat, and preprocessing, GA, and fallback for our hybrid.
The report additionally compares complete worker wall times, including Python
startup and result writing. RoundingSat's native `cpu time` statistic is coarse on
Windows and is not used for the main speed comparison. Native decisions, conflicts,
and propagations are separate from GA fitness evaluations and hybrid backtracks;
inapplicable metrics are N/A. One seed per size gives a descriptive comparison,
not a statistical performance claim.

To expand to five seeds later, or resume this unchanged two-method study:

```powershell
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py --algorithms ours roundingsat --trials 5 --output-dir roundingsat_comparison_5_runs
& '.\.venv\Scripts\python.exe' -E -s compare_algorithms.py --algorithms ours roundingsat --output-dir roundingsat_comparison --resume
```
