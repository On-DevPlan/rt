"""Pydantic schemas for the mediacrawler module."""
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=100, description="搜索关键词")
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=20, ge=1, le=50)
    order: str = Field(default="default", description="排序：default/click/pubdate/dm/stow")
    pubtime_begin_s: int = Field(default=0, description="发布时间过滤起点（秒级时间戳）")
    pubtime_end_s: int = Field(default=0, description="发布时间过滤终点（秒级时间戳）")
    sessdata: str | None = Field(default=None, description="可选 SESSDATA，降低风控概率")


class SearchItem(BaseModel):
    aid: int | None = None
    bvid: str
    title: str
    author: str
    mid: int | None = None
    play: int | None = None
    danmaku: int | None = None
    favorites: int | None = None
    tag: str = ""
    pubdate: int | None = None
    description: str = ""
    pic: str = ""


class SearchResponse(BaseModel):
    keyword: str
    page: int
    num_results: int | None = None
    items: list[SearchItem]


class PlatformInfo(BaseModel):
    name: str
    login_required: bool
    playwright_required: bool
    wrapped: bool
    note: str


class PlatformsResponse(BaseModel):
    source: str = ".claude/repo/MediaCrawler"
    platforms: list[PlatformInfo]
