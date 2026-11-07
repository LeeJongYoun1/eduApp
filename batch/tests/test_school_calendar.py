import copy
import json
from datetime import date
from pathlib import Path

import httpx

from eduapp_batch import school_calendar
from eduapp_batch.school_calendar import fetch_schedule, parse_schedule

FIX = json.loads((Path(__file__).parent / "fixtures/neis_school_schedule.json").read_text())
ROWS = FIX["SchoolSchedule"][1]["row"]
GRADES = ["ONE", "TW", "THREE", "FR", "FIV", "SIX"]


def _payload(rows):
    return {"SchoolSchedule": [FIX["SchoolSchedule"][0], {"row": rows}]}


def test_parse_marks_holidays():
    by_name = {d.event_name: d for d in parse_schedule(FIX)}
    assert by_name["대체공휴일"].day.weekday() < 5 and by_name["대체공휴일"].is_holiday is True  # 평일 공휴일
    assert by_name["시업,입학식"].is_holiday is False  # 해당없음


def _row(ymd, name, kind):
    return {**ROWS[0], "AA_YMD": ymd, "EVENT_NM": name, "SBTR_DD_SC_NM": kind}


def test_weekend_off_days_are_stored_but_not_holidays():
    # 2026-11-07 토요일, 2026-11-09 월요일. 주말 휴업일·공휴일은 '우리 학교 쉬는 날'이 아니다.
    days = {d.event_name: d for d in parse_schedule(_payload([
        _row("20261107", "토요휴업일", "휴업일"), _row("20261108", "일요 공휴일", "공휴일"),
        _row("20261109", "학교장재량휴업일", "공휴일")]))}
    assert days["토요휴업일"].is_holiday is False and days["일요 공휴일"].is_holiday is False
    assert days["학교장재량휴업일"].is_holiday is True


def test_parse_skips_rows_not_for_any_grade_1_to_6():
    row = copy.deepcopy(ROWS[0])
    for g in GRADES:
        row[f"{g}_GRADE_EVENT_YN"] = "N" if g == "ONE" else "*"
    assert parse_schedule(_payload([row])) == []
    row["FIV_GRADE_EVENT_YN"] = "Y"
    assert len(parse_schedule(_payload([row]))) == 1


def test_parse_dedupes_same_day_and_event():
    assert len(parse_schedule(_payload([ROWS[0], ROWS[0]]))) == 1


def test_parse_no_result_is_empty():
    assert parse_schedule({"RESULT": {"CODE": "INFO-200"}}) == []


def test_fetch_schedule_covers_today_to_plus_365_days(monkeypatch):
    calls = []

    def fake_get(url, timeout, params):
        calls.append(params)
        return httpx.Response(200, json=FIX, request=httpx.Request("GET", url))

    monkeypatch.setattr(school_calendar.httpx, "get", fake_get)
    days = fetch_schedule("J10", "7569013", "k", date(2026, 11, 7))
    assert len(days) == len(parse_schedule(FIX))
    assert calls[0]["AA_FROM_YMD"] == "20261107" and calls[0]["AA_TO_YMD"] == "20271107"
    assert calls[0]["ATPT_OFCDC_SC_CODE"] == "J10" and calls[0]["SD_SCHUL_CODE"] == "7569013"
