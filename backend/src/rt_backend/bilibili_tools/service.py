"""Bilibili tools core logic.

Extracted from ``.claude/repo/BilibiliTools``（requests 脚本集）并改写为
httpx.AsyncClient 版本：

- 收藏夹视频枚举（原 ``BilibiliGetFavorite/BiliFavDownLd.py`` 的现代化：
  原 /x/space/fav/arc ps=1 逐页 → 现 /x/v3/fav/resource/list ps=20 分页，
  media_id 为完整 mlid = fid×100 + 创建者 mid 尾号 2 位，
  字段参照 bilibili-API-collect/docs/fav/list.md）
- 批量添加收藏（原 ``BiliBiliAddFavorite/AutoAddFav.py``：
  /x/v2/fav/video/add + csrf，原脚本带结果码表）
- 音频区：歌曲信息 / 播放 CDN（原 ``BilibiliAudioGet.py`` 的 songDownloader）
- 音频区：歌单 / UP 主上传歌曲列表（原 playlistDownloader / userDownloader）

原脚本中「下载到本地文件」的部分（you-get / aria2 / os.system）不在 API 范围：
接口返回元数据与 CDN 直链，下载动作交给调用方。
"""
from typing import Any

import asyncio

import httpx

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BilibiliToolsError(Exception):
    """Base error for the bilibili_tools module."""


class AuthError(BilibiliToolsError):
    """登录态 / csrf 问题（code -101 / -111）。"""


class PrivateFolderError(BilibiliToolsError):
    """收藏夹未公开 / 访问权限不足（code 11004 / 11010 / 53013 / -403）。"""


class UpstreamError(BilibiliToolsError):
    """B 站接口返回异常。"""


_PRIVATE_FAV_CODES = {11004, 11010, 53013}


def _check_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """统一处理 B 站 code envelope，返回 data。"""
    code = payload.get("code")
    if code == 0:
        return payload.get("data") or {}
    if code == -101:
        raise AuthError(f"账号未登录或 cookie 过期（code=-101）")
    if code == -111:
        raise AuthError("csrf 校验失败（code=-111）")
    if code in _PRIVATE_FAV_CODES:
        raise PrivateFolderError(f"收藏夹未公开（code={code}），请确认收藏夹已公开")
    if code == -403:
        raise PrivateFolderError("访问权限不足（code=-403），收藏夹可能未公开或需要登录")
    raise UpstreamError(f"B 站接口 code={code}: {payload.get('message')}")


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    resp = await client.get(url, params=params, headers=headers)
    resp.raise_for_status()
    return _check_envelope(resp.json())


_UA_FIREFOX = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:60.0) Gecko/20100101 Firefox/60.0"
}
_UA_CLIENT = {"User-Agent": "BilibiliClient/2.33.3", "Accept": "*/*", "Connection": "keep-alive"}

# ---------------------------------------------------------------------------
# 收藏夹枚举（BiliFavDownLd.py）
# ---------------------------------------------------------------------------

_FAV_ARC_API = "https://api.bilibili.com/x/space/fav/arc"  # 旧接口，保留给兼容场景
_FAV_RESOURCE_API = "https://api.bilibili.com/x/v3/fav/resource/list"


def fav_mlid(mid: str, fid: str) -> int:
    """收藏夹完整 mlid = 原始 fid × 100 + 创建者 mid 尾号 2 位。

    v3 接口的 media_id 参数要求完整 id（bilibili-API-collect/docs/fav/list.md：
    例 fid=10526220 + mid=686127 → mlid=1052622027）。
    """
    return int(fid) * 100 + int(mid) % 100


def parse_fav_link(link: str) -> tuple[str, str]:
    """从收藏夹链接解析 (mid, fid)。

    支持 ``https://space.bilibili.com/{mid}/favlist?fid={fid}`` 等形态
    （原脚本用字符串切片，这里用正则更稳）。
    """
    import re

    m_mid = re.search(r"space\.bilibili\.com/(\d+)", link)
    m_fid = re.search(r"fid=(\d+)", link)
    if not m_mid or not m_fid:
        raise ValueError(f"无法从链接解析 mid/fid：{link!r}")
    return m_mid.group(1), m_fid.group(1)


