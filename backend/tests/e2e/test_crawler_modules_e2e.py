"""端到端测试：真实 create_app 全链路。

- /health 与纯计算端点：直接打真实 app
- skill_seekers 爬取：对本地 fixture 文档站（conftest.doc_site）发真 HTTP 回环请求
- bilibili 系列上游端点：respx 拦截 api.bilibili.com，其余链路全真
"""
import respx
from httpx import Response

BILI = "https://api.bilibili.com"


def test_health(real_app_client):
    r = real_app_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_all_crawler_prefixes_mounted(real_app_client):
    """四个新模块 + 既有模块都在真实 app 的 OpenAPI 里，前缀互不重叠。"""
    paths = set(real_app_client.get("/openapi.json").json()["paths"])
    for prefix in (
        "/api/bilibili-crawler",
        "/api/bilibili-tools",
        "/api/skill-seekers",
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
        "data": {"archives": [{"aid": 5, "title": "e2e 视频", "pic": "http://p/5.jpg", "state": 0}]},
    }
    with respx.mock(base_url=BILI) as router:
        router.get("/x/space/fav/arc").mock(return_value=Response(200, json=payload))
        r = real_app_client.get("/api/bilibili-tools/favorites", params={"mid": "42", "fid": "1", "limit": 1})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "e2e 视频"


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
