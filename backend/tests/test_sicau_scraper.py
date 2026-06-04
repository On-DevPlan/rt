from rt_backend.sicau_timetable.scraper import (
    _map_slot_to_period,
    course_to_dsl_lines,
    parse_time_segments,
    parse_week_range,
    to_dsl,
    weeks_to_dsl,
)


# --------------------------- parse_week_range ---------------------------


def test_parse_simple_range():
    assert parse_week_range("1-14") == list(range(1, 15))


def test_parse_comma_list():
    assert parse_week_range("7,9,11") == [7, 9, 11]


def test_parse_odd_parity():
    assert parse_week_range("1-16(单)") == [1, 3, 5, 7, 9, 11, 13, 15]


def test_parse_even_parity():
    assert parse_week_range("1-16(双)") == [2, 4, 6, 8, 10, 12, 14, 16]


def test_parse_empty():
    assert parse_week_range("") == []


def test_parse_full_width_parens():
    assert parse_week_range("1-8（单）") == [1, 3, 5, 7]


# --------------------------- _map_slot_to_period ---------------------------


def test_map_slot_to_period():
    assert _map_slot_to_period(1) == 1
    assert _map_slot_to_period(2) == 1
    assert _map_slot_to_period(3) == 2
    assert _map_slot_to_period(4) == 2
    assert _map_slot_to_period(9) == 5
    assert _map_slot_to_period(10) == 5


# --------------------------- parse_time_segments ---------------------------


def test_parse_single_segment():
    # 1-1,1-2 都映射到大节 1，去重后只剩一个
    assert parse_time_segments("1-1,1-2") == [(1, 1, None)]


def test_parse_segment_with_parity():
    # 4-5,4-6 映射到大节 3，去重后只剩一个
    assert parse_time_segments("4-5,4-6(单)") == [(4, 3, "单")]


def test_parse_multi_day():
    # 2-9,3-9：day2 slot9→period5，day3 slot9→period5
    assert parse_time_segments("2-9,3-9") == [(2, 5, None), (3, 5, None)]


def test_parse_two_segments_separated_by_space():
    # 2-9,2-10 → period5 (day2)；4-5,4-6 → period3 (day4)
    result = parse_time_segments("2-9,2-10 4-5,4-6")
    assert result == [(2, 5, None), (4, 3, None)]


def test_parse_empty():
    assert parse_time_segments("") == []


# --------------------------- weeks_to_dsl ---------------------------


def test_weeks_to_dsl_empty():
    assert weeks_to_dsl([]) == ""


def test_weeks_to_dsl_expanded():
    assert weeks_to_dsl([1, 3, 5]) == "w1,3,5"


def test_weeks_to_dsl_long():
    weeks = list(range(1, 9))
    assert weeks_to_dsl(weeks) == "w1,2,3,4,5,6,7,8"


# --------------------------- course_to_dsl_lines ---------------------------


def test_course_to_dsl_simple():
    course = {
        "课程名称": "高等数学",
        "教师": "张老师",
        "教室": "教学楼A101",
        "周次": "1-14",
        "上课时间": "1-1,1-2",
    }
    lines = course_to_dsl_lines(course)
    # slot 1,2 都映射到 period 1，去重后只剩一行
    assert lines == ["高等数学 @ 1 1 w1,2,3,4,5,6,7,8,9,10,11,12,13,14 教学楼A101 张老师"]


def test_course_to_dsl_odd_weeks_split():
    course = {
        "课程名称": "体育",
        "教师": "王老师",
        "教室": "操场",
        "周次": "1-8",
        "上课时间": "2-1(单)",
    }
    lines = course_to_dsl_lines(course)
    # slot 1 → period 1
    assert lines == ["体育 @ 2 1 w1,3,5,7 操场 王老师"]


def test_course_to_dsl_no_time_skips():
    course = {
        "课程名称": "在线课程",
        "教师": "",
        "教室": "",
        "周次": "1-8",
        "上课时间": "",
    }
    lines = course_to_dsl_lines(course)
    # No time info — skip online courses
    assert lines == []


# --------------------------- to_dsl ---------------------------


def test_to_dsl_full_pipeline():
    courses = [
        {
            "课程名称": "高等数学",
            "教师": "张老师",
            "教室": "教学楼A101",
            "周次": "1-14",
            "上课时间": "1-1,1-2",
        },
        {
            "课程名称": "体育",
            "教师": "王老师",
            "教室": "操场",
            "周次": "1-8",
            "上课时间": "2-1(单)",
        },
    ]
    out = to_dsl(courses)
    assert "高等数学 @ 1 1 w1,2,3,4,5,6,7,8,9,10,11,12,13,14 教学楼A101 张老师" in out
    assert "体育 @ 2 1 w1,3,5,7 操场 王老师" in out
    assert out.startswith("# 课表 DSL")
