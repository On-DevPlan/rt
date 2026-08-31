"""MP4→Animated WebP 任务的临时持久化（与 IslandVideoJobStore 同机制）。"""
from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .service import VideoResult


@dataclass
class VideoJob:
    id: str
    dir: Path
    webp_path: Path
    preview_path: Path
    width: int
    height: int
    frame_count: int
    src_fps: float
    out_fps: float
    duration_sec: float
    created: float


WEBP_NAME = "output.webp"
PREVIEW_NAME = "preview.png"


class IslandVideoWebPJobStore:
    def __init__(self, root: Path, ttl_sec: float = 3600.0, clock=time.monotonic):
        self._root = root
        self._ttl = ttl_sec
        self._clock = clock
        self._jobs: dict[str, VideoJob] = {}
        self._lock = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    def create(self, result: VideoResult, webp: bytes, preview: bytes) -> VideoJob:
        self._prune()
        job_id = uuid.uuid4().hex[:12]
        job_dir = self._root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        webp_path = job_dir / WEBP_NAME
        prev_path = job_dir / PREVIEW_NAME
        webp_path.write_bytes(webp)
        prev_path.write_bytes(preview)
        job = VideoJob(
            id=job_id, dir=job_dir, webp_path=webp_path, preview_path=prev_path,
            width=result.width, height=result.height, frame_count=result.frame_count,
            src_fps=result.src_fps, out_fps=result.out_fps, duration_sec=result.duration_sec,
            created=self._clock(),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> VideoJob | None:
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