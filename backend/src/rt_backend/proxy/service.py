"""代理编排：订阅管理 / mihomo 热重载 / 白名单 client 解析。

数据流：订阅 URL --直连拉取--> parse/build（base 键全胜）--> /data/mihomo/config.yaml
      --PUT /configs?force=true--> mihomo 热重载；白名单模块经 ProxyClientView
      每请求动态解析直连/代理 client，开关与白名单改动即时生效。
"""
import asyncio
import datetime
import logging
from pathlib import Path
from typing import Any, Optional

import httpx

from ..core.config import Settings
from ..core.http import HttpClientHolder
from .config_builder import (
    SubscriptionInvalidError,
    build_config,
    parse_subscription,
    render_base_yaml,
    to_yaml,
)
from .mihomo import MihomoClient, MihomoError
from .store import ProxySettings, ProxySettingsStore

logger = logging.getLogger(__name__)

# 订阅面板按 UA 下发对应客户端格式——带 clash UA 拿 Clash YAML
_CLASH_UA = "clash.meta/rt-backend"
_IP_PROBE_URL = "https://api.ipify.org?format=json"
_IP_PROBE_TIMEOUT = 6.0


class ProxyError(RuntimeError):
    """代理模块基础异常。"""


class SubscriptionFetchError(ProxyError):
    """订阅 URL 拉取失败（网络/非 2xx/空响应）。"""


class MihomoUnavailableError(ProxyError):
    """mihomo 未运行或拒绝了配置。"""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


class ProxyClientView:
    """给路由当 holder 用（路由只访问 .client）。

    每次访问按「enabled + 模块在白名单」动态解析直连/代理 client，
    开关与白名单改动即时生效，无需重启。注意它不是 HttpClientHolder
    子类——main.py 的 _proxied_http_dep 只把它喂给外部 HTTP 模块的路由。
    """

    def __init__(self, holder: HttpClientHolder, proxy: "ProxyService", module: str) -> None:
        self._holder = holder
        self._proxy = proxy
        self.module = module

    @property
    def client(self):  # -> httpx.AsyncClient
        return self._proxy.resolve_client(self._holder, self.module)


