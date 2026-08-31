"""MP4 → 透明 Animated PNG 端点（/api/island-cut/video-apng/*）。"""
from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request
from fastapi.responses import FileResponse

from .schemas import VideoCutParams, VideoCutResponse
from .service import VideoOversizeError, process_video
from .store import IslandVideoApngJobStore, VideoJob

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _job_or_404(job_id: str, store: IslandVideoApngJobStore) -> VideoJob:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, f"任务不存在或已过期: {job_id}")
    return job


def build_apng_router(store_provider) -> APIRouter:
    router = APIRouter(prefix="/api/island-cut/video-apng", tags=["island-cut-video-apng"])

    def _store(request: Request) -> IslandVideoApngJobStore:
        return store_provider(request)

    @router.post("/jobs", response_model=VideoCutResponse)
    def create_job(
        file: bytes = File(...),
        params: str = Form("{}"),
        store: IslandVideoApngJobStore = Depends(_store),
    ):
        try:
            cut_params = VideoCutParams(**json.loads(params or "{}"))
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(422, f"params 解析失败: {exc}") from exc
        if len(file) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB 上限")

        started = time.perf_counter()
        try:
            result = process_video(file, **cut_params.model_dump())
        except VideoOversizeError as exc:
            raise HTTPException(413, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(413, f"压缩失败: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"视频解码失败: {exc}") from exc

        job = store.create(result, apng=result.apng, preview=result.preview)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log.info("island-cut-video-apng job=%s frames=%d %dx%d final_fps=%.1f size=%d attempts=%d in %dms",
                 job.id, result.frame_count, result.width, result.height,
                 result.final_fps, result.output_size_bytes, result.compression_attempts, elapsed_ms)
        return VideoCutResponse(
            job_id=job.id,
            width=result.width,
            height=result.height,
            frame_count=result.frame_count,
            src_fps=result.src_fps,
            out_fps=result.out_fps,
            final_fps=result.final_fps,
            duration_sec=result.duration_sec,
            elapsed_ms=elapsed_ms,
            output_size_bytes=result.output_size_bytes,
            compression_attempts=result.compression_attempts,
            apng_url=f"/api/island-cut/video-apng/jobs/{job.id}/apng",
            preview_url=f"/api/island-cut/video-apng/jobs/{job.id}/preview.png",
        )

    @router.get("/jobs/{job_id}/apng")
    def get_apng(job_id: str, store: IslandVideoApngJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.apng_path, media_type="image/png", filename="output.apng")

    @router.get("/jobs/{job_id}/preview.png")
    def get_preview(job_id: str, store: IslandVideoApngJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.preview_path, media_type="image/png")

    @router.delete("/jobs/{job_id}")
    def delete_job(job_id: str, store: IslandVideoApngJobStore = Depends(_store)):
        if not store.delete(job_id):
            raise HTTPException(404, f"任务不存在或已过期: {job_id}")
        return {"deleted": job_id}

    return router