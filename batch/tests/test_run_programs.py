from datetime import date

from eduapp_batch.models import Institution, Program
from eduapp_batch.run_programs import run

TODAY = date(2026, 11, 6)


class Fake:
    def __init__(self, key, programs=None, error=None):
        self.institution = Institution(key=key, name=key, sido="서울", sigungu=None, homepage_url="https://x")
        self._programs, self._error = programs or [], error

    def collect(self, fetch, today):
        fetch(f"https://x/{self.institution.key}")
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


def test_fetch_retries_transient_errors(monkeypatch):
    import httpx
    from eduapp_batch import run_programs
    calls = []

    def flaky_get(url, **kw):
        calls.append(url)
        if len(calls) < 3:
            raise httpx.ConnectError("reset")
        return httpx.Response(200, text="ok", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", flaky_get)
    monkeypatch.setattr(run_programs.time, "sleep", lambda s: None)
    assert run_programs._fetch("https://x") == "ok" and len(calls) == 3
