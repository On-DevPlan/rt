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

    # --- Anime season (yuc.wiki + bangumi fallback) ---
    anime_cache_ttl_sec: int = 21600  # 6h，契约 §3.5
    anime_upstream_timeout_sec: int = 15

    tts_cache_db_path: str = "./tts_cache.db"

    # --- Rapfi (gomoku engine) ---
    rapfi_bin_path: str = "/opt/rapfi/pbrain-Rapfi"
    rapfi_model_dir: str = "/opt/rapfi"
    rapfi_time_turn_weak: int = 500
    rapfi_time_turn_mid: int = 2000
    rapfi_time_turn_strong: int = 5000
    rapfi_max_memory_mb: int = 256
    rapfi_threads: int = 1
    rapfi_max_node: int = 10_000_000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
