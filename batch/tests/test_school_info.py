import psycopg
import pytest

from test_app_basics import U1, U2, add_user, as_user


def add_school(db, code):
    return db.execute(
        "insert into schools (neis_code, edu_office_code, name, sido) values (%s, 'J10', %s, '경기') returning id",
        (code, code),
    ).fetchone()[0]


def add_child(db, uid, school, grade):
    return db.execute(
        "insert into children (parent_id, nickname, school_id, grade) values (%s, 'c', %s, %s) returning id",
        (uid, school, grade),
    ).fetchone()[0]


def apply(db, school, grade, subject, publisher, url="https://x"):
    db.execute("select apply_school_textbook(%s, %s, %s, %s, %s)", (school, grade, subject, publisher, url))


def test_apply_creates_textbook_and_school_row(db):
    s = add_school(db, "A")
    apply(db, s, 4, "과학", "천재교육")
    apply(db, s, 4, "과학", "천재교육")
    assert db.execute("select confidence::text, source::text, source_url from school_textbooks").fetchall() == [
        ("confirmed", "auto", "https://x")]
    assert db.execute("select count(*) from textbooks").fetchone()[0] == 1


@pytest.mark.parametrize("grade,subject,publisher", [
    (4, "체육", "천재교육"), (2, "과학", "천재교육"), (4, "과학", "  "), (4, "과학", "가" * 21)])
def test_apply_rejects_bad_input(db, grade, subject, publisher):
    s = add_school(db, "A")
    with pytest.raises(psycopg.errors.RaiseException):
        apply(db, s, grade, subject, publisher)


def test_batch_does_not_overwrite_parent(db):
    add_user(db, U1)
    s = add_school(db, "A")
    c = add_child(db, U1, s, 4)
    as_user(db, U1)
    db.execute("select correct_school_publisher(%s, '과학', '비상교육')", (c,))
    db.execute("reset role")
    apply(db, s, 4, "과학", "천재교육")
    assert db.execute(
        "select t.publisher, st.source::text from school_textbooks st join textbooks t on t.id = st.textbook_id"
    ).fetchall() == [("비상교육", "parent")]


def test_correct_requires_own_child(db):
    add_user(db, U1)
    add_user(db, U2)
    c = add_child(db, U1, add_school(db, "A"), 4)
    as_user(db, U2)
    with pytest.raises(psycopg.errors.RaiseException, match="not your child"):
        db.execute("select correct_school_publisher(%s, '과학', '비상교육')", (c,))


def test_child_textbooks_uses_school_row_then_guess(db):
    add_user(db, U1)
    a, b, c_, d = (add_school(db, k) for k in "ABCD")
    apply(db, a, 4, "과학", "천재교육")
    apply(db, b, 4, "과학", "천재교육")
    apply(db, c_, 4, "과학", "비상교육")
    ca, cd = add_child(db, U1, a, 4), add_child(db, U1, d, 4)
    as_user(db, U1)
    q = "select subject, publisher, confidence::text, is_guess from child_textbooks(%s)"
    rows = db.execute(q, (cd,)).fetchall()
    assert [r[0] for r in rows] == ["수학", "사회", "과학", "영어"]
    assert rows[2] == ("과학", "천재교육", "unverified", True)
    assert rows[0][1] is None
    assert db.execute(q, (ca,)).fetchall()[2] == ("과학", "천재교육", "confirmed", False)


def parent_fix(db, uid, school, publisher):
    c = add_child(db, uid, school, 4)
    as_user(db, uid)
    db.execute("select correct_school_publisher(%s, '과학', %s)", (c, publisher))
    db.execute("reset role")


def test_guess_ignores_parent_typed_values(db):
    add_user(db, U1)
    a, b, c_, d, target = (add_school(db, k) for k in "ABCDE")
    for sch in (a, b, c_):
        parent_fix(db, U1, sch, "오타출판")  # 학부모가 입력한 값이 다수
    apply(db, d, 4, "과학", "천재교육")  # 배치 값은 소수
    ct = add_child(db, U1, target, 4)
    as_user(db, U1)
    assert db.execute("select publisher, is_guess from child_textbooks(%s)", (ct,)).fetchall()[2] == ("천재교육", True)


def test_guess_is_null_when_only_parent_values_exist(db):
    add_user(db, U1)
    a, target = add_school(db, "A"), add_school(db, "B")
    parent_fix(db, U1, a, "오타출판")
    ct = add_child(db, U1, target, 4)
    as_user(db, U1)
    assert db.execute("select publisher, is_guess from child_textbooks(%s)", (ct,)).fetchall()[2] == (None, False)


def test_child_textbooks_empty_for_grade_under_3(db):
    add_user(db, U1)
    c = add_child(db, U1, add_school(db, "A"), 2)
    as_user(db, U1)
    assert db.execute("select * from child_textbooks(%s)", (c,)).fetchall() == []


def test_child_textbooks_requires_own_child(db):
    add_user(db, U1)
    add_user(db, U2)
    c = add_child(db, U1, add_school(db, "A"), 4)
    as_user(db, U2)
    with pytest.raises(psycopg.errors.RaiseException, match="not your child"):
        db.execute("select * from child_textbooks(%s)", (c,))


def test_batch_functions_not_callable_by_app(db):
    as_user(db, U1)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("select apply_school_textbook(1, 4, '과학', '천재교육', null)")
