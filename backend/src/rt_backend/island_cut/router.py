"""岛屿切割 HTTP 端点（/api/island-cut/*）。

端点全部为同步 def：numpy/PIL 切割是 CPU 密集，FastAPI 会把它们
丢进线程池，不阻塞事件循环。
"""
from __future__ import annotations

import io
import json
import logging
import time
import zipfile

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response

from .schemas import CutParams, CutResponse, PieceInfo
from .service import FULL_NAME, CutParams as ServiceCutParams, load_rgba, run_cut
from .store import IslandJobStore, Job

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB，与 nginx client_max_body_size 对齐
# 1600 万像素（4000×4000）封顶：label 的 int32 标签数组 + RGBA 副本的峰值内存
# 才能压在单服务 300MB 预算内（见 island-cut-deploy-budget）
MAX_PIXELS = 16_000_000


def build_router(store_provider) -> APIRouter:
    router = APIRouter(prefix="/api/island-cut", tags=["island-cut"])

    def _store(request: Request) -> IslandJobStore:
        return store_provider(request)

    def _job_or_404(job_id: str, store: IslandJobStore) -> Job:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, f"任务不存在或已过期: {job_id}")
        return job

    @router.post("/jobs", response_model=CutResponse)
    def create_job(
        file: bytes = File(...),
        params: str = Form("{}"),
        store: IslandJobStore = Depends(_store),
    ):
        try:
            cut_params = CutParams(**json.loads(params or "{}"))
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(422, f"params 解析失败: {exc}") from exc

        if len(file) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB 上限")
        try:
            rgba_img = load_rgba(file)
        except Exception as exc:
            raise HTTPException(400, f"图片解析失败: {exc}") from exc
        if rgba_img.width * rgba_img.height > MAX_PIXELS or max(
            rgba_img.width, rgba_img.height
        ) > 16384:
            raise HTTPException(413, f"图片尺寸过大: {rgba_img.width}x{rgba_img.height}")

        started = time.perf_counter()
        result = run_cut(np.asarray(rgba_img), ServiceCutParams(**cut_params.model_dump()))
        job = store.create(result)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "island-cut job=%s mode=%s %dx%d pieces=%d in %dms",
            job.id, result.mode, result.width, result.height, len(result.pieces), elapsed_ms,
        )
        return CutResponse(
            job_id=job.id,
            mode=result.mode,
            width=result.width,
            height=result.height,
            elapsed_ms=elapsed_ms,
            pieces=[PieceInfo(**p) for p in job.pieces],
            piece_count=len(job.pieces),
            zip_url=f"/api/island-cut/jobs/{job.id}/zip",
            full_url=f"/api/island-cut/jobs/{job.id}/full.png",
        )

    @router.get("/jobs/{job_id}/pieces/{filename}")
    def get_piece(job_id: str, filename: str, store: IslandJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        if not any(p["filename"] == filename for p in job.pieces):
            raise HTTPException(404, f"切片不存在: {filename}")
        # 走 attachment：浏览器触发下载而非打开大图；filename 参数固定 Content-Disposition
        return FileResponse(
            job.dir / filename, media_type="image/png",
            filename=filename, content_disposition_type="attachment",
        )

    @router.get("/jobs/{job_id}/full.png")
    def get_full(job_id: str, store: IslandJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.dir / FULL_NAME, media_type="image/png")

    @router.get("/jobs/{job_id}/zip")
    def download_zip(job_id: str, store: IslandJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in job.pieces:
                zf.write(job.dir / p["filename"], p["filename"])
            zf.write(job.dir / FULL_NAME, FULL_NAME)
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="island-cut-{job_id}.zip"'},
        )

    @router.delete("/jobs/{job_id}")
    def delete_job(job_id: str, store: IslandJobStore = Depends(_store)):
        if not store.delete(job_id):
            raise HTTPException(404, f"任务不存在或已过期: {job_id}")
        return {"deleted": job_id}

    return router
