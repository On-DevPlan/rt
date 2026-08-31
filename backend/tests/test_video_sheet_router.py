"""Tests for video_sheet.router (POST/GET/DELETE endpoints)."""
import io
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from rt_backend.island_cut.video_sheet.router import build_sheet_router
from rt_backend.island_cut.video_sheet.service import SheetResult
from rt_backend.island_cut.video_sheet.store import IslandSheetJobStore


@pytest.fixture
def client(tmp_path):
    store = IslandSheetJobStore(root=tmp_path / "jobs")
    app = FastAPI()
    app.include_router(build_sheet_router(lambda request: store))
    return TestClient(app)


def _fake_mp4_bytes():
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


def _patch_process(monkeypatch, result_kwargs=None):
    monkeypatch.setattr(
        "rt_backend.island_cut.video_sheet.router.process_video",
        lambda data, out_dir, **kw: _fake_write_outputs(out_dir, **result_kwargs or {}),
    )


def _fake_write_outputs(out_dir, **kwargs):
    """为 router 测试造一份最小可用产物。"""
    import json
    from pathlib import Path
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "frames").mkdir(exist_ok=True)
    Image.new("RGBA", (50, 50), (200, 30, 30, 255)).save(out_dir / "sheet.png")
    Image.new("RGBA", (50, 50), (200, 30, 30, 255)).save(out_dir / "frames" / "frame_00001.png")
    Image.new("RGBA", (50, 50), (200, 30, 30, 255)).save(out_dir / "preview.apng")
    Image.new("RGBA", (50, 50), (200, 30, 30, 255)).save(out_dir / "preview.webp")
    (out_dir / "frames.json").write_text(json.dumps({
        "fps_hint": 12, "frames": [{"id": "frame_000", "filename": "frames/frame_00001.png"}],
        "canvas": {"x": 0, "y": 0, "w": 50, "h": 50},
        "canvas_size": {"w": 50, "h": 50},
        "grid": {"cols": 1, "rows": 1},
    }))
    return SheetResult(frame_count=1, fps_hint=12, width=50, height=50, cols=1, rows=1)


def test_post_returns_metadata(client, monkeypatch):
    _patch_process(monkeypatch)
    r = client.post(
        "/api/island-cut/video-sheet/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": '{"fps": 12, "tol": 35, "min_area": 200}'},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["frame_count"] == 1
    assert body["width"] == 50
    assert body["cols"] == 1
    assert body["sheet_url"].endswith("/sheet.png")
    assert body["frames_zip_url"].endswith("/frames.zip")
    assert body["frames_json_url"].endswith("/frames.json")


def test_post_bad_params_422(client):
    r = client.post(
        "/api/island-cut/video-sheet/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "not json"},
    )
    assert r.status_code == 422


def test_get_files_and_zip(client, monkeypatch):
    _patch_process(monkeypatch)
    r = client.post(
        "/api/island-cut/video-sheet/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    job_id = r.json()["job_id"]

    assert client.get(f"/api/island-cut/video-sheet/jobs/{job_id}/sheet.png").status_code == 200
    assert client.get(f"/api/island-cut/video-sheet/jobs/{job_id}/frames.json").status_code == 200
    z = client.get(f"/api/island-cut/video-sheet/jobs/{job_id}/frames.zip")
    assert z.status_code == 200
    assert "attachment" in z.headers.get("content-disposition", "")
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        assert any(n.endswith(".png") for n in zf.namelist())
    assert client.get(f"/api/island-cut/video-sheet/jobs/{job_id}/preview.apng").status_code == 200
    assert client.get(f"/api/island-cut/video-sheet/jobs/{job_id}/preview.webp").status_code == 200


def test_delete_and_unknown_404(client, monkeypatch):
    _patch_process(monkeypatch)
    r = client.post(
        "/api/island-cut/video-sheet/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    job_id = r.json()["job_id"]
    assert client.delete(f"/api/island-cut/video-sheet/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/island-cut/video-sheet/jobs/{job_id}/sheet.png").status_code == 404
    assert client.delete(f"/api/island-cut/video-sheet/jobs/nope").status_code == 404