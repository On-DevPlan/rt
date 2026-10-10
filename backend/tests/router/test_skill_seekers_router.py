"""Router-level tests for the skill_seekers module（respx 拦上游）。

注意两点：
- 正文必须超过 20 字符（extract_content 跳过短段落，忠实原仓库语义）
- max_pages / exclude / dry-run 场景天然不会打全部路由，用 assert_all_called=False
"""
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from rt_backend.core.http import HttpClientHolder
from rt_backend.skill_seekers.router import build_router

LONG = "这一段正文足够长，超过二十个字符的提取阈值，会被保留进 content 字段。"


def _page(title: str, links: str = "") -> str:
    return f"""
    <html><head><title>{title}</title></head><body>
    <article><h1>{title}</h1><p>{LONG}</p>{links}</article>
    </body></html>
    """


async def _make_client():
    holder = HttpClientHolder(timeout=5.0)
    await holder.start()
    app = FastAPI()
    app.include_router(build_router(lambda: holder))
    return TestClient(app)


BASE = "https://docs.test/guide/index.html"


@pytest.mark.asyncio
async def test_scrape_bfs_follows_links():
    client = await _make_client()
    pages = {
        "/guide/index.html": _page(
            "Index",
            links='<a href="/guide/start.html">开始</a>'
            '<a href="/api/other.html">站外</a>'
            '<a href="/guide/start.html#top">重复锚点</a>',
        ),
        "/guide/start.html": _page("Start", links='<a href="/guide/advanced.html">进阶</a>'),
        "/guide/advanced.html": _page("Advanced"),
        "/api/other.html": _page("Other"),
    }
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        for path, html in pages.items():
            router.get(path).mock(return_value=Response(200, html=html))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={"base_url": BASE, "use_sitemap": False, "rate_limit": 0},
            )
            other_calls = router.routes[-1].call_count  # /api/other.html 的路由

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pages_scraped"] == 3  # index + start + advanced
    assert body["discovered_via_sitemap"] == 0
    assert body["pages_saved"] == 3
    urls = [p["url"] for p in body["pages"]]
    assert "https://docs.test/guide/advanced.html" in urls
    # 目录前缀外不进队列、不被抓
    assert other_calls == 0
    assert all("api/other" not in u for u in urls)
    adv = next(p for p in body["pages"] if p["url"].endswith("advanced.html"))
    assert adv["title"] == "Advanced"
    assert adv["headings"][0]["text"] == "Advanced"
    assert "超过二十个字符" in adv["content"]


@pytest.mark.asyncio
async def test_scrape_sitemap_discovery_layer():
    client = await _make_client()
    sitemap = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://docs.test/guide/a.html</loc></url>
      <url><loc>https://docs.test/guide/b.html</loc></url>
      <url><loc>https://docs.test/elsewhere/x.html</loc></url>
    </urlset>"""
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        router.get("/sitemap.xml").mock(
            return_value=Response(200, text=sitemap, headers={"content-type": "application/xml"})
        )
        # base_url 本身也会被当页面访问
        router.get("/guide/").mock(return_value=Response(200, html=_page("GuideHome")))
        router.get("/guide/a.html").mock(return_value=Response(200, html=_page("A")))
        router.get("/guide/b.html").mock(return_value=Response(200, html=_page("B")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={"base_url": "https://docs.test/guide/", "rate_limit": 0},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    # sitemap 发现 3 个，目录前缀过滤后剩 2 个（a/b），elsewhere 不进队列
    assert body["discovered_via_sitemap"] == 2
    urls = [p["url"] for p in body["pages"]]
    assert "https://docs.test/guide/a.html" in urls
    assert all("elsewhere" not in u for u in urls)


@pytest.mark.asyncio
async def test_scrape_llms_txt_layer_when_sitemap_missing():
    """Layer 2：sitemap 没有结果才探测 llms.txt，发现链接并入 BFS。"""
    client = await _make_client()
    llms = """# Docs

