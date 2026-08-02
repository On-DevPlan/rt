"""Gomoku AI HTTP endpoints — stateless, like /api/tetris/next-move."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import List

from fastapi import APIRouter, HTTPException, Request

from .board import SIZE, has_any_stone
from .rapfi import (
    RapfiUnavailable,
    compute_move,
    get_model_dir,
    get_rapfi_command,
    is_rapfi_available,
)
from .schemas import EngineDebugOut, MoveOut, NextMoveRequest, NextMoveResponse
from .service import Move, best_move, top_moves

log = logging.getLogger(__name__)


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
            # time_turn controls Rapfi's think time (ms); timeout is a wall-clock
            # cap = time_turn + 3s slack for the subprocess round-trip.
            timeout = time_turn / 1000.0 + 3.0
            try:
                mv = await compute_move(
                    board, to_move, time_turn_ms=time_turn, timeout_s=timeout
                )
                return mv, "rapfi"
            except RapfiUnavailable as e:
                log.warning("rapfi compute_move failed, falling back: %s", e)
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

    @router.get("/engine-debug", response_model=EngineDebugOut)
    async def engine_debug(request: Request):
        """Probe Rapfi and return its stdout/stderr verbatim.

        Three passes:
          1. Spawn with no stdin, read startup output (catches load errors).
          2. Spawn and do the minimal piskvork protocol (START + BOARD + DONE
             + END) WITHOUT INFO commands — to isolate whether INFO is the
             problem.
          3. Run the real compute_move with an optional ``?time_turn_ms=`` to
             confirm the time-budget wait actually sleeps.

        ``has_search_wait`` reports whether the deployed rapfi module has the
        ``_search_wait`` (time-budget) logic — a deployed-code version marker.
        """
        import os
        import time as _time
        import traceback

        from .rapfi import _probe, _reset_state_for_tests
        import rt_backend.gomoku_ai.rapfi as _rapfi_mod

        has_search_wait = hasattr(_rapfi_mod, "_search_wait")
        _reset_state_for_tests()
        try:
            q_time_turn = int(request.query_params.get("time_turn_ms", ""))
        except ValueError:
            q_time_turn = None

        bin_path = get_rapfi_command()[0]
        model_dir = get_model_dir()
        binary_on_disk = os.path.isfile(bin_path)
        try:
            listing = sorted(os.listdir(model_dir))[:60]
        except OSError as e:
            listing = [f"<listdir error: {e}>"]

        stderr_chunks: list[str] = []
        stdout_chunks: list[str] = []
        rc: int | None = None
        timed_out = False
        protocol_output: list[str] = []  # raw lines from pass 2

        # --- Pass 1: spawn with no stdin, read startup output ---
        try:
            cmd = get_rapfi_command()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=model_dir,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert proc.stdout is not None and proc.stderr is not None
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=3.0
                )
                rc = proc.returncode
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                timed_out = True
                rc = proc.returncode
            stdout_chunks.append(stdout.decode("utf-8", "replace"))
            stderr_chunks.append(stderr.decode("utf-8", "replace"))
        except FileNotFoundError as e:
            stderr_chunks.append(f"FileNotFoundError: {e}")
        except Exception as e:
            stderr_chunks.append(f"spawn error: {type(e).__name__}: {e}")
            stderr_chunks.append(traceback.format_exc())

        # --- Pass 2: minimal piskvork protocol (no INFO) ---
        try:
            cmd = get_rapfi_command()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=model_dir,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
            proc.stdin.write(b"START 15\n")
            proc.stdin.write(b"BOARD\n")
            proc.stdin.write(b"7,7,1\n")
            proc.stdin.write(b"DONE\n")
            await proc.stdin.drain()
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(b"END\n"), timeout=5.0
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
            for line in (stdout + stderr).decode("utf-8", "replace").splitlines():
                protocol_output.append(line)
        except Exception as e:
            protocol_output.append(f"protocol pass error: {type(e).__name__}: {e}")
            protocol_output.append(traceback.format_exc())

        # --- Pass 3: real compute_move (with optional time_turn_ms) ---
        probe_ok: bool | None = None
        probe_error: str | None = None
        probe_move = None
        probe_elapsed_ms: float | None = None
        try:
            from .rapfi import compute_move as _compute_move
            board = [[0] * 15 for _ in range(15)]
            board[7][7] = 1
            t0 = _time.perf_counter()
            probe_move = await _compute_move(
                board, to_move=2, time_turn_ms=q_time_turn, timeout_s=9.0
            )
            probe_elapsed_ms = round((_time.perf_counter() - t0) * 1000, 1)
            probe_ok = True
        except Exception as e:
            probe_ok = False
            probe_error = f"{type(e).__name__}: {e}"
            stderr_chunks.append(f"compute_move error: {probe_error}")
            stderr_chunks.append(traceback.format_exc())

        try:
            rap_avail = bool(await is_rapfi_available())
        except Exception as e:
            stderr_chunks.append(f"is_rapfi_available error: {type(e).__name__}: {e}")
            rap_avail = False

        return EngineDebugOut(
            binary_path=bin_path,
            binary_exists=binary_on_disk,
            cwd=model_dir,
            listing=listing,
            stdout=stdout_chunks[:80] + ["--- protocol pass (START/BOARD/DONE/END, no INFO) ---"] + protocol_output[:60] + [
                f"--- compute_move probe: ok={probe_ok} move={probe_move} elapsed_ms={probe_elapsed_ms} "
                f"time_turn_ms={q_time_turn} has_search_wait={has_search_wait} error={probe_error} ---"
            ],
            stderr=stderr_chunks,
            exit_code=rc,
            timed_out=timed_out,
            probe_ok=probe_ok,
            rapfi_available=rap_avail,
        )

    return router
