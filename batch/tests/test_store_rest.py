import json
from datetime import date, datetime

import httpx
import pytest

from eduapp_batch.models import CalendarDay, Institution, Program
from eduapp_batch.parse import KST
from eduapp_batch.store import RestStore

INST = Institution(key="k", name="관", sido="서울", sigungu=None, homepage_url="https://x")


def store_with(handler):
    seen = []

    def h(req):
        seen.append(req)
        return handler(req)
    client = httpx.Client(transport=httpx.MockTransport(h), base_url="https://p.supabase.co")
    return RestStore("https://p.supabase.co", "sb_secret_x", client=client), seen


def test_ensure_institution_upserts_on_key_and_returns_id():
    s, seen = store_with(lambda r: httpx.Response(201, json=[{"id": 7}]))
    assert s.ensure_institution(INST) == 7
    r = seen[0]
    assert r.url.path == "/rest/v1/institutions" and r.url.params["on_conflict"] == "key"
    assert "resolution=merge-duplicates" in r.headers["Prefer"] and r.headers["apikey"] == "sb_secret_x"
    assert json.loads(r.content)[0]["key"] == "k"


def test_upsert_programs_serializes_dates_and_sets_collected_at():
    s, seen = store_with(lambda r: httpx.Response(201))
    p = Program(source_id="1", title="t", url="u", starts_on=date(2026, 11, 8),
                apply_ends_at=datetime(2026, 11, 26, 23, 59, tzinfo=KST))
    assert s.upsert_programs(7, [p]) == 1
    r = seen[0]
    assert r.url.params["on_conflict"] == "institution_id,source_id"
    row = json.loads(r.content)[0]
    assert row["institution_id"] == 7 and row["starts_on"] == "2026-11-08"
    assert row["apply_ends_at"] == "2026-11-26T23:59:00+09:00" and "collected_at" in row


def test_http_error_raises():
    s, _ = store_with(lambda r: httpx.Response(400, json={"message": "bad"}))
    try:
        s.record_run("k", False, None, "x")
    except httpx.HTTPStatusError:
        return
    raise AssertionError("expected HTTPStatusError")


COLS = "id,neis_code,edu_office_code,name,homepage_url,collect_status"


def test_schools_to_collect_sends_status_and_cutoff_filter():
    s, seen = store_with(lambda r: httpx.Response(200, json=[{"id": 1}]))
    assert s.schools_to_collect(date(2026, 11, 7)) == [{"id": 1}]
    r = seen[0]
    assert r.method == "GET" and r.url.path == "/rest/v1/schools" and r.url.params["select"] == COLS
    assert r.url.params["or"] == ("(collect_status.in.(pending,failed),and(collect_status.eq.done,"
                                  "or(last_collected_at.is.null,last_collected_at.lt.2025-12-12T00:00:00+00:00)))")


def test_schools_with_children_embeds_and_strips_children():
    s, seen = store_with(lambda r: httpx.Response(200, json=[{"id": 1, "name": "a", "children": [{"id": 9}]}]))
    assert s.schools_with_children() == [{"id": 1, "name": "a"}]
    r = seen[0]
    assert r.url.path == "/rest/v1/schools" and r.url.params["select"] == COLS + ",children!inner(id)"


def test_upsert_calendar_dedupes_and_upserts_on_pk():
    s, seen = store_with(lambda r: httpx.Response(201))
    days = [CalendarDay(date(2026, 12, 25), "성탄절", False), CalendarDay(date(2026, 12, 25), "성탄절", True),
            CalendarDay(date(2026, 12, 1), "시험", False)]
    assert s.upsert_calendar(5, days) == 2
    r = seen[0]
    assert r.url.path == "/rest/v1/school_calendar" and r.url.params["on_conflict"] == "school_id,day,event_name"
    assert json.loads(r.content) == [
        {"school_id": 5, "day": "2026-12-25", "event_name": "성탄절", "is_holiday": True},
        {"school_id": 5, "day": "2026-12-01", "event_name": "시험", "is_holiday": False}]
    assert s.upsert_calendar(5, []) == 0 and len(seen) == 1


def test_apply_textbook_calls_rpc_with_named_args():
    s, seen = store_with(lambda r: httpx.Response(204))
    s.apply_textbook(5, 3, "수학", "천재교육", None)
    r = seen[0]
    assert r.method == "POST" and r.url.path == "/rest/v1/rpc/apply_school_textbook"
    assert json.loads(r.content) == {"p_school_id": 5, "p_grade": 3, "p_subject": "수학",
                                     "p_publisher": "천재교육", "p_source_url": None}


def test_set_school_status_patches_by_id():
    s, seen = store_with(lambda r: httpx.Response(204))
    s.set_school_status(5, "failed")
    s.set_school_status(5, "done")
    assert [r.method for r in seen] == ["PATCH", "PATCH"] and seen[0].url.params["id"] == "eq.5"
    assert json.loads(seen[0].content) == {"collect_status": "failed"}
    body = json.loads(seen[1].content)
    assert body["collect_status"] == "done" and body["last_collected_at"].endswith("+00:00")
    with pytest.raises(ValueError):
        s.set_school_status(5, "pending")
    assert len(seen) == 2
