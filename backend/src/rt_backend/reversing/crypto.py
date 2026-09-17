"""reversing 密码学原语。

必须与 public/reversing/js/hb-crypto.js 逐字节一致。
两边的一致性由 backend/tests/test_reversing_crypto.py 里的固定向量守住。
契约见 docs/reversing-protocol.md §1
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Iterable

BLOCK_LABEL = "HB"


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hmac_sha256_hex(key_hex: str, msg: str) -> str:
    """key_hex 是 hex 字符串，按 ASCII 字节解释；msg 按 UTF-8。"""
    return hmac.new(
        key_hex.encode("ascii"), msg.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def keystream(key_hex: str, length: int) -> bytes:
    """HMAC-SHA256(key, "HB" + i) 逐块拼接，取前 length 字节。"""
    key = key_hex.encode("ascii")
    out = bytearray()
    i = 0
    while len(out) < length:
        out += hmac.new(key, f"{BLOCK_LABEL}{i}".encode("utf-8"), hashlib.sha256).digest()
        i += 1
    return bytes(out[:length])


def encrypt(key_hex: str, text: str) -> str:
    plain = text.encode("utf-8")
    stream = keystream(key_hex, len(plain))
    return bytes(a ^ b for a, b in zip(plain, stream)).hex()


def decrypt(key_hex: str, hex_cipher: str) -> str:
    cipher = bytes.fromhex(hex_cipher)
    stream = keystream(key_hex, len(cipher))
    return bytes(a ^ b for a, b in zip(cipher, stream)).decode("utf-8")


# ---------------------------------------------------------------- 派生

def derive_k4(s0: str, s1: str, s2: str, s3: str) -> str:
    return sha256_hex(s0 + s1 + s2 + s3)


def derive_k6(s6: str) -> str:
    return sha256_hex(s6)


def derive_k8(s7: str) -> str:
    return sha256_hex(s7)


def derive_k(shards: Iterable[str]) -> str:
    return sha256_hex("".join(shards))


# ---------------------------------------------------------------- 签名

def sign(key_hex: str, *parts: object) -> str:
    """契约 §3：签名对象是显式字符串拼接，绝不是 JSON 原文。"""
    return hmac_sha256_hex(key_hex, "|".join(str(p) for p in parts))


def verify(key_hex: str, sig: str, *parts: object) -> bool:
    return hmac.compare_digest(sign(key_hex, *parts), sig)


# ---------------------------------------------------------------- PoW

def leading_zero_bits(digest_hex: str) -> int:
    """十六进制摘要开头连续为 0 的比特数。"""
    bits = 0
    for ch in digest_hex:
        nibble = int(ch, 16)
        if nibble == 0:
            bits += 4
            continue
        if nibble < 0b10:
            bits += 3
        elif nibble < 0b100:
            bits += 2
        elif nibble < 0b1000:
            bits += 1
        break
    return bits


def check_pow(challenge: str, nonce: int, bits: int) -> bool:
    return leading_zero_bits(sha256_hex(f"{challenge}:{nonce}")) >= bits
