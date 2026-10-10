"""Tests for the bilibili_crawler router（迁移自 Bilibili_crawler 仓库）。

上游 B 站接口用 respx 拦截，不依赖外网与真实 cookie。
"""
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from rt_backend.bilibili_crawler.router import build_router
from rt_backend.bilibili_crawler.service import av2bv, bv2av
from rt_backend.core.http import HttpClientHolder

NAV_URL = "/x/web-interface/nav"
VIEW_URL = "/x/v2/reply/main"
SUB_URL = "/x/v2/reply/reply"
SPACE_URL = "/x/polymer/web-dynamic/v1/feed/space"


def _nav_payload() -> dict:
    # 真实 wbi key 各 32 字符（混淆表索引最大到 63，短 key 会在签名时越界）
    img_key = "a" * 32
    sub_key = "b" * 32
    return {
        "code": 0,
        "message": "0",
        "data": {
            "wbi_img": {
                "img_url": f"https://i0.hdslb.com/bfs/wbi/{img_key}.png",
                "sub_url": f"https://i0.hdslb.com/bfs/wbi/{sub_key}.png",
            }
        },
    }


def _holder() -> HttpClientHolder:
    return HttpClientHolder(timeout=5.0)


@pytest.mark.asyncio
async def test_wbi_sign_success():
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(NAV_URL).mock(return_value=Response(200, json=_nav_payload()))
        with TestClient(app) as client:
            r = client.post("/api/bilibili-crawler/wbi/sign", json={"params": {"oid": 123, "type": 1}})

    assert r.status_code == 200, r.text
    body = r.json()
    # w_rid 是 32 位 hex；签名后的参数里必须带 wts/w_rid
    assert len(body["w_rid"]) == 32
    int(body["w_rid"], 16)  # 不抛异常即合法 hex
    # enc_wbi 会把参数值字符串化（与原脚本 str(v) 行为一致）
    assert int(body["signed_params"]["wts"]) == body["wts"]
    assert int(body["signed_params"]["oid"]) == 123
    assert "w_rid" in body["query"] and "wts" in body["query"]


def test_convert_av_bv_roundtrip():
    """av<->bv 纯函数：往返一致性 + 已知向量。"""
    app = FastAPI()
    app.include_router(build_router(lambda: _holder()))
    with TestClient(app) as client:
        for aid in (2, 170001, 1504733402):
            r = client.get("/api/bilibili-crawler/convert", params={"aid": aid})
            assert r.status_code == 200, r.text
            bvid = r.json()["bvid"]
            assert bvid.startswith("BV1")
            # 往返
            r2 = client.get("/api/bilibili-crawler/convert", params={"bvid": bvid})
            assert r2.status_code == 200
            assert r2.json()["aid"] == aid
        # 已知向量（Bilibili_crawler/bv2oid.py 中的样例）：解码后再编码应还原
        assert av2bv(bv2av("BV1yTLAzuEZB")) == "BV1yTLAzuEZB"


