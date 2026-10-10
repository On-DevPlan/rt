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


class VideoPage(BaseModel):
    page: int | None = None
    part: str = ""
    cid: int | None = None


class VideoInfoResponse(BaseModel):
    bvid: str
    aid: int | None = None
    cid: int | None = None
    title: str
    desc: str
    pic: str = ""
    owner_mid: int | None = None
    owner_name: str
    pubdate: int | None = None
    duration: int | None = None
    pages: list[VideoPage] = []
    view: int | None = None
    danmaku: int | None = None
    reply: int | None = None
    favorite: int | None = None
    coin: int | None = None
    share: int | None = None
    like: int | None = None


# --- 播放直链 / 清晰度 ----------------------------------------------------------


class PlayUrlRequest(BaseModel):
    aid: int = Field(description="视频 aid（配合分P cid；aid/cid 可从 GET /video/{id} 的响应拿）")
    cid: int = Field(description="分P cid")
    qn: int = Field(
        default=80,
        description="清晰度：120=4K 116=1080P60 112=1080P+ 80=1080P 74=720P60 64=720P 32=480P 16=360P（高的多需 SESSDATA；4K 还需 fnval 含 128 + fourk）",
    )
    fnval: int = Field(
        default=1,
        description="格式位掩码：1=音视频合一 mp4（返回 durl 直链）；16=仅 DASH；4048=全部 DASH（无 durl，dash=true）",
    )
    fourk: bool = Field(default=True, description="允许 4K")
    sessdata: str | None = Field(default=None, description="高清晰度需要 SESSDATA")


class DurlItem(BaseModel):
    url: str | None = None
    backup_url: str | list[str] | None = None
    size: int | None = None


class PlayUrlResponse(BaseModel):
    quality: int | None = None
    format: str | None = None
    accept_quality: list[int] = []
    accept_description: list[str] = []
    timelength: int | None = Field(default=None, description="片长（毫秒）")
    support_formats: list[dict[str, Any]] = Field(
        default=[],
        description="各清晰度明细（上游透传）：quality/format/new_description/display_desc/codecs[]",
    )
    durl: list[DurlItem] = []
    dash: bool = False


# --- 弹幕 -------------------------------------------------------------------


class DanmakuItem(BaseModel):
    time: float | None = None
    mode: int | None = None
    text: str = ""


class DanmakuResponse(BaseModel):
    cid: int
    total: int
    items: list[DanmakuItem]


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
    pinned: bool = False
    replies: list["CommentItem"] = []


class CommentsRequest(BaseModel):
    oid: str = Field(description="评论区 id：type=1 时为 aid（纯数字），type=17 时为动态 id")
    type: int = Field(default=1, ge=1, le=17, description="评论区类型：1=视频 17=动态")
    ps: int = Field(default=20, ge=1, le=30, description="每页条数")
    pages: int = Field(default=1, ge=1, le=20, description="一级评论抓取页数")
    include_replies: bool = Field(default=True, description="是否抓取楼中楼回复")
    mode: int = Field(
        default=3,
        ge=0,
        le=3,
        description="排序（透传上游）：2=按时间 3=按热度，0/1 为混合态",
    )
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
    pub_time: str = Field(default="", description="发布时间展示串（如 27分钟前）")
    pub_ts: int | None = Field(default=None, description="发布 unix 秒")
    play: int | None = Field(default=None, description="播放数（视频类动态；与 user-videos 的 play 对齐）")


class UserSpaceResponse(BaseModel):
    mid: str
    pages_fetched: int
    total: int
    items: list[UserSpaceItem]


# --- UP 主全量投稿 -------------------------------------------------------------


class UserVideosRequest(BaseModel):
    mid: str = Field(description="UP 主 uid")
    pn: int = Field(default=1, ge=1, le=100, description="页码")
    ps: int = Field(default=30, ge=1, le=50, description="每页条数")
    order: str = Field(
        default="pubdate", description="排序：pubdate=最近发布 click=最多播放 stow=最多收藏"
    )
    sessdata: str | None = None


class UserVideoItem(BaseModel):
    aid: int | None = None
    bvid: str
    title: str
    created: int | None = None
    play: int | None = None
    video_review: int | None = None
    length: str = ""


class UserVideosResponse(BaseModel):
    mid: str
    count: int | None = None
    total: int
    items: list[UserVideoItem]
