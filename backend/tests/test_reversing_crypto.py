"""前后端密码学一致性。

这些向量由 public/reversing/js/hb-crypto.js 生成（见 .tool/reversing-check/vectors.mjs）。
如果哪天有人改了 JS 侧的实现而没同步 Python，这里会红。
"""
from __future__ import annotations

import pytest

from rt_backend.reversing import crypto

KEY = "37d11fcfcc5edae71659d47c822960cfc3c2bfa12668a2707bea5f67b118597f"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
        (
            "hb:shard:0:0bs3rv3r-4w4k3",
            "23e6a2414b3cfcb6199c71bf319d915f526122cc250530725c8ec12bd7a98e17",
        ),
        (
            "a" * 56,  # padding 边界
            "b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a",
        ),
        (
            "中文 🎯",  # 多字节 + 代理对
            "12eac4a3a6d35513ed8c89041ac0e6415e8c6c9554a89796961201d171b5eb46",
        ),
    ],
)
def test_sha256_matches_js(text: str, expected: str) -> None:
    assert crypto.sha256_hex(text) == expected


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("", "92f82a499882b4bd5ccc6a2e9f93f1691ce5b07bb2688bedf0349f2a89529220"),
        ("HB0", "35dcf1bcbab09d602ca1d57b87bf13451cf3de49a76aa100f7b3e7851f16660e"),
        (
            "1758000000|hb-web/1.0|deadbeefdeadbeef",
            "89e3eca208463fd11653362500499916b5bf26d01f2e82879e6495ff29769312",
        ),
        ("中文消息 🎯", "a5adf01106aeaba78dd67c8bf6f2b91e843baa97b492367e5fc7b709cb0ed3f5"),
    ],
)
def test_hmac_matches_js(msg: str, expected: str) -> None:
    assert crypto.hmac_sha256_hex(KEY, msg) == expected


@pytest.mark.parametrize(
    "text,expected_ct",
    [
        ("", ""),
        # 刻意不用真实答案做向量——答案不进仓库，见 .tool/reversing-audit/audit.sh
        ("hb-vector-1", "5dbedccadfd3e90f5e8ce4"),
        ("a" * 40, "54bd90dddbd1fc014dc0b41ae6de72247d92bf28c60bc06196d286e47e77076fa9dc94bdfa58b2c1"),
        ("中文字符串 🎯", "d1645c5a2c3778cdbb4679dd6307a165ec6c50e6"),
    ],
)
def test_stream_cipher_matches_js(text: str, expected_ct: str) -> None:
    assert crypto.encrypt(KEY, text) == expected_ct
    assert crypto.decrypt(KEY, expected_ct) == text


def test_derive_k4_matches_js() -> None:
    assert (
        crypto.derive_k4("a" * 16, "b" * 16, "c" * 16, "d" * 16)
        == "77cbc55b06a638f8c9751999d670e78a9d5bc7ae4b7c072ef0b2906b3717468e"
    )


def test_derive_k_is_plain_concatenation() -> None:
    shards = [f"{i:016x}" for i in range(8)]
    assert crypto.derive_k(shards) == crypto.sha256_hex("".join(shards))


def test_keystream_is_deterministic_and_extends() -> None:
    short = crypto.keystream(KEY, 16)
    long = crypto.keystream(KEY, 64)
    assert long[:16] == short
    assert len(crypto.keystream(KEY, 33)) == 33


def test_sign_rejects_reordered_parts() -> None:
    """签名对象是拼接字符串，段序必须参与校验。"""
    sig = crypto.sign(KEY, 1758000000, "hb-web/1.0", "deadbeefdeadbeef")
    assert crypto.verify(KEY, sig, 1758000000, "hb-web/1.0", "deadbeefdeadbeef")
    assert not crypto.verify(KEY, sig, "hb-web/1.0", 1758000000, "deadbeefdeadbeef")


@pytest.mark.parametrize(
    "digest,bits",
    [
        ("0000ffff", 16),
        ("000fffff", 12),
        ("7fffffff", 1),  # 0b0111 —— 头一个 nibble 有 1 位前导零
        ("00000000", 32),
        ("1fffffff", 3),
        ("ffffffff", 0),
    ],
)
def test_leading_zero_bits(digest: str, bits: int) -> None:
    assert crypto.leading_zero_bits(digest) == bits


def test_check_pow() -> None:
    challenge = "abcd1234"
    found = next(n for n in range(100000) if crypto.check_pow(challenge, n, 8))
    assert crypto.check_pow(challenge, found, 8)
    assert not crypto.check_pow(challenge, found, 40)
