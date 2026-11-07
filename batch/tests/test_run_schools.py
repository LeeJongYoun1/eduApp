import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from pypdf import PdfWriter
from test_school_notices import HOME, make_fetch

from eduapp_batch import run_schools
from eduapp_batch.models import CalendarDay
from eduapp_batch.run_schools import apply, prepare
from eduapp_batch.school_notices import Attachment, Post

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 7)


def school(id, code, url=HOME, status="pending"):
    return {"id": id, "neis_code": code, "edu_office_code": "J10", "name": "학교" + code,
            "homepage_url": url, "collect_status": status}


class FakeStore:
    def __init__(self, collect=(), children=()):
        self.collect, self.children = list(collect), list(children)
        self.status, self.runs, self.saved, self.calendar = {}, [], [], {}

    def schools_to_collect(self, today):
        return self.collect

    def schools_with_children(self):
        return self.children

    def upsert_calendar(self, school_id, days):
        self.calendar[school_id] = days
        return len(days)

    def apply_textbook(self, school_id, grade, subject, publisher, source_url):
        if subject not in ("과학", "수학"):
            raise ValueError("invalid subject")
        self.saved.append((school_id, grade, subject, publisher, source_url))

    def set_school_status(self, school_id, status):
        self.status[school_id] = status

    def record_run(self, target, ok, item_count, error):
        self.runs.append((target, ok, item_count, error))


def blob(url):
    return (FX / ("sample.hwp" if url.endswith(".hwp") else "sample.pdf")).read_bytes()


def blank_pdf(url):
    import io
    w = PdfWriter()
    w.add_blank_page(100, 100)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def go(store, tmp_path, fetch=None, fetch_bytes=blob, sleep=lambda s: None):
    return prepare(store, fetch or make_fetch(), fetch_bytes, "K", tmp_path, TODAY, sleep=sleep)


def post(body="", atts=(("a.pdf", "https://x/a.pdf"),), title="교과서 선정"):
    return Post(title, "https://x/post", body, [Attachment(n, u) for n, u in atts])


def test_prepare_writes_text_and_meta(tmp_path):
    store = FakeStore([school(1, "A")])
    res = go(store, tmp_path)
    files = sorted((tmp_path / "A").glob("text_*.txt"))
    assert res["A"] == len(files) >= 1
    assert files[0].read_text().startswith("# ") and " | " in files[0].read_text().splitlines()[0]
    assert any("천재교육" in f.read_text() for f in files)
    meta = json.loads((tmp_path / "A" / "meta.json").read_text())
    assert meta["school_id"] == 1 and meta["source_url"].startswith(HOME)
    assert store.status == {}  # 상태는 그대로


def test_prepare_isolates_failures(tmp_path):
    store = FakeStore([school(1, "B", "https://bad.goeay.kr"), school(2, "A")])
    res = go(store, tmp_path)
    assert isinstance(res["A"], int) and "KeyError" in res["B"]
    assert store.status == {1: "failed"}
    assert ("school:B", False, None, res["B"]) in store.runs


def test_prepare_unsupported_and_missing_homepage_mark_not_found(tmp_path):
    store = FakeStore([school(1, "A", ""), school(2, "B", "https://example.com")])
    res = go(store, tmp_path)
    assert res == {"A": "홈페이지 주소 없음", "B": "지원하지 않는 홈페이지"}
    assert store.status == {1: "not_found", 2: "not_found"}
    assert ("school:A", False, None, "홈페이지 주소 없음") in store.runs


def test_no_notice_marks_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: [])
    store = FakeStore([school(1, "A")])
    assert go(store, tmp_path) == {"A": "교과서 선정 공지 없음"}
    assert store.status == {1: "not_found"}


def test_empty_text_marks_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: [post()])
    store = FakeStore([school(1, "A")])
    assert go(store, tmp_path, fetch_bytes=blank_pdf) == {"A": "첨부에서 글자를 읽지 못함"}
    assert store.status == {1: "not_found"}
    assert ("school:A", False, None, "첨부에서 글자를 읽지 못함") in store.runs


def test_all_downloads_failing_marks_failed_not_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: [post()])

    def down(url):
        raise httpx.ConnectError("reset")
    store = FakeStore([school(1, "A")])
    res = go(store, tmp_path, fetch_bytes=down)
    assert "ConnectError" in res["A"] and store.status == {1: "failed"}


def _down(url):
    raise httpx.ConnectError("reset")


def test_download_failures_with_no_attachment_text_mark_failed_even_with_body(tmp_path, monkeypatch):
    posts = [post("붙임 참조", [("a.pdf", "https://x/a.pdf"), ("b.pdf", "https://x/b.pdf")])]
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: posts)
    store = FakeStore([school(1, "A")])
    res = go(store, tmp_path, fetch_bytes=_down)
    assert "ConnectError" in res["A"] and store.status == {1: "failed"}
    assert not (tmp_path / "A").exists()


