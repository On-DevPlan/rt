"""MediaCrawler capability HTTP endpoints（前缀 /api/mediacrawler）。"""
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..bilibili_crawler.service import AuthError, UpstreamError
from ..core.http import HttpClientHolder
from .schemas import PlatformsResponse, SearchRequest, SearchResponse
from .service import PLATFORMS, PlatformNotWrappedError, search_bilibili_videos


def build_router(http_provider: Callable[[], HttpClientHolder]) -> APIRouter:
    router = APIRouter(prefix="/api/mediacrawler", tags=["mediacrawler"])

    @router.get("/platforms", response_model=PlatformsResponse)
    async def platforms():
        """能力矩阵：MediaCrawler 支持的平台 × 本 API 是否包装（哪些需要浏览器登录）。"""
        return PlatformsResponse(platforms=PLATFORMS)

    @router.post("/search", response_model=SearchResponse)
    async def search(
        req: SearchRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """B 站关键词搜索视频（MediaCrawler bilibili client 核心的免登录 Web 化）。

        其他平台（xhs/douyin 等）需浏览器登录态，返回 501；见 GET /platforms。
        """
        if req.keyword and req.order not in ("default", "click", "pubdate", "dm", "stow"):
            raise HTTPException(status_code=422, detail=f"非法 order：{req.order!r}")
        try:
            data = await search_bilibili_videos(
                http.client,
                keyword=req.keyword,
                page=req.page,
                page_size=req.page_size,
                order=req.order,
                pubtime_begin_s=req.pubtime_begin_s,
                pubtime_end_s=req.pubtime_end_s,
                sessdata=req.sessdata,
            )
        except PlatformNotWrappedError as e:
            raise HTTPException(status_code=501, detail=str(e))
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return SearchResponse(**data)

    return router
