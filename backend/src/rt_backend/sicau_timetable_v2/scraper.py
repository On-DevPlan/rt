"""Parse the WebVPN jiaowu timetable iframe DOM into course dicts.

The WebVPN iframe DOM has a `table[1]` that's a giant merged cell containing
all the page content — the v1 scoring heuristic picks that one and then crashes.
This module picks the **detail table directly**: the table whose first row
starts with `["校区", "课程名称", …]` (the actual course list at the bottom).
"""
from typing import List

from bs4 import BeautifulSoup


# Mirrors the v1 _COLUMN_NAMES fallback but kept explicit here because v1's
# heuristic doesn't fire on the WebVPN DOM (header doesn't start with
# ["校区", "课程名称"] in some renderings).
_DETAIL_HEADER = [
    "校区", "课程名称", "编号", "周次", "教室", "上课时间",
    "学分", "学时", "周学时", "实验周学时", "考核方法",
    "教师", "选课方式", "混合式教学",
]


def parse_timetable_iframe_html(html: str) -> List[dict]:
    """Pick the detail course table and return rows as dicts."""
    soup = BeautifulSoup(html, "html.parser")

    detail = _find_detail_table(soup)
    if detail is None:
        raise ValueError("未找到课表明细表（缺少 校区/课程名称 表头）")

    rows = detail.find_all("tr")
    if len(rows) < 2:
        raise ValueError("课表为空（仅表头，无数据行）")

    n_cols = len(_DETAIL_HEADER)
    courses: List[dict] = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        # Skip rows with too few cells (title rows, empty rows)
        if len(cells) < 2 or not cells[1]:
            continue
        # Pad / trim to header length
        cells = (cells + [""] * n_cols)[:n_cols]
        courses.append(dict(zip(_DETAIL_HEADER, cells)))
    return courses


def _find_detail_table(soup: BeautifulSoup) -> BeautifulSoup | None:
    """Return the table whose header is the 14-column detail header."""
    for t in soup.find_all("table"):
        first = t.find("tr")
        if not first:
            continue
        heads = [c.get_text(" ", strip=True) for c in first.find_all(["th", "td"])]
        if len(heads) != len(_DETAIL_HEADER):
            continue
        if heads[:2] != _DETAIL_HEADER[:2]:
            continue
        # Sanity: must have 校区 + 课程名称 + 编号 + 上课时间
        joined = " ".join(heads)
        if "课程名称" in joined and "编号" in joined and "上课时间" in joined:
            return t
    return None