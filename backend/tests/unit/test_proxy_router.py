"""proxy 路由 + 编排：订阅生命周期 / 白名单解析 / 开关 / 状态。"""
import json
import os
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from fastapi import FastAPI

from rt_backend.core.config import Settings
from rt_backend.core.http import HttpClientHolder
from rt_backend.proxy.mihomo import MihomoError
from rt_backend.proxy.router import build_router
from rt_backend.proxy.service import ProxyClientView, ProxyService

SUB_URL = "https://panel.example.com/sub?token=secret123"

CLASH_SUB = yaml.safe_dump(
    {
        "proxies": [
            {"name": "hk-1", "type": "ss", "server": "1.2.3.4", "port": 443},
            {"name": "us-1", "type": "ss", "server": "5.6.7.8", "port": 443},
        ],
        "proxy-groups": [{"name": "🚀 PROXY", "type": "select", "proxies": ["hk-1", "us-1"]}],
        "rules": ["DOMAIN-SUFFIX,example.com,🚀 PROXY", "MATCH,🚀 PROXY"],
        # 危险键：必须被合并丢弃
        "tun": {"enable": True},
        "external-controller": "0.0.0.0:9999",
        "secret": "evil",
        "mixed-port": 1234,
    }
)


class FakeMihomo:
    def __init__(self):
        self.reloads: list[tuple[str, str]] = []
        self.version_value: str | None = None
        self.fail_reload = False

    async def version(self):
        return self.version_value

    async def reload(self, *, path, payload):
        if self.fail_reload:
            raise MihomoError("mihomo 拒绝了新配置（400）：bad")
        self.reloads.append((path, payload))

    async def counts(self):
        return (3, 1)

    async def close(self):
        pass


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        proxy_data_dir=str(tmp_path),
        mihomo_api_base="http://127.0.0.1:9090",
        mihomo_mixed_port=7890,
        proxy_subscription_timeout_sec=5,
        proxy_restore_wait_sec=0.1,
    )


def make_app(tmp_path: Path):
    """独立组装（不走 main.create_app，避免牵连全部模块）。"""
    holder = HttpClientHolder()
    fake = FakeMihomo()
    service = ProxyService(store_dir=tmp_path, mihomo=fake, settings=_settings(tmp_path))
    app = FastAPI()
    app.state.http = holder
    app.state.proxy = service
    app.include_router(build_router(lambda: holder, lambda: service))
    return app, holder, fake, service


