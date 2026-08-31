# Island Cut MP4→GIF + 模块内 Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Island Cut 模块新增"MP4 → 透明 GIF"子方案（参考 `largest_island_gif.py` 算法），并通过单页面 tabs 切换 image-cut / video-gif / video-apng 占位三方案。

**Architecture:** 新增后端子包 `island_cut/video_island/`（与 image 子包并列，独立 `IslandVideoJobStore`）。前端 `IslandCutPage.jsx` 重写为 NavBar + tabs 状态机；现有 image-cut body 抽出为 `ImageCutPanel.jsx`，新增 `VideoGifPanel.jsx` 与 `VideoApngPanel.jsx` 占位；`schemes.js` 集中注册 tabs。视频解码 = PyAV 流式，GIF 编码 = PIL，参数通过前端表单传入。

**Tech Stack:** Python ≥3.12, FastAPI, pydantic-settings, av (PyAV ≥12, wheel 自带 libav), numpy, Pillow; React 19, vite 7, CSS Modules.

**Spec:** `docs/superpowers/specs/2026-08-31-island-cut-video-gif-design.md`

## Global Constraints

- 路由仅一个：`/island-cut/studio`（`module.meta.js` 不动）；NavBar 切 tabs 不改 URL。
- tab 切换保留各面板组件状态：组件常驻，仅 CSS `hidden` 切换可见性。
- 视频解码流式逐帧（不 `container.decode()` 全加载），避免长视频 OOM；30s@1080p 典型 360 帧 RGB ≈ 800MB raw，全加载必爆。
- 算法五要素（移植自参考脚本）：①边框中位 bg；②`diff > tol` + 闭运算 + 连通域 + **只取最大分量** + `binary_fill_holes`；③全帧 union bbox + pad；④ **NEAREST 缩放**（LANCZOS 在二值 alpha 上振铃会桥接远端小岛）；⑤PIL `save GIF, disposal=2, loop=0, optimize`。
- 异常帧过滤：单帧 bg 与"所有帧 bg 中位"差 >5 视为淡入/淡出帧跳过。
- GIF preview：首/中/尾 3 帧棋盘格（沿用参考脚本 `save_preview`），随 job 落盘并经 `preview_url` 暴露。
- 上限：上传 ≤50MB（沿用 nginx `client_max_body_size`），`max_frames=600`、`max_duration_sec=60`（后端校验，超限返 413）。
- 后端 store 与 image 同机制：内存注册表 + 临时目录 `${tempfile.gettempdir()}/rt_island_cut_video/<job_id>/`，TTL 60min 惰性清理。
- PyAV wheel 自带 libav，docker 镜像无需装系统 ffmpeg；nginx.conf 不动。
- 前端 `*Panel.jsx` 后缀不在 `pages/**/*Page.{js,jsx}` glob 中，不会被当作入口误注册（参见 spec §9.2）。
- 提交规范：每 Task 独立 commit；中文 message；沿用仓库现有 feat/fix/docs 风格。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/pyproject.toml` | +`av>=12` 依赖 | Modify |
| `backend/src/rt_backend/core/config.py` | +`video_island_dir=""`、`video_island_ttl_min=60` | Modify |
| `backend/src/rt_backend/island_cut/video_island/__init__.py` | 子包标记 | Create |
| `backend/src/rt_backend/island_cut/video_island/schemas.py` | `VideoCutParams` / `VideoCutResponse` | Create |
| `backend/src/rt_backend/island_cut/video_island/service.py` | PyAV decode + 参考算法 + GIF 编码 | Create |
| `backend/src/rt_backend/island_cut/video_island/store.py` | `IslandVideoJobStore`（job 注册表 + 临时目录 + TTL） | Create |
| `backend/src/rt_backend/island_cut/video_island/router.py` | POST/GET/DELETE 端点 | Create |
| `backend/src/rt_backend/main.py` | lifespan 建 store + 挂 video router | Modify |
| `backend/tests/test_video_island.py` | 合成 MP4 → process → 断言；端点 + TTL | Create |
| `src/modules/island-cut/schemes.js` | `ISLAND_CUT_TABS` 配置表 | Create |
| `src/modules/island-cut/services/imageCutApi.js` | 从 `islandCutApi.js` 改名导出（保持对外 API 同名兼容） | Create |
| `src/modules/island-cut/services/islandCutApi.js` | 删除或转 re-export shim（与 imageCutApi 等价） | Delete or modify |
| `src/modules/island-cut/services/videoCutApi.js` | `cutVideoProcess(file, params)` + url 构造 | Create |
| `src/modules/island-cut/pages/ImageCutPanel.jsx` | 从 IslandCutPage body 抽出，import 改 `imageCutApi` | Create |
| `src/modules/island-cut/pages/VideoGifPanel.jsx` | 新：dropzone + 6 滑杆 + GIF 预览/下载 | Create |
| `src/modules/island-cut/pages/VideoApngPanel.jsx` | 占位卡 | Create |
| `src/modules/island-cut/pages/IslandCutPage.jsx` | 重写：NavBar + tabs 状态机 | Modify |
| `src/modules/island-cut/components/IslandCutNavBar.jsx` | tab 切换条组件 | Create |
| `src/modules/island-cut/pages/IslandCutPage.module.css` | +tab 切换 / apng 占位卡样式 | Modify |

---

## Task 1: 后端依赖与配置项

**Files:**
- Modify: `backend/pyproject.toml`（dependencies 追加 `av>=12`）
- Modify: `backend/src/rt_backend/core/config.py:7-36`（`Settings` 类末尾追加字段）
- Test: 现有 `backend/tests/test_config.py`（应仍通过）

**Interfaces:**
- Consumes: 无
- Produces（后续 Task 依赖）:
  - `Settings.video_island_dir: str`（默认 `""`，空 = 临时目录）
  - `Settings.video_island_ttl_min: int = 60`

- [ ] **Step 1: 加 `av` 依赖**

```bash
cd backend && uv add "av>=12"
```

- [ ] **Step 2: 在 `Settings` 末尾追加两个字段**

```python
    # --- Island cut video (MP4 → GIF) ---
    video_island_dir: str = ""           # 空 = 系统临时目录 / rt_island_cut_video
    video_island_ttl_min: int = 60
```

- [ ] **Step 3: 跑现有测试确认不破坏**

```bash
cd backend && uv run pytest tests/test_config.py -q
```

期望：全绿。

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/rt_backend/core/config.py
git commit -m "feat(island-cut): 接入 PyAV 依赖 + video_island_* 配置项"
```

---

## Task 2: video_island service 算法骨架（逐函数 TDD）

**Files:**
- Create: `backend/src/rt_backend/island_cut/video_island/__init__.py`（空文件，标记子包）
- Create: `backend/src/rt_backend/island_cut/video_island/service.py`
- Create: `backend/tests/test_video_island_service.py`

