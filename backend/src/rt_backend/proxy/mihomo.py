"""mihomo external-controller REST 客户端（控制面）。

自带小 client 且 trust_env=False——控制面请求永不走 7890 代理，
否则 mihomo 一挂整个 proxy 模块就跟着失联。
"""
import httpx
from typing import Optional, Tuple

# mihomo /proxies 返回里的内建条目（不算真实节点）
_BUILTIN_PROXIES = {"DIRECT", "REJECT", "REJECT-DROP", "COMPATIBLE", "PASS", "GLOBAL"}


class MihomoError(RuntimeError):
    """mihomo controller 返回非 2xx（如坏配置 400）。"""


class MihomoClient:
    def __init__(self, base_url: str = "http://127.0.0.1:9090", timeout: float = 4.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, trust_env=False, timeout=timeout
        )

    async def version(self) -> Optional[str]:
        """GET /version → 版本串；连接失败返回 None（探活语义，不抛）。"""
        try:
            resp = await self._client.get("/version")
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        return str(resp.json().get("version")) if resp.json().get("version") else None

    async def reload(self, *, path: str, payload: str) -> None:
        """PUT /configs?force=true 热重载。同时传 path（落盘真相）与 payload
        （内容优先，规避容器内路径解析差异）。坏配置 400 → MihomoError，旧配置继续跑。"""
        try:
            resp = await self._client.put(
                "/configs",
                params={"force": "true"},
                json={"path": path, "payload": payload},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise MihomoError(f"mihomo 拒绝了新配置（{e.response.status_code}）：{e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            raise MihomoError(f"无法连接 mihomo controller：{e}") from e

    async def counts(self) -> Optional[Tuple[int, int]]:
        """GET /proxies → (真实节点数, 策略组数)；失败返回 None。"""
        try:
            resp = await self._client.get("/proxies")
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        entries = resp.json().get("proxies") or {}
        proxies = 0
        groups = 0
        for name, value in entries.items():
            if not isinstance(value, dict):
                continue
            if "all" in value:
                groups += 1
            elif name not in _BUILTIN_PROXIES:
                proxies += 1
        return proxies, groups

    async def close(self) -> None:
        await self._client.aclose()
