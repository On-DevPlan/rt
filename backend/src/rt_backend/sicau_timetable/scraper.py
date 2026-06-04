"""Pure functions for parsing SICAU jiaowu timetable data into the project's DSL.

Source: D:\\code\\a_dart\\prj\\fr\\scripts\\sicau_timetable\\fetch_sicau_timetable.py
DSL spec: D:\\code\\a_dart\\prj\\fr\\lib\\core\\timetable\\DSL_FORMAT.md
"""
import re
from typing import List, Optional, Tuple


def parse_week_range(text: str) -> List[int]:
    """Parse SICAU week range strings like '1-14', '7,9,11', '1-16(单)'."""
    if not text:
        return []

    # Normalize full-width parentheses
    text = text.replace("（", "(").replace("）", ")")

    parity = None
    if "(单)" in text:
        parity = "odd"
        text = text.replace("(单)", "")
    elif "(双)" in text:
        parity = "even"
        text = text.replace("(双)", "")

    weeks: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            weeks.extend(range(int(start), int(end) + 1))
        elif part:
            weeks.append(int(part))

    if parity == "odd":
        weeks = [w for w in weeks if w % 2 == 1]
    elif parity == "even":
        weeks = [w for w in weeks if w % 2 == 0]

    return weeks


def _map_slot_to_period(slot: int) -> int:
    """Map SICAU slot number to big period number.

    SICAU uses 10 slots per day, grouped into 5 big periods:
    1-2 -> 1, 3-4 -> 2, 5-6 -> 3, 7-8 -> 4, 9-10 -> 5
    """
    return (slot + 1) // 2


def parse_time_segments(text: str) -> List[Tuple[int, int, Optional[str]]]:
    """Parse SICAU time strings like '1-1,1-2' or '2-1(单)'.

    Returns list of (day, period, parity) tuples.
    Each token like '1-1' is parsed as (day=1, slot=1) then mapped to big period 1.
    Duplicates (same day + same period + same parity) are deduplicated.
    """
    if not text:
        return []

    # Normalize full-width parentheses
    text = text.replace("（", "(").replace("）", ")")

    seen: set[tuple[int, int, Optional[str]]] = set()
    segments: List[Tuple[int, int, Optional[str]]] = []

    for seg in text.split():
        seg = seg.strip()
        if not seg:
            continue

        parity: Optional[str] = None
        if "(单)" in seg:
            parity = "单"
            seg = seg.replace("(单)", "")
        elif "(双)" in seg:
            parity = "双"
            seg = seg.replace("(双)", "")

        for part in seg.split(","):
            part = part.strip()
            if not part:
                continue
            dp = part.split("-")
            if len(dp) != 2:
                continue
            day = int(dp[0])
            slot = int(dp[1])
            period = _map_slot_to_period(slot)

            key = (day, period, parity)
            if key not in seen:
                seen.add(key)
                segments.append((day, period, parity))

    return segments


def weeks_to_dsl(weeks: List[int]) -> str:
    """Convert a list of week numbers to DSL week string like 'w1,2,3'."""
    if not weeks:
        return ""
    return "w" + ",".join(str(w) for w in weeks)


def split_multi(text: str) -> List[str]:
    """Split a possibly multi-value string by common separators."""
    if not text:
        return []
    # Split by comma, semicolon, or Chinese comma
    parts = re.split(r"[,;，；]", text)
    return [p.strip() for p in parts if p.strip()]


def course_to_dsl_lines(course: dict) -> List[str]:
    """Convert a single SICAU course dict to one or more DSL lines.

    DSL format: 课程名称 @ 星期 节次 周次 教室 教师
    """
    name = course.get("课程名称", "").strip()
    teacher = course.get("教师", "").strip()
    room = course.get("教室", "").strip()
    weeks_text = course.get("周次", "").strip()
    time_text = course.get("上课时间", "").strip()

    weeks = parse_week_range(weeks_text)
    weeks_str = weeks_to_dsl(weeks)

    lines: List[str] = []

    if not time_text:
        # Online courses without time info — skip
        return lines

    segments = parse_time_segments(time_text)
    if not segments:
        # No valid time segments — skip
        return lines

    for day, period, parity in segments:
        seg_weeks = weeks
        if parity == "单":
            seg_weeks = [w for w in weeks if w % 2 == 1]
        elif parity == "双":
            seg_weeks = [w for w in weeks if w % 2 == 0]
        seg_weeks_str = weeks_to_dsl(seg_weeks)

        parts = [name, "@", str(day), str(period), seg_weeks_str]
        if room:
            parts.append(room)
        if teacher:
            parts.append(teacher)
        lines.append(" ".join(parts))

    return lines


def to_dsl(courses: List[dict]) -> str:
    """Convert a list of SICAU course dicts to a single DSL string."""
    lines: List[str] = ["# 课表 DSL"]
    for course in courses:
        lines.extend(course_to_dsl_lines(course))
    return "\n".join(lines)
