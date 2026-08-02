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
    assert "7,7,1" in lines      # black -> color 1 (first player)
    assert "8,7,2" in lines      # x=col=8, y=row=7, white -> color 2


def test_encode_is_fixed_black_color1_white_color2():
    """Piskvork colors are fixed (black=1, white=2), independent of to_move.
    A to_move-relative encoding would put color 1 behind on stones for
    to_move=2, which Rapfi rejects as illegal and never answers."""
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1   # black
    board[7][8] = 2   # white
    lines = board_to_gomocup_lines(board, to_move=2)  # engine = white
    assert "7,7,1" in lines      # black still color 1
    assert "8,7,2" in lines      # white still color 2


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


# --- subprocess driver (mock binary) --------------------------------------
# Mock pbrain scripts: read commands on stdin line-by-line, answer on stdout.
# Using print(..., flush=True) avoids newline-escaping inside the heredoc.

NORMAL_MOCK = """\
import sys
def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        c = line.strip()
        if c.startswith('START'):
            print('OK', flush=True)
        elif c.startswith('INFO'):
            pass
        elif c == 'BOARD':
            n = 0
            while True:
                l = sys.stdin.readline()
                if not l or l.strip() == 'DONE':
                    break
                n += 1
            print('DEBUG saw %d stones' % n, flush=True)
            print('3,3', flush=True)   # x=col=3, y=row=3 -> (row=3,col=3)
        elif c == 'END':
            return
main()
"""

HANG_MOCK = """\
import sys, time
def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        c = line.strip()
        if c.startswith('START'):
            print('OK', flush=True)
        elif c == 'BOARD':
            while True:
                l = sys.stdin.readline()
                if not l or l.strip() == 'DONE':
                    break
            time.sleep(30)   # never answer
        elif c == 'END':
            return
main()
"""

GARBAGE_MOCK = """\
import sys
def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        c = line.strip()
        if c.startswith('START'):
            print('OK', flush=True)
        elif c == 'BOARD':
            while True:
                l = sys.stdin.readline()
                if not l or l.strip() == 'DONE':
                    break
            print('ERROR no weights', flush=True)
            return
        elif c == 'END':
            return
main()
"""


def _write_mock(tmp_path, body: str):
    p = tmp_path / "mock_pbrain.py"
    p.write_text(body, encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _reset_rapfi_state():
    rapfi._reset_state_for_tests()
    yield
    rapfi._reset_state_for_tests()


def _patch_cmd(monkeypatch, mock_path):
    monkeypatch.setattr(rapfi, "get_rapfi_command", lambda: [sys.executable, str(mock_path)])
    monkeypatch.setattr(rapfi, "get_model_dir", lambda: str(mock_path.parent))


async def test_compute_move_round_trip_returns_parsed_move(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, NORMAL_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    mv = await rapfi.compute_move(board, to_move=2, timeout_s=5.0)
    assert isinstance(mv, RapfiMove)
    assert (mv.row, mv.col) == (3, 3)
    assert mv.winning is False
    assert mv.blocks is False


async def test_compute_move_marks_winning(tmp_path, monkeypatch):
    # Mock reports a move at (row=7, col=9) -> Gomocup "x,y" = "9,7".
    winning_mock = NORMAL_MOCK.replace("3,3", "9,7")
    _patch_cmd(monkeypatch, _write_mock(tmp_path, winning_mock))
    board = [[0] * 15 for _ in range(15)]
    for c in range(5, 9):       # black four in a row, col 5..8 at row 7
        board[7][c] = 1
    mv = await rapfi.compute_move(board, to_move=1, timeout_s=5.0)
    assert (mv.row, mv.col) == (7, 9)
    assert mv.winning is True


async def test_compute_move_timeout_raises_unavailable(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, HANG_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    with pytest.raises(RapfiUnavailable):
        await rapfi.compute_move(board, to_move=2, timeout_s=0.5)


async def test_compute_move_no_move_line_raises_unavailable(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, GARBAGE_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    with pytest.raises(RapfiUnavailable):
        await rapfi.compute_move(board, to_move=2, timeout_s=3.0)


async def test_circuit_breaker_trips_after_three_failures(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, GARBAGE_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    for _ in range(3):
        with pytest.raises(RapfiUnavailable):
            await rapfi.compute_move(board, to_move=2, timeout_s=1.0)
    assert rapfi._disabled is True
    assert rapfi._fail_count >= 3


async def test_success_resets_failure_counter(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, NORMAL_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    await rapfi.compute_move(board, to_move=2, timeout_s=5.0)
    assert rapfi._fail_count == 0


TIME_MOCK = """\
import sys
def main():
    tt = 'none'
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        c = line.strip()
        if c.startswith('INFO timeout_turn'):
            tt = c.split()[-1]
        elif c == 'BOARD':
            while True:
                l = sys.stdin.readline()
                if not l or l.strip() == 'DONE':
                    break
            open(sys.argv[1], 'w').write(tt)
            print('3,3', flush=True)
        elif c == 'END':
            return
main()
"""


def _patch_cmd_with_arg(monkeypatch, mock_path, arg):
    monkeypatch.setattr(rapfi, "get_rapfi_command",
                        lambda: [sys.executable, str(mock_path), str(arg)])
    monkeypatch.setattr(rapfi, "get_model_dir", lambda: str(mock_path.parent))


async def test_compute_move_sends_info_time_turn(tmp_path, monkeypatch):
    capture = tmp_path / "tt.txt"
    p = _write_mock(tmp_path, TIME_MOCK)
    _patch_cmd_with_arg(monkeypatch, p, capture)
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    mv = await rapfi.compute_move(board, to_move=2, time_turn_ms=5000, timeout_s=5.0)
    assert (mv.row, mv.col) == (3, 3)
    assert capture.read_text() == "5000"


async def test_compute_move_without_time_turn_sends_none(tmp_path, monkeypatch):
    capture = tmp_path / "tt.txt"
    p = _write_mock(tmp_path, TIME_MOCK)
    _patch_cmd_with_arg(monkeypatch, p, capture)
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    await rapfi.compute_move(board, to_move=2, timeout_s=5.0)
    assert capture.read_text() == "none"


# --- availability probe ---------------------------------------------------

async def test_probe_unavailable_when_binary_missing(monkeypatch):
    monkeypatch.setattr(rapfi, "get_rapfi_command",
                        lambda: ["/nonexistent/path/pbrain-Rapfi"])
    monkeypatch.setattr(rapfi, "get_model_dir", lambda: "/tmp")
    rapfi._reset_state_for_tests()
    assert await rapfi.is_rapfi_available() is False


async def test_probe_unavailable_when_circuit_open(monkeypatch):
    rapfi._disabled = True
    monkeypatch.setattr(rapfi, "get_rapfi_command",
                        lambda: [sys.executable, "does-not-matter"])
    assert await rapfi.is_rapfi_available() is False


async def test_probe_available_when_mock_responds(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, NORMAL_MOCK))
    rapfi._reset_state_for_tests()
    assert await rapfi.is_rapfi_available() is True
    # cached: second call does not re-probe
    assert await rapfi.is_rapfi_available() is True
