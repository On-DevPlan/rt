"""Bilibili history HTTP endpoints."""
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..core.http import HttpClientHolder
from .schemas import HistoryRequest, HistoryResponse
from .service import (
    AuthError,
    BilibiliHistoryError,
    FetchError,
    fetch_recent_history,
)


def _mask_sessdata(sessdata: str) -> str:
    """Mask the SESSDATA so the response doesn't echo the full token back."""
    if len(sessdata) <= 8:
        return "***"
    return f"{sessdata[:4]}***{sessdata[-4:]}"


def build_router(
    http_provider: Callable[[], HttpClientHolder],
) -> APIRouter:
    router = APIRouter(prefix="/api/bilibili", tags=["bilibili"])

    @router.post("/history/recent", response_model=HistoryResponse)
    async def recent_history(
        req: HistoryRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        now = datetime.now(tz=timezone.utc)
        now_ts = int(now.timestamp())
        since_ts = now_ts - req.days * 86400

        try:
            items, pages_used = await fetch_recent_history(
                http=http,
                sessdata=req.sessdata,
                extra_cookies=req.extra_cookies,
                days=req.days,
                business=req.business,
                max_pages=req.max_pages,
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except FetchError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliHistoryError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"未预期错误：{e}")

        return HistoryResponse(
            sessdata_masked=_mask_sessdata(req.sessdata),
            days=req.days,
            business=req.business,
            since_ts=since_ts,
            since_iso=datetime.fromtimestamp(since_ts, tz=timezone.utc),
            until_ts=now_ts,
            until_iso=now,
            total=len(items),
            page_count=pages_used,
            items=items,
        )

    return router
