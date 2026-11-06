import json
from datetime import date, datetime

import httpx

from eduapp_batch.models import Institution, Program
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
