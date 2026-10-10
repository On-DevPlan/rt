"""MediaCrawler core capability, scoped for a no-browser Web API.

Extracted from ``.claude/repo/MediaCrawler``（Playwright 多平台爬虫）。

范围决策（详见 docs/crawler-webapi-migration.md）：
- MediaCrawler 的完整链路 = Playwright 登录（扫码/cookie）+ 平台 client + 存储。
  重量级且强登录依赖，不适合直接进 rt 后端（无浏览器、无登录会话托管）。
- 本模块只包装**免登录可用的核心能力**：B 站关键词搜索视频
  （``media_platform/bilibili/client.py: search_video_by_keyword``，
  /x/web-interface/wbi/search/type + WBI 签名——签名算法复用 bilibili_crawler 模块）。
- 其余平台（xhs/douyin/kuaishou/weibo/tieba/zhihu）需浏览器登录态，通过
  ``/platforms`` 能力端点说明现状，请求时返回 501。
"""
import re
from typing import Any

import httpx

from ..bilibili_crawler.service import (
    AuthError,
    RiskControlError,
    UpstreamError,
    invalidate_wbi_keys,
    sign_params,
)

_SEARCH_API = "https://api.bilibili.com/x/web-interface/wbi/search/type"

# 对齐 MediaCrawler media_platform/bilibili/field.py: SearchOrderType
SEARCH_ORDERS: dict[str, str] = {
    "default": "",  # 综合排序
    "click": "click",  # 最多点击
    "pubdate": "pubdate",  # 最新发布
    "dm": "dm",  # 弹幕最多
    "stow": "stow",  # 最多收藏
}

# 对齐 MediaCrawler 支持的平台与其依赖（config/base_config.py PLATFORM 列表 +
# 各 media_platform/* 的登录方式），用于 /platforms 能力端点。
PLATFORMS: list[dict[str, Any]] = [
    {"name": "bilibili", "login_required": False, "playwright_required": False, "wrapped": True,
     "note": "关键词搜索已包装为 POST /search；免登录可用，带 SESSDATA 更稳"},
    {"name": "xhs", "login_required": True, "playwright_required": True, "wrapped": False,
     "note": "需扫码/cookie 登录 + 浏览器签名，未进 API"},
    {"name": "douyin", "login_required": True, "playwright_required": True, "wrapped": False,
     "note": "需扫码/cookie 登录 + 浏览器签名，未进 API"},
    {"name": "kuaishou", "login_required": True, "playwright_required": True, "wrapped": False,
     "note": "需登录态，未进 API"},
    {"name": "weibo", "login_required": True, "playwright_required": True, "wrapped": False,
     "note": "需登录态，未进 API"},
    {"name": "tieba", "login_required": True, "playwright_required": True, "wrapped": False,
     "note": "需登录态，未进 API"},
    {"name": "zhihu", "login_required": True, "playwright_required": True, "wrapped": False,
     "note": "需登录态，未进 API"},
]

_EM_TAG_RE = re.compile(r"</?em[^>]*>")


class PlatformNotWrappedError(Exception):
    """平台需要浏览器登录态，本 API 未包装。"""


def _strip_highlight(title: str) -> str:
    """搜索结果的标题带 <em class="keyword"> 高亮标签，剥掉。"""
    return _EM_TAG_RE.sub("", title)


async def search_bilibili_videos(
    client: httpx.AsyncClient,
    keyword: str,
    page: int = 1,
    page_size: int = 20,
    order: str = "default",
    pubtime_begin_s: int = 0,
    pubtime_end_s: int = 0,
    sessdata: str | None = None,
) -> dict[str, Any]:
    """B 站关键词搜索视频（对齐 MediaCrawler search_video_by_keyword）。

    与 MediaCrawler 的差异：不用 Playwright 取 cookie，改为可选传入 SESSDATA；
    WBI 签名实时取 key（复用 bilibili_crawler 模块）。
    """
    if order not in SEARCH_ORDERS:
        raise ValueError(f"order 必须是 {sorted(SEARCH_ORDERS)} 之一")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
    }
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"

    params = {
        "search_type": "video",
        "keyword": keyword,
        "page": page,
        "page_size": page_size,
        "order": SEARCH_ORDERS[order],
        "pubtime_begin_s": pubtime_begin_s,
        "pubtime_end_s": pubtime_end_s,
    }
    signed = await sign_params(client, params)
    resp = await client.get(_SEARCH_API, params=signed, headers=headers)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") == -412:
        # 风控：key 可能已轮转，失效缓存换新 key 重试一次（对齐 bilibili_crawler._signed_get_json）
        invalidate_wbi_keys(client)
        signed = await sign_params(client, params)
        resp = await client.get(_SEARCH_API, params=signed, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    code = payload.get("code")
    if code == -101:
        raise AuthError(f"登录态失效（code=-101）：{payload.get('message')}")
    if code in (-352, -403, -412):
        raise RiskControlError(f"B 站风控拦截（code={code}）：{payload.get('message')}")
    if code != 0:
        raise UpstreamError(f"B 站接口 code={code}: {payload.get('message')}")

    data = payload.get("data") or {}
    items: list[dict[str, Any]] = []
    for block in data.get("result") or []:
        if block.get("result_type") != "video":
            continue
        for row in block.get("data") or []:
            items.append(
                {
                    "aid": row.get("aid"),
                    "bvid": row.get("bvid", ""),
                    "title": _strip_highlight(row.get("title", "")),
                    "author": row.get("author", ""),
                    "mid": row.get("mid"),
                    "play": row.get("play"),
                    "danmaku": row.get("video_review") if row.get("video_review") else row.get("danmaku"),
                    "favorites": row.get("favorites"),
                    "tag": row.get("tag", ""),
                    "pubdate": row.get("pubdate"),
                    "description": row.get("description", ""),
                    "pic": row.get("pic", ""),
                }
            )
    return {"keyword": keyword, "page": page, "num_results": data.get("numResults"), "items": items}
