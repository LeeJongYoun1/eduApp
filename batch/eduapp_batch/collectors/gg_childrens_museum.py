"""경기도어린이박물관 — 교육 목록(현재 교육) HTML. 목록 카드에 대상·기간·접수기간·참가비가 다 있다."""
import re
from datetime import date, datetime, time

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_date_range, parse_grades

BASE = "https://gcm.ggcf.kr"
LIST_URL = f"{BASE}/edus?current%5B%5D=now"
_COUNT = re.compile(r"\d+\s*(?:팀|명|인)")
_AGE = re.compile(r"(만\s*)?(\d{1,2})\s*(?:~\s*(?:만\s*)?(\d{1,2}))?\s*세\s*(이상)?")


def age_grades(text: str) -> tuple[int, int] | None:
    """'만 7~9세', '5세 이상' 같은 나이 표기를 초등 학년 범위로. 만 7세·(한국 나이) 8세 = 초1."""
    found = []
    for man, lo, hi, plus in _AGE.findall(text):
        off = 6 if man else 7
        g_lo, g_hi = max(1, int(lo) - off), 6 if plus else min(6, int(hi or lo) - off)
        if g_lo <= g_hi:
            found.append((g_lo, g_hi))
    return (min(g[0] for g in found), max(g[1] for g in found)) if found else None


def last_page(html: str) -> int:
    btn = BeautifulSoup(html, "html.parser").select_one("a.btn-more")
    return int(btn["data-last-page"]) if btn else 1


def parse_list(html: str, today: date) -> list[Program]:
    out = []
    for li in BeautifulSoup(html, "html.parser").select(".exhibition-list > ul > li"):
        title = li.h4.get_text(strip=True)
        rows = {tr.th.get_text(strip=True): " ".join(tr.td.get_text(" ").split()) for tr in li.select("table tr")}
        target = rows.get("대상", "")
        if "단체" in target or title.startswith("[단체]"):  # 단체 전용은 학부모가 신청할 수 없다
            continue
        target = _COUNT.sub("", target)  # "가족 5팀"의 5를 학년으로 읽지 않게
        grades = parse_grades(target) or age_grades(target)
        if not grades:
            continue
        start, end = parse_date_range(rows.get("교육기간", ""), today)
        _, apply_end = parse_date_range(rows.get("접수기간", ""), today)
        desc = li.select_one("p.list-pointer")
        out.append(Program(
            source_id=li.a["href"].rstrip("/").rsplit("/", 1)[-1],
            title=title,
            url=li.a["href"],
            description=desc.get_text(strip=True)[:500] if desc else None,
            grade_min=grades[0], grade_max=grades[1],
            starts_on=start, ends_on=end,
            apply_starts_at=None,  # 접수 시작 시각은 공개하지 않는다
            apply_ends_at=datetime.combine(apply_end, time(23, 59), KST) if apply_end else None,
            fee=rows.get("참가비") or None,
        ))
    return out


class GgChildrensMuseum:
    institution = Institution(key="gg_childrens_museum", name="경기도어린이박물관", sido="경기",
                              sigungu="용인시", homepage_url=BASE)

    def collect(self, fetch, today: date) -> list[Program]:
        first = fetch(LIST_URL)
        pages = [first] + [fetch(f"{LIST_URL}&page={n}") for n in range(2, last_page(first) + 1)]
        return [p for html in pages for p in parse_list(html, today)]
