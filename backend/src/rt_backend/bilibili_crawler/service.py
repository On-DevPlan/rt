"""Bilibili crawler core logic.

Extracted from ``.claudi/repo/Bilibili_crawler``（requests 脚本）并改写为
httpx.AsyncClient 版本：

- WBI 签名（原 ``b站使用wbi签名的爬取方式.py``：mixinKeyEncTab + md5）
- av<->bv 互转（原 ``bv2oid.py`` 的 NEWBV 编码算法）
- 两级评论爬取（原 ``Bilibili_crawler.py``：/x/v2/reply/main 分页 +
  /x/v2/reply/reply 楼中楼，字段抽取 昵称/性别/时间/点赞/评论/IP属地/等级/uid/rpid）
- 用户空间动态列表（原 ``bili_user_space.py``：
  /x/polymer/web-dynamic/v1/feed/space 的 offset 翻页，抽取 comment_id_str/comment_type）
"""
import asyncio
import random
import time
import weakref
from hashlib import md5
from typing import Any
from urllib.parse import urlencode

import httpx

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BilibiliCrawlerError(Exception):
    """Base error for the bilibili_crawler module."""


class AuthError(BilibiliCrawlerError):
    """Upstream rejected the credentials (code -101 等)."""


class UpstreamError(BilibiliCrawlerError):
    """B 站接口返回非 0 code / 非 200 状态。"""


class RiskControlError(UpstreamError):
    """B 站风控拦截（HTTP 412 或 envelope code -352/-403/-412）。

    继承 UpstreamError 以沿用路由层的 502 映射；签名请求链路捕获它做
    换 key 重试（fetch_wbi_keys 缓存失效）。
    """


# ---------------------------------------------------------------------------
# av <-> bv conversion（bv2oid.py 原样移植，纯函数）
# ---------------------------------------------------------------------------

_XOR_CODE = 23442827791579
_MASK_CODE = 2251799813685247
_MAX_AID = 1 << 51
_ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
_ENCODE_MAP = (8, 7, 0, 5, 1, 3, 2, 4, 6)
_DECODE_MAP = tuple(reversed(_ENCODE_MAP))
_BASE = len(_ALPHABET)
_PREFIX = "BV1"
_CODE_LEN = len(_ENCODE_MAP)


def av2bv(aid: int) -> str:
    """aid（av 号）→ bvid（BV 号）。"""
    bvid = [""] * 9
    tmp = (_MAX_AID | aid) ^ _XOR_CODE
    for i in range(_CODE_LEN):
        bvid[_ENCODE_MAP[i]] = _ALPHABET[tmp % _BASE]
        tmp //= _BASE
    return _PREFIX + "".join(bvid)


def bv2av(bvid: str) -> int:
    """bvid（BV 号）→ aid（av 号）。"""
    if not bvid.startswith(_PREFIX):
        raise ValueError(f"bvid 必须以 {_PREFIX} 开头: {bvid!r}")
    bvid = bvid[3:]
    tmp = 0
    for i in range(_CODE_LEN):
        idx = _ALPHABET.index(bvid[_DECODE_MAP[i]])
        tmp = tmp * _BASE + idx
    return (tmp & _MASK_CODE) ^ _XOR_CODE


# ---------------------------------------------------------------------------
# WBI 签名（b站使用wbi签名的爬取方式.py 原样移植）
# ---------------------------------------------------------------------------

_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

_NAV_API = "https://api.bilibili.com/x/web-interface/nav"
_WBI_TTL_SECONDS = 3600  # 1 hour, reused per client instance

# WBI key 缓存：WeakKeyDictionary（client 被 GC 时条目随之消失，杜绝 id 复用脏读），
# 1h TTL 防 key 轮转后脏读；签名遇风控时用 invalidate_wbi_keys 主动失效
_wbi_cache: "weakref.WeakKeyDictionary[httpx.AsyncClient, tuple[float, str, str]]" = (
    weakref.WeakKeyDictionary()
)
_wbi_lock = asyncio.Lock()


def invalidate_wbi_keys(client: httpx.AsyncClient) -> None:
    """签名失败（风控信号 412/-352/-403/-412）后清掉该 client 的 key 缓存。"""
    _wbi_cache.pop(client, None)


def get_mixin_key(orig: str) -> str:
    """对 imgKey + subKey 按混淆表重排，取前 32 位。"""
    return "".join(orig[i] for i in _MIXIN_KEY_ENC_TAB)[:32]


