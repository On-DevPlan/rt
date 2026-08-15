"""yuc.wiki 月度新番页解析器。

页面结构（Hexo 静态页，长期稳定）：
- 按星期分节：`<!--周一-->` 注释 + `<td class="date2">周一 (月)</td>`，随后是当日网格。
- 网格条目：`<div style="float:left"><div class="div_date">
    <p class="imgtext4|5">21:00~</p>          <- 播出时刻（JST，深夜用 24:00+ 记法）
    <p class="imgep">(全12话)</p>              <- 总集数；或 <p class="imgep2">8/12~</p> 中途加入
    <img data-src="https://i0.hdslb.com/.../<hash>.jpg"/>
  </div><div><table><td class="date_title_*">中文标题<br>可换行</td>...
- 末尾「网络放送 & 其他」节：非 TV 桌面放送，跳过。
- 详情区（同页下方 500px 表格）：`p.title_cn_r*` 中文全名 / `p.title_jp_r*` 日文名 /
  `p.broadcast_r`（"8/12周三晚间"）/ `p.broadcast_ex_r`（"(全8话)"）/ 官网链接。
  网格与详情用图片 hash（data-src 文件名）join。

深夜归一化：yuc 的 24:00+ 表示次日凌晨（自然日语义），按接口契约
输出 time ∈ [00:00, 23:59] 且 weekday 与 time 同一自然日：
  周六 24:30 -> weekday=7, time="00:30"；周日 25:00 -> weekday=1, time="01:00"。
"""
import re
from typing import Optional

from bs4 import BeautifulSoup

_WEEKDAY_CN = {"周一": 1, "周二": 2, "周三": 3, "周四": 4, "周五": 5, "周六": 6, "周日": 7}
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})~?$")
_EP_TOTAL_RE = re.compile(r"全(\d+)话")
_PART_EP_RE = re.compile(r"P\d+=(\d+)话")
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})")


def normalize_time(text: str) -> Optional[tuple[int, str]]:
    """'21:00' -> (0, '21:00'); '24:30' -> (1, '00:30'); '27:08' -> (1, '03:08').

    Returns (weekday_carry, HH:mm) or None if not a valid grid time.
    """
    m = _TIME_RE.match(text.strip())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh >= 24 and hh < 48 and mm < 60:
        return 1, f"{hh - 24:02d}:{mm:02d}"
    if hh < 24 and mm < 60:
        return 0, f"{hh:02d}:{mm:02d}"
    return None


def _img_key(tag) -> Optional[str]:
    src = tag.get("data-src") or tag.get("src") or ""
    m = re.search(r"([0-9a-f]{16,})\.\w+$", src)
    return m.group(1) if m else None


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("　", " ")).strip()


def parse_episode_count(text: str) -> Optional[int]:
    """'(全12话)' -> 12; 'P1=24话' -> 24; else None."""
    m = _EP_TOTAL_RE.search(text)
    if m:
        return int(m.group(1))
    m = _PART_EP_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def parse_start_date(text: str, page_year: int, page_month: int) -> Optional[str]:
    """'8/12周三晚间' / '12/28周六深夜' -> ISO date，处理跨年（1月页上的 12/x）."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = page_year
    if page_month == 1 and month == 12:
        year -= 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_yuc_page(html: str, page_year: int, page_month: int) -> list[dict]:
    """Parse a yuc.wiki month page into raw item dicts (unsorted, TV grid only)."""
    soup = BeautifulSoup(html, "lxml")

    # --- 详情区：img_key -> {cn, jp, broadcast, eps} ---
    details: dict[str, dict] = {}
    for p in soup.find_all("p", class_=re.compile(r"^title_cn_")):
        table = p.find_parent("table")
        if not table:
            continue
        # 详情条目结构：<div float-left><img 180px/></div><div><table>... — 两 div 是兄弟，
        # 中间可能有换行 NavigableString。用 find_previous_sibling 自动跳过文本节点。
        wrapper = table.find_parent("div")
        prev_div = wrapper.find_previous_sibling("div") if wrapper else None
        img = prev_div.find("img") if prev_div is not None else None
        jp = table.find("p", class_=re.compile(r"^title_jp_"))
        broadcast = table.find("p", class_="broadcast_r")
        bex = table.find("p", class_="broadcast_ex_r")
        link = table.find("a", href=True)
        key = _img_key(img) if img else None
        entry = {
            "cn": _clean_title(p.get_text(" ", strip=True)),
            "jp": _clean_title(jp.get_text(" ", strip=True)) if jp else None,
            "broadcast": broadcast.get_text(" ", strip=True) if broadcast else None,
            "eps_text": bex.get_text(" ", strip=True) if bex else None,
            "url": link["href"] if link else None,
        }
        if key:
            details[key] = entry
        else:
            # hash join 失败时按中文标题兜底
            details.setdefault("t:" + entry["cn"], entry)

    # --- 网格区：按星期分节，节头 td.date2 与条目 div.div_date 按文档顺序遍历 ---
    items: list[dict] = []
    current_weekday: Optional[int] = None
    for tag in soup.find_all(["td", "div"], class_=re.compile(r"^(date2|div_date)$")):
        cls = " ".join(tag.get("class", []))
        if cls == "date2":
            text = tag.get_text(strip=True)
            current_weekday = _WEEKDAY_CN.get(text[:2])
            continue
        if current_weekday is None:
            continue  # 网络放送或其他无名节
        time_p = tag.find("p", class_=re.compile(r"^imgtext"))
        if not time_p:
            continue
        # 文本可能是合法时刻（"21:00~" / "24:30~"）或状态标记（"完结"）。
        # 过去季页（季已结束）用 "完结" 取代时刻——仍保留条目，只把 time 置 null。
        time_text = time_p.get_text(strip=True)
        norm = normalize_time(time_text)
        hhmm: Optional[str] = None
        if norm:
            carry, hhmm = norm
            weekday = ((current_weekday - 1 + carry) % 7) + 1
        else:
            weekday = current_weekday

        img = tag.find("img")
        key = _img_key(img) if img else None
        # 网格条目的外层 div 的兄弟 div 里是标题表格
        title: Optional[str] = None
        grid_eps: Optional[int] = None
        start_text: Optional[str] = None
        outer = tag.parent
        if outer:
            for cousin in outer.find_all("td", class_=re.compile(r"^date_title")):
                title = _clean_title(cousin.get_text(" ", strip=True))
                break
        ep_p = tag.find("p", class_="imgep") or tag.find("p", class_="imgep2")
        if ep_p:
            ep_text = ep_p.get_text(" ", strip=True)
            grid_eps = parse_episode_count(ep_text)
            m = _DATE_RE.search(ep_text)
            if m:
                start_text = ep_text

        detail = details.get(key) if key else None
        if detail is None and title:
            detail = details.get("t:" + title)

        cn_title = (detail and detail["cn"]) or title
        if not cn_title:
            continue
        eps = (detail and detail["eps_text"] and parse_episode_count(detail["eps_text"])) or grid_eps
        broadcast_text = (detail and detail["broadcast"]) or start_text
        start_iso = (
            parse_start_date(broadcast_text, page_year, page_month) if broadcast_text else None
        )

        items.append(
            {
                "id": f"yuc:{key or cn_title}",
                "title": cn_title,
                "titleNative": detail and detail["jp"],
                "startDateIso": start_iso,
                "weekday": weekday,
                "time": hhmm,
                "episodes": eps,
                "durationMin": None,
                "sourceUrl": (detail and detail["url"]) or None,
                "matchedSources": ["yuc"],
            }
        )
    return items