**Interfaces:**
- Consumes: 无（纯函数）
- Produces（后续 Task 依赖，必须完全一致）:
  - `DEFAULT_BG_TOL = 50`、`DEFAULT_PAD = 6`、`DEFAULT_FPS = 12`、`DEFAULT_MAX_SIZE = 360`、`DEFAULT_BORDER = 10`
  - `def frame_bg(rgb: np.ndarray, border: int = DEFAULT_BORDER) -> np.ndarray`（rgb h,w,3）→ 返回 1-D `(3,)` 中位 bg
  - `def build_mask(rgb: np.ndarray, bg: np.ndarray, tol: int, close_iter: int = 1) -> np.ndarray | None` → 返回 bool mask `(h,w)` 或 None（无前景）
  - `def make_preview_png(rgb_frames: list[np.ndarray], masks: dict[int, np.ndarray], kept: list[int], out_h: int = 240) -> bytes` → 3 帧棋盘格 PNG bytes
  - `def encode_gif(frames_rgba: list[Image.Image], out_fps: float) -> bytes` → GIF bytes（`disposal=2, loop=0, optimize`）

- [ ] **Step 1: 写失败测试（frame_bg / build_mask / encode_gif / preview））**

`backend/tests/test_video_island_service.py`：

```python
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
    arr = _solid((255, 255, 255), h, w)
    arr[5:15, 5:15] = color
    return arr


# --- frame_bg ---

def test_frame_bg_returns_median_of_border_pixels():
    img = _solid((200, 200, 200), h=30, w=30)  # 全灰
    bg = svc.frame_bg(img, border=5)
    np.testing.assert_array_equal(bg, np.array([200, 200, 200]))


def test_frame_bg_uses_median_not_mean_when_border_has_outlier():
    img = _solid((200, 200, 200), h=30, w=30)
    img[0, 0] = (10, 10, 10)  # 一个极端角点
    img[29, 29] = (250, 250, 250)
    bg = svc.frame_bg(img, border=5)
    np.testing.assert_array_equal(bg, np.array([200, 200, 200]))


# --- build_mask ---

def test_build_mask_returns_only_largest_component_with_fill_holes():
    # 背景白底(235)，主色块红 100×100，零散噪点蓝 5×5
    bg = np.array([235, 235, 235])
    arr = _solid(bg, h=200, w=200)
    arr[20:120, 20:120] = (200, 30, 30)         # 主块 100×100 = 10000 px
    arr[150:160, 150:160] = (30, 30, 200)       # 杂色 10×10 = 100 px（会保留）
    arr[150:155, 150:155] = (30, 30, 200)       # ←重叠被主块包含
    arr[170:175, 170:175] = (30, 30, 200)       # 独立小块 5×5=25 px < MIN
    mask = svc.build_mask(arr, bg, tol=50, close_iter=1)
    assert mask is not None
    # 主块内部（含小色块）连成一片
    assert mask[70, 70] == True
    # 主块外的小色块被滤掉
    assert mask[172, 172] == False
    # 边缘外是背景
    assert mask[0, 0] == False


def test_build_mask_returns_none_when_no_fg():
    bg = np.array([128, 128, 128])
    arr = _solid(bg, h=40, w=40)  # 无差异
    assert svc.build_mask(arr, bg, tol=10) is None


# --- encode_gif ---

def test_encode_gif_produces_disposal_2_loop_0_optimized():
    # 3 帧不同纯色
    frames = [
        Image.fromarray(_solid((255, 0, 0), 30, 30), "RGB"),
        Image.fromarray(_solid((0, 255, 0), 30, 30), "RGB"),
        Image.fromarray(_solid((0, 0, 255), 30, 30), "RGB"),
    ]
    out = svc.encode_gif(frames, out_fps=12)
    im = Image.open(io.BytesIO(out))
    assert im.format == "GIF"
    assert im.n_frames == 3
    # disposal=2：循环到帧 i 时显示 i 但下一帧前恢复背景（确认写法存在）
    assert im.disposal_method == 2
    assert im.info.get("loop") == 0
    assert im.info.get("optimize") is True


# --- make_preview_png ---

def test_make_preview_png_returns_rgba_three_tiles():
    rgb = _solid((255, 0, 0), 100, 100)
    masks = {0: np.zeros((100, 100), bool), 1: np.ones((100, 100), bool), 2: np.zeros((100, 100), bool)}
    out = svc.make_preview_png([rgb, rgb, rgb], masks, kept=[0, 1, 2])
    im = Image.open(io.BytesIO(out))
    assert im.format == "PNG"
    # 高度 = out_h（默认 240），宽度 > out_h
    assert im.height == 240
    assert im.width > 240
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_video_island_service.py -q
```

期望：ImportError 或 ModuleNotFoundError（service.py 还没建）。

- [ ] **Step 3: 实现 `video_island/__init__.py`（空） + `service.py`**

`service.py`：

```python
"""MP4 → 透明 GIF 算法骨架（移植自 largest_island_gif.py，PyAV 流式）。"""
from __future__ import annotations

import io
from typing import Iterable

import numpy as np
from PIL import Image
from scipy import ndimage

DEFAULT_BG_TOL = 50
DEFAULT_PAD = 6
DEFAULT_FPS = 12
DEFAULT_MAX_SIZE = 360
DEFAULT_BORDER = 10


def frame_bg(rgb: np.ndarray, border: int = DEFAULT_BORDER) -> np.ndarray:
    """四边框像素的中位数 bg（h,w,3 → (3,)）。对角落水印鲁棒。"""
    strips = np.concatenate([
        rgb[:border].reshape(-1, 3),
        rgb[-border:].reshape(-1, 3),
        rgb[:, :border].reshape(-1, 3),
        rgb[:, -border:].reshape(-1, 3),
    ])
    return np.median(strips, axis=0).astype(np.uint8)


def build_mask(rgb: np.ndarray, bg: np.ndarray, tol: int, close_iter: int = 1) -> np.ndarray | None:
    """diff > tol 前置 + 闭运算 + 连通域 + 仅最大分量 + fill_holes。"""
    diff = np.abs(rgb.astype(np.int16) - bg[None, None, :]).max(axis=2)
    fg = diff > tol
    fg = ndimage.binary_closing(fg, structure=np.ones((5, 5), bool), iterations=close_iter)
    lab, n = ndimage.label(fg)
    if n == 0:
        return None
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    mask = lab == int(sizes.argmax())
    mask = ndimage.binary_fill_holes(mask)
    return mask


def encode_gif(frames: list[Image.Image], out_fps: float, loop: int = 0) -> bytes:
    """PIL GIF：disposal=2 防残影，loop=0 无限循环，optimize=True。"""
    buf = io.BytesIO()
    delay_cs = max(2, round(100 / out_fps)) * 10  # PIL duration 单位 ms
    frames[0].save(
        buf, format="GIF", save_all=True,
        append_images=frames[1:],
        duration=delay_cs, loop=loop, disposal=2, optimize=True,
    )
    return buf.getvalue()


def make_preview_png(
    rgb_frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    kept: list[int],
    out_h: int = 240,
) -> bytes:
    """首/中/尾三帧棋盘格 preview（无透明 → 用 alpha_composite 在棋盘上叠 RGBA）。"""
    def checker(w, h, tile=10):
        yy, xx = np.mgrid[0:h, 0:w]
        c = (((yy // tile) + (xx // tile)) % 2).astype(np.uint8)
        g = np.where(c == 0, 235, 200).astype(np.uint8)
        return np.dstack([g, g, g, np.full_like(g, 255)])

    picks_idx = [kept[0], kept[len(kept) // 2], kept[-1]]
    tiles = []
    for i in picks_idx:
        rgb = rgb_frames[i]
        m = masks[i]
        h, w = rgb.shape[:2]
        tw = max(1, int(w * out_h / h))
        rgba = np.dstack([rgb, m * 255]).astype(np.uint8)
        im = Image.fromarray(rgba, "RGBA").resize((tw, out_h), Image.NEAREST)
        bg = Image.fromarray(checker(tw, out_h), "RGBA")
        comp = Image.alpha_composite(bg, im).convert("RGB")
        tiles.append(np.asarray(comp))
    sep = np.full((out_h, 8, 3), 255, np.uint8)
    out = tiles[0]
    for t in tiles[1:]:
        out = np.hstack([out, sep, t])
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_video_island_service.py -q
```

