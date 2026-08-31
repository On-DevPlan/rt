"""岛屿切割核心算法：连通域切分 → 带透明通道的像素块 PNG。

参考实现：a_dart/prj/fr/.tool/chess-piece-extract/scripts/
  - extract_islands.py v5（透明底 RGBA：alpha>0 前景 + 闭运算 + mask 恢复 AA 边缘）
  - extract.py v9（白底泛洪 + 小连通域归属主岛）

支持两类源图，mode=auto 时自动判定：
  - alpha 模式：存在明显透明像素（alpha<10）→ 前景 = alpha > alpha_threshold
  - white 模式：否则按白底处理 → 背景 = 与边缘连通的 >= bg_threshold 白色（泛洪）

输出：每岛一张 RGBA PNG（bbox+padding 裁剪，邻岛像素 alpha=0），
外加一张整图透明底 PNG 便于核对。
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy import ndimage

ALPHA_MODE = "alpha"
WHITE_MODE = "white"
FULL_NAME = "00_full_transparent.png"


@dataclass
class CutParams:
    mode: str = "auto"
    bg_threshold: int = 235
    alpha_threshold: int = 0
    closing_iters: int = 2
    min_area: int = 1000
    padding: int = 20
    small_min_area: int = 12
    connectivity: int = 8


@dataclass
class CutResult:
    mode: str
    width: int
    height: int
    pieces: list[dict]  # {id, filename, x, y, width, height, area, image: PIL.Image}
    full_image: Image.Image


def load_rgba(data: bytes) -> Image.Image:
    """从上传字节加载 RGBA 图（透明白底 JPEG 等一律转 RGBA）。"""
    return Image.open(io.BytesIO(data)).convert("RGBA")


def detect_mode(rgba: np.ndarray) -> str:
    """存在明显透明像素 → alpha 模式；否则按白底处理。"""
    return ALPHA_MODE if bool((rgba[..., 3] < 10).any()) else WHITE_MODE


def flood_fill_background(is_white: np.ndarray) -> np.ndarray:
    """与图像边缘连通的白色 = 背景（泛洪，不吃被前景环绕的内部亮区）。"""
    lbl, _ = ndimage.label(is_white)
    border_labels = set(lbl[0]) | set(lbl[-1]) | set(lbl[:, 0]) | set(lbl[:, -1])
    border_labels.discard(0)
    return np.isin(lbl, list(border_labels)) if border_labels else np.zeros_like(is_white)


def _structure(connectivity: int) -> np.ndarray | None:
    if connectivity >= 8:
        return np.ones((3, 3), dtype=bool)
    return None  # scipy 默认十字 = 4 连通


def _center(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    y0, y1, x0, x1 = bbox
    return (x0 + x1) // 2, (y0 + y1) // 2  # (cx, cy)


def _label_islands(
    fg: np.ndarray, params: CutParams, structure: np.ndarray | None
) -> list[dict]:
    """label 前景 → 主岛（>=min_area）+ 小连通域归属（细节/花纹归入包含它的主岛）。"""
    lbl, n = ndimage.label(fg, structure=structure)
    islands: list[dict] = []
    smalls: list[dict] = []
    for idx in range(1, n + 1):
        m = lbl == idx
        area = int(m.sum())
        ys, xs = np.where(m)
        bbox = (int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1)
        item = {"mask": m, "bbox": bbox, "area": area, "center": _center(bbox)}
        if area < params.min_area:
            if params.small_min_area and area >= params.small_min_area:
                smalls.append(item)
            continue
        islands.append(item)

    pad = params.padding
    for s in smalls:
        cy, cx = s["center"][1], s["center"][0]
        sy0, sy1, sx0, sx1 = s["bbox"]
        holders = [
            isl
            for isl in islands
            if isl["bbox"][0] - pad <= cy < isl["bbox"][1] + pad
            and isl["bbox"][2] - pad <= cx < isl["bbox"][3] + pad
        ]
        if not holders:
            continue
        tgt = min(holders, key=lambda isl: (isl["center"][0] - cx) ** 2 + (isl["center"][1] - cy) ** 2)
        tgt["mask"] |= s["mask"]
        by0, by1, bx0, bx1 = tgt["bbox"]
        tgt["bbox"] = (min(by0, sy0), max(by1, sy1), min(bx0, sx0), max(bx1, sx1))
        tgt["center"] = _center(tgt["bbox"])
        tgt["area"] += s["area"]
    return islands


def _order_reading(islands: list[dict]) -> list[dict]:
    """阅读顺序：按 cy 聚成视觉行（容差 = 岛高 0.6，下限 24px），行内按 cx 升序。"""
    remaining = sorted(islands, key=lambda i: i["center"][1])
    rows: list[list[dict]] = []
    for it in remaining:
        h = it["bbox"][1] - it["bbox"][0]
        tol = max(24, int(h * 0.6))
        for row in rows:
            ref_cy = sum(i["center"][1] for i in row) / len(row)
            if abs(it["center"][1] - ref_cy) <= tol:
                row.append(it)
                break
        else:
            rows.append([it])
    rows.sort(key=lambda r: sum(i["center"][1] for i in r) / len(r))
    ordered: list[dict] = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda i: i["center"][0]))
    return ordered


def _crop_piece(
    rgba: np.ndarray, isl: dict, pad: int, mode: str
) -> tuple[Image.Image, int, int]:
    """bbox+pad 裁剪，写透明 alpha；返回 (PNG 图, 裁剪原点 x, y)。

    alpha 模式：保留 mask 内（外扩一圈）的原始 alpha，AA 半透明边缘不失真；
    white 模式：岛 mask 内 alpha=255，其余 0。
    """
    y0, y1, x0, x1 = isl["bbox"]
    h, w = rgba.shape[:2]
    py0, py1 = max(0, y0 - pad), min(h, y1 + pad)
    px0, px1 = max(0, x0 - pad), min(w, x1 + pad)
    crop = rgba[py0:py1, px0:px1].copy()
    if mode == ALPHA_MODE:
        m = isl["mask"][py0:py1, px0:px1]
        keep = (crop[..., 3] > 0) & ndimage.binary_dilation(m, iterations=1)
        crop[..., 3] = np.where(keep, crop[..., 3], 0)
    else:
        crop[..., 3] = np.where(isl["mask"][py0:py1, px0:px1], 255, 0)
    return Image.fromarray(crop, "RGBA"), int(px0), int(py0)


def run_cut(rgba: np.ndarray, params: CutParams) -> CutResult:
    """执行切割：前景判定 → 闭运算 → label → 岛屿 → 逐岛透明 PNG。"""
    h, w = rgba.shape[:2]
    mode = detect_mode(rgba) if params.mode == "auto" else params.mode
    alpha = rgba[..., 3]

    if mode == ALPHA_MODE:
        fg = alpha > params.alpha_threshold
    else:
        is_white = np.all(rgba[..., :3] >= params.bg_threshold, axis=2)
        fg = ~flood_fill_background(is_white)

    if params.closing_iters > 0:
        fg = ndimage.binary_closing(fg, iterations=params.closing_iters)

    structure = _structure(params.connectivity)
    islands = _order_reading(_label_islands(fg, params, structure))

    pieces: list[dict] = []
    for i, isl in enumerate(islands):
        image, px, py = _crop_piece(rgba, isl, params.padding, mode)
        pieces.append(
            {
                "id": f"island_{i:02d}",
                "filename": f"island_{i:02d}.png",
                "x": px,
                "y": py,
                "width": image.width,
                "height": image.height,
                "area": isl["area"],
                "image": image,
            }
        )

    # 整图透明底（核对用）：alpha 模式直接用原图，white 模式把泛洪背景置透明
    full = rgba.copy()
    if mode == WHITE_MODE:
        full[..., 3] = np.where(fg, 255, 0)
    full_image = Image.fromarray(full, "RGBA")

    return CutResult(mode=mode, width=int(w), height=int(h), pieces=pieces, full_image=full_image)
