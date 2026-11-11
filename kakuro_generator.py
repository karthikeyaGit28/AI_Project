"""Generate reproducible rectangular Kakuro benchmark instances.

Dimensions include the top and left clue borders. Large boards use 2/3-cell
bands and separated block tiles, keeping every digit run between 2 and 9 cells.
Generated instances are solvable but are not guaranteed to have unique answers.
"""

import random


def _bands(length, rng):
    """Partition a dimension into twos and, for odd lengths, one three."""
    widths = [2] * (length // 2)
    if length % 2:
        widths[-1] += 1
        rng.shuffle(widths)
    result = []
    for index, width in enumerate(widths):
        result.extend([index] * width)
    return result


def _generate_with_witness(rows, columns, seed):
    if type(rows) is not int or type(columns) is not int or rows < 3 or columns < 3:
        raise ValueError("rows and columns must be integers of at least 3, including clue borders")
    rng = random.Random(seed)
    row_bands = _bands(rows - 1, rng)
    column_bands = _bands(columns - 1, rng)
    offset = rng.randrange(5)
    row_coefficient, column_coefficient = rng.choice(((1, 2), (2, 1)))

    # No two blocked tiles touch, even diagonally. Thus the white region is
    # connected when both axes contain at least two bands. A row or column has
    # at most four consecutive white bands: 8 cells, or 9 when it contains the
    # one 3-cell band. Apply the same sparse mask at every size that has two
    # bands per axis. Very narrow boards only need blocks if a run exceeds 9.
    needs_blocks = (rows >= 5 and columns >= 5) or rows > 10 or columns > 10
    white_cells = {
        (r, c)
        for r in range(1, rows)
        for c in range(1, columns)
        if not needs_blocks or (
            row_coefficient * row_bands[r - 1]
            + column_coefficient * column_bands[c - 1] + offset
        ) % 5 != 0
    }
    digits = list(range(1, 10))
    rng.shuffle(digits)
    row_step = rng.choice((1, 2, 4, 5, 7, 8))
    column_step = rng.choice((1, 2, 4, 5, 7, 8))
    phase = rng.randrange(9)
    witness = {
        (r, c): digits[((r - 1) * row_step + (c - 1) * column_step + phase) % 9]
        for r, c in white_cells
    }
    grid = [["#" for _ in range(columns)] for _ in range(rows)]
    for r, c in white_cells:
        grid[r][c] = None
    for r, c in sorted(white_cells):
        for direction, dr, dc in (("across", 0, 1), ("down", 1, 0)):
            clue_r, clue_c = r - dr, c - dc
            if (clue_r, clue_c) in white_cells:
                continue
            rr, cc = r, c
            total = 0
            while (rr, cc) in white_cells:
                total += witness[(rr, cc)]
                rr += dr
                cc += dc
            if grid[clue_r][clue_c] == "#":
                grid[clue_r][clue_c] = {}
            grid[clue_r][clue_c][direction] = total
    puzzle = {
        "format": "kakuro-grid-v1",
        "generator": "rectangular-bands-v1",
        "dimension_convention": "full board including top and left clue borders",
        "rows": rows,
        "columns": columns,
        "seed": seed,
        "grid": grid,
    }
    return puzzle, witness


def generate_rectangular_puzzle(rows, columns, seed):
    """Return a solvable puzzle with exactly ``rows`` by ``columns`` cells.

    For boards with at least two bands on each axis (at least 5 by 5 cells),
    the white region is connected. Very narrow large boards may have separated
    white regions; the benchmark dimensions do not have this limitation.
    """
    return _generate_with_witness(rows, columns, seed)[0]
