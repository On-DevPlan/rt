"""Tests for the bilibili_tools router（迁移自 BilibiliTools 仓库）。

上游 B 站接口用 respx 拦截，不依赖外网与真实 cookie。
"""
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from rt_backend.bilibili_tools.router import build_router
from rt_backend.core.http import HttpClientHolder

FAV_LIST_URL = "/x/v3/fav/resource/list"
FAV_ADD_URL = "/x/v2/fav/video/add"
SONG_INFO_URL = "/audio/music-service-c/web/song/info"
AUDIO_URL_API = "/audio/music-service-c/url"
MENU_URL = "/audio/music-service-c/web/song/of-menu"
UPPER_URL = "/audio/music-service/web/song/upper"


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(build_router(lambda: _HOLDER))
    return app


@pytest_asyncio.fixture
async def client():
    await _HOLDER.start()
    with TestClient(_app()) as c:
        yield c
    await _HOLDER.close()


_HOLDER = HttpClientHolder(timeout=5.0)


def test_favorites_via_link_v3_api(client):
    """收藏夹枚举走 v3 接口：media_id= fid×100+mid尾号，ps≤20 分页按 has_more 停止。"""
    page1 = {
        "code": 0,
        "data": {
            "info": {"title": "我的收藏"},
            "medias": [
                {"id": 111, "bvid": "BV1a", "title": "视频一", "cover": "http://p/1.jpg", "attr": 0},
                {"id": 222, "bvid": "BV1b", "title": "已失效视频", "cover": "http://p/2.jpg", "attr": 1},
            ],
            "has_more": True,
        },
    }
    page2 = {
        "code": 0,
        "data": {
            "info": {"title": "我的收藏"},
            "medias": [{"id": 333, "bvid": "BV1c", "title": "视频三", "cover": "http://p/3.jpg", "attr": 0}],
            "has_more": False,
        },
    }

    with respx.mock(base_url="https://api.bilibili.com") as router:
        fav_route = router.get(FAV_LIST_URL).mock(
            side_effect=[Response(200, json=page1), Response(200, json=page2)]
        )
        with client as c:
            r = c.get(
                "/api/bilibili-tools/favorites",
                params={"link": "https://space.bilibili.com/42/favlist?fid=12345"},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mid"] == "42" and body["fid"] == "12345"
    assert body["fav_title"] == "我的收藏"
    assert body["total"] == 3
    # attr bit0 → 失效标记
    assert body["items"][0]["state"] == 0
    assert body["items"][1]["state"] == 1
    assert body["items"][0]["bvid"] == "BV1a"
    # media_id = 12345*100 + 42%100 = 1234542
    sent_p1 = dict(fav_route.calls[0].request.url.params)
    assert sent_p1["media_id"] == "1234542"
    assert sent_p1["ps"] == "20"
    # has_more=False → 停止翻页
    assert fav_route.call_count == 2


def test_favorites_limit_stops_early(client):
    page1 = {
        "code": 0,
        "data": {
            "info": {"title": "t"},
            "medias": [
                {"id": i, "bvid": f"BV{i}", "title": f"v{i}", "cover": "", "attr": 0}
                for i in range(5)
            ],
            "has_more": True,
        },
    }
    with respx.mock(base_url="https://api.bilibili.com") as router:
        fav_route = router.get(FAV_LIST_URL).mock(return_value=Response(200, json=page1))
        with client as c:
            r = c.get("/api/bilibili-tools/favorites", params={"mid": "42", "fid": "7", "limit": 3})

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3  # limit 截断
    assert fav_route.call_count == 1  # 不再多翻页


def test_favorites_private_folder_maps_403(client):
    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(FAV_LIST_URL).mock(
            return_value=Response(200, json={"code": -403, "message": "访问权限不足"})
        )
        with client as c:
            r = c.get("/api/bilibili-tools/favorites", params={"mid": "42", "fid": "999"})
    assert r.status_code == 403
    assert "权限" in r.json()["detail"]


def test_favorites_validation_requires_ids(client):
    r = client.get("/api/bilibili-tools/favorites")
    assert r.status_code == 422
    r = client.get("/api/bilibili-tools/favorites", params={"link": "https://example.com/nope"})
    assert r.status_code == 422


def test_favorites_add_batch(client):
    responses = [
        Response(200, json={"code": 0, "message": "0", "ttl": 1}),  # 成功
        Response(200, json={"code": 11007, "message": "你已经收藏过该视频！", "ttl": 1}),  # 已收藏
        Response(200, json={"code": 10003, "message": "不存在该稿件", "ttl": 1}),  # 不存在
    ]
    with respx.mock(base_url="https://api.bilibili.com") as router:
        add_route = router.post(FAV_ADD_URL).mock(side_effect=responses)
        r = client.post(
            "/api/bilibili-tools/favorites/add",
            json={"sessdata": "sd", "bili_jct": "jct", "fid": "123", "aids": ["1", "2", "3"]},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requested"] == 3
    assert body["ok_count"] == 2  # 成功 + 已收藏都算 ok
    assert body["results"][2]["pattern"] == 1  # 不存在
    # 请求体里必须带 csrf 与 aid
    sent = add_route.calls[0].request.content.decode()
    assert "csrf=jct" in sent and "fid=123" in sent


def test_song_info_merges_info_and_cdns(client):
    info = {"code": 0, "data": {"title": "歌", "author": "唱见", "lyric": "http://l.lrc", "cover": "http://c.jpg"}}
    urls = {"code": 0, "data": {"cdns": ["http://cdn1/song.m4a", "http://cdn2/song.m4a"]}}

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(SONG_INFO_URL).mock(return_value=Response(200, json=info))
        router.get(AUDIO_URL_API).mock(return_value=Response(200, json=urls))
        # 支持直接传 au{id} 完整链接
        r = client.get("/api/bilibili-tools/audio/au241921", params={"quality": 1})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sid"] == "241921"
    assert body["title"] == "歌"
    assert body["author"] == "唱见"
    assert body["quality"] == 1
    assert len(body["cdns"]) == 2


def test_song_info_invalid_id(client):
    r = client.get("/api/bilibili-tools/audio/notanid")
    assert r.status_code == 422


def test_menu_songs_paging(client):
    page1 = {
        "code": 0,
        "data": {
            "data": [
                {"id": 1, "title": "歌一", "author": "a", "lyric": "", "cover": ""},
            ],
            "pageCount": 2,
            "curPage": 1,
        },
    }
    page2 = {
        "code": 0,
        "data": {
            "data": [
                {"id": 2, "title": "歌二", "author": "b", "lyric": "", "cover": ""},
            ],
            "pageCount": 2,
            "curPage": 2,
        },
    }
    with respx.mock(base_url="https://api.bilibili.com") as router:
        menu_route = router.get(MENU_URL).mock(
            side_effect=[Response(200, json=page1), Response(200, json=page2)]
        )
        r = client.get("/api/bilibili-tools/audio/playlist/am76105", params={"max_pages": 5})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["menu_sid"] == "76105"
    assert body["total"] == 2
    assert body["items"][0]["sid"] == "1"
    assert menu_route.call_count == 2  # pageCount==curPage 后停止


def test_user_songs(client):
    payload = {
        "code": 0,
        "data": {
            "data": [
                {"id": 9, "title": "曲", "uname": "up", "lyric": "", "cover": ""},
            ],
            "pageCount": 1,
            "curPage": 1,
        },
    }
    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(UPPER_URL).mock(return_value=Response(200, json=payload))
        # 支持直接传 space 链接（query 参数，避免路径编码问题）
        r = client.get(
            "/api/bilibili-tools/audio/user",
            params={"link": "https://space.bilibili.com/2932528/audio"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uid"] == "2932528"
    assert body["total"] == 1
    assert body["items"][0]["author"] == "up"  # upper 接口的 uname 归一为 author


def test_user_songs_order_three_accepted_and_forwarded(client):
    payload = {"code": 0, "data": {"data": [], "pageCount": 1, "curPage": 1}}
    with respx.mock(base_url="https://api.bilibili.com") as router:
        route = router.get(UPPER_URL).mock(return_value=Response(200, json=payload))
        r = client.get(
            "/api/bilibili-tools/audio/user",
            params={"uid": "2932528", "order": 3},  # 3=最多收藏（上游合法）
        )
    assert r.status_code == 200, r.text
    assert route.calls.last.request.url.params["order"] == "3"


def test_user_songs_order_out_of_range_rejected(client):
    r = client.get("/api/bilibili-tools/audio/user", params={"uid": "2932528", "order": 4})
    assert r.status_code == 422  # 上游 order 合法域为 1/2/3