def enc_wbi(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, Any]:
    """为请求参数计算 wbi 签名，返回带 wts/w_rid 的新参数 dict。"""
    mixin_key = get_mixin_key(img_key + sub_key)
    signed = dict(params)
    signed["wts"] = round(time.time())  # 添加 wts 时间戳
    signed = dict(sorted(signed.items()))  # 按 key 重排
    # 过滤 value 中的 "!'()*" 字符
    signed = {
        k: "".join(ch for ch in str(v) if ch not in "!'()*")
        for k, v in signed.items()
    }
    query = urlencode(signed)
    signed["w_rid"] = md5((query + mixin_key).encode()).hexdigest()
    return signed


async def fetch_wbi_keys(client: httpx.AsyncClient) -> tuple[str, str]:
    """从 nav 接口取最新的 img_key / sub_key（同 client 实例内 1 小时缓存）。"""
    now = asyncio.get_event_loop().time()
    cached = _wbi_cache.get(client)
    if cached is not None:
        expires, img_key, sub_key = cached
        if now < expires:
            return img_key, sub_key

    async with _wbi_lock:
        # 锁等待后重取时钟：TTL 不被等待时间侵蚀；双检防并发重复打 nav
        now = asyncio.get_event_loop().time()
        cached = _wbi_cache.get(client)
        if cached is not None:
            expires, img_key, sub_key = cached
            if now < expires:
                return img_key, sub_key

        resp = await client.get(
            _NAV_API,
            headers={"Referer": "https://www.bilibili.com/"},
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0 or not payload.get("data"):
            raise UpstreamError(f"nav 接口返回异常: code={payload.get('code')}")
        wbi_img = payload["data"].get("wbi_img") or {}
        img_url: str = wbi_img.get("img_url", "")
        sub_url: str = wbi_img.get("sub_url", "")
        if not img_url or not sub_url:
            raise UpstreamError("nav 接口缺少 wbi_img 字段")
        img_key = img_url.rsplit("/", 1)[1].split(".")[0]
        sub_key = sub_url.rsplit("/", 1)[1].split(".")[0]
        _wbi_cache[client] = (now + _WBI_TTL_SECONDS, img_key, sub_key)
        return img_key, sub_key


async def sign_params(client: httpx.AsyncClient, params: dict[str, Any]) -> dict[str, Any]:
    """取 key 并签名的一步封装。"""
    img_key, sub_key = await fetch_wbi_keys(client)
    return enc_wbi(params, img_key, sub_key)


# ---------------------------------------------------------------------------
# 通用请求 helper
# ---------------------------------------------------------------------------

_BILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def _headers(sessdata: str | None) -> dict[str, str]:
    headers = dict(_BILI_HEADERS)
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"
    return headers


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    sessdata: str | None,
) -> dict[str, Any]:
    """GET 并解析 B 站 JSON envelope；code!=0 时抛对应错误。5xx/网络错误自动重试。"""
    from ..core.http import request_with_retry

    resp = await request_with_retry(client, "GET", url, params=params, headers=_headers(sessdata))
    if resp.status_code == 412:
        raise RiskControlError("B 站风控拦截（412），请提供 SESSDATA 或稍后再试")
    resp.raise_for_status()
    payload = resp.json()
    code = payload.get("code")
    if code == -101:
        raise AuthError(f"登录态失效或未登录（code=-101）：{payload.get('message')}")
    if code in (-352, -403, -412):
        raise RiskControlError(f"B 站风控拦截（code={code}）：{payload.get('message')}")
    if code != 0:
        raise UpstreamError(f"B 站接口 code={code}: {payload.get('message')}")
    return payload.get("data") or {}


async def _signed_get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    sessdata: str | None,
) -> dict[str, Any]:
    """签名 + GET 组合：遇风控（412/-352/-403/-412）清 key 缓存换新 key 重试一次。

    场景：B 站 key 服务端轮转后，缓存里的旧 key 会持续被风控拒绝，
    不失效则最长 1 小时内所有签名请求全部 502。
    """
    signed = await sign_params(client, params)
    try:
        return await _get_json(client, url, signed, sessdata)
    except RiskControlError:
        invalidate_wbi_keys(client)
        signed = await sign_params(client, params)
        return await _get_json(client, url, signed, sessdata)


