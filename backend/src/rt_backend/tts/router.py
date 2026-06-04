"""TTS HTTP endpoints."""
import base64
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .cache import TTSCache
from .schemas import (
    DEFAULT_VOICES,
    TTSRequest,
    TTSWithTimingResponse,
    VoicesResponse,
)
from .service import stream_audio, synthesize_with_timing


def build_router(cache_provider: Callable[[], TTSCache]) -> APIRouter:
    """Build the TTS router. `cache_provider` is a FastAPI dependency that returns the TTSCache."""
    router = APIRouter(prefix="/api/tts", tags=["tts"])

    @router.post("", response_class=StreamingResponse)
    async def tts_stream(req: TTSRequest):
        async def gen():
            try:
                async for chunk in stream_audio(req.text, req.voice, req.rate, req.pitch):
                    yield chunk
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        return StreamingResponse(gen(), media_type="audio/mpeg")

    @router.post("/with-timing", response_model=TTSWithTimingResponse)
    async def tts_with_timing(
        req: TTSRequest,
        cache: TTSCache = Depends(cache_provider),
    ):
        try:
            audio_bytes, words, was_cached = await synthesize_with_timing(
                req.text, req.voice, req.rate, req.pitch, cache
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return TTSWithTimingResponse(
            audio=base64.b64encode(audio_bytes).decode(),
            voice=req.voice,
            text=req.text,
            words=words,
            cached=was_cached,
        )

    @router.get("/voices", response_model=VoicesResponse)
    async def voices():
        return VoicesResponse(voices=DEFAULT_VOICES)

    return router
