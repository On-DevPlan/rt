"""TTS service: streams audio from edge-tts and returns timing-aware responses."""
import asyncio
import base64
import json
from typing import AsyncIterator, List, Optional, Tuple

import edge_tts

from .cache import TTSCache
from .schemas import WordTiming


async def stream_audio(text: str, voice: str, rate: str, pitch: str) -> AsyncIterator[bytes]:
    """Yield audio chunks as they arrive from edge-tts."""
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]


async def synthesize_with_timing(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    cache: TTSCache,
) -> Tuple[bytes, List[WordTiming], bool]:
    """Return (audio_bytes, word_timings, was_cached)."""
    key = TTSCache.make_key(text, voice, rate, pitch)
    cached = cache.get(key)
    if cached:
        audio_b64, words_json = cached
        words: List[WordTiming] = []
        if words_json:
            for w in json.loads(words_json):
                words.append(WordTiming(**w))
        return base64.b64decode(audio_b64), words, True

    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    audio = bytearray()
    words: List[WordTiming] = []
    async for chunk in comm.stream():
        if chunk["type"] == "WordBoundary":
            words.append(
                WordTiming(
                    text=chunk["text"],
                    offset=round(chunk["offset"] / 10 / 1000, 2),
                    duration=round(chunk["duration"] / 10 / 1000, 2),
                )
            )
        elif chunk["type"] == "audio":
            audio.extend(chunk["data"])

    audio_b64 = base64.b64encode(bytes(audio)).decode()
    cache.set(key, audio_b64, voice, text, json.dumps([w.model_dump() for w in words]))
    return bytes(audio), words, False
