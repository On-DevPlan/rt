"""Tests for video_island.router (POST/GET/DELETE endpoints)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.island_cut.video_island.router import build_video_router
from rt_backend.island_cut.video_island.store import IslandVideoJobStore


@pytest.fixture
def app_store(tmp_path):
    store = IslandVideoJobStore(root=tmp_path / "jobs")
    app = FastAPI()
    app.include_router(build_video_router(lambda request: store))
    return app, store


@pytest.fixture
def client(app_store):
    app, _ = app_store
    return TestClient(app)


def _fake_mp4_bytes():
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


def test_post_returns_200_and_metadata(client, monkeypatch):
    from rt_backend.island_cut.video_island.service import VideoResult
    monkeypatch.setattr(
        "rt_backend.island_cut.video_island.router.process_video",
        lambda data, **kw: VideoResult(
            gif=b"GIF89a-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0, final_fps=12.0,
            width=100, height=100, duration_sec=5.0,
            output_size_bytes=len(b"GIF89a-data"), compression_attempts=1),
    )
    r = client.post(
        "/api/island-cut/video/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": '{"fps": 12, "max_size": 360}'},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["frame_count"] == 10
    assert body["width"] == 100
    assert body["out_fps"] == 12.0
    assert body["final_fps"] == 12.0
    assert body["compression_attempts"] == 1
    assert body["output_size_bytes"] > 0
    assert body["gif_url"].startswith("/api/island-cut/video/jobs/")
    assert body["preview_url"].startswith("/api/island-cut/video/jobs/")


def test_post_bad_params_422(client):
    r = client.post(
        "/api/island-cut/video/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "not json"},
    )
    assert r.status_code == 422


def test_post_oversize_413(client, monkeypatch):
    from rt_backend.island_cut.video_island.service import VideoOversizeError
    def _raise(data, **kw):
        raise VideoOversizeError("too big")
    monkeypatch.setattr(
        "rt_backend.island_cut.video_island.router.process_video", _raise)
    r = client.post(
        "/api/island-cut/video/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    assert r.status_code == 413


def test_post_compress_failure_413(client, monkeypatch):
    """max_output_bytes 设置后仍超限 → ValueError 转 413。"""
    def _raise(data, **kw):
        raise ValueError("无法压缩到 1024 字节")
    monkeypatch.setattr(
        "rt_backend.island_cut.video_island.router.process_video", _raise)
    r = client.post(
        "/api/island-cut/video/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": '{"max_output_bytes": 1024}'},
    )
    assert r.status_code == 413


def test_get_gif_preview_and_delete(client, monkeypatch):
    from rt_backend.island_cut.video_island.service import VideoResult
    monkeypatch.setattr(
        "rt_backend.island_cut.video_island.router.process_video",
        lambda data, **kw: VideoResult(
            gif=b"GIF89a-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0, final_fps=12.0,
            width=100, height=100, duration_sec=5.0,
            output_size_bytes=len(b"GIF89a-data"), compression_attempts=1),
    )
    r = client.post(
        "/api/island-cut/video/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    job_id = r.json()["job_id"]

    g = client.get(f"/api/island-cut/video/jobs/{job_id}/gif")
    assert g.status_code == 200
    assert g.content == b"GIF89a-data"
    assert g.headers["content-type"] == "image/gif"

    p = client.get(f"/api/island-cut/video/jobs/{job_id}/preview.png")
    assert p.status_code == 200
    assert p.content == b"PNG-data"
    assert p.headers["content-type"] == "image/png"

    assert client.delete(f"/api/island-cut/video/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/island-cut/video/jobs/{job_id}/gif").status_code == 404


def test_unknown_job_404(client):
    assert client.get("/api/island-cut/video/jobs/nope/gif").status_code == 404
    assert client.delete("/api/island-cut/video/jobs/nope").status_code == 404