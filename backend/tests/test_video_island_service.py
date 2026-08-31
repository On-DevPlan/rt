"""Tests for video_island.service pure functions (algorithm & encoding)."""
import io

import numpy as np
import pytest
from PIL import Image

from rt_backend.island_cut.video_island import service as svc


def _solid(rgb, h=20, w=20):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[..., 0] = rgb[0]; arr[..., 1] = rgb[1]; arr[..., 2] = rgb[2]
    return arr


def _square(rgb, h, w, color):
    arr = _solid(rgb, h, w)
    arr[5:15, 5:15] = color
    return arr


# --- frame_bg ---

def test_frame_bg_returns_median_of_border_pixels():
    img = _solid((200, 200, 200), h=30, w=30)
    bg = svc.frame_bg(img, border=5)
    np.testing.assert_array_equal(bg, np.array([200, 200, 200]))


def test_frame_bg_uses_median_not_mean_when_border_has_outlier():
    img = _solid((200, 200, 200), h=30, w=30)
    img[0, 0] = (10, 10, 10)
    img[29, 29] = (250, 250, 250)
    bg = svc.frame_bg(img, border=5)
    np.testing.assert_array_equal(bg, np.array([200, 200, 200]))


# --- build_mask ---

def test_build_mask_returns_only_largest_component_with_fill_holes():
    bg = np.array([235, 235, 235])
    arr = _solid(tuple(bg), h=200, w=200)
    arr[20:120, 20:120] = (200, 30, 30)         # 主块 100×100 = 10000 px
    arr[150:160, 150:160] = (30, 30, 200)       # 杂色 10×10 = 100 px（会被并入主块因连通）
    arr[170:175, 170:175] = (30, 30, 200)       # 独立小块 5×5=25 px < 主块，会被抛弃
    mask = svc.build_mask(arr, bg, tol=50, close_iter=1)
    assert mask is not None
    assert mask[70, 70] == True
    assert mask[172, 172] == False
    assert mask[0, 0] == False


def test_build_mask_returns_none_when_no_fg():
    bg = np.array([128, 128, 128])
    arr = _solid(tuple(bg), h=40, w=40)
    assert svc.build_mask(arr, bg, tol=10) is None


# --- encode_gif ---

def test_encode_gif_three_frames():
    frames = [
        Image.fromarray(_solid((255, 0, 0), 30, 30), "RGB"),
        Image.fromarray(_solid((0, 255, 0), 30, 30), "RGB"),
        Image.fromarray(_solid((0, 0, 255), 30, 30), "RGB"),
    ]
    out = svc.encode_gif(frames, out_fps=12)
    im = Image.open(io.BytesIO(out))
    assert im.format == "GIF"
    assert im.n_frames == 3


# --- make_preview_png ---

def test_make_preview_png_returns_png_three_tiles():
    rgb = _solid((255, 0, 0), 100, 100)
    masks = {0: np.zeros((100, 100), bool), 1: np.ones((100, 100), bool), 2: np.zeros((100, 100), bool)}
    out = svc.make_preview_png([rgb, rgb, rgb], masks, kept=[0, 1, 2])
    im = Image.open(io.BytesIO(out))
    assert im.format == "PNG"
    assert im.height == 240
    assert im.width > 240


# --- 端到端：合成 MP4 → process_video ---

def _encode_synthetic_mp4(frames_rgb, fps=12):
    """用 av 写一个最简单的 mp4（H.264 在某些 CI 不可用，回退 rawvideo）。"""
    av = pytest.importorskip("av")
    out_path = "/tmp/_synth_island_video.mp4"
    container = av.open(out_path, "w")
    try:
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width, stream.height = frames_rgb[0].shape[1], frames_rgb[0].shape[0]
        stream.pix_fmt = "yuv420p"
        for rgb in frames_rgb:
            vf = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            for p in stream.encode(vf):
                container.mux(p)
        for p in stream.encode():
            container.mux(p)
    finally:
        container.close()
    import pathlib
    return pathlib.Path(out_path).read_bytes()


def test_process_video_end_to_end_synthetic_mp4():
    """5 帧 200×200：前 2 帧背景异常，后 3 帧含红块主体。"""
    H, W = 200, 200
    f0 = np.full((H, W, 3), 250, dtype=np.uint8)
    f1 = np.full((H, W, 3), 240, dtype=np.uint8)
    body = np.full((H, W, 3), 240, dtype=np.uint8)
    body[40:160, 40:160] = (200, 30, 30)
    body[160:165, 160:165] = (30, 30, 200)  # 与主体连通，被并入
    f2 = body.copy(); f3 = body.copy(); f4 = body.copy()
    mp4 = _encode_synthetic_mp4([f0, f1, f2, f3, f4], fps=12)

    result = svc.process_video(mp4, fps=12, max_size=160, bg_tol=50, pad=6,
                               max_duration_sec=30, max_frames=60)
    assert result.frame_count >= 3   # 异常帧被丢
    assert result.gif[:6] in (b"GIF87a", b"GIF89a")
    im = Image.open(io.BytesIO(result.gif))
    assert im.format == "GIF"
    assert max(im.size) <= 160
    assert result.preview[:8] == b"\x89PNG\r\n\x1a\n"


def test_process_video_rejects_oversize_duration():
    av = pytest.importorskip("av")
    H, W = 60, 60
    frames = []
    for _ in range(150):
        f = np.full((H, W, 3), 200, np.uint8)
        f[20:40, 20:40] = (200, 30, 30)
        frames.append(f)
    mp4 = _encode_synthetic_mp4(frames, fps=30)
    with pytest.raises(svc.VideoOversizeError):
        svc.process_video(mp4, fps=30, max_frames=10, max_duration_sec=600)


def test_process_video_rejects_oversize_duration_short():
    """时长直接超 max_duration（用容器 duration）。"""
    av = pytest.importorskip("av")
    H, W = 60, 60
    frames = []
    for _ in range(150):  # 30fps × 5s
        f = np.full((H, W, 3), 200, np.uint8)
        f[20:40, 20:40] = (200, 30, 30)
        frames.append(f)
    mp4 = _encode_synthetic_mp4(frames, fps=30)
    with pytest.raises(svc.VideoOversizeError):
        svc.process_video(mp4, fps=30, max_frames=600, max_duration_sec=2)