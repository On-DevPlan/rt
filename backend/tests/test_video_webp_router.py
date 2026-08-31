"""Tests for video_webp.router (POST/GET/DELETE endpoints)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.island_cut.video_webp.router import build_webp_router
from rt_backend.island_cut.video_webp.store import IslandVideoWebPJobStore


@pytest.fixture
def client(tmp_path):
    store = IslandVideoWebPJobStore(root=tmp_path / "jobs")
    app = FastAPI()
    app.include_router(build_webp_router(lambda request: store))
    return TestClient(app)


def _fake_mp4_bytes():
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


def test_post_returns_200_and_metadata(client, monkeypatch):
    from rt_backend.island_cut.video_webp.service import VideoResult
    monkeypatch.setattr(
        "rt_backend.island_cut.video_webp.router.process_video",
        lambda data, **kw: VideoResult(
            webp=b"RIFF\x00\x00\x00\x00WEBP-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0,
            width=100, height=100, duration_sec=5.0),
    )
    r = client.post(
        "/api/island-cut/video-webp/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": '{"fps": 12, "max_size": 360}'},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["frame_count"] == 10
    assert body["width"] == 100
    assert body["webp_url"].startswith("/api/island-cut/video-webp/jobs/")
    assert body["preview_url"].startswith("/api/island-cut/video-webp/jobs/")


def test_post_bad_params_422(client):
    r = client.post(
        "/api/island-cut/video-webp/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "not json"},
    )
    assert r.status_code == 422


def test_post_oversize_413(client, monkeypatch):
    from rt_backend.island_cut.video_webp.service import VideoOversizeError
    monkeypatch.setattr(
        "rt_backend.island_cut.video_webp.router.process_video",
        lambda data, **kw: (_ for _ in ()).throw(VideoOversizeError("too big")),
    )
    r = client.post(
        "/api/island-cut/video-webp/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    assert r.status_code == 413


def test_get_webp_preview_and_delete(client, monkeypatch):
    from rt_backend.island_cut.video_webp.service import VideoResult
    monkeypatch.setattr(
        "rt_backend.island_cut.video_webp.router.process_video",
        lambda data, **kw: VideoResult(
            webp=b"RIFF\x00\x00\x00\x00WEBP-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0,
            width=100, height=100, duration_sec=5.0),
    )
    r = client.post(
        "/api/island-cut/video-webp/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    job_id = r.json()["job_id"]

    w = client.get(f"/api/island-cut/video-webp/jobs/{job_id}/webp")
    assert w.status_code == 200
    assert w.content == b"RIFF\x00\x00\x00\x00WEBP-data"
    assert w.headers["content-type"] == "image/webp"

    p = client.get(f"/api/island-cut/video-webp/jobs/{job_id}/preview.png")
    assert p.status_code == 200
    assert p.content == b"PNG-data"

    assert client.delete(f"/api/island-cut/video-webp/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/island-cut/video-webp/jobs/{job_id}/webp").status_code == 404


def test_unknown_job_404(client):
    assert client.get("/api/island-cut/video-webp/jobs/nope/webp").status_code == 404
    assert client.delete("/api/island-cut/video-webp/jobs/nope").status_code == 404