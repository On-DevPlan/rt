"""前景掩膜策略：色距阈值 + 边界泛洪 + 仅最大连通域。

三步链路：
  1. color_distance_mask：与 bg 色距 < tol 视为"背景候选"
  2. flood_fill_background：与图像边缘连通的候选才算真背景（防误伤主体内部同色）
  3. keep_largest_island：仅保留最大连通域（自然吃掉水印/杂色小岛）

单独可测；多个 sheet 方案复用。
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


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