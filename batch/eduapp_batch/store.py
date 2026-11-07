"""수집 결과를 DB에 저장. 같은 프로그램을 다시 넣으면 내용만 갱신된다."""
import contextlib
import json
from dataclasses import asdict, fields
from datetime import date, datetime, timedelta, timezone

import httpx

from .models import CalendarDay, Institution, Program, School
from .school_progress import ProgressRow

_COLS = [f.name for f in fields(Program)]
_SCHOOL_COLS = "id,neis_code,edu_office_code,name,homepage_url,collect_status"
_STATUSES = ("done", "failed", "not_found")
_STALE_DAYS = 330
_PROGRESS_DAYS = 30  # shortcut: 평가계획은 학기에 한두 번 올라오므로 30일마다 다시 본다, 놓치는 학교가 많으면 줄인다


def _cutoff(today: date) -> datetime:
    return datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=_STALE_DAYS)


def _progress_cutoff(today: date) -> datetime:
    return datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=_PROGRESS_DAYS)


def _dedupe(days: list[CalendarDay]) -> list[CalendarDay]:
    """같은 (day, event_name)이 한 번의 upsert에 두 번 들어가면 Postgres가 실패한다. 하나라도 휴업일이면 휴업일."""
    out: dict[tuple, CalendarDay] = {}
    for d in days:
        k = (d.day, d.event_name)
        out[k] = CalendarDay(d.day, d.event_name, d.is_holiday or (k in out and out[k].is_holiday))
    return list(out.values())


def _check_status(status: str) -> None:
    if status not in _STATUSES:
        raise ValueError(f"bad status: {status}")


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

    def _schools(self, where: str, params=()) -> list[dict]:
        cur = self.conn.execute(
            f"select {_SCHOOL_COLS} from schools s where {where} order by id", params)
        names = [c.name for c in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

    def schools_to_collect(self, today: date) -> list[dict]:
        return self._schools(
            "collect_status in ('pending', 'failed') or (collect_status = 'done' and "
            "(last_collected_at is null or last_collected_at < %s))", (_cutoff(today),))

    def schools_with_children(self) -> list[dict]:
        return self._schools("exists (select 1 from children c where c.school_id = s.id)")

    def upsert_calendar(self, school_id: int, days: list[CalendarDay]) -> int:
        rows = [(school_id, d.day, d.event_name, d.is_holiday) for d in _dedupe(days)]
        with self.conn.cursor() as cur:
            cur.executemany(
                """insert into school_calendar (school_id, day, event_name, is_holiday) values (%s, %s, %s, %s)
                   on conflict (school_id, day, event_name) do update set is_holiday = excluded.is_holiday""", rows)
        return len(rows)

    def schools_needing_progress(self, today: date) -> list[dict]:
        return self._schools(
            "exists (select 1 from children c where c.school_id = s.id) and "
            "(progress_collected_at is null or progress_collected_at < %s)", (_progress_cutoff(today),))

    def apply_progress(self, school_id: int, school_year: int, grade: int, semester: int, row: ProgressRow,
                       source_url: str | None) -> None:
        self.conn.execute("select apply_school_progress(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                          (school_id, school_year, grade, semester, row.subject, row.standard_code,
                           row.unit_title, row.month, source_url))

    def set_progress_collected(self, school_id: int) -> None:
        self.conn.execute("update schools set progress_collected_at = now() where id = %s", (school_id,))

    def apply_textbook(self, school_id: int, grade: int, subject: str, publisher: str,
                       source_url: str | None) -> None:
        self.conn.execute("select apply_school_textbook(%s, %s, %s, %s, %s)",
                          (school_id, grade, subject, publisher, source_url))

    def set_school_status(self, school_id: int, status: str) -> None:
        _check_status(status)
        self.conn.execute(
            "update schools set collect_status = %s, last_collected_at = case when %s = 'done' "
            "then now() else last_collected_at end where id = %s", (status, status, school_id))


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

    def _get(self, table: str, **params) -> list[dict]:
        r = self.client.get(f"/rest/v1/{table}", params=params)
        r.raise_for_status()
        return r.json()

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

    def schools_to_collect(self, today: date) -> list[dict]:
        cutoff = _cutoff(today).isoformat()
        return self._get("schools", select=_SCHOOL_COLS, order="id", **{"or": (
            f"(collect_status.in.(pending,failed),and(collect_status.eq.done,"
            f"or(last_collected_at.is.null,last_collected_at.lt.{cutoff})))")})

    def schools_with_children(self) -> list[dict]:
        rows = self._get("schools", select=_SCHOOL_COLS + ",children!inner(id)", order="id")
        return [{k: v for k, v in r.items() if k != "children"} for r in rows]

    def upsert_calendar(self, school_id: int, days: list[CalendarDay]) -> int:
        rows = [{"school_id": school_id, "day": d.day, "event_name": d.event_name, "is_holiday": d.is_holiday}
                for d in _dedupe(days)]
        if rows:
            self._post("school_calendar", rows, "resolution=merge-duplicates,return=minimal",
                       on_conflict="school_id,day,event_name")
        return len(rows)

    def schools_needing_progress(self, today: date) -> list[dict]:
        cutoff = _progress_cutoff(today).isoformat()
        rows = self._get("schools", select=_SCHOOL_COLS + ",children!inner(id)", order="id", **{"or": (
            f"(progress_collected_at.is.null,progress_collected_at.lt.{cutoff})")})
        return [{k: v for k, v in r.items() if k != "children"} for r in rows]

    def apply_progress(self, school_id: int, school_year: int, grade: int, semester: int, row: ProgressRow,
                       source_url: str | None) -> None:
        r = self.client.post("/rest/v1/rpc/apply_school_progress", content=json.dumps(
            {"p_school_id": school_id, "p_school_year": school_year, "p_grade": grade, "p_semester": semester,
             "p_subject": row.subject, "p_standard_code": row.standard_code, "p_unit_title": row.unit_title,
             "p_month": row.month, "p_source_url": source_url}, ensure_ascii=False))
        r.raise_for_status()

    def set_progress_collected(self, school_id: int) -> None:
        r = self.client.patch("/rest/v1/schools", params={"id": f"eq.{school_id}"},
                              headers={"Prefer": "return=minimal"},
                              content=json.dumps({"progress_collected_at": datetime.now(timezone.utc).isoformat()}))
        r.raise_for_status()

    def apply_textbook(self, school_id: int, grade: int, subject: str, publisher: str,
                       source_url: str | None) -> None:
        r = self.client.post("/rest/v1/rpc/apply_school_textbook", content=json.dumps(
            {"p_school_id": school_id, "p_grade": grade, "p_subject": subject,
             "p_publisher": publisher, "p_source_url": source_url}, ensure_ascii=False))
        r.raise_for_status()

    def set_school_status(self, school_id: int, status: str) -> None:
        _check_status(status)
        body = {"collect_status": status}
        if status == "done":
            body["last_collected_at"] = datetime.now(timezone.utc).isoformat()
        r = self.client.patch("/rest/v1/schools", params={"id": f"eq.{school_id}"},
                              headers={"Prefer": "return=minimal"}, content=json.dumps(body))
        r.raise_for_status()


def _iso(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    raise TypeError(type(v))
