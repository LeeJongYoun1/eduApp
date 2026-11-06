"""한국잡월드 통합예약(개인) — 체험관별 상품 목록 API를 돌고, 상품 상세 API를 읽는다."""
import json
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..models import Institution, Program

BASE = "https://www.koreajobworld.or.kr"
# 통합예약 SPA의 체험관 구분(pdDiv) ↔ 상세 페이지 경로
EXP_DIVS = {"01": "child", "02": "teen", "03": "course", "08": "event", "09": "makive", "10": "skill", "20": "future"}


def list_url(pd_div: str) -> str:
    return f"{BASE}/api/product?pdDiv={pd_div}&pgDiv=P"  # P = 개인


def parse_list(text: str) -> list[int]:
    return [o["mrktnPdNo"] for o in json.loads(text)["response"]]


def parse_product(text: str, today: date) -> Program | None:
    p = json.loads(text)["response"]["product"]
    # target "01,E1,E2,M1,…": E1~E6 = 초1~초6
    grades = [int(c[1]) for c in (p.get("target") or "").split(",") if c[:1] == "E" and c[1:].isdigit()]
    if not grades or "학교방문형" in p["mrktnPdNm"]:
        return None
    start, end = date.fromisoformat(p["rvpossStartDt"]), date.fromisoformat(p["rvpossEndDt"])
    # 체험관 일반권·공방 클래스는 예약 가능일이 오늘부터 1년으로 굴러간다: 기간 있는 프로그램이 아니다
    if end >= today + timedelta(days=365):
        return None
    desc = " ".join(BeautifulSoup(p.get("salepdDtlExpl") or "", "html.parser").get_text(" ").split())
    fee = p.get("basePrice") or 0
    return Program(
        source_id=str(p["mrktnPdNo"]),
        title=p["mrktnPdNm"].strip(),
        url=f"{BASE}/reserve/ind/{EXP_DIVS[p['pdDiv']]}/{p['mrktnPdNo']}",
        description=desc[:500] or None,
        grade_min=min(grades), grade_max=max(grades),
        starts_on=start, ends_on=end,  # 예약 가능한 방문일 범위
        apply_starts_at=None, apply_ends_at=None,  # 회차별 상시 예약, 마감 시각 비공개
        fee=f"{fee:,}원" if fee else "무료",
    )


class KoreaJobWorld:
    institution = Institution(key="korea_job_world", name="한국잡월드", sido="경기",
                              sigungu="성남시", homepage_url=BASE)

    def collect(self, fetch, today: date) -> list[Program]:
        ids = dict.fromkeys(i for d in EXP_DIVS for i in parse_list(fetch(list_url(d))))
        found = (parse_product(fetch(f"{BASE}/api/product/{i}?pgDiv=P"), today) for i in ids)
        return [p for p in found if p]
