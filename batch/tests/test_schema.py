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


def test_upcoming_view_hides_closed_applications(db):
    iid = add_institution(db)
    db.execute(
        "insert into programs (institution_id, source_id, title, url, starts_on, apply_ends_at) values "
        "(%s, 'c', '접수마감', 'https://x/c', current_date + 1, now() - interval '1 day'), "
        "(%s, 'o', '접수중', 'https://x/o', current_date + 1, now() + interval '1 day'), "
        "(%s, 'n', '기간없음', 'https://x/n', current_date + 1, null)",
        (iid, iid, iid),
    )
    assert sorted(r[0] for r in db.execute("select title from upcoming_programs")) == ["기간없음", "접수중"]


def test_textbook_correction_rejects_mismatched_textbook(db):
    uid = "00000000-0000-0000-0000-00000000000a"
    db.execute("insert into auth.users values (%s)", (uid,))
    db.execute("insert into profiles (id) values (%s)", (uid,))
    db.execute("insert into schools (neis_code, edu_office_code, name, sido) values ('1', 'B10', '초', '서울')")
    db.execute("insert into children (parent_id, nickname, school_id, grade) values (%s, 'a', 1, 4)", (uid,))
    db.execute("insert into textbooks (subject, grade, publisher, title) values ('수학', 4, 'A', 'm'), ('과학', 4, 'A', 's')")
    db.execute("set role authenticated")
    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (uid,))
    with pytest.raises(psycopg.errors.RaiseException):
        db.execute("select correct_school_textbook(1, '과학', 1)")  # 수학 교과서를 과학으로
    db.execute("select correct_school_textbook(1, '과학', 2)")
