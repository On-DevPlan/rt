"""Pydantic schemas for the Bilibili history endpoints."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class HistoryRequest(BaseModel):
    """Request body for fetching recent watch history.

    `sessdata` is the user's B 站 login cookie (SESSDATA=xxx). Other cookies
    (bili_jct, buvid3, etc.) are not required for the history endpoint but may
    be supplied via `extra_cookies` for completeness.
    """

    sessdata: str = Field(..., min_length=1, description="B 站 SESSDATA cookie 值")
    extra_cookies: Optional[str] = Field(
        None,
        description="可选，额外的 cookie 字符串，例如 'bili_jct=xxx; buvid3=xxx'",
    )
    days: int = Field(
        7,
        ge=1,
        le=90,
        description="获取最近多少天的观看记录（1-90）",
    )
    business: str = Field(
        "all",
        description="业务类型筛选：all / archive / live / article",
    )
    max_pages: int = Field(
        10,
        ge=1,
        le=30,
        description="最多翻多少页（B 站接口单页最多 30 条），防止无限翻页",
    )


class HistoryItem(BaseModel):
    """A single history record (the B 站 `list[i]` object, normalized)."""

    title: str
    cover: Optional[str] = None
    bvid: Optional[str] = None
    aid: Optional[int] = None
    cid: Optional[int] = None
    author_name: Optional[str] = None
    author_mid: Optional[int] = None
    view_at: int
    view_at_iso: datetime
    progress: int = 0
    duration: int = 0
    business: str = ""
    tag_name: Optional[str] = None
    show_title: Optional[str] = None
    kid: Optional[int] = None
    dt: Optional[int] = None
    is_fav: int = 0


class HistoryResponse(BaseModel):
    """Aggregated history response."""

    sessdata_masked: str
    days: int
    business: str
    since_ts: int
    since_iso: datetime
    until_ts: int
    until_iso: datetime
    total: int
    page_count: int
    items: List[HistoryItem]
