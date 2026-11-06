"""서울대공원 교육 프로그램 — 목록 HTML을 넘기며 끝나지 않은 교육을 찾고, 상세 페이지를 읽는다."""
import re
from datetime import date, datetime, time

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_date_range, parse_grades

BASE = "https://grandpark.seoul.go.kr/edu/program"
MENU = "S001005001002"
MAX_PAGES = 10
_ANYONE = ("누구나", "어린이", "가족", "제한없음")  # 학년 표기 없이 아이도 받는 교육


def list_url(page: int) -> str:
    return f"{BASE}/list/ko/{MENU}.do?pageIndex={page}"


def _fields(items) -> dict[str, str]:
    # <li><strong>운영기간</strong>2026-11-07 ~ 2026-11-28</li>
    return {li.strong.get_text(strip=True): " ".join(li.get_text(" ").split()[1:]) for li in items if li.strong}


def parse_list(html: str, today: date) -> list[str]:
    out = []
    for box in BeautifulSoup(html, "html.parser").select(".board-list .list-box"):
        m = re.search(r"viewPage\('(\d+)'\)", str(box))
        _, end = parse_date_range(_fields(box.select(".list-bottom li")).get("운영기간", ""), today)
        if m and end and end >= today:
            out.append(m[1])
    return list(dict.fromkeys(out))


def _after(label: str, text: str) -> str:
    # "○ 교육 대상 :|어린이, 청소년…" 또는 표 "참여대상|일반시민 누구나|"
    m = re.search(label + r"\s*:?\s*\|?\s*([^○※|]+)", text)
    return m[1].strip() if m else ""


def _grades(target: str) -> tuple[int, int] | None:
    if "단체" in target:  # 학교·유치원 단체 교육은 학부모가 신청할 수 없다
        return None
    return parse_grades(target) or ((1, 6) if any(w in target for w in _ANYONE) else None)


def parse_view(html: str, seq: str, today: date) -> Program | None:
    s = BeautifulSoup(html, "html.parser")
    head = s.select_one(".view-header h4")
    for state in head.select(".list-state"):
        state.decompose()
    rows = _fields(s.select(".edu-program-view li"))
    body = s.select_one(".view-contents-container")
    text = body.get_text("|") if body else ""
    grades = _grades(rows.get("대상") or _after(r"(?:교육|참여|참가)\s*대상", text))
    if not grades:
        return None
    start, end = parse_date_range(rows.get("운영기간", ""), today)
    _, apply_end = parse_date_range(rows.get("접수기간", ""), today)
    fee = _after(r"(?:교육비|참가비용?|참여비용)", text)
    return Program(
        source_id=seq,
        title=" ".join(head.get_text(" ").split()),
        url=f"{BASE}/view/ko/{MENU}.do?seq={seq}",
        description=" ".join(text.replace("|", " ").split())[:500] or None,
        grade_min=grades[0], grade_max=grades[1],
        starts_on=start, ends_on=end,
        apply_starts_at=None,  # 접수 시작 시각은 본문 문장에만 있다
        apply_ends_at=datetime.combine(apply_end, time(23, 59), KST) if apply_end else None,
        fee="무료" if fee.startswith("무료") else fee or None,
    )


class SeoulGrandPark:
    institution = Institution(key="seoul_grand_park", name="서울대공원", sido="경기",
                              sigungu="과천시", homepage_url="https://grandpark.seoul.go.kr")

    def collect(self, fetch, today: date) -> list[Program]:
        # 목록은 운영 시작일 역순: 끝나지 않은 교육이 하나도 없는 페이지에서 멈춘다.
        # shortcut: 몇 해 전 시작해 아직 안 끝난 교육이 뒤 페이지에 있으면 놓친다, 그런 교육이 생기면 전체 페이지를 돈다.
        seqs = []
        for page in range(1, MAX_PAGES + 1):
            found = parse_list(fetch(list_url(page)), today)
            if not found:
                break
            seqs += found
        views = (parse_view(fetch(f"{BASE}/view/ko/{MENU}.do?seq={q}"), q, today) for q in dict.fromkeys(seqs))
        return [p for p in views if p]
