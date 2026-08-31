"""MP4 → sprite sheet 端点（/api/island-cut/video-sheet/*）。

产物：sheet.png / frames/frame_*.png / frames.json / preview.apng / preview.webp。
下载：frames_zip_url 把 frames/ 全部打成 zip。
"""
from __future__ import annotations

import io
import json
import logging
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response

from .schemas import SheetParams, SheetResponse
from .service import SheetOversizeError, SheetResult, process_video
from .store import IslandSheetJobStore, SheetJob

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _job_or_404(job_id: str, store: IslandSheetJobStore) -> SheetJob:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, f"任务不存在或已过期: {job_id}")
    return job


def build_sheet_router(store_provider) -> APIRouter:
    router = APIRouter(prefix="/api/island-cut/video-sheet", tags=["island-cut-video-sheet"])

    def _store(request: Request) -> IslandSheetJobStore:
        return store_provider(request)

    @router.post("/jobs", response_model=SheetResponse)
    def create_job(
        file: bytes = File(...),
        params: str = Form("{}"),
        store: IslandSheetJobStore = Depends(_store),
    ):
        try:
            cut_params = SheetParams(**json.loads(params or "{}"))
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(422, f"params 解析失败: {exc}") from exc
        if len(file) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB 上限")

        started = time.perf_counter()
        # 用 uuid 作 job 目录名（store.create 用 dir.name）
        import uuid
        job_id = uuid.uuid4().hex[:12]
        job_dir = store._root / job_id
        try:
            result: SheetResult = process_video(file, job_dir, **cut_params.model_dump())
        except SheetOversizeError as exc:
            raise HTTPException(413, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"视频处理失败: {exc}") from exc

        job = store.create(
            job_dir,
            frame_count=result.frame_count,
            width=result.width, height=result.height,
            cols=result.cols, rows=result.rows,
            fps_hint=result.fps_hint,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log.info("island-cut-sheet job=%s frames=%d %dx%d in %dms",
                 job.id, result.frame_count, result.width, result.height, elapsed_ms)
        return SheetResponse(
            job_id=job.id,
            frame_count=result.frame_count,
            fps_hint=result.fps_hint,
            width=result.width,
            height=result.height,
            cols=result.cols,
            rows=result.rows,
            elapsed_ms=elapsed_ms,
            sheet_url=f"/api/island-cut/video-sheet/jobs/{job.id}/sheet.png",
            frames_zip_url=f"/api/island-cut/video-sheet/jobs/{job.id}/frames.zip",
            frames_json_url=f"/api/island-cut/video-sheet/jobs/{job.id}/frames.json",
            preview_apng_url=f"/api/island-cut/video-sheet/jobs/{job.id}/preview.apng",
            preview_webp_url=f"/api/island-cut/video-sheet/jobs/{job.id}/preview.webp",
        )

    @router.get("/jobs/{job_id}/sheet.png")
    def get_sheet(job_id: str, store: IslandSheetJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.sheet_path, media_type="image/png")

    @router.get("/jobs/{job_id}/frames.json")
    def get_frames_json(job_id: str, store: IslandSheetJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.frames_json_path, media_type="application/json", filename="frames.json")

    @router.get("/jobs/{job_id}/frames.zip")
    def get_frames_zip(job_id: str, store: IslandSheetJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        if not job.frames_dir.exists():
            raise HTTPException(404, "frames 目录不存在")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in sorted(job.frames_dir.glob("*.png")):
                zf.write(fp, fp.name)
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="frames-{job_id}.zip"'},
        )

    @router.get("/jobs/{job_id}/frames/{filename}")
    def get_single_frame(
        job_id: str, filename: str, store: IslandSheetJobStore = Depends(_store),
    ):
        """单帧直下（路径穿越防御：白名单 frame_NNNNN.png + 路径必须在 frames_dir 内）。"""
        job = _job_or_404(job_id, store)
        # 白名单：仅 frame_NNNNN.png（5 位数字）
        import re as _re
        if not _re.fullmatch(r"frame_\d{5}\.png", filename):
            raise HTTPException(404, f"非法文件名: {filename}")
        target = (job.frames_dir / filename).resolve()
        if job.frames_dir.resolve() not in target.parents:
            raise HTTPException(404, f"非法路径: {filename}")
        if not target.exists():
            raise HTTPException(404, f"帧不存在: {filename}")
        return FileResponse(target, media_type="image/png")

    @router.get("/jobs/{job_id}/bundle.zip")
    def get_bundle_zip(job_id: str, store: IslandSheetJobStore = Depends(_store)):
        """全产物 zip：sheet.png + frames.json + frames/*.png + preview.apng + preview.webp。"""
        job = _job_or_404(job_id, store)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if job.sheet_path.exists():
                zf.write(job.sheet_path, "sheet.png")
            if job.frames_json_path.exists():
                zf.write(job.frames_json_path, "frames.json")
            if job.frames_dir.exists():
                for fp in sorted(job.frames_dir.glob("*.png")):
                    zf.write(fp, f"frames/{fp.name}")
            if job.preview_apng_path.exists():
                zf.write(job.preview_apng_path, "preview.apng")
            if job.preview_webp_path.exists():
                zf.write(job.preview_webp_path, "preview.webp")
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="sheet-bundle-{job_id}.zip"'},
        )

    @router.get("/jobs/{job_id}/preview.apng")
    def get_preview_apng(job_id: str, store: IslandSheetJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.preview_apng_path, media_type="image/png")

    @router.get("/jobs/{job_id}/preview.webp")
    def get_preview_webp(job_id: str, store: IslandSheetJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.preview_webp_path, media_type="image/webp")

    @router.delete("/jobs/{job_id}")
    def delete_job(job_id: str, store: IslandSheetJobStore = Depends(_store)):
        if not store.delete(job_id):
            raise HTTPException(404, f"任务不存在或已过期: {job_id}")
        return {"deleted": job_id}

    return router