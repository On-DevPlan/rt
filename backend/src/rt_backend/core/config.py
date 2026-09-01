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

    # --- SICAU timetable v2 (WebVPN + Playwright) ---
    sicau_v2_headless: bool = True
    sicau_v2_browser_timeout_ms: int = 60_000
    sicau_v2_total_timeout_sec: int = 90
    sicau_v2_captcha_max_retries: int = 3
    # 智谱 BigModel API key — GLM-4.6V-Flash 用于验证码识别（ddddocr 对该校验证码不准）
    sicau_v2_glm_api_key: str = ""

    # --- Anime season (yuc.wiki + bangumi fallback) ---
    anime_cache_ttl_sec: int = 21600  # 6h，契约 §3.5
    anime_upstream_timeout_sec: int = 15

    tts_cache_db_path: str = "./tts_cache.db"

    # --- Island cut (临时持久化，TTL 后清扫) ---
    island_cut_dir: str = ""  # 空 = 系统临时目录 / rt_island_cut
    island_cut_ttl_min: int = 60

    # --- Island cut video (MP4 → GIF) ---
    video_island_dir: str = ""  # 空 = 系统临时目录 / rt_island_cut_video
    video_island_ttl_min: int = 60

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
