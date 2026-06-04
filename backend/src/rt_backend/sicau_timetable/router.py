"""SICAU jiaowu timetable HTTP endpoints."""
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..core.config import Settings
from ..core.http import HttpClientHolder
from .schemas import TimetableRequest, TimetableResponse
from .service import (
    FetchError,
    LoginError,
    SicauError,
    fetch_timetable_dsl,
)


def build_router(
    http_provider: Callable[[], HttpClientHolder],
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/api/sicau", tags=["sicau"])

    @router.post("/timetable", response_model=TimetableResponse)
    async def timetable(
        req: TimetableRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        semester = req.semester or settings.sicau_default_semester
        try:
            result = await fetch_timetable_dsl(
                http, req.user_id, req.password, semester
            )
        except LoginError as e:
            raise HTTPException(status_code=401, detail=f"登录失败：{e}")
        except FetchError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except SicauError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return TimetableResponse(**result)

    return router
