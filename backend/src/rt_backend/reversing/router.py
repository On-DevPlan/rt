"""reversing 路由。契约见 docs/reversing-protocol.md §4"""
from __future__ import annotations

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from ..core.config import Settings
from ..core.logging import get_request_id
from . import service
from .schemas import (
    ChallengeResponse,
    CipherResponse,
    NotarizeRequest,
    SignedNonceRequest,
    TerminalRequest,
)

logger = logging.getLogger(__name__)

PREFIX = "/api/reversing/v1"


def _trace_id() -> str:
    """优先用 request_id 中间件注入的那个。

    中间件不在场时（例如测试里挂的裸 app）退化成随机值——信封的形状
    必须始终像真的，不能露出 '-' 这种内部占位符。
    """
    rid = get_request_id()
    if rid and rid != "-":
        return rid
    return secrets.token_hex(6)


def _envelope(exc: service.ReversingError) -> JSONResponse:
    """统一错误信封。什么都不透露。"""
    return JSONResponse(
        status_code=exc.status,
        content={
            "code": exc.status,
            "msg": exc.message,
            "trace_id": _trace_id(),
        },
    )


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix=PREFIX, tags=["reversing"])

    ledger = service.load_ledger()
    blob = service.load_blob()

    @router.get("/challenge", response_model=ChallengeResponse)
    async def challenge() -> ChallengeResponse:
        """G8 的 PoW 前缀。无状态：challenge 由主盐与时间窗纯函数派生。"""
        window = service.current_window()
        return ChallengeResponse(
            challenge=service.challenge_for(window, ledger.salt),
            bits=settings.reversing_pow_bits,
            window=window,
        )

    @router.post("/handshake", response_model=CipherResponse)
    async def handshake(req: SignedNonceRequest):
        """G4：签名校验。站点自己发的请求会故意失败。"""
        if not service.in_time_window(req.ts):
            return _envelope(service.SignatureError())
        try:
            ct = service.handshake(
                ledger, ts=req.ts, client=req.client, nonce=req.nonce, sig=req.sig
            )
        except service.ReversingError as exc:
            logger.info("handshake rejected client=%s", req.client)
            return _envelope(exc)
        return CipherResponse(ct=ct)

    @router.post("/attest", response_model=CipherResponse)
    async def attest(req: SignedNonceRequest):
        """G5：下发一段密文，真碎片藏在诱饵之后。"""
        if not service.in_time_window(req.ts):
            return _envelope(service.SignatureError())
        try:
            ct = service.attest(
                ledger, ts=req.ts, client=req.client, nonce=req.nonce, sig=req.sig
            )
        except service.ReversingError as exc:
            logger.info("attest rejected client=%s", req.client)
            return _envelope(exc)
        return CipherResponse(ct=ct)

    @router.post("/notarize", response_model=CipherResponse)
    async def notarize(
        req: NotarizeRequest,
        user_agent: Annotated[str, Header(alias="User-Agent")] = "",
    ):
        """G7：UA 硬门。浏览器无法设置 User-Agent，只能离开浏览器。"""
        if not service.in_time_window(req.ts):
            return _envelope(service.SignatureError())
        try:
            ct = service.notarize(
                ledger, ts=req.ts, client=req.client, sig=req.sig, user_agent=user_agent
            )
        except service.ReversingError as exc:
            logger.info("notarize rejected client=%s ua=%r", req.client, user_agent[:48])
            return _envelope(exc)
        return CipherResponse(ct=ct)

    @router.post("/terminal", response_model=CipherResponse)
    async def terminal(req: TerminalRequest):
        """G8：验 PoW + 验签，然后交出终章密文。"""
        if not service.in_time_window(req.ts):
            return _envelope(service.SignatureError())
        try:
            ct = service.terminal(
                ledger,
                blob,
                ts=req.ts,
                window=req.window,
                nonce=req.nonce,
                client=req.client,
                sig=req.sig,
                pow_bits=settings.reversing_pow_bits,
            )
        except service.ReversingError as exc:
            logger.info("terminal rejected client=%s", req.client)
            return _envelope(exc)
        return CipherResponse(ct=ct)

    # 蜜罐：好奇心撞墙区。恒 403，trace_id 是假的。
    @router.api_route(
        "/admin/{rest:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def honey_admin(rest: str):
        logger.warning("honeypot hit path=/admin/%s", rest)
        return JSONResponse(
            status_code=403,
            content={
                "code": 403,
                "msg": "权限不足",
                "trace_id": secrets.token_hex(6),
            },
        )

    return router
