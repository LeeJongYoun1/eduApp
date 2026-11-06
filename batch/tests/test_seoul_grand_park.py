from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.seoul_grand_park import SeoulGrandPark, list_url, parse_list, parse_view
from eduapp_batch.parse import KST

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
PAGE1 = (FX / "seoul_grand_park_list_1.html").read_text()
PAGE4 = (FX / "seoul_grand_park_list_4.html").read_text()  # 모두 2025년 이전에 끝난 교육


def view(n: int) -> str:
    return (FX / f"seoul_grand_park_view_{n}.html").read_text()


def test_list_url_pages():
    assert list_url(2) == "https://grandpark.seoul.go.kr/edu/program/list/ko/S001005001002.do?pageIndex=2"


def test_parse_list_keeps_programs_not_ended():
    assert parse_list(PAGE1, TODAY) == ["369", "368", "367", "365", "364"]  # 365·364는 오늘 끝난다
    assert parse_list(PAGE4, TODAY) == []


def test_parse_view_first_program():
    p = parse_view(view(369), "369", TODAY)
    assert p.source_id == "369"
    assert p.title == "유인원관 겨울 이야기"
    assert p.url == "https://grandpark.seoul.go.kr/edu/program/view/ko/S001005001002.do?seq=369"
    assert (p.grade_min, p.grade_max) == (1, 6)  # 어린이, 청소년, 성인 등 누구나
    assert (p.starts_on, p.ends_on) == (date(2026, 11, 7), date(2026, 11, 28))
    assert p.apply_starts_at is None  # 접수 시작 시각은 본문 문장에만 있다
    assert p.apply_ends_at == datetime(2026, 11, 28, 23, 59, tzinfo=KST)
    assert p.fee == "무료"
    assert p.description.startswith("고릴라, 오랑우탄, 침팬지 등 유인원과")


def test_parse_view_table_layout():
    p = parse_view(view(348), "348", TODAY)
    assert p.title == "식물이라는 세계 속으로"
    assert (p.grade_min, p.grade_max) == (1, 6)  # 일반시민 누구나
    assert (p.starts_on, p.ends_on) == (date(2026, 3, 1), date(2026, 11, 30))
    assert p.fee == "무료"


def test_parse_view_skips_adults_and_groups():
    assert parse_view(view(350), "350", TODAY) is None  # 일반 성인(개인)
    assert parse_view(view(364), "364", TODAY) is None  # 유아교육기관 (단체)


def test_collect_walks_pages_until_all_ended():
    pages = []

    def fetch(url):
        if "pageIndex=" in url:
            pages.append(url)
            return PAGE1 if url.endswith("=1") else PAGE4
        return view(369)
    progs = SeoulGrandPark().collect(fetch, TODAY)
    assert len(pages) == 2
    assert [p.source_id for p in progs] == ["369", "368", "367", "365", "364"]  # 365·364는 오늘 끝난다


def test_registered():
    assert COLLECTORS["seoul_grand_park"].institution.sigungu == "과천시"