- [A 页](https://docs.test/guide/a.html)
- [站外](https://other.test/x)
"""
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        # sitemap 不存在（404）
        router.get("/sitemap.xml").mock(return_value=Response(404))
        router.get("/llms.txt").mock(return_value=Response(200, text=llms))
        router.get("/guide/").mock(return_value=Response(200, html=_page("GuideHome")))
        a_calls = router.get("/guide/a.html").mock(return_value=Response(200, html=_page("A")))
        outside = router.get("/x").mock(return_value=Response(200, html=_page("X")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={"base_url": "https://docs.test/guide/", "rate_limit": 0},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discovered_via_sitemap"] == 0
    # llms.txt 2 个链接，目录前缀过滤后剩 1 个（a.html）
    assert body["discovered_via_llms_txt"] == 1
    assert a_calls.call_count == 1
    assert outside.call_count == 0  # 站外链接不入队


@pytest.mark.asyncio
async def test_scrape_llms_txt_skipped_when_sitemap_hit():
    """Layer 优先级：sitemap 已有结果就不探测 llms.txt（原仓库语义）。"""
    client = await _make_client()
    sitemap = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://docs.test/guide/a.html</loc></url>
    </urlset>"""
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        router.get("/sitemap.xml").mock(
            return_value=Response(200, text=sitemap, headers={"content-type": "application/xml"})
        )
        llms_calls = router.get("/llms.txt").mock(return_value=Response(200, text="# x"))
        router.get("/guide/").mock(return_value=Response(200, html=_page("GuideHome")))
        router.get("/guide/a.html").mock(return_value=Response(200, html=_page("A")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={"base_url": "https://docs.test/guide/", "rate_limit": 0},
            )

    assert r.status_code == 200
    assert r.json()["discovered_via_sitemap"] == 1
    assert llms_calls.call_count == 0  # sitemap 命中 → llms.txt 不探测


@pytest.mark.asyncio
async def test_scrape_exclude_patterns():
    client = await _make_client()
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        router.get("/guide/index.html").mock(
            return_value=Response(
                200,
                html=_page(
                    "Index",
                    links='<a href="/guide/old-page.html">旧页</a>'
                    '<a href="/guide/new-page.html">新页</a>',
                ),
            )
        )
        old_calls = router.get("/guide/old-page.html").mock(
            return_value=Response(200, html=_page("Old"))
        )
        router.get("/guide/new-page.html").mock(return_value=Response(200, html=_page("New")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={
                    "base_url": BASE,
                    "use_sitemap": False,
                    "rate_limit": 0,
                    "exclude_patterns": ["old-page"],
                },
            )

    assert r.status_code == 200
    assert old_calls.call_count == 0  # exclude 命中 → 根本不请求
    urls = [p["url"] for p in r.json()["pages"]]
    assert all("old-page" not in u for u in urls)


@pytest.mark.asyncio
async def test_scrape_dry_run_discovery_only():
    client = await _make_client()
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        router.get("/guide/index.html").mock(
            return_value=Response(
                200,
                html=_page("Index", links='<a href="/guide/x.html">X</a>'),
            )
        )
        x_calls = router.get("/guide/x.html").mock(return_value=Response(200, html=_page("X")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={"base_url": BASE, "use_sitemap": False, "dry_run": True, "rate_limit": 0},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert body["pages_saved"] == 0
    # dry-run 仍会抓每页做链接发现（原仓库语义），但只返回发现记录
    assert len(body["pages"]) == 2
    assert body["pages"][0]["dry_run"] is True
    assert body["pages"][0]["url"].endswith("index.html")
    assert "https://docs.test/guide/x.html" in body["pages"][0]["links"]
    assert body["pages"][1]["url"].endswith("x.html")
    assert x_calls.call_count == 1


@pytest.mark.asyncio
async def test_scrape_max_pages_cap():
    client = await _make_client()
    links = "".join(f'<a href="/guide/p{i}.html">{i}</a>' for i in range(10))
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        router.get("/guide/index.html").mock(
            return_value=Response(200, html=_page("Index", links))
        )
        for i in range(10):
            router.get(f"/guide/p{i}.html").mock(return_value=Response(200, html=_page(f"P{i}")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={"base_url": BASE, "use_sitemap": False, "max_pages": 3, "rate_limit": 0},
            )

    assert r.status_code == 200
    body = r.json()
    assert body["pages_scraped"] == 3  # max_pages 截断生效


@pytest.mark.asyncio
async def test_scrape_sitemap_index_recursion():
    """索引型 sitemap：对每个子 sitemap 拉取一次并提取页面（原仓库一层递归语义）。"""
    client = await _make_client()
    index = """<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://docs.test/sitemap-1.xml</loc></sitemap>
      <sitemap><loc>https://docs.test/sitemap-2.xml</loc></sitemap>
    </sitemapindex>"""
    sm1 = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://docs.test/guide/i1.html</loc></url>
    </urlset>"""
    sm2 = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://docs.test/guide/i2.html</loc></url>
    </urlset>"""
    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        router.get("/sitemap.xml").mock(
            return_value=Response(200, text=index, headers={"content-type": "application/xml"})
        )
        router.get("/sitemap-1.xml").mock(
            return_value=Response(200, text=sm1, headers={"content-type": "application/xml"})
        )
        router.get("/sitemap-2.xml").mock(
            return_value=Response(200, text=sm2, headers={"content-type": "application/xml"})
        )
        # 页面本体（BFS 抓正文）
        router.get("/guide/").mock(return_value=Response(200, html=_page("GuideHome")))
        router.get("/guide/i1.html").mock(return_value=Response(200, html=_page("I1")))
        router.get("/guide/i2.html").mock(return_value=Response(200, html=_page("I2")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={"base_url": "https://docs.test/guide/", "rate_limit": 0},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    # 索引里的子 sitemap 地址本身不应被当页面（/sitemap-1.xml 不在 guide 前缀内）
    assert body["discovered_via_sitemap"] == 2
    urls = [p["url"] for p in body["pages"]]
    assert any(u.endswith("i1.html") for u in urls)
    assert any(u.endswith("i2.html") for u in urls)


@pytest.mark.asyncio
async def test_scrape_categorize_aggregation():
    """categorize=true：响应附带 categories + quick_reference（patterns 聚合去重）。"""
    client = await _make_client()

    def _page_html(title: str, url_hint: str) -> str:
        return f"""
        <html><head><title>{title}</title></head><body>
        <article>
          <h1>{title}</h1>
          <p>{LONG}</p>
          <p>Usage: create a client with the base url for {url_hint}.</p>
          <pre><code>def make_{url_hint}():
    return Client()</code></pre>
          <a href="/guide/a.html">A</a><a href="/guide/b.html">B</a>
        </article>
        </body></html>
        """

    with respx.mock(base_url="https://docs.test", assert_all_called=False) as router:
        router.get("/guide/").mock(
            return_value=Response(
                200,
                html=_page_html(
                    "Alpha Index",
                    "alpha",
                ),
            )
        )
        router.get("/guide/a.html").mock(return_value=Response(200, html=_page_html("Beta page", "beta")))
        router.get("/guide/b.html").mock(return_value=Response(200, html=_page_html("Gamma page", "gamma")))
        with client as c:
            r = c.post(
                "/api/skill-seekers/scrape",
                json={
                    "base_url": "https://docs.test/guide/",
                    "rate_limit": 0,
                    "categorize": True,
                    "categories": {"manual": ["alpha"], "ref": ["beta", "gamma"]},
                },
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["categories"] is not None
    # 打分归类（title 命中 +2 过阈值）：alpha 页 → manual；beta/gamma 页 → ref
    assert "https://docs.test/guide/" in body["categories"]["manual"]
    assert set(body["categories"]["ref"]) == {
        "https://docs.test/guide/a.html",
        "https://docs.test/guide/b.html",
    }
    # patterns 聚合：3 页各自一条 usage pattern（代码不同不去重）
    assert body["quick_reference"] is not None
    assert len(body["quick_reference"]) == 3
    assert all(qr["description"] for qr in body["quick_reference"])
