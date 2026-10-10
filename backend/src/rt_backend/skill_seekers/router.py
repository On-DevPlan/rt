"""Skill Seekers doc-crawler HTTP endpoints（前缀 /api/skill-seekers）。"""
import time
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..core.http import HttpClientHolder
from .schemas import ScrapeRequest, ScrapeResponse
from .service import ScraperError, scrape_docs


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

    return router