# ---------------------------------------------------------------------------
# 视频详情（MediaCrawler get_video_info 的 /x/web-interface/view/detail 完整版：
# aid/bvid 二选一、免签名、含分P pages[]）
# ---------------------------------------------------------------------------

_VIEW_DETAIL_API = "https://api.bilibili.com/x/web-interface/view/detail"
_PLAYURL_API = "https://api.bilibili.com/x/player/wbi/playurl"
_DM_API = "https://api.bilibili.com/x/v1/dm/list.so"


async def fetch_video_detail(
    client: httpx.AsyncClient,
    *,
    aid: int | None = None,
    bvid: str | None = None,
    sessdata: str | None = None,
) -> dict[str, Any]:
    """视频完整详情：标题/UP 主/统计 + 分P 列表 pages[]（含每P cid，playurl/弹幕的前置）。

    对齐 MediaCrawler get_video_info：aid 优先、免签名、端点为 view/detail。
    """
    if not aid and not bvid:
        raise ValueError("aid 与 bvid 至少提供一个")
    params: dict[str, Any] = {"aid": aid} if aid else {"bvid": bvid}
    data = await _get_json(client, _VIEW_DETAIL_API, params, sessdata)
    view = data.get("View") or {}
    stat = view.get("stat") or {}
    owner = view.get("owner") or {}
    pages = [
        {"page": p.get("page"), "part": p.get("part", ""), "cid": p.get("cid")}
        for p in view.get("pages") or []
    ]
    return {
        "bvid": view.get("bvid") or bvid or "",
        "aid": view.get("aid") or aid,
        "cid": view.get("cid"),
        "title": view.get("title", ""),
        "desc": view.get("desc", ""),
        "pic": view.get("pic", ""),
        "owner_mid": owner.get("mid"),
        "owner_name": owner.get("name", ""),
        # 合作视频：staff[] 在 View 顶层（非合作视频无此项），is_cooperation 在 View.rights
        "is_cooperation": bool((view.get("rights") or {}).get("is_cooperation")),
        "staff": [
            {"mid": m.get("mid"), "name": m.get("name", ""), "title": m.get("title", "")}
            for m in view.get("staff") or []
        ],
        "pubdate": view.get("pubdate"),
        "duration": view.get("duration"),
        "pages": pages,
        "view": stat.get("view"),
        "danmaku": stat.get("danmaku"),
        "reply": stat.get("reply"),
        "favorite": stat.get("favorite"),
        "coin": stat.get("coin"),
        "share": stat.get("share"),
        "like": stat.get("like"),
    }


async def fetch_play_url(
    client: httpx.AsyncClient,
    *,
    aid: int,
    cid: int,
    qn: int = 80,
    fnval: int = 1,
    fourk: bool = True,
    sessdata: str | None = None,
) -> dict[str, Any]:
    """播放直链 + 清晰度（MediaCrawler get_video_play_url 的 WBI 签名 playurl 包装）。

    qn 语义（BiliDown.py 原文）：116=1080P60 112=1080P+ 80=1080P 74=720P60
    64=720P 48=720P MP4 32=480P 16=360P（高 qn 多数需要 SESSDATA）。
    fnval：1=音视频合一 mp4（返回 durl 直链）；4048=DASH（无 durl，dash=True）。
    直链交给调用方下载，带 B 站 Referer。
    """
    params: dict[str, Any] = {
        "avid": aid,
        "cid": cid,
        "qn": qn,
        "fourk": 1 if fourk else 0,
        "fnval": fnval,
        "platform": "pc",
    }
    data = await _signed_get_json(client, _PLAYURL_API, params, sessdata)
    durl = [
        {"url": u.get("url"), "backup_url": u.get("backup_url"), "size": u.get("size")}
        for u in data.get("durl") or []
    ]
    return {
        "quality": data.get("quality"),
        "format": data.get("format"),
        "accept_quality": data.get("accept_quality") or [],
        "accept_description": data.get("accept_description") or [],
        "timelength": data.get("timelength"),  # 片长 ms
        "support_formats": data.get("support_formats") or [],  # 各清晰度 format/codecs 透传
        "durl": durl,
        "dash": bool(data.get("dash")),
    }


