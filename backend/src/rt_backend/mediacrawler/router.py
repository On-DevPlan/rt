"""MediaCrawler capability HTTP endpoints（前缀 /api/mediacrawler）。"""
import datetime
import json
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..bilibili_crawler.service import AuthError, UpstreamError
from ..core.archive import md_table, readme_index, zip_bytes
from ..core.http import HttpClientHolder
from .schemas import PlatformsResponse, SearchRequest, SearchResponse
from .service import (
    PLATFORMS,
    PlatformNotWrappedError,
    search_bilibili_videos,
    search_bilibili_videos_all,
)


class SearchArchiveRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=100, description="搜索关键词")
    order: str = Field(default="default", description="排序：default/click/pubdate/dm/stow")
    page_size: int = Field(default=20, ge=1, le=50, description="每页条数")
    sessdata: str | None = Field(default=None, description="可选 SESSDATA，降低风控概率")
    max_pages: int = Field(
        default=50, ge=1, le=100, description="贪心翻页安全上限（结果不足一页提前停）"
    )


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

    @router.post("/search/archive")
    async def search_archive(
        req: SearchArchiveRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """关键词搜索贪心翻页（翻到结果不足一页）→ zip 下载
        （README.md + results.json + results.md 表格）。"""
        try:
            data = await search_bilibili_videos_all(
                http.client,
                keyword=req.keyword,
                order=req.order,
                page_size=req.page_size,
                sessdata=req.sessdata,
                max_pages=req.max_pages,
            )
        except PlatformNotWrappedError as e:
            raise HTTPException(status_code=501, detail=str(e))
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        results_md = md_table(
            ["#", "title", "bvid", "author", "play"],
            [
                [i + 1, v["title"], v["bvid"], v.get("author", ""), v.get("play")]
                for i, v in enumerate(data["items"])
            ],
        )
        day = datetime.date.today().isoformat()
        # 关键词可能含中文：主 filename 保持 ASCII，UTF-8 名走 RFC 5987 filename*
        from urllib.parse import quote

        ascii_name = f"mediacrawler-search-{day}.zip"
        utf8_name = quote(f"mediacrawler-search-{req.keyword[:20]}-{day}.zip")
        payload = {
            "results.json": json.dumps(data, ensure_ascii=False, indent=2),
            "results.md": results_md,
        }
        payload["README.md"] = readme_index(
            f"Search Archive: {req.keyword}",
            [(k, v) for k, v in data.items() if k != "items"],
            [(n, n.rsplit(".", 1)[-1].upper() + " 数据") for n in payload],
        )
        return Response(
            content=zip_bytes(payload),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'
                ),
                "X-Archive-Items": str(data["total"]),
            },
        )

    return router
