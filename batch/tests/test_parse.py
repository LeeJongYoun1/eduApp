from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from eduapp_batch.parse import parse_date, parse_date_range, parse_datetime, parse_grades

TODAY = date(2026, 11, 6)


@pytest.mark.parametrize("text,expected", [
    ("2026. 11. 6.(목)", date(2026, 11, 6)),
    ("2026-11-06", date(2026, 11, 6)),
    ("11.20", date(2026, 11, 20)),
    ("1.5", date(2027, 1, 5)),        # 오늘보다 2개월 넘게 이전이면 다음 해
    ("10.1", date(2026, 10, 1)),      # 2개월 이내 과거는 올해
    ("상시", None),
])
def test_parse_date(text, expected):
    assert parse_date(text, TODAY) == expected


@pytest.mark.parametrize("text,expected", [
    ("2026.11.6 ~ 2026.11.20", (date(2026, 11, 6), date(2026, 11, 20))),
    ("11.6~11.20", (date(2026, 11, 6), date(2026, 11, 20))),
    ("2026-11-08", (date(2026, 11, 8), date(2026, 11, 8))),
    ("12.20~1.10", (date(2026, 12, 20), date(2027, 1, 10))),
    ("상시 운영", (None, None)),
])
def test_parse_date_range(text, expected):
    assert parse_date_range(text, TODAY) == expected


def test_parse_datetime_is_kst():
    assert parse_datetime("2026-11-10 10:00", TODAY) == datetime(2026, 11, 10, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))


def test_parse_datetime_without_time_is_none():
    assert parse_datetime("2026-11-10", TODAY) is None


@pytest.mark.parametrize("text,expected", [
    ("초등 3~4학년", (3, 4)),
    ("초3-6", (3, 6)),
    ("전학년", (1, 6)),
    ("초등학생", (1, 6)),
    ("유아", None),
    ("중학생 이상", None),
    ("7세~초2", (1, 2)),
    ("초등 5학년", (5, 5)),
])
def test_parse_grades(text, expected):
    assert parse_grades(text) == expected


def test_parse_grades_open_ended():
    assert parse_grades("초등 5학년 이상") == (5, 6)


@pytest.mark.parametrize("text,expected", [
    ("중1~3학년", None),
    ("고등학생 1~2학년", None),
    ("중학교 전학년", None),
    ("초등학생(3~6학년)", (3, 6)),
    ("초등 3, 4학년", (3, 4)),
    ("초등 4학년~중등 2학년", (4, 6)),
    ("초등 2학년 이하", (1, 2)),
    ("초등 저학년", (1, 3)),
    ("초등 고학년", (4, 6)),
])
def test_parse_grades_real_world(text, expected):
    assert parse_grades(text) == expected


@pytest.mark.parametrize("text", ["2.30", "2026.13.01", "2026. 2. 30."])
def test_parse_date_invalid_is_none(text):
    assert parse_date(text, TODAY) is None


def test_parse_grades_ignores_head_counts():
    assert parse_grades("초등학생 포함 가족 5팀") == (1, 6)
    assert parse_grades("초등 3~4학년 20명") == (3, 4)


def test_age_grades():
    from eduapp_batch.parse import age_grades
    assert age_grades("8~10세(2017~2019년생)") == (1, 3)          # 한국 나이 8세 = 초1 (기본)
    assert age_grades("만 7~9세") == (1, 3)                      # 만 나이는 늘 N-6
    assert age_grades("5세 이상") == (1, 6)
    assert age_grades("만 4~6세 이상") == (1, 6)                 # 범위 뒤 "이상"
    assert age_grades("6세~10세", first_grade_age=7) == (1, 4)  # 기관이 7세 = 초1로 쓰는 경우
    assert age_grades("6-7세") is None                           # 미취학만
    assert age_grades("28 - 48개월") is None
    assert age_grades("성인") is None
