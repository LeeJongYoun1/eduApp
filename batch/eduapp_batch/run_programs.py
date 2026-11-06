"""기관 프로그램 수집 실행: python -m eduapp_batch.run_programs"""
import json
import os
import sys
from collections.abc import Callable
from datetime import date, datetime

import httpx
import psycopg

from .collectors import COLLECTORS, Collector
from .parse import KST
from .store import ensure_institution, record_run, upsert_programs


def run(conn, collectors: dict[str, Collector], fetch: Callable[[str], str], today: date) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for key, c in collectors.items():
        try:
            with conn.transaction():  # 기관마다 따로 커밋: 한 곳 실패가 다른 곳을 되돌리지 않게
                programs = [p for url in c.list_urls for p in c.parse(fetch(url), url, today)]
                count = upsert_programs(conn, ensure_institution(conn, c.institution), programs)
            record_run(conn, key, True, count, None)
            result[key] = count
        except Exception as e:  # noqa: BLE001 — 실패는 기록하고 다음 기관으로
            msg = f"{type(e).__name__}: {e}"
            record_run(conn, key, False, None, msg)
            result[key] = msg
    return result


def _fetch(url: str) -> str:
    r = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "eduApp-collector"})
    r.raise_for_status()
    return r.text


def main() -> int:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        result = run(conn, COLLECTORS, _fetch, datetime.now(KST).date())
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result and all(isinstance(v, str) for v in result.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
