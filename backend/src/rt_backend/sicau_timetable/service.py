"""SICAU jiaowu scraping service: login -> fetch HTML -> parse -> DSL."""
import re
from typing import List

from ..core.http import HttpClientHolder
from .scraper import to_dsl

BASE = "https://jiaowu.sicau.edu.cn"
LOGIN_PAGE = f"{BASE}/web/web/web/index.asp"
LOGIN_POST = f"{BASE}/jiaoshi/bangong/check.asp"
SEMESTER_PAGE = f"{BASE}/xuesheng/gongxuan/gongxuan/xszhinan.asp"
TIMETABLE_PAGE = f"{BASE}/xuesheng/gongxuan/gongxuan/kbbanji.asp"

# Fallback column names when the rendered table header doesn't match.
_COLUMN_NAMES = [
    "校区", "课程名称", "编号", "周次", "教室", "上课时间",
    "学分", "学时", "周学时", "实验周学时", "考核方法",
    "教师", "选课方式", "混合式教学",
]


class SicauError(Exception):
    """Base SICAU error."""


class LoginError(SicauError):
    """Wrong credentials or login page changed."""


class FetchError(SicauError):
    """Network or page-structure error after login."""


def _decode_sicau_bytes(content: bytes) -> str:
    """SICAU jiaowu pages are GBK / GB2312. Decode accordingly."""
    head = content[:2048]
    m = re.search(rb"charset=([\w-]+)", head, re.IGNORECASE)
    declared = m.group(1).decode("ascii", errors="ignore").lower() if m else ""
    encoding = "gbk"
    if declared in ("gbk", "gb2312", "gb18030"):
        encoding = declared
    return content.decode(encoding, errors="replace")


async def login(http: HttpClientHolder, user_id: str, password: str) -> None:
    """Log in to SICAU jiaowu. Raises LoginError on bad credentials."""
    client = http.client
    assert client is not None

    r = await client.get(LOGIN_PAGE)
    r.raise_for_status()
    html = _decode_sicau_bytes(r.content)

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", attrs={"name": "form1"})
    if not form:
        raise FetchError("登录页未找到 form1")
    sign = form.find("input", attrs={"name": "sign"})
    hour_key = form.find("input", attrs={"name": "hour_key"})
    if not sign or not hour_key:
        raise FetchError("登录页缺少 sign / hour_key 隐藏字段")

    payload = {
        "user": user_id,
        "pwd": password,
        "lb": "S",
        "sign": sign.get("value", ""),
        "hour_key": hour_key.get("value", ""),
        "submit": "",
    }
    r = await client.post(
        LOGIN_POST,
        data=payload,
        headers={"Referer": LOGIN_PAGE},
    )
    r.raise_for_status()
    text = _decode_sicau_bytes(r.content)

    if "index1.asp" not in str(r.url) and "学生-课业信息" not in text and user_id not in text:
        m = re.search(r"alert\(['\"]([^'\"]+)", text) or re.search(
            r"<font[^>]*color=red[^>]*>([^<]+)</font>", text
        )
        msg = m.group(1) if m else "登录失败，可能是学号/密码错误"
        raise LoginError(msg)


async def fetch_timetable_html(http: HttpClientHolder, semester: str) -> str:
    """Switch to the given semester and return the timetable page HTML."""
    client = http.client
    assert client is not None

    r = await client.get(
        SEMESTER_PAGE,
        params={"title_id1": "9", "xueqi": semester},
    )
    r.raise_for_status()

    r = await client.get(TIMETABLE_PAGE, params={"title_id1": "4"})
    r.raise_for_status()
    return _decode_sicau_bytes(r.content)


def parse_courses_from_html(html: str) -> List[dict]:
    """Parse the SICAU timetable HTML into course dicts."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    candidates = []
    for t in tables:
        first_row = t.find("tr")
        if not first_row:
            continue
        header_cells = [c.get_text(" ", strip=True) for c in first_row.find_all(["th", "td"])]
        head_text = " ".join(header_cells)
        score = 0
        if "课程名称" in head_text and "编号" in head_text:
            score += 100
        if "校区" in head_text:
            score += 10
        if "上课时间" in head_text:
            score += 10
        if "教师" in head_text:
            score += 5
        if "学分" in head_text:
            score += 5
        if score > 0:
            candidates.append((len(header_cells), t, score, header_cells))

    if not candidates:
        raise FetchError("未找到课表明细表（缺少 课程名称/编号 列）")

    candidates.sort(key=lambda x: (x[2], x[0]), reverse=True)
    target = None
    for cols, t, score, _ in candidates:
        if cols >= 10:
            target = t
            break
    if target is None:
        target = candidates[0][1]

    rows = target.find_all("tr")
    if len(rows) < 2:
        raise FetchError("课表为空（仅表头，无数据行）")

    header_cells = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    if header_cells[:2] != ["校区", "课程名称"]:
        header_cells = _COLUMN_NAMES

    courses: List[dict] = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or not cells[1]:
            continue
        cells = (cells + [""] * len(header_cells))[: len(header_cells)]
        courses.append(dict(zip(header_cells, cells)))
    return courses


async def fetch_timetable_dsl(
    http: HttpClientHolder,
    user_id: str,
    password: str,
    semester: str,
) -> dict:
    """Full pipeline. Returns dict with user_id, semester, dsl, course_count, generated_at."""
    await login(http, user_id, password)
    html = await fetch_timetable_html(http, semester)
    courses = parse_courses_from_html(html)
    dsl = to_dsl(courses)
    from datetime import datetime
    return {
        "user_id": user_id,
        "semester": semester,
        "dsl": dsl,
        "course_count": len(courses),
        "generated_at": datetime.now().astimezone(),
    }
