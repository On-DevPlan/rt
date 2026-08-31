"""Pydantic schemas for /api/island-cut/video-sheet/* (MP4 → sprite sheet + 元数据)."""
from pydantic import BaseModel, Field


class SheetParams(BaseModel):
    fps: int = Field(12, ge=1, le=30)
    tol: float = Field(35.0, ge=1, le=255, description="色距阈值（背景判定；越大越激进）")
    min_area: int = Field(200, ge=1, description="最小岛屿面积（噪声过滤）")
    max_duration_sec: int = Field(60, ge=1, le=600)
    max_frames: int = Field(600, ge=1, le=3000)
    max_output_bytes: int | None = Field(None, ge=1024, le=500_000_000,
                                       description="输出产物总体积上限（字节）；超限自动二分 fps 重抽帧")


class SheetResponse(BaseModel):
    job_id: str
    frame_count: int
    fps_hint: float
    final_fps: float = Field(..., description="压缩迭代后的最终 fps（可能低于 fps_hint）")
    width: int
    height: int
    cols: int
    rows: int
    elapsed_ms: int
    output_size_bytes: int = Field(..., description="最终产物总字节数")
    compression_attempts: int = 1
    sheet_url: str
    frames_zip_url: str
    frames_json_url: str
    preview_apng_url: str
    preview_webp_url: str