from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.gg_childrens_museum import GgChildrensMuseum, age_grades, last_page, parse_list
from eduapp_batch.parse import KST

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
P1 = (FX / "gg_childrens_museum_p1.html").read_text()
P2 = (FX / "gg_childrens_museum_p2.html").read_text()


def test_parse_first_page_skips_group_programs():
    progs = parse_list(P1, TODAY)
    assert [p.source_id for p in progs] == ["800", "786", "785"]  # 단체 동화구연 2건 제외
    p = progs[0]
    assert p.title == "[주말가족] 너의 목소리가 들려"
    assert p.url == "https://gcm.ggcf.kr/edus/800"
    assert (p.grade_min, p.grade_max) == (1, 6)  # 만 4~6세 이상 / 만 7~9세
    assert (p.starts_on, p.ends_on) == (date(2026, 9, 27), date(2026, 12, 13))
    assert p.apply_starts_at is None and p.apply_ends_at is None  # 접수기간 표기 없음
    assert p.fee == "2,000원"
    assert p.description.startswith("가족 간의 소통을 담아")


def test_parse_apply_period_and_free_fee():
    p = parse_list(P1, TODAY)[1]
    assert p.apply_starts_at is None
    assert p.apply_ends_at == datetime(2026, 12, 31, 23, 59, tzinfo=KST)
    assert p.fee == "무료"


def test_second_page_skips_height_only_target():
    progs = parse_list(P2, TODAY)
    # 키 120cm 이상(학년·나이 없음) 제외
    assert [(p.title, p.grade_min, p.grade_max) for p in progs] == [("《두 개의 DMZ》 본 체험 프로그램", 1, 6)]


def test_age_grades():
    assert age_grades("만 7~9세 어린이") == (1, 3)
    assert age_grades("5세 이상 어린이") == (1, 6)
    assert age_grades("만 4~6세 어린이") is None
    assert age_grades("키 120cm 이상") is None


def test_collect_follows_pages():
    assert last_page(P1) == 2
    urls = []

    def fetch(url):
        urls.append(url)
        return P2 if "page=2" in url else P1
    progs = GgChildrensMuseum().collect(fetch, TODAY)
    assert len(progs) == 4 and len(urls) == 2


def test_registered():
    assert COLLECTORS["gg_childrens_museum"].institution.sigungu == "용인시"
