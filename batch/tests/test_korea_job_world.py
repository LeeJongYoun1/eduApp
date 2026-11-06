from datetime import date
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.korea_job_world import KoreaJobWorld, list_url, parse_list, parse_product

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
LIST = (FX / "korea_job_world_list_03.json").read_text()


def product(n: int) -> str:
    return (FX / f"korea_job_world_product_{n}.json").read_text()


def test_list_url_individual():
    assert list_url("03") == "https://www.koreajobworld.or.kr/api/product?pdDiv=03&pgDiv=P"


def test_parse_list_ids():
    assert parse_list(LIST) == [1334, 1327, 1336, 1335, 1339, 1337]


def test_parse_product_dated_elementary_program():
    p = parse_product(product(1336), TODAY)
    assert p.source_id == "1336"
    assert p.title == "(주말) 2026년 드림 베이커리"
    assert p.url == "https://www.koreajobworld.or.kr/reserve/ind/course/1336"
    assert (p.grade_min, p.grade_max) == (1, 4)
    assert (p.starts_on, p.ends_on) == (date(2026, 11, 7), date(2026, 12, 31))
    assert p.apply_starts_at is None and p.apply_ends_at is None  # 회차별 상시 예약, 마감 시각 비공개
    assert p.fee == "3,000원"
    assert p.description.startswith("* 본 프로그램 참여 시 진로설계관 입장권 발권(3,000원)이 필요하며")


def test_parse_product_upper_grades():
    p = parse_product(product(1412), TODAY)
    assert (p.grade_min, p.grade_max) == (6, 6)
    assert p.url.endswith("/reserve/ind/future/1412")


def test_skips_always_on_no_grades_and_school_visit():
    assert parse_product(product(1331), TODAY) is None    # 1년 굴러가는 상시 예약
    assert parse_product(product(100590), TODAY) is None  # 대상 없음(패키지 이벤트)
    assert parse_product(product(890), TODAY) is None     # 학교방문형


def test_collect_lists_then_products():
    def fetch(url):
        if "pdDiv=03" in url:
            return LIST
        if "pdDiv=" in url:
            return '{"success":true,"response":[]}'
        n = int(url.split("/api/product/")[1].split("?")[0])
        return product(1336 if n == 1336 else 1331)
    assert [p.source_id for p in KoreaJobWorld().collect(fetch, TODAY)] == ["1336"]


def test_registered():
    assert COLLECTORS["korea_job_world"].institution.sigungu == "성남시"
