"""边缘羽化策略：高斯模糊 + 阈值抗锯齿。

像素画/赛璐璐素材无抗锯齿时本策略可绕过（use_feather=False 标志待加）。
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def feathering(mask: np.ndarray) -> np.ndarray:
    """简单抗锯齿：高斯模糊（σ=0.7） + 阈值 0.5 → uint8。"""
    soft = ndimage.gaussian_filter(mask.astype(np.float32), sigma=0.7)
    return (soft > 0.5).astype(np.uint8)