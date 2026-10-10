"""Pydantic schemas for the bilibili_crawler module."""
from typing import Any

from pydantic import BaseModel, Field


# --- wbi 签名 ---------------------------------------------------------------


class WbiSignRequest(BaseModel):
    params: dict[str, Any] = Field(description="待签名的业务参数（将附加 wts/w_rid）")


class WbiSignResponse(BaseModel):
    w_rid: str
    wts: int
    signed_params: dict[str, Any]
    query: str


# --- av/bv 互转 -------------------------------------------------------------


class IdConvertResponse(BaseModel):
    aid: int | None = None
    bvid: str | None = None


# --- 视频信息 ----------------------------------------------------------------


class VideoInfoResponse(BaseModel):
    bvid: str
    aid: int | None = None
    title: str
    desc: str
    owner_mid: int | None = None
    owner_name: str
    pubdate: int | None = None
    duration: int | None = None
    view: int | None = None
    danmaku: int | None = None
    reply: int | None = None
    favorite: int | None = None
    coin: int | None = None
    share: int | None = None
    like: int | None = None


# --- 评论 -------------------------------------------------------------------


class CommentItem(BaseModel):
    rpid: str
    name: str
    sex: str
    time: str
    like: int
    message: str
    location: str
    level: int
    mid: str
    reply_count: int
    replies: list["CommentItem"] = []


class CommentsRequest(BaseModel):
    oid: str = Field(description="评论区 id：type=1 时为 aid（纯数字），type=17 时为动态 id")
    type: int = Field(default=1, ge=1, le=17, description="评论区类型：1=视频 17=动态")
    ps: int = Field(default=20, ge=1, le=30, description="每页条数")
    pages: int = Field(default=1, ge=1, le=20, description="一级评论抓取页数")
    include_replies: bool = Field(default=True, description="是否抓取楼中楼回复")
    sessdata: str | None = Field(default=None, description="可选 SESSDATA 登录态，未登录也能爬部分评论")


class CommentsResponse(BaseModel):
    oid: str
    type: int
    pages_fetched: int
    total: int
    is_end: bool | None = None
    items: list[CommentItem]


# --- 用户空间 ----------------------------------------------------------------


class UserSpaceRequest(BaseModel):
    mid: str = Field(description="UP 主 uid")
    max_pages: int = Field(default=3, ge=1, le=20, description="feed 翻页上限")
    sessdata: str | None = None


class UserSpaceItem(BaseModel):
    comment_id_str: str
    comment_type: int | None = None
    dyn_type: int | None = None
    title: str = ""


class UserSpaceResponse(BaseModel):
    mid: str
    pages_fetched: int
    total: int
    items: list[UserSpaceItem]
