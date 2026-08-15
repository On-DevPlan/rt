"""Anime season HTTP endpoint — 契约见 anime-backend-api-spec.md §3."""
import logging
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..core.config import Settings
from ..core.http import HttpClientHolder
from .schemas import SeasonResponse
from .service import SEASONS, AnimeUpstreamError, current_season_now, fetch_season

logger = logging.getLogger(__name__)


def build_router(
    http_provider: Callable[[], HttpClientHolder],
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/anime", tags=["anime"])

    @router.get("/season", response_model=SeasonResponse)
    async def season(
        season: Optional[str] = Query(None, description="WINTER|SPRING|SUMMER|FALL，缺省=当前季(JST)"),
        year: Optional[int] = Query(None, ge=1970, le=2999),
        weekday: Optional[int] = Query(None, ge=1, le=7, description="1=周一..7=周日，过滤该星期的条目"),
        http: HttpClientHolder = Depends(http_provider),
    ):
        if season is None:
            season, default_year = current_season_now()
            year = year or default_year
        else:
            season = season.upper()
            if season not in SEASONS:
                return JSONResponse(
                    status_code=400,
                    content={"error": {"code": "BAD_SEASON", "message": f"season 必须是 {SEASONS} 之一"}},
                )
            year = year or current_season_now()[1]

        try:
            payload = await fetch_season(
                http,
                season,
                year,
                cache_ttl_sec=settings.anime_cache_ttl_sec,
                timeout_sec=float(settings.anime_upstream_timeout_sec),
            )
        except AnimeUpstreamError as e:
            logger.exception("anime season upstream failed season=%s year=%s", season, year)
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "UPSTREAM_TIMEOUT", "message": str(e)}},
            )

        payload.pop("_source", None)
        if weekday is not None:
            payload = {**payload, "items": [i for i in payload["items"] if i.get("weekday") == weekday]}
        return SeasonResponse(**payload)

    return router
