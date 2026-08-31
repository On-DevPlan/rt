"""Tests for IslandVideoJobStore."""
import time
from pathlib import Path

import pytest

from rt_backend.island_cut.video_island.service import VideoResult
from rt_backend.island_cut.video_island.store import IslandVideoJobStore


@pytest.fixture
def store(tmp_path):
    return IslandVideoJobStore(root=tmp_path / "jobs", ttl_sec=3600.0)


def _result(gif=b"GIF89a", preview=b"\x89PNG\r\n"):
    return VideoResult(gif=gif, preview=preview, frame_count=10, src_fps=30.0,
                       out_fps=12.0, final_fps=12.0, width=100, height=100,
                       duration_sec=5.0, output_size_bytes=len(gif),
                       compression_attempts=1)


def test_create_writes_gif_and_preview(store):
    job = store.create(_result(), b"GIF89a-data", b"PNG-data")
    assert (job.dir / "output.gif").exists()
    assert (job.dir / "preview.png").exists()
    assert (job.dir / "output.gif").read_bytes() == b"GIF89a-data"


def test_get_unknown_returns_none(store):
    assert store.get("nope") is None


def test_get_expired_returns_none_and_removes_dir(tmp_path):
    s = IslandVideoJobStore(root=tmp_path / "jobs", ttl_sec=0.05)
    job = s.create(_result(), b"a", b"b")
    jd = job.dir
    time.sleep(0.08)
    assert s.get(job.id) is None
    assert not jd.exists()


def test_delete_removes_dir(store):
    job = store.create(_result(), b"a", b"b")
    assert store.delete(job.id) is True
    assert not (job.dir).exists()


def test_delete_unknown_returns_false(store):
    assert store.delete("nope") is False