def client_for(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _put_subscription(client: httpx.AsyncClient) -> httpx.Response:
    with respx.mock(base_url="https://panel.example.com") as router:
        router.get("/sub").mock(return_value=httpx.Response(200, text=CLASH_SUB))
        return await client.put("/api/proxy/subscription", json={"url": SUB_URL})


# --- PUT /subscription --------------------------------------------------------


@pytest.mark.asyncio
async def test_put_subscription_writes_config_and_reloads(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        resp = await _put_subscription(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["proxies"] == 3 and body["groups"] == 1
    assert body["rules"] == 2
    assert body["enabled"] is False  # 填订阅不改开关
    assert body["mihomo_reloaded"] is True

    # 落盘配置：base 键全胜、危险键丢弃、流量键存活
    cfg = yaml.safe_load((tmp_path / "mihomo" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["mixed-port"] == 7890
    assert cfg["external-controller"] == "127.0.0.1:9090"
    assert cfg["tun"] == {"enable": False}
    assert "secret" not in cfg
    assert cfg["proxies"][0]["name"] == "hk-1"
    assert cfg["rules"][0].startswith("DOMAIN-SUFFIX")

    assert len(fake.reloads) == 1
    # 状态持久化（URL 是凭据，只落本地 JSON）
    saved = json.loads((tmp_path / "proxy_settings.json").read_text(encoding="utf-8"))
    assert saved["subscription_url"] == SUB_URL


@pytest.mark.asyncio
async def test_put_subscription_invalid_422(tmp_path):
    app, *_ = make_app(tmp_path)
    async with client_for(app) as client:
        with respx.mock(base_url="https://panel.example.com") as router:
            router.get("/sub").mock(return_value=httpx.Response(200, text="proxies: []\n"))
            resp = await client.put("/api/proxy/subscription", json={"url": SUB_URL})
    assert resp.status_code == 422
    assert "节点" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_put_subscription_fetch_500_502(tmp_path):
    app, *_ = make_app(tmp_path)
    async with client_for(app) as client:
        with respx.mock(base_url="https://panel.example.com") as router:
            router.get("/sub").mock(return_value=httpx.Response(500))
            resp = await client.put("/api/proxy/subscription", json={"url": SUB_URL})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_put_subscription_mihomo_rejects_503_but_config_on_disk(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    fake.fail_reload = True
    async with client_for(app) as client:
        with respx.mock(base_url="https://panel.example.com") as router:
            router.get("/sub").mock(return_value=httpx.Response(200, text=CLASH_SUB))
            resp = await client.put("/api/proxy/subscription", json={"url": SUB_URL})
    assert resp.status_code == 503
    assert (tmp_path / "mihomo" / "config.yaml").exists()  # 配置已落盘
    settings_file = tmp_path / "proxy_settings.json"
    saved = json.loads(settings_file.read_text(encoding="utf-8")) if settings_file.exists() else {}
    assert saved.get("subscription_url") is None  # 失败不回写状态


# --- toggle / allowlist / 白名单解析 ---------------------------------------------


@pytest.mark.asyncio
async def test_toggle_without_subscription_422(tmp_path):
    app, *_ = make_app(tmp_path)
    async with client_for(app) as client:
        resp = await client.post("/api/proxy/toggle", json={"enabled": True})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_toggle_mihomo_down_503(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        await _put_subscription(client)  # fake.version 仍为 None
        resp = await client.post("/api/proxy/toggle", json={"enabled": True})
    assert resp.status_code == 503
    assert holder.proxy_client is None


@pytest.mark.asyncio
async def test_toggle_on_off_and_allowlist_resolution(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        await _put_subscription(client)
        fake.version_value = "v1.19.13"

        resp = await client.post("/api/proxy/toggle", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["effective"] is True
        assert holder.proxy_url == "http://127.0.0.1:7890"

        # 白名单核心：默认只有 skill_seekers 走代理
        proxied = ProxyClientView(holder, service, "skill_seekers").client
        direct = ProxyClientView(holder, service, "bilibili_crawler").client
        assert proxied is holder.proxy_client
        assert direct is holder.client

        # 改白名单即时生效（无需重建任何东西）
        resp = await client.put("/api/proxy/allowlist", json={"modules": ["bilibili_crawler", ""]})
        assert resp.status_code == 200
        assert resp.json()["modules"] == ["bilibili_crawler"]
        assert ProxyClientView(holder, service, "bilibili_crawler").client is holder.proxy_client
        assert ProxyClientView(holder, service, "skill_seekers").client is holder.client

        resp = await client.post("/api/proxy/toggle", json={"enabled": False})
        assert resp.status_code == 200
        assert holder.proxy_client is None
        assert ProxyClientView(holder, service, "bilibili_crawler").client is holder.client


# --- DELETE / refresh / status ---------------------------------------------------


@pytest.mark.asyncio
async def test_delete_subscription_resets_everything(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        await _put_subscription(client)
        fake.version_value = "v1.19.13"
        await client.post("/api/proxy/toggle", json={"enabled": True})

        resp = await client.delete("/api/proxy/subscription")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert holder.proxy_client is None
    cfg = yaml.safe_load((tmp_path / "mihomo" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["rules"] == ["MATCH,DIRECT"]  # stub 复位
    saved = json.loads((tmp_path / "proxy_settings.json").read_text(encoding="utf-8"))
    assert saved["subscription_url"] is None


@pytest.mark.asyncio
async def test_refresh_without_subscription_422(tmp_path):
    app, *_ = make_app(tmp_path)
    async with client_for(app) as client:
        resp = await client.post("/api/proxy/refresh")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_refresh_reapplies_subscription(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        await _put_subscription(client)
        reloaded_before = len(fake.reloads)
        with respx.mock(base_url="https://panel.example.com") as router:
            router.get("/sub").mock(return_value=httpx.Response(200, text=CLASH_SUB))
            resp = await client.post("/api/proxy/refresh")
    assert resp.status_code == 200
    assert len(fake.reloads) == reloaded_before + 1


@pytest.mark.asyncio
async def test_status_flags(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        resp = await client.get("/api/proxy/status?check_ip=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription_set"] is False
    assert body["enabled"] is False
    assert body["effective"] is False
    assert body["mihomo"]["running"] is False  # fake.version 未设置
    assert body["egress"] is None
    assert body["config_present"] is False


# --- restore_on_startup（重启恢复）------------------------------------------------


@pytest.mark.asyncio
async def test_restore_rebuilds_proxy_client(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        await _put_subscription(client)
        fake.version_value = "v1.19.13"
        await client.post("/api/proxy/toggle", json={"enabled": True})
    await service.close()
    await holder.close()

    # 模拟重启：全新 holder + service，同一数据目录
    holder2 = HttpClientHolder()
    service2 = ProxyService(store_dir=tmp_path, mihomo=fake, settings=_settings(tmp_path))
    await service2.restore_on_startup(holder2)
    assert holder2.proxy_client is not None
    assert holder2.proxy_url == "http://127.0.0.1:7890"
    await service2.close()
    await holder2.close()


@pytest.mark.asyncio
async def test_restore_degrades_to_direct_when_mihomo_down(tmp_path):
    app, holder, fake, service = make_app(tmp_path)
    async with client_for(app) as client:
        await _put_subscription(client)
        fake.version_value = "v1.19.13"
        await client.post("/api/proxy/toggle", json={"enabled": True})
    await service.close()
    await holder.close()

    fake.version_value = None  # mihomo 挂了
    holder2 = HttpClientHolder()
    service2 = ProxyService(store_dir=tmp_path, mihomo=fake, settings=_settings(tmp_path))
    await service2.restore_on_startup(holder2)  # 不抛，降级直连
    assert holder2.proxy_client is None
    saved = json.loads((tmp_path / "proxy_settings.json").read_text(encoding="utf-8"))
    assert saved["enabled"] is True  # 状态保留，status.effective 会显示 mismatch
    await service2.close()
    await holder2.close()
