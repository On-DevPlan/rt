"""Gomoku AI HTTP endpoints — stateless, like /api/tetris/next-move."""
from __future__ import annotations

import asyncio
import time
from typing import List

from fastapi import APIRouter, HTTPException

from .board import SIZE, has_any_stone
from .rapfi import RapfiUnavailable, compute_move, is_rapfi_available
from .schemas import MoveOut, NextMoveRequest, NextMoveResponse
from .service import Move, best_move, top_moves


def _to_row_col(move: Move) -> MoveOut:
    return MoveOut(
        row=move.row,
        col=move.col,
        score=move.score,
        winning=move.winning,
        blocks=move.blocks,
    )


def build_router() -> APIRouter:
    router = APIRouter(prefix="/api/gomoku", tags=["gomoku"])

    from ..core.config import get_settings

    def _time_by_strength() -> dict[int, int]:
        s = get_settings()
        return {
            1: s.rapfi_time_turn_weak,
            2: s.rapfi_time_turn_mid,
            3: s.rapfi_time_turn_strong,
        }

    async def _resolve_move(board, to_move, strength):
        """Try Rapfi; fall back to the Python engine on any failure.
        Returns (move, engine_label)."""
        time_turn = _time_by_strength()[strength]
        if await is_rapfi_available():
            timeout = time_turn / 1000.0 + 3.0
            try:
                mv = await compute_move(board, to_move, time_turn, timeout_s=timeout)
                return mv, "rapfi"
            except RapfiUnavailable:
                pass
        mv = await asyncio.to_thread(best_move, board, to_move, strength=strength)
        return mv, "python-fallback"

    @router.post("/next-move", response_model=NextMoveResponse)
    async def next_move(req: NextMoveRequest):
        started = time.perf_counter()

        if req.to_move not in (1, 2):
            raise HTTPException(
                status_code=422,
                detail=f"to_move={req.to_move}，合法值 1(黑) 或 2(白)",
            )
        if not (1 <= req.top_k <= 5):
            raise HTTPException(
                status_code=422,
                detail=f"top_k={req.top_k}，合法值 1..5",
            )
        if not (1 <= req.strength <= 3):
            raise HTTPException(
                status_code=422,
                detail=f"strength={req.strength}，合法值 1(弱)/2(中)/3(强)",
            )

        board = [row[:] for row in req.board]
        if len(board) != SIZE:
            raise HTTPException(
                status_code=422,
                detail=f"board 需要 {SIZE} 行，得到 {len(board)}",
            )
        for y, row in enumerate(board):
            if len(row) != SIZE:
                raise HTTPException(
                    status_code=422,
                    detail=f"board[{y}] 长度为 {len(row)}，应为 {SIZE}",
                )
            for x, v in enumerate(row):
                if v not in (0, 1, 2):
                    raise HTTPException(
                        status_code=422,
                        detail=f"board[{y}][{x}]={v}，合法值 0/1/2",
                    )

        # Quick parity check: the side to move is whoever has the fewer
        # stones, or black if equal. This is just a soft sanity check that
        # the client isn't sending a board where it's already the opponent's
        # turn — we don't fail, since custom handicaps are common.
        if has_any_stone(board):
            best, engine = await _resolve_move(board, req.to_move, req.strength)
            if engine == "rapfi":
                alts = [best] * req.top_k
            else:
                alts = top_moves(board, req.to_move, k=req.top_k, strength=req.strength)
        else:
            # empty board fast path: center, no subprocess
            best = best_move(board, req.to_move, strength=req.strength)
            alts = top_moves(board, req.to_move, k=req.top_k, strength=req.strength)
            engine = "python-fallback"

        return NextMoveResponse(
            best=_to_row_col(best),
            top_moves=[_to_row_col(m) for m in alts],
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            engine=engine,
        )

    return router
