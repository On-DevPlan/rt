"""FastAPI application factory."""
from contextlib import asynccontextmanager
from pathlib import Path
import tempfile

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.http import HttpClientHolder
from .core.logging import configure_logging, request_id_middleware
from .island_cut.store import IslandJobStore
from .island_cut.video_apng.store import IslandVideoApngJobStore
from .island_cut.video_island.store import IslandVideoJobStore
from .island_cut.video_sheet.store import IslandSheetJobStore
from .island_cut.video_webp.store import IslandVideoWebPJobStore
from .sicau_timetable_v2.browser import PlaywrightHolder
from .tts.cache import TTSCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    http_holder = HttpClientHolder(timeout=float(settings.sicau_request_timeout_sec))
    await http_holder.start()
    app.state.http = http_holder

    v2_browser = PlaywrightHolder(headless=settings.sicau_v2_headless)
    await v2_browser.start()
    app.state.v2_browser = v2_browser

    tts_cache = TTSCache(settings.tts_cache_db_path)
    app.state.tts_cache = tts_cache

    island_root = (
        Path(settings.island_cut_dir)
        if settings.island_cut_dir
        else Path(tempfile.gettempdir()) / "rt_island_cut"
    )
    app.state.island_store = IslandJobStore(
        root=island_root, ttl_sec=settings.island_cut_ttl_min * 60
    )

    try:
        yield
    finally:
        await http_holder.close()
        await v2_browser.close()
        tts_cache.close()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="rt-backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS (open, like the previous TTS server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # request_id middleware
    @app.middleware("http")
    async def _rid(request, call_next):
        return await request_id_middleware(request, call_next)

    # video-sheet 整模块封锁（预览是其中 11MB/job 的浪费 + OOM 风险）
    # 取消封锁：删除此中间件 或 改 path 不以 /api/island-cut/video-sheet 开头
    @app.middleware("http")
    async def _lock_sheet_module(request, call_next):
        if request.url.path.startswith("/api/island-cut/video-sheet"):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"detail": "video-sheet 模块维护中（预览机制暂禁用）", "locked": True},
                status_code=503,
            )
        return await call_next(request)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Routers mounted with dependency providers that read from app.state
    from fastapi import Request as _Req

    def _tts_cache_dep(request: _Req) -> TTSCache:
        return request.app.state.tts_cache

    def _http_dep(request: _Req) -> HttpClientHolder:
        return request.app.state.http

    from .tts.router import build_router as _build_tts
    app.include_router(_build_tts(_tts_cache_dep))

    from .sicau_timetable.router import build_router as _build_sicau_old
    app.include_router(_build_sicau_old(_http_dep, settings))

    from .sicau_timetable_v2.router import build_router as _build_sicau_v2

    def _v2_browser_dep(request: _Req) -> PlaywrightHolder:
        return request.app.state.v2_browser

    app.include_router(_build_sicau_v2(_v2_browser_dep, settings))

    from .bilibili_history.router import build_router as _build_bili
    app.include_router(_build_bili(_http_dep))

    from .tetris_ai.router import build_router as _build_tetris
    app.include_router(_build_tetris())

    from .anime_season.router import build_router as _build_anime
    app.include_router(_build_anime(_http_dep, settings))

    def _island_store_dep(request: _Req) -> IslandJobStore:
        return request.app.state.island_store

    from .island_cut.router import build_router as _build_island_cut
    app.include_router(_build_island_cut(_island_store_dep))

    video_root = (
        Path(settings.video_island_dir)
        if settings.video_island_dir
        else Path(tempfile.gettempdir()) / "rt_island_cut_video"
    )
    app.state.video_store = IslandVideoJobStore(
        root=video_root, ttl_sec=settings.video_island_ttl_min * 60
    )

    def _island_video_store_dep(request: _Req) -> IslandVideoJobStore:
        return request.app.state.video_store

    from .island_cut.video_island.router import build_video_router as _build_video_island
    app.include_router(_build_video_island(_island_video_store_dep))

    webp_root = (
        Path(settings.video_island_dir)
        if settings.video_island_dir
        else Path(tempfile.gettempdir()) / "rt_island_cut_video_webp"
    )
    app.state.video_webp_store = IslandVideoWebPJobStore(
        root=webp_root, ttl_sec=settings.video_island_ttl_min * 60
    )

    def _island_video_webp_store_dep(request: _Req) -> IslandVideoWebPJobStore:
        return request.app.state.video_webp_store

    from .island_cut.video_webp.router import build_webp_router as _build_video_webp
    app.include_router(_build_video_webp(_island_video_webp_store_dep))

    apng_root = (
        Path(settings.video_island_dir)
        if settings.video_island_dir
        else Path(tempfile.gettempdir()) / "rt_island_cut_video_apng"
    )
    app.state.video_apng_store = IslandVideoApngJobStore(
        root=apng_root, ttl_sec=settings.video_island_ttl_min * 60
    )

    def _island_video_apng_store_dep(request: _Req) -> IslandVideoApngJobStore:
        return request.app.state.video_apng_store

    from .island_cut.video_apng.router import build_apng_router as _build_video_apng
    app.include_router(_build_video_apng(_island_video_apng_store_dep))

    sheet_root = (
        Path(settings.video_island_dir)
        if settings.video_island_dir
        else Path(tempfile.gettempdir()) / "rt_island_cut_video_sheet"
    )
    app.state.sheet_store = IslandSheetJobStore(
        root=sheet_root, ttl_sec=settings.video_island_ttl_min * 60
    )

    def _island_sheet_store_dep(request: _Req) -> IslandSheetJobStore:
        return request.app.state.sheet_store

    from .island_cut.video_sheet.router import build_sheet_router as _build_video_sheet
    app.include_router(_build_video_sheet(_island_sheet_store_dep))

    return app


app = create_app()
