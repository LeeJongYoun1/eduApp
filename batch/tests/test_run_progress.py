import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

from eduapp_batch import run_progress
from eduapp_batch.run_progress import MAX_SCHOOLS, run
from eduapp_batch.school_notices import Attachment, Post
from test_school_notices import HOME, prog_fetch

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 7)
NO_SLEEP = lambda s: None  # noqa: E731


def school(id, code, url=HOME):
    return {"id": id, "neis_code": code, "edu_office_code": "J10", "name": code, "homepage_url": url,
            "collect_status": "done"}


class FakeStore:
    def __init__(self, schools, fail_apply_for=(), fail_row=None):
        self.schools, self.applied, self.collected, self.runs = schools, [], [], []
        self.fail_apply_for, self.fail_row = set(fail_apply_for), fail_row

    def schools_needing_progress(self, today):
        return self.schools

    def apply_progress(self, school_id, school_year, grade, semester, row, source_url):
        if school_id in self.fail_apply_for or row.standard_code == self.fail_row:
            raise RuntimeError("db down" if school_id in self.fail_apply_for else "bad row")
        self.applied.append((school_id, school_year, grade, semester, row, source_url))

    def set_progress_collected(self, school_id):
        self.collected.append(school_id)

    def record_run(self, target, ok, item_count, error):
        self.runs.append((target, ok, item_count, error))


def hwpx(*lines: str) -> bytes:
    buf = io.BytesIO()
    paras = "".join(f"<hp:p><hp:run><hp:t>{x}</hp:t></hp:run></hp:p>" for x in lines)
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Contents/section0.xml", '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
                   f'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">{paras}</hs:sec>')
    return buf.getvalue()


def plan_bytes(unit="2. 서로 다른 의견", month="4월", grade=4) -> bytes:
    return hwpx(f"2026학년도 귀인초 {grade}학년 1학기 학생평가 계획", "국어", "[4국02-04] 설명", unit, "읽기", month)


def fixture_bytes(url_to_name):
    files = {"1학년": "assessment_1_1.hwp", "3학년": "assessment_3_1.hwpx", "4학년": "assessment_4_1.hwpx"}

    def fetch_bytes(url):
        name = url_to_name[url]
        for k, f in files.items():
            if k in name and "1학기" in name:
                return (FIX / f).read_bytes()
        return b""
    return fetch_bytes


def post(n, atts, title="2026학년도 1학기 학생평가계획"):
    return Post(title, f"{HOME}/kwiin-e/na/ntt/selectNttInfo.do?mi=1&bbsId=2800&nttSn={n}", "",
                [Attachment(name, f"https://x/{n}/{name}") for name in atts])


def go(store, fetch_bytes, sleep=NO_SLEEP, fetch=None):
    return run(store, fetch or prog_fetch(), fetch_bytes, TODAY, sleep)


def test_saves_rows_and_marks_collected():
    store = FakeStore([school(1, "A")])
    from eduapp_batch.school_notices import find_assessment_posts
    names = {a.url: a.name for p in find_assessment_posts(HOME, prog_fetch()) for a in p.attachments}
    result = go(store, fixture_bytes(names))
    assert result == {"A": 59}  # 1학년 13 + 3학년 23 + 4학년 23 행
    assert store.collected == [1] and len(store.applied) == 59
    assert {(g, s) for _, y, g, s, _, _ in store.applied} == {(1, 1), (3, 1), (4, 1)}
    assert store.runs == [("progress:A", True, 59, None)]


def test_later_post_overwrites_earlier_for_same_key(monkeypatch):
    posts = [post(1, ["a.hwpx"]), post(2, ["b.hwpx"])]
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: posts)
    data = {"https://x/1/a.hwpx": plan_bytes("2. 옛 단원", "4월"), "https://x/2/b.hwpx": plan_bytes("2. 새 단원", "5월")}
    store = FakeStore([school(1, "A")])
    assert go(store, data.__getitem__) == {"A": 1}
    (_, _, _, _, row, url), = store.applied
    assert (row.unit_title, row.month, url) == ("2. 새 단원", 5, posts[1].url)


def test_no_posts_marks_collected_with_reason(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [])
    store = FakeStore([school(1, "A")])
    assert go(store, lambda u: b"") == {"A": "평가계획 공지 없음"}
    assert store.collected == [1] and store.runs == [("progress:A", False, None, "평가계획 공지 없음")]


def test_missing_and_unsupported_homepage_are_collected_with_reason():
    store = FakeStore([school(1, "A", ""), school(2, "B", "https://x.sen.es.kr")])
    assert go(store, lambda u: b"") == {"A": "홈페이지 주소 없음", "B": "지원하지 않는 홈페이지"}
    assert store.collected == [1, 2]


def test_all_downloads_fail_does_not_mark_collected(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [post(1, ["a.hwpx", "b.hwpx"])])

    def down(url):
        raise ConnectionError("reset")
    store = FakeStore([school(1, "A")])
    out = go(store, down)
    assert out["A"].startswith("ConnectionError") and store.collected == []
    assert store.runs[0][:2] == ("progress:A", False)


def test_empty_text_records_reason(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [post(1, ["a.hwpx"])])
    store = FakeStore([school(1, "A")])
    assert go(store, lambda u: b"") == {"A": "첨부에서 글자를 읽지 못함"} and store.collected == [1]


def test_unreadable_format_records_reason(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [post(1, ["a.hwpx"])])
    store = FakeStore([school(1, "A")])
    assert go(store, lambda u: hwpx("그냥 안내문입니다")) == {"A": "평가계획 형식을 읽지 못함"}
    assert store.collected == [1]


def test_one_school_db_error_does_not_stop_others(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [post(1, ["a.hwpx"])])
    store = FakeStore([school(1, "A"), school(2, "B")], fail_apply_for=[1])
    out = go(store, lambda u: plan_bytes())
    assert out["A"].startswith("RuntimeError") and out["B"] == 1
    assert store.collected == [2]


def test_rejected_row_is_skipped_and_noted(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [post(1, ["a.hwpx"])])
    data = hwpx("2026학년도 귀인초 4학년 1학기 학생평가 계획", "[4국02-04] 설명", "2. 단원", "4월",
                "[4수01-01] 설명", "1. 큰 수", "5월")
    store = FakeStore([school(1, "A")], fail_row="[4국02-04]")
    assert go(store, lambda u: data) == {"A": 1}
    assert store.runs[0][:3] == ("progress:A", True, 1) and "1" in store.runs[0][3]


def test_caps_at_max_schools_and_throttles(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [])
    sleeps = []
    store = FakeStore([school(i, f"S{i}") for i in range(MAX_SCHOOLS + 5)])
    out = go(store, lambda u: b"", sleep=sleeps.append)
    assert len(out) == MAX_SCHOOLS == 20 and sleeps.count(1.0) == MAX_SCHOOLS - 1


def test_download_pause_between_attachments(monkeypatch):
    monkeypatch.setattr(run_progress, "find_assessment_posts", lambda h, f: [post(1, ["a.hwpx", "b.hwpx", "c.hwpx"])])
    sleeps = []
    go(FakeStore([school(1, "A")]), lambda u: plan_bytes(), sleep=sleeps.append)
    assert sleeps == [0.5, 0.5]
