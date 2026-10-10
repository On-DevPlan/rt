"""Pydantic schemas for the bilibili_tools module."""
from pydantic import BaseModel, Field


# --- 收藏夹枚举 ---------------------------------------------------------------


class FavoriteItem(BaseModel):
    aid: str
    title: str
    pic: str
    state: int = 0


class FavoritesResponse(BaseModel):
    mid: str
    fid: str
    total: int
    items: list[FavoriteItem]


# --- 批量添加收藏 ---------------------------------------------------------------


class AddFavoriteRequest(BaseModel):
    sessdata: str = Field(description="SESSDATA cookie 值")
    bili_jct: str = Field(description="bili_jct cookie 值（csrf）")
    fid: str = Field(description="目标收藏夹 id")
    aids: list[str] = Field(min_length=1, max_length=100, description="要收藏的视频 av 号列表")


class AddFavoriteResult(BaseModel):
    aid: str
    code: str | None = None
    ok: bool
    pattern: int
    message: str


class AddFavoriteResponse(BaseModel):
    fid: str
    requested: int
    ok_count: int
    results: list[AddFavoriteResult]


# --- 音频区 -------------------------------------------------------------------


class SongItem(BaseModel):
    sid: str
    title: str
    author: str
    lyric: str = ""
    cover: str = ""


class SongInfoResponse(BaseModel):
    sid: str
    title: str
    author: str
    lyric: str
    cover: str
    quality: int
    cdns: list[str]


class MenuSongsResponse(BaseModel):
    menu_sid: str
    total: int
    items: list[SongItem]


class UserSongsResponse(BaseModel):
    uid: str
    total: int
    items: list[SongItem]
