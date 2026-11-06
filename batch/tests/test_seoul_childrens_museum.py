from datetime import date
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.seoul_childrens_museum import (SeoulChildrensMuseum, parse_detail, target_grades,
                                                            parse_list)

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
LIST = (FX / "seoul_childrens_museum_list.html").read_text()
DETAIL = (FX / "seoul_childrens_museum_detail_2696.html").read_text()


def test_parse_list_keeps_open_programs_for_school_age():
    # 신청 가능 + 상세 id + 초등 나이: 6-7세·개월·성인·마감 항목은 빠진다
    assert parse_list(LIST) == {"2696": (1, 6), "2697": (1, 6), "2660": (1, 6), "2661": (1, 6),
                                "2692": (1, 6), "2699": (1, 6), "2676": (1, 6)}


def test_target_grades():
    assert target_grades("5세 이상 어린이") == (1, 6)
    assert target_grades("8~10세 어린이(2017~2019년생)") == (1, 3)
    assert target_grades("초1~2학년") == (1, 2)
    assert target_grades("누구나") == (1, 6)
    for t in ("6 - 7세 어린이", "28 - 48개월", "36개월미만", "성인", "만 3-5세 포함 서울 거주 가족(최대 4인)"):
        assert target_grades(t) is None, t


def test_parse_detail_fields():
    p = parse_detail(DETAIL, "2696", (1, 6), TODAY)
    assert p.title == "후끈! 열에너지 숨바꼭질"
    assert p.url == "https://www.seoulchildrensmuseum.org/education/educationView.do?id=2696"
    assert (p.grade_min, p.grade_max) == (1, 6)
    assert (p.starts_on, p.ends_on) == (date(2026, 11, 1), date(2026, 12, 27))
    assert p.apply_starts_at is None and p.apply_ends_at is None  # 회차별 '수업 전일까지' 예약
    assert p.fee == "8,000원"
    assert p.description.startswith("색이 변하는 슬라임으로")


def test_collect_fetches_list_then_details():
    seen = []

    def fetch(url):
        seen.append(url)
        return DETAIL if "educationView" in url else LIST
    progs = SeoulChildrensMuseum().collect(fetch, TODAY)
    assert len(progs) == 7 and len(seen) == 8


def test_registered():
    assert COLLECTORS["seoul_childrens_museum"].institution.sigungu == "광진구"
