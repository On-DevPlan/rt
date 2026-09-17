"""reversing 业务逻辑。

无状态：不签发票据、不建会话表、不落盘任何人。
每个请求自带 ts，用时间窗判重放；签名密钥是玩家已掌握的碎片派生物。
服务器纯函数复算，零存储。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from . import crypto

DATA_DIR = Path(__file__).parent / "data"
SHARDS_FILE = DATA_DIR / "shards.json"
BLOB_FILE = DATA_DIR / "final.blob"

# 契约 §3：时间窗 ±120 秒
TIME_WINDOW_SEC = 120

# 契约 §4.4：这一关的墙是"浏览器设不了 User-Agent"，值本身不是秘密
REQUIRED_UA = "hb-client/1.0"

# 契约 §4.3：站点只消费前 16 位的诱饵，真碎片在后面
DECOY_5 = "0000000000000000"
TAIL_5 = "hb-attest-v1-tail"


@dataclass(frozen=True)
class Ledger:
    """从 data/shards.json 读出来的常量。进程启动读一次。"""

    salt: str
    shards: dict[int, str]

    @property
    def k4(self) -> str:
        return crypto.derive_k4(self.shards[0], self.shards[1], self.shards[2], self.shards[3])

    @property
    def k6(self) -> str:
        return crypto.derive_k6(self.shards[6])

    @property
    def k8(self) -> str:
        return crypto.derive_k8(self.shards[7])


def load_ledger() -> Ledger:
    raw = json.loads(SHARDS_FILE.read_text(encoding="utf-8"))
    return Ledger(
        salt=raw["salt"],
        shards={int(k): v for k, v in raw["shards"].items()},
    )


def load_blob() -> str:
    return BLOB_FILE.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------- 时间窗

def now_ts() -> int:
    return int(time.time())


def in_time_window(ts: int, *, now: int | None = None) -> bool:
    return abs((now if now is not None else now_ts()) - ts) <= TIME_WINDOW_SEC


def current_window(*, now: int | None = None) -> int:
    return (now if now is not None else now_ts()) // TIME_WINDOW_SEC


def challenge_for(window: int, salt: str) -> str:
    return crypto.hmac_sha256_hex(salt, f"challenge:{window}")[:32]


def window_is_fresh(window: int, *, now: int | None = None) -> bool:
    """接受当前窗与上一窗，避免玩家在边界上被卡。"""
    cur = current_window(now=now)
    return window in (cur, cur - 1)


# ---------------------------------------------------------------- 各关

def handshake(ledger: Ledger, *, ts: int, client: str, nonce: str, sig: str) -> str:
    """G4：验签通过后下发 S4（用 K4 加密）。"""
    if not crypto.verify(ledger.k4, sig, ts, client, nonce):
        raise SignatureError
    return crypto.encrypt(ledger.k4, ledger.shards[4])


def attest(ledger: Ledger, *, ts: int, client: str, nonce: str, sig: str) -> str:
    """G5：验签通过后下发一段密文，真碎片藏在第 17 位之后。"""
    if not crypto.verify(ledger.k4, sig, ts, client, nonce):
        raise SignatureError
    payload = f"{DECOY_5}|{ledger.shards[5]}|{TAIL_5}"
    return crypto.encrypt(ledger.k4, payload)


def notarize(
    ledger: Ledger, *, ts: int, client: str, sig: str, user_agent: str
) -> str:
    """G7：UA 硬门。浏览器改不了 User-Agent，只能靠 Node / curl。"""
    if not user_agent.startswith(REQUIRED_UA):
        raise ClientNotAuthorizedError
    if not crypto.verify(ledger.k6, sig, ts, client):
        raise SignatureError
    return crypto.encrypt(ledger.k6, ledger.shards[7])


def terminal(
    ledger: Ledger,
    blob: str,
    *,
    ts: int,
    window: int,
    nonce: int,
    client: str,
    sig: str,
    pow_bits: int,
) -> str:
    """G8：验 PoW + 验签 → 交出终章密文。服务器不知道 K，也不知道答案。"""
    if not window_is_fresh(window):
        raise SignatureError
    challenge = challenge_for(window, ledger.salt)
    if not crypto.check_pow(challenge, nonce, pow_bits):
        raise ProofOfWorkError
    if not crypto.verify(ledger.k8, sig, ts, window, nonce):
        raise SignatureError
    return blob


# ---------------------------------------------------------------- 异常

class ReversingError(Exception):
    """带 HTTP 状态码与对外文案的领域异常。"""

    status = 400
    message = "请求格式不合法"


class SignatureError(ReversingError):
    status = 401
    message = "凭据校验失败"


class ClientNotAuthorizedError(ReversingError):
    status = 403
    message = "客户端未被授权"


class ProofOfWorkError(ReversingError):
    status = 401
    message = "凭据校验失败"
