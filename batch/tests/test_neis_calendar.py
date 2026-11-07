import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from eduapp_batch.models import CalendarDay, SchoolRef
from eduapp_batch.neis_calendar import fetch_schedule, parse_schedule
from eduapp_batch.store import PgStore, RestStore

FIX = Path(__file__).parent / "fixtures"
REAL = json.loads((FIX / "neis_school_schedule.json").read_text())  # 실제 응답 (키 없는 호출, 5행)
CLOSURE = json.loads((FIX / "neis_school_schedule_closure.json").read_text())  # 재량휴업일 행을 같은 형식으로 추가
SCHOOL = SchoolRef(id=1, neis_code="7569013", edu_office_code="J10", name="귀인초등학교")


def test_parse_real_response_saturday_closure_is_not_a_holiday():
    days = parse_schedule(REAL)
    assert CalendarDay(date(2026, 9, 24), "추석연휴", False) in days  # 공휴일
    assert [d.day for d in days if d.event_name == "토요휴업일"] == [date(2026, 9, 5), date(2026, 9, 12), date(2026, 9, 19)]
    assert not any(d.is_holiday for d in days)  # 토요휴업일은 SBTR_DD_SC_NM이 '휴업일'이어도 제외


def test_parse_flags_closure_day_only():
    got = {d.event_name: d.is_holiday for d in parse_schedule(CLOSURE)}
    # 재량휴업일은 학교에 따라 '휴업일'(율목초) 또는 '공휴일'(귀인초)로 오므로 이름으로도 판단.
    # 방학은 날짜별 '휴업일' 행으로 오지만 is_holiday가 아니라 is_vacation으로 따로 표시한다.
    assert got == {"학교장재량휴업일": True, "어린이날": False, "개교기념일": False, "여름방학": False}
    assert [d.day for d in parse_schedule(CLOSURE) if d.event_name == "학교장재량휴업일" and d.is_holiday] == [
        date(2026, 5, 4), date(2026, 11, 19)]


def test_parse_marks_vacation_separately():
    by = {d.event_name: d for d in parse_schedule(CLOSURE)}
    assert by["여름방학"] == CalendarDay(date(2026, 7, 25), "여름방학", False, True)
    assert not by["학교장재량휴업일"].is_vacation and not by["어린이날"].is_vacation


def test_parse_vacation_ceremony_days_are_school_days():
    """'여름방학식'·'여름개학식'은 학교가 열리는 날(해당없음)이라 방학이 아니다."""
    p = json.loads(json.dumps(CLOSURE))
    for r, name in zip(p["SchoolSchedule"][1]["row"][:2], ("여름방학식", "여름개학식")):
        r.update(EVENT_NM=name, SBTR_DD_SC_NM="해당없음")
    got = {d.event_name: d for d in parse_schedule(p)}
    assert not got["여름방학식"].is_vacation and not got["여름개학식"].is_vacation


def test_parse_no_result_returns_empty():
    assert parse_schedule({"RESULT": {"CODE": "INFO-200"}}) == []


def _client(pages):
    seen = []

    def h(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json=pages[int(req.url.params["pIndex"]) - 1])
    return httpx.Client(transport=httpx.MockTransport(h)), seen


def _page(n, start=301):
    row = REAL["SchoolSchedule"][1]["row"][0]
    return {"SchoolSchedule": [{"head": []}, {"row": [dict(row, AA_YMD=f"2026{(start + i):04d}") for i in range(n)]}]}


def test_fetch_paginates_with_key_and_school(monkeypatch):
    monkeypatch.setattr("eduapp_batch.neis_calendar.PAGE", 2)
    client, seen = _client([_page(2, 301), _page(1, 303)])
    days = fetch_schedule(SCHOOL, "K", date(2026, 3, 1), date(2027, 2, 28), client=client)
    assert len(days) == 3 and [p["pIndex"] for p in seen] == ["1", "2"]
    assert seen[0]["KEY"] == "K" and seen[0]["SD_SCHUL_CODE"] == "7569013" and seen[0]["ATPT_OFCDC_SC_CODE"] == "J10"
    assert seen[0]["AA_FROM_YMD"] == "20260301" and seen[0]["AA_TO_YMD"] == "20270228"


