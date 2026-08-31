"""Pydantic schemas for /api/island-cut/video-apng/* (MP4 → Animated PNG)."""
from pydantic import BaseModel, Field


class VideoCutParams(BaseModel):
    fps: int = Field(12, ge=1, le=30)
    max_size: int = Field(360, ge=0, le=4096, description="0 = 不缩放")
    bg_tol: int = Field(50, ge=1, le=255)
    pad: int = Field(6, ge=0, le=50)
    max_duration_sec: int = Field(60, ge=1, le=600)
    max_frames: int = Field(600, ge=1, le=3000)
    max_output_bytes: int | None = Field(None, ge=1024, le=100_000_000,
                                       description="输出体积上限（字节）；超限自动二分 fps 重编")


class VideoCutResponse(BaseModel):
    job_id: str
    width: int
    height: int
    frame_count: int
    src_fps: float
    out_fps: float
    final_fps: float
    duration_sec: float
    elapsed_ms: int
    output_size_bytes: int
    compression_attempts: int = 1
    apng_url: str
    preview_url: str