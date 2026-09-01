"""SICAU v2 HTTP endpoint — POST /api/sicau/v2/timetable."""
import logging
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..core.config import Settings
from ..sicau_timetable.service import FetchError, LoginError, SicauError
from .browser import PlaywrightHolder
from .captcha_ocr import configure as configure_ocr
from .schemas import TimetableRequest, TimetableResponse
from .service import fetch_timetable_dsl_v2

logger = logging.getLogger(__name__)


def build_router(
    browser_provider: Callable[[], PlaywrightHolder],
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/api/sicau", tags=["sicau"])

    if settings.sicau_v2_glm_api_key:
        configure_ocr(settings.sicau_v2_glm_api_key)

    @router.post("/timetable", response_model=TimetableResponse)
    async def timetable(
        req: TimetableRequest,
        browser: PlaywrightHolder = Depends(browser_provider),
    ):
        semester = req.semester or settings.sicau_default_semester
        try:
            result = await fetch_timetable_dsl_v2(
                browser,
                req.user_id,
                req.password,
                semester,
                headless=settings.sicau_v2_headless,
                browser_timeout_ms=settings.sicau_v2_browser_timeout_ms,
                captcha_max_retries=max(30, settings.sicau_v2_captcha_max_retries),
            )
        except LoginError as e:
            raise HTTPException(status_code=401, detail=f"登录失败：{e}")
        except FetchError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except SicauError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            logger.exception("sicau v2 timetable failed user=%s semester=%s", req.user_id, semester)
            raise HTTPException(status_code=500, detail=repr(e))
        return TimetableResponse(**result)

    return router