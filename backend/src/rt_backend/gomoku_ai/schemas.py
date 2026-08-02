"""Pydantic schemas for the Gomoku AI endpoints."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

BoardRow = List[int]
Player = int


class NextMoveRequest(BaseModel):
    """Current board + side to move.

    ``board`` is a 15x15 matrix, top-row first. Cells: 0=empty, 1=black, 2=white.
    The board MUST reflect the position BEFORE the AI's move; the client does
    not pre-emptively place anything. Invalid cell values trigger a 422 from
    the server-side validator in the router.
    """

    board: List[BoardRow] = Field(
        ...,
        description="15x15 棋盘，自上而下。0=空 1=黑 2=白",
    )
    to_move: Player = Field(..., description="AI 执子方：1 黑 / 2 白")
    top_k: int = Field(
        default=3,
        description="返回的候选着点数（1-5，按评估分降序）",
    )
    strength: int = Field(
        default=2,
        description="AI 强度档位：1 弱 / 2 中 / 3 强。弱=贪心无前瞻，中=1步前瞻beam6，强=1步前瞻beam12",
    )


class MoveOut(BaseModel):
    row: int
    col: int
    score: int
    winning: bool
    blocks: bool


class NextMoveResponse(BaseModel):
    best: MoveOut
    top_moves: List[MoveOut]
    elapsed_ms: float
    engine: str = "rapfi"


class EngineDebugOut(BaseModel):
    """Diagnostic payload returned by GET /api/gomoku/engine-debug.

    Lets us see WHY Rapfi isn't loading on the server (the production
    next-move endpoint silently falls back to Python). Includes the raw
    stdout/stderr from a /opt/rapfi/pbrain-Rapfi subprocess probe so the
    actual Rapfi error message is visible from outside the container.
    """

    binary_path: str
    binary_exists: bool
    cwd: str
    listing: List[str]
    stdout: List[str]
    stderr: List[str]
    exit_code: int | None
    timed_out: bool
    probe_ok: bool | None
    rapfi_available: bool
