"""MP4 → 透明 sprite sheet + 元数据（编排层，薄壳）。

只负责把 strategies/* 拼起来——具体算法（背景估计、前景、羽化、IO）
都在 strategies/ 子包各自的文件里，便于单独替换或测试。
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from .strategies import bg, feather, fg, io as strat_io


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
    """写 out_dir 下的全部产物（sheet.png / frames/ / frames.json / preview.*）。

    算法（参考 .tool/video-sheet/scripts/build_sheet.py）：
      bg.estimate_bg_from_border → fg.color_distance_mask → fg.flood_fill_background →
      binary_closing → fg.keep_largest_island → feather.feathering →
      全片 union bbox → 拼 sprite sheet + 预览
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        src_mp4 = strat_io._save_to_tmp(data, td)
        tmp_frames_dir = Path(td) / "frames_tmp"
        frames = strat_io.extract_frames(src_mp4, tmp_frames_dir, fps=fps)
        if not frames:
            raise ValueError("no frames extracted")
        if len(frames) > max_frames:
            raise SheetOversizeError(f"采样帧数 {len(frames)} 超过 {max_frames}")

        # 每帧独立处理
        rendered: list[tuple[str, np.ndarray, tuple[int, int, int, int] | None, list[int]]] = []
        for f in frames:
            rgba = np.array(Image.open(f).convert("RGBA"))
            bg_color = bg.estimate_bg_from_border(rgba)
            is_bg = fg.color_distance_mask(rgba, bg_color, tol)
            flood_bg = fg.flood_fill_background(is_bg)
            foreground = ndimage.binary_closing(~flood_bg, iterations=2)
            subject = fg.keep_largest_island(foreground, min_area)
            alpha = feather.feathering(subject) * 255
            out_rgba = np.dstack([rgba[..., :3], alpha])
            ys, xs = np.where(subject)
            bbox = (int(ys.min()), int(xs.min()), int(ys.max()) + 1, int(xs.max()) + 1) if len(ys) else None
            rendered.append((f.name, out_rgba, bbox, bg_color.tolist()))

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