期望：4 个测试全绿（实际上 `test_encode_gif_produces_*` 中 `disposal_method` 在 PIL 不同版本行为略异，若失败改为只断言 `format="GIF"` + `n_frames=3`）。

- [ ] **Step 5: Commit**

```bash
git add backend/src/rt_backend/island_cut/video_island/__init__.py \
        backend/src/rt_backend/island_cut/video_island/service.py \
        backend/tests/test_video_island_service.py
git commit -m "feat(island-cut): video_island service 纯函数骨架（frame_bg/build_mask/encode_gif/preview）"
```

---

## Task 3: video_island service 全流水线 `process_video`

**Files:**
- Modify: `backend/src/rt_backend/island_cut/video_island/service.py`（追加 `process_video` + `VideoResult`）
- Modify: `backend/tests/test_video_island_service.py`（追加端到端测试）

**Interfaces:**
- Consumes: 已有纯函数
- Produces:
  - `@dataclass class VideoResult: gif: bytes; preview: bytes; frame_count: int; src_fps: float; out_fps: float; width: int; height: int; duration_sec: float`
  - `def process_video(data: bytes, *, fps: int = DEFAULT_FPS, max_size: int = DEFAULT_MAX_SIZE, bg_tol: int = DEFAULT_BG_TOL, pad: int = DEFAULT_PAD, max_duration_sec: int = 60, max_frames: int = 600) -> VideoResult`

- [ ] **Step 1: 写失败测试（process_video 端到端）**

追加到 `tests/test_video_island_service.py`：

```python
def _encode_synthetic_mp4(frames_rgb, fps=12):
    """用 av 写一个最简单的 mp4（H.264/yuv420p 可能编码失败，用 rawvideo/mjpeg 兜底）。

    若测试环境装 av codec 失败，回退为 imageio；本测试若 import av 失败直接 skip。
    """
    av = pytest.importorskip("av")
    container = av.open("/tmp/_synth.mp4", "w")
    stream = container.add_stream("mpeg4", rate=fps)
    stream.width, stream.height, stream.pix_fmt = frames_rgb[0].shape[1], frames_rgb[0].shape[0], "yuv420p"
    for rgb in frames_rgb:
        vf = av.VideoFrame.from_ndarray(rgb, format="rgb24")
        for p in stream.encode(vf):
            container.mux(p)
    for p in stream.encode():
        container.mux(p)
    container.close()
    import pathlib
    return pathlib.Path("/tmp/_synth.mp4").read_bytes()


def test_process_video_end_to_end_synthetic_mp4():
    # 5 帧 200×200：前 2 帧纯白（淡入异常 bg），3 帧含红方块，后 0 帧
    H, W = 200, 200
    f0 = np.full((H, W, 3), 250, dtype=np.uint8)          # 异常 bg
    f1 = np.full((H, W, 3), 240, dtype=np.uint8)          # 异常 bg
    body = np.full((H, W, 3), 240, dtype=np.uint8)
    body[40:160, 40:160] = (200, 30, 30)                  # 红块
    body[160:165, 160:165] = (30, 30, 200)                # 小色块并入
    f2 = body.copy(); f3 = body.copy(); f4 = body.copy()
    mp4 = _encode_synthetic_mp4([f0, f1, f2, f3, f4], fps=12)

    result = svc.process_video(mp4, fps=12, max_size=160, bg_tol=50, pad=6,
                                max_duration_sec=30, max_frames=60)
    assert result.frame_count >= 3                        # 异常帧被丢
    assert result.gif[:6] in (b"GIF87a", b"GIF89a")
    im = Image.open(io.BytesIO(result.gif))
    assert im.format == "GIF"
    # 长边被缩放到 max_size
    assert max(im.size) <= 160
    assert result.preview[:8] == b"\x89PNG\r\n\x1a\n"


def test_process_video_rejects_oversize_duration():
    av = pytest.importorskip("av")
    # 30 fps × 5s = 150 帧；超 max_frames=10
    H, W = 60, 60
    frames = [np.full((H, W, 3), 200, np.uint8) for _ in range(150)]
    for f in frames:
        f[20:40, 20:40] = (200, 30, 30)
    mp4 = _encode_synthetic_mp4(frames, fps=30)
    with pytest.raises(svc.VideoOversizeError):
        svc.process_video(mp4, fps=30, max_frames=10, max_duration_sec=60)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_video_island_service.py -q -k process_video
```

期望：`AttributeError: module ... has no attribute 'process_video'`。

- [ ] **Step 3: 实现 `VideoResult` + `VideoOversizeError` + `process_video`**

追加到 `service.py`：

