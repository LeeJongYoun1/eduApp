"""국립한글박물관 교육 신청 — 접수중·접수예정 목록 HTML에서 '개별' 접수 초등 교육을 고르고, 상세에서 참가비를 읽는다."""
from dataclasses import replace
from datetime import date, datetime, time

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_date_range, parse_grades

BASE = "https://www.hangeul.go.kr/education"
MENU = "curr_menu_cd=0103010000"
OPEN, UPCOMING = 1, 2  # showGubun: 접수중, 접수예정


def list_url(show: int, page: int) -> str:
    return f"{BASE}?{MENU}&target=0&showGubun={show}&page={page}"


def parse_list(html: str, today: date) -> list[Program]:
    out = []
    for li in BeautifulSoup(html, "html.parser").select(".apply-list > ul > li"):
        # 머리 라벨 "초등 | 개별 | 온라인 접수 ...": 단체 교육은 학부모가 신청할 수 없다
        if "개별" not in [x.get_text(strip=True) for x in li.select(".head .label")]:
            continue
        rows = {dl.dt.get_text(strip=True): " ".join(dl.dd.get_text(" ").split()) for dl in li.select(".foot dl")}
        grades = parse_grades(rows.get("교육 대상", ""))
        if not grades:
            continue
        a = li.select_one(".go-view-page")
        no = a["data-program-no"]
        _, apply_end = parse_date_range(rows.get("신청 기간", ""), today)
        start, end = parse_date_range(rows.get("교육 기간", ""), today)
        out.append(Program(
            source_id=no,
            title=a.get_text(strip=True),
            url=f"{BASE}/view?{MENU}&programNo={no}",
            grade_min=grades[0], grade_max=grades[1],
            starts_on=start, ends_on=end,
            apply_starts_at=None,  # 접수 시작 시각은 본문 글로만 안내한다
            apply_ends_at=datetime.combine(apply_end, time(23, 59), KST) if apply_end else None,
        ))
    return out


def parse_fee(html: str) -> str | None:
    th = BeautifulSoup(html, "html.parser").find("th", string="참가비")
    return " ".join(th.find_next_sibling("td").get_text(" ").split()) or None if th else None


class HangeulMuseum:
    institution = Institution(key="hangeul_museum", name="국립한글박물관", sido="서울",
                              sigungu="용산구", homepage_url="https://www.hangeul.go.kr")

    def collect(self, fetch, today: date) -> list[Program]:
        progs = []
        for show in (OPEN, UPCOMING):
            for page in range(1, 20):  # 페이지당 10건, 마지막 다음 페이지는 비어 있다
                html = fetch(list_url(show, page))
                if "data-program-no" not in html:
                    break
                progs += parse_list(html, today)
        return [replace(p, fee=parse_fee(fetch(p.url))) for p in progs]
