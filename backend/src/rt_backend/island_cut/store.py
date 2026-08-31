"""切割任务的临时持久化：内存注册表 + 系统临时目录文件，按 TTL 惰性清理。

设计：单机自用 demo，不落数据库。每次上传建一个 job 目录
（{root}/{job_id}/island_NN.png + 00_full_transparent.png），
注册表只存元数据；每次 create 时顺带清扫过期 job。
"""
from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .service import FULL_NAME, CutResult


@dataclass
class Job:
    id: str
    dir: Path
    pieces: list[dict]  # PieceInfo 字段（不含 image）
    created: float


class IslandJobStore:
    def __init__(self, root: Path, ttl_sec: float = 3600.0, clock=time.monotonic):
        self._root = root
        self._ttl = ttl_sec
        self._clock = clock
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()  # sync 端点跑在线程池，注册表需加锁
        self._root.mkdir(parents=True, exist_ok=True)

    def create(self, result: CutResult) -> Job:
        self._prune()
        job_id = uuid.uuid4().hex[:12]
        job_dir = self._root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        for piece in result.pieces:
            piece["image"].save(job_dir / piece["filename"], format="PNG")
        result.full_image.save(job_dir / FULL_NAME, format="PNG")
        job = Job(
            id=job_id,
            dir=job_dir,
            pieces=[{k: v for k, v in p.items() if k != "image"} for p in result.pieces],
            created=self._clock(),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
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