async def fetch_favorites(
    client: httpx.AsyncClient, mid: str, fid: str, limit: int = 20
) -> dict[str, Any]:
    """枚举收藏夹内容（v3 接口，ps≤20 分页，按 has_more 停止）。

    字段对齐原脚本的 aid/title/pic/state 语义：state 用 medias[].attr 的
    bit0（1=已失效视频）；额外补充 bvid 与收藏夹标题。
    """
    items: list[dict[str, Any]] = []
    fav_title = ""
    pn = 1
    while len(items) < limit:
        data = await _get_json(
            client,
            _FAV_RESOURCE_API,
            params={
                "media_id": fav_mlid(mid, fid),
                "pn": pn,
                "ps": min(20, limit - len(items)),
                "platform": "web",
            },
            headers=_UA_FIREFOX,
        )
        info = data.get("info") or {}
        fav_title = fav_title or str(info.get("title", ""))
        medias = data.get("medias") or []
        if not medias:
            break
        for m in medias:
            attr = m.get("attr") or 0
            items.append(
                {
                    "aid": str(m.get("id", "")),
                    "bvid": m.get("bvid", ""),
                    "title": str(m.get("title", "")),
                    "pic": str(m.get("cover", "")),
                    "state": 1 if attr & 0x1 else 0,  # bit0=1 已失效
                }
            )
            if len(items) >= limit:
                break
        if not data.get("has_more"):
            break
        pn += 1
    return {
        "mid": mid,
        "fid": fid,
        "fav_title": fav_title,
        "total": len(items),
        "items": items,
    }


# ---------------------------------------------------------------------------
# 批量添加收藏（AutoAddFav.py，含结果码表）
# ---------------------------------------------------------------------------

_FAV_ADD_API = "https://api.bilibili.com/x/v2/fav/video/add"

# 原脚本的码表：pattern 0=成功(或已收藏) 1=稿件不存在 2=限流 -1=凭证问题
_FAV_ADD_CODE_TABLE: dict[str, tuple[int, str]] = {
    "0": (0, "收藏成功"),
    "11007": (0, "你已经收藏过该视频！"),
    "11201": (0, "已经收藏过了"),
    "10003": (1, "不存在该稿件"),
    "-404": (1, "啥都木有"),
    "-503": (2, "调用速度过快"),
    "-509": (2, "请求过于频繁，请稍后再试"),
    "-111": (-1, "csrf 校验失败"),
    "-101": (-1, "账号未登录,可能是cookie过期"),
}


# 节流与限流退避（模块常量便于测试 monkeypatch；-503/-509 是 HTTP 200 envelope，
# request_with_retry 的 HTTP 状态码重试看不见它们，必须按 envelope code 重试）
_FAV_ADD_THROTTLE = 0.3
_FAV_ADD_RETRY_DELAYS = (0.5, 1.5)


