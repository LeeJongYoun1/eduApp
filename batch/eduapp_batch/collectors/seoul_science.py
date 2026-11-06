"""서울시립과학관 — 교육 목록에서 진행 중인 교육을 찾고, 상세에 걸린 서울시 공공서비스예약 페이지를 읽는다."""
import re
from datetime import date

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_date_range, parse_datetime, parse_grades

BASE = "https://science.seoul.go.kr"
YEYAK = "https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id="
MENUS = (("experience", 70), ("experiment", 71), ("talk", 73))  # 성인과학·단체교육은 제외
_YEYAK_ID = re.compile(r"yeyak\.seoul\.go\.kr/web/reservation/selectReservView\.do\?rsv_svc_id=(\w+)")


def parse_list(html: str, today: date) -> list[tuple[str, str | None]]:
    """끝나지 않은 교육의 (상세 URL, 비용). 신청은 예약 페이지에서 받지만 비용은 '유료'로만 나와 목록 것을 쓴다."""
    out = []
    for ev in BeautifulSoup(html, "html.parser").select("div.event_gs"):
        rows = {li.b.get_text(strip=True).rstrip(" :"): " ".join(li.get_text(" ").split()).split(":", 1)[-1].strip()
                for li in ev.select("li") if li.b}
        _, end = parse_date_range(rows.get("교육기간", ""), today)
        if end and end >= today:
            out.append((BASE + ev.select_one(".event_gs_btn a")["href"], rows.get("비용") or None))
    return out


def yeyak_ids(html: str) -> list[str]:
    return list(dict.fromkeys(_YEYAK_ID.findall(html)))


def parse_yeyak(html: str, svc_id: str, fee: str | None, today: date) -> Program | None:
    s = BeautifulSoup(html, "html.parser")
    rows = {b.get_text(strip=True): " ".join(b.parent.get_text(" ").split())[len(b.get_text(strip=True)):].strip()
            for b in s.select("b.tit1")}
    grades = parse_grades(rows.get("대상", ""))
    if not grades:
        return None
    start, end = parse_date_range(rows.get("이용기간", ""), today)
    apply = re.split(r"~", rows.get("접수기간", ""), maxsplit=1) + [""]
    detail = s.select_one(".sub_detail")
    return Program(
        source_id=svc_id,
        title=" ".join(s.select_one("span.tit").get_text().split()),
        url=YEYAK + svc_id,
        description=" ".join(detail.get_text(" ").split())[:500] or None if detail else None,
        grade_min=grades[0], grade_max=grades[1],
        starts_on=start, ends_on=end,
        apply_starts_at=parse_datetime(apply[0], today), apply_ends_at=parse_datetime(apply[1], today),
        fee=fee,
    )


class SeoulScience:
    institution = Institution(key="seoul_science", name="서울시립과학관", sido="서울",
                              sigungu="노원구", homepage_url="https://science.seoul.go.kr")

    def collect(self, fetch, today: date) -> list[Program]:
        ids: dict[str, str | None] = {}  # 예약 서비스 id → 비용
        for path, menu in MENUS:
            for url, fee in parse_list(fetch(f"{BASE}/sciEdu/{path}?menuId={menu}"), today):
                for i in yeyak_ids(fetch(url)):  # 예약 링크가 없는 교육은 현장 참여라 신청 정보가 없다
                    ids.setdefault(i, fee)
        found = (parse_yeyak(fetch(YEYAK + i), i, fee, today) for i, fee in ids.items())
        return [p for p in found if p]
