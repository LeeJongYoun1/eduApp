from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U1 = "00000000-0000-0000-0000-0000000000a1"
U2 = "00000000-0000-0000-0000-0000000000a2"


def add_user(db, uid):
    db.execute("insert into auth.users values (%s)", (uid,))


def add_inst(db, key, sido, sigungu):
    return db.execute(
        "insert into institutions (key, name, sido, sigungu, homepage_url) values (%s, %s, %s, %s, 'https://x') returning id",
        (key, key, sido, sigungu),
    ).fetchone()[0]


def add_prog(db, iid, title, grade_min=None, grade_max=None, start=None, end=None, apply_end=None):
    """start/end: current_date 기준 일수 차이."""
    db.execute(
        "insert into programs (institution_id, source_id, title, url, grade_min, grade_max, starts_on, ends_on, apply_ends_at) "
        "values (%s, %s, %s, 'https://x', %s, %s, current_date + %s::int, current_date + %s::int, %s)",
        (iid, title, title, grade_min, grade_max, start, end, apply_end),
    )


def as_user(db, uid):
    db.execute("set role authenticated")
    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (uid,))


def titles(db, sql="select title from my_programs()", params=()):
    return sorted(r[0] for r in db.execute(sql, params))


def test_profile_created_on_signup(db):
    add_user(db, U1)
    assert db.execute("select is_operator from profiles where id = %s", (U1,)).fetchall() == [(False,)]


def test_my_programs_filters_by_region(db):
    add_user(db, U1)
    add_prog(db, add_inst(db, "g", "경기", "과천시"), "과천", end=5)
    add_prog(db, add_inst(db, "s", "서울", "용산구"), "용산", end=5)
    db.execute("insert into user_regions values (%s, '경기', '과천시')", (U1,))
    as_user(db, U1)
    assert titles(db) == ["과천"]
    db.execute("insert into user_regions values (%s, '서울', '')", (U1,))
    assert titles(db) == ["과천", "용산"]


def test_my_programs_filters_by_grade(db):
    add_user(db, U1)
    iid = add_inst(db, "g", "경기", "과천시")
    add_prog(db, iid, "A", 3, 4, end=5)
    add_prog(db, iid, "B", 5, 6, end=5)
    add_prog(db, iid, "C", end=5)
    db.execute("insert into user_regions values (%s, '경기', '')", (U1,))
    as_user(db, U1)
    assert titles(db, "select title from my_programs(p_grade => 4)") == ["A", "C"]


def test_my_programs_filters_by_dates(db):
    add_user(db, U1)
    iid = add_inst(db, "g", "경기", "과천시")
    add_prog(db, iid, "A", start=1, end=2)
    add_prog(db, iid, "B", start=8, end=9)
    db.execute(
        "insert into programs (institution_id, source_id, title, url, apply_ends_at) "
        "values (%s, 'C', 'C', 'https://x', now() + interval '1 day')", (iid,))
    db.execute("insert into user_regions values (%s, '경기', '')", (U1,))
    as_user(db, U1)
    assert titles(db, "select title from my_programs(p_from => current_date + 1, p_to => current_date + 2)") == ["A", "C"]


def test_my_programs_hides_closed(db):
    add_user(db, U1)
    add_prog(db, add_inst(db, "g", "경기", "과천시"), "지난것", 4, 4, start=-3, end=-1)
    db.execute("insert into user_regions values (%s, '경기', '')", (U1,))
    as_user(db, U1)
    assert titles(db, "select title from my_programs(p_grade => 4)") == []


def test_my_programs_other_user_regions_ignored(db):
    add_user(db, U1)
    add_user(db, U2)
    add_prog(db, add_inst(db, "g", "경기", "과천시"), "과천", end=5)
    db.execute("insert into user_regions values (%s, '경기', '')", (U2,))
    as_user(db, U1)
    assert titles(db) == []


def test_schema_sql_matches_migrations():
    migrations = sorted((ROOT / "supabase/migrations").glob("*.sql"))
    assert (ROOT / "supabase/schema.sql").read_text() == "".join(m.read_text() for m in migrations)
