"""Bilibili tools core logic.

Extracted from ``.claude/repo/BilibiliTools``（requests 脚本集）并改写为
httpx.AsyncClient 版本：

- 收藏夹视频枚举（原 ``BilibiliGetFavorite/BiliFavDownLd.py``：
  /x/space/fav/arc 逐页抓取，私有收藏夹错误码 11004/11010/53013）
- 批量添加收藏（原 ``BiliBiliAddFavorite/AutoAddFav.py``：
  /x/v2/fav/video/add + csrf，原脚本带结果码表）
- 音频区：歌曲信息 / 播放 CDN（原 ``BilibiliAudioGet.py`` 的 songDownloader）
- 音频区：歌单 / UP 主上传歌曲列表（原 playlistDownloader / userDownloader）

原脚本中「下载到本地文件」的部分（you-get / aria2 / os.system）不在 API 范围：
接口返回元数据与 CDN 直链，下载动作交给调用方。
"""
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BilibiliToolsError(Exception):
    """Base error for the bilibili_tools module."""


class AuthError(BilibiliToolsError):
    """登录态 / csrf 问题（code -101 / -111）。"""


class PrivateFolderError(BilibiliToolsError):
    """收藏夹未公开（code 11004 / 11010 / 53013）。"""


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

_FAV_ARC_API = "https://api.bilibili.com/x/space/fav/arc"


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
    """枚举公开收藏夹里的视频（aid/title/pic/state），逐页抓取（原脚本 ps=1）。"""
    items: list[dict[str, Any]] = []
    for pn in range(1, limit + 1):
        data = await _get_json(
            client,
            _FAV_ARC_API,
            params={"vmid": mid, "ps": 1, "fid": fid, "pn": pn},
            headers=_UA_FIREFOX,
        )
        archives = data.get("archives") or []
        if not archives:
            break  # 翻到头了
        arc = archives[0]
        items.append(
            {
                "aid": str(arc.get("aid", "")),
                "title": str(arc.get("title", "")),
                "pic": str(arc.get("pic", "")),
                "state": arc.get("state", 0),
            }
        )
    return {"mid": mid, "fid": fid, "total": len(items), "items": items}


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


async def add_favorites(
    client: httpx.AsyncClient,
    sessdata: str,
    bili_jct: str,
    fid: str,
    aids: list[str],
) -> dict[str, Any]:
    """批量把视频加入收藏夹，逐个返回结果。"""
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
    for aid in aids:
        resp = await client.post(
            _FAV_ADD_API,
            data={"aid": aid, "fid": fid, "jsonp": "jsonp", "csrf": bili_jct},
            cookies=cookies,
            headers=headers,
        )
        resp.raise_for_status()
        try:
            payload = resp.json()
        except Exception:
            results.append({"aid": aid, "ok": False, "pattern": -1, "message": "响应非 JSON"})
            continue
        code = str(payload.get("code"))
        pattern, msg = _FAV_ADD_CODE_TABLE.get(code, (-1, f"未知 code={code}: {payload.get('message')}"))
        results.append(
            {"aid": aid, "code": code, "ok": pattern == 0, "pattern": pattern, "message": msg}
        )
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
) -> list[dict[str, Any]]:
    """歌单/UP 主歌曲的通用翻页（原脚本按 pageCount==curPage 停止）。"""
    songs: list[dict[str, Any]] = []
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
        if data.get("pageCount") == data.get("curPage"):
            break
    return songs


async def fetch_menu_songs(
    client: httpx.AsyncClient, sid: str, max_pages: int = 3
) -> dict[str, Any]:
    """歌单（am{id}）内全部歌曲。"""
    songs = await _fetch_song_list(
        client, _MENU_SONGS_API, lambda pn: {"ps": 100, "sid": sid, "pn": pn}, max_pages
    )
    return {"menu_sid": sid, "total": len(songs), "items": songs}


async def fetch_user_songs(
    client: httpx.AsyncClient, uid: str, order: int = 1, max_pages: int = 3
) -> dict[str, Any]:
    """UP 主上传的歌曲列表。"""
    songs = await _fetch_song_list(
        client, _UPPER_SONGS_API, lambda pn: {"ps": 30, "uid": uid, "order": order, "pn": pn}, max_pages
    )
    return {"uid": uid, "total": len(songs), "items": songs}
