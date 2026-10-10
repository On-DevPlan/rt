"""Unit tests for bilibili_crawler service 纯函数（av/bv 互转、WBI 签名）。"""
from hashlib import md5
from urllib.parse import urlencode

import httpx
import pytest

from rt_backend.bilibili_crawler.service import (
    _MIXIN_KEY_ENC_TAB,
    av2bv,
    bv2av,
    enc_wbi,
    fetch_wbi_keys,
    get_mixin_key,
)


class TestAvBvConvert:
    """av<->bv 纯函数（bv2oid.py 移植）。"""

    def test_known_vectors(self):
        # 用 service 实现独立验证过的已知识别（见 e2e 文档）
        assert av2bv(170001) == "BV17x411w7KC"
        assert av2bv(2) == "BV1xx411c7mD"
        assert bv2av("BV17x411w7KC") == 170001
        assert bv2av("BV1xx411c7mD") == 2

    def test_roundtrip_many(self):
        for aid in (1, 2, 999, 170001, 1504733402, 2**40):
            assert bv2av(av2bv(aid)) == aid

    def test_bv2av_rejects_bad_prefix(self):
        with pytest.raises(ValueError):
            bv2av("XX1abcdefghi")


class TestWbiSign:
    """WBI 签名纯函数（b站使用wbi签名的爬取方式.py 移植）。"""

    def test_get_mixin_key_spec(self):
        # 混淆表语义：输出第 i 位 = orig[TAB[i]]，截断到 32
        orig = "".join(chr(65 + i) for i in range(64))  # 64 个不同字符
        mixin = get_mixin_key(orig)
        assert len(mixin) == 32
        assert mixin[0] == orig[_MIXIN_KEY_ENC_TAB[0]]
        assert mixin[1] == orig[_MIXIN_KEY_ENC_TAB[1]]
        assert mixin[31] == orig[_MIXIN_KEY_ENC_TAB[31]]

    def test_enc_wbi_structure_and_filter(self, monkeypatch):
        monkeypatch.setattr("rt_backend.bilibili_crawler.service.time.time", lambda: 1700000000)
        img_key, sub_key = "k" * 32, "s" * 32
        signed = enc_wbi({"z": 1, "a": "x!y*z", "b": "普通(文本)"}, img_key, sub_key)

        assert signed["wts"] == "1700000000"  # 与原脚本一致：值统一 str(v)
        # "!'()*" 被过滤
        assert signed["a"] == "xyz"
        assert "(" not in signed["b"]
        # w_rid = md5(urlencode(排序后过滤值) + mixin_key)
        expected_params = {
            "a": "xyz",
            "b": "普通文本",
            "wts": "1700000000",
            "z": "1",
        }
        query = urlencode(expected_params)
        expected_rid = md5((query + get_mixin_key(img_key + sub_key)).encode()).hexdigest()
        assert signed["w_rid"] == expected_rid

    @pytest.mark.asyncio
    async def test_fetch_wbi_keys_parses_urls(self):
        nav_payload = {
            "code": 0,
            "data": {
                "wbi_img": {
                    "img_url": "https://i0.hdslb.com/bfs/wbi/aaaa1111.png",
                    "sub_url": "https://i0.hdslb.com/bfs/wbi/bbbb2222.png",
                }
            },
        }

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/x/web-interface/nav"
            return httpx.Response(200, json=nav_payload)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            img_key, sub_key = await fetch_wbi_keys(client)
        finally:
            await client.aclose()
        assert img_key == "aaaa1111"
        assert sub_key == "bbbb2222"


class TestWbiKeyCache:
    """WBI key 缓存（1 小时 TTL，同一 client 实例内复用）。"""

    @pytest.fixture(autouse=True)
    def clear_wbi_cache(self, monkeypatch):
        """每个测试前清空缓存，避免跨测试污染。"""
        monkeypatch.setattr("rt_backend.bilibili_crawler.service._wbi_cache", {})

    def _nav_response(self, img="img1", sub="sub1"):
        return {
            "code": 0,
            "data": {
                "wbi_img": {
                    "img_url": f"https://i0.hdslb.com/bfs/wbi/{img}.png",
                    "sub_url": f"https://i0.hdslb.com/bfs/wbi/{sub}.png",
                }
            },
        }

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_second_nav_request(self):
        """同一 client 的第二次调用命中缓存，不发第二个 nav 请求。"""
        nav_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal nav_calls
            nav_calls += 1
            return httpx.Response(200, json=self._nav_response())

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            k1 = await fetch_wbi_keys(client)
            k2 = await fetch_wbi_keys(client)
            k3 = await fetch_wbi_keys(client)
        finally:
            await client.aclose()

        assert nav_calls == 1
        assert k1 == k2 == k3 == ("img1", "sub1")

    @pytest.mark.asyncio
    async def test_different_clients_each_hit_nav(self):
        """不同 client 实例各有独立缓存项，各自只发一次 nav。"""
        nav_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal nav_calls
            nav_calls += 1
            return httpx.Response(
                200, json=self._nav_response(img=f"img{nav_calls}", sub=f"sub{nav_calls}")
            )

        client1 = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client2 = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            k1 = await fetch_wbi_keys(client1)
            k2 = await fetch_wbi_keys(client2)
            # client1 第二次不重发
            k1b = await fetch_wbi_keys(client1)
        finally:
            await client1.aclose()
            await client2.aclose()

        assert nav_calls == 2
        assert k1 == ("img1", "sub1")
        assert k2 == ("img2", "sub2")
        assert k1b == ("img1", "sub1")
