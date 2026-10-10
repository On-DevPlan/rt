"""端到端测试：真实 create_app 全链路。

- /health 与纯计算端点：直接打真实 app
- skill_seekers 爬取：对本地 fixture 文档站（conftest.doc_site）发真 HTTP 回环请求
- bilibili 系列上游端点：respx 拦截 api.bilibili.com，其余链路全真
"""
import pytest
import respx
from httpx import Response

BILI = "https://api.bilibili.com"


def test_health(real_app_client):
    r = real_app_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_all_crawler_prefixes_mounted(real_app_client):
    """五个新模块 + 既有模块都在真实 app 的 OpenAPI 里，前缀互不重叠。"""
    paths = set(real_app_client.get("/openapi.json").json()["paths"])
    for prefix in (
        "/api/bilibili-crawler",
        "/api/bilibili-tools",
        "/api/skill-seekers",
        "/api/mediacrawler",
        "/api/bilibili",
        "/api/tts",
    ):
        assert any(p.startswith(prefix) for p in paths), f"{prefix} 未挂载"


def test_convert_through_real_app(real_app_client):
    r = real_app_client.get("/api/bilibili-crawler/convert", params={"aid": 2})
    assert r.status_code == 200
    assert r.json()["bvid"] == "BV1xx411c7mD"


def test_skill_seekers_scrape_e2e_real_http(real_app_client, doc_site):
    """对本地 fixture 文档站发起真实 HTTP 爬取：sitemap 发现 + BFS + 内容提取。"""
    r = real_app_client.post(
        "/api/skill-seekers/scrape",
        json={"base_url": f"{doc_site}/docs/", "max_pages": 10, "rate_limit": 0},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    # sitemap 发现 a/b 两页（且在 base 目录前缀内）
    assert body["discovered_via_sitemap"] == 2
    assert body["pages_scraped"] >= 3  # /docs/ 索引 + a + b
    urls = [p["url"] for p in body["pages"]]
    assert any(u.endswith("/docs/guide/a.html") for u in urls)
    assert any(u.endswith("/docs/guide/b.html") for u in urls)
    assert all("skip-me" not in u for u in urls), "目录前缀外的页面不应被抓取"

    a = next(p for p in body["pages"] if p["url"].endswith("a.html"))
    assert a["title"] == "PageA"
    assert "超过二十个字符" in a["content"]
    # index 页上的 utm 跟踪参数应被规范化剥离（链接去重后 a.html 只有一份）
    a_links = sum(1 for u in urls if u.endswith("a.html"))
    assert a_links == 1


def test_skill_seekers_scrape_include_pattern_e2e(real_app_client, doc_site):
    r = real_app_client.post(
        "/api/skill-seekers/scrape",
        json={
            "base_url": f"{doc_site}/docs/",
            "rate_limit": 0,
            "include_patterns": ["b.html"],
        },
    )
    assert r.status_code == 200
    urls = [p["url"] for p in r.json()["pages"]]
    assert any(u.endswith("b.html") for u in urls)
    # include 对后续发现的链接生效：a.html 不被抓（起始页 /docs/ 无条件入队，原仓库语义）
    assert not any(u.endswith("a.html") for u in urls)


def test_bilibili_crawler_comments_through_real_app(real_app_client):
    """真实 app 路由 → HttpClientHolder → respx 拦截的上游。"""
    page1 = {
        "code": 0,
        "data": {
            "replies": [
                {
                    "rpid": "900",
                    "member": {
                        "uname": "e2e用户",
                        "sex": "女",
                        "mid": 7,
                        "level_info": {"current_level": 6},
                    },
                    "ctime": 1700000000,
                    "like": 99,
                    "content": {"message": "e2e 评论"},
                    "reply_control": {"location": "IP属地：上海"},
                    "rcount": 0,
                }
            ],
            "cursor": {"is_end": True},
        },
    }
    with respx.mock(base_url=BILI) as router:
        router.get("/x/v2/reply/main").mock(return_value=Response(200, json=page1))
        r = real_app_client.post(
            "/api/bilibili-crawler/comments",
            json={"oid": "170001", "type": 1, "pages": 1},
        )

    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["name"] == "e2e用户"
    assert item["location"] == "上海"
    assert item["level"] == 6


def test_bilibili_tools_favorites_through_real_app(real_app_client):
    payload = {
        "code": 0,
        "data": {
            "info": {"title": "e2e 收藏夹"},
            "medias": [{"id": 5, "bvid": "BV1e2e", "title": "e2e 视频", "cover": "http://p/5.jpg", "attr": 0}],
            "has_more": False,
        },
    }
    with respx.mock(base_url=BILI) as router:
        router.get("/x/v3/fav/resource/list").mock(return_value=Response(200, json=payload))
        r = real_app_client.get("/api/bilibili-tools/favorites", params={"mid": "42", "fid": "1", "limit": 1})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["fav_title"] == "e2e 收藏夹"
    assert body["items"][0]["title"] == "e2e 视频"


@pytest.mark.asyncio
async def test_real_app_via_httpx_asgi_transport(doc_site):
    """验收标准 2 的字面实现：httpx ASGITransport 启动真实 ASGI app 打完整链路。

    TestClient 走的是 starlette 的 portal 封装；这里用原生 httpx.AsyncClient +
    ASGITransport，并手动驱动 lifespan（ASGITransport 不触发 lifespan 事件）。
    """
    import httpx
    from httpx import ASGITransport

    import rt_backend.main as main_mod
    from rt_backend.sicau_timetable_v2.browser import PlaywrightHolder

    async def _noop_start(self):  # noqa: ANN001
        return None

    original = PlaywrightHolder.start
    PlaywrightHolder.start = _noop_start
    try:
        app = main_mod.create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                # 纯计算端点
                r = await client.get("/api/bilibili-crawler/convert", params={"aid": 2})
                assert r.status_code == 200
                assert r.json()["bvid"] == "BV1xx411c7mD"
                # 爬虫端点：对本地 fixture 站点发真实 HTTP
                r = await client.post(
                    "/api/skill-seekers/scrape",
                    json={"base_url": f"{doc_site}/docs/", "max_pages": 5, "rate_limit": 0},
                )
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["pages_saved"] >= 3
                assert any(p["url"].endswith("b.html") for p in body["pages"])
    finally:
        PlaywrightHolder.start = original


def test_mediacrawler_platforms_through_real_app(real_app_client):
    r = real_app_client.get("/api/mediacrawler/platforms")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()["platforms"]]
    assert names == ["bilibili", "xhs", "douyin", "kuaishou", "weibo", "tieba", "zhihu"]


