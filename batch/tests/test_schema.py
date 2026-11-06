import psycopg
import pytest


def add_institution(db, sido="경기"):
    return db.execute(
        "insert into institutions (key, name, sido, homepage_url) values ('t', '테스트관', %s, 'https://x') returning id",
        (sido,),
    ).fetchone()[0]


def test_upcoming_view_hides_ended(db):
    iid = add_institution(db)
    db.execute(
        "insert into programs (institution_id, source_id, title, url, ends_on) values "
        "(%s, 'a', '지난것', 'https://x/a', current_date - 1), (%s, 'b', '내일', 'https://x/b', current_date + 1)",
        (iid, iid),
    )
    assert [r[0] for r in db.execute("select title from upcoming_programs")] == ["내일"]


def test_sido_rejects_other_region(db):
    with pytest.raises(psycopg.errors.InvalidTextRepresentation):
        add_institution(db, "부산")


def test_anon_can_read_but_not_write(db):
    iid = add_institution(db)
    db.execute("set role anon")
    db.execute("select * from programs").fetchall()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute(
            "insert into programs (institution_id, source_id, title, url) values (%s, 'z', 'z', 'z')", (iid,)
        )


def test_grade_range_check(db):
    iid = add_institution(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "insert into programs (institution_id, source_id, title, url, grade_min, grade_max) "
            "values (%s, 'g', 'g', 'g', 5, 3)",
            (iid,),
        )
