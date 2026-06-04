import pytest
from rt_backend.core.config import Settings, get_settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("APP_HOST", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)
    s = Settings()
    assert s.app_host == "0.0.0.0"
    assert s.app_port == 8080
    assert s.log_level == "INFO"
    assert s.sicau_default_semester == "2025-2026-2"
    assert s.sicau_request_timeout_sec == 30


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("APP_PORT", "9999")
    monkeypatch.setenv("SICAU_DEFAULT_SEMESTER", "2026-2027-1")
    s = Settings()
    assert s.app_port == 9999
    assert s.sicau_default_semester == "2026-2027-1"


def test_get_settings_cached():
    a = get_settings()
    b = get_settings()
    assert a is b
