"""Board representation and Dellacherie evaluation.

The board is stored as a list of row bitmasks (``rows[0]`` is the top row, bit
``x`` set means the cell at column ``x`` is occupied). Bit tricks keep the
evaluation cheap enough to brute-force ~1600 two-piece placements per request in
pure Python.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

Rows = List[int]

# Empty-cell markers accepted when a client uploads the board as a matrix.
_EMPTY_TOKENS = {0, "0", ".", " ", "", "_", None, False}


class BoardError(ValueError):
    """Raised when the uploaded board cannot be interpreted."""


def parse_board(board: Sequence, width: int | None = None) -> Tuple[Rows, int]:
    """Normalize a client-uploaded board into ``(row_bitmasks, width)``.

    Accepts either a list of strings (``"..##......"``) or a list of rows of
    ints/bools, where any value in :data:`_EMPTY_TOKENS` counts as empty and
    everything else counts as occupied.
    """
    if not board:
        raise BoardError("board 不能为空")

    parsed: Rows = []
    detected_width = width

    for y, row in enumerate(board):
        if isinstance(row, str):
            cells: Sequence = tuple(row)
        elif isinstance(row, (list, tuple)):
            cells = row
        else:
            raise BoardError(f"board[{y}] 必须是字符串或数组，得到 {type(row).__name__}")

        if detected_width is None:
            detected_width = len(cells)
        if len(cells) != detected_width:
            raise BoardError(
                f"board[{y}] 长度为 {len(cells)}，与首行宽度 {detected_width} 不一致"
            )

        mask = 0
        for x, cell in enumerate(cells):
            if isinstance(cell, str):
                filled = cell not in _EMPTY_TOKENS
            else:
                filled = bool(cell) and cell not in _EMPTY_TOKENS
            if filled:
                mask |= 1 << x
        parsed.append(mask)

    assert detected_width is not None
    if detected_width < 4:
        raise BoardError(f"board 宽度至少为 4，得到 {detected_width}")
    if detected_width > 32:
        raise BoardError(f"board 宽度最多为 32，得到 {detected_width}")
    return parsed, detected_width


def rows_to_matrix(rows: Rows, width: int) -> List[List[int]]:
    """Inverse of :func:`parse_board` (1 = occupied). Used for debug output."""
    return [[(r >> x) & 1 for x in range(width)] for r in rows]


def column_tops(rows: Rows, width: int) -> List[int]:
    """For each column, the index of its topmost occupied row (``len(rows)`` if empty)."""
    height = len(rows)
    tops = [height] * width
    remaining = width
    for y, mask in enumerate(rows):
        if not mask:
            continue
        m = mask
        while m:
            bit = m & -m
            x = bit.bit_length() - 1
            if tops[x] == height:
                tops[x] = y
                remaining -= 1
            m ^= bit
        if remaining == 0:
            break
    return tops


@dataclass(frozen=True)
class Metrics:
    """The six Dellacherie features of a board after a placement."""

    landing_height: float
    eroded_piece_cells: int
    row_transitions: int
    column_transitions: int
    holes: int
    wells: int
    cleared_lines: int


# Pierre Dellacherie's weights, in the widely used El-Tetris normalization.
DEFAULT_WEIGHTS: dict[str, float] = {
    "landing_height": -4.500158825082766,
    "eroded_piece_cells": 3.4181268101392694,
    "row_transitions": -3.2178882868487753,
    "column_transitions": -9.348695305445199,
    "holes": -7.899265427351652,
    "wells": -3.3855972247263626,
}


def evaluate(metrics: Metrics, weights: dict[str, float] | None = None) -> float:
    """Linear combination of the six features. Higher is better."""
    w = weights or DEFAULT_WEIGHTS
    return (
        w["landing_height"] * metrics.landing_height
        + w["eroded_piece_cells"] * metrics.eroded_piece_cells
        + w["row_transitions"] * metrics.row_transitions
        + w["column_transitions"] * metrics.column_transitions
        + w["holes"] * metrics.holes
        + w["wells"] * metrics.wells
    )


def _row_transitions(rows: Rows, width: int, full: int) -> int:
    """Horizontal filled<->empty flips, counting both side walls as filled.

    Rows entirely above the stack are skipped: they are identical for every
    candidate placement of a given piece except for line-clear effects, and
    counting them would make an empty board look worse than a filled one.
    """
    total = 0
    top_bit = 1 << (width - 1)
    started = False
    for mask in rows:
        if not mask:
            if not started:
                continue
            # An empty row below the stack still counts (two wall transitions).
            total += 2
            continue
        started = True
        # XOR each cell against its left neighbour; the left wall counts as filled.
        total += bin((mask ^ ((mask << 1) | 1)) & full).count("1")
        if not mask & top_bit:
            total += 1  # right wall
    return total


def _column_transitions(rows: Rows, full: int) -> int:
    """Vertical flips, counting above-the-board as empty and the floor as filled."""
    total = bin(rows[0]).count("1")  # empty sky -> first row
    for y in range(len(rows) - 1):
        total += bin(rows[y] ^ rows[y + 1]).count("1")
    total += bin(~rows[-1] & full).count("1")  # last row -> solid floor
    return total


def _holes(rows: Rows, full: int) -> int:
    """Empty cells that have at least one occupied cell somewhere above them."""
    total = 0
    filled_above = 0
    for mask in rows:
        if filled_above:
            total += bin(filled_above & ~mask & full).count("1")
        filled_above |= mask
    return total


def _wells(rows: Rows, width: int, full: int) -> int:
    """Sum of 1+2+...+depth over every well (empty column notch walled on both sides)."""
    total = 0
    left_wall = 1  # column -1 is treated as occupied
    right_wall = 1 << (width - 1)
    depth: dict[int, int] = {}
    for mask in rows:
        # Empty cells whose left AND right neighbours are occupied (walls count).
        well_mask = ~mask & ((mask << 1) | left_wall) & ((mask >> 1) | right_wall) & full
        if not well_mask:
            if depth:
                depth = {}
            continue
        nxt: dict[int, int] = {}
        m = well_mask
        while m:
            bit = m & -m
            x = bit.bit_length() - 1
            d = depth.get(x, 0) + 1
            nxt[x] = d
            total += d
            m ^= bit
        depth = nxt
    return total


def apply_placement(
    rows: Rows,
    width: int,
    cells: Iterable[Tuple[int, int]],
    x0: int,
    y0: int,
) -> Tuple[Rows, Metrics]:
    """Stamp ``cells`` at ``(x0, y0)``, clear full lines, and measure the result.

    ``cells`` are normalized ``(dx, dy)`` offsets; ``(x0, y0)`` is the top-left
    corner of the piece's bounding box. The caller is responsible for having
    computed a landing position that neither overlaps nor leaves the board.
    """
    height = len(rows)
    full = (1 << width) - 1

    new_rows = list(rows)
    piece_rows: dict[int, int] = {}
    min_y = height
    max_y = -1
    for dx, dy in cells:
        y = y0 + dy
        piece_rows[y] = piece_rows.get(y, 0) | (1 << (x0 + dx))
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
    for y, mask in piece_rows.items():
        new_rows[y] |= mask

    cleared_rows = [y for y in piece_rows if new_rows[y] == full]
    cleared_lines = len(cleared_rows)
    eroded = 0
    if cleared_lines:
        eroded = cleared_lines * sum(
            bin(piece_rows[y]).count("1") for y in cleared_rows
        )
        keep = [new_rows[y] for y in range(height) if new_rows[y] != full]
        new_rows = [0] * (height - len(keep)) + keep

    # Height of the piece's centre above the floor, measured before line clears.
    landing_height = height - (min_y + max_y) / 2.0

    metrics = Metrics(
        landing_height=landing_height,
        eroded_piece_cells=eroded,
        row_transitions=_row_transitions(new_rows, width, full),
        column_transitions=_column_transitions(new_rows, full),
        holes=_holes(new_rows, full),
        wells=_wells(new_rows, width, full),
        cleared_lines=cleared_lines,
    )
    return new_rows, metrics
