import psycopg
import pytest

from test_app_basics import U1, U2, add_user, as_user
from test_school_info import add_child, add_school


def apply(db, school, year=2026, grade=4, sem=1, subject="국어", code="[4국02-04]", unit="2. 서로 다른 의견", month=4, url="https://x"):
    db.execute("select apply_school_progress(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
               (school, year, grade, sem, subject, code, unit, month, url))


def test_apply_inserts_and_updates_in_place(db):
    s = add_school(db, "A")
    apply(db, s)
    apply(db, s, unit="2. 바뀐 단원", month=5)
    assert db.execute("select unit_title, month from school_progress").fetchall() == [("2. 바뀐 단원", 5)]


@pytest.mark.parametrize("kw", [
    {"code": "[abc]"}, {"month": 13}, {"month": 0}, {"sem": 3}, {"grade": 7}, {"unit": "  "}, {"unit": "가" * 61}, {"subject": " "}])
def test_apply_rejects_bad_input(db, kw):
    s = add_school(db, "A")
    with pytest.raises((psycopg.errors.RaiseException, psycopg.errors.CheckViolation)):
        apply(db, s, **kw)


def test_child_progress_scopes_to_child_school_grade_and_term(db):
    add_user(db, U1)
    s, other = add_school(db, "A"), add_school(db, "B")
    c = add_child(db, U1, s, 4)
    apply(db, s, month=6, code="[4국02-04]")
    apply(db, s, month=4, subject="수학", code="[4수01-01]", unit="1. 큰 수")
    apply(db, s, grade=3, code="[4국01-01]")        # 다른 학년
    apply(db, s, sem=2, code="[4국01-02]")          # 다른 학기
    apply(db, s, year=2025, code="[4국01-03]")      # 다른 학년도
    apply(db, other, code="[4국01-04]")             # 다른 학교
    as_user(db, U1)
    rows = db.execute("select subject, standard_code, unit_title, month from child_progress(%s, 2026, 1)", (c,)).fetchall()
    assert rows == [("수학", "[4수01-01]", "1. 큰 수", 4), ("국어", "[4국02-04]", "2. 서로 다른 의견", 6)]


def test_child_progress_requires_own_child(db):
    add_user(db, U1)
    add_user(db, U2)
    c = add_child(db, U1, add_school(db, "A"), 4)
    as_user(db, U2)
    with pytest.raises(psycopg.errors.RaiseException, match="not your child"):
        db.execute("select * from child_progress(%s, 2026, 1)", (c,))


def test_apply_not_executable_by_authenticated_or_anon(db):
    s = add_school(db, "A")
    add_user(db, U1)
    as_user(db, U1)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        apply(db, s)


def test_authenticated_can_read_but_not_write_progress(db):
    s = add_school(db, "A")
    apply(db, s)
    add_user(db, U1)
    as_user(db, U1)
    assert db.execute("select count(*) from school_progress").fetchone()[0] == 1
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("delete from school_progress")
