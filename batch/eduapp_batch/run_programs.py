"""기관 프로그램 수집 실행: python -m eduapp_batch.run_programs"""
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import date, datetime

import httpx
import psycopg

from .collectors import COLLECTORS, Collector
from .parse import KST
from .store import PgStore, RestStore


def run(store, collectors: dict[str, Collector], fetch: Callable[[str], str], today: date) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for key, c in collectors.items():
        try:
            with store.transaction():  # 기관마다 따로 커밋: 한 곳 실패가 다른 곳을 되돌리지 않게
                programs = list({p.source_id: p for p in c.collect(fetch, today)}.values())  # 여러 달 목록 중복 제거
                count = store.upsert_programs(store.ensure_institution(c.institution), programs)
            store.record_run(key, True, count, None)
            result[key] = count
        except Exception as e:  # noqa: BLE001 — 실패는 기록하고 다음 기관으로
            msg = f"{type(e).__name__}: {e}"
            store.record_run(key, False, None, msg)
            result[key] = msg
    return result


def _fetch(url: str, tries: int = 3) -> str:
    return _get(url, tries).text


def _get(url: str, tries: int = 3) -> httpx.Response:
    for i in range(tries):
        try:
            r = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "eduApp-collector"})
            r.raise_for_status()
            return r
        except httpx.TransportError:  # 연결 끊김 등 일시 오류만 재시도
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))


def main() -> int:
    today = datetime.now(KST).date()
    if os.environ.get("SUPABASE_URL"):
        result = run(RestStore(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]),
                     COLLECTORS, _fetch, today)
    else:
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
            result = run(PgStore(conn), COLLECTORS, _fetch, today)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result and all(isinstance(v, str) for v in result.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
