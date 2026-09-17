"""reversing 端点契约测试。契约见 docs/reversing-protocol.md §4"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.core.config import Settings
from rt_backend.reversing import crypto, service
from rt_backend.reversing.router import build_router

PREFIX = "/api/reversing/v1"
WEB = "hb-web/1.0"
NODE = "hb-node/1.0"
NONCE = "deadbeefdeadbeef"


@pytest.fixture
def ledger() -> service.Ledger:
    return service.load_ledger()


@pytest.fixture
def settings() -> Settings:
    return Settings(reversing_pow_bits=4)  # 测试里用低难度，别烧 CPU


@pytest.fixture
def api(settings: Settings):
    app = FastAPI()
    app.include_router(build_router(settings))
    with TestClient(app) as client:
        yield client


def now() -> int:
    return int(time.time())


# ---------------------------------------------------------------- challenge

def test_challenge_is_stateless_and_derived_from_window(api, ledger) -> None:
    body = api.get(f"{PREFIX}/challenge").json()
    assert len(body["challenge"]) == 32
    assert body["bits"] == 4
    assert body["challenge"] == service.challenge_for(body["window"], ledger.salt)


def test_challenge_is_stable_within_a_window(api) -> None:
    a = api.get(f"{PREFIX}/challenge").json()
    b = api.get(f"{PREFIX}/challenge").json()
    assert a == b


# ---------------------------------------------------------------- handshake (G4)

def test_handshake_rejects_bad_signature(api) -> None:
    r = api.post(
        f"{PREFIX}/handshake",
        json={"ts": now(), "client": WEB, "nonce": NONCE, "sig": "0" * 64},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == 401
    assert body["msg"] == "凭据校验失败"
    assert len(body["trace_id"]) == 12
    # 不能透露任何方向
    assert "shard" not in r.text and "key" not in r.text.lower()


def test_handshake_accepts_correct_signature_and_yields_s4(api, ledger) -> None:
    ts = now()
    sig = crypto.sign(ledger.k4, ts, WEB, NONCE)
    r = api.post(
        f"{PREFIX}/handshake",
        json={"ts": ts, "client": WEB, "nonce": NONCE, "sig": sig},
    )
    assert r.status_code == 200
    assert crypto.decrypt(ledger.k4, r.json()["ct"]) == ledger.shards[4]


def test_handshake_rejects_stale_timestamp(api, ledger) -> None:
    ts = now() - 600
    sig = crypto.sign(ledger.k4, ts, WEB, NONCE)  # 签名本身是对的
    r = api.post(
        f"{PREFIX}/handshake",
        json={"ts": ts, "client": WEB, "nonce": NONCE, "sig": sig},
    )
    assert r.status_code == 401


def test_handshake_signature_binds_all_three_parts(api, ledger) -> None:
    """签名拼接若少一段或多一段，都必须失败。"""
    ts = now()
    loose = crypto.sign(ledger.k4, ts, WEB)  # 漏掉 nonce
    r = api.post(
        f"{PREFIX}/handshake",
        json={"ts": ts, "client": WEB, "nonce": NONCE, "sig": loose},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------- attest (G5)

def test_attest_hides_shard5_behind_a_decoy(api, ledger) -> None:
    ts = now()
    sig = crypto.sign(ledger.k4, ts, WEB, NONCE)
    r = api.post(
        f"{PREFIX}/attest",
        json={"ts": ts, "client": WEB, "nonce": NONCE, "sig": sig},
    )
    assert r.status_code == 200

    plain = crypto.decrypt(ledger.k4, r.json()["ct"])
    parts = plain.split("|")
    # 站点只消费前 16 位（诱饵），真碎片在第二段
    assert parts[0] == service.DECOY_5
    assert parts[1] == ledger.shards[5]
    assert parts[1] not in parts[0]


def test_attest_needs_the_same_key_as_handshake(api) -> None:
    ts = now()
    r = api.post(
        f"{PREFIX}/attest",
        json={"ts": ts, "client": WEB, "nonce": NONCE, "sig": "f" * 64},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------- notarize (G7)

def test_notarize_rejects_browser_user_agent(api, ledger) -> None:
    """浏览器改不了 User-Agent —— 这是本关的墙。"""
    ts = now()
    sig = crypto.sign(ledger.k6, ts, NODE)
    r = api.post(
        f"{PREFIX}/notarize",
        json={"ts": ts, "client": NODE, "sig": sig},
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
        },
    )
    assert r.status_code == 403
    assert r.json()["msg"] == "客户端未被授权"


def test_notarize_accepts_required_ua_and_yields_s7(api, ledger) -> None:
    ts = now()
    sig = crypto.sign(ledger.k6, ts, NODE)
    r = api.post(
        f"{PREFIX}/notarize",
        json={"ts": ts, "client": NODE, "sig": sig},
        headers={"User-Agent": f"{service.REQUIRED_UA} (node v20)"},
    )
    assert r.status_code == 200
    assert crypto.decrypt(ledger.k6, r.json()["ct"]) == ledger.shards[7]


def test_notarize_still_checks_signature(api) -> None:
    ts = now()
    r = api.post(
        f"{PREFIX}/notarize",
        json={"ts": ts, "client": NODE, "sig": "0" * 64},
        headers={"User-Agent": service.REQUIRED_UA},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------- terminal (G8)

def solve_pow(challenge: str, bits: int) -> int:
    n = 0
    while not crypto.check_pow(challenge, n, bits):
        n += 1
    return n


def test_terminal_full_protocol(api, ledger) -> None:
    ch = api.get(f"{PREFIX}/challenge").json()
    nonce = solve_pow(ch["challenge"], ch["bits"])
    ts = now()
    sig = crypto.sign(ledger.k8, ts, ch["window"], nonce)

    r = api.post(
        f"{PREFIX}/terminal",
        json={
            "ts": ts,
            "window": ch["window"],
            "nonce": nonce,
            "client": NODE,
            "sig": sig,
        },
    )
    assert r.status_code == 200

    # 终章密文：服务器不知道 K，但玩家用 8 个碎片拼出来就能解开
    k = crypto.derive_k(ledger.shards[n] for n in range(8))
    answer = crypto.decrypt(k, r.json()["ct"])
    assert answer == crypto.decrypt(k, service.load_blob())
    assert answer.isdigit() and len(answer) >= 6


def test_terminal_rejects_bad_pow(api, ledger) -> None:
    ch = api.get(f"{PREFIX}/challenge").json()
    ts = now()
    bad = solve_pow(ch["challenge"], ch["bits"]) + 1
    while crypto.check_pow(ch["challenge"], bad, ch["bits"]):
        bad += 1
    sig = crypto.sign(ledger.k8, ts, ch["window"], bad)

    r = api.post(
        f"{PREFIX}/terminal",
        json={
            "ts": ts,
            "window": ch["window"],
            "nonce": bad,
            "client": NODE,
            "sig": sig,
        },
    )
    assert r.status_code == 401


def test_terminal_rejects_stale_window(api, ledger) -> None:
    old = service.current_window() - 50
    ts = now()
    nonce = solve_pow(service.challenge_for(old, ledger.salt), 4)
    sig = crypto.sign(ledger.k8, ts, old, nonce)
    r = api.post(
        f"{PREFIX}/terminal",
        json={"ts": ts, "window": old, "nonce": nonce, "client": NODE, "sig": sig},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------- 蜜罐

@pytest.mark.parametrize("path", ["admin", "admin/users", "admin/keys/all"])
def test_honeypot_always_403_with_fake_trace(api, path: str) -> None:
    r = api.get(f"{PREFIX}/{path}")
    assert r.status_code == 403
    body = r.json()
    assert body["msg"] == "权限不足"
    assert len(body["trace_id"]) == 12


# ---------------------------------------------------------------- 无状态

def test_server_keeps_no_session_state(api, ledger) -> None:
    """同一份签名打两次都成立；换一份也一样成立。没有会话可查。"""
    ts = now()
    sig = crypto.sign(ledger.k4, ts, WEB, NONCE)
    payload = {"ts": ts, "client": WEB, "nonce": NONCE, "sig": sig}
    first = api.post(f"{PREFIX}/handshake", json=payload).json()
    second = api.post(f"{PREFIX}/handshake", json=payload).json()
    assert first == second


def test_ledger_holds_no_plaintext_answer(ledger) -> None:
    """服务器侧只有盐、碎片和密文，没有任何明文答案。

    真正的"群号零命中"审计在 .tool/reversing-audit/audit.sh —— 那里才允许
    拿到答案原文做比对。这里只断言结构：全是 hex，没有可读文本。
    """
    blob = service.load_blob()
    assert all(len(v) == 16 and all(c in "0123456789abcdef" for c in v)
               for v in ledger.shards.values())
    assert all(c in "0123456789abcdef" for c in blob)
    assert crypto.decrypt(crypto.derive_k(ledger.shards[n] for n in range(8)), blob) != ""
