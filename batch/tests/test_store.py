from datetime import date

from eduapp_batch.models import Institution, Program
from eduapp_batch.store import ensure_institution, record_run, upsert_programs

INST = Institution(key="gwacheon_science", name="국립과천과학관", sido="경기", sigungu="과천시",
                   homepage_url="https://example.org")


def test_upsert_is_idempotent(db):
    iid = ensure_institution(db, INST)
    progs = [Program(source_id="1", title="화석 탐험대", url="https://e/1", starts_on=date(2026, 11, 8)),
             Program(source_id="2", title="별자리 교실", url="https://e/2")]
    assert upsert_programs(db, iid, progs) == 2
    progs[0] = Program(source_id="1", title="화석 탐험대 (마감)", url="https://e/1")
    assert upsert_programs(db, iid, progs) == 2
    rows = db.execute("select source_id, title from programs order by source_id").fetchall()
    assert rows == [("1", "화석 탐험대 (마감)"), ("2", "별자리 교실")]


def test_ensure_institution_returns_same_id(db):
    assert ensure_institution(db, INST) == ensure_institution(db, INST)


def test_record_run_stores_error(db):
    record_run(db, "gwacheon_science", ok=False, item_count=None, error="boom")
    assert db.execute("select target, ok, error from collect_runs").fetchall() == [("gwacheon_science", False, "boom")]
