"""背景色估计策略：边缘像素的颜色中位数（抗噪）。"""
from __future__ import annotations

import numpy as np


def estimate_bg_from_border(rgba: np.ndarray) -> np.ndarray:
    """四边像素的颜色中位数（uint8 RGB）。"""
    edges = np.concatenate([
        rgba[0], rgba[-1],
        rgba[:, 0], rgba[:, -1],
    ])[:, :3]
    return np.median(edges, axis=0).astype(np.uint8)