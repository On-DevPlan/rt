"""Board geometry and move-iteration utilities for the Gomoku engine.

Pure functions; no FastAPI, no Pydantic.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

SIZE = 15
CENTER = SIZE // 2

WIN_LEN = 5
DIRECTIONS: Tuple[Tuple[int, int], ...] = ((1, 0), (0, 1), (1, 1), (1, -1))

BLACK = 1
WHITE = 2
EMPTY = 0

PLAYER_TO_GLYPH = {BLACK: "●", WHITE: "○"}


def opponent(player: int) -> int:
    return 3 - player


def on_board(r: int, c: int) -> bool:
    return 0 <= r < SIZE and 0 <= c < SIZE


def has_any_stone(board) -> bool:
    return any(any(cell != EMPTY for cell in row) for row in board)


def _empty_neighbors(board, r: int, c: int, radius: int = 2) -> bool:
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            nr, nc = r + dr, c + dc
            if 0 <= nr < SIZE and 0 <= nc < SIZE and board[nr][nc] != EMPTY:
                return True
    return False


def legal_moves(board) -> List[Tuple[int, int]]:
    """All empty cells within 2 squares of an existing stone.

    On an empty board, return only the center — otherwise we'd generate 225
    moves with no signal.
    """
    if not has_any_stone(board):
        return [(CENTER, CENTER)]
    moves: List[Tuple[int, int]] = []
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] == EMPTY and _empty_neighbors(board, r, c):
                moves.append((r, c))
    return moves


def _run_with_hypothetical(board, r: int, c: int, dr: int, dc: int, player: int) -> Tuple[int, int, int]:
    """Treat (r, c) as if it held ``player``'s stone and walk in both
    directions to count the run length and its open ends.

    Returns ``(length, open_fwd, open_back)``. The cell at (r, c) is the
    "anchor" of the run and is counted as one of ``player``'s stones even
    if it's actually empty. No mutations to the board.
    """
    anchor_is_player = True

    def is_match(nr, nc) -> bool:
        if nr == r and nc == c:
            return anchor_is_player
        return on_board(nr, nc) and board[nr][nc] == player

    fwd = 0
    nr, nc = r + dr, c + dc
    while is_match(nr, nc):
        fwd += 1
        nr, nc = nr + dr, nc + dc
    open_fwd = 1 if on_board(nr, nc) and board[nr][nc] == EMPTY else 0

    back = 0
    nr, nc = r - dr, c - dc
    while is_match(nr, nc):
        back += 1
        nr, nc = nr - dr, nc - dc
    open_back = 1 if on_board(nr, nc) and board[nr][nc] == EMPTY else 0

    return fwd + back + 1, open_fwd, open_back


def line_at(board, r: int, c: int, dr: int, dc: int, player: int) -> Tuple[int, int]:
    """Like ``_run_with_hypothetical`` but returns ``(length, open_ends)``.

    Used by the pattern scorer to evaluate how good a move at (r, c) is for
    ``player``. The board cell at (r, c) is treated as belonging to
    ``player`` for the length calculation, even if it's actually empty.
    """
    length, open_fwd, open_back = _run_with_hypothetical(board, r, c, dr, dc, player)
    return length, open_fwd + open_back


def would_win(board, r: int, c: int, player: int) -> bool:
    """True if placing ``player``'s stone at (r, c) completes a 5-in-a-row."""
    for dr, dc in DIRECTIONS:
        length, _, _ = _run_with_hypothetical(board, r, c, dr, dc, player)
        if length >= WIN_LEN:
            return True
    return False


def would_complete_opp_win(board, r: int, c: int, opp: int) -> bool:
    """True if ``opp`` would win by playing at (r, c). Used to detect a
    block-now requirement: if we leave (r, c) empty, opponent could win
    there on their next move, so we must answer there."""
    for dr, dc in DIRECTIONS:
        length, _, _ = _run_with_hypothetical(board, r, c, dr, dc, opp)
        if length >= WIN_LEN:
            return True
    return False
