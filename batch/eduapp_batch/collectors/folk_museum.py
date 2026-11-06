"""국립민속박물관(어린이박물관 포함) 교육안내·신청 — 접수 상태별 목록 HTML, 참가비만 상세 본문에서 읽는다."""
import re
from dataclasses import replace
from datetime import date, datetime, time

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_date_range, parse_grades

BASE = "https://www.nfm.go.kr/user/eduPlan/home/85"
STATES = ("1", "2")  # 접수중, 접수예정
_AGES = re.compile(r"(\d{1,2})\s*(?:~\s*(\d{1,2})\s*)?세")


def list_url(state: str) -> str:
    return f"{BASE}/dataList.do?searchStatus={state}&row=48"


def age_grades(text: str) -> tuple[int, int] | None:
    # "6세~10세", "6세 이상": 연 나이로 보고 7세 = 초1. 어린이박물관 교육은 학년 대신 나이를 쓴다.
    ages = [int(n) for m in _AGES.findall(text) for n in m if n]
    if not ages:
        return None
    lo, hi = max(min(ages) - 6, 1), 6 if "이상" in text else min(max(ages) - 6, 6)
    return (lo, hi) if lo <= hi else None


def parse_list(html: str, today: date) -> list[Program]:
    out = []
    for li in BeautifulSoup(html, "html.parser").select("ul.mixed_list li.mixed_item"):
        status = li.select_one(".item_info").get_text(strip=True)
        title = " ".join(li.select_one(".item_title").get_text().split())
        lines = (" ".join(t.get_text(" ").split()) for t in li.select(".item_txt"))
        f = {k.strip(): v.strip() for k, _, v in (s.partition(":") for s in lines)}
        target = f.get("접수대상", "")
        if status == "마감" or "파주" in title + f.get("교육장소", ""):  # 파주관은 경기 파주시 — 종로 본관만 싣는다
            continue
        if re.search("단체|기관", target) and not re.search("개인|가족", target):
            continue
        grades = parse_grades(target) or age_grades(target)
        if not grades:
            continue
        idx = re.search(r"'(\d+)'", li.select_one("a[onclick]")["onclick"])[1]
        starts_on, ends_on = parse_date_range(f.get("교육기간", ""), today)
        _, apply_end = parse_date_range(f.get("접수기간", ""), today)
        out.append(Program(
            source_id=idx, title=title, url=f"{BASE}/dataView.do?eduPlanIdx={idx}",
            description=target or None,
            grade_min=grades[0], grade_max=grades[1],
            starts_on=starts_on, ends_on=ends_on,
            apply_starts_at=None,  # 접수 시작 시각을 공개하지 않는다
            apply_ends_at=datetime.combine(apply_end, time(23, 59), KST) if apply_end else None,
        ))
    return out


def parse_fee(html: str) -> str | None:
    # 참가비는 본문 자유 서술에만 있다: "참가비 : 무료"
    m = re.search(r"참가비\s*:\s*([^\s<]+)", BeautifulSoup(html, "html.parser").get_text(" "))
    return m[1] if m else None


class FolkMuseum:
    institution = Institution(key="folk_museum", name="국립민속박물관", sido="서울",
                              sigungu="종로구", homepage_url="https://www.nfm.go.kr")

    def collect(self, fetch, today: date) -> list[Program]:
        progs = [p for st in STATES for p in parse_list(fetch(list_url(st)), today)]
        return [replace(p, fee=parse_fee(fetch(p.url))) for p in progs]