class ProxyService:
    def __init__(self, *, store_dir: str | Path, mihomo: MihomoClient, settings: Settings) -> None:
        self._store = ProxySettingsStore(store_dir)
        self._mihomo = mihomo
        self._settings = settings
        self._s: ProxySettings = self._store.load()  # 内存镜像；所有变更走 _mutate

    @property
    def store(self) -> ProxySettingsStore:
        return self._store

    async def close(self) -> None:
        await self._mihomo.close()

    # --- 内部工具 -----------------------------------------------------------

    def _proxy_url(self) -> str:
        return f"http://127.0.0.1:{self._settings.mihomo_mixed_port}"

    def _controller(self) -> str:
        # "http://127.0.0.1:9090" -> "127.0.0.1:9090"（写进 mihomo 配置的 external-controller）
        return self._settings.mihomo_api_base.split("://", 1)[-1]

    def _mutate(self, **kw: Any) -> ProxySettings:
        for k, v in kw.items():
            setattr(self._s, k, v)
        self._s.updated_at = _now()
        self._store.save(self._s)
        return self._s

    def _write_config(self, payload: str) -> None:
        self._store.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._store.config_path.with_suffix(".yaml.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self._store.config_path)  # 原子落盘

    async def _reload(self, payload: str) -> None:
        try:
            await self._mihomo.reload(path=str(self._store.config_path), payload=payload)
        except MihomoError as e:
            raise MihomoUnavailableError(str(e)) from e

    async def _fetch_subscription(self, url: str) -> str:
        """直连拉取订阅（鸡生蛋：代理尚不存在时只能直连）。"""
        try:
            async with httpx.AsyncClient(
                trust_env=False,
                timeout=self._settings.proxy_subscription_timeout_sec,
                follow_redirects=True,
                headers={"User-Agent": _CLASH_UA},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SubscriptionFetchError(f"订阅拉取失败：{e}") from e
        if not resp.text.strip():
            raise SubscriptionFetchError("订阅响应为空")
        return resp.text

    async def _wait_mihomo(self, timeout: float) -> bool:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while await self._mihomo.version() is None:
            if loop.time() >= deadline:
                return False
            await asyncio.sleep(0.5)
        return True

    # --- 白名单核心 -----------------------------------------------------------

    def resolve_client(self, holder: HttpClientHolder, module: str):
        """enabled 且模块在白名单 → 代理 client，否则直连 client。"""
        if (
            self._s.enabled
            and holder.proxy_client is not None
            and module in self._s.allow_modules
        ):
            return holder.proxy_client
        return holder.client

    # --- 生命周期 -------------------------------------------------------------

    async def restore_on_startup(self, holder: HttpClientHolder) -> None:
        """进程启动恢复状态。幂等、永不抛——失败降级直连并告警。"""
        if not self._s.subscription_url:
            return
        if not self._store.config_path.exists():
            # config 丢失（如新数据卷）：用已存 URL 重拉，吞异常
            try:
                await self.set_subscription(holder, self._s.subscription_url)
            except Exception as e:  # noqa: BLE001 — 启动路径必须不抛
                logger.warning("proxy: 启动时恢复订阅失败: %s", e)
                return
        if not self._s.enabled:
            return
        if await self._wait_mihomo(self._settings.proxy_restore_wait_sec):
            await holder.start_proxy(self._proxy_url())
            logger.info("proxy: 已恢复代理（%s）", self._proxy_url())
        else:
            logger.warning(
                "proxy: mihomo 未就绪，白名单模块暂以直连运行（enabled 状态保留，可 POST /toggle 重试）"
            )

    # --- 订阅操作 -------------------------------------------------------------

    async def set_subscription(self, holder: HttpClientHolder, url: str) -> dict[str, Any]:
        text = await self._fetch_subscription(url)
        sub = parse_subscription(text)  # SubscriptionInvalidError → 422
        cfg = build_config(
            sub,
            mixed_port=self._settings.mihomo_mixed_port,
            controller=self._controller(),
        )
        payload = to_yaml(cfg)
        self._write_config(payload)
        await self._reload(payload)  # MihomoUnavailableError → 503（文件已落盘）
        self._mutate(subscription_url=url)
        counts = await self._mihomo.counts()
        return {
            "proxies": counts[0] if counts else None,
            "groups": counts[1] if counts else None,
            "rules": len(cfg.get("rules") or []),
            "enabled": self._s.enabled,
            "mihomo_reloaded": True,
            "mihomo_version": await self._mihomo.version(),
            "updated_at": self._s.updated_at,
        }

    async def clear_subscription(self, holder: HttpClientHolder) -> dict[str, Any]:
        """清除订阅：复位 stub 配置、关闭代理 client、清空状态。mihomo 不可达也不阻塞。"""
        payload = render_base_yaml(
            mixed_port=self._settings.mihomo_mixed_port,
            controller=self._controller(),
            stub=True,
        )
        self._write_config(payload)
        reloaded = True
        try:
            await self._reload(payload)
        except MihomoUnavailableError as e:
            # 状态清除是主目标；mihomo 内存里的旧配置等下次 reload 自然覆盖
            logger.warning("proxy: 复位配置后 mihomo 重载失败（%s）", e)
            reloaded = False
        await holder.stop_proxy()
        self._mutate(subscription_url=None, enabled=False)
        return {
            "proxies": None,
            "groups": None,
            "rules": 1,  # stub 的 MATCH,DIRECT
            "enabled": False,
            "mihomo_reloaded": reloaded,
            "mihomo_version": await self._mihomo.version(),
            "updated_at": self._s.updated_at,
        }

    async def refresh(self, holder: HttpClientHolder) -> dict[str, Any]:
        """用已存订阅 URL 重新拉取并应用。"""
        if not self._s.subscription_url:
            raise SubscriptionInvalidError("尚未配置订阅，无可刷新")
        return await self.set_subscription(holder, self._s.subscription_url)

    async def toggle(self, holder: HttpClientHolder, *, enabled: bool) -> dict[str, Any]:
        if enabled:
            if not self._s.subscription_url or not self._store.config_path.exists():
                raise SubscriptionInvalidError("尚未配置订阅，无法启用代理")
            version = await self._mihomo.version()
            if version is None:
                raise MihomoUnavailableError("mihomo 未运行，无法启用代理")
            await holder.start_proxy(self._proxy_url())
        else:
            await holder.stop_proxy()
        self._mutate(enabled=enabled)
        return {
            "enabled": self._s.enabled,
            "effective": enabled and holder.proxy_client is not None,
            "proxy_url": self._proxy_url() if enabled else None,
            "mihomo_version": await self._mihomo.version(),
        }

    def set_allowlist(self, modules: list[str]) -> dict[str, Any]:
        clean = sorted({m.strip() for m in modules if m and m.strip()})
        self._mutate(allow_modules=clean)
        return {"modules": clean, "enabled": self._s.enabled}

    # --- 状态 -----------------------------------------------------------------

    async def status(self, holder: HttpClientHolder, *, check_ip: bool) -> dict[str, Any]:
        version = await self._mihomo.version()
        counts = await self._mihomo.counts() if version else None
        effective = bool(
            self._s.enabled and version and holder.proxy_client is not None
        )
        egress: Optional[dict[str, Any]] = None
        if check_ip:
            egress = {
                "direct_ip": await self._probe_ip(None),
                "proxied_ip": await self._probe_ip(holder.proxy_client),
            }
        return {
            "subscription_url": self._s.subscription_url,
            "subscription_set": self._s.subscription_url is not None,
            "enabled": self._s.enabled,
            "effective": effective,
            "proxy_url": self._proxy_url() if holder.proxy_client is not None else None,
            "allow_modules": self._s.allow_modules,
            "mihomo": {
                "running": version is not None,
                "version": version,
                "proxies": counts[0] if counts else None,
                "groups": counts[1] if counts else None,
            },
            "config_present": self._store.config_path.exists(),
            "config_path": str(self._store.config_path),
            "updated_at": self._s.updated_at,
            "egress": egress,
        }

    @staticmethod
    async def _probe_ip(client: Optional[httpx.AsyncClient]) -> Optional[str]:
        """经指定 client 探测出口 IP；client=None 走一次性直连。失败返回 None 不抛。"""
        if client is None:
            async with httpx.AsyncClient(trust_env=False, timeout=_IP_PROBE_TIMEOUT) as c:
                client = c
        try:
            resp = await client.get(_IP_PROBE_URL)
            resp.raise_for_status()
            return str(resp.json().get("ip")) or None
        except (httpx.HTTPError, ValueError):
            return None