def test_body_alone_is_enough_when_post_has_no_attachments(tmp_path, monkeypatch):
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: [post("2026학년도 천재교육 과학", [])])
    store = FakeStore([school(1, "A")])
    assert go(store, tmp_path, fetch_bytes=_down) == {"A": 1}
    assert "(본문)" in (tmp_path / "A" / "text_1.txt").read_text().splitlines()[0]
    assert store.status == {}


def test_one_attachment_ok_and_one_failed_is_written(tmp_path, monkeypatch):
    posts = [post("", [("a.pdf", "https://x/a.pdf"), ("b.pdf", "https://x/b.pdf")])]
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: posts)

    def down(url):
        if url.endswith("b.pdf"):
            raise httpx.ConnectError("reset")
        return blob(url)
    store = FakeStore([school(1, "A")])
    assert go(store, tmp_path, fetch_bytes=down) == {"A": 1}
    assert store.status == {}


def test_prepare_throttles_between_schools_and_downloads(tmp_path, monkeypatch):
    posts = [post("", [("a.pdf", "https://x/a.pdf"), ("b.pdf", "https://x/b.pdf")])]
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: posts)
    sleeps = []
    go(FakeStore([school(1, "A"), school(2, "B")]), tmp_path, sleep=sleeps.append)
    assert sleeps.count(1.0) == 1 and sleeps.count(0.5) == 2


def test_prepare_caps_posts_and_attachments(tmp_path, monkeypatch):
    many = [post("", [(f"{i}_{j}.pdf", f"https://x/{i}_{j}.pdf") for j in range(3)], title=f"t{i}")
            for i in range(10)]
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: many)
    got = []
    go(FakeStore([school(1, "A")]), tmp_path, fetch_bytes=lambda u: got.append(u) or blob(u))
    assert len(got) == 12 and not any(u.startswith("https://x/8_") for u in got)


class BrokenStore(FakeStore):
    """record_run / set_school_status가 특정 학교(school_id 2)에서만 DB 오류를 낸다."""
    def record_run(self, target, ok, item_count, error):
        if target.endswith(":B"):
            raise RuntimeError("rest 503")
        super().record_run(target, ok, item_count, error)

    def set_school_status(self, school_id, status):
        if school_id == 2:
            raise RuntimeError("rest 503")
        super().set_school_status(school_id, status)


def test_prepare_db_error_on_one_school_does_not_stop_others(tmp_path, monkeypatch):
    monkeypatch.setattr(run_schools, "find_textbook_posts", lambda u, f: [])  # 모두 not_found 경로
    store = BrokenStore([school(1, "A"), school(2, "B"), school(3, "C")])
    res = go(store, tmp_path)
    assert res["A"] == res["C"] == "교과서 선정 공지 없음" and "rest 503" in res["B"]
    assert store.status == {1: "not_found", 3: "not_found"}


def test_prepare_db_error_inside_failure_handler_is_swallowed(tmp_path):
    store = BrokenStore([school(1, "B", "https://bad.goeay.kr"), school(2, "A")])
    res = go(store, tmp_path)  # B의 예외 처리 중 DB 호출도 실패
    assert "rest 503" in res["B"] and isinstance(res["A"], int)


def test_prepare_calendar_record_run_error_does_not_stop_run(tmp_path, monkeypatch):
    def fake(office, code, key, today):
        raise RuntimeError("neis down")
    monkeypatch.setattr(run_schools, "fetch_schedule", fake)
    store = BrokenStore([school(3, "C")], children=[school(1, "B"), school(2, "A")])
    go(store, tmp_path)
    assert (tmp_path / "C" / "meta.json").exists()
    assert ("calendar:A", False, None, "RuntimeError: neis down") in store.runs


def test_apply_db_error_on_one_school_does_not_stop_others(tmp_path):
    answer(tmp_path, "A", 1, {"items": [item()]})
    answer(tmp_path, "B", 2, {"items": [item()]})
    answer(tmp_path, "C", 3, {"items": [item()]})
    store = BrokenStore()
    res = apply(store, tmp_path)
    assert res["A"] == res["C"] == 1 and "rest 503" in res["B"]
    assert (tmp_path / "B").exists() and (tmp_path / "_done" / "C").exists()


def test_apply_malformed_answer_with_failing_record_run_continues(tmp_path):
    answer(tmp_path, "B", 2, "{not json")
    answer(tmp_path, "C", 3, {"items": [item()]})
    res = apply(BrokenStore(), tmp_path)
    assert isinstance(res["B"], str) and res["C"] == 1


