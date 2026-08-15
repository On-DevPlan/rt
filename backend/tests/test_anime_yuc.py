"""Unit tests for yuc.wiki parser: time normalization, weekday sections, deep-night, join."""
from pathlib import Path

from rt_backend.anime_season.yuc import (
    normalize_time,
    parse_episode_count,
    parse_start_date,
    parse_yuc_page,
)

FIXTURE = Path(__file__).parent / "fixtures" / "yuc_sample.html"
PAST_FIXTURE = Path(__file__).parent / "fixtures" / "yuc_past_season.html"


def test_normalize_time_regular():
    assert normalize_time("21:00~") == (0, "21:00")
    assert normalize_time("23:56~") == (0, "23:56")


def test_normalize_time_deep_night():
    # yuc 深夜记法：24:00+ 表示次日凌晨
    assert normalize_time("24:00~") == (1, "00:00")
    assert normalize_time("24:30~") == (1, "00:30")
    assert normalize_time("25:30~") == (1, "01:30")
    assert normalize_time("27:08~") == (1, "03:08")


def test_normalize_time_invalid():
    assert normalize_time("7/19网络放送") is None
    assert normalize_time("") is None
    assert normalize_time("99:00~") is None


def test_parse_episode_count():
    assert parse_episode_count("(全12话)") == 12
    assert parse_episode_count("P1=24话") == 24
    assert parse_episode_count("8/12~") is None


def test_parse_start_date():
    assert parse_start_date("7/6周一深夜", 2026, 7) == "2026-07-06"
    assert parse_start_date("8/12周三晚间", 2026, 7) == "2026-08-12"
    # 1 月季页上的 12/x 开播 → 上一年
    assert parse_start_date("12/28周六深夜", 2026, 1) == "2025-12-28"


def test_parse_page_counts_and_filtering():
    items = parse_yuc_page(FIXTURE.read_text(encoding="utf-8"), 2026, 7)
    titles = {i["title"] for i in items}
    # 5 个 TV 网格条目；网络放送条目被过滤（无合法时刻或位于非星期节）
    assert len(items) == 5
    assert "网络独播番" not in titles


def test_parse_page_deep_night_natural_day():
    items = {i["title"]: i for i in parse_yuc_page(FIXTURE.read_text(encoding="utf-8"), 2026, 7)}
    # 周六 24:30 -> 周日 00:30（自然日）
    assert items["周六深夜番"]["weekday"] == 7
    assert items["周六深夜番"]["time"] == "00:30"
    # 周日 25:00 -> 周一 01:00（跨周回绕）
    assert items["周日跨零番"]["weekday"] == 1
    assert items["周日跨零番"]["time"] == "01:00"


def test_parse_page_detail_join_by_image_hash():
    items = {i["title"]: i for i in parse_yuc_page(FIXTURE.read_text(encoding="utf-8"), 2026, 7)}
    # 网格标题是简写，详情区中文全名 + 日文名通过图片 hash join 进来
    cont = items["跨季续播番 第4期 Part.2 夺还篇"]
    assert cont["titleNative"] == "続編アニメ 4th season"
    assert cont["startDateIso"] == "2026-08-12"
    assert cont["episodes"] == 8  # 详情 (全8话) 覆盖网格
    assert cont["sourceUrl"] == "https://example.com/cont/"
    assert cont["weekday"] == 3
    assert cont["time"] == "21:00"


def test_parse_page_grid_only_entry_fallback():
    items = {i["title"]: i for i in parse_yuc_page(FIXTURE.read_text(encoding="utf-8"), 2026, 7)}
    # 无详情条目：标题来自网格，集数来自网格 imgep，其余 null
    lone = items["无详情番"]
    assert lone["titleNative"] is None
    assert lone["episodes"] == 10
    assert lone["sourceUrl"] is None
    assert lone["matchedSources"] == ["yuc"]


def test_parse_page_grid_start_date_from_imgep2():
    items = {i["title"]: i for i in parse_yuc_page(FIXTURE.read_text(encoding="utf-8"), 2026, 7)}
    # imgep2 "8/12~" 中途加入 → startDateIso 兜底
    assert items["跨季续播番 第4期 Part.2 夺还篇"]["startDateIso"] == "2026-08-12"


def test_parse_past_season_keeps_finished_entries():
    """过去季页用 <p class=imgtext2>完结</p> 取代时刻 —— 仍保留条目，time=null。

    这是兼容性修复：之前 parser 因 normalize_time("完结") 返 None 而跳过整行，
    导致 2025年1月页 63 条只剩 1 条；现在保留全部（time=null，weekday 来自节头）。
    """
    items = parse_yuc_page(PAST_FIXTURE.read_text(encoding="utf-8"), 2025, 1)
    titles = {i["title"] for i in items}
    # 2 个 TV 网格完结条目保留；网络放送条目被过滤
    assert len(items) == 2
    assert "网络独播番" not in titles
    # 所有保留条目 time=null，但 weekday/startDateIso/episodes 都有
    for i in items:
        assert i["time"] is None
        assert i["weekday"] is not None
        assert i["startDateIso"] is not None
        assert i["episodes"] is not None


def test_parse_past_season_detail_join_still_works():
    """imgtext2 完结条目仍按图片哈希 join 详情区拿到 titleNative/sourceUrl/eps."""
    items = {i["title"]: i for i in parse_yuc_page(PAST_FIXTURE.read_text(encoding="utf-8"), 2025, 1)}
    re0 = items["Re:从零开始的异世界生活 第3期 Part.2 反击篇"]
    assert re0["titleNative"] == "Re:ゼロから始める異世界生活 3rd season"
    assert re0["weekday"] == 3
    assert re0["startDateIso"] == "2025-02-05"  # 详情 broadcast_r "2/5周三晚间"
    assert re0["episodes"] == 8  # 详情 (全8话) 覆盖网格
    assert re0["sourceUrl"] == "https://re-zero-anime.jp/tv/"
