"""Tests for island_cut service + router (合成图片，不依赖外部资源)."""
import io
import zipfile

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from rt_backend.island_cut.service import FULL_NAME, CutParams, run_cut
from rt_backend.island_cut.store import IslandJobStore
from rt_backend.island_cut.router import build_router


# ---------------------------------------------------------------------------
# 合成图片工具
# ---------------------------------------------------------------------------

def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _disc_image(w, h, discs, bg=(0, 0, 0, 0)) -> Image.Image:
    """discs: [(cx, cy, r, (r,g,b,a)), ...]"""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :] = bg
    yy, xx = np.mgrid[0:h, 0:w]
    for cx, cy, r, color in discs:
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
        arr[mask] = color
    return Image.fromarray(arr, "RGBA")


def make_client(tmp_path, ttl_sec=3600.0):
    store = IslandJobStore(root=tmp_path / "jobs", ttl_sec=ttl_sec)
    app = FastAPI()
    app.include_router(build_router(lambda request: store))
    return TestClient(app), store


def _cut(client, image_bytes, params=None):
    return client.post(
        "/api/island-cut/jobs",
        files={"file": ("src.png", image_bytes, "image/png")},
        data={"params": params or "{}"},
    )


# ---------------------------------------------------------------------------
# service 单测
# ---------------------------------------------------------------------------

def test_detect_mode_alpha_vs_white():
    from rt_backend.island_cut.service import ALPHA_MODE, WHITE_MODE, detect_mode

    alpha_img = np.asarray(_disc_image(60, 40, [(20, 20, 8, (255, 0, 0, 255))]))
    assert detect_mode(alpha_img) == ALPHA_MODE

    white_img = np.asarray(_disc_image(60, 40, [(20, 20, 8, (10, 10, 10, 255))], bg=(255, 255, 255, 255)))
    assert detect_mode(white_img) == WHITE_MODE


def test_alpha_mode_two_discs_reading_order():
    img = _disc_image(
        300, 100,
        [(60, 50, 30, (200, 30, 30, 255)), (230, 50, 30, (30, 30, 220, 255))],
    )
    result = run_cut(np.asarray(img), CutParams(padding=0, closing_iters=0, min_area=100))
    assert len(result.pieces) == 2
    # 左岛在前
    p0, p1 = result.pieces
    assert p0["x"] < p1["x"]
    # padding=0 时裁剪紧贴圆外接方
    assert abs(p0["width"] - 60) <= 2 and abs(p0["height"] - 60) <= 2
    # 岛外像素 alpha=0（角落必透明），岛内不透明
    arr0 = np.asarray(p0["image"])
    assert arr0[0, 0, 3] == 0
    assert arr0[30, 30, 3] == 255
    assert (arr0[..., 3] > 0).sum() == p0["area"]


def test_white_mode_flood_fill_keeps_inner_bright():
    # 白底 + 深色方块，方块内有一块亮色（被环绕，不该被吃掉）
    arr = np.full((100, 240, 3), 255, dtype=np.uint8)
    arr[30:70, 40:90] = 20            # 深色方块
    arr[45:55, 60:70] = 250           # 方块内部亮区
    arr[35:65, 150:210] = 60          # 右侧深色圆 方
    img = Image.fromarray(np.dstack([arr, np.full((100, 240), 255, np.uint8)]), "RGBA")

    result = run_cut(np.asarray(img), CutParams(mode="white", padding=10, closing_iters=0, min_area=100))
    assert result.mode == "white"
    assert len(result.pieces) == 2
    p0 = result.pieces[0]
    # 内部亮区被保留（挖掉的只有与边缘连通的白底）
    assert p0["area"] >= 40 * 50
    arr0 = np.asarray(p0["image"])
    assert arr0[0, 0, 3] == 0        # 留白处透明
    assert arr0[30, 35, 3] == 255    # 方块内部亮区保留（全局 y=50,x=65 → crop 30,35）


def test_small_components_attach_to_main_island():
    # 主方块旁边漂浮一个小细节（在主岛 bbox+pad 范围内）
    arr = np.full((120, 120, 3), 255, dtype=np.uint8)
    arr[20:100, 20:100] = 30
    arr[10:16, 50:56] = 30            # 上方 6x6 小细节
    img = Image.fromarray(np.dstack([arr, np.full((120, 120), 255, np.uint8)]), "RGBA")
    result = run_cut(np.asarray(img), CutParams(mode="white", padding=10, closing_iters=0, min_area=1000))
    assert len(result.pieces) == 1
    # 小细节并入主岛 → bbox 上边越过了主方块 y=20
    assert result.pieces[0]["y"] <= 10


