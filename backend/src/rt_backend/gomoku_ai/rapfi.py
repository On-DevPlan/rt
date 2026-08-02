"""Rapfi (Gomocup) engine driver: spawn-per-request subprocess + BOARD protocol.

Pure-Python module (no FastAPI/Pydantic). The router calls compute_move()
when is_rapfi_available() is True and falls back to the hand-written engine
otherwise. See docs/superpowers/specs/2026-08-02-gomoku-rapfi-engine-design.md.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..core.config import get_settings
from .board import (
    SIZE,
    opponent,
    would_complete_opp_win,
    would_win,
)


class RapfiUnavailable(Exception):
    """Raised when Rapfi cannot produce a move (binary missing, timeout,
    protocol error). The router catches this and falls back to the Python engine."""


@dataclass(frozen=True)
class RapfiMove:
    row: int
    col: int
    score: int
    winning: bool
    blocks: bool


def get_rapfi_command() -> List[str]:
    """Argv to launch Rapfi. Returned as a list so tests can swap in
    ``[sys.executable, mock_script]`` for a mock binary."""
    return [get_settings().rapfi_bin_path]


def get_model_dir() -> str:
    return get_settings().rapfi_model_dir


def board_to_gomocup_lines(board: List[List[int]], to_move: int) -> List[str]:
    """Encode the board as Gomocup BOARD-command stone lines.

    Each line is ``"<col>,<row>,<color>"`` where ``to_move`` becomes color 1
    (the side Rapfi plays) and the opponent becomes color 2. Empty cells are
    skipped. Order is irrelevant.
    """
    opp = 3 - to_move
    lines: List[str] = []
    for r in range(SIZE):
        for c in range(SIZE):
            v = board[r][c]
            if v == to_move:
                lines.append(f"{c},{r},1")
            elif v == opp:
                lines.append(f"{c},{r},2")
    return lines


def parse_gomocup_move(text: str) -> Optional[Tuple[int, int]]:
    """Parse a Gomocup move line ``"x,y"`` into ``(row=y, col=x)``.

    Returns None for non-move lines (INFO/DEBUG/MESSAGE/OK/UNKNOWN/ERROR/blank)
    and for coordinates outside the board. The ``int()`` parse plus range check
    is the entire filter — noise lines fail one of the two.
    """
    s = text.strip()
    parts = s.split(",")
    if len(parts) != 2:
        return None
    try:
        x, y = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    row, col = y, x
    if 0 <= row < SIZE and 0 <= col < SIZE:
        return row, col
    return None


# --- circuit breaker ------------------------------------------------------

_disabled: bool = False
_fail_count: int = 0
_FAIL_THRESHOLD = 3
_availability: Optional[bool] = None


def _record_failure() -> None:
    global _disabled, _fail_count
    _fail_count += 1
    if _fail_count >= _FAIL_THRESHOLD:
        _disabled = True


def _record_success() -> None:
    global _disabled, _fail_count
    _fail_count = 0
    _disabled = False


def _reset_state_for_tests() -> None:
    global _disabled, _fail_count, _availability
    _disabled = False
    _fail_count = 0
    _availability = None


# --- subprocess driver ----------------------------------------------------

async def _read_move(stdout: asyncio.StreamReader) -> Tuple[int, int]:
    while True:
        raw = await stdout.readline()
        if not raw:
            raise RapfiUnavailable("rapfi closed stdout without a move")
        text = raw.decode("utf-8", "replace").strip()
        mv = parse_gomocup_move(text)
        if mv is not None:
            return mv


async def _reap(proc: asyncio.subprocess.Process) -> None:
    """END the engine and reap it, killing on timeout."""
    try:
        proc.stdin.write(b"END\n")
        await proc.stdin.drain()
    except Exception:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def _compute_move_inner(board, to_move, time_turn_ms, timeout_s):
    s = get_settings()
    cmd = get_rapfi_command()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=get_model_dir(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, PermissionError) as e:
        raise RapfiUnavailable(f"cannot launch rapfi: {e}")

    assert proc.stdin is not None and proc.stdout is not None
    try:
        w = proc.stdin.write
        w(b"START 15\n")
        w(f"INFO time_turn {time_turn_ms}\n".encode())
        w(f"INFO max_memory {s.rapfi_max_memory_mb}\n".encode())
        w(f"INFO number_of_threads {s.rapfi_threads}\n".encode())
        w(f"INFO max_node {s.rapfi_max_node}\n".encode())
        w(b"BOARD\n")
        for line in board_to_gomocup_lines(board, to_move):
            w(line.encode() + b"\n")
        w(b"DONE\n")
        await proc.stdin.drain()

        row, col = await asyncio.wait_for(_read_move(proc.stdout), timeout=timeout_s)
    finally:
        await _reap(proc)

    return RapfiMove(
        row=row,
        col=col,
        score=0,
        winning=would_win(board, row, col, to_move),
        blocks=would_complete_opp_win(board, row, col, opponent(to_move)),
    )


async def compute_move(board, to_move, time_turn_ms, *, timeout_s: float) -> RapfiMove:
    """Run one Rapfi subprocess, set the full board via BOARD, return its move.

    Any failure (launch error, timeout, no move line) is recorded against the
    circuit breaker and re-raised as RapfiUnavailable.
    """
    try:
        mv = await _compute_move_inner(board, to_move, time_turn_ms, timeout_s)
    except RapfiUnavailable:
        _record_failure()
        raise
    except Exception as e:  # subprocess / decode surprises
        _record_failure()
        raise RapfiUnavailable(str(e)) from e
    _record_success()
    return mv


# --- availability probe ---------------------------------------------------

def _binary_exists() -> bool:
    path = get_rapfi_command()[0]
    return os.path.isfile(path)


async def _probe() -> bool:
    """Run one trivial round-trip on a near-empty board. True if Rapfi
    returns a sane move, False on any RapfiUnavailable (incl. missing binary).
    """
    if not _binary_exists():
        return False
    board = [[0] * SIZE for _ in range(SIZE)]
    board[SIZE // 2][SIZE // 2] = 1
    try:
        await compute_move(board, to_move=2, time_turn_ms=200, timeout_s=4.0)
        return True
    except RapfiUnavailable:
        return False


async def is_rapfi_available() -> bool:
    """True iff Rapfi is usable. Lazy: probes once on first call and caches.

    Must be awaited — the router calls it inside the async endpoint, so the
    probe runs on the request's own event loop. The circuit breaker
    (``_disabled``) can still force False at runtime.
    """
    global _availability
    if _disabled:
        return False
    if _availability is None:
        try:
            _availability = await _probe()
        except Exception:
            _availability = False
    return bool(_availability)