async def fetch_danmaku(client: httpx.AsyncClient, cid: int) -> dict[str, Any]:
    """分P弹幕（BilibiliDownloader dmApi 的 XML 解析版；上游仓库只落盘原始 XML，
    这里按 B 站标准 dm XML 格式解析 <d p="time,mode,...">text</d>）。"""
    resp = await client.get(_DM_API, params={"oid": cid}, headers=_BILI_HEADERS)
    resp.raise_for_status()
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(resp.text.lstrip())
    except ET.ParseError as e:
        raise UpstreamError(f"弹幕 XML 解析失败: {e}")
    items: list[dict[str, Any]] = []
    for d in root.iter("d"):
        p = (d.get("p") or "").split(",")
        items.append(
            {
                "time": float(p[0]) if p and p[0] else None,
                "mode": int(p[1]) if len(p) > 1 and p[1].isdigit() else None,
                "text": (d.text or "").strip(),
            }
        )
    return {"cid": cid, "total": len(items), "items": items}


# ---------------------------------------------------------------------------
# 评论爬取（Bilibili_crawler.py 的两级评论逻辑）
# ---------------------------------------------------------------------------

_REPLY_MAIN_API = "https://api.bilibili.com/x/v2/reply/main"
_REPLY_SUB_API = "https://api.bilibili.com/x/v2/reply/reply"


