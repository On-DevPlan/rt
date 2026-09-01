"""Tests for the v2 WebVPN iframe timetable parser."""
import pytest

from rt_backend.sicau_timetable_v2.scraper import parse_timetable_iframe_html


def _iframe_html() -> str:
    """Mimics the WebVPN jiaowu kbbanji.asp DOM: a merged junk table + the
    14-column detail table at the bottom."""
    return """<html><body>
    <table><tr><td>四川农业大学2026-2027-1学期课程表 物联网202303 赵刘学 时间 星期一 ...
    校区 课程名称 编号 周次 教室 上课时间 学分 学时 周学时 实验周学时 考核方法 教师 选课方式 混合式教学</td></tr></table>
    <table>
      <tr>
        <td>校区</td><td>课程名称</td><td>编号</td><td>周次</td><td>教室</td><td>上课时间</td>
        <td>学分</td><td>学时</td><td>周学时</td><td>实验周学时</td><td>考核方法</td>
        <td>教师</td><td>选课方式</td><td>混合式教学</td>
      </tr>
      <tr>
        <td>雅安</td><td>测试课</td><td>CS001</td><td>1-2</td><td>A101</td><td>1-1,1-2</td>
        <td>2</td><td>32</td><td>2</td><td>0</td><td>考试</td><td>张老师</td><td>正常</td><td></td>
      </tr>
      <tr><td>雅安</td></tr>
    </table>
    </body></html>"""


def test_parser_picks_detail_table_and_skips_junk():
    courses = parse_timetable_iframe_html(_iframe_html())
    # The merged junk table and the 1-cell row must be skipped.
    assert len(courses) == 1
    assert courses[0]["课程名称"] == "测试课"
    assert courses[0]["教师"] == "张老师"
    assert courses[0]["上课时间"] == "1-1,1-2"


def test_parser_roundtrip_to_dsl():
    from rt_backend.sicau_timetable.scraper import to_dsl

    courses = parse_timetable_iframe_html(_iframe_html())
    dsl = to_dsl(courses)
    assert "测试课 @ 1 1 w1,2 A101 张老师" in dsl


def test_parser_raises_on_missing_table():
    with pytest.raises(ValueError):
        parse_timetable_iframe_html("<html><body><p>no tables</p></body></html>")
