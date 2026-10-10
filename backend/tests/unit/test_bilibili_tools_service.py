"""Unit tests for bilibili_tools service 纯函数（fav_mlid 数学、链接解析）。"""

import pytest

from rt_backend.bilibili_tools.service import (
    fav_mlid,
    parse_audio_sid,
    parse_fav_link,
    parse_menu_sid,
    parse_space_uid,
)


class TestFavMlid:
    """收藏夹完整 mlid 数学（fid × 100 + mid 尾号 2 位）。"""

    def test_known_vector_from_docs(self):
        # bilibili-API-collect/docs/fav/list.md：fid=10526220 + mid=686127 → mlid=1052622027
        assert fav_mlid("10526220", "10526220") is not None  # 防呆：签名正确性
        assert fav_mlid("686127", "10526220") == 1052622027

    def test_mid_tail_two_digits(self):
        # mid 尾号 2 位 = mid % 100
        assert fav_mlid("42", "12345") == 1234542
        assert fav_mlid("7", "999") == 99907
        assert fav_mlid("100", "1") == 100  # mid=100 → 尾号 00

    def test_requires_numeric(self):
        with pytest.raises(ValueError):
            fav_mlid("abc", "123")


class TestParseFavLink:
    """收藏夹链接解析（mid + fid）。"""

    def test_standard_favlist_url(self):
        mid, fid = parse_fav_link("https://space.bilibili.com/42/favlist?fid=12345")
        assert mid == "42"
        assert fid == "12345"

    def test_url_with_extra_params(self):
        mid, fid = parse_fav_link(
            "https://space.bilibili.com/2932528/favlist?fid=10526220&ftype=collect&p=2"
        )
        assert mid == "2932528"
        assert fid == "10526220"

    def test_missing_fid_raises(self):
        with pytest.raises(ValueError, match="mid/fid"):
            parse_fav_link("https://space.bilibili.com/42/favlist")

    def test_missing_mid_raises(self):
        with pytest.raises(ValueError, match="mid/fid"):
            parse_fav_link("https://example.com/favlist?fid=1")


class TestAudioParsers:
    """音频区链接解析。"""

    def test_parse_audio_sid_full_url(self):
        assert parse_audio_sid("https://www.bilibili.com/audio/au241921") == "241921"

    def test_parse_audio_sid_bare_au(self):
        assert parse_audio_sid("au682118") == "682118"

    def test_parse_audio_sid_no_match(self):
        assert parse_audio_sid("https://example.com/x") == ""

    def test_parse_menu_sid_full_url(self):
        assert parse_menu_sid("https://www.bilibili.com/audio/am76105") == "76105"

    def test_parse_menu_sid_bare_am(self):
        assert parse_menu_sid("am123") == "123"

    def test_parse_menu_sid_no_match(self):
        assert parse_menu_sid("https://example.com/am") == ""

    def test_parse_space_uid_audio_url(self):
        assert parse_space_uid("https://space.bilibili.com/2932528/audio") == "2932528"

    def test_parse_space_uid_plain_space(self):
        assert parse_space_uid("https://space.bilibili.com/686127") == "686127"

    def test_parse_space_uid_no_match(self):
        assert parse_space_uid("https://example.com/space") == ""
