"""Async HTTP client holder. Single httpx.AsyncClient per process, managed via lifespan."""
import asyncio
from typing import Any, Optional

import httpx

# 重试默认值（语义对齐 Skill_Seekers retry_with_backoff：3 次尝试、base*2^(n-1) 退避、
# 仅 5xx 与连接错误重试，4xx 为确定性响应不重试）
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0
_RETRY_STATUSES = frozenset({500, 502, 503, 504})

# 模块级 sleep 符号：测试 monkeypatch 这里即可精确拦截重试退避，
# 不污染全局 asyncio.sleep（其他线程/模块的 sleep 不受影响）
_sleep = asyncio.sleep


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int | None = None,
    base_delay: float | None = None,
    retry_statuses: frozenset[int] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """带指数退避的请求：连接/超时异常与 retry_statuses 触发重试，其余响应原样返回。

    delay = base_delay * 2**(attempt-1)（1s, 2s, 4s…）；4xx 不重试（调用方自行
    raise_for_status）。默认值从模块常量读取，便于测试 monkeypatch。
    """
    attempts = max_attempts if max_attempts is not None else _RETRY_MAX_ATTEMPTS
    delay_base = base_delay if base_delay is not None else _RETRY_BASE_DELAY
    statuses = retry_statuses if retry_statuses is not None else _RETRY_STATUSES

    for attempt in range(1, attempts + 1):
        try:
            resp = await client.request(method, url, **kwargs)
        except httpx.HTTPError:
            if attempt >= attempts:
                raise
        else:
            if resp.status_code in statuses and attempt < attempts:
                await _sleep(delay_base * (2 ** (attempt - 1)))
                continue
            return resp
        await _sleep(delay_base * (2 ** (attempt - 1)))
    raise RuntimeError("unreachable")  # pragma: no cover


class HttpClientHolder:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> Optional[httpx.AsyncClient]:
        return self._client

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
                follow_redirects=True,
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
