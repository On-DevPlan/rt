"""Pydantic schemas for the anime season endpoint.

Contract: D:\\code\\a_dart\\prj\\fr\\.claude\\skills\\timetable-module\\references\\anime-backend-api-spec.md
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class AnimeItem(BaseModel):
    id: str = Field(..., description="稳定唯一 id，<source>:<key>")
    title: str = Field(..., min_length=1, description="中文优先标题")
    titleNative: Optional[str] = Field(None, description="日文原名")
    startDateIso: Optional[str] = Field(None, description="开播日期 YYYY-MM-DD (JST)")
    weekday: Optional[int] = Field(None, ge=1, le=7, description="1=周一..7=周日，JST 自然日")
    time: Optional[str] = Field(None, description="HH:mm JST 自然日 24h 制")
    episodes: Optional[int] = Field(None, gt=0)
    durationMin: Optional[int] = Field(None, gt=0)
    sourceUrl: Optional[str] = Field(None)
    matchedSources: List[str] = Field(default_factory=list)


class SeasonResponse(BaseModel):
    season: str
    year: int
    generatedAt: str
    items: List[AnimeItem]
