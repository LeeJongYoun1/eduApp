"""국립과천과학관 교육관 개인예약(초등) — 교육관 목록 JSON."""
import json
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import KST, parse_grades

BASE = "https://www.sciencecenter.go.kr/edu/user/edu"
ELEMENTARY = 109  # 교육관 분류: 초


class GwacheonScience:
    institution = Institution(key="gwacheon_science", name="국립과천과학관", sido="경기",
                              sigungu="과천시", homepage_url="https://www.sciencecenter.go.kr")

    def __init__(self, today: date | None = None):
        self.today = today or datetime.now(KST).date()

    @property
    def list_urls(self) -> list[str]:
        y, m = self.today.year, self.today.month
        months = [(y, m), (y + m // 12, m % 12 + 1)]  # 이번 달, 다음 달
        return [f"{BASE}/eduList.json?srchCtgry={ELEMENTARY}&srchYear={y}&srchMonth={m}" for y, m in months]

    def parse(self, html: str, page_url: str, today: date) -> list[Program]:
        out = []
        for o in json.loads(html)["lctreList"]:
            grades = parse_grades(o.get("addTargetsStr") or "")
            if not grades:
                continue
            fee = o.get("addFeeCurrency") or "0"
            out.append(Program(
                source_id=str(o["eduSeq"]),
                title=o["eduNm"].strip(),
                url=f"{BASE}/eduView.do?eduSeq={o['eduSeq']}",
                description=" ".join(BeautifulSoup(o.get("cn") or "", "html.parser").get_text(" ").split())[:500] or None,
                grade_min=grades[0], grade_max=grades[1],
                starts_on=_date(o.get("eduPeriodBegin")), ends_on=_date(o.get("eduPeriodEnd")),
                apply_starts_at=_dt(o.get("rceptPeriodBegin")), apply_ends_at=_dt(o.get("rceptPeriodEnd")),
                fee="무료" if fee == "0" else f"{fee}원",
            ))
        return out


def _date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _dt(s: str | None) -> datetime | None:
    return datetime.strptime(s, "%Y%m%d%H%M").replace(tzinfo=KST) if s else None
