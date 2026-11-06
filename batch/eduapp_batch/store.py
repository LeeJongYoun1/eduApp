"""수집 결과를 DB에 저장. 같은 프로그램을 다시 넣으면 내용만 갱신된다."""
import contextlib
import json
from dataclasses import asdict, fields
from datetime import date, datetime, timezone

import httpx

from .models import Institution, Program, School

_COLS = [f.name for f in fields(Program)]


def ensure_institution(conn, inst: Institution) -> int:
    return conn.execute(
        """insert into institutions (key, name, sido, sigungu, homepage_url)
           values (%(key)s, %(name)s, %(sido)s, %(sigungu)s, %(homepage_url)s)
           on conflict (key) do update set name = excluded.name, sido = excluded.sido,
             sigungu = excluded.sigungu, homepage_url = excluded.homepage_url
           returning id""",
        asdict(inst),
    ).fetchone()[0]


def upsert_programs(conn, institution_id: int, programs: list[Program]) -> int:
    cols = ", ".join(_COLS)
    vals = ", ".join(f"%({c})s" for c in _COLS)
    updates = ", ".join(f"{c} = excluded.{c}" for c in _COLS if c != "source_id")
    sql = (f"insert into programs (institution_id, {cols}) values (%(institution_id)s, {vals}) "
           f"on conflict (institution_id, source_id) do update set {updates}, collected_at = now()")
    with conn.cursor() as cur:
        cur.executemany(sql, [asdict(p) | {"institution_id": institution_id} for p in programs])
    return len(programs)


def upsert_schools(conn, schools: list[School]) -> int:
    """보낸 컬럼만 갱신 — collect_status 등 수집 상태는 그대로 둔다."""
    with conn.cursor() as cur:
        cur.executemany(
            """insert into schools (neis_code, edu_office_code, name, sido, sigungu, homepage_url)
               values (%(neis_code)s, %(edu_office_code)s, %(name)s, %(sido)s, %(sigungu)s, %(homepage_url)s)
               on conflict (neis_code) do update set edu_office_code = excluded.edu_office_code,
                 name = excluded.name, sido = excluded.sido, sigungu = excluded.sigungu,
                 homepage_url = excluded.homepage_url""",
            [asdict(s) for s in schools])
    return len(schools)


def record_run(conn, target: str, ok: bool, item_count: int | None, error: str | None) -> None:
    conn.execute(
        "insert into collect_runs (target, ok, item_count, error) values (%s, %s, %s, %s)",
        (target, ok, item_count, error),
    )


class PgStore:
    """DB 직접 연결 (로컬 테스트, 직접 연결 가능한 환경)."""

    def __init__(self, conn):
        self.conn = conn

    def transaction(self):
        return self.conn.transaction()

    def ensure_institution(self, inst: Institution) -> int:
        return ensure_institution(self.conn, inst)

    def upsert_programs(self, institution_id: int, programs: list[Program]) -> int:
        return upsert_programs(self.conn, institution_id, programs)

    def upsert_schools(self, schools: list[School]) -> int:
        return upsert_schools(self.conn, schools)

    def record_run(self, target: str, ok: bool, item_count: int | None, error: str | None) -> None:
        record_run(self.conn, target, ok, item_count, error)


class RestStore:
    """Supabase REST(HTTPS) 저장. 클라우드 환경에서 DB 직접 연결이 막혀 있어 배치는 이 경로를 쓴다."""

    def __init__(self, url: str, key: str, client: httpx.Client | None = None):
        headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):  # 예전 JWT 형식 service_role 키는 Authorization도 필요
            headers["Authorization"] = f"Bearer {key}"
        self.client = client or httpx.Client(base_url=url, timeout=30)
        self.client.headers.update(headers)

    def transaction(self):
        return contextlib.nullcontext()  # REST는 요청 단위로 원자적

    def _post(self, table: str, rows: list[dict], prefer: str, **params) -> httpx.Response:
        r = self.client.post(f"/rest/v1/{table}", params=params, headers={"Prefer": prefer},
                             content=json.dumps(rows, default=_iso, ensure_ascii=False))
        r.raise_for_status()
        return r

    def ensure_institution(self, inst: Institution) -> int:
        r = self._post("institutions", [asdict(inst)], "resolution=merge-duplicates,return=representation",
                       on_conflict="key", select="id")
        return r.json()[0]["id"]

    def upsert_programs(self, institution_id: int, programs: list[Program]) -> int:
        now = datetime.now(timezone.utc)
        rows = [asdict(p) | {"institution_id": institution_id, "collected_at": now} for p in programs]
        if rows:
            self._post("programs", rows, "resolution=merge-duplicates,return=minimal",
                       on_conflict="institution_id,source_id")
        return len(rows)

    def upsert_schools(self, schools: list[School]) -> int:
        if schools:
            self._post("schools", [asdict(s) for s in schools], "resolution=merge-duplicates,return=minimal",
                       on_conflict="neis_code")
        return len(schools)

    def record_run(self, target: str, ok: bool, item_count: int | None, error: str | None) -> None:
        self._post("collect_runs", [{"target": target, "ok": ok, "item_count": item_count, "error": error}],
                   "return=minimal")


def _iso(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    raise TypeError(type(v))
