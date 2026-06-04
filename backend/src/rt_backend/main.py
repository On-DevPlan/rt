"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.http import HttpClientHolder
from .core.logging import configure_logging, request_id_middleware
from .tts.cache import TTSCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    http_holder = HttpClientHolder(timeout=float(settings.sicau_request_timeout_sec))
    await http_holder.start()
    app.state.http = http_holder

    tts_cache = TTSCache(settings.tts_cache_db_path)
    app.state.tts_cache = tts_cache

    try:
        yield
    finally:
        await http_holder.close()
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

    from .sicau_timetable.router import build_router as _build_sicau
    app.include_router(_build_sicau(_http_dep, settings))

    return app


app = create_app()
