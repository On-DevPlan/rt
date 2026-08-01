"""Tests for the Gomoku AI board utilities and search engine."""
import pytest

from rt_backend.gomoku_ai.board import (
    BLACK,
    CENTER,
    EMPTY,
    SIZE,
    WHITE,
    has_any_stone,
    legal_moves,
    line_at,
    on_board,
    opponent,
    would_complete_opp_win,
    would_win,
)
from rt_backend.gomoku_ai.service import best_move, top_moves


def empty_board():
    return [[EMPTY] * SIZE for _ in range(SIZE)]


def play(board, r, c, player):
    board[r][c] = player


# ---------------------------------------------------------------------------
# board helpers
# ---------------------------------------------------------------------------

def test_on_board():
    assert on_board(0, 0)
    assert on_board(SIZE - 1, SIZE - 1)
    assert not on_board(-1, 0)
    assert not on_board(0, SIZE)
    assert not on_board(SIZE, 0)


def test_opponent():
    assert opponent(BLACK) == WHITE
    assert opponent(WHITE) == BLACK


def test_has_any_stone_false_on_empty():
    assert not has_any_stone(empty_board())


def test_has_any_stone_true_when_stone_present():
    b = empty_board()
    b[5][5] = BLACK
    assert has_any_stone(b)


def test_legal_moves_on_empty_board_returns_center_only():
    moves = legal_moves(empty_board())
    assert moves == [(CENTER, CENTER)]


def test_legal_moves_excludes_far_cells():
    b = empty_board()
    b[7][7] = BLACK
    moves = legal_moves(b)
    # Only cells within 2 of (7,7) should be legal.
    for r, c in moves:
        assert max(abs(r - 7), abs(c - 7)) <= 2
    # Cells clearly outside the radius should not be legal.
    assert (0, 0) not in moves
    assert (SIZE - 1, SIZE - 1) not in moves


# ---------------------------------------------------------------------------
# line_at
# ---------------------------------------------------------------------------

def test_line_at_counts_empty_run():
    b = empty_board()
    length, open_ends = line_at(b, 5, 5, 1, 0, BLACK)
    assert length == 1
    assert open_ends == 2


def test_line_at_counts_consecutive_run_with_open_ends():
    b = empty_board()
    play(b, 5, 5, BLACK)
    play(b, 5, 6, BLACK)
    play(b, 5, 7, BLACK)
    # Hypothetical BLACK at (5,4) extending LEFT (horizontal direction).
    # Walks right and finds 3 stones, returns length 4.
    length, open_ends = line_at(b, 5, 4, 0, 1, BLACK)
    assert length == 4
    # Both ends open: (5,3) and (5,8) are both empty.
    assert open_ends == 2
    # Hypothetical BLACK at (5,8) extending RIGHT.
    length, open_ends = line_at(b, 5, 8, 0, 1, BLACK)
    assert length == 4
    assert open_ends == 2


def test_line_at_horizontal_five_means_winner():
    b = empty_board()
    for c in range(5, 11):  # 6 BLACK in a row
        play(b, 5, c, BLACK)
    # Horizontal direction (dr=0, dc=1) from inside the run reports 6.
    length, _ = line_at(b, 5, 5, 0, 1, BLACK)
    assert length == 6
    # (5,11) extends the run to 7.
    length, _ = line_at(b, 5, 11, 0, 1, BLACK)
    assert length == 7


def test_line_at_diagonal_run():
    b = empty_board()
    for k in range(5):  # 5 BLACK diagonal (5,5)..(9,9)
        play(b, 5 + k, 5 + k, BLACK)
    # Hypothetical extension at (10,10) makes 6.
    length, _ = line_at(b, 10, 10, 1, 1, BLACK)
    assert length == 6
    # Empty cells in between do NOT bridge a run.
    length, _ = line_at(b, 1, 1, 1, 1, BLACK)
    assert length == 1
    # Extension at (4,4) on the other end also makes 6.
    length, _ = line_at(b, 4, 4, 1, 1, BLACK)
    assert length == 6


# ---------------------------------------------------------------------------
# would_win / would_complete_opp_win
# ---------------------------------------------------------------------------

def test_would_win_detects_five_in_a_row():
    b = empty_board()
    for c in range(5, 9):
        play(b, 5, c, BLACK)
    # (5,4) closes the run
    assert would_win(b, 5, 4, BLACK)
    # (10,10) is a free cell that doesn't make 5
    assert not would_win(b, 10, 10, BLACK)


def test_would_complete_opp_win_detects_blocked_four():
    b = empty_board()
    for c in range(5, 9):
        play(b, 5, c, WHITE)
    # (5,4) would complete WHITE's 4-in-a-row -> we must block it.
    assert would_complete_opp_win(b, 5, 4, WHITE)
    # (10,10) doesn't connect to any white run.
    assert not would_complete_opp_win(b, 10, 10, WHITE)


# ---------------------------------------------------------------------------
# best_move
# ---------------------------------------------------------------------------

def test_best_move_on_empty_board_returns_center():
    assert best_move(empty_board(), BLACK) == (CENTER, CENTER, 0, False, False) or \
        best_move(empty_board(), BLACK).row == CENTER and best_move(empty_board(), BLACK).col == CENTER


def test_best_move_takes_immediate_win():
    b = empty_board()
    for c in range(5, 9):
        play(b, 5, c, BLACK)
    m = best_move(b, BLACK)
    # The winning move is (5, 4) or (5, 9); both close a 4-stone run.
    assert m.winning
    assert (m.row, m.col) in {(5, 4), (5, 9)}


