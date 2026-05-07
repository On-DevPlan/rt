#!/usr/bin/env python3
"""
Edge TTS Server - Free natural English TTS using Microsoft Edge
Run: python tts_server.py
"""

import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import sys
import traceback
from aiohttp import web
import edge_tts

DB_PATH = os.path.join(os.path.dirname(__file__), "tts_cache.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tts_cache (
            cache_key TEXT PRIMARY KEY,
            audio_b64 TEXT NOT NULL,
            voice TEXT NOT NULL,
            text TEXT NOT NULL,
            words TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()

init_db()

def make_cache_key(text, voice, rate, pitch):
    data = f"{text}|{voice}|{rate}|{pitch}"
    return hashlib.sha256(data.encode()).hexdigest()

def get_cached(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT audio_b64, words FROM tts_cache WHERE cache_key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None

def set_cached(key, audio_b64, voice, text, words=None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO tts_cache (cache_key, audio_b64, voice, text, words) VALUES (?, ?, ?, ?, ?)",
        (key, audio_b64, voice, text, words)
    )
    conn.commit()
    conn.close()

async def cors_middleware(app, handler):
    async def middleware(request):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    return middleware

async def tts_handler(request):
    """Streaming TTS - returns audio chunks as generated."""
    try:
        data = await request.json()
        text = data.get("text", "")
        voice = data.get("voice", "en-US-AndrewNeural")
        rate = data.get("rate", "+0%")
        pitch = data.get("pitch", "+0Hz")

        if not text:
            return web.json_response({"error": "text is required"}, status=400)

        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'audio/mpeg',
                'Transfer-Encoding': 'chunked',
                'Access-Control-Allow-Origin': '*',
            }
        )
        await response.prepare(request)

        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                try:
                    await response.write(chunk["data"])
                except ConnectionResetError:
                    break

        await response.write_eof()
        return response

    except ConnectionResetError:
        raise
    except Exception as e:
        print(f"[tts_handler] Error: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        return web.json_response({"error": str(e)}, status=500)

async def tts_with_timing_handler(request):
    """
    Returns audio + word timings for synchronized highlighting.
    Uses cache for performance.
    """
    try:
        data = await request.json()
        text = data.get("text", "")
        voice = data.get("voice", "en-US-AndrewNeural")
        rate = data.get("rate", "+0%")
        pitch = data.get("pitch", "+0Hz")

        if not text:
            return web.json_response({"error": "text is required"}, status=400)

        cache_key = make_cache_key(text, voice, rate, pitch)
        cached = get_cached(cache_key)
        if cached:
            audio_b64, words_json = cached
            words = json.loads(words_json) if words_json else []
            return web.json_response({
                "audio": audio_b64,
                "voice": voice,
                "text": text,
                "words": words,
                "cached": True
            })

        communicate = edge_tts.Communicate(
            text, voice, rate=rate, pitch=pitch, boundary='WordBoundary'
        )
        words = []
        audio_data = bytearray()

        async for chunk in communicate.stream():
            if chunk["type"] == "WordBoundary":
                offset_ms = chunk["offset"] / 10 / 1000
                duration_ms = chunk["duration"] / 10 / 1000
                words.append({
                    "text": chunk["text"],
                    "offset": round(offset_ms, 2),
                    "duration": round(duration_ms, 2)
                })
            elif chunk["type"] == "audio":
                audio_data.extend(chunk["data"])

        audio_b64 = base64.b64encode(bytes(audio_data)).decode()
        set_cached(cache_key, audio_b64, voice, text, json.dumps(words))

        return web.json_response({
            "audio": audio_b64,
            "voice": voice,
            "text": text,
            "words": words,
            "cached": False
        })

    except Exception as e:
        print(f"[tts_with_timing] Error: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        return web.json_response({"error": str(e)}, status=500)
    voices = [
        "en-US-AndrewNeural", "en-US-AriaNeural", "en-US-GuyNeural",
        "en-US-JennyNeural", "en-GB-RyanNeural", "en-GB-SoniaNeural",
        "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunyangNeural",
    ]
    return web.json_response({"voices": voices})

async def health_handler(request):
    return web.Response(text='ok', content_type='text/plain')

app = web.Application(middlewares=[cors_middleware])
app.router.add_post("/tts", tts_handler)
app.router.add_post("/tts_with_timing", tts_with_timing_handler)
app.router.add_get("/voices", voices_handler)
app.router.add_get("/health", health_handler)

if __name__ == "__main__":
    print("Edge TTS Server starting on port 8080...")
    web.run_app(app, host="0.0.0.0", port=8080)
