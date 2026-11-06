"""서울역사박물관(분관 포함) 교육예약 게시판 — 접수 상태별 목록 HTML, 대상은 상세 페이지에서 읽는다."""
import re
from datetime import date, datetime, time

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_date_range, parse_grades

BASE = "https://museum.seoul.go.kr/www/board"
STATES = ("1001", "1002")  # 안내(접수 전), 접수중
# 모든 페이지가 서울시 SSO로 302된다. sso=ok를 붙이면 쿠키 없이 바로 본문을 준다.


def list_url(state: str) -> str:
    return f"{BASE}/NR_boardList.do?bbsCd=1005&q_applyState={state}&rowPerPage=50&sso=ok"


def parse_list(html: str, today: date) -> list[dict]:
    rows = []
    for tr in BeautifulSoup(html, "html.parser").select("#boardTbl tbody tr"):
        a = tr.select_one("a[onclick]")
        if not a:  # "데이터가 존재하지 않습니다."
            continue
        tds = [" ".join(td.get_text(" ").split()) for td in tr.select("td")]
        starts_on, ends_on = parse_date_range(tds[3], today)
        _, apply_ends_on = parse_date_range(tds[5], today)
        rows.append({"seq": re.findall(r"'(\d+)'", a["onclick"])[1], "title": " ".join(a.get_text().split()),
                     "starts_on": starts_on, "ends_on": ends_on, "apply_ends_on": apply_ends_on})
    return rows


def parse_detail(row: dict, html: str) -> Program | None:
    s = BeautifulSoup(html, "html.parser")
    cells = {th.get_text(strip=True): th.find_next_sibling("td") for th in s.select("table.tb_view th")}
    target = cells.get("대상")
    target = " ".join(target.select_one(".row").get_text(" ").split()) if target and target.select_one(".row") else ""
    if "단체" in target:  # 학급·기관 단체만 받는 교육은 학부모가 신청할 수 없다
        return None
    grades = parse_grades(target)
    if not grades:
        return None
    fee = cells.get("수강료")
    fee = " ".join(fee.get_text(" ").split()) if fee else None
    end = row["apply_ends_on"]
    return Program(
        source_id=row["seq"],
        title=row["title"],
        url=f"{BASE}/NR_boardView.do?bbsCd=1005&seq={row['seq']}",
        description=target,
        grade_min=grades[0], grade_max=grades[1],
        starts_on=row["starts_on"], ends_on=row["ends_on"],
        apply_starts_at=None,  # 접수 시작 시각을 공개하지 않는다
        apply_ends_at=datetime.combine(end, time(23, 59), KST) if end else None,
        fee=fee or None,
    )


class SeoulHistoryMuseum:
    institution = Institution(key="seoul_history_museum", name="서울역사박물관", sido="서울",
                              sigungu="종로구", homepage_url="https://museum.seoul.go.kr")

    def collect(self, fetch, today: date) -> list[Program]:
        rows = [r for st in STATES for r in parse_list(fetch(list_url(st)), today)]
        found = (parse_detail(r, fetch(f"{BASE}/NR_boardView.do?bbsCd=1005&seq={r['seq']}&sso=ok")) for r in rows)
        return [p for p in found if p]
