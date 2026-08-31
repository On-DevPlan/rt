"""MP4 → 透明 sprite sheet + 元数据（自完备；移植 .tool/video-sheet/scripts/build_sheet.py）。

算法（参考 build_sheet.py）：
  1. ffmpeg 抽帧（带 mpdecimate 去重复帧 + 重采样到目标 fps）
  2. 每帧独立：边缘 bg 估计 + 色距掩膜 + 边界泛洪 + closing + 仅最大岛 + 高斯羽化
  3. 全片 union bbox → 统一画布
  4. 拼 sprite sheet 网格 + frames.json + 预览 APNG/WebP
  5. 落盘：sheet.png / frames/frame_*.png / frames.json / preview.apng / preview.webp

与 video_island / video_webp / video_apng 不同的算法（不是 max-island 系列）。
横向隔离：本文件不 import 其他 video_* 子包。
"""
from __future__ import annotations

import io
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


# ===== 算法原语 =====

def estimate_bg_from_border(rgba: np.ndarray) -> np.ndarray:
    """四边像素的颜色中位数（uint8 RGB）。抗噪。"""
    edges = np.concatenate([
        rgba[0], rgba[-1],
        rgba[:, 0], rgba[:, -1],
    ])[:, :3]
    return np.median(edges, axis=0).astype(np.uint8)


def color_distance_mask(rgba: np.ndarray, bg: np.ndarray, tol: float) -> np.ndarray:
    """色距 < tol 视为背景候选（bool）。"""
    diff = rgba[..., :3].astype(np.int32) - bg.astype(np.int32)
    dist = np.sqrt((diff ** 2).sum(axis=-1))
    return dist < tol


def flood_fill_background(is_bg: np.ndarray) -> np.ndarray:
    """与边缘连通的 bg 候选 = 真背景。"""
    lbl, _ = ndimage.label(is_bg)
    border_labels = (
        set(lbl[0].tolist())
        | set(lbl[-1].tolist())
        | set(lbl[:, 0].tolist())
        | set(lbl[:, -1].tolist())
    )
    border_labels.discard(0)
    if not border_labels:
        return np.zeros_like(is_bg)
    return np.isin(lbl, list(border_labels))


def keep_largest_island(fg: np.ndarray, min_area: int) -> np.ndarray:
    """保留最大连通域 = 主体色块，其余清零。"""
    lbl, n = ndimage.label(fg)
    if n == 0:
        return np.zeros_like(fg)
    sizes = np.bincount(lbl.ravel())[1:]
    if (sizes >= min_area).sum() == 0:
        return np.zeros_like(fg)
    keep_idx = int(np.argmax(sizes)) + 1
    return lbl == keep_idx


def feathering(mask: np.ndarray) -> np.ndarray:
    """简单抗锯齿：高斯模糊 + 阈值。"""
    soft = ndimage.gaussian_filter(mask.astype(np.float32), sigma=0.7)
    return (soft > 0.5).astype(np.uint8)


# ===== 流水线 =====

def _save_to_tmp(data: bytes, td: str) -> Path:
    """把 MP4 字节落临时文件，让 ffmpeg 直接读。"""
    p = Path(td) / "input.mp4"
    p.write_bytes(data)
    return p


