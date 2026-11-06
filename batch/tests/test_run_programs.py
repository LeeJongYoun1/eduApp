from datetime import date

from eduapp_batch.models import Institution, Program
from eduapp_batch.run_programs import run

TODAY = date(2026, 11, 6)


class Fake:
    def __init__(self, key, programs=None, error=None, fail_after_parse=False):
        self.institution = Institution(key=key, name=key, sido="서울", sigungu=None, homepage_url="https://x")
        self.list_urls = [f"https://x/{key}"]
        self._programs, self._error = programs or [], error

    def parse(self, html, page_url, today):
        if self._error:
            raise ValueError(self._error)
        return self._programs


def fetch(url):
    return "<html></html>"


def test_one_collector_failure_does_not_stop_others(db):
    collectors = {"a": Fake("a", error="layout changed"),
                  "b": Fake("b", [Program(source_id="1", title="t", url="https://x/1")])}
    result = run(db, collectors, fetch, TODAY)
    assert result["b"] == 1
    assert "layout changed" in result["a"]
    assert db.execute("select count(*) from programs").fetchone()[0] == 1
    runs = db.execute("select target, ok from collect_runs order by target").fetchall()
    assert runs == [("a", False), ("b", True)]


def test_each_institution_commits_separately(db):
    collectors = {"b": Fake("b", [Program(source_id="1", title="t", url="https://x/1")]),
                  "a": Fake("a", error="boom")}
    run(db, collectors, fetch, TODAY)
    assert db.execute("select count(*) from programs").fetchone()[0] == 1


def test_fetch_error_is_recorded(db):
    def bad_fetch(url):
        raise ConnectionError("timeout")
    result = run(db, {"a": Fake("a")}, bad_fetch, TODAY)
    assert "timeout" in result["a"]
