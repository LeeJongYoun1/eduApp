from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.folk_museum import FolkMuseum, age_grades, list_url, parse_fee, parse_list
from eduapp_batch.parse import KST

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
LIST = (FX / "folk_museum_list.html").read_text()            # 접수중 9건(파주·단체·성인·마감 포함)
DETAIL = (FX / "folk_museum_detail_2992.html").read_text()


def test_list_url():
    assert list_url("1") == "https://www.nfm.go.kr/user/eduPlan/home/85/dataList.do?searchStatus=1&row=48"


def test_parse_list_keeps_individual_elementary_seoul_programs():
    # 파주관(3021·3022·3006), 단체(3005), 마감(3002), 성인 대상(3008), 학년·나이 없음(3009) 제외
    assert [p.source_id for p in parse_list(LIST, TODAY)] == ["2992", "2990"]


def test_first_program_fields():
    p = parse_list(LIST, TODAY)[0]
    assert p.title == "[2026년 전시연계] 할머니의 옛이야기"
    assert p.url == "https://www.nfm.go.kr/user/eduPlan/home/85/dataView.do?eduPlanIdx=2992"
    assert (p.grade_min, p.grade_max) == (1, 6)  # "6세 이상"
    assert (p.starts_on, p.ends_on) == (date(2026, 3, 5), date(2026, 12, 31))
    assert p.apply_starts_at is None  # 접수 시작 시각 비공개
    assert p.apply_ends_at == datetime(2026, 12, 31, 23, 59, tzinfo=KST)
    assert p.description == "6세 이상 (개인: 6명 단체: 30명)"


def test_age_range_maps_to_grades():
    assert parse_list(LIST, TODAY)[1].grade_min == 1 and parse_list(LIST, TODAY)[1].grade_max == 4  # 6세~10세
    assert age_grades("유아(만5~6세)") is None
    assert age_grades("어린이 동반 가족") is None


def test_parse_fee():
    assert parse_fee(DETAIL) == "무료"
    assert parse_fee("<p>안내</p>") is None


def test_collect_adds_fee_from_detail():
    def fetch(url):
        if "dataList" in url:
            return LIST if "searchStatus=1" in url else ""
        return DETAIL
    progs = FolkMuseum().collect(fetch, TODAY)
    assert [(p.source_id, p.fee) for p in progs] == [("2992", "무료"), ("2990", "무료")]


def test_registered():
    assert COLLECTORS["folk_museum"].institution.sigungu == "종로구"
