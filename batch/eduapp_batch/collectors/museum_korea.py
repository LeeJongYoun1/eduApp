"""국립중앙박물관 교육플랫폼 '모두' — 달력 API로 접수 중인 교육을 찾고, 상세 페이지를 읽는다."""
import json
from datetime import date, datetime, time, timedelta

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_date_range, parse_grades

BASE = "https://modu.museum.go.kr"
MUSEUMS = (1, 15)  # 1 = 국립중앙박물관, 15 = 국립중앙박물관 어린이 교육
MAX_DAYS = 35      # 달력 API는 35일 넘게 조회하면 400


def calendar_url(today: date) -> str:
    to = today + timedelta(days=MAX_DAYS)
    museums = "&".join(f"museum={m}" for m in MUSEUMS)
    return f"{BASE}/api/fo/learn/calendar?from={today}&to={to}&searchApplyStatus=ONGOING&{museums}"


def parse_calendar(text: str) -> list[int]:
    days = json.loads(text)["body"]["days"]
    return list(dict.fromkeys(p["id"] for d in days.values() for p in d["programs"]))


def parse_detail(html: str, program_id: int, today: date) -> Program | None:
    s = BeautifulSoup(html, "html.parser")
    rows = {th.get_text(strip=True): " ".join(th.find_next_sibling("td").get_text(" ").split())
            for th in s.select("th.detail_section_th")}
    # 교육그룹 "어린이(6~13세) | 청소년 , 단체": 쉼표 뒤가 신청 유형. 단체만 받는 교육은 학부모가 신청할 수 없다.
    if "개인" not in rows.get("교육그룹", "").rsplit(",", 1)[-1]:
        return None
    grades = parse_grades(rows.get("교육대상", ""))
    if not grades:
        return None
    _, apply_end = parse_date_range(rows.get("접수기간", ""), today)
    start, end = parse_date_range(rows.get("교육기간", ""), today)
    fee = rows.get("참가비", "").replace(",", "")
    return Program(
        source_id=str(program_id),
        title=s.title.get_text().split(" | ")[0].strip(),
        url=f"{BASE}/learn/detail/{program_id}",
        description=rows.get("주제/내용") or None,
        grade_min=grades[0], grade_max=grades[1],
        starts_on=start, ends_on=end,
        apply_starts_at=None,  # 접수 시작 시각을 표에 공개하지 않는다
        apply_ends_at=datetime.combine(apply_end, time(23, 59), KST) if apply_end else None,
        fee="무료" if fee in ("", "0") else f"{int(fee):,}원" if fee.isdigit() else rows["참가비"],
    )


class MuseumKorea:
    institution = Institution(key="museum_korea", name="국립중앙박물관", sido="서울",
                              sigungu="용산구", homepage_url="https://www.museum.go.kr")

    def collect(self, fetch, today: date) -> list[Program]:
        ids = parse_calendar(fetch(calendar_url(today)))
        found = (parse_detail(fetch(f"{BASE}/learn/detail/{i}"), i, today) for i in ids)
        return [p for p in found if p]
