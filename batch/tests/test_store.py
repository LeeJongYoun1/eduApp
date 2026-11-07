from datetime import date

import pytest

from eduapp_batch.models import CalendarDay, Institution, Program
from eduapp_batch.store import PgStore, ensure_institution, record_run, upsert_programs

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


def _school(db, code, status="not_requested", collected="null"):
    return db.execute(
        f"""insert into schools (neis_code, edu_office_code, name, sido, collect_status, last_collected_at)
            values (%s, 'J10', %s, '경기', %s, {collected}) returning id""",
        (code, "학교" + code, status)).fetchone()[0]


def test_schools_to_collect_selects_pending_failed_and_stale_done(db):
    ids = {
        "pending": _school(db, "1", "pending"),
        "failed": _school(db, "2", "failed"),
        "stale": _school(db, "3", "done", "now() - interval '331 days'"),
        "fresh": _school(db, "4", "done", "now() - interval '1 day'"),
        "none": _school(db, "5", "not_requested"),
        "nf": _school(db, "6", "not_found"),
    }
    rows = PgStore(db).schools_to_collect(date.today())
    assert sorted(r["id"] for r in rows) == sorted(ids[k] for k in ("pending", "failed", "stale"))
    assert set(rows[0]) == {"id", "neis_code", "edu_office_code", "name", "homepage_url", "collect_status"}


def test_schools_with_children_only(db):
    a, _ = _school(db, "1"), _school(db, "2")
    db.execute("insert into auth.users (id) values ('00000000-0000-0000-0000-000000000001')")
    for n in ("a", "b"):  # 같은 학교에 자녀 둘 -> 한 번만
        db.execute("insert into children (parent_id, nickname, school_id, grade) values "
                   "('00000000-0000-0000-0000-000000000001', %s, %s, 3)", (n, a))
    rows = PgStore(db).schools_with_children()
    assert [r["id"] for r in rows] == [a]


def test_upsert_calendar_is_idempotent(db):
    sid = _school(db, "1")
    days = [CalendarDay(date(2026, 12, 25), "성탄절", True), CalendarDay(date(2026, 12, 1), "시험", False)]
    s = PgStore(db)
    assert s.upsert_calendar(sid, days) == 2
    assert s.upsert_calendar(sid, days) == 2
    assert db.execute("select count(*) from school_calendar").fetchone()[0] == 2


def test_upsert_calendar_dedupes_and_keeps_holiday(db):
    sid = _school(db, "1")
    days = [CalendarDay(date(2026, 12, 25), "성탄절", False), CalendarDay(date(2026, 12, 25), "성탄절", True),
            CalendarDay(date(2026, 12, 25), "성탄절", False)]
    assert PgStore(db).upsert_calendar(sid, days) == 1
    assert db.execute("select is_holiday from school_calendar").fetchall() == [(True,)]
    assert PgStore(db).upsert_calendar(sid, []) == 0


def test_apply_textbook_and_set_status(db):
    sid = _school(db, "1", "pending")
    s = PgStore(db)
    s.apply_textbook(sid, 3, "수학", "천재교육", "https://s/n")
    assert db.execute("select grade, subject, source_url from school_textbooks").fetchall() == [
        (3, "수학", "https://s/n")]
    s.set_school_status(sid, "failed")
    assert db.execute("select collect_status, last_collected_at from schools").fetchone() == ("failed", None)
    s.set_school_status(sid, "done")
    status, at = db.execute("select collect_status, last_collected_at from schools").fetchone()
    assert status == "done" and at is not None
    with pytest.raises(ValueError):
        s.set_school_status(sid, "pending")
