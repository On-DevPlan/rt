import httpx
import pytest
import respx
from httpx import AsyncClient, Response

from rt_backend.core.http import HttpClientHolder, request_with_retry


@pytest.mark.asyncio
async def test_holder_starts_and_closes_client():
    holder = HttpClientHolder(timeout=5.0)
    assert holder.client is None
    await holder.start()
    assert isinstance(holder.client, AsyncClient)
    await holder.close()
    assert holder.client is None


@pytest.mark.asyncio
async def test_holder_idempotent():
    holder = HttpClientHolder()
    await holder.start()
    first = holder.client
    await holder.start()  # second call should not replace
    assert holder.client is first
    await holder.close()


# --- 代理 client：start_proxy / stop_proxy ------------------------------------


@pytest.mark.asyncio
async def test_proxy_client_lifecycle():
    holder = HttpClientHolder()
    await holder.start()
    assert holder.proxy_client is None
    assert holder.proxy_url is None

    await holder.start_proxy("http://127.0.0.1:7890")
    proxied = holder.proxy_client
    assert isinstance(proxied, AsyncClient)
    assert proxied is not holder.client  # 与直连 client 相互独立
    assert holder.proxy_url == "http://127.0.0.1:7890"

    await holder.stop_proxy()
    assert holder.proxy_client is None
    assert holder.proxy_url is None
    assert holder.client is not None  # 直连 client 不受影响
    await holder.close()


@pytest.mark.asyncio
async def test_proxy_client_idempotent_same_url():
    holder = HttpClientHolder()
    await holder.start_proxy("http://127.0.0.1:7890")
    first = holder.proxy_client
    await holder.start_proxy("http://127.0.0.1:7890")  # 同 URL 不重建
    assert holder.proxy_client is first
    await holder.close()


@pytest.mark.asyncio
async def test_proxy_client_rebuild_on_url_change():
    holder = HttpClientHolder()
    await holder.start_proxy("http://127.0.0.1:7890")
    first = holder.proxy_client
    await holder.start_proxy("http://127.0.0.1:7891")  # 换 URL 重建
    assert holder.proxy_client is not first
    assert holder.proxy_url == "http://127.0.0.1:7891"
    await holder.close()


@pytest.mark.asyncio
async def test_close_closes_proxy_client_too():
    holder = HttpClientHolder()
    await holder.start_proxy("http://127.0.0.1:7890")
    await holder.close()
    assert holder.client is None
    assert holder.proxy_client is None
    assert holder.proxy_url is None


# --- request_with_retry：指数退避重试 -----------------------------------------


@pytest.fixture
def sleep_calls(monkeypatch):
    """记录退避时长但不真正等待（避免测试变慢）。

    只 patch core.http 的模块级 _sleep，不碰全局 asyncio.sleep——
    全局 patch 会把其他线程（如 e2e 的 uvicorn loop）的 sleep 也记进来。
    """
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("rt_backend.core.http._sleep", fake_sleep)
    return delays


@pytest.mark.asyncio
async def test_retry_5xx_then_success(sleep_calls):
    with respx.mock(base_url="https://up.example.com") as router:
        route = router.get("/a").mock(side_effect=[Response(502), Response(200, json={"ok": True})])
        async with AsyncClient() as client:
            resp = await request_with_retry(client, "GET", "https://up.example.com/a", base_delay=0.01)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert route.call_count == 2
    assert len(sleep_calls) == 1  # 失败一次后退避一次


@pytest.mark.asyncio
async def test_retry_4xx_not_retried(sleep_calls):
    with respx.mock(base_url="https://up.example.com") as router:
        route = router.get("/b").mock(return_value=Response(404, json={"code": -404}))
        async with AsyncClient() as client:
            resp = await request_with_retry(client, "GET", "https://up.example.com/b")
    assert resp.status_code == 404
    assert route.call_count == 1  # 4xx 是确定性响应，不重试
    assert sleep_calls == []


@pytest.mark.asyncio
async def test_retry_exhausted_returns_last_5xx(sleep_calls):
    with respx.mock(base_url="https://up.example.com") as router:
        route = router.get("/c").mock(return_value=Response(503))
        async with AsyncClient() as client:
            resp = await request_with_retry(
                client, "GET", "https://up.example.com/c", max_attempts=3, base_delay=0.0
            )
    assert resp.status_code == 503  # 耗尽后返回最后一个响应，由调用方 raise_for_status
    assert route.call_count == 3


@pytest.mark.asyncio
async def test_retry_backoff_delay_doubles(sleep_calls):
    with respx.mock(base_url="https://up.example.com") as router:
        router.get("/d").mock(return_value=Response(500))
        async with AsyncClient() as client:
            await request_with_retry(
                client, "GET", "https://up.example.com/d", max_attempts=3, base_delay=2.0
            )
    # 尝试 1 后 2*2^0=2；尝试 2 后 2*2^1=4；尝试 3 无退避
    assert sleep_calls == [2.0, 4.0]


@pytest.mark.asyncio
async def test_retry_connection_error_then_success(sleep_calls):
    with respx.mock(base_url="https://up.example.com") as router:
        route = router.get("/e").mock(
            side_effect=[httpx.ConnectError("boom"), Response(200, json={"ok": True})]
        )
        async with AsyncClient() as client:
            resp = await request_with_retry(client, "GET", "https://up.example.com/e", base_delay=0.01)
    assert resp.status_code == 200
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_retry_connection_error_exhausted_raises(sleep_calls):
    with respx.mock(base_url="https://up.example.com") as router:
        route = router.get("/f").mock(side_effect=httpx.ConnectError("boom"))
        async with AsyncClient() as client:
            with pytest.raises(httpx.HTTPError):
                await request_with_retry(
                    client, "GET", "https://up.example.com/f", max_attempts=2, base_delay=0.0
                )
    assert route.call_count == 2