def test_prepare_caps_schools_per_run(tmp_path):
    res = go(FakeStore([school(i, f"S{i:02d}") for i in range(25)]), tmp_path)
    assert len(res) == 20 and "S19" in res and "S20" not in res


def test_rerun_clears_old_text_files(tmp_path):
    (tmp_path / "A").mkdir()
    (tmp_path / "A" / "text_99.txt").write_text("old")
    go(FakeStore([school(1, "A")]), tmp_path)
    assert not (tmp_path / "A" / "text_99.txt").exists()


def test_rerun_deletes_stale_answer_json(tmp_path):
    (tmp_path / "A").mkdir()
    (tmp_path / "A" / "answer.json").write_text('{"items": []}')
    go(FakeStore([school(1, "A")]), tmp_path)
    assert not (tmp_path / "A" / "answer.json").exists() and (tmp_path / "A" / "meta.json").exists()


def test_prepare_refreshes_calendar_for_schools_with_children(tmp_path, monkeypatch):
    def fake(office, code, key, today):
        if code == "B":
            raise RuntimeError("neis down")
        return [CalendarDay(day=date(2026, 12, 25), event_name="성탄절", is_holiday=True)]
    monkeypatch.setattr(run_schools, "fetch_schedule", fake)
    store = FakeStore([school(3, "C")], children=[school(1, "A"), school(2, "B")])
    go(store, tmp_path)
    assert list(store.calendar) == [1]
    assert ("calendar:A", True, 1, None) in store.runs
    assert ("calendar:B", False, None, "RuntimeError: neis down") in store.runs
    assert (tmp_path / "C" / "meta.json").exists()  # 달력 실패가 교과서 수집을 막지 않음


# ---- apply ----

def answer(tmp_path, code="A", sid=1, content=None):
    d = tmp_path / code
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps({"school_id": sid, "source_url": "https://x/post"}))
    if content is not None:
        (d / "answer.json").write_text(content if isinstance(content, str) else json.dumps(content))
    return d


def item(grade=4, subject="과학", publisher=" 천재교육 ", certain=True):
    return {"grade": grade, "subject": subject, "publisher": publisher, "certain": certain}


def test_apply_saves_only_certain_items_and_marks_done(tmp_path):
    answer(tmp_path, content={"items": [item(), item(3, "수학", "동아", False)]})
    store = FakeStore()
    assert apply(store, tmp_path) == {"A": 1}
    assert store.saved == [(1, 4, "과학", "천재교육", "https://x/post")]
    assert store.status == {1: "done"} and ("school:A", True, 1, None) in store.runs


def test_apply_empty_items_marks_not_found(tmp_path):
    answer(tmp_path, content={"items": []})
    store = FakeStore()
    assert apply(store, tmp_path) == {"A": 0}
    assert store.status == {1: "not_found"}
    assert ("school:A", False, None, "답안에 확신하는 출판사 없음") in store.runs


def test_apply_skips_invalid_item_and_keeps_others(tmp_path):
    answer(tmp_path, content={"items": [item(subject="체육"), item(5, "수학", "동아")]})
    store = FakeStore()
    assert apply(store, tmp_path) == {"A": 1}
    assert [s[1:4] for s in store.saved] == [(5, "수학", "동아")]
    assert store.status == {1: "done"}
    assert any(r[0] == "school:A" and r[1] is False and "ValueError" in r[3] for r in store.runs)


@pytest.mark.parametrize("content", ["{not json", {"items": "x"}, {"items": [{"grade": "4"}]},
                                     {"items": [item(grade=True)]}, {"items": [item(certain="yes")]}, []])
def test_apply_malformed_answer_changes_nothing(tmp_path, content):
    d = answer(tmp_path, content=content)
    store = FakeStore()
    res = apply(store, tmp_path)
    assert isinstance(res["A"], str) and store.saved == [] and store.status == {}
    assert d.exists() and any(r[0] == "school:A" and r[1] is False for r in store.runs)


def test_apply_moves_processed_dirs_and_ignores_unanswered(tmp_path):
    answer(tmp_path, "A", 1, {"items": [item()]})
    answer(tmp_path, "B", 2)  # answer.json 없음
    (tmp_path / "_done" / "A").mkdir(parents=True)
    (tmp_path / "_done" / "A" / "old").write_text("x")
    apply(FakeStore(), tmp_path)
    assert not (tmp_path / "A").exists() and (tmp_path / "B").exists()
    assert (tmp_path / "_done" / "A" / "answer.json").exists() and not (tmp_path / "_done" / "A" / "old").exists()
    assert apply(FakeStore(), tmp_path) == {}
