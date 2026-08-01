"""Tetris AI HTTP endpoints.

Stateless decision service: the client owns the game, uploads a board snapshot
plus the piece it needs to place, and gets back where to put it.
"""
from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException

from .board import BoardError, parse_board
from .pieces import PIECE_NAMES
from .schemas import MetricsOut, NextMoveRequest, NextMoveResponse
from .service import NoPlacementError, best_placement, plan_moves


def build_router() -> APIRouter:
    router = APIRouter(prefix="/api/tetris", tags=["tetris"])

    @router.get("/pieces")
    async def pieces():
        """Piece letters this service understands."""
        return {"pieces": list(PIECE_NAMES)}

    @router.post("/next-move", response_model=NextMoveResponse)
    async def next_move(req: NextMoveRequest):
        started = time.perf_counter()

        try:
            rows, width = parse_board(req.board)
        except BoardError as e:
            raise HTTPException(status_code=422, detail=str(e))

        if req.current_x is not None and req.current_x >= width:
            raise HTTPException(
                status_code=422,
                detail=f"current_x={req.current_x} 超出棋盘宽度 {width}",
            )

        weights = req.weights.model_dump() if req.weights else None

        try:
            placement = best_placement(
                rows=rows,
                width=width,
                piece=req.piece,
                next_piece=req.next_piece,
                weights=weights,
            )
        except NoPlacementError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        moves = plan_moves(
            piece=req.piece,
            target_rotation=placement.rotation,
            target_x=placement.x,
            width=width,
            current_x=req.current_x,
            current_rotation=req.current_rotation,
        )

        m = placement.metrics
        return NextMoveResponse(
            rotation=placement.rotation,
            target_x=placement.x,
            final_y=placement.y,
            moves=moves,
            score=round(placement.score, 4),
            cleared_lines=placement.cleared_lines,
            lookahead=req.next_piece is not None,
            metrics=MetricsOut(
                landing_height=m.landing_height,
                eroded_piece_cells=m.eroded_piece_cells,
                row_transitions=m.row_transitions,
                column_transitions=m.column_transitions,
                holes=m.holes,
                wells=m.wells,
            ),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        )

    return router
