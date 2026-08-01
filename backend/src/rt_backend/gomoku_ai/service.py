"""Pattern-evaluation + 1-ply lookahead for the Gomoku engine.

The scoring table is calibrated so a single open-3 (50) is worth less than a
closed-4 (1000) and far less than an open-4 (10000), mirroring the rough
hierarchy used in classic gomoku AIs: < 100 = noise, 100..1000 = a real
threat, > 1000 = the opponent must answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .board import (
    CENTER,
    DIRECTIONS,
    EMPTY,
    WIN_LEN,
    has_any_stone,
    legal_moves,
    line_at,
    opponent,
    would_complete_opp_win,
    would_win,
)

# (run_length, open_ends) -> score. open_ends in {0, 1, 2}.
# Runs of 5+ are the winning line, scored high enough to dominate everything.
PATTERN_SCORE: dict[Tuple[int, int], int] = {
    (1, 0): 1,
    (1, 1): 2,
    (2, 0): 5,
    (2, 1): 10,
    (2, 2): 15,
    (3, 0): 20,
    (3, 1): 50,
    (3, 2): 110,
    (4, 0): 100,
    (4, 1): 1000,
    (4, 2): 10000,
    (5, 0): 100000,
    (5, 1): 100000,
    (5, 2): 100000,
    (6, 0): 100000,
    (6, 1): 100000,
    (6, 2): 100000,
}

# Minimum "threat" threshold for a move: if scoring below this, the move is
# noise and the engine will only pick it after all threats are exhausted.
THREAT_FLOOR = 50

# How heavily the opponent's best response weighs against our move in the
# 1-ply lookahead. The opponent's score is multiplied by this.
OPP_WEIGHT = 1.2

# Cap on candidates for the 1-ply lookahead pass.
LOOKAHEAD_K = 6
STRONG_BEAM = 12

# Strength tiers: 1=弱, 2=中, 3=强.
STRENGTH_MIN = 1
STRENGTH_MAX = 3
_BEAM_BY_STRENGTH = {1: 6, 2: LOOKAHEAD_K, 3: STRONG_BEAM}
# 弱 does no 1-ply lookahead (pure greedy on forced tactics + static eval).
_LOOKAHEAD_BY_STRENGTH = {1: False, 2: True, 3: True}


@dataclass(frozen=True)
class Move:
    row: int
    col: int
    score: int
    winning: bool
    blocks: bool


def _score_at(board, r: int, c: int, player: int) -> int:
    """Score of hypothetically placing `player`'s stone at (r, c).

    Sums the pattern score across all four directions.
    """
    total = 0
    for dr, dc in DIRECTIONS:
        length, open_ends = line_at(board, r, c, dr, dc, player)
        if length >= WIN_LEN:
            return PATTERN_SCORE[(5, 0)]
        total += PATTERN_SCORE.get((length, open_ends), 0)
    return total


def _static_eval(board, r: int, c: int, player: int) -> int:
    """Combined static score: my offensive potential + half the opponent's
    threat that this move would close."""
    opp = opponent(player)
    my = _score_at(board, r, c, player)
    theirs = _score_at(board, r, c, opp)
    return my + theirs // 2


def _candidate(board, r: int, c: int, player: int) -> Move:
    if would_win(board, r, c, player):
        return Move(r, c, PATTERN_SCORE[(5, 0)], winning=True, blocks=False)
    blocks = would_complete_opp_win(board, r, c, opponent(player))
    return Move(
        r,
        c,
        _static_eval(board, r, c, player),
        winning=False,
        blocks=blocks,
    )


def _best_response(board, r: int, c: int, player: int) -> int:
    """Score of `player`'s best response after (r, c) is filled with the
    opponent. Used as the second-half of the 1-ply score."""
    board[r][c] = player
    try:
        best = -1
        for nr, nc in legal_moves(board):
            best = max(best, _static_eval(board, nr, nc, player))
        return best
    finally:
        board[r][c] = EMPTY


def _ranked_candidates(board, to_move: int) -> List[Tuple[int, Move]]:
    """Static-eval ranking of all legal moves for ``to_move``.

    If the opponent has any 5-threat (a cell where they would complete five),
    the candidate pool is *restricted* to the blocking cells — gomoku forces
    the answer there at every strength level. Otherwise the whole legal-move
    set is ranked. Sorted by static score, descending.
    """
    opp = opponent(to_move)
    moves = legal_moves(board)
    block_cells = [(r, c) for r, c in moves if would_complete_opp_win(board, r, c, opp)]
    pool = block_cells if block_cells else moves
    ranked = [(_static_eval(board, r, c, to_move), _candidate(board, r, c, to_move)) for r, c in pool]
    ranked.sort(key=lambda t: t[0], reverse=True)
    return ranked


def _lookahead_pick(board, to_move: int, ranked: List[Tuple[int, Move]], beam: int) -> Move:
    """1-ply lookahead over the top-``beam`` static candidates.

    For each candidate we simulate the move, read the opponent's best static
    reply, and pick the move maximising ``my_score - opp_reply * OPP_WEIGHT``
    (with a center-distance tiebreak for determinism).
    """
    opp = opponent(to_move)
    top = [m for _, m in ranked[:beam]]
    best: Move | None = None
    best_total = -(10 ** 9)
    for m in top:
        board[m.row][m.col] = to_move
        try:
            reply = _best_response(board, m.row, m.col, opp)
        finally:
            board[m.row][m.col] = EMPTY
        total = m.score - int(reply * OPP_WEIGHT)
        total -= abs(m.row - CENTER) + abs(m.col - CENTER)
        if total > best_total:
            best_total = total
            best = m
    assert best is not None
    return best


def best_move(board, to_move: int, strength: int = 2) -> Move:
    """Best move for ``to_move`` on ``board`` at the given ``strength`` tier.

    All tiers share: empty board → center; any immediate win is taken; a
    forced block (opponent 5-threat) restricts the candidate pool.

    - strength 1 (弱): greedy static pick, no lookahead.
    - strength 2 (中): 1-ply lookahead, beam 6.
    - strength 3 (强): 1-ply lookahead, beam 12.
    """
    if to_move not in (1, 2):
        raise ValueError(f"to_move must be 1 (black) or 2 (white), got {to_move!r}")
    if strength < STRENGTH_MIN or strength > STRENGTH_MAX:
        raise ValueError(f"strength must be {STRENGTH_MIN}..{STRENGTH_MAX}, got {strength!r}")

    if not has_any_stone(board):
        return Move(CENTER, CENTER, 0, winning=False, blocks=False)

    # Pass 1: any immediate win?
    for r, c in legal_moves(board):
        if would_win(board, r, c, to_move):
            return Move(r, c, PATTERN_SCORE[(5, 0)], winning=True, blocks=False)

    ranked = _ranked_candidates(board, to_move)
    if not _LOOKAHEAD_BY_STRENGTH[strength]:
        return ranked[0][1]
    return _lookahead_pick(board, to_move, ranked, _BEAM_BY_STRENGTH[strength])


def top_moves(board, to_move: int, k: int = 3, strength: int = 2) -> List[Move]:
    """Return up to ``k`` best candidates for the response payload.

    On an empty board the only legal move is the center; we pad the result
    with that same move so the response always has ``k`` entries.
    """
    if not has_any_stone(board):
        center = Move(CENTER, CENTER, 0, winning=False, blocks=False)
        return [center] * k

    # Immediate win short-circuits the candidate set to that single move.
    for r, c in legal_moves(board):
        if would_win(board, r, c, to_move):
            win = Move(r, c, PATTERN_SCORE[(5, 0)], winning=True, blocks=False)
            return [win] + [win] * (k - 1)

    ranked = _ranked_candidates(board, to_move)
    if not _LOOKAHEAD_BY_STRENGTH[strength]:
        return [m for _, m in ranked[:k]]

    # Re-rank the top-(beam) by lookahead score, then return the first ``k``.
    refined = _lookahead_ranked(board, to_move, ranked, _BEAM_BY_STRENGTH[strength])
    return [m for _, m in refined[:k]]


def _lookahead_ranked(board, to_move: int, ranked: List[Tuple[int, Move]], beam: int) -> List[Tuple[int, Move]]:
    """Same as ``_lookahead_pick`` but returns the full scored list (for top_moves)."""
    opp = opponent(to_move)
    refined: List[Tuple[int, Move]] = []
    for m in [mv for _, mv in ranked[:beam]]:
        board[m.row][m.col] = to_move
        try:
            reply = _best_response(board, m.row, m.col, opp)
        finally:
            board[m.row][m.col] = EMPTY
        total = m.score - int(reply * OPP_WEIGHT)
        total -= abs(m.row - CENTER) + abs(m.col - CENTER)
        refined.append((total, m))
    refined.sort(key=lambda t: t[0], reverse=True)
    return refined
