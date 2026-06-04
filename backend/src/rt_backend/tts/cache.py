"""SQLite-backed TTS cache. Keyed by sha256 of (text|voice|rate|pitch)."""
import hashlib
import sqlite3
from pathlib import Path
from typing import Optional, Tuple


class TTSCache:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tts_cache (
                cache_key TEXT PRIMARY KEY,
                audio_b64 TEXT NOT NULL,
                voice TEXT NOT NULL,
                text TEXT NOT NULL,
                words TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

    @staticmethod
    def make_key(text: str, voice: str, rate: str, pitch: str) -> str:
        return hashlib.sha256(f"{text}|{voice}|{rate}|{pitch}".encode()).hexdigest()

    def get(self, key: str) -> Optional[Tuple[str, Optional[str]]]:
        row = self._conn.execute(
            "SELECT audio_b64, words FROM tts_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def set(
        self, key: str, audio_b64: str, voice: str, text: str, words: Optional[str]
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tts_cache (cache_key, audio_b64, voice, text, words) VALUES (?, ?, ?, ?, ?)",
            (key, audio_b64, voice, text, words),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