async def add_favorites(
    client: httpx.AsyncClient,
    sessdata: str,
    bili_jct: str,
    fid: str,
    aids: list[str],
) -> dict[str, Any]:
    """批量把视频加入收藏夹，逐个返回结果。

    节流：相邻 aid 之间隔 _FAV_ADD_THROTTLE 秒，降低 -503/-509 触发概率；
    限流重试：envelope code -503/-509 按退避序列重试（最多 1+2 次尝试）；
    部分结果保留：单条网络错误只记 pattern=-1 条目，不丢已完成的批次。
    """
    from ..core.http import request_with_retry

    cookies = {"SESSDATA": sessdata, "bili_jct": bili_jct}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36"
        ),
        "Origin": "https://www.bilibili.com",
        "Referer": "https://www.bilibili.com/",
    }
    results: list[dict[str, Any]] = []
    for idx, aid in enumerate(aids):
        if idx:
            await asyncio.sleep(_FAV_ADD_THROTTLE)
        code = ""
        pattern = -1
        msg = ""
        ok = False
        for attempt in range(1 + len(_FAV_ADD_RETRY_DELAYS)):
            try:
                resp = await request_with_retry(
                    client,
                    "POST",
                    _FAV_ADD_API,
                    data={"aid": aid, "fid": fid, "jsonp": "jsonp", "csrf": bili_jct},
                    cookies=cookies,
                    headers=headers,
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                code, pattern, msg = "", -1, f"网络错误: {e}"
                break
            try:
                payload = resp.json()
            except Exception:
                code, pattern, msg = "", -1, "响应非 JSON"
                break
            code = str(payload.get("code"))
            pattern, msg = _FAV_ADD_CODE_TABLE.get(
                code, (-1, f"未知 code={code}: {payload.get('message')}")
            )
            if code in ("-503", "-509") and attempt < len(_FAV_ADD_RETRY_DELAYS):
                await asyncio.sleep(_FAV_ADD_RETRY_DELAYS[attempt])
                continue
            ok = pattern == 0
            break
        results.append({"aid": aid, "code": code, "ok": ok, "pattern": pattern, "message": msg})
    ok_count = sum(1 for r in results if r["ok"])
    return {"fid": fid, "requested": len(aids), "ok_count": ok_count, "results": results}


# ---------------------------------------------------------------------------
# 音频区（BilibiliAudioGet.py）
# ---------------------------------------------------------------------------

_SONG_INFO_API = "https://api.bilibili.com/audio/music-service-c/web/song/info"
_AUDIO_URL_API = "https://api.bilibili.com/audio/music-service-c/url"
_MENU_SONGS_API = "https://api.bilibili.com/audio/music-service-c/web/song/of-menu"
_UPPER_SONGS_API = "https://api.bilibili.com/audio/music-service/web/song/upper"

import re as _re

_AU_RE = _re.compile(r"au([1-9]\d*)")
_AM_RE = _re.compile(r"am([1-9]\d*)")
_SPACE_UID_RE = _re.compile(r"space\.bilibili\.com/([1-9]\d*)")


def parse_audio_sid(url: str) -> str:
    """从 ``https://www.bilibili.com/audio/au241921`` 提取 sid。"""
    m = _AU_RE.search(url)
    return m.group(1) if m else ""


def parse_menu_sid(url: str) -> str:
    """从 ``https://www.bilibili.com/audio/am76105`` 提取歌单 sid。"""
    m = _AM_RE.search(url)
    return m.group(1) if m else ""


def parse_space_uid(url: str) -> str:
    """从 ``https://space.bilibili.com/2932528/audio`` 提取 uid。"""
    m = _SPACE_UID_RE.search(url)
    return m.group(1) if m else ""


async def fetch_song_info(client: httpx.AsyncClient, sid: str, quality: int = 2) -> dict[str, Any]:
    """歌曲信息（标题/作者/歌词地址/封面）+ 播放 CDN 直链。"""
    info = await _get_json(
        client, _SONG_INFO_API, params={"sid": sid}, headers=_UA_FIREFOX
    )
    # CDN 接口用的是 BilibiliClient UA，envelope 同样是 code 0
    url_data = await _get_json(
        client,
        _AUDIO_URL_API,
        params={
            "mid": 8047632,
            "mobi_app": "iphone",
            "platform": "ios",
            "privilege": 2,
            "quality": quality,
            "songid": sid,
        },
        headers=_UA_CLIENT,
    )
    return {
        "sid": sid,
        "title": info.get("title", ""),
        "author": info.get("author", ""),
        "lyric": info.get("lyric", ""),
        "cover": info.get("cover", ""),
        "quality": quality,
        "cdns": url_data.get("cdns") or [],
    }


async def _fetch_song_list(
    client: httpx.AsyncClient,
    url: str,
    params_fn,  # Callable[[int], dict]  pn → params
    max_pages: int,
) -> tuple[list[dict[str, Any]], int, bool]:
    """歌单/UP 主歌曲的通用翻页（原脚本按 pageCount==curPage 停止）。

    返回 (songs, page_count 上游总页数, truncated 是否因 max_pages 截断)——
    截断必须可感知，否则调用方会把残缺列表当全量。
    """
    songs: list[dict[str, Any]] = []
    page_count = 1
    truncated = False
    for pn in range(1, max_pages + 1):
        data = await _get_json(client, url, params=params_fn(pn), headers=_UA_FIREFOX)
        # envelope 的 data 即 {"data": [rows], "pageCount": .., "curPage": ..}
        rows = data.get("data") or []
        if not rows:
            break
        for song in rows:
            songs.append(
                {
                    "sid": str(song.get("id", "")),
                    "title": song.get("title", ""),
                    "author": song.get("author") or song.get("uname", ""),
                    "lyric": song.get("lyric", ""),
                    "cover": song.get("cover", ""),
                }
            )
        page_count = int(data.get("pageCount") or 1)
        if data.get("pageCount") == data.get("curPage"):
            break
    else:
        truncated = page_count > max_pages  # 翻满 max_pages 仍未到最后一页
    return songs, page_count, truncated


async def fetch_menu_songs(
    client: httpx.AsyncClient, sid: str, max_pages: int = 3
) -> dict[str, Any]:
    """歌单（am{id}）内全部歌曲。"""
    songs, page_count, truncated = await _fetch_song_list(
        client, _MENU_SONGS_API, lambda pn: {"ps": 100, "sid": sid, "pn": pn}, max_pages
    )
    return {
        "menu_sid": sid,
        "total": len(songs),
        "page_count": page_count,
        "truncated": truncated,
        "items": songs,
    }


async def fetch_user_songs(
    client: httpx.AsyncClient, uid: str, order: int = 1, max_pages: int = 3
) -> dict[str, Any]:
    """UP 主上传的歌曲列表。"""
    songs, page_count, truncated = await _fetch_song_list(
        client, _UPPER_SONGS_API, lambda pn: {"ps": 30, "uid": uid, "order": order, "pn": pn}, max_pages
    )
    return {
        "uid": uid,
        "total": len(songs),
        "page_count": page_count,
        "truncated": truncated,
        "items": songs,
    }