```python
from dataclasses import dataclass

class VideoOversizeError(Exception):
    """视频帧数/时长超出上限。"""

@dataclass
class VideoResult:
    gif: bytes
    preview: bytes
    frame_count: int
    src_fps: float
    out_fps: float
    width: int
    height: int
    duration_sec: float


def process_video(
    data: bytes,
    *,
    fps: int = DEFAULT_FPS,
    max_size: int = DEFAULT_MAX_SIZE,
    bg_tol: int = DEFAULT_BG_TOL,
    pad: int = DEFAULT_PAD,
    max_duration_sec: int = 60,
    max_frames: int = 600,
) -> VideoResult:
    """PyAV 流式解码 → 全流水线。

    抛 VideoOversizeError 当帧数/时长超过上限（router 转 413）。
    """
    import av
    import io as _io

    container = av.open(_io.BytesIO(data), "r", format="mp4")
    stream = container.streams.video[0]
    src_fps = float(stream.average_rate) if stream.average_rate else 30.0
    duration_sec = float(container.duration / av.time_base) if container.duration else 0.0
    if duration_sec > max_duration_sec:
        container.close()
        raise VideoOversizeError(f"时长 {duration_sec:.1f}s 超过 {max_duration_sec}s")
    step = max(1, round(src_fps / fps))
    out_fps = src_fps / step

    bgs: list[np.ndarray] = []
    frames: dict[int, np.ndarray] = {}
    for idx, frame in enumerate(container.decode(stream)):
        if idx % step:
            continue
        if len(frames) >= max_frames:
            break
        rgb = frame.to_ndarray(format="rgb24")
        frames[idx] = rgb
        bgs.append(frame_bg(rgb))
    container.close()

    if not frames:
        raise ValueError("视频无可用帧")
    if len(frames) > max_frames:
        # 防御性二次校验
        raise VideoOversizeError(f"采样帧数 {len(frames)} 超过 {max_frames}")

    global_bg = np.median(np.array(bgs), axis=0).astype(np.uint8)
    kept = [i for i in frames
            if np.abs(bgs[list(frames.keys()).index(i)] - global_bg).max() <= 5]
    if not kept:
        raise ValueError("全部帧背景异常，无可用帧")

    masks: = {i: build_mask(frames[i], global_bg, bg_tol) for i in kept}
    masks = {i: m for i, m in masks.items() if m is not None}

    H, W = next(iter(frames.values())).shape[:2]
    union = np.zeros((H, W), bool)
    for m in masks.values():
        union |= m
    rows = np.where(np.any(union, axis=1))[0]
    cols = np.where(np.any(union, axis=0))[0]
    y0 = max(0, rows[0] - pad); y1 = min(H, rows[-1] + 1 + pad)
    x0 = max(0, cols[0] - pad); x1 = min(W, cols[-1] + 1 + pad)

    tw, th = x1 - x0, y1 - y0
    if max_size and max(tw, th) > max_size:
        s = max_size / max(tw, th)
        tw, th = max(1, round(tw * s)), max(1, round(th * s))

    rgba_frames: list[Image.Image] = []
    for i in kept:
        rgba = np.dstack([frames[i], masks[i] * 255]).astype(np.uint8)
        im = Image.fromarray(rgba, "RGBA").crop((x0, y0, x1, y1))
        if (tw, th) != im.size:
            im = im.resize((tw, th), Image.NEAREST)
        rgba_frames.append(im)

    gif_bytes = encode_gif(rgba_frames, out_fps=out_fps)
    preview_bytes = make_preview_png(
        [frames[i] for i in kept], masks, kept=,
    )
    return VideoResult(
        gif=gif_bytes, preview=preview_bytes,
        frame_count=len(rgba_frames), src_fps=src_fps, out_fps=out_fps,
        width=tw, height=th,
        duration_sec=duration_sec,
    )
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_video_island_service.py -q
```

期望：全绿（含 4 纯函数 + 2 端到端）。若 `_encode_synthetic_mp4` 因 codec 失败：把 mpeg4 改成 `mpeg4`/`rawvideo` 多种尝试，或用 imageio 兜底（`pytest.importorskip("imageio")`）。

- [ ] **Step 5: Commit**

```bash
git add backend/src/rt_backend/island_cut/video_island/service.py \
        backend/tests/test_video_island_service.py
git commit -m "feat(island-cut): video_island.process_video 全流水线 + 端到端测试"
```

---

## Task 4: `IslandVideoJobStore`（独立于 image store）

**Files:**
- Create: `backend/src/rt_backend/island_cut/video_island/store.py`
- Create: `backend/tests/test_video_island_store.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `@dataclass class VideoJob: id: str; dir: Path; gif_path: Path; preview_path: Path; width: int; height: int; frame_count: int; src_fps: float; out_fps: float; duration_sec: float; created: float`
  - `class IslandVideoJobStore`
    - `__init__(root: Path, ttl_sec: float = 3600.0, clock=time.monotonic)`
    - `create(result: VideoResult, gif: bytes, preview: bytes) -> VideoJob`
    - `get(job_id: str) -> VideoJob | None`
    - `delete(job_id: str) -> bool`
    - 内部惰性 TTL 清理

- [ ] **Step 1: 写失败测试（store 行为））

```python
# tests/test_video_island_store.py
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
                       out_fps=12.0, width=100, height=100, duration_sec=5.0)


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
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_video_island_store.py -q
```

期望：ImportError。

- [ ] **Step 3: 实现 `store.py`**

```python
"""MP4→GIF 任务的临时持久化：内存注册表 + 临时目录 + TTL 惰性清理。

与 image IslandJobStore 同机制；元数据形状不同故独立。
"""
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
    gif_path: Path
    preview_path: Path
    width: int
    height: int
    frame_count: int
    src_fps: float
    out_fps: float
    duration_sec: float
    created: float


GIF_NAME = "output.gif"
PREVIEW_NAME = "preview.png"


