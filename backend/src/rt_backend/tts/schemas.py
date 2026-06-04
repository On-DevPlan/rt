"""Pydantic schemas for the TTS endpoints."""
from typing import List, Optional

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str = "en-US-AndrewNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"


class WordTiming(BaseModel):
    text: str
    offset: float
    duration: float


class TTSWithTimingResponse(BaseModel):
    audio: str  # base64
    voice: str
    text: str
    words: List[WordTiming]
    cached: bool


class VoicesResponse(BaseModel):
    voices: List[str]


# Static voice list (matches previous tts_server.py behavior)
DEFAULT_VOICES: List[str] = [
    "en-US-AndrewNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunyangNeural",
]
