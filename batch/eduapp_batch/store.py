"""수집 결과를 DB에 저장. 같은 프로그램을 다시 넣으면 내용만 갱신된다."""
from dataclasses import asdict, fields

from .models import Institution, Program

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


def record_run(conn, target: str, ok: bool, item_count: int | None, error: str | None) -> None:
    conn.execute(
        "insert into collect_runs (target, ok, item_count, error) values (%s, %s, %s, %s)",
        (target, ok, item_count, error),
    )
