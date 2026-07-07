"""Tests for the bilibili_history router."""
import time

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from rt_backend.bilibili_history.router import build_router
from rt_backend.core.http import HttpClientHolder

HISTORY_URL = "https://api.bilibili.com/x/web-interface/history/cursor"


def _make_payload(items: list[dict], cursor: dict | None = None) -> dict:
    return {
        "code": 0,
        "message": "0",
        "ttl": 1,
        "data": {
            "cursor": cursor
            or {
                "max": items[-1]["history"]["oid"] if items else 0,
                "view_at": items[-1]["view_at"] if items else 0,
                "business": items[-1]["history"]["business"] if items else "",
                "ps": 30,
            },
            "tab": [],
            "list": items,
        },
    }


def _item(view_at: int, bvid: str = "BV1xx", title: str = "test", business: str = "archive") -> dict:
    return {
        "title": title,
        "cover": "http://example.com/c.jpg",
        "covers": None,
        "uri": "",
        "history": {
            "oid": 100,
            "epid": 0,
            "bvid": bvid,
            "page": 1,
            "cid": 200,
            "part": "p1",
            "business": business,
            "dt": 2,
        },
        "videos": 1,
        "author_name": "up",
        "author_face": "http://example.com/f.jpg",
        "author_mid": 1,
        "view_at": view_at,
        "progress": 10,
        "badge": "",
        "show_title": "p1",
        "duration": 100,
        "current": "",
        "total": 0,
        "new_desc": "",
        "is_finish": 0,
        "is_fav": 0,
        "kid": 100,
        "tag_name": "测试",
        "live_status": 0,
    }


@pytest.mark.asyncio
async def test_bilibili_history_success_filters_by_days():
    app = FastAPI()
    holder = HttpClientHolder(timeout=5.0)
    await holder.start()
    app.include_router(build_router(lambda: holder))

    now = int(time.time())
    # 3 条在 3 天内，1 条在 5 天前（应被过滤）
    recent_items = [
        _item(now - 3600, bvid="BV1", title="a"),
        _item(now - 86400, bvid="BV2", title="b"),
        _item(now - 86400 * 2, bvid="BV3", title="c"),
    ]
    old = _item(now - 86400 * 10, bvid="BV4", title="old")

    with respx.mock(base_url="https://api.bilibili.com") as router:
        # 第一次返回 recent + old（模拟 cursor 推进）
        router.get("/x/web-interface/history/cursor").mock(
            return_value=Response(
                200,
                json=_make_payload(
                    recent_items + [old],
                    cursor={"max": 100, "view_at": old["view_at"], "business": "archive", "ps": 30},
                ),
            )
        )

        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili/history/recent",
                json={"sessdata": "abc123def456", "days": 3},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert body["days"] == 3
    assert body["page_count"] == 1
    # 确认 SESSDATA 被脱敏
    assert "abc123def456" not in body["sessdata_masked"]
    assert body["sessdata_masked"].startswith("abc1")
    # 检查按 view_at 降序
    timestamps = [it["view_at"] for it in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
    # 老的 "old" 不在结果中
    titles = [it["title"] for it in body["items"]]
    assert "old" not in titles
    assert "a" in titles and "b" in titles and "c" in titles


@pytest.mark.asyncio
async def test_bilibili_history_auth_error():
    app = FastAPI()
    holder = HttpClientHolder(timeout=5.0)
    await holder.start()
    app.include_router(build_router(lambda: holder))

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get("/x/web-interface/history/cursor").mock(
            return_value=Response(200, json={"code": -101, "message": "未登录", "ttl": 1, "data": None})
        )
        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili/history/recent",
                json={"sessdata": "expired_token", "days": 7},
            )
    assert r.status_code == 401
    assert "-101" in r.json()["detail"] or "SESSDATA" in r.json()["detail"]


def test_bilibili_history_validation_missing_sessdata():
    app = FastAPI()
    holder = HttpClientHolder(timeout=5.0)
    app.include_router(build_router(lambda: holder))
    with TestClient(app) as client:
        r = client.post("/api/bilibili/history/recent", json={"days": 7})
    assert r.status_code == 422


def test_bilibili_history_validation_days_out_of_range():
    app = FastAPI()
    holder = HttpClientHolder(timeout=5.0)
    app.include_router(build_router(lambda: holder))
    with TestClient(app) as client:
        r = client.post(
            "/api/bilibili/history/recent",
            json={"sessdata": "x", "days": 100},
        )
    assert r.status_code == 422
