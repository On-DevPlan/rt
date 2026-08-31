"""MP4 → 透明 sprite sheet + 元数据（编排层，薄壳）。

只负责把 strategies/* 拼起来——具体算法（背景估计、前景、羽化、IO）
都在 strategies/ 子包各自的文件里，便于单独替换或测试。
"""
from __future__ import annotations

import json
import shutil
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
    final_fps: float = 0.0
    output_size_bytes: int = 0
    compression_attempts: int = 1


class SheetOversizeError(Exception):
    """采样帧数/时长超出上限。"""


def _dir_size_bytes(d: Path) -> int:
    """目录总字节数（递归）。"""
    total = 0
    for p in d.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def process_video(
    data: bytes,
    out_dir: Path,
    *,
    fps: int = 12,
    tol: float = 35.0,
    min_area: int = 200,
    max_duration_sec: int = 60,
    max_frames: int = 600,
    max_output_bytes: int | None = None,
    max_size: int = 512,
) -> SheetResult:
    """写 out_dir 下的全部产物（sheet.png / frames/ / frames.json / preview.*）。

    算法（参考 .tool/video-sheet/scripts/build_sheet.py）：
      bg.estimate_bg_from_border → fg.color_distance_mask → fg.flood_fill_background →
      binary_closing → fg.keep_largest_island → feather.feathering →
      全片 union bbox → 拼 sprite sheet + 预览

    若 max_output_bytes 设置：写盘后统计产物总字节数，超限则二分 fps 阶梯
    （fps/2, fps/4, fps/8, 1）重抽帧重做全流程，直到 ≤ 限值。
    仍超限抛 ValueError（router 转 413）。

    内存策略（300MB 预算 / 1.8GB 主机实测 OOM 教训）：
      渲染后 RGBA 立即落盘，内存只留 (name, bbox, bg) 元数据；
      sheet 拼装与预览逐帧从磁盘读回（canvas 经 max_size 缩放控制位图峰值）。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def _render_and_pack(trial_fps: int) -> SheetResult:
        """以指定 fps 抽帧并写盘全部产物。"""
        frames_dir = out_dir / "frames"
        # 清空旧帧，保证重试干净
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        frames_dir.mkdir(exist_ok=True)

        with tempfile.TemporaryDirectory() as td:
            src_mp4 = strat_io._save_to_tmp(data, td)
            tmp_frames_dir = Path(td) / "frames_tmp"
            frames = strat_io.extract_frames(src_mp4, tmp_frames_dir, fps=trial_fps)
            if not frames:
                raise ValueError("no frames extracted")
            if len(frames) > max_frames:
                raise SheetOversizeError(f"采样帧数 {len(frames)} 超过 {max_frames}")

            # 每帧独立处理：RGBA 处理完立即落盘（磁盘换内存），内存只留元数据
            rendered: list[tuple[str, tuple[int, int, int, int] | None, list[int]]] = []
            for f in frames:
                rgba = np.array(Image.open(f).convert("RGBA"))
                bg_color = bg.estimate_bg_from_border(rgba)
                is_bg = fg.color_distance_mask(rgba, bg_color, tol)
                flood_bg = fg.flood_fill_background(is_bg)
                foreground = ndimage.binary_closing(~flood_bg, iterations=2)
                subject = fg.keep_largest_island(foreground, min_area)
                alpha = feather.feathering(subject) * 255
                out_rgba = np.dstack([rgba[..., :3], alpha])
                del rgba
                ys, xs = np.where(subject)
                bbox = (int(ys.min()), int(xs.min()), int(ys.max()) + 1, int(xs.max()) + 1) if len(ys) else None
                Image.fromarray(out_rgba, "RGBA").save(frames_dir / f.name)
                rendered.append((f.name, bbox, bg_color.tolist()))
                del out_rgba

            valid = [r for r in rendered if r[1] is not None]
            if not valid:
                raise ValueError("全片未识别到主体（检查 tol / min-area）")

            uy0 = min(r[1][0] for r in valid)
            ux0 = min(r[1][1] for r in valid)
            uy1 = max(r[1][2] for r in valid)
            ux1 = max(r[1][3] for r in valid)
            canvas_h, canvas_w = uy1 - uy0, ux1 - ux0

            # canvas 过大时缩帧（内存/浏览器渲染双约束）：NEAREST 保像素锐利
            scale = 1.0
            if max_size and max(canvas_h, canvas_w) > max_size:
                scale = max_size / max(canvas_h, canvas_w)
                canvas_h = max(1, round(canvas_h * scale))
                canvas_w = max(1, round(canvas_w * scale))

            n = len(rendered)
            cols = int(np.ceil(np.sqrt(n)))
            rows = int(np.ceil(n / cols))
            sheet_w = cols * canvas_w
            sheet_h = rows * canvas_h
            sheet_img = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

            meta = {
                "fps_hint": trial_fps,
                "params": {"tol": tol, "min_area": min_area},
                "canvas": {"x": ux0, "y": uy0, "w": round((ux1 - ux0) * scale), "h": round((uy1 - uy0) * scale)},
                "canvas_src": {"x": ux0, "y": uy0, "w": ux1 - ux0, "h": uy1 - uy0},
                "scale": round(scale, 4),
                "grid": {"cols": cols, "rows": rows},
                "canvas_size": {"w": sheet_w, "h": sheet_h},
                "frames": [],
                "per_frame_bg": [r[2] for r in rendered],
            }

            for i, (name, bbox, _) in enumerate(rendered):
                r, c = divmod(i, cols)
                if bbox:
                    rgba = np.array(Image.open(frames_dir / name).convert("RGBA"))  # 按需读回
                    cropped = rgba[uy0:uy1, ux0:ux1]
                    del rgba
                    im = Image.fromarray(cropped, "RGBA")
                    if scale != 1.0:
                        im = im.resize((canvas_w, canvas_h), Image.NEAREST)
                    del cropped
                else:
                    im = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                sheet_img.paste(im, (c * canvas_w, r * canvas_h))
                del im
                meta["frames"].append({
                    "id": f"frame_{i:03d}",
                    "filename": f"frames/{name}",
                    "col": c, "row": r,
                    "bbox": bbox,
                    "t": round(i / trial_fps, 3),  # mpdecimate 后每帧=等间隔 1/fps 秒
                })
            sheet_img.save(out_dir / "sheet.png")

            # 预览 APNG + Animated WebP（小尺寸 + 8fps）
            PREVIEW_W, PREVIEW_FPS = 240, 8
            imgs_small: list[Image.Image] = []
            for name, _, _ in rendered:
                im = Image.open(frames_dir / name).convert("RGBA")  # 按需读回
                h, w = im.height, im.width
                tw = max(1, int(w * PREVIEW_W / h))
                imgs_small.append(im.resize((tw, PREVIEW_W), Image.NEAREST))
                im.close()
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
            fps_hint=trial_fps,
            width=canvas_w,
            height=canvas_h,
            cols=cols,
            rows=rows,
        )

    # 主流程：全量编码 → 超限则二分 fps 阶梯重做
    attempts = 1
    current_fps = fps
    result = _render_and_pack(current_fps)
    if max_output_bytes is not None:
        for trial in (fps / 2, fps / 4, fps / 8, 1):
            trial_fps = max(1, int(trial))
            if trial_fps >= current_fps:
                continue
            size = _dir_size_bytes(out_dir)
            if size <= max_output_bytes:
                break
            result = _render_and_pack(trial_fps)
            attempts += 1
            current_fps = trial_fps
        if _dir_size_bytes(out_dir) > max_output_bytes:
            raise ValueError(
                f"无法压缩到 {max_output_bytes} 字节（最小 fps=1 仍为 {_dir_size_bytes(out_dir)}）"
            )

    result.final_fps = current_fps
    result.output_size_bytes = _dir_size_bytes(out_dir)
    result.compression_attempts = attempts
    return result