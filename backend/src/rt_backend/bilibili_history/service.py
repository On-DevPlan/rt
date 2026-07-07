"""Bilibili history-fetching service.

Talks to https://api.bilibili.com/x/web-interface/history/cursor with the
user's SESSDATA cookie. The endpoint uses cursor-based pagination
(`max` + `view_at` + `business`); we loop until the items are older than the
requested cutoff, or `max_pages` is reached.
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import httpx

from ..core.http import HttpClientHolder
from .schemas import HistoryItem

HISTORY_URL = "https://api.bilibili.com/x/web-interface/history/cursor"
PAGE_SIZE = 30  # B 站单页最大
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"


class BilibiliHistoryError(Exception):
    """Base error for the bilibili history module."""


class AuthError(BilibiliHistoryError):
    """SESSDATA invalid or missing (-101)."""


class FetchError(BilibiliHistoryError):
    """Network / non-200 / malformed payload."""


def _build_cookie_header(sessdata: str, extra: Optional[str]) -> str:
    """Build a Cookie header from SESSDATA + optional extra cookies string."""
    parts = [f"SESSDATA={sessdata}"]
    if extra:
        # 允许前端直接传整段 cookie：去掉可能的 "Cookie: " 前缀
        cleaned = extra.strip()
        if cleaned.lower().startswith("cookie:"):
            cleaned = cleaned.split(":", 1)[1].strip()
        # 用 ; 拆分，丢掉空段
        for kv in cleaned.split(";"):
            kv = kv.strip()
            if kv and "SESSDATA=" not in kv.upper():
                parts.append(kv)
    return "; ".join(parts)


def _item_from_raw(raw: dict) -> HistoryItem:
    """Map the B 站 `list[i]` payload to our normalized `HistoryItem`."""
    hist = raw.get("history") or {}
    view_at = int(raw.get("view_at", 0))
    view_at_iso = datetime.fromtimestamp(view_at, tz=timezone.utc) if view_at else datetime.fromtimestamp(0, tz=timezone.utc)
    return HistoryItem(
        title=raw.get("title", ""),
        cover=raw.get("cover") or None,
        bvid=hist.get("bvid") or None,
        aid=hist.get("oid") if hist.get("business") == "archive" else None,
        cid=hist.get("cid") or None,
        author_name=raw.get("author_name") or None,
        author_mid=raw.get("author_mid") or None,
        view_at=view_at,
        view_at_iso=view_at_iso,
        progress=int(raw.get("progress", 0) or 0),
        duration=int(raw.get("duration", 0) or 0),
        business=hist.get("business", raw.get("business", "")),
        tag_name=raw.get("tag_name") or None,
        show_title=raw.get("show_title") or None,
        kid=raw.get("kid") or None,
        dt=hist.get("dt"),
        is_fav=int(raw.get("is_fav", 0) or 0),
    )


async def _fetch_one_page(
    http: HttpClientHolder,
    cookie_header: str,
    business: str,
    cursor_max: int,
    cursor_view_at: int,
    cursor_business: str,
) -> dict:
    """Hit the B 站 history API once. Returns the parsed `data` object.

    Raises:
        AuthError: code == -101 (未登录)
        FetchError: network error or unexpected response
    """
    client = http.client
    if client is None:
        raise FetchError("HTTP client 未初始化")

    params: dict = {
        "ps": PAGE_SIZE,
        "type": business,
    }
    # 只有当 cursor 真正有值时再加（首次 max=0, view_at=0, business 空）
    if cursor_max:
        params["max"] = cursor_max
    if cursor_view_at:
        params["view_at"] = cursor_view_at
    if cursor_business:
        params["business"] = cursor_business

    try:
        r = await client.get(
            HISTORY_URL,
            params=params,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": REFERER,
                "Cookie": cookie_header,
            },
        )
    except httpx.HTTPError as e:
        raise FetchError(f"网络错误：{e}") from e

    if r.status_code != 200:
        raise FetchError(f"HTTP {r.status_code}")

    try:
        payload = r.json()
    except ValueError as e:
        raise FetchError(f"返回非 JSON：{e}") from e

    code = payload.get("code")
    if code == -101:
        raise AuthError("SESSDATA 无效或已过期（-101）")
    if code != 0:
        raise FetchError(
            f"B 站返回错误：code={code}, message={payload.get('message')}"
        )

    return payload.get("data") or {}


async def fetch_recent_history(
    http: HttpClientHolder,
    sessdata: str,
    extra_cookies: Optional[str],
    days: int,
    business: str,
    max_pages: int,
) -> Tuple[List[HistoryItem], int]:
    """Fetch all history items newer than `now - days*86400` seconds.

    Returns (items_sorted_desc, pages_used). The list is sorted by `view_at`
    descending (most recent first), already trimmed to the cutoff.
    """
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    since_ts = now_ts - days * 86400

    cookie_header = _build_cookie_header(sessdata, extra_cookies)

    cursor_max = 0
    cursor_view_at = 0
    cursor_business = ""

    collected: List[HistoryItem] = []
    pages_used = 0
    seen_keys: set = set()  # (view_at, bvid/oid) 去重

    for _ in range(max_pages):
        pages_used += 1
        data = await _fetch_one_page(
            http,
            cookie_header,
            business,
            cursor_max,
            cursor_view_at,
            cursor_business,
        )

        items = data.get("list") or []
        cursor = data.get("cursor") or {}

        if not items:
            break

        for raw in items:
            view_at = int(raw.get("view_at", 0))
            item = _item_from_raw(raw)
            if view_at < since_ts:
                # 已经穿越到旧数据，停止收这一页剩下的
                collected.append(item)
                continue
            # 用 (view_at, bvid/oid) 去重，防止 cursor 边界重复
            key = (item.view_at, item.bvid or item.aid or item.kid, item.title)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            collected.append(item)

        # 推进 cursor
        next_max = int(cursor.get("max", 0) or 0)
        next_view_at = int(cursor.get("view_at", 0) or 0)
        next_business = cursor.get("business") or ""
        if (
            next_view_at == cursor_view_at
            and next_max == cursor_max
            and next_business == cursor_business
        ):
            # B 站不再返回更老的数据，停止
            break
        if next_view_at and next_view_at < since_ts:
            # 下一页全部 < 截止时间，可以提前收工（不再请求）
            break
        cursor_max, cursor_view_at, cursor_business = next_max, next_view_at, next_business

    # 按 view_at 降序
    collected.sort(key=lambda x: x.view_at, reverse=True)
    # 最终裁剪到截止时间（含边界）
    collected = [it for it in collected if it.view_at >= since_ts]
    return collected, pages_used
