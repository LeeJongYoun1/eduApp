"""서울·경기 초등학교 목록을 나이스 Open API에서 받아 schools에 저장: python -m eduapp_batch.schools_list"""
import json
import os
import sys

import httpx
import psycopg

from .models import School
from .store import PgStore, RestStore

URL = "https://open.neis.go.kr/hub/schoolInfo"
OFFICES = {"B10": "서울", "J10": "경기"}
SIDO = {"서울특별시": "서울", "경기도": "경기"}
PAGE = 1000


def parse_school_info(payload: dict) -> list[School]:
    if "schoolInfo" not in payload:  # 결과 없음: {"RESULT": {"CODE": "INFO-200"}}
        return []
    out = []
    for r in payload["schoolInfo"][1]["row"]:
        sido = SIDO.get(r["LCTN_SC_NM"])
        if not sido or not r["SD_SCHUL_CODE"].strip():  # 신설 예정 학교는 코드가 공백이라 건너뜀
            continue
        parts = (r.get("ORG_RDNMA") or "").split()
        homepage = (r.get("HMPG_ADRES") or "").strip()
        out.append(School(neis_code=r["SD_SCHUL_CODE"], edu_office_code=r["ATPT_OFCDC_SC_CODE"], name=r["SCHUL_NM"],
                          sido=sido, sigungu=parts[1] if len(parts) > 1 else None,
                          homepage_url=homepage if homepage.rstrip("/") not in ("", "http:", "https:") else None))
    return out


def fetch_office(office: str, key: str) -> list[School]:
    schools, page = [], 1
    while True:
        r = httpx.get(URL, timeout=30, params={"KEY": key, "Type": "json", "ATPT_OFCDC_SC_CODE": office,
                                               "SCHUL_KND_SC_NM": "초등학교", "pIndex": page, "pSize": PAGE})
        r.raise_for_status()
        payload = r.json()
        if "schoolInfo" not in payload and payload.get("RESULT", {}).get("CODE") != "INFO-200":
            raise RuntimeError(payload)  # 인증키 오류 등
        rows = parse_school_info(payload)
        schools += rows
        if "schoolInfo" not in payload or len(payload["schoolInfo"][1]["row"]) < PAGE:
            return schools
        page += 1


def main() -> int:
    key = os.environ["NEIS_API_KEY"]
    if os.environ.get("SUPABASE_URL"):
        store = RestStore(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        result = {o: store.upsert_schools(fetch_office(o, key)) for o in OFFICES}
    else:
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
            result = {o: PgStore(conn).upsert_schools(fetch_office(o, key)) for o in OFFICES}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
