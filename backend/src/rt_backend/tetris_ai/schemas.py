"""Pydantic schemas for the Tetris AI endpoints."""
from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

PieceName = Literal["I", "O", "T", "S", "Z", "J", "L", "i", "o", "t", "s", "z", "j", "l"]
BoardRow = Union[str, List[Union[int, str, bool, None]]]


class Weights(BaseModel):
    """Optional override of the six Dellacherie weights."""

    landing_height: float = -4.500158825082766
    eroded_piece_cells: float = 3.4181268101392694
    row_transitions: float = -3.2178882868487753
    column_transitions: float = -9.348695305445199
    holes: float = -7.899265427351652
    wells: float = -3.3855972247263626


class NextMoveRequest(BaseModel):
    """Current game state uploaded by the client.

    ``board`` is top-row-first. Each row may be a string (any character other
    than ``.``/``0``/space counts as occupied) or an array of ints/bools. The
    board must NOT include the currently falling piece.
    """

    board: List[BoardRow] = Field(
        ...,
        min_length=1,
        max_length=64,
        description="棋盘矩阵，自上而下。每行可为字符串（'.'/'0'/空格为空）或数组",
        examples=[["..........", "..........", "###....###", "####..####"]],
    )
    piece: PieceName = Field(..., description="当前需要落子的方块：I/O/T/S/Z/J/L")
    next_piece: Optional[PieceName] = Field(
        None,
        description="下一个方块，给出则开启 1 步前瞻，显著提升棋力",
    )
    current_x: Optional[int] = Field(
        None,
        ge=0,
        description="当前方块包围盒最左列；省略则按出生位置（居中）计算按键序列",
    )
    current_rotation: int = Field(
        0,
        ge=0,
        le=3,
        description="当前方块已有的旋转态（0-3），用于计算需要几次 rotate",
    )
    weights: Optional[Weights] = Field(
        None, description="可选，覆盖默认的 Dellacherie 权重"
    )


class MetricsOut(BaseModel):
    """The six features of the board after the recommended placement."""

    landing_height: float
    eroded_piece_cells: int
    row_transitions: int
    column_transitions: int
    holes: int
    wells: int


class NextMoveResponse(BaseModel):
    """Where to put the piece, and which keys to press to get it there."""

    rotation: int = Field(..., description="目标旋转态（顺时针 rotate 次数达成）")
    target_x: int = Field(..., description="目标位置：方块包围盒最左列")
    final_y: int = Field(..., description="落地后方块包围盒最上行")
    moves: List[str] = Field(
        ...,
        description="按键序列，依次执行：rotate / left / right / hard_drop",
        examples=[["rotate", "left", "left", "hard_drop"]],
    )
    score: float = Field(..., description="该落点的评估分（越大越好，通常为负）")
    cleared_lines: int = Field(..., description="该落点可消除的行数")
    lookahead: bool = Field(..., description="是否使用了 next_piece 前瞻")
    metrics: MetricsOut
    elapsed_ms: float = Field(..., description="后端搜索耗时（毫秒）")
