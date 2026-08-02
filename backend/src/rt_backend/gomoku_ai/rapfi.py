"""Rapfi (Gomocup) engine driver: spawn-per-request subprocess + BOARD protocol.

Pure-Python module (no FastAPI/Pydantic). The router calls compute_move()
when is_rapfi_available() is True and falls back to the hand-written engine
otherwise. See docs/superpowers/specs/2026-08-02-gomoku-rapfi-engine-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..core.config import get_settings
from .board import SIZE


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
