"""MihomoClient：version 探活 / reload 传参 / 400 → MihomoError。"""
import httpx
import pytest
import respx

from rt_backend.proxy.mihomo import MihomoClient, MihomoError

CTRL = "http://127.0.0.1:9090"


@pytest.mark.asyncio
async def test_version_ok():
    with respx.mock(base_url=CTRL) as router:
        router.get("/version").mock(return_value=httpx.Response(200, json={"version": "v1.19.13"}))
        client = MihomoClient(CTRL)
        assert await client.version() == "v1.19.13"
        await client.close()


@pytest.mark.asyncio
async def test_version_down_returns_none():
    with respx.mock(base_url=CTRL) as router:
        router.get("/version").mock(side_effect=httpx.ConnectError("refused"))
        client = MihomoClient(CTRL)
        assert await client.version() is None  # 探活语义：挂了 = None，不抛
        await client.close()


@pytest.mark.asyncio
async def test_reload_sends_path_and_payload():
    with respx.mock(base_url=CTRL) as router:
        route = router.put("/configs").mock(return_value=httpx.Response(204))
        client = MihomoClient(CTRL)
        await client.reload(path="/data/mihomo/config.yaml", payload="mixed-port: 7890\n")
        await client.close()
    req = route.calls.last.request
    assert req.url.params["force"] == "true"
    body = req.read().decode()
    assert "/data/mihomo/config.yaml" in body
    assert "mixed-port" in body


@pytest.mark.asyncio
async def test_reload_bad_config_raises_mihomo_error():
    with respx.mock(base_url=CTRL) as router:
        router.put("/configs").mock(
            return_value=httpx.Response(400, text="yaml unmarshal errors")
        )
        client = MihomoClient(CTRL)
        with pytest.raises(MihomoError, match="400"):
            await client.reload(path="/x", payload="bad")
        await client.close()


@pytest.mark.asyncio
async def test_reload_controller_down_raises():
    with respx.mock(base_url=CTRL) as router:
        router.put("/configs").mock(side_effect=httpx.ConnectError("refused"))
        client = MihomoClient(CTRL)
        with pytest.raises(MihomoError, match="controller"):
            await client.reload(path="/x", payload="y")
        await client.close()


@pytest.mark.asyncio
async def test_counts_groups_and_proxies():
    payload = {
        "proxies": {
            "DIRECT": {"type": "Direct"},
            "REJECT": {"type": "Reject"},
            "GLOBAL": {"type": "Selector", "all": ["DIRECT"]},
            "hk-1": {"type": "Shadowsocks"},
            "us-1": {"type": "Vmess"},
            "🚀 选择": {"type": "Selector", "all": ["hk-1", "us-1"]},
        }
    }
    with respx.mock(base_url=CTRL) as router:
        router.get("/proxies").mock(return_value=httpx.Response(200, json=payload))
        client = MihomoClient(CTRL)
        assert await client.counts() == (2, 2)  # 节点 hk-1/us-1；组 GLOBAL/🚀选择
        await client.close()


@pytest.mark.asyncio
async def test_counts_down_returns_none():
    with respx.mock(base_url=CTRL) as router:
        router.get("/proxies").mock(side_effect=httpx.ConnectError("refused"))
        client = MihomoClient(CTRL)
        assert await client.counts() is None
        await client.close()
