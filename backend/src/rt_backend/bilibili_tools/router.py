"""Bilibili tools HTTP endpoints（前缀 /api/bilibili-tools）。"""
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.http import HttpClientHolder
from .schemas import (
    AddFavoriteRequest,
    AddFavoriteResponse,
    FavoritesResponse,
    MenuSongsResponse,
    SongInfoResponse,
    UserSongsResponse,
)
from .service import (
    AuthError,
    BilibiliToolsError,
    PrivateFolderError,
    UpstreamError,
    add_favorites,
    fetch_favorites,
    fetch_menu_songs,
    fetch_song_info,
    fetch_user_songs,
    parse_fav_link,
)


def _http_exc(e: BilibiliToolsError) -> HTTPException:
    if isinstance(e, AuthError):
        return HTTPException(status_code=401, detail=str(e))
    if isinstance(e, PrivateFolderError):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, UpstreamError):
        return HTTPException(status_code=502, detail=str(e))
    return HTTPException(status_code=500, detail=str(e))


def build_router(http_provider: Callable[[], HttpClientHolder]) -> APIRouter:
    router = APIRouter(prefix="/api/bilibili-tools", tags=["bilibili-tools"])

    @router.get("/favorites", response_model=FavoritesResponse)
    async def favorites(
        http: HttpClientHolder = Depends(http_provider),
        link: str | None = Query(default=None, description="收藏夹链接 space.bilibili.com/{mid}/favlist?fid={fid}"),
        mid: str | None = Query(default=None, description="UP 主 uid（与 fid 一起提供，优先用 link）"),
        fid: str | None = Query(default=None, description="收藏夹 id"),
        limit: int = Query(default=20, ge=1, le=200, description="抓取条数上限"),
    ):
        """枚举公开收藏夹的视频列表（aid/标题/封面/状态）。link 或 mid+fid 二选一。"""
        if link:
            try:
                mid, fid = parse_fav_link(link)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
        if not mid or not fid:
            raise HTTPException(status_code=422, detail="需要 link 或 (mid + fid)")
        try:
            data = await fetch_favorites(http.client, mid, fid, limit)
        except BilibiliToolsError as e:
            raise _http_exc(e)
        return FavoritesResponse(**data)

    @router.post("/favorites/add", response_model=AddFavoriteResponse)
    async def favorites_add(
        req: AddFavoriteRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """批量添加视频到收藏夹（需要 SESSDATA + bili_jct，即写操作）。"""
        try:
            data = await add_favorites(
                http.client,
                sessdata=req.sessdata,
                bili_jct=req.bili_jct,
                fid=req.fid,
                aids=req.aids,
            )
        except BilibiliToolsError as e:
            raise _http_exc(e)
        return AddFavoriteResponse(**data)

    # 注意：/audio/{sid} 是通配路由，必须注册在 /audio/playlist、/audio/user 之后，
    # 否则 /audio/user 会被当成 sid="user" 吃掉（FastAPI 按注册顺序匹配）。
    @router.get("/audio/playlist/{sid}", response_model=MenuSongsResponse)
    async def menu_songs(
        sid: str,
        http: HttpClientHolder = Depends(http_provider),
        max_pages: int = Query(default=3, ge=1, le=10),
    ):
        """歌单（am{id}）内全部歌曲列表。"""
        from .service import parse_menu_sid

        real_sid = parse_menu_sid(sid) or sid
        if not real_sid.isdigit():
            raise HTTPException(status_code=422, detail=f"非法歌单 id：{sid!r}")
        try:
            data = await fetch_menu_songs(http.client, real_sid, max_pages)
        except BilibiliToolsError as e:
            raise _http_exc(e)
        return MenuSongsResponse(**data)

    @router.get("/audio/user", response_model=UserSongsResponse)
    async def user_songs(
        http: HttpClientHolder = Depends(http_provider),
        uid: str | None = Query(default=None, description="数字 uid"),
        link: str | None = Query(default=None, description="完整 space 链接 space.bilibili.com/{uid}/audio"),
        order: int = Query(
            default=1, ge=1, le=3, description="排序：1=最新发布 2=最多播放 3=最多收藏"
        ),
        max_pages: int = Query(default=3, ge=1, le=10),
    ):
        """UP 主上传的歌曲列表。uid 或 link 二选一。"""
        from .service import parse_space_uid

        if link:
            real_uid = parse_space_uid(link)
        elif uid:
            # uid 可为纯数字或 space 链接
            real_uid = parse_space_uid(uid) or (uid if uid.isdigit() else "")
        else:
            real_uid = ""
        if not real_uid:
            raise HTTPException(status_code=422, detail="需要 uid（数字或 space 链接）或 link")
        try:
            data = await fetch_user_songs(http.client, real_uid, order, max_pages)
        except BilibiliToolsError as e:
            raise _http_exc(e)
        return UserSongsResponse(**data)

    @router.get("/audio/{sid}", response_model=SongInfoResponse)
    async def song_info(
        sid: str,
        http: HttpClientHolder = Depends(http_provider),
        quality: int = Query(
            default=2, ge=0, le=2, description="音质位率：0=128K 1=192K 2=320K（越大越高）"
        ),
    ):
        """音频区歌曲信息 + 播放 CDN 直链（支持传 au{id} 完整链接或纯数字 id）。"""
        from .service import parse_audio_sid

        real_sid = parse_audio_sid(sid) or sid
        if not real_sid.isdigit():
            raise HTTPException(status_code=422, detail=f"非法歌曲 id：{sid!r}")
        try:
            data = await fetch_song_info(http.client, real_sid, quality)
        except BilibiliToolsError as e:
            raise _http_exc(e)
        return SongInfoResponse(**data)

    return router
