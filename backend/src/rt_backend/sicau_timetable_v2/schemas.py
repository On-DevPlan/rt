"""Pydantic schemas for SICAU v2 endpoints."""
from datetime import datetime

from pydantic import BaseModel, Field


class TimetableRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="学号")
    password: str = Field(..., min_length=1, description="密码")
    semester: str | None = Field(None, description="学期，如 2025-2026-2")


class TimetableResponse(BaseModel):
    user_id: str
    semester: str
    dsl: str
    course_count: int
    generated_at: datetime