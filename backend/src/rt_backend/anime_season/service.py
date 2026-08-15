"""Anime season aggregation service.

数据源选型（对照接口契约 §2.2）：
- 主源 yuc.wiki 月度新番页：中文标题 + 精确 JST 时刻 + 总集数 + 星期。
  关键优势：按"实际播出月"收录，split-cour 中途加入的续播（如 Re:0 S4 P2，
  AniList 归档为 SPRING 单条目、7 月才回归）也会出现在当季页上。
- 降级源 Bangumi /calendar：仅当季可用，有中文名和星期，无时刻 —— 主源挂掉时
  保底返回（契约 §5.6"上游任一家挂掉时接口仍 200 返回降级数据"）。
- 不用 AniList：按条目季归档会漏跨季分割续播，且无中文译名。
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..core.http import HttpClientHolder
from .yuc import parse_yuc_page

JST = timezone(timedelta(hours=9))

SEASONS = ("WINTER", "SPRING", "SUMMER", "FALL")
_SEASON_MONTH = {"WINTER": 1, "SPRING": 4, "SUMMER": 7, "FALL": 10}
_BGM_WEEKDAY = {0: 7, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}  # 0=周日(旧口径) -> 7


class AnimeUpstreamError(Exception):
    """主源+降级源全部失败。"""


def current_season_now(now: Optional[datetime] = None) -> tuple[str, int]:
    """按 JST 日期推断当前季（冬1/春4/夏7/秋10）。now 可注入用于测试。"""
    now = now or datetime.now(JST)
    month = now.month
    if month <= 3:
        return "WINTER", now.year
    if month <= 6:
        return "SPRING", now.year
    if month <= 9:
        return "SUMMER", now.year
    return "FALL", now.year


class _Cache:
    def __init__(self, ttl_sec: int) -> None:
        self.ttl = ttl_sec
        self._store: dict[tuple[str, int], tuple[float, dict]] = {}

    def get(self, key: tuple[str, int]) -> Optional[dict]:
        hit = self._store.get(key)
        if not hit:
            return None
        expires, payload = hit
        if time.monotonic() >= expires:
            self._store.pop(key, None)
            return None
        return payload

    def put(self, key: tuple[str, int], payload: dict) -> None:
        self._store[key] = (time.monotonic() + self.ttl, payload)


_cache: Optional[_Cache] = None


def _get_cache(ttl_sec: int) -> _Cache:
    global _cache
    if _cache is None or _cache.ttl != ttl_sec:
        _cache = _Cache(ttl_sec)
    return _cache


async def _fetch_yuc(
    http: HttpClientHolder, season: str, year: int, timeout: float
) -> list[dict]:
    month = _SEASON_MONTH[season]
    url = f"http://yuc.wiki/{year:04d}{month:02d}/"
    client = http.client
    assert client is not None
    r = await client.get(url, timeout=timeout)
    r.raise_for_status()
    return parse_yuc_page(r.text, year, month)


async def _fetch_bangumi_calendar(http: HttpClientHolder, timeout: float) -> list[dict]:
    """降级源：当季 Bangumi calendar，中文名 + 星期，无时刻。"""
    client = http.client
    assert client is not None
    r = await client.get("https://api.bgm.tv/calendar", timeout=timeout)
    r.raise_for_status()
    items = []
    for day in r.json():
        wd = (day.get("weekday") or {}).get("id")
        for s in day.get("items", []):
            name_cn = (s.get("name_cn") or "").strip()
            name = (s.get("name") or "").strip()
            title = name_cn or name
            if not title:
                continue
            items.append(
                {
                    "id": f"bangumi:{s.get('id')}",
                    "title": title,
                    "titleNative": name or None,
                    "startDateIso": None,
                    "weekday": _BGM_WEEKDAY.get(wd),
                    "time": None,
                    "episodes": None,
                    "durationMin": None,
                    "sourceUrl": f"https://bgm.tv/subject/{s['id']}" if s.get("id") else None,
                    "matchedSources": ["bangumi"],
                }
            )
    return items


async def fetch_season(
    http: HttpClientHolder,
    season: str,
    year: int,
    cache_ttl_sec: int,
    timeout_sec: float,
) -> dict:
    key = (season, year)
    cache = _get_cache(cache_ttl_sec)
    cached = cache.get(key)
    if cached:
        return cached

    # 主源 + 降级源并发起跑：主源成功即取消降级，主源失败用降级（仅当前季有意义）。
    cur_season, cur_year = current_season_now()
    degraded_ok = (season, year) == (cur_season, cur_year)

    async def _yuc() -> list[dict]:
        return await _fetch_yuc(http, season, year, timeout_sec)

    async def _bgm() -> list[dict]:
        await asyncio.sleep(0.2)  # 让主源先跑，正常路径零浪费
        return await _fetch_bangumi_calendar(http, timeout_sec)

    yuc_task = asyncio.create_task(_yuc())
    bgm_task = asyncio.create_task(_bgm()) if degraded_ok else None

    items: Optional[list[dict]] = None
    matched = "yuc"
    try:
        items = await yuc_task
    except Exception:
        if bgm_task is None:
            raise AnimeUpstreamError(f"yuc.wiki fetch failed ({season} {year})")
        try:
            items = await bgm_task
            matched = "bangumi"
        except Exception as e:
            raise AnimeUpstreamError(f"yuc + bangumi both failed: {e!r}")
    finally:
        if bgm_task is not None and not bgm_task.done():
            bgm_task.cancel()

    payload = {
        "season": season,
        "year": year,
        "generatedAt": datetime.now(JST).isoformat(),
        "items": items,
        "_source": matched,
    }
    cache.put(key, payload)
    return payload