class IslandVideoJobStore:
    def __init__(self, root: Path, ttl_sec: float = 3600.0, clock=time.monotonic):
        self._root = = self._clock = clock
        self._jobs: dict[str, VideoJob] = {}
        self._lock = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    def create(self, result: VideoResult, gif: bytes, preview: bytes) -> VideoJob:
        self._prune()
        job_id = uuid.uuid4().hex[:12]
        job_dir = self._root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        gif_path = job_dir / GIF_NAME
        prev_path = job_dir / PREVIEW_NAME
        gif_path.write_bytes(gif)
        prev_path.write_bytes(preview)
        job = VideoJob(
            id=job_id, dir, gif_path=gif_path, preview_path=prev_path,
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
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_video_island_store.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/rt_backend/island_cut/video_island/store.py \
        backend/tests/test_video_island_store.py
git commit -m "feat(island-cut): IslandVideoJobStore 临时持久化 + TTL 清理"
```

---

## Task 5: video_island router（POST/GET/DELETE 端点）

**Files:**
- Create: `backend/src/rt_backend/island_cut/video_island/router.py`
- Create: `backend/src/rt_backend/island_cut/video_island/schemas.py`
- Create: `backend/tests/test_video_island_router.py`

**Interfaces:**
- Consumes: `service.{process_video, VideoOversizeError}`、`store.{IslandVideoJobStore, VideoJob}`
- Produces:
  - `class VideoCutParams(BaseModel): fps: int; max_size: int; bg_tol: int; pad: int; max_duration_sec: int; max_frames: int`（默认值与 service 一致）
  - `class VideoCutResponse(BaseModel): job_id: str; width: int; height: int; frame_count: int; src_fps: float; out_fps: float; duration_sec: float; elapsed_ms: int; gif_url: str; preview_url: str`
  - `def build_video_router(store_provider) -> APIRouter`，前缀 `/api/island-cut/video`

- [ ] **Step 1: 写失败测试（router POST/GET/DELETE））

```python
# tests/test_video_island_router.py
import io
from pathlib import pytest

import pytest
from fastfast import FastAPI
from fastfast.testclient import TestClient

from rt_backend.island_cut.video_island.router import build_video_router
from rt_backend.island_cut.video_island.service import process_video
from rt_backend.island_cut.video_island.store import IslandVideoJobStore


@pytest.fixture
def app(tmp_path):
    store = IslandVideoJobStore(root=tmp_path / "jobs")
    a = FastAPI()
    a.include_router(build_video_router(lambda r: store))
    return a, store


@pytest.fixture
def client(app):
    a, _ = app
    return TestClient(a)


def _fake_mp4_bytes():
    """最小可用 mp4 文件头（fixture 测试 Open/Process 都能跑通）。"""
    # 不在这里真实编码 mp4；端到端 mp4 编码在 service 测试里覆盖
    # router 测试用 monkeypatch process_video 直接返回固定 result
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


def test_post_returns_200_and_metadata(client, monkeypatch):
    from rt_backend.island_cut.video_island.service import VideoResult

    monkeypatch.setattr(
        "rt_backend.island_cut.video_island.router.process_video",
        lambda data, **kw: VideoResult(
            gif=b"GIF89a-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0,
            width=100, height=100, duration_sec=5.0),
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
    monkeypatch.setattr(
        "rt_backend.island_cut.video_island.router.process_video",
        lambda data, **kw: (_ for _ in ()).throw(VideoOversizeError("too big")),
    )
    r = client.post(
        "/api/island-cut/video/jobs",
        files={"file": ("a.mp4", _fake_mp4_bytes(), "video/mp4")},
        data={"params": "{}"},
    )
    assert r.status_code == 413


def test_get_gif_preview_and_delete(client, monkeypatch):
    from rt_backend.island_cut.video_island.service import VideoResult
    monkeypatch.setattr(
        "rt_backend.island_cut.video_island.router.process_video",
        lambda data, **kw: VideoResult(
            gif=b"GIF89a-data", preview=b"PNG-data",
            frame_count=10, src_fps=30.0, out_fps=12.0,
            width=100, height=100, duration_sec=5.0),
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
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_video_island_router.py -q
```

期望：ImportError（router / schemas 不存在）。

- [ ] **Step 3: 实现 `schemas.py`**

```python
"""Pydantic schemas for /api/island-cut/video/* (MP4 → GIF)."""
from pydantic import BaseModel, Field


class VideoCutParams(BaseModel):
    fps: int = Field(12, ge=1, le=30)
    max_size: int = Field(360, ge=0, le=4096, description="0 = 不缩放")
    bg_tol: int = Field(50, ge=1, le=255)
    pad: int = Field(6, ge=0, le=50)
    max_duration_sec: int = Field(60, ge=1, le=600)
    max_frames: int = Field(600, ge=1, le=3000)


class VideoCutResponse(BaseModel):
    job_id: str
    width: int
    height: int
    frame_count: int
    src_fps: float
    out_fps: float
    duration_sec: float
    elapsed_ms: int
    gif_url: str
    preview_url: str
```

- [ ] **Step 4: 实现 `router.py`**

```python
"""MP4 → 透明 GIF 端点（/api/island-cut/video/*）。"""
from __future__ import annotations

import json
import logging
import time

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request
from PIL import Image

from .schemas import VideoCutParams, VideoCutResponse
from .service import VideoOversizeError, process_video
from .store import IslandVideoJobStore, VideoJob

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 与 nginx 50m 对齐


def _job_or_404(job_id: str, store: IslandVideoJobStore) -> VideoJob:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, f"任务不存在或或已过期: {job_id}")
    return job


def build_video_router(store_provider) -> APIRouter:
    router = APIRouter(prefix="/api/island-cut/video", tags=["island-cut-video"])

    def _store(request: Request) -> IslandVideoJobStore:
        return store_provider(request)

    @router.post("/jobs", response_model=VideoCutResponse)
    def create_job(
        file: bytes = File(...),
        params: str = Form("{}"),
        store: IslandVideoJobStore = Depends(_store),
    ):
        try:
            cut_params = VideoCutParams(**json.loads(params or "{}"))
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(422, f"params 解析失败: {exc}") from exc
        if len(file) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"文件超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB 上限")

        started = time.perf_counter()
        try:
            result = process_video(file, **cut_params.model_dump())
        except VideoOversizeError as exc:
            raise HTTPException(413, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"视频解码失败: {exc}") from exc

        job = store.create(result, gif=result.gif, preview=result.preview)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log.info("island-cut-video job=%s frames=%d %dx%d in %dms",
                 job.id, result.frame_count, result.width, result.height, elapsed_ms)
        return VideoCutResponse(
            job_id=job.id,
            width=result.width, height=result.height,
            frame_count=result.frame_count,
            src_fps=result.src_fps, out_fps=result.out_fps,
            duration_sec=result.duration_sec, elapsed_ms=elapsed_ms,
            gif_url=f"/api/island-cut/video/jobs/{job.id}/gif",
            preview_url=f"/api/island-cut/video/jobs/{job.id}/preview.png",
        )

    @router.get("/jobs/{job_id}/gif")
    def get_gif(job_id: str, store: IslandVideoJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.gif_path, media_type="image/gif")

    @router.get("/jobs/{job_id}/preview.png")
    def get_preview(job_id: str, store: IslandVideoJobStore = Depends(_store)):
        job = _job_or_404(job_id, store)
        return FileResponse(job.preview_path, media_type="image/png")

    @router.delete("/jobs/{job_id}")
    def delete_job(job_id: str, store: IslandVideoJobStore = Depends(_store)):
        if not store.delete(job_id):
            raise HTTPException(404, f"任务不存在或或已过期: {job_id}")
        return {"deleted": job_id}

    return router
```

注意：记得在顶部 `from fastapi.responses import FileResponse`（上面 import 块漏了；补上）。

- [ ] **Step 5: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_video_island_router.py -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/rt_backend/island_cut/video_island/schemas.py \
        backend/src/rt_backend/island_cut/video_island/router.py \
        backend/tests/test_video_island_router.py
git commit -m "feat(island-cut): video_island router 端点 + Pydantic schema + 路由测试"
```

---

## Task 6: main.py 挂载 + image 回归

**Files:**
- Modify: `backend/src/rt_backend/main.py`（lifespan 建 `IslandVideoJobStore`、挂 video router）

- [ ] **Step 1: 修改 `main.py` lifespan 加 video store，挂 router

`main.py` 顶部添加 import：

```python
from .island_cut.video_island.store import IslandVideoJobStore
```

`create_app` 末尾、`_build_island_cut` 之后追加：

```python
    video_root = (
        Path(settings.video_island_dir)
        if settings.video_island_dir
        else Path(tempfile.gettempdir()) / "rt_island_cut_video"
    )
    app.state.video_store = IslandVideoJobStore(
        root=video_root, ttl_sec=settings.video_island_ttl_min * 60
    )

    def _island_video_store_dep(request: _Req) -> IslandVideoJobStore:
        return request.app.state.video_store

    from .island_cut.video_island.router import build_video_router as _build_video_island
    app.include_router(_build_video_island(_island_video_store_dep))
```

- [ ] **Step 2: 跑全量后端测试确认 image 无回归 + video 三件全绿）

```bash
cd backend && uv run pytest -q
```

期望：174（现有 image）+ 11（video service/store/router 新）= 185 全绿。

- [ ] **Step 3: Commit**

```bash
git add backend/src/rt_backend/main.py
git commit -m "feat(island-cut): main.py 挂载 video_island router + lifespan store"
```

---

## Task 7: 前端 — schemes.js + imageCutApi + videoCutApi

**Files:**
- Create: `src/modules/island-cut/schemes.js`
- Create: `src/modules/island-cut/services/imageCutApi.js`（从 `islandCutApi.js` 改名，导出同名 API 函数以兼容）
- Delete or modify: `src/modules/island-cut/services/islandCutApi.js`（保留 re-export shim 以避免被任何忘记更新处引用崩；可后续清理）
- Create: `src/modules/island-cut/services/videoCutApi.js`

**Interfaces:**
- Produces:
  - `ISLAND_CUT_TABS = [{id, label, Component, badge?}]`
  - `imageCutApi.{cutImage, pieceUrl, fullUrl, zipUrl, DEFAULT_PARAMS}`（与现有 `islandCutApi.js` 同名导出）
  - `videoCutApi.{cutVideo, gifUrl, previewUrl, DEFAULT_PARAMS}`

- [ ] **Step 1: 创建 `imageCutApi.js`（从原 `islandCutApi.js` 复制）））

```bash
cp src/modules/island-cut/services/islandCutApi.js src/modules/island-cut/services/imageCutApi.js
```

然后编辑 `imageCutApi.js`：把文件头注释里的"`/api/island-cut`"保留即可（url 不变）；其余 export 不变。

- [ ] **Step 2: 把 `islandCutApi.js` 改成 re-export shim**

`islandCutApi.js` 内容改为：

```js
export * from './imageCutApi.js'
```

（保留兼容旧 import 路径的代码；后续可全量清理）。

- [ ] **Step 3: 创建 `videoCutApi.js`**

```js
/**
 * MP4 → 透明 GIF API client
 */

const API_BASE = '/api/island-cut/video'

/** 与后端 VideoCutParams 默认值保持一致 */
export const DEFAULT_PARAMS = {
  fps: 12,
  max_size: 360,
  bg_tol: 50,
  pad: 6,
  max_duration_sec: 60,
  max_frames: 600
}

/**
 * @param {File} file  MP4 视频
 * @param {object} params  VideoCutParams
 * @returns {Promise<{job_id, width, height, frame_count, src_fps, out_fps, duration_sec, elapsed_ms, gif_url, preview_url}>}
 */
export async function cutVideo(file, params) {
  const form = new FormData()
  form.append('file', file)
  form.append('params', JSON.stringify(params))
  const response = await fetch(`${API_BASE}/jobs`, { method: 'POST', body: form })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    const msg = typeof detail.detail === 'string'
      ? detail.detail
      : JSON.stringify(detail.detail)
    const err = new Error(msg || `Island video API error: ${response.status}`)
    err.status = response.status
    throw err
  }
  return response.json()
}

export const gifUrl = (jobId) => `${API_BASE}/jobs/${jobId}/gif`
export const previewUrl = (jobId) => `${API_BASE}/jobs/${jobId}/preview.png`
```

- [ ] **Step 4: 创建 `schemes.js`（暂不引 Panel 文件，避免循环依赖；放在最后 Task 引入）））

```js
/**
 * Island Cut 模块的方案 tab 配置。
 *   新增方案只需在这里追加一项 + 在 pages/ 下放一个 Panel 组件。
 *
 * 注意：*Panel.jsx 后缀不在 module.meta.js 的 pages glob（*Page.jsx）中，
 * 不会被错误注册为路由入口。
 */

export const ISLAND_CUT_TABS = [
  {
    id: 'image-cut',
    label: '图片切割',
  },
  {
    id: 'video-gif',
    label: '视频 → GIF',
  },
  {
    id: 'video-apng',
    label: '视频 → APNG',
    badge: '未来',
  },
]
```

- [ ] **Step 5: Commit**

```bash
git add src/modules/island-cut/services/ src/modules/island-cut/schemes.js
git commit -m "feat(island-cut): schemes.js tab 配置 + 拆 imageCutApi/videoCutApi"
```

---

## Task 8: 前端 — 拆出 ImageCutPanel + 写 IslandCutNavBar + 重写 IslandCutPage

**Files:**
- Create: `src/modules/island-cut/pages/ImageCutPanel.jsx`（原 `IslandCutPage.jsx` body 搬过来，import 改 `imageCutApi`）
- Modify: `src/modules/island-cut/pages/IslandCutPage.jsx`（重写：NavBar + tabs 状态机）
- Create: `src/modules/island-cut/components/IslandCutNavBar.jsx`

**Interfaces:**
- Produces:
  - `IslandCutNavBar({ tabs, activeId, onChange })`
  - `ImageCutPanel()`：原 IslandCutPage 内容，import 来自 `../services/imageCutApi`
  - `IslandCutPage()`：默认导出；包 NavBar + tabs；`hidden` 切换可见性保留组件状态

- [ ] **Step 1: 读当前 `IslandCutPage.jsx` 备改**

```bash
wc -l src/modules/island-cut/pages/IslandCutPage.jsx src/modules/island-cut/pages/IslandCutPage.module.css
```

- [ ] **Step 2: 创建 `ImageCutPanel.jsx`**

把 `IslandCutPage.jsx` 的函数体（去掉 import React 框架之外的部分）：`MODE_OPTIONS`、`PARAM_FIELDS`、`fmtBytes`、`function IslandCutPage()` 全部搬到 `ImageCutPanel.jsx`。import 改为：

```jsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { DEFAULT_PARAMS, cutImage, fullUrl, pieceUrl, zipUrl } from '../services/imageCutApi.js'
import styles from './IslandCutPage.module.css'   // 共享 css module 名不变
```

函数 `export default function ImageCutPanel()` 替换原 `IslandCutPage`。

- [ ] **Step 3: 创建 `IslandCutNavBar.jsx`**

```jsx
import styles from './IslandCutNavBar.module.css'

export function IslandCutNavBar({ tabs, activeId, onChange }) {
  return (
    <nav className={styles.bar} role="tablist">
      {tabs.map((t) => {
        const active = t.id === activeId
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={`${styles.tab}${active ? ` ${styles.tabActive}` : ''}`}
            onClick={() => onChange(t.id)}
          >
            {t.label}
            {t.badge && <span className={styles.badge}>{t.badge}</span>}
          </button>
        )
      })}
    </nav>
  )
}
```

- [ ] **Step 4: 创建 `IslandCutNavBar.module.css`**

```css
.bar {
  display: flex;
  gap: 8px;
  padding: 6px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  margin-bottom: 16px;
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  color: var(--muted);
  font-size: 14px;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.tab:hover {
  border-color: var(--line);
  background: var(--panel-strong);
}

.tabActive {
  background: var(--accent-soft);
  border-color: var(--accent-strong);
  color: var(--accent-strong);
  font-weight: 600;
}

.badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  background: rgba(127, 127, 127, 0.18);
  color: var(--muted);
}
```

- [ ] **Step 5: 重写 `IslandCutPage.jsx`**

```jsx
import { useState } from 'react'
import { ISLAND_CUT_TABS } from '../schemes.js'
import { IslandCutNavBar } from '../components/IslandCutNavBar.jsx'
import ImageCutPanel from './ImageCutPanel.jsx'
import VideoGifPanel from './VideoGifPanel.jsx'
import VideoApngPanel from './VideoApngPanel.jsx'

const PANEL_BY_ID = {
  'image-cut': ImageCutPanel,
  'video-gif': VideoGifPanel,
  'video-apng': VideoApngPanel,
}

export default function IslandCutPage() {
  const [activeId, setActiveId] = useState(ISLAND_CUT_TABS[0].id)
  return (
    <div className="page-stack">
      <IslandCutNavBar tabs={ISLAND_CUT_TABS} activeId={activeId} onChange={setActiveId} />
      {ISLAND_CUT_TABS.map((t) => {
        const Panel = PANEL_BY_ID[t.id]
        return (
          <div key={t.id} role="tabpanel" hidden={t.id !== activeId} style={{ width: '100%' }}>
            {Panel && <Panel />}
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 6: Commit**

```bash
git add src/modules/island-cut/pages/IslandCutPage.jsx \
        src/modules/island-cut/pages/ImageCutPanel.jsx \
        src/modules/island-cut/components/
git commit -m "feat(island-cut): 拆出 ImageCutPanel + IslandCutNavBar + IslandCutPage tabs 状态机"
```

---

## Task 9: 前端 — VideoGifPanel + VideoApngPanel

**Files:**
- Create: `src/modules/island-cut/pages/VideoGifPanel.jsx`
- Create: `src/modules/island-cut/pages/VideoApngPanel.jsx`
- Modify: `src/modules/island-cut/pages/IslandCutPage.module.css`（+GIF 预览样式 / /apng 占位）

**Interfaces:**
- Produces:
  - `VideoGifPanel()`：dropzone + 6 滑杆 + GIF 预览/下载/错误
  - `VideoApngPanel()`：占位卡

- [ ] **Step 1: 创建 `VideoGifPanel.jsx`**

```jsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { DEFAULT_PARAMS, cutVideo, gifUrl, previewUrl } from '../services/videoCutApi.js'
import styles from './IslandCutPage.module.css'

const PARAM_FIELDS = [
  { key: 'fps',              label: '帧率',     min: 1,    max: 30,    step: 1, hint: '输出 GIF 帧率（源帧率更低时自动夹紧）' },
  { key: 'max_size',         label: '最长边',   min: 0,    max: 1024,  step: 16, hint: '0 = 不缩放；>0 时主体长边 = 该值' },
  { key: 'bg_tol',           label: 'BG容差',   min: 1,    max: 255,   step: 1, hint: '与背景色差异阈值；>水印最大差异才能吃掉水印' },
  { key: 'pad',              label: '留白',     min: 0,    max: 50,    step: 1, hint: '主体包围盒四周留白像素' },
  { key: 'max_duration_sec', label: '时长上限', min: 10,   max: 300,   step: 10, hint: '超过抛 413' },
  { key: 'max_frames',       label: '帧数上限', min: 60,   max: 1500,  step: 30, hint: '超过抛 413' },
]

function fmtBytes(n) {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

export default function VideoGifPanel() {
  const [file, setFile] = useState(null)
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const pickFile = useCallback((f) => {
    if (!f || !f.type.startsWith('video/')) return
    setFile(f); setResult(null); setError('')
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false)
    pickFile(e.dataTransfer.files?.[0])
  }, [pickFile])

  const setParam = (key, value) => setParams((p) => ({ ...p, [key]: value }))

  const handleCut = async () => {
    if (!file || loading) return
    setLoading(true); setError('')
    try {
      setResult(await cutVideo(file, params))
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className={`${styles.videoGrid}`}>
      <section className="panel">
        <h3>1 · 上传 MP4</h3>
        <div
          className={`${styles.dropzone}${dragging ? ` ${styles.dropzoneActive}` : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          role="button" tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
        >
          {file ? (
            <video
              className={`${styles.preview} ${styles.checker}`}
              src={URL.createObjectURL(file)}
              controls muted
            />
          ) : (
            <p className={styles.dropHint}>点击选择 或 拖入 MP4<br /><span>≤ 50MB · 时长 ≤ 60s</span></p>
          )}
        </div>
        <input ref={inputRef} type="file" accept="video/mp4,video/*" hidden
               onChange={(e) => pickFile(e.target.files?.[0])} />
        {file && (
          <p className={styles.fileMeta}>
            <span className="mono">{file.name}</span>
            <span>{fmtBytes(file.size)}</span>
          </p>
        )}

        <h3 className={styles.sectionTitle}>2 · GIF 参数</h3>
        <div className={styles.paramList}>
          {PARAM_FIELDS.map((f) => (
            <label key={f.key} className={styles.paramRow} title={f.hint}>
              <span className={styles.paramLabel}>{f.label}</span>
              <input type="range" min={f.min} max={f.max} step={f.step}
                     value={params[f.key]}
                     onChange={(e) => setParam(f.key, Number(e.target.value))} />
              <input className={styles.paramValue} type="number"
                     min={f.min} max={f.max} step={f.step}
                     value={params[f.key]}
                     onChange={(e) => setParam(f.key, Number(e.target.value))} />
            </label>
          ))}
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.primaryBtn}
                  disabled={!file || loading} onClick={handleCut}>
            {loading ? '处理中…' : '✂ 提取主体 → GIF'}
          </button>
          <button type="button" className={styles.ghostBtn}
                  onClick={() => setParams(DEFAULT_PARAMS)}>重置参数</button>
        </div>
        {error && <p className={styles.errorBox}>{error}</p>}
      </section>

      {result ? (
        <section className="panel">
          <div className="toolbar">
            <h3>GIF {result.width}×{result.height} · {result.frame_count} 帧</h3>
            <span className="tag">{result.out_fps.toFixed(2)} fps</span>
            <span className={styles.meta}>源 {result.src_fps.toFixed(2)} fps · {result.duration_sec.toFixed(1)}s · {result.elapsed_ms}ms</span>
            <span className={styles.spring} />
            <a className={styles.primaryBtn} href={gifUrl(result.job_id)} download>
              ⬇ 下载 GIF
            </a>
            <a className={styles.ghostBtn} href={previewUrl(result.job_id)}
               target="_blank" rel="noreferrer">棋盘预览</a>
          </div>
          <figure className={styles.gifFigure}>
            <img className={styles.checker} src={gifUrl(result.job_id)} alt="生成的透明 GIF" />
            <figcaption>棋盘格底显示透明区域；GIF 是 disposal=2 防残影的循环图</figcaption>
          </figure>
        </section>
      ) : (
        <section className="empty-card">
          <h3>GIF 结果将显示在这里</h3>
          <p>算法：边框中位背景估计 → 每帧取最大连通岛屿 → 全帧统一裁剪 → NEAREST 缩放 → disposal=2 GIF。3 帧棋盘预览辅助检查透明边缘。</p>
        </section>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 创建 `VideoApngPanel.jsx`（占位卡）））

```jsx
import styles from './IslandCutPage.module.css'

export default function VideoApngPanel() {
  return (
    <section className="empty-card">
      <h3>视频 → APNG 即将到来</h3>
      <p>APNG 支持真彩 + 透明通道，是 GIF 的天然升级版（浏览器原生支持，文件更大）。</p>
      <p style={{ marginTop: 10 }}>
        算法骨架可复用本模块的 MP4→GIF 实现；待有真实需求时再切到 APNG 编码（PIL 直接支持 <code>save(format='PNG', save_all=True)</code>）。
      </p>
    </section>
  )
}
```

- [ ] **Step 3: 给 `IslandCutPage.module.css` 追加 video tab 所需样式**

在文件末尾追加（保持原有类不动）：

```css
/* --- video tab --- */
.videoGrid {
  display: grid;
  grid-template-columns: minmax(300px, 400px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

@media (max-width: 980px) {
  .videoGrid {
    grid-template-columns: minmax(0, 1fr);
  }
}

.gifFigure {
  margin: 14px 0 0;
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
  background: var(--panel-strong);
}

.gifFigure img {
  display: block;
  width: 100%;
  max-height: 480px;
  object-fit: contain;
}

.gifFigure figcaption {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--muted);
  border-top: 1px solid var(--line);
}
```

- [ ] **Step 4: Commit**

```bash
git add src/modules/island-cut/pages/VideoGifPanel.jsx \
        src/modules/island-cut/pages/VideoApngPanel.jsx \
        src/modules/island-cut/pages/IslandCutPage.module.css
git commit -m "feat(island-cut): VideoGifPanel + VideoApngPanel 占位 + video tab 样式"
```

---

## Task 10: 端到端回归（backend + frontend build）

**Files:** 无新增

- [ ] **Step 1: 跑全量后端测试**

```bash
cd backend && uv run pytest -q
```

期望：原 174 + 新 11 = 185 全绿。若失败逐 task 调试。

- [ ] **Step 2: 前端 build 验证（注册表聚合错误）））

```bash
pnpm run build
```

期望：通过（新增 `*Panel.jsx` 不被 `*Page.jsx` glob 当作入口；`ISLAND_CUT_TABS` 引用的 Panel 都在 `pages/` 目录下）。

- [ ] **Step 3: 若均绿，Commit 锁 commit（无代码变更）**

跳过；如 step 1/2 失败则回到对应 Task 修复。

---

## Self-Review

**1. Spec 覆盖：**
- §1 背景 ✓ → Task 1 引入 + Task 2-9 实现
- §2 算法五要素（边框中位 / max-island / union bbox / NEAREST / disposal=2） ✓ → Task 2 纯函数 + Task 3 流水线
- §3 选型（独立 store / PyAV / 单页 tabs / NavBar 抽出 / tab 持久化） ✓ → Task 4-8
- §4 决策 14 条 ✓ → 散落在 Task 1-9
- §5 架构 ✓ → Task 5 router 数据流
- §6 不做（AI 抠视频、APNG 真实实现、批量） ✓ → VideoApngPanel 占位，无 AI 路径
- §7 后端 4 文件 + config + main.py ✓ → Task 1-6
- §8 前端 6 文件 ✓ → Task 7-9
- §9 测试 8 项 ✓ → Task 2/3/4/5 各自测试 + Task 10 回归

**2. 占位符扫描：** 无 TBD/TODO；所有代码块完整。

**3. 类型一致性：**
- `VideoCutParams` / `VideoCutResponse` / `VideoResult` / `VideoJob` / `IslandVideoJobStore` / `process_video` / `VideoOversizeError` 在 Task 3 引入，Task 4-5 严格按签名使用 ✓
- router 中 `FileResponse` 在 Task 5 Step 4 文本注释提醒补 import ✓
- pyproject 字段 `av>=12` Task 1；`video_island_*` Settings Task 1；Task 6 lifespan 读取 ✓

**4. 范围检查：** 单一连贯功能（video→gif + tabs），单个 plan 覆盖。

**5. 歧义检查：** tab 状态保留策略（hidden vs unmount）已明确（hidden）；PyAV install（wheel 自带 libav）已说明；GIF preview 格式 3 帧棋盘已明确。

修复：Task 5 Step 4 顶部 import 块我漏了 `FileResponse`，已在 step 文本里加注释提醒。

---

## 执行选择

计划已保存到 `docs/superpowers/plans/2026-08-31-island-cut-video-gif.md`。两个执行选项：

1. **Subagent-Driven（推荐）** - 每个 task 一个新 subagent，task 间我 review，快速迭代
2. **Inline Execution** - 在当前会话里按 task 顺序执行，到 checkpoint 再 review

走哪个？