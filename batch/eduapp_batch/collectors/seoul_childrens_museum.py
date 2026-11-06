"""서울상상나라 교육 — 전체 목록 HTML에서 신청 가능한 초등 나이 교육을 고르고, 상세에서 기간을 읽는다."""
import re
from datetime import date

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import parse_date, parse_grades

BASE = "https://www.seoulchildrensmuseum.org/education"
_RANGE = re.compile(r"(만\s*)?(\d+)\s*(?:세\s*)?[-~]\s*(\d+)\s*세")
_OVER = re.compile(r"(만\s*)?(\d+)\s*세\s*이상")


def age_grades(text: str) -> tuple[int, int] | None:
    """대상 나이("5세 이상", "8~10세")를 학년으로. 이 기관은 연 나이 표기(8세 = 초1, "8~10세(2017~2019년생)")."""
    if "초" in text:
        return parse_grades(text)
    if text.strip() == "누구나":
        return 1, 6
    if m := _RANGE.search(text):
        lo, hi = int(m[2]), int(m[3])
    elif m := _OVER.search(text):
        lo, hi = int(m[2]), 99
    else:  # "28 - 48개월", "성인"
        return None
    off = 6 if m[1] else 7  # 만 7세 = 초1
    lo, hi = max(1, lo - off), min(6, hi - off)
    return (lo, hi) if lo <= hi else None


def parse_list(html: str) -> dict[str, tuple[int, int]]:
    """신청 가능한 초등 대상 교육: {id: 학년}."""
    out = {}
    for li in BeautifulSoup(html, "html.parser").select("li.item"):
        a, cond, age = li.select_one("a[href*='educationView.do?id=']"), li.select_one(".condition"), li.select_one(".age")
        if not a or not cond or cond.get_text(strip=True) != "신청가능":
            continue
        if grades := age_grades(age.get_text(strip=True) if age else ""):
            out[a["href"].rsplit("=", 1)[1]] = grades
    return out


def parse_detail(html: str, program_id: str, grades: tuple[int, int], today: date) -> Program:
    s = BeautifulSoup(html, "html.parser")
    rows = {th.get_text(strip=True): " ".join(th.find_next_sibling("td").get_text(" ").split())
            for th in s.select(".group_reservation th[scope=row]")}
    # "2026.11.1 - 12.27 (주말, 공휴일)": 범위 구분이 '-'라 parse_date_range를 쓸 수 없다
    parts = re.split(r"\s+-\s+|~", rows.get("기간", ""), maxsplit=1)
    start = parse_date(parts[0], today)
    end = parse_date(parts[-1], today) if len(parts) > 1 else start
    if start and end and end < start:
        end = end.replace(year=start.year + 1)
    intro = s.select_one(".group_reservation_tit > p:not(.condition)")
    return Program(
        source_id=program_id,
        title=s.select_one(".group_reservation_tit h2").get_text(strip=True),
        url=f"{BASE}/educationView.do?id={program_id}",
        description=" ".join(intro.get_text(" ").split())[:500] or None if intro else None,
        grade_min=grades[0], grade_max=grades[1],
        starts_on=start, ends_on=end,
        apply_starts_at=None, apply_ends_at=None,  # 회차별로 '수업 전일까지' 예약 — 기간이 따로 없다
        fee=rows.get("참가비") or None,
    )


class SeoulChildrensMuseum:
    institution = Institution(key="seoul_childrens_museum", name="서울상상나라", sido="서울",
                              sigungu="광진구", homepage_url="https://www.seoulchildrensmuseum.org")

    def collect(self, fetch, today: date) -> list[Program]:
        found = parse_list(fetch(f"{BASE}/educationList.do"))
        return [parse_detail(fetch(f"{BASE}/educationView.do?id={i}"), i, g, today) for i, g in found.items()]
