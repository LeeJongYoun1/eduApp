"""나이스 학사일정(SchoolSchedule) 파서·수집기: 학교 휴업일·공휴일을 CalendarDay로 만든다."""
from datetime import date, datetime, timedelta

import httpx

from .models import CalendarDay

URL = "https://open.neis.go.kr/hub/SchoolSchedule"
PAGE = 1000
HOLIDAY_KINDS = {"휴업일", "공휴일"}
GRADE_FLAGS = ["ONE_GRADE_EVENT_YN", "TW_GRADE_EVENT_YN", "THREE_GRADE_EVENT_YN",
               "FR_GRADE_EVENT_YN", "FIV_GRADE_EVENT_YN", "SIX_GRADE_EVENT_YN"]


def parse_schedule(payload: dict) -> list[CalendarDay]:
    if "SchoolSchedule" not in payload:  # 결과 없음: {"RESULT": {"CODE": "INFO-200"}}
        return []
    out: dict[tuple[date, str], CalendarDay] = {}
    for r in payload["SchoolSchedule"][1]["row"]:
        if not any(r.get(f) == "Y" for f in GRADE_FLAGS):  # 1~6학년 대상이 아닌 행 제외
            continue
        day = datetime.strptime(r["AA_YMD"], "%Y%m%d").date()
        name = r["EVENT_NM"]
        out.setdefault((day, name), CalendarDay(day=day, event_name=name,
                                                is_holiday=r["SBTR_DD_SC_NM"] in HOLIDAY_KINDS and day.weekday() < 5))  # 주말은 원래 쉬는 날
    return list(out.values())


def fetch_schedule(edu_office_code: str, neis_code: str, key: str, today: date) -> list[CalendarDay]:
    days, page = [], 1
    while True:
        r = httpx.get(URL, timeout=30, params={
            "KEY": key, "Type": "json", "ATPT_OFCDC_SC_CODE": edu_office_code, "SD_SCHUL_CODE": neis_code,
            "AA_FROM_YMD": today.strftime("%Y%m%d"), "AA_TO_YMD": (today + timedelta(days=365)).strftime("%Y%m%d"),
            "pIndex": page, "pSize": PAGE})
        if r.is_error:  # raise_for_status의 예외 문구에는 KEY=가 든 요청 주소가 들어가므로 상태 코드만 남긴다
            raise RuntimeError(f"NEIS HTTP {r.status_code}")
        payload = r.json()
        if "SchoolSchedule" not in payload and payload.get("RESULT", {}).get("CODE") != "INFO-200":
            raise RuntimeError(payload)  # 인증키 오류 등
        days += parse_schedule(payload)
        if "SchoolSchedule" not in payload or len(payload["SchoolSchedule"][1]["row"]) < PAGE:
            return days
        page += 1
