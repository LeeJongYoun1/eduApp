from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.hangeul_museum import HangeulMuseum, list_url, parse_fee, parse_list
from eduapp_batch.parse import KST

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
LIST = (FX / "hangeul_museum_list.html").read_text()  # 10건 중 개별(가족) 접수는 848 하나
DETAIL = (FX / "hangeul_museum_detail_848.html").read_text()


def test_parse_list_keeps_only_individual_elementary():
    progs = parse_list(LIST, TODAY)
    assert [p.source_id for p in progs] == ["848"]  # 초등 단체(859 등)·유아 단체는 제외


def test_first_program_fields():
    p = parse_list(LIST, TODAY)[0]
    assert p.title == "[여름방학 현장교육] 한글 고전 탐험대"
    assert p.url == "https://www.hangeul.go.kr/education/view?curr_menu_cd=0103010000&programNo=848"
    assert (p.grade_min, p.grade_max) == (1, 2)
    assert (p.starts_on, p.ends_on) == (date(2026, 8, 4), date(2026, 8, 13))
    assert p.apply_starts_at is None  # 접수 시작 시각은 본문 글로만 안내
    assert p.apply_ends_at == datetime(2026, 8, 13, 23, 59, tzinfo=KST)


def test_parse_fee_from_detail():
    assert parse_fee(DETAIL) == "무료"


def test_collect_reads_open_and_upcoming_pages_then_details():
    seen = []

    def fetch(url):
        seen.append(url)
        if "programNo=848" in url:
            return DETAIL
        return LIST if url == list_url(1, 1) else "<html></html>"
    progs = HangeulMuseum().collect(fetch, TODAY)
    assert [(p.source_id, p.fee) for p in progs] == [("848", "무료")]
    assert list_url(1, 2) in seen and list_url(2, 1) in seen  # 빈 페이지에서 멈춘다


def test_registered():
    assert COLLECTORS["hangeul_museum"].institution.sigungu == "용산구"
