"""Tests for video_apng.router (POST/GET/DELETE endpoints)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.island_cut.video_apng.router import build_apng_router
from rt_backend.island_cut.video_apng.store import IslandVideoApngJobStore


@pytest.fixture
def client(tmp_path):
    store = IslandVideoApngJobStore(root=tmp_path / "jobs")
    app = FastAPI()
    app.include_router(build_apng_router(lambda request: store))
    return TestClient(app)


def _fake_mp4_bytes():
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


def test_post_returns_200_and_metadata(client, monkeypatch):
    from rt_backend.island_cut.video_apng.service import VideoResult
    monkeypatch.setattr(
        "rt_backend.island_cut.video_apng.router.process_video",
        lambda data, **kw: VideoResult(
            apng=b"\x89PNG-APNG-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0, final_fps=12.0,
            width=100, height=100, duration_sec=5.0,
            output_size_bytes=20, compression_attempts=1),
    )
    r = client.post(
        "/api/island-cut/video-apng/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": '{"fps": 12, "max_size": 360}'},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["frame_count"] == 10
    assert body["final_fps"] == 12.0
    assert body["output_size_bytes"] == 20
    assert body["compression_attempts"] == 1
    assert body["apng_url"].startswith("/api/island-cut/video-apng/jobs/")


def test_post_compress_failure_413(client, monkeypatch):
    """max_output_bytes 后仍超限 → ValueError 转 413。"""
    def _raise(data, **kw):
        raise ValueError("无法压缩到 1024 字节")
    monkeypatch.setattr(
        "rt_backend.island_cut.video_apng.router.process_video", _raise)
    r = client.post(
        "/api/island-cut/video-apng/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": '{"max_output_bytes": 1024}'},
    )
    assert r.status_code == 413


def test_get_apng_preview_and_delete(client, monkeypatch):
    from rt_backend.island_cut.video_apng.service import VideoResult
    monkeypatch.setattr(
        "rt_backend.island_cut.video_apng.router.process_video",
        lambda data, **kw: VideoResult(
            apng=b"\x89PNG-APNG-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0, final_fps=12.0,
            width=100, height=100, duration_sec=5.0,
            output_size_bytes=20, compression_attempts=1),
    )
    r = client.post(
        "/api/island-cut/video-apng/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    job_id = r.json()["job_id"]
    a = client.get(f"/api/island-cut/video-apng/jobs/{job_id}/apng")
    assert a.status_code == 200 and a.content == b"\x89PNG-APNG-data" and a.headers["content-type"] == "image/png"
    p = client.get(f"/api/island-cut/video-apng/jobs/{job_id}/preview.png")
    assert p.status_code == 200 and p.content == b"PNG-data"
    assert client.delete(f"/api/island-cut/video-apng/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/island-cut/video-apng/jobs/{job_id}/apng").status_code == 404


def test_unknown_job_404(client):
    assert client.get("/api/island-cut/video-apng/jobs/nope/apng").status_code == 404