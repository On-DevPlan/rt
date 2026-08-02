"""Tests for the Rapfi subprocess driver: protocol encoding/parsing,
subprocess round-trip, availability probe, circuit breaker.

Uses a mock pbrain script (no real Rapfi binary) so tests are deterministic
and run anywhere (including CI without AVX2).
"""
import asyncio
import os
import sys
import textwrap

import pytest

from rt_backend.gomoku_ai import rapfi
from rt_backend.gomoku_ai.rapfi import (
    RapfiMove,
    RapfiUnavailable,
    board_to_gomocup_lines,
    get_model_dir,
    get_rapfi_command,
    parse_gomocup_move,
)


# --- pure helpers ---------------------------------------------------------

def test_encode_to_move_becomes_color_one():
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1   # black
    board[7][8] = 2   # white
    lines = board_to_gomocup_lines(board, to_move=1)  # engine = black
    assert "7,7,1" in lines      # black -> color 1
    assert "8,7,2" in lines      # x=col=8, y=row=7, white -> color 2


def test_encode_to_move_white_swaps_colors():
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    board[7][8] = 2
    lines = board_to_gomocup_lines(board, to_move=2)  # engine = white
    assert "8,7,1" in lines      # white -> color 1
    assert "7,7,2" in lines      # black -> color 2


def test_encode_skips_empty_cells():
    board = [[0] * 15 for _ in range(15)]
    board[0][0] = 1
    lines = board_to_gomocup_lines(board, to_move=1)
    assert lines == ["0,0,1"]


def test_parse_move_returns_row_col_from_xy():
    assert parse_gomocup_move("3,5") == (5, 3)   # x=col=3, y=row=5 -> (row=5,col=3)


def test_parse_move_rejects_non_move_lines():
    for noise in ["", "OK", "UNKNOWN command", "DEBUG depth 4",
                  "INFO something", "MESSAGE hello", "ERROR bad"]:
        assert parse_gomocup_move(noise) is None


def test_parse_move_rejects_out_of_range():
    assert parse_gomocup_move("20,3") is None
    assert parse_gomocup_move("-1,3") is None
