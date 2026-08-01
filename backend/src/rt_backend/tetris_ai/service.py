"""Placement search and key-sequence planning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .board import (
    DEFAULT_WEIGHTS,
    Metrics,
    Rows,
    apply_placement,
    evaluate,
)
from .pieces import distinct_rotations, normalize_piece, rotation_states, spawn_x


class NoPlacementError(RuntimeError):
    """No legal placement exists — the client should treat this as game over."""


@dataclass(frozen=True)
class Placement:
    rotation: int
    x: int
    y: int
    cleared_lines: int
    score: float
    metrics: Metrics


def _landing_y(rows: Rows, cells: Sequence[Tuple[int, int]], x0: int) -> Optional[int]:
    """Lowest ``y0`` at which the piece rests, or ``None`` if it cannot be placed.

    Uses per-column contact points: for each column of the piece, the deepest
    cell in that column determines how far it may fall before hitting the stack.
    The candidate also passes a full overlap check against the stack at every
    step of the descent so we never let the piece tunnel through a buried
    block on the way down.
    """
    height = len(rows)

    # Deepest piece cell per column (dx -> max dy).
    bottoms: dict[int, int] = {}
    for dx, dy in cells:
        if dy > bottoms.get(dx, -1):
            bottoms[dx] = dy

    drop = height  # max rows the piece may descend from y0 = 0
    for dx, bottom_dy in bottoms.items():
        x = x0 + dx
        # First occupied row in this column at or below the piece's bottom cell.
        limit = height
        for y in range(bottom_dy, height):
            if (rows[y] >> x) & 1:
                limit = y
                break
        drop = min(drop, limit - bottom_dy - 1)

    if drop < 0:
        return None

    # Final overlap check: the resting position must not collide with the stack.
    piece_mask_by_row: dict[int, int] = {}
    for dx, dy in cells:
        y = drop + dy
        piece_mask_by_row[y] = piece_mask_by_row.get(y, 0) | (1 << (x0 + dx))
    for y, mask in piece_mask_by_row.items():
        if (rows[y] & mask) != 0:
            return None
    return drop


def _candidates(rows: Rows, width: int, piece: str):
    """Yield every legal ``(rotation, x0, y0, cells)`` landing for ``piece``."""
    states = rotation_states(piece)
    for rotation in distinct_rotations(piece):
        cells = states[rotation]
        piece_w = max(dx for dx, _ in cells) + 1
        for x0 in range(0, width - piece_w + 1):
            y0 = _landing_y(rows, cells, x0)
            if y0 is None:
                continue
            yield rotation, x0, y0, cells


def best_placement(
    rows: Rows,
    width: int,
    piece: str,
    next_piece: Optional[str] = None,
    weights: Optional[dict] = None,
) -> Placement:
    """Brute-force the best landing for ``piece``, optionally 1 piece deep.

    With ``next_piece`` given, each candidate is scored by the *best* follow-up
    placement of the next piece, which is what makes the bot avoid setups that
    only look good for one move.
    """
    piece = normalize_piece(piece)
    w = weights or DEFAULT_WEIGHTS
    next_norm = normalize_piece(next_piece) if next_piece else None

    best: Optional[Placement] = None
    best_score = float("-inf")

    for rotation, x0, y0, cells in _candidates(rows, width, piece):
        after, metrics = apply_placement(rows, width, cells, x0, y0)
        score = evaluate(metrics, w)

        if next_norm is not None:
            lookahead = float("-inf")
            for _, n_x, n_y, n_cells in _candidates(after, width, next_norm):
                _, n_metrics = apply_placement(after, width, n_cells, n_x, n_y)
                n_score = evaluate(n_metrics, w)
                if n_score > lookahead:
                    lookahead = n_score
            # No legal follow-up means this placement tops the board out.
            score = score + lookahead if lookahead != float("-inf") else float("-inf")

        if score > best_score:
            best_score = score
            best = Placement(
                rotation=rotation,
                x=x0,
                y=y0,
                cleared_lines=metrics.cleared_lines,
                score=score,
                metrics=metrics,
            )

    if best is None:
        raise NoPlacementError("当前方块无合法落点，游戏已结束")
    return best


def plan_moves(
    piece: str,
    target_rotation: int,
    target_x: int,
    width: int,
    current_x: Optional[int] = None,
    current_rotation: int = 0,
) -> List[str]:
    """Translate a target landing into a key sequence.

    Rotations are emitted first (clockwise, since that is the single rotate key
    most clients bind), then horizontal moves, then a hard drop. ``current_x``
    is the piece's current leftmost column; when omitted the spawn position is
    assumed.

    Note this assumes the piece can rotate freely at spawn height and travel
    horizontally without obstruction — true for the top few rows of a standard
    board, which is where a piece lives before it is dropped.
    """
    piece = normalize_piece(piece)
    rotations = (target_rotation - current_rotation) % 4

    if current_x is None:
        current_x = spawn_x(piece, width, current_rotation)

    moves: List[str] = ["rotate"] * rotations

    # Rotating around the bounding-box top-left can push the piece off the right
    # edge; clamp the pre-move column the same way a client's kick would.
    from .pieces import piece_width

    max_x = width - piece_width(piece, target_rotation)
    start_x = min(current_x, max_x) if max_x >= 0 else 0

    delta = target_x - start_x
    moves += ["left"] * (-delta) if delta < 0 else ["right"] * delta
    moves.append("hard_drop")
    return moves
