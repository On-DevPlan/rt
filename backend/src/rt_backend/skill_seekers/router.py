"""Skill Seekers doc-crawler HTTP endpoints（前缀 /api/skill-seekers）。"""
import time
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response

from ..core.http import HttpClientHolder
from .schemas import ArchiveScrapeRequest, ScrapeRequest, ScrapeResponse
from .service import ScraperError, archive_filename, build_docs_archive, scrape_docs


def build_router(http_provider: Callable[[], HttpClientHolder]) -> APIRouter:
    router = APIRouter(prefix="/api/skill-seekers", tags=["skill-seekers"])

    @router.post("/scrape", response_model=ScrapeResponse)
    async def scrape(
        req: ScrapeRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """文档站爬取：sitemap 发现 + BFS 抓取正文，返回页面 JSON（Skill_Seekers
        doc_scraper 核心逻辑的 Web 化）。dry_run=true 时只做链接发现。"""
        started = time.time()
        try:
            data = await scrape_docs(
                http.client,
                base_url=req.base_url,
                max_pages=req.max_pages,
                rate_limit=req.rate_limit,
                include_patterns=req.include_patterns,
                exclude_patterns=req.exclude_patterns,
                selector=req.selector,
                use_sitemap=req.use_sitemap,
                use_llms_txt=req.use_llms_txt,
                dry_run=req.dry_run,
                categorize=req.categorize,
                categories=req.categories,
            )
        except ScraperError as e:
            raise HTTPException(status_code=502, detail=str(e))
        data["elapsed_sec"] = round(time.time() - started, 3)
        return ScrapeResponse(**data)

    @router.post("/scrape/archive")
    async def scrape_archive(
        req: ArchiveScrapeRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """递归抓取文档站并直接打包 zip 下载：README.md 索引 + pages/*.md +
        categories.json / quick_reference.md（categorize=true 时）。"""
        started = time.time()
        # scope=auto：无扩展名叶子起始页（…/introduction）放宽到所在目录，
        # 否则目录前缀只会圈住起始页自己、包里永远只有一页
        scope_root = None
        if req.scope == "auto" and not req.base_url.endswith("/"):
            last = req.base_url.rsplit("/", 1)[-1]
            if last and "." not in last:
                scope_root = req.base_url.rsplit("/", 1)[0] + "/"
        try:
            data = await scrape_docs(
                http.client,
                base_url=req.base_url,
                max_pages=req.max_pages,
                rate_limit=req.rate_limit,
                include_patterns=req.include_patterns,
                exclude_patterns=req.exclude_patterns,
                selector=req.selector,
                use_sitemap=req.use_sitemap,
                use_llms_txt=req.use_llms_txt,
                dry_run=False,
                categorize=req.categorize,
                categories=req.categories,
                scope_root=scope_root,
            )
        except ScraperError as e:
            raise HTTPException(status_code=502, detail=str(e))
        data["elapsed_sec"] = round(time.time() - started, 3)
        zip_bytes = build_docs_archive(data)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{archive_filename(req.base_url)}"',
                "X-Scrape-Pages": str(data.get("pages_saved", 0)),
            },
        )

    return router
