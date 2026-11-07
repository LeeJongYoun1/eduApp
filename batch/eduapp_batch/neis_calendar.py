"""자녀가 등록된 학교의 나이스 학사일정을 school_calendar에 저장: python -m eduapp_batch.neis_calendar"""
import json
import os
import sys
from datetime import date, datetime, timedelta

import httpx
import psycopg

from .models import CalendarDay, SchoolRef
from .parse import KST
from .store import PgStore, RestStore

URL = "https://open.neis.go.kr/hub/SchoolSchedule"
PAGE = 1000
DAYS_AHEAD = 180  # shortcut: 다음 학년도 일정은 보통 이 기간 안에 아직 없음, 학년도가 바뀌면 늘린다


def parse_schedule(payload: dict) -> list[CalendarDay]:
    if "SchoolSchedule" not in payload:  # 결과 없음: {"RESULT": {"CODE": "INFO-200"}}
        return []
    out = []
    for r in payload["SchoolSchedule"][1]["row"]:
        ymd = r["AA_YMD"]
        # 토요휴업일도 SBTR_DD_SC_NM이 '휴업일'로 오므로 제외해야 모든 토요일이 쉬는 날이 되지 않는다.
        closed = r.get("SBTR_DD_SC_NM") == "휴업일" and r["EVENT_NM"] != "토요휴업일"
        out.append(CalendarDay(date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])), r["EVENT_NM"], closed))
    return out


def fetch_schedule(school: SchoolRef, key: str, start: date, end: date,
                   client: httpx.Client | None = None) -> list[CalendarDay]:
    client = client or httpx.Client(timeout=30)
    days, page, total = [], 1, None
    while True:
        r = client.get(URL, params={"KEY": key, "Type": "json", "ATPT_OFCDC_SC_CODE": school.edu_office_code,
                                    "SD_SCHUL_CODE": school.neis_code, "AA_FROM_YMD": f"{start:%Y%m%d}",
                                    "AA_TO_YMD": f"{end:%Y%m%d}", "pIndex": page, "pSize": PAGE})
        r.raise_for_status()
        payload = r.json()
        if "SchoolSchedule" not in payload:
            if payload.get("RESULT", {}).get("CODE") != "INFO-200":
                raise RuntimeError(payload)  # 인증키 오류 등
            break
        head = payload["SchoolSchedule"][0]["head"]
        total = head[0]["list_total_count"] if head else total
        rows = parse_schedule(payload)
        days += rows
        if len(payload["SchoolSchedule"][1]["row"]) < PAGE:
            break
        page += 1
    if total is not None and len(days) < total:  # 키 없는 호출은 5건만 주고 전체 건수만 알려준다
        raise RuntimeError(f"incomplete: got {len(days)} of {total} (인증키 확인)")
    return days


def run(store, key: str, today: date, client: httpx.Client | None = None) -> dict[int, int | str]:
    result: dict[int, int | str] = {}
    for school in store.schools_with_children():
        try:
            with store.transaction():
                days = fetch_schedule(school, key, today, today + timedelta(days=DAYS_AHEAD), client)
                count = store.upsert_school_calendar(school.id, days)
            store.record_run(f"calendar:{school.id}", True, count, None)
            result[school.id] = count
        except Exception as e:  # noqa: BLE001 — 한 학교 실패가 다른 학교를 막지 않게
            msg = f"{type(e).__name__}: {e}"
            store.record_run(f"calendar:{school.id}", False, None, msg)
            result[school.id] = msg
    return result


def main() -> int:
    key = os.environ["NEIS_API_KEY"]
    today = datetime.now(KST).date()
    if os.environ.get("SUPABASE_URL"):
        result = run(RestStore(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]), key, today)
    else:
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
            result = run(PgStore(conn), key, today)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result and all(isinstance(v, str) for v in result.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
