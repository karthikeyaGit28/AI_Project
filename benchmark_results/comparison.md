# Kakuro grid-size comparison

Seeds: 42. Population: 160. GA budget: 1500 generations, then exact backtracking fallback.

Dimensions are rows x columns; they include all clue borders and internal blocks. A listed 4x4 puzzle is a 4x4 JSON board.

Each seed generates a separate solvable puzzle. Trials run sequentially in fresh Python processes. Times are solver-reported and exclude generation, parsing, validation, file I/O, and process startup. Means below cover completed, independently validated trials only; Valid/Trials shows their coverage. Timeouts and errors are retained in the JSON.

| Grid | White cells (mean) | Time (s, mean) | Backtracks (mean) | GA evaluations (mean) | GA / fallback | Valid / trials | Validity |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4x4 | 9.00 | 0.0058 | 0.00 | 320.00 | 1 / 0 | 1 / 1 | 100.0% |
| 5x5 | 12.00 | 0.0178 | 0.00 | 480.00 | 1 / 0 | 1 / 1 | 100.0% |
| 6x6 | 21.00 | 0.3049 | 0.00 | 11,360.00 | 1 / 0 | 1 / 1 | 100.0% |
| 8x8 | 39.00 | 10.7155 | 0.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 10x10 | 67.00 | 15.8869 | 1.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 12x12 | 97.00 | 22.7624 | 370.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 15x15 | 156.00 | 34.5824 | 5.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 16x16 | 181.00 | 66.9095 | 7,774.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 11x17 | 128.00 | 31.6921 | 995.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 13x17 | 152.00 | 75.1105 | 11,139.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 14x14 | 137.00 | 32.2675 | 72.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |
| 14x17 | 164.00 | 35.1594 | 3.00 | 240,000.00 | 0 / 1 | 1 / 1 | 100.0% |

GA / fallback counts how many trials each method solved. A zero backtracking count means no failed branches, and can still occur when fallback was used.

These are measurements of generated examples, not a calibrated difficulty benchmark. Layout, run lengths, and clue tightness affect runtime; size alone does not determine difficulty. Unique solutions are not guaranteed. Raw trial metrics, white-cell ranges, time ranges, environment, and source hashes are recorded in comparison.json.