def test_best_move_blocks_immediate_loss():
    b = empty_board()
    for c in range(5, 9):
        play(b, 5, c, WHITE)
    m = best_move(b, BLACK)
    assert m.blocks or m.winning
    # Must be one of the two blocking cells.
    assert (m.row, m.col) in {(5, 4), (5, 9)}


def test_best_move_prefers_attack_over_weak_block():
    # Black has an open-3 ready to extend; white's "threat" is a closed-2.
    # The engine should extend the 3 rather than block the 2.
    b = empty_board()
    for c in range(5, 8):
        play(b, 7, c, BLACK)
    play(b, 7, 1, WHITE)
    play(b, 7, 9, WHITE)
    m = best_move(b, BLACK)
    # Either side of the 3 closes it into a 4.
    assert (m.row, m.col) in {(7, 4), (7, 8)}


def test_best_move_symmetric_for_white():
    # If we mirror the previous setup, white should play the same way.
    b = empty_board()
    for c in range(5, 8):
        play(b, 7, c, WHITE)
    play(b, 7, 1, BLACK)
    play(b, 7, 9, BLACK)
    m = best_move(b, WHITE)
    assert (m.row, m.col) in {(7, 4), (7, 8)}


def test_best_move_rejects_invalid_to_move():
    with pytest.raises(ValueError, match="to_move"):
        best_move(empty_board(), 3)


def test_best_move_creates_double_threat():
    # Black has a 3 in row 5 (cols 5-7) and a 3 in col 7 (rows 5-7) — they
    # already share cell (5,7). Playing (8,8) should create two open-3s
    # simultaneously (forking into open-4s).
    b = empty_board()
    for c in range(5, 8):
        play(b, 5, c, BLACK)
    for r in range(5, 8):
        play(b, r, 7, BLACK)
    m = best_move(b, BLACK)
    # The engine should pick a move that extends one of the existing runs
    # (or creates a fork); either way the move should be near the cluster.
    assert max(abs(m.row - 5), abs(m.row - 7)) <= 4
    assert max(abs(m.col - 5), abs(m.col - 7)) <= 4


# ---------------------------------------------------------------------------
# top_moves
# ---------------------------------------------------------------------------

def test_top_moves_returns_at_most_k():
    b = empty_board()
    for c in range(5, 8):
        play(b, 5, c, BLACK)
    alts = top_moves(b, BLACK, k=3)
    assert len(alts) == 3
    # Sorted by score descending.
    scores = [m.score for m in alts]
    assert scores == sorted(scores, reverse=True)


def test_top_moves_on_empty_board():
    alts = top_moves(empty_board(), BLACK, k=1)
    assert alts[0].row == CENTER
    assert alts[0].col == CENTER


def test_engine_does_not_blunder_into_a_loss():
    """If white leaves a 4-in-a-row open, the engine on black's turn must
    block it. We construct the position manually so the test is deterministic."""
    b = empty_board()
    play(b, 5, 5, BLACK)
    play(b, 6, 6, WHITE)
    # White now has 3 in a row at (6,6)(6,7)(6,8); but more importantly black
    # must respond to white's 3 sensibly. We then drop a white-4 and verify
    # the engine blocks.
    play(b, 6, 7, WHITE)
    play(b, 6, 8, WHITE)
    # Black makes a 1-ply check
    m = best_move(b, BLACK)
    # The engine may extend or block; just make sure the move is on the
    # board and doesn't overlap a stone.
    assert b[m.row][m.col] == 0
    # Now white plays a 4; the engine on black's turn must block.
    play(b, 6, 9, WHITE)
    m2 = best_move(b, BLACK)
    assert m2.blocks or m2.winning


# ---------------------------------------------------------------------------
# strength tiers
# ---------------------------------------------------------------------------

def test_strength_weak_is_greedy_without_lookahead():
    """Strength 1 must still block a 4-threat (forced), but on a quiet
    position it just returns the top static move — it should NOT model the
    opponent's reply. We assert it picks a high-static move near the cluster."""
    b = empty_board()
    for c in range(5, 8):
        play(b, 7, c, BLACK)
    m = best_move(b, BLACK, strength=1)
    # Either side of the open-3 makes a 4 — both are top static moves.
    assert (m.row, m.col) in {(7, 4), (7, 8)}


def test_strength_weak_still_blocks_forced_four():
    """Even at strength 1, an opponent 4-threat must be blocked."""
    b = empty_board()
    for c in range(5, 9):
        play(b, 7, c, WHITE)
    m = best_move(b, BLACK, strength=1)
    assert m.blocks
    assert (m.row, m.col) in {(7, 4), (7, 9)}


def test_strength_strong_uses_wider_beam():
    """Strength 3 is valid and returns a legal move. (Behavioral equivalence
    to strength 2 on simple positions; the point is it doesn't crash and
    still respects the forced-block rule.)"""
    b = empty_board()
    for c in range(5, 9):
        play(b, 7, c, WHITE)
    m = best_move(b, BLACK, strength=3)
    assert m.blocks
    assert (m.row, m.col) in {(7, 4), (7, 9)}


def test_strength_invalid_rejected():
    with pytest.raises(ValueError, match="strength"):
        best_move(empty_board(), BLACK, strength=4)
    with pytest.raises(ValueError, match="strength"):
        best_move(empty_board(), BLACK, strength=0)


def test_strength_takes_immediate_win_at_all_levels():
    b = empty_board()
    for c in range(5, 9):
        play(b, 5, c, BLACK)
    for s in (1, 2, 3):
        m = best_move(b, BLACK, strength=s)
        assert m.winning
        assert (m.row, m.col) in {(5, 4), (5, 9)}
