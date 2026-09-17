"""reversing 模块的请求 / 响应模型。契约见 docs/reversing-protocol.md §4"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SignedNonceRequest(BaseModel):
    """handshake / attest 的入参。"""

    ts: int = Field(..., description="客户端 Unix 秒时间戳，服务器容忍 ±120s")
    client: str = Field(..., description="客户端标识，参与签名拼接")
    nonce: str = Field(..., description="16 位 hex，让签名不可复用")
    sig: str = Field(..., description="hmac_sha256(K, ts + '|' + client + '|' + nonce)")


class NotarizeRequest(BaseModel):
    """notarize 的入参。签名没有 nonce 段。"""

    ts: int
    client: str
    sig: str = Field(..., description="hmac_sha256(K6, ts + '|' + client)")


class TerminalRequest(BaseModel):
    """terminal 的入参。"""

    ts: int
    window: int = Field(..., description="来自 GET /challenge 的时间窗序号")
    nonce: int = Field(..., description="满足 PoW 的整数")
    client: str
    sig: str = Field(..., description="hmac_sha256(K8, ts + '|' + window + '|' + nonce)")


class ChallengeResponse(BaseModel):
    challenge: str = Field(..., description="32 位 hex，PoW 的前缀")
    bits: int = Field(..., description="需要的前导零比特数")
    window: int = Field(..., description="时间窗序号，terminal 请求要回显它")


class CipherResponse(BaseModel):
    ct: str = Field(..., description="xor_stream 加密后的 hex 密文")


class ErrorResponse(BaseModel):
    """拟真生产系统的错误信封。不透露任何方向。"""

    code: int
    msg: str
    trace_id: str
