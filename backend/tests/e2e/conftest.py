"""E2E fixtures：本地 fixture 文档站（真 HTTP 回环）+ 真实 create_app 组装。

分层约定（见 tests/README.md）：
- unit/        纯函数，无 IO
- router/      respx 拦上游 + TestClient 打单模块路由
- e2e/（本层）  真实 create_app 全链路；爬虫场景对本地 fixture 站点发真 HTTP
"""
import socket
import threading
import time

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, PlainTextResponse

PAGE_TMPL = """
<html><head><title>{title}</title></head><body>
<article>
  <h1>{title}</h1>
  <p>{body}</p>
  {links}
</article>
</body></html>
"""

LONG = "这一段正文足够长，超过二十个字符的提取阈值，会被保留进 content 字段。"


def _page(title: str, links: str = "") -> str:
    return PAGE_TMPL.format(title=title, body=LONG, links=links)


def _fixture_site() -> Starlette:
    """一个迷你文档站：sitemap + 三页 + 跟踪参数链接 + 站外链接。"""

    async def sitemap(request):
        xml = f"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{request.base_url}docs/guide/a.html</loc></url>
  <url><loc>{request.base_url}docs/guide/b.html</loc></url>
</urlset>"""
        return PlainTextResponse(xml, media_type="application/xml")

    async def index(request):
        base = str(request.base_url)
        return HTMLResponse(
            _page(
                "Index",
                links=(
                    f'<a href="{base}docs/guide/a.html?utm_source=nav">A</a>'
                    f'<a href="{base}docs/guide/b.html#top">B</a>'
                    f'<a href="{base}api/skip-me.html">站外</a>'
                ),
            )
        )

    async def page_a(request):
        return HTMLResponse(_page("PageA", links=f'<a href="{request.base_url}docs/guide/b.html">B</a>'))

    async def page_b(request):
        return HTMLResponse(_page("PageB"))

    async def skip_me(request):
        return HTMLResponse(_page("SkipMe"))

    app = Starlette()
    app.router.add_route("/sitemap.xml", sitemap, methods=["GET"])
    app.router.add_route("/docs/", index, methods=["GET"])
    app.router.add_route("/docs/guide/a.html", page_a, methods=["GET"])
    app.router.add_route("/docs/guide/b.html", page_b, methods=["GET"])
    app.router.add_route("/api/skip-me.html", skip_me, methods=["GET"])
    return app


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def doc_site() -> str:
    """起真实 uvicorn 服务 fixture 文档站，返回 base_url（session 级共享）。"""
    import uvicorn

    port = _free_port()
    config = uvicorn.Config(_fixture_site(), host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):  # 等就绪
        if server.started:
            break
        time.sleep(0.1)
    assert server.started, "fixture 文档站未能启动"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def real_app_client():
    """真实 create_app()（main.py 全部路由挂载 + lifespan）。

    唯一妥协：PlaywrightHolder.start（sicau_v2 的 chromium 急启动）patch 成 no-op，
    e2e 目标是爬虫新模块与整体装配，不是 sicau 浏览器。
    """
    import rt_backend.main as main_mod
    from rt_backend.sicau_timetable_v2.browser import PlaywrightHolder

    async def _noop_start(self):  # noqa: ANN001
        return None

    original = PlaywrightHolder.start
    PlaywrightHolder.start = _noop_start
    try:
        app = main_mod.create_app()
        with TestClient(app) as client:
            yield client
    finally:
        PlaywrightHolder.start = original
