"""Bilibili crawler HTTP endpoints（前缀 /api/bilibili-crawler）。"""
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..core.http import HttpClientHolder
from .schemas import (
    CommentsRequest,
    CommentsResponse,
    IdConvertResponse,
    UserSpaceRequest,
    UserSpaceResponse,
    VideoInfoResponse,
    WbiSignRequest,
    WbiSignResponse,
)
from .service import (
    AuthError,
    BilibiliCrawlerError,
    UpstreamError,
    av2bv,
    bv2av,
    fetch_comments,
    fetch_user_space,
    fetch_video_info,
    sign_params,
)


def build_router(http_provider: Callable[[], HttpClientHolder]) -> APIRouter:
    router = APIRouter(prefix="/api/bilibili-crawler", tags=["bilibili-crawler"])

    @router.post("/wbi/sign", response_model=WbiSignResponse)
    async def wbi_sign(
        req: WbiSignRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """对任意参数做 B 站 WBI 签名（实时取 nav 接口的 img/sub key）。"""
        try:
            signed = await sign_params(http.client, dict(req.params))
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        wts = int(signed["wts"])
        return WbiSignResponse(
            w_rid=signed["w_rid"],
            wts=wts,
            signed_params=signed,
            query="&".join(f"{k}={v}" for k, v in signed.items()),
        )

    @router.get("/convert", response_model=IdConvertResponse)
    async def convert_id(aid: int | None = None, bvid: str | None = None):
        """av<->bv 互转（纯计算，不访问网络）；两个参数二选一。"""
        if (aid is None) == (bvid is None):
            raise HTTPException(status_code=422, detail="aid 与 bvid 恰好提供一个")
        try:
            if aid is not None:
                return IdConvertResponse(aid=aid, bvid=av2bv(aid))
            return IdConvertResponse(aid=bv2av(bvid), bvid=bvid)
        except (ValueError, IndexError) as e:
            raise HTTPException(status_code=422, detail=f"非法 id：{e}")

    @router.get("/video/{bvid}", response_model=VideoInfoResponse)
    async def video_info(
        bvid: str,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """抓取视频元信息（标题/UP 主/各维度统计）。"""
        try:
            info = await fetch_video_info(http.client, bvid)
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return VideoInfoResponse(**info)

    @router.post("/comments", response_model=CommentsResponse)
    async def comments(
        req: CommentsRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """两级评论爬取：一级评论分页 + 楼中楼展开，字段与原脚本对齐。"""
        try:
            data = await fetch_comments(
                http.client,
                oid=req.oid,
                type_=req.type,
                ps=req.ps,
                pages=req.pages,
                include_replies=req.include_replies,
                sessdata=req.sessdata,
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return CommentsResponse(**data)

    @router.post("/user-space", response_model=UserSpaceResponse)
    async def user_space(
        req: UserSpaceRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """UP 主动态列表：抽取每条的 comment_id_str/comment_type（可用于后续爬评论）。"""
        try:
            data = await fetch_user_space(
                http.client, mid=req.mid, max_pages=req.max_pages, sessdata=req.sessdata
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return UserSpaceResponse(**data)

    return router
