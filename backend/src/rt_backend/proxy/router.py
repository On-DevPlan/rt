"""代理管理 HTTP 端点（前缀 /api/proxy）。

注意：订阅 URL 是凭据——服务端任何路径都不打它的日志；
/status 回显它是为了单用户前端能展示当前值。
"""
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..core.http import HttpClientHolder
from .schemas import (
    AllowlistRequest,
    AllowlistResponse,
    ProxyStatusResponse,
    SubscriptionRequest,
    SubscriptionResponse,
    ToggleRequest,
    ToggleResponse,
)
from .service import (
    MihomoUnavailableError,
    ProxyService,
    SubscriptionFetchError,
    SubscriptionInvalidError,
)


def build_router(
    http_provider: Callable[[], HttpClientHolder],
    proxy_provider: Callable[[], ProxyService],
) -> APIRouter:
    router = APIRouter(prefix="/api/proxy", tags=["proxy"])

    @router.get("/status", response_model=ProxyStatusResponse)
    async def status(
        check_ip: bool = True,
        http: HttpClientHolder = Depends(http_provider),
        proxy: ProxyService = Depends(proxy_provider),
    ):
        """代理全景：订阅/开关/mihomo 存活/出口 IP 对比（check_ip=false 跳过探测）。"""
        data = await proxy.status(http, check_ip=check_ip)
        return ProxyStatusResponse(**data)

    @router.put("/subscription", response_model=SubscriptionResponse)
    async def put_subscription(
        req: SubscriptionRequest,
        http: HttpClientHolder = Depends(http_provider),
        proxy: ProxyService = Depends(proxy_provider),
    ):
        """填写订阅 URL：拉取 → 校验合并 → 落盘 → mihomo 热重载（不改变开关）。"""
        try:
            data = await proxy.set_subscription(http, req.url)
        except SubscriptionInvalidError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except SubscriptionFetchError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except MihomoUnavailableError as e:
            # 配置已落盘，mihomo 一恢复即可 POST /refresh 重试
            raise HTTPException(status_code=503, detail=f"{e}（配置已落盘，可稍后 POST /api/proxy/refresh 重试）")
        return SubscriptionResponse(**data)

    @router.delete("/subscription", response_model=SubscriptionResponse)
    async def delete_subscription(
        http: HttpClientHolder = Depends(http_provider),
        proxy: ProxyService = Depends(proxy_provider),
    ):
        """清除订阅并复位：关闭代理、恢复 stub 配置。"""
        data = await proxy.clear_subscription(http)
        return SubscriptionResponse(**data)

    @router.post("/toggle", response_model=ToggleResponse)
    async def toggle(
        req: ToggleRequest,
        http: HttpClientHolder = Depends(http_provider),
        proxy: ProxyService = Depends(proxy_provider),
    ):
        """启用/停用代理（仅影响白名单模块的出站）。"""
        try:
            data = await proxy.toggle(http, enabled=req.enabled)
        except SubscriptionInvalidError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except MihomoUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e))
        return ToggleResponse(**data)

    @router.post("/refresh", response_model=SubscriptionResponse)
    async def refresh(
        http: HttpClientHolder = Depends(http_provider),
        proxy: ProxyService = Depends(proxy_provider),
    ):
        """用已存订阅 URL 重新拉取（订阅更新 / mihomo 恢复后重试）。"""
        try:
            data = await proxy.refresh(http)
        except SubscriptionInvalidError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except SubscriptionFetchError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except MihomoUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e))
        return SubscriptionResponse(**data)

    @router.put("/allowlist", response_model=AllowlistResponse)
    async def put_allowlist(
        req: AllowlistRequest,
        proxy: ProxyService = Depends(proxy_provider),
    ):
        """设置允许走代理的模块白名单（即时生效，无需重启）。"""
        data = proxy.set_allowlist(req.modules)
        return AllowlistResponse(**data)

    return router