def test_convert_validation():
    app = FastAPI()
    app.include_router(build_router(lambda: _holder()))
    with TestClient(app) as client:
        # 两个都不给
        r = client.get("/api/bilibili-crawler/convert")
        assert r.status_code == 422
        # 两个都给
        r = client.get("/api/bilibili-crawler/convert", params={"aid": 2, "bvid": "BV1xx411c7mD"})
        assert r.status_code == 422
        # 非法 bvid
        r = client.get("/api/bilibili-crawler/convert", params={"bvid": "XX1xxx"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_video_info_success():
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    view_payload = {
        "code": 0,
        "data": {
            "bvid": "BV1xx411c7mD",
            "aid": 170001,
            "title": "测试视频",
            "desc": "描述",
            "owner": {"mid": 42, "name": "up主"},
            "pubdate": 1700000000,
            "duration": 300,
            "stat": {
                "view": 1000,
                "danmaku": 10,
                "reply": 20,
                "favorite": 30,
                "coin": 40,
                "share": 50,
                "like": 60,
            },
        },
    }
    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get("/x/web-interface/view").mock(return_value=Response(200, json=view_payload))
        with TestClient(app) as client:
            r = client.get("/api/bilibili-crawler/video/BV1xx411c7mD")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "测试视频"
    assert body["owner_name"] == "up主"
    assert body["view"] == 1000
    assert body["like"] == 60


def _reply(rid: str, rcount: int = 0) -> dict:
    return {
        "rpid": rid,
        "member": {
            "uname": f"用户{rid}",
            "sex": "男",
            "mid": 1000 + int(rid),
            "level_info": {"current_level": 3},
        },
        "ctime": 1700000000,
        "like": 5,
        "content": {"message": "评论内容"},
        "reply_control": {"location": "IP属地：北京"},
        "rcount": rcount,
    }


@pytest.mark.asyncio
async def test_comments_two_level_extraction():
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    page1 = {
        "code": 0,
        "data": {
            "replies": [_reply("1", rcount=2), _reply("2", rcount=0)],
            "cursor": {"is_end": False},
        },
    }
    page2 = {"code": 0, "data": {"replies": [], "cursor": {"is_end": True}}}
    sub = {"code": 0, "data": {"replies": [_reply("11"), _reply("12")], "page": {"count": 2}}}

    with respx.mock(base_url="https://api.bilibili.com") as router:
        main_route = router.get(VIEW_URL).mock(
            side_effect=[Response(200, json=page1), Response(200, json=page2)]
        )
        router.get(SUB_URL).mock(return_value=Response(200, json=sub))
        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili-crawler/comments",
                json={"oid": "1504733402", "type": 1, "pages": 2},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    first = body["items"][0]
    # 字段抽取与原脚本对齐
    assert first["name"] == "用户1"
    assert first["location"] == "北京"  # 去掉 "IP属地：" 前缀
    assert first["level"] == 3
    assert first["mid"] == "1001"
    # 楼中楼被展开
    assert len(first["replies"]) == 2
    assert body["items"][0]["replies"][0]["rpid"] == "11"
    # 第二页空 → 停止翻页（main 一共被请求 2 次）
    assert main_route.call_count == 2


@pytest.mark.asyncio
async def test_comments_auth_error_maps_401():
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(VIEW_URL).mock(
            return_value=Response(200, json={"code": -101, "message": "账号未登录", "data": None})
        )
        with TestClient(app) as client:
            r = client.post("/api/bilibili-crawler/comments", json={"oid": "123"})

    assert r.status_code == 401
    assert "-101" in r.json()["detail"]


@pytest.mark.asyncio
async def test_comments_upstream_error_maps_502():
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(VIEW_URL).mock(
            return_value=Response(200, json={"code": -404, "message": "啥都木有", "data": None})
        )
        with TestClient(app) as client:
            r = client.post("/api/bilibili-crawler/comments", json={"oid": "123"})

    assert r.status_code == 502


@pytest.mark.asyncio
async def test_user_space_offset_paging():
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    def _feed_item(cid: str, ctype: int, title: str) -> dict:
        return {
            "dyn_type": 8,
            "basic": {"comment_id_str": cid, "comment_type": ctype},
            "modules": {
                "module_dynamic": {"major": {"archive": {"title": title}}},
            },
        }

    page1 = {
        "code": 0,
        "data": {
            "items": [_feed_item("111", 1, "视频一")],
            "offset": "offset-1",
            "has_more": True,
        },
    }
    page2 = {
        "code": 0,
        "data": {
            "items": [_feed_item("222", 17, "")],
            "offset": "",
            "has_more": False,
        },
    }

    with respx.mock(base_url="https://api.bilibili.com") as router:
        space_route = router.get(SPACE_URL).mock(
            side_effect=[Response(200, json=page1), Response(200, json=page2)]
        )
        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili-crawler/user-space",
                json={"mid": "42", "max_pages": 5},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert body["items"][0]["comment_id_str"] == "111"
    assert body["items"][0]["title"] == "视频一"
    assert body["items"][1]["comment_type"] == 17
    # 第二页 has_more=False → 停止
    assert space_route.call_count == 2


# ---------------------------------------------------------------------------
# loop-2 第 1 轮补齐：置顶评论 / mode 排序 / 412 风控 / 楼中楼边界 / UP 全量投稿
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comments_pinned_dedup_and_flag():
    """置顶评论（top_replies）置入结果头部 + pinned 标记 + 与普通列表 rpid 去重。"""
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    page1 = {
        "code": 0,
        "data": {
            "top_replies": [_reply("900", rcount=1)],
            "replies": [_reply("900"), _reply("1")],  # 900 与置顶重复
            "cursor": {"is_end": True},
        },
    }
    sub = {"code": 0, "data": {"replies": [_reply("901")], "page": {"count": 1}}}

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(VIEW_URL).mock(return_value=Response(200, json=page1))
        router.get(SUB_URL).mock(return_value=Response(200, json=sub))
        with TestClient(app) as client:
            r = client.post("/api/bilibili-crawler/comments", json={"oid": "1", "pages": 1})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2  # 900(pinned) + 1，去重后不含第二个 900
    assert body["items"][0]["rpid"] == "900"
    assert body["items"][0]["pinned"] is True  # 置顶在前
    assert body["items"][1]["pinned"] is False
    assert body["items"][0]["replies"][0]["rpid"] == "901"  # 置顶的楼中楼也展开


@pytest.mark.asyncio
async def test_comments_mode_passthrough():
    """mode 排序参数透传上游。"""
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    page1 = {"code": 0, "data": {"replies": [_reply("1")], "cursor": {"is_end": True}}}
    with respx.mock(base_url="https://api.bilibili.com") as router:
        main_route = router.get(VIEW_URL).mock(return_value=Response(200, json=page1))
        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili-crawler/comments", json={"oid": "1", "mode": 2}
            )

    assert r.status_code == 200, r.text
    sent = dict(main_route.calls[0].request.url.params)
    assert sent["mode"] == "2"  # 按时间


@pytest.mark.asyncio
async def test_comments_412_risk_control_maps_502():
    """上游风控 412 → 502 + 提示文案（README「已知限制」第 1 条）。"""
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(VIEW_URL).mock(return_value=Response(412, text="blocked"))
        with TestClient(app) as client:
            r = client.post("/api/bilibili-crawler/comments", json={"oid": "1"})

    assert r.status_code == 502
    assert "风控" in r.json()["detail"]


@pytest.mark.asyncio
async def test_comments_include_replies_false_skips_sub_api():
    """include_replies=false 时不请求楼中楼接口。"""
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    page1 = {"code": 0, "data": {"replies": [_reply("1", rcount=9)], "cursor": {}}}
    # 被测行为就是「SUB 路由不被调用」，需关掉 respx 的 all-called 断言
    with respx.mock(base_url="https://api.bilibili.com", assert_all_called=False) as router:
        router.get(VIEW_URL).mock(return_value=Response(200, json=page1))
        sub_route = router.get(SUB_URL).mock(
            return_value=Response(200, json={"code": 0, "data": {"replies": [], "page": {}}})
        )
        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili-crawler/comments",
                json={"oid": "1", "include_replies": False},
            )

    assert r.status_code == 200
    assert sub_route.call_count == 0
    assert r.json()["items"][0]["replies"] == []