def extract_frames(video: Path, out_dir: Path, fps: int) -> list[Path]:
    """ffmpeg 抽帧 + mpdecimate 去重复帧 + 重采样到目标 fps。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%05d.png"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video),
        "-vf", f"mpdecimate,fps={fps}",
        str(pattern),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return sorted(out_dir.glob("frame_*.png"))


@dataclass
class SheetResult:
    frame_count: int
    fps_hint: float
    width: int
    height: int
    cols: int
    rows: int


class SheetOversizeError(Exception):
    """采样帧数/时长超出上限。"""


def process_video(
    data: bytes,
    out_dir: Path,
    *,
    fps: int = 12,
    tol: float = 35.0,
    min_area: int = 200,
    max_duration_sec: int = 60,
    max_frames: int = 600,
) -> SheetResult:
    """写 out_dir 下的全部产物。data 为 MP4 字节。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        src_mp4 = _save_to_tmp(data, td)
        tmp_frames_dir = Path(td) / "frames_tmp"
        frames = extract_frames(src_mp4, tmp_frames_dir, fps=fps)
        if not frames:
            raise ValueError("no frames extracted")
        if len(frames) > max_frames:
            raise SheetOversizeError(f"采样帧数 {len(frames)} 超过 {max_frames}")

        # 每帧独立处理
        rendered: list[tuple[str, np.ndarray, tuple[int, int, int, int] | None, list[int]]] = []
        for f in frames:
            rgba = np.array(Image.open(f).convert("RGBA"))
            bg = estimate_bg_from_border(rgba)
            is_bg = color_distance_mask(rgba, bg, tol)
            flood_bg = flood_fill_background(is_bg)
            fg = ndimage.binary_closing(~flood_bg, iterations=2)
            subject = keep_largest_island(fg, min_area)
            alpha = feathering(subject) * 255
            out_rgba = np.dstack([rgba[..., :3], alpha])
            ys, xs = np.where(subject)
            bbox = (int(ys.min()), int(xs.min()), int(ys.max()) + 1, int(xs.max()) + 1) if len(ys) else None
            rendered.append((f.name, out_rgba, bbox, bg.tolist()))

        valid = [r for r in rendered if r[2] is not None]
        if not valid:
            raise ValueError("全片未识别到主体（检查 tol / min-area）")

        uy0 = min(r[2][0] for r in valid)
        ux0 = min(r[2][1] for r in valid)
        uy1 = max(r[2][2] for r in valid)
        ux1 = max(r[2][3] for r in valid)
        canvas_h, canvas_w = uy1 - uy0, ux1 - ux0

        n = len(rendered)
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        sheet_w = cols * canvas_w
        sheet_h = rows * canvas_h
        sheet_img = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

        meta = {
            "fps_hint": fps,
            "params": {"tol": tol, "min_area": min_area},
            "canvas": {"x": ux0, "y": uy0, "w": canvas_w, "h": canvas_h},
            "grid": {"cols": cols, "rows": rows},
            "canvas_size": {"w": sheet_w, "h": sheet_h},
            "frames": [],
            "per_frame_bg": [r[3] for r in rendered],
        }

        for i, (name, rgba, bbox, _) in enumerate(rendered):
            r, c = divmod(i, cols)
            cropped = rgba[uy0:uy1, ux0:ux1] if bbox else np.zeros((canvas_h, canvas_w, 4), np.uint8)
            sheet_img.paste(Image.fromarray(cropped, "RGBA"), (c * canvas_w, r * canvas_h))
            Image.fromarray(rgba, "RGBA").save(frames_dir / name)
            meta["frames"].append({
                "id": f"frame_{i:03d}",
                "filename": f"frames/{name}",
                "col": c, "row": r,
                "bbox": bbox,
            })
        sheet_img.save(out_dir / "sheet.png")

        # 预览 APNG + Animated WebP（小尺寸 + 8fps）
        PREVIEW_W, PREVIEW_FPS = 240, 8
        imgs_small: list[Image.Image] = []
        for _, rgba_full, _, _ in rendered:
            h, w = rgba_full.shape[:2]
            tw = max(1, int(w * PREVIEW_W / h))
            im = Image.fromarray(rgba_full, "RGBA").resize((tw, PREVIEW_W), Image.NEAREST)
            imgs_small.append(im)
        if imgs_small:
            frame_ms = int(1000 / PREVIEW_FPS)
            imgs_small[0].save(
                out_dir / "preview.apng",
                format="PNG",
                save_all=True,
                append_images=imgs_small[1:],
                duration=frame_ms,
                loop=0,
                optimize=True,
            )
            imgs_small[0].save(
                out_dir / "preview.webp",
                format="WEBP",
                save_all=True,
                append_images=imgs_small[1:],
                duration=frame_ms,
                loop=0,
                lossless=True,
            )

        (out_dir / "frames.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2)
        )

    return SheetResult(
        frame_count=n,
        fps_hint=fps,
        width=canvas_w,
        height=canvas_h,
        cols=cols,
        rows=rows,
    )