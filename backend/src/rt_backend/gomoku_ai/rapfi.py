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

    Piskvork convention: black (value 1) is always color 1 (the first player)
    and white (value 2) is color 2. Rapfi plays whichever side is to move
    (determined by stone-count parity), which equals ``to_move`` for any legal
    position. (A relative ``to_move -> color 1`` encoding is wrong: for
    ``to_move=2`` it would put color 1 *behind* on stones, which Rapfi rejects
    as an illegal position and never answers — verified via engine-debug, where
    sending ``7,7,2`` for a black stone times out but ``7,7,1`` replies.)
    """
    lines: List[str] = []
    for r in range(SIZE):
        for c in range(SIZE):
            v = board[r][c]
            if v == 1:
                lines.append(f"{c},{r},1")
            elif v == 2:
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

async def _compute_move_inner(board, to_move, timeout_s):
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

    protocol = "START 15\nBOARD\n"
    for line in board_to_gomocup_lines(board, to_move):
        protocol += line + "\n"
    protocol += "DONE\n"

    # Send the whole protocol plus END, then read ALL output until the process
    # exits. Rapfi block-buffers stdout when piped and only flushes on exit, so
    # a live readline() never sees the move (this was the timeout root cause —
    # confirmed by engine-debug Pass 2 which uses communicate() and succeeds).
    # communicate() + END forces the flush; then parse the move from the full
    # captured output.
    try:
        stdout, _stderr = await asyncio.wait_for(
            proc.communicate(input=(protocol + "END\n").encode()),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RapfiUnavailable("rapfi did not respond within timeout")

    row: int | None = None
    col: int | None = None
    for line in stdout.decode("utf-8", "replace").splitlines():
        mv = parse_gomocup_move(line.strip())
        if mv is not None:
            row, col = mv
            break
    if row is None or col is None:
        raise RapfiUnavailable("no move line in rapfi output")

    return RapfiMove(
        row=row,
        col=col,
        score=0,
        winning=would_win(board, row, col, to_move),
        blocks=would_complete_opp_win(board, row, col, opponent(to_move)),
    )


async def compute_move(board, to_move, *, timeout_s: float) -> RapfiMove:
    """Run one Rapfi subprocess, set the full board via BOARD, return its move.

    Any failure (launch error, timeout, no move line) is recorded against the
    circuit breaker and re-raised as RapfiUnavailable. We deliberately don't
    send piskvork INFO commands (time_turn / max_memory / threads / max_node):
    Rapfi's per-move time default works fine for our 0.5/2/5s tiers, and the
    bare protocol is more robust.
    """
    try:
        mv = await _compute_move_inner(board, to_move, timeout_s)
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
        await compute_move(board, to_move=2, timeout_s=4.0)
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