@pytest.mark.asyncio
async def test_comments_sub_replies_multipage():
    """楼中楼 count=45、ps=20 → ceil 后抓 3 页。"""
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    page1 = {"code": 0, "data": {"replies": [_reply("1", rcount=45)], "cursor": {}}}

    def _sub_page(pn: int) -> dict:
        rows = [_reply(str(1000 + pn * 20 + i)) for i in range(20 if pn < 3 else 5)]
        return {"code": 0, "data": {"replies": rows, "page": {"count": 45}}}

    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(VIEW_URL).mock(return_value=Response(200, json=page1))
        sub_route = router.get(SUB_URL).mock(
            side_effect=[Response(200, json=_sub_page(pn)) for pn in (1, 2, 3)]
        )
        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili-crawler/comments", json={"oid": "1", "ps": 20}
            )

    assert r.status_code == 200, r.text
    assert sub_route.call_count == 3  # ceil(45/20) = 3
    assert len(r.json()["items"][0]["replies"]) == 45


@pytest.mark.asyncio
async def test_user_videos_signed_arc_search():
    """UP 全量投稿：nav 取 key + WBI 签名的 arc/search，返回 vlist 规范化。"""
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))

    arc_payload = {
        "code": 0,
        "data": {
            "count": 88,
            "list": {
                "vlist": [
                    {
                        "aid": 170001,
                        "bvid": "BV17x411w7KC",
                        "title": "投稿一",
                        "created": 1700000000,
                        "play": 500,
                        "video_review": 12,
                        "length": "5:30",
                    }
                ]
            },
        },
    }
    with respx.mock(base_url="https://api.bilibili.com") as router:
        router.get(NAV_URL).mock(return_value=Response(200, json=_nav_payload()))
        arc_route = router.get("/x/space/wbi/arc/search").mock(
            return_value=Response(200, json=arc_payload)
        )
        with TestClient(app) as client:
            r = client.post(
                "/api/bilibili-crawler/user-videos",
                json={"mid": "42", "order": "click"},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 88
    assert body["total"] == 1
    assert body["items"][0]["bvid"] == "BV17x411w7KC"
    sent = dict(arc_route.calls[0].request.url.params)
    assert sent["w_rid"] and sent["wts"]  # 必须带 WBI 签名
    assert sent["mid"] == "42" and sent["order"] == "click"


@pytest.mark.asyncio
async def test_user_videos_invalid_order_422():
    app = FastAPI()
    holder = _holder()
    await holder.start()
    app.include_router(build_router(lambda: holder))
    with TestClient(app) as client:
        r = client.post("/api/bilibili-crawler/user-videos", json={"mid": "42", "order": "bogus"})
    assert r.status_code == 422