def test_fetch_raises_on_auth_error():
    client, _ = _client([{"RESULT": {"CODE": "INFO-300", "MESSAGE": "인증키가 유효하지 않습니다."}}])
    with pytest.raises(RuntimeError, match="INFO-300"):
        fetch_schedule(SCHOOL, "bad", date(2026, 3, 1), date(2027, 2, 28), client=client)


def test_fetch_detects_sample_key_truncation():
    """키가 없으면 나이스가 5건만 주고 list_total_count는 전체를 알린다 → 조용히 일부만 저장하지 않는다."""
    p = _page(5)
    p["SchoolSchedule"][0]["head"] = [{"list_total_count": 165}, {"RESULT": {"CODE": "INFO-000"}}]
    client, _ = _client([p])
    with pytest.raises(RuntimeError, match="165"):
        fetch_schedule(SCHOOL, "", date(2026, 3, 1), date(2027, 2, 28), client=client)


def test_pgstore_calendar_upsert_updates_holiday_flag(db):
    sid = db.execute("insert into schools (neis_code, edu_office_code, name, sido) values ('7569013','J10','귀인초등학교','경기') returning id").fetchone()[0]
    store = PgStore(db)
    store.upsert_school_calendar(sid, [CalendarDay(date(2026, 5, 4), "학교장재량휴업일", False)])
    store.upsert_school_calendar(sid, [CalendarDay(date(2026, 5, 4), "학교장재량휴업일", True),
                                       CalendarDay(date(2026, 7, 25), "여름방학", False, True)])
    assert db.execute("select day, event_name, is_holiday, is_vacation from school_calendar order by day").fetchall() == [
        (date(2026, 5, 4), "학교장재량휴업일", True, False), (date(2026, 7, 25), "여름방학", False, True)]


def test_pgstore_schools_with_children_lists_only_registered_schools(db):
    db.execute("insert into auth.users values ('00000000-0000-0000-0000-0000000000a1')")
    a = db.execute("insert into schools (neis_code, edu_office_code, name, sido) values ('1','J10','가초','경기') returning id").fetchone()[0]
    db.execute("insert into schools (neis_code, edu_office_code, name, sido) values ('2','J10','나초','경기')")
    db.execute("insert into children (parent_id, nickname, school_id, grade) values ('00000000-0000-0000-0000-0000000000a1','a',%s,3)", (a,))
    db.execute("insert into children (parent_id, nickname, school_id, grade) values ('00000000-0000-0000-0000-0000000000a1','b',%s,4)", (a,))
    assert PgStore(db).schools_with_children() == [SchoolRef(a, "1", "J10", "가초")]  # 자녀 둘이어도 학교는 한 번


def test_reststore_calendar_upsert_and_schools_with_children():
    seen = []

    def h(req):
        seen.append(req)
        if req.method == "GET":
            return httpx.Response(200, json=[{"id": 7, "neis_code": "9", "edu_office_code": "J10", "name": "다초", "children": [{"id": 1}]}])
        return httpx.Response(201)
    s = RestStore("https://p.supabase.co", "sb_secret_x", client=httpx.Client(transport=httpx.MockTransport(h), base_url="https://p.supabase.co"))
    assert s.schools_with_children() == [SchoolRef(7, "9", "J10", "다초")]
    g = seen[0]
    assert g.url.path == "/rest/v1/schools" and "children!inner" in g.url.params["select"]
    assert s.upsert_school_calendar(7, [CalendarDay(date(2026, 5, 4), "학교장재량휴업일", True)]) == 1
    p = seen[1]
    assert p.url.path == "/rest/v1/school_calendar" and p.url.params["on_conflict"] == "school_id,day,event_name"
    assert json.loads(p.content) == [{"school_id": 7, "day": "2026-05-04", "event_name": "학교장재량휴업일",
                                      "is_holiday": True, "is_vacation": False}]