def test_reading_order_rows_before_columns():
    img = _disc_image(
        400, 200,
        [
            (300, 150, 25, (200, 30, 30, 255)),  # 右下
            (80, 150, 25, (30, 200, 30, 255)),   # 左下
            (300, 50, 25, (30, 30, 220, 255)),   # 右上
            (80, 50, 25, (220, 220, 30, 255)),   # 左上
        ],
    )
    result = run_cut(np.asarray(img), CutParams(padding=0, closing_iters=0, min_area=100))
    assert [p["id"] for p in result.pieces] == ["island_00", "island_01", "island_02", "island_03"]
    # 顺序：左上 → 右上 → 左下 → 右下
    colors = []
    for p in result.pieces:
        arr = np.asarray(p["image"])
        ys, xs = np.where(arr[..., 3] > 0)
        colors.append(tuple(arr[ys[len(ys) // 2], xs[len(xs) // 2]][:3]))
    assert colors[0] == (220, 220, 30)   # 黄 左上
    assert colors[1] == (30, 30, 220)    # 蓝 右上
    assert colors[2] == (30, 200, 30)    # 绿 左下
    assert colors[3] == (200, 30, 30)    # 红 右下


# ---------------------------------------------------------------------------
# router 集成
# ---------------------------------------------------------------------------

def test_create_job_alpha_mode_roundtrip(tmp_path):
    client, store = make_client(tmp_path)
    img = _disc_image(
        300, 100,
        [(60, 50, 30, (200, 30, 30, 255)), (230, 50, 30, (30, 30, 220, 255))],
    )
    r = _cut(client, _png_bytes(img))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "alpha"
    assert body["piece_count"] == 2
    assert body["pieces"][0]["id"] == "island_00"
    assert body["width"] == 300 and body["height"] == 100

    # 单切片可取
    pr = client.get(f"/api/island-cut/jobs/{body['job_id']}/pieces/island_00.png")
    assert pr.status_code == 200
    assert pr.headers["content-type"] == "image/png"
    cut_img = Image.open(io.BytesIO(pr.content))
    assert cut_img.mode == "RGBA"

    # 整图透明底
    fr = client.get(body["full_url"])
    assert fr.status_code == 200

    # 非法文件名（不在白名单）404
    assert client.get(f"/api/island-cut/jobs/{body['job_id']}/pieces/nope.png").status_code == 404


def test_zip_download_contains_pieces_and_full(tmp_path):
    client, _ = make_client(tmp_path)
    img = _disc_image(300, 100, [(60, 50, 30, (200, 30, 30, 255)), (230, 50, 30, (30, 30, 220, 255))])
    body = _cut(client, _png_bytes(img)).json()

    zr = client.get(body["zip_url"])
    assert zr.status_code == 200
    assert zr.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zr.content)) as zf:
        names = sorted(zf.namelist())
    assert names == sorted(["island_00.png", "island_01.png", FULL_NAME])


def test_min_area_filter_yields_zero_pieces(tmp_path):
    client, _ = make_client(tmp_path)
    img = _disc_image(200, 100, [(60, 50, 10, (200, 30, 30, 255))])
    r = _cut(client, _png_bytes(img), params='{"min_area": 100000}')
    assert r.status_code == 200
    assert r.json()["piece_count"] == 0


def test_bad_params_and_unknown_job(tmp_path):
    client, _ = make_client(tmp_path)
    r = _cut(client, _png_bytes(_disc_image(50, 50, [(25, 25, 8, (200, 0, 0, 255))])), params="not json")
    assert r.status_code == 422

    assert client.get("/api/island-cut/jobs/nope/zip").status_code == 404
    assert client.get("/api/island-cut/jobs/nope/full.png").status_code == 404
    assert client.delete("/api/island-cut/jobs/nope").status_code == 404


def test_delete_job_removes_files(tmp_path):
    client, store = make_client(tmp_path)
    img = _disc_image(200, 100, [(60, 50, 20, (200, 30, 30, 255))])
    body = _cut(client, _png_bytes(img)).json()
    job_dir = store.get(body["job_id"]).dir
    assert job_dir.exists()

    assert client.delete(f"/api/island-cut/jobs/{body['job_id']}").status_code == 200
    assert not job_dir.exists()
    assert client.get(body["zip_url"]).status_code == 404


def test_store_ttl_expires(tmp_path):
    client, store = make_client(tmp_path, ttl_sec=0.05)
    img = _disc_image(200, 100, [(60, 50, 20, (200, 30, 30, 255))])
    body = _cut(client, _png_bytes(img)).json()
    job_dir = store.get(body["job_id"]).dir
    import time

    time.sleep(0.08)
    assert store.get(body["job_id"]) is None
    assert not job_dir.exists()
