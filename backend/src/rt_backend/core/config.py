"""Application settings loaded from environment via pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8080
    log_level: str = "INFO"

    sicau_default_semester: str = "2025-2026-2"
    sicau_request_timeout_sec: int = 30

    tts_cache_db_path: str = "./tts_cache.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