def test_mediacrawler_search_through_real_app(real_app_client):
    """真实 app 路由 → 跨模块复用 bilibili_crawler 的 WBI 签名 → respx 拦截上游。"""
    nav = {
        "code": 0,
        "data": {
            "wbi_img": {
                "img_url": f"https://i0.hdslb.com/bfs/wbi/{'a' * 32}.png",
                "sub_url": f"https://i0.hdslb.com/bfs/wbi/{'b' * 32}.png",
            }
        },
    }
    search = {
        "code": 0,
        "data": {
            "numResults": 42,
            "result": [
                {
                    "result_type": "video",
                    "data": [
                        {
                            "aid": 9,
                            "bvid": "BV1e2e3e4e5",
                            "title": '<em class="keyword">e2e</em>搜索',
                            "author": "up",
                            "play": 10,
                        }
                    ],
                }
            ],
        },
    }
    with respx.mock(base_url=BILI) as router:
        router.get("/x/web-interface/nav").mock(return_value=Response(200, json=nav))
        router.get("/x/web-interface/wbi/search/type").mock(return_value=Response(200, json=search))
        r = real_app_client.post("/api/mediacrawler/search", json={"keyword": "e2e"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["num_results"] == 42
    assert body["items"][0]["title"] == "e2e搜索"  # 高亮标签剥除


def test_play_url_risk_control_key_refresh_through_real_app(real_app_client):
    """全链路风控换 key：签名请求首次 -352 → 失效 WBI 缓存重签 → 第二次成功。

    nav 至少被取一次（真实 app 的 client 缓存可能已被前面的 e2e 预热），
    playurl 恰好两次（失败 + 重试）。
    """
    def _nav() -> dict:
        return {
            "code": 0,
            "data": {
                "wbi_img": {
                    "img_url": f"https://i0.hdslb.com/bfs/wbi/{'a' * 32}.png",
                    "sub_url": f"https://i0.hdslb.com/bfs/wbi/{'b' * 32}.png",
                }
            },
        }

    playurl_ok = {
        "code": 0,
        "data": {
            "quality": 80,
            "format": "mp4",
            "accept_quality": [80],
            "accept_description": ["高清 1080P"],
            "timelength": 300000,
            "durl": [{"url": "http://cdn/x.mp4", "backup_url": None, "size": 1}],
        },
    }
    with respx.mock(base_url=BILI) as router:
        nav_route = router.get("/x/web-interface/nav").mock(side_effect=[Response(200, json=_nav()), Response(200, json=_nav())])
        play_route = router.get("/x/player/wbi/playurl").mock(
            side_effect=[
                Response(200, json={"code": -352, "message": "风控拦截"}),
                Response(200, json=playurl_ok),
            ]
        )
        r = real_app_client.post(
            "/api/bilibili-crawler/play-url",
            json={"aid": 170001, "cid": 9001, "qn": 80},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["quality"] == 80
    assert body["durl"][0]["url"] == "http://cdn/x.mp4"
    assert play_route.call_count == 2  # -352 失败一次 + 换 key 重试成功
    assert nav_route.call_count >= 1


def test_bilibili_tools_favorites_add_through_real_app(monkeypatch, real_app_client):
    """写操作全链路：-503 envelope 限流 → 自动退避重试 → 第二次成功。"""
    import rt_backend.bilibili_tools.service as svc

    monkeypatch.setattr(svc, "_FAV_ADD_THROTTLE", 0.0)
    monkeypatch.setattr(svc, "_FAV_ADD_RETRY_DELAYS", (0.0, 0.0))
    with respx.mock(base_url=BILI) as router:
        add_route = router.post("/x/v2/fav/video/add").mock(
            side_effect=[
                Response(200, json={"code": -503, "message": "调用速度过快"}),
                Response(200, json={"code": 0, "message": "0"}),
            ]
        )
        r = real_app_client.post(
            "/api/bilibili-tools/favorites/add",
            json={"sessdata": "sd", "bili_jct": "jct", "fid": "123", "aids": ["170001"]},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok_count"] == 1
    assert add_route.call_count == 2


def test_bilibili_tools_audio_trio_through_real_app(real_app_client):
    """音频区三端点全链路（单曲信息 / 歌单 / UP 主歌曲）。"""
    info = {"code": 0, "data": {"title": "e2e歌", "author": "唱见", "lyric": "http://l.lrc", "cover": "http://c.jpg"}}
    urls = {"code": 0, "data": {"cdns": ["http://cdn/song.m4a"]}}
    menu = {
        "code": 0,
        "data": {"data": [{"id": 1, "title": "歌一", "author": "a"}], "pageCount": 1, "curPage": 1},
    }
    upper = {
        "code": 0,
        "data": {"data": [{"id": 2, "title": "歌二", "uname": "b"}], "pageCount": 1, "curPage": 1},
    }
    with respx.mock(base_url=BILI) as router:
        router.get("/audio/music-service-c/web/song/info").mock(return_value=Response(200, json=info))
        router.get("/audio/music-service-c/url").mock(return_value=Response(200, json=urls))
        router.get("/audio/music-service-c/web/song/of-menu").mock(return_value=Response(200, json=menu))
        router.get("/audio/music-service/web/song/upper").mock(return_value=Response(200, json=upper))

        r1 = real_app_client.get("/api/bilibili-tools/audio/au241921", params={"quality": 1})
        r2 = real_app_client.get("/api/bilibili-tools/audio/playlist/am76105")
        r3 = real_app_client.get("/api/bilibili-tools/audio/user", params={"uid": "2932528"})

    assert r1.status_code == 200, r1.text
    assert r1.json()["cdns"] == ["http://cdn/song.m4a"]
    assert r2.status_code == 200, r2.text
    assert r2.json()["total"] == 1 and r2.json()["truncated"] is False
    assert r3.status_code == 200, r3.text
    assert r3.json()["items"][0]["author"] == "b"  # uname 归一为 author
