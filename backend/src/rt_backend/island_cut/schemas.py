"""Pydantic schemas for /api/island-cut."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CutParams(BaseModel):
    """切割参数（对应参考实现 extract_islands v5 / extract v9 的 CLI 旗标）。"""

    mode: Literal["auto", "alpha", "white"] = "auto"
    bg_threshold: int = Field(235, ge=0, le=255, description="white 模式背景白色阈值")
    alpha_threshold: int = Field(0, ge=0, le=255, description="alpha 模式前景阈值")
    closing_iters: int = Field(2, ge=0, le=10, description="形态学闭运算迭代次数，0 关闭")
    min_area: int = Field(1000, ge=1, description="最小岛屿面积（低于视为噪点丢弃）")
    padding: int = Field(20, ge=0, le=200, description="每岛裁剪留白像素")
    small_min_area: int = Field(12, ge=0, description="小连通域归属主岛的最低面积，0 关闭归属")
    connectivity: Literal[4, 8] = Field(8, description="连通域判定 4/8 邻域")


class PieceInfo(BaseModel):
    id: str
    filename: str
    x: int
    y: int
    width: int
    height: int
    area: int


class CutResponse(BaseModel):
    job_id: str
    mode: str
    width: int
    height: int
    elapsed_ms: int
    pieces: list[PieceInfo]
    piece_count: int
    zip_url: str
    full_url: str
