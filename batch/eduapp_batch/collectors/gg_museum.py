"""경기도박물관 — 교육 목록 '어린이' 분류(진행·예정) HTML. 목록에는 기간·대상만 있다."""
from datetime import date

from bs4 import BeautifulSoup

from ..models import Institution, Program
from ..parse import parse_date_range, parse_grades

BASE = "https://musenet.ggcf.kr"


def parse_list(html: str, today: date) -> list[Program]:
    out = []
    for item in BeautifulSoup(html, "html.parser").select(".edu-item"):
        rows = {dl.dt.get_text(strip=True): " ".join(dl.dd.get_text(" ").split()) for dl in item.select("dl")}
        grades = parse_grades(rows.get("대상", ""))
        if not grades:  # '어린이'처럼 학년 표기가 없으면 건너뛴다
            continue
        start, end = parse_date_range(rows.get("기간", ""), today)
        desc = item.select_one("p.txt")
        url = item.a["href"]
        out.append(Program(
            source_id=url.rstrip("/").rsplit("/", 1)[-1],
            title=item.select_one("p.title").get_text(strip=True),
            url=url,
            description=desc.get_text(strip=True)[:500] if desc else None,
            grade_min=grades[0], grade_max=grades[1],
            starts_on=start, ends_on=end,
            # shortcut: 접수기간·참가비는 상세 본문 자유 서술에만 있어 비워 둔다. 형식이 생기면 상세 파싱 추가.
        ))
    return out


class GgMuseum:
    institution = Institution(key="gg_museum", name="경기도박물관", sido="경기",
                              sigungu="용인시", homepage_url=BASE)

    def collect(self, fetch, today: date) -> list[Program]:
        # 01 = 어린이. shortcut: 첫 페이지(5건)만 읽는다. 진행·예정 어린이 교육이 5건을 넘으면 페이지 순회 추가.
        urls = [f"{BASE}/edus?category=01&progress={p}" for p in ("now", "yet")]
        return [p for u in urls for p in parse_list(fetch(u), today)]
