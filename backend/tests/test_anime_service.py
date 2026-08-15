"""Service-level tests: season inference, weekday mapping, upstream orchestration."""
from datetime import datetime, timezone, timedelta

from rt_backend.anime_season.service import (
    JST,
    current_season_now,
)


def test_current_season_quarter_boundaries():
    # 冬：1-3 月；春：4-6；夏：7-9；秋：10-12
    assert current_season_now(datetime(2026, 1, 15, tzinfo=JST)) == ("WINTER", 2026)
    assert current_season_now(datetime(2026, 3, 31, 23, 59, tzinfo=JST)) == ("WINTER", 2026)
    assert current_season_now(datetime(2026, 4, 1, tzinfo=JST)) == ("SPRING", 2026)
    assert current_season_now(datetime(2026, 6, 30, tzinfo=JST)) == ("SPRING", 2026)
    assert current_season_now(datetime(2026, 7, 1, tzinfo=JST)) == ("SUMMER", 2026)
    assert current_season_now(datetime(2026, 9, 30, tzinfo=JST)) == ("SUMMER", 2026)
    assert current_season_now(datetime(2026, 10, 1, tzinfo=JST)) == ("FALL", 2026)
    assert current_season_now(datetime(2026, 12, 31, tzinfo=JST)) == ("FALL", 2026)