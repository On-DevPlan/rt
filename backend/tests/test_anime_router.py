"""Router integration tests with respx-mocked upstreams."""
import json
from pathlib import Path

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from rt_backend.anime_season.router import build_router
from rt_backend.core.config import Settings
from rt_backend.core.http import HttpClientHolder

FIXTURE = Path(__file__).parent / "fixtures" / "yuc_sample.html"

YUC_URL = "http://yuc.wiki/202607/"
BGM_URL = "https://api.bgm.tv/calendar"


def _build_app(settings: Settings):
    app = FastAPI()
    holder = HttpClientHolder(timeout=10.0)
    app.include_router(build_router(lambda: holder, settings))
    return app, holder


@pytest.mark.asyncio
async def test_season_default_yuc_success():
    settings = Settings(anime_cache_ttl_sec=0)  # 缓存关，强制重取
    app, holder = _build_app(settings)
    await holder.start()
    with respx.mock() as router:
        router.get(YUC_URL).mock(return_value=Response(200, text=FIXTURE.read_text(encoding="utf-8")))
        with TestClient(app) as client:
            r = client.get("/api/v1/anime/season?season=SUMMER&year=2026")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["season"] == "SUMMER"
    assert body["year"] == 2026
    assert len(body["items"]) == 5  # fixture 中 5 个 TV 条目
    # 验收锚点：Re:0 风格跨季续播条目
    re0_like = next(i for i in body["items"] if "跨季续播番" in i["title"])
    assert re0_like["weekday"] == 3
    assert re0_like["time"] == "21:00"
    assert re0_like["titleNative"] == "続編アニメ 4th season"


@pytest.mark.asyncio
async def test_season_weekday_filter():
    settings = Settings(anime_cache_ttl_sec=0)
    app, holder = _build_app(settings)
    await holder.start()
    with respx.mock() as router:
        router.get(YUC_URL).mock(return_value=Response(200, text=FIXTURE.read_text(encoding="utf-8")))
        with TestClient(app) as client:
            r = client.get("/api/v1/anime/season?season=SUMMER&year=2026&weekday=7")
    items = r.json()["items"]
    # fixture 中 weekday=7 只有周六深夜番（周六 24:30 → 自然日周日）
    assert all(i["weekday"] == 7 for i in items)
    assert any(i["time"] == "00:30" for i in items)


@pytest.mark.asyncio
async def test_season_falls_back_to_bangumi_when_yuc_fails():
    settings = Settings(anime_cache_ttl_sec=0)
    app, holder = _build_app(settings)
    await holder.start()
    bgm_body = [
        {
            "weekday": {"id": 7, "cn": "星期日"},
            "items": [
                {"id": 999, "name": "降级测试番", "name_cn": "降级测试番"},
                {"id": 998, "name": "Old API", "name_cn": ""},
            ],
        }
    ]
    with respx.mock() as router:
        router.get(YUC_URL).mock(return_value=Response(502, text="upstream bad"))
        router.get(BGM_URL).mock(return_value=Response(200, text=json.dumps(bgm_body)))
        with TestClient(app) as client:
            r = client.get("/api/v1/anime/season?season=SUMMER&year=2026")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(i["title"] == "降级测试番" and i["weekday"] == 7 for i in items)
    # 无 name_cn 的条目降级用日文名（兜底）
    fallback = [i for i in items if i["title"] == "Old API"]
    assert fallback and fallback[0]["titleNative"] == "Old API"


@pytest.mark.asyncio
async def test_season_both_upstreams_fail_returns_error_shape():
    settings = Settings(anime_cache_ttl_sec=0)
    app, holder = _build_app(settings)
    await holder.start()
    with respx.mock() as router:
        router.get(YUC_URL).mock(return_value=Response(500, text="x"))
        router.get(BGM_URL).mock(return_value=Response(500, text="x"))
        with TestClient(app) as client:
            r = client.get("/api/v1/anime/season?season=SUMMER&year=2026")
    assert r.status_code == 502
    body = r.json()
    assert "error" in body and "code" in body["error"]
    assert body["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_season_bad_season_param_returns_error_shape():
    settings = Settings(anime_cache_ttl_sec=0)
    app, holder = _build_app(settings)
    with TestClient(app) as client:
        r = client.get("/api/v1/anime/season?season=BOGUS&year=2026")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "BAD_SEASON"