def _format_comment_time(ctime: int) -> str:
    """评论时间戳 → 北京时间字符串（原脚本按 UTC 展示，这里改为 +08:00）。"""
    import datetime

    dt = datetime.datetime.fromtimestamp(ctime, datetime.timezone(datetime.timedelta(hours=8)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _normalize_reply(reply: dict[str, Any], pinned: bool = False) -> dict[str, Any]:
    """抽取原脚本关注的字段：昵称/性别/时间/点赞/评论/IP属地/等级/uid/rpid。"""
    member = reply.get("member") or {}
    control = reply.get("reply_control") or {}
    location = control.get("location") or "未知"
    if isinstance(location, str):
        location = location.replace("IP属地：", "")
    return {
        "rpid": str(reply.get("rpid", "")),
        "name": member.get("uname", ""),
        "sex": member.get("sex", ""),
        "time": _format_comment_time(reply.get("ctime", 0)),
        "like": reply.get("like", 0),
        "message": (reply.get("content") or {}).get("message", ""),
        "location": location,
        "level": (member.get("level_info") or {}).get("current_level", 0),
        "mid": str(member.get("mid", "")),
        "reply_count": reply.get("rcount", 0),
        "pinned": pinned,
    }


def _extract_pinned_replies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """首页置顶评论提取（对齐原仓库行为：Bilibili_crawler.py 的 top_replies +
    MediaCrawler client.py _extract_pinned_comments 的 top dict/list 混合形态）。

    - top_replies: list[reply]
    - top: dict（{upper: reply, admin: reply} 或 reply 本身）或 list（元素为 reply
      或 {upper: reply} 包装），按 rpid 去重
    """
    pinned: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _push(reply: Any) -> None:
        if not isinstance(reply, dict):
            return
        rpid = str(reply.get("rpid", ""))
        if not rpid or rpid in seen:
            return
        seen.add(rpid)
        pinned.append(reply)

    for reply in data.get("top_replies") or []:
        _push(reply)

    top = data.get("top")
    if isinstance(top, dict):
        upper = top.get("upper")
        admin = top.get("admin")
        if isinstance(upper, dict):
            _push(upper)
        if isinstance(admin, dict):
            _push(admin)
        if not isinstance(upper, dict) and not isinstance(admin, dict):
            _push(top)  # top 本身就是一条 reply
    elif isinstance(top, list):
        for entry in top:
            if isinstance(entry, dict):
                _push(entry.get("upper") if isinstance(entry.get("upper"), dict) else entry)
    return pinned


async def _fetch_sub_replies(
    client: httpx.AsyncClient,
    oid: str,
    type_: int,
    root_rpid: str,
    ps: int,
    sessdata: str | None,
) -> list[dict[str, Any]]:
    """楼中楼：按 root rpid 翻 /x/v2/reply/reply。"""
    total_pages = None
    replies: list[dict[str, Any]] = []
    page = 1
    while total_pages is None or page <= total_pages:
        data = await _get_json(
            client,
            _REPLY_SUB_API,
            {"type": type_, "oid": oid, "ps": ps, "pn": page, "root": root_rpid},
            sessdata,
        )
        page_replies = data.get("replies") or []
        replies.extend(_normalize_reply(r) for r in page_replies)
        if total_pages is None:
            count = data.get("page", {}).get("count", 0)
            total_pages = -(-count // ps) if count else 1  # ceil
        page += 1
        if not page_replies:
            break
        await asyncio_sleep_small()
    return replies


async def asyncio_sleep_small() -> None:
    """页间隔小睡，降低风控概率（原脚本 0.3-0.4s，这里稍短）。"""
    await asyncio.sleep(random.uniform(0.1, 0.2))


async def fetch_comments(
    client: httpx.AsyncClient,
    oid: str,
    type_: int = 1,
    ps: int = 20,
    pages: int = 1,
    include_replies: bool = True,
    mode: int = 3,
    sessdata: str | None = None,
    *,
    greedy: bool = False,
    max_pages: int = 100,
) -> dict[str, Any]:
    """爬取两级评论（含置顶，对齐原仓库 top_replies/top 处理）。

    Args:
        oid: 目标 id（type=1 视频为 aid，type=17 动态为动态 id）
        type_: 评论区类型（1=视频 17=动态，见 bilibili-API-collect）
        ps: 每页条数（上游上限 49？常用 20/30）
        pages: 抓取的一级评论页数（greedy=False 时生效）
        include_replies: 是否抓取楼中楼
        mode: 排序参数透传上游（2=按时间 3=按热度，0/1 为混合态）
        sessdata: 可选登录态
        greedy: 贪心模式——忽略 pages，翻到上游 is_end 为止（安全上限 max_pages）
        max_pages: greedy 模式的翻页安全上限（触顶记 limit_hit=True）
    """
    comments: list[dict[str, Any]] = []
    seen_rpids: set[str] = set()

    async def _append(reply: dict[str, Any], pinned: bool) -> None:
        rpid = str(reply.get("rpid", ""))
        if rpid and rpid in seen_rpids:
            return  # 置顶常与普通列表重复下发，按 rpid 去重（MediaCrawler 语义）
        if rpid:
            seen_rpids.add(rpid)
        item = _normalize_reply(reply, pinned=pinned)
        item["replies"] = []
        if include_replies and item["reply_count"] > 0:
            item["replies"] = await _fetch_sub_replies(
                client, oid, type_, item["rpid"], ps, sessdata
            )
        comments.append(item)

    page = 0
    fetched = 0
    is_end = None
    limit_hit = False
    while True:
        if not greedy and page >= pages:
            break
        if greedy and page >= max_pages:
            limit_hit = True
            break
        page += 1
        fetched = page
        data = await _get_json(
            client,
            _REPLY_MAIN_API,
            {"next": page, "type": type_, "oid": oid, "ps": ps, "mode": mode},
            sessdata,
        )
        if page == 1:
            for reply in _extract_pinned_replies(data):
                await _append(reply, pinned=True)
        replies = data.get("replies") or []
        if not replies:
            break
        for reply in replies:
            await _append(reply, pinned=False)
        cursor = data.get("cursor") or {}
        is_end = bool(cursor.get("is_end")) if cursor else None
        if greedy and is_end:
            break
        await asyncio_sleep_small()

    return {
        "oid": oid,
        "type": type_,
        "pages_fetched": fetched,
        "total": len(comments),
        "is_end": is_end,
        "greedy": greedy,
        "limit_hit": limit_hit,  # greedy 模式被 max_pages 截断（非上游到底）
        "items": comments,
    }


# ---------------------------------------------------------------------------
# 用户空间动态（bili_user_space.py 的 feed/space offset 翻页）
# ---------------------------------------------------------------------------

_SPACE_FEED_API = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"


async def fetch_user_space(
    client: httpx.AsyncClient,
    mid: str,
    max_pages: int = 3,
    sessdata: str | None = None,
) -> dict[str, Any]:
    """抓取 UP 主动态列表，抽取每条的 comment_id_str / comment_type（原脚本用途：
    得到可爬评论的 oid/type 对），附带标题摘要。"""
    items: list[dict[str, Any]] = []
    offset = ""
    has_more = True
    pages_fetched = 0
    while has_more and pages_fetched < max_pages:
        params: dict[str, Any] = {"host_mid": mid}
        if offset:
            params["offset"] = offset
        data = await _get_json(client, _SPACE_FEED_API, params, sessdata)
        pages_fetched += 1
        for module in data.get("items") or []:
            modules = module.get("modules") or {}
            basic = modules.get("module_basic") or module.get("basic") or {}
            dynamic = modules.get("module_dynamic") or {}
            major = dynamic.get("major") or {}
            author = modules.get("module_author") or {}
            archive = major.get("archive") or {}
            stat_play = (archive.get("stat") or {}).get("play")
            items.append(
                {
                    "comment_id_str": str(basic.get("comment_id_str", "")),
                    "comment_type": basic.get("comment_type"),
                    "dyn_type": module.get("dyn_type"),
                    "title": archive.get("title", ""),
                    # module_author 的展示时间与 unix 秒（space.md:217-218）
                    "pub_time": author.get("pub_time", ""),
                    "pub_ts": author.get("pub_ts"),
                    # 播放数在 archive.stat.play（字符串），与 user-videos 的 play 命名对齐
                    "play": int(stat_play) if isinstance(stat_play, str) and stat_play.isdigit() else stat_play,
                }
            )
        offset = data.get("offset") or ""
        has_more = bool(data.get("has_more")) and bool(offset)
        if has_more:
            await asyncio_sleep_small()

    return {"mid": mid, "pages_fetched": pages_fetched, "total": len(items), "items": items}


# ---------------------------------------------------------------------------
# UP 主全量投稿（MediaCrawler get_creator_videos 的 /x/space/wbi/arc/search 包装）
# ---------------------------------------------------------------------------

_ARC_SEARCH_API = "https://api.bilibili.com/x/space/wbi/arc/search"

_ARC_ORDERS = ("pubdate", "click", "stow")  # 最近发布 / 最多播放 / 最多收藏


async def fetch_user_videos(
    client: httpx.AsyncClient,
    mid: str,
    pn: int = 1,
    ps: int = 30,
    order: str = "pubdate",
    sessdata: str | None = None,
) -> dict[str, Any]:
    """UP 主全部投稿列表（区别于 user-space 的动态子集：置顶隐藏、非动态化
    投稿都能拿到），WBI 签名跨请求复用 sign_params。"""
    if order not in _ARC_ORDERS:
        raise ValueError(f"order 必须是 {_ARC_ORDERS} 之一")
    params: dict[str, Any] = {"mid": mid, "pn": pn, "ps": ps, "order": order}
    data = await _signed_get_json(client, _ARC_SEARCH_API, params, sessdata)
    vlist = (data.get("list") or {}).get("vlist") or []
    items = [
        {
            "aid": v.get("aid"),
            "bvid": v.get("bvid", ""),
            "title": v.get("title", ""),
            "created": v.get("created"),
            "play": v.get("play"),
            "video_review": v.get("video_review"),
            "length": v.get("length", ""),
        }
        for v in vlist
    ]
    return {"mid": mid, "count": data.get("count"), "total": len(items), "items": items}


async def fetch_user_videos_all(
    client: httpx.AsyncClient,
    mid: str,
    ps: int = 30,
    order: str = "pubdate",
    sessdata: str | None = None,
    max_pn: int = 20,
) -> dict[str, Any]:
    """贪心版 UP 主全量投稿：自动翻 pn 直到 count 覆盖完 / 空页（安全上限 max_pn）。

    归档用：items 与单页版同构，另带 pages_fetched / limit_hit。
    """
    if order not in _ARC_ORDERS:
        raise ValueError(f"order 必须是 {_ARC_ORDERS} 之一")
    items: list[dict[str, Any]] = []
    count = None
    pn = 0
    limit_hit = False
    while True:
        if pn >= max_pn:
            limit_hit = True
            break
        pn += 1
        params: dict[str, Any] = {"mid": mid, "pn": pn, "ps": ps, "order": order}
        data = await _signed_get_json(client, _ARC_SEARCH_API, params, sessdata)
        vlist = (data.get("list") or {}).get("vlist") or []
        if not vlist:
            break
        items.extend(
            {
                "aid": v.get("aid"),
                "bvid": v.get("bvid", ""),
                "title": v.get("title", ""),
                "created": v.get("created"),
                "play": v.get("play"),
                "video_review": v.get("video_review"),
                "length": v.get("length", ""),
            }
            for v in vlist
        )
        count = data.get("count")
        if count is not None and pn * ps >= int(count):
            break
        await asyncio_sleep_small()
    return {
        "mid": mid,
        "count": count,
        "total": len(items),
        "pages_fetched": pn,
        "limit_hit": limit_hit,  # max_pn 触顶（非上游到底）
        "items": items,
    }
