"""Sprite sheet 任务的临时持久化（与 IslandVideoJobStore 同机制；目录形态）。"""
from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


SHEET_NAME = "sheet.png"
FRAMES_DIR_NAME = "frames"
FRAMES_JSON_NAME = "frames.json"
PREVIEW_APNG_NAME = "preview.apng"
PREVIEW_WEBP_NAME = "preview.webp"


@dataclass
class SheetJob:
    id: str
    dir: Path
    sheet_path: Path
    frames_dir: Path
    frames_json_path: Path
    preview_apng_path: Path
    preview_webp_path: Path
    frame_count: int
    width: int
    height: int
    cols: int
    rows: int
    fps_hint: float
    created: float


class IslandSheetJobStore:
    def __init__(self, root: Path, ttl_sec: float = 3600.0, clock=time.monotonic):
        self._root = root
        self._ttl = ttl_sec
        self._clock = clock
        self._jobs: dict[str, SheetJob] = {}
        self._lock = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        job_dir: Path,
        *,
        frame_count: int,
        width: int,
        height: int,
        cols: int,
        rows: int,
        fps_hint: float,
    ) -> SheetJob:
        """假设 job_dir 已经由 service.process_video 写入全部产物（sheet.png 等），
        本方法仅把它登记到内存 + 记录元数据。job_id 复用目录名（便于按目录清理）。"""
        self._prune()
        job_id = job_dir.name
        job = SheetJob(
            id=job_id,
            dir=job_dir,
            sheet_path=job_dir / SHEET_NAME,
            frames_dir=job_dir / FRAMES_DIR_NAME,
            frames_json_path=job_dir / FRAMES_JSON_NAME,
            preview_apng_path=job_dir / PREVIEW_APNG_NAME,
            preview_webp_path=job_dir / PREVIEW_WEBP_NAME,
            frame_count=frame_count,
            width=width,
            height=height,
            cols=cols,
            rows=rows,
            fps_hint=fps_hint,
            created=self._clock(),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> SheetJob | None:
        self._prune()
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        shutil.rmtree(job.dir, ignore_errors=True)
        return True

    def _prune(self) -> None:
        now = self._clock()
        with self._lock:
            dead = [j for j in self._jobs.values() if now - j.created > self._ttl]
            for j in dead:
                self._jobs.pop(j.id, None)
        for j in dead:
            shutil.rmtree(j.dir, ignore_errors=True)