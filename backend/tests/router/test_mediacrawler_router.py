"""Router-level tests for the mediacrawler module（respx 拦上游）。"""
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from rt_backend.core.http import HttpClientHolder
from rt_backend.mediacrawler.router import build_router

NAV_URL = "/x/web-interface/nav"
SEARCH_URL = "/x/web-interface/wbi/search/type"

KEYS = {"img": "a" * 32, "sub": "b" * 32}


def _nav() -> dict:
    return {
        "code": 0,
        "data": {
            "wbi_img": {
                "img_url": f"https://i0.hdslb.com/bfs/wbi/{KEYS['img']}.png",
                "sub_url": f"https://i0.hdslb.com/bfs/wbi/{KEYS['sub']}.png",
            }
        },
    }


def _search_payload() -> dict:
    return {
        "code": 0,
        "data": {
            "numResults": 1234,
            "result": [
                {
                    "result_type": "video",
                    "data": [
                        {
                            "aid": 1,
                            "bvid": "BV1xx411c7mD",
                            "title": '<em class="keyword">爬虫</em>教程',
                            "author": "up1",
                            "mid": 10,
                            "play": 100,
                            "video_review": 5,
                            "favorites": 3,
                            "tag": "编程",
                            "pubdate": 1700000000,
                            "description": "描述",
                            "pic": "http://p/1.jpg",
                        }
                    ],
                },
                {"result_type": "live", "data": [{"title": "直播不该出现"}]},
            ],
        },
    }


async def _make_client():
    holder = HttpClientHolder(timeout=5.0)
    await holder.start()
    app = FastAPI()
    app.include_router(build_router(lambda: holder))
    return TestClient(app)


@pytest.mark.asyncio
async def test_platforms_capability_matrix():
    client = await _make_client()
    with client as c:
        r = c.get("/api/mediacrawler/platforms")
    assert r.status_code == 200
    body = r.json()
    names = [p["name"] for p in body["platforms"]]
    # MediaCrawler 的 7 平台全部列出
    assert set(names) == {"bilibili", "xhs", "douyin", "kuaishou", "weibo", "tieba", "zhihu"}
    bili = next(p for p in body["platforms"] if p["name"] == "bilibili")
    assert bili["wrapped"] is True and bili["playwright_required"] is False
    xhs = next(p for p in body["platforms"] if p["name"] == "xhs")
    assert xhs["wrapped"] is False and xhs["login_required"] is True


@pytest.mark.asyncio
async def test_search_signed_request_and_normalization():
    client = await _make_client()
    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(NAV_URL).mock(return_value=Response(200, json=_nav()))
        search_route = router.get(SEARCH_URL).mock(
            return_value=Response(200, json=_search_payload())
        )
        with client as c:
            r = c.post(
                "/api/mediacrawler/search",
                json={"keyword": "爬虫", "page": 2, "order": "click"},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["keyword"] == "爬虫"
    assert body["num_results"] == 1234
    # 只取 video 类型，live 块被过滤
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["bvid"] == "BV1xx411c7mD"
    assert item["title"] == "爬虫教程"  # <em> 高亮标签被剥掉
    # 请求必须带 WBI 签名参数与排序值
    sent = dict(search_route.calls[0].request.url.params)
    assert "w_rid" in sent and "wts" in sent
    assert sent["order"] == "click"
    assert sent["keyword"] == "爬虫"


@pytest.mark.asyncio
async def test_search_risk_control_maps_502():
    client = await _make_client()
    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(NAV_URL).mock(return_value=Response(200, json=_nav()))
        router.get(SEARCH_URL).mock(
            return_value=Response(200, json={"code": -412, "message": "请求被拦截"})
        )
        with client as c:
            r = c.post("/api/mediacrawler/search", json={"keyword": "x"})
    assert r.status_code == 502
    assert "风控" in r.json()["detail"]


@pytest.mark.asyncio
async def test_search_validation():
    client = await _make_client()
    with client as c:
        r = c.post("/api/mediacrawler/search", json={"keyword": ""})
        assert r.status_code == 422
        r = c.post("/api/mediacrawler/search", json={"keyword": "x", "order": "bogus"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_archive_greedy_zip():
    """搜索贪心翻页 → zip：第 2 页不足一页即停。"""
    import io
    import json as _json
    import zipfile

    client = await _make_client()

    def _search_page(n_hits):
        return {
            "code": 0,
            "data": {
                "numResults": 99,
                "result": [
                    {
                        "result_type": "video",
                        "data": [
                            {"aid": i, "bvid": f"BV{i}", "title": f"视频{i}", "author": "up", "play": i}
                            for i in range(n_hits)
                        ],
                    }
                ],
            },
        }

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(NAV_URL).mock(return_value=Response(200, json=_nav()))
        search_route = router.get(SEARCH_URL).mock(
            side_effect=[
                Response(200, json=_search_page(2)),
                Response(200, json=_search_page(1)),  # 不足 page_size=2 → 到底
            ]
        )
        with client as c:
            r = c.post(
                "/api/mediacrawler/search/archive",
                json={"keyword": "测试", "page_size": 2},
            )

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert search_route.call_count == 2
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(zf.namelist()) == {"README.md", "results.json", "results.md"}
    body = _json.loads(zf.read("results.json"))
    assert body["total"] == 3 and body["limit_hit"] is False
    assert "视频0" in zf.read("results.md").decode()
