"""MP4 → 透明 GIF 算法骨架（移植自 largest_island_gif.py，PyAV 流式）。

核心五要素（与参考脚本 1:1 对齐）：
  1. 边框中位 bg（对角落水印鲁棒）
  2. diff > tol + 闭运算 + 连通域 + 仅最大分量 + binary_fill_holes
  3. 全帧 union bbox + pad
  4. NEAREST 缩放（LANCZOS 在二值 alpha 上振铃会桥接远端小岛）
  5. PIL GIF：disposal=2 / loop=0 / optimize
"""
from __future__ import annotations

import io
from dataclasses import dataclass

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
    delay_ms = max(20, round(1000 / out_fps))  # PIL duration 单位 ms
    frames[0].save(
        buf, format="GIF", save_all=True,
        append_images=frames[1:],
        duration=delay_ms, loop=loop, disposal=2, optimize=True,
    )
    return buf.getvalue()


def make_preview_png(
    rgb_frames: list[np.ndarray],
    masks: dict[int, np.ndarray],
    kept: list[int],
    out_h: int = 240,
) -> bytes:
    """首/中/尾三帧棋盘格 preview（在棋盘上 alpha_composite 叠 RGBA）。"""
    def checker(w, h, tile=10):
        yy, xx = np.mgrid[0:h, 0:w]
        c = (((yy // tile) + (xx // tile)) % 2).astype(np.uint8)
        g = np.where(c == 0, 235, 200).astype(np.uint8)
        return np.dstack([g, g, g, np.full_like(g, 255)])

    if not kept:
        return b""
    picks_idx = [kept[0], kept[len(kept) // 2], kept[-1]]
    tiles = []
    for i in picks_idx:
        if i >= len(rgb_frames):
            continue
        rgb = rgb_frames[i]
        m = masks[i]
        h, w = rgb.shape[:2]
        tw = max(1, int(w * out_h / h))
        rgba = np.dstack([rgb, m * 255]).astype(np.uint8)
        im = Image.fromarray(rgba, "RGBA").resize((tw, out_h), Image.NEAREST)
        bg = Image.fromarray(checker(tw, out_h), "RGBA")
        comp = Image.alpha_composite(bg, im).convert("RGB")
        tiles.append(np.asarray(comp))
    if not tiles:
        return b""
    sep = np.full((out_h, 8, 3), 255, np.uint8)
    out = tiles[0]
    for t in tiles[1:]:
        out = np.hstack([out, sep, t])
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, format="PNG")
    return buf.getvalue()


# --- 全流水线 --------------------------------------------------------------

class VideoOversizeError(Exception):
    """视频帧数/时长超出上限。"""


@dataclass
class VideoResult:
    gif: bytes
    preview: bytes
    frame_count: int
    src_fps: float
    out_fps: float
    final_fps: float
    width: int
    height: int
    duration_sec: float
    output_size_bytes: int
    compression_attempts: int


def process_video(
    data: bytes,
    *,
    fps: int = DEFAULT_FPS,
    max_size: int = DEFAULT_MAX_SIZE,
    bg_tol: int = DEFAULT_BG_TOL,
    pad: int = DEFAULT_PAD,
    max_duration_sec: int = 60,
    max_frames: int = 600,
    max_output_bytes: int | None = None,
) -> VideoResult:
    """PyAV 流式解码 → 全流水线。

    若 max_output_bytes 设置：首次编码后超限则二分 fps 阶梯（fps/2, fps/4, ... 直到 1）
    重新编码直到 ≤ 限值。仍超限抛 ValueError（router 转 413）。
    """
    import av

    container = av.open(io.BytesIO(data), "r", format="mp4")
    try:
        stream = container.streams.video[0]
        src_fps = float(stream.average_rate) if stream.average_rate else 30.0
        duration_sec = float(container.duration / av.time_base) if container.duration else 0.0
        if duration_sec > max_duration_sec:
            raise VideoOversizeError(f"时长 {duration_sec:.1f}s 超过 {max_duration_sec}s")

        step = max(1, round(src_fps / fps))
        out_fps = src_fps / step

        bgs: list[np.ndarray] = []
        frames: dict[int, np.ndarray] = {}
        truncated = False
        for idx, frame in enumerate(container.decode(stream)):
            if idx % step:
                continue
            if len(frames) >= max_frames:
                truncated = True
                break
            rgb = frame.to_ndarray(format="rgb24")
            frames[idx] = rgb
            bgs.append(frame_bg(rgb))
    finally:
        container.close()

    if not frames:
        raise ValueError("视频无可用帧")
    if truncated or len(frames) > max_frames:
        raise VideoOversizeError(f"采样帧数 {len(frames)} 超过 {max_frames}")

    global_bg = np.median(np.array(bgs), axis=0).astype(np.uint8)
    keys = list(frames.keys())
    kept = [k for k in keys if np.abs(bgs[keys.index(k)] - global_bg).max() <= 5]
    if not kept:
        raise ValueError("全部帧背景异常，无可用帧")

    masks_raw: dict[int, np.ndarray | None] = {i: build_mask(frames[i], global_bg, bg_tol) for i in kept}
    masks = {i: m for i, m in masks_raw.items() if m is not None}
    if not masks:
        raise ValueError("全部帧未检测到前景")
    # 仅保留有效帧（与 masks 同步）
    kept = list(masks.keys())

    H, W = next(iter(frames.values())).shape[:2]
    union = np.zeros((H, W), bool)
    for m in masks.values():
        union |= m
    rows = np.where(np.any(union, axis=1))[0]
    cols = np.where(np.any(union, axis=0))[0]
    y0 = max(0, rows[0] - pad)
    y1 = min(H, rows[-1] + 1 + pad)
    x0 = max(0, cols[0] - pad)
    x1 = min(W, cols[-1] + 1 + pad)

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

    # 体积压缩：先全量编码，超限则二分 fps 阶梯
    current_fps = out_fps
    attempts = 1
    gif_bytes = encode_gif(rgba_frames, out_fps=current_fps)
    if max_output_bytes is not None:
        # fps 阶梯：[fps/2, fps/4, fps/8, ...] 直到 1 fps
        for trial_fps in (current_fps / 2, current_fps / 4, current_fps / 8, 1):
            trial_fps = max(1, int(trial_fps))
            if trial_fps >= current_fps:
                continue
            gif_bytes = encode_gif(rgba_frames, out_fps=trial_fps)
            attempts += 1
            current_fps = trial_fps
            if len(gif_bytes) <= max_output_bytes:
                break
        if len(gif_bytes) > max_output_bytes:
            raise ValueError(
                f"无法压缩到 {max_output_bytes} 字节（最小 fps=1 仍为 {len(gif_bytes)}）"
            )

    preview_bytes = make_preview_png(
        [frames[i] for i in kept],
        masks,
        kept=kept,
    )

    return VideoResult(
        gif=gif_bytes,
        preview=preview_bytes,
        frame_count=len(rgba_frames),
        src_fps=src_fps,
        out_fps=out_fps,
        final_fps=current_fps,
        width=tw,
        height=th,
        duration_sec=duration_sec,
        output_size_bytes=len(gif_bytes),
        compression_attempts=attempts,
    )