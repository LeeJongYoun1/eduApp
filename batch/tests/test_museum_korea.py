from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.museum_korea import MuseumKorea, calendar_url, parse_calendar, parse_detail
from eduapp_batch.parse import KST

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
CAL = (FX / "museum_korea_calendar.json").read_text()
OPEN = (FX / "museum_korea_detail_10621.html").read_text()   # 개인 신청, 초5 이상
GROUP = (FX / "museum_korea_detail_10619.html").read_text()  # 단체만


def test_calendar_url_spans_35_days_and_both_museums():
    u = calendar_url(TODAY)
    assert "from=2026-11-06" in u and "to=2026-12-11" in u
    assert "museum=1&museum=15" in u and "searchApplyStatus=ONGOING" in u


def test_parse_calendar_returns_unique_ids():
    ids = parse_calendar(CAL)
    assert len(ids) == len(set(ids)) == 8
    assert 10621 in ids


def test_parse_detail_individual_elementary_program():
    p = parse_detail(OPEN, 10621, TODAY)
    assert p.source_id == "10621"
    assert p.title == "[26년도 11월] 공·감·각 전시 학습 ‘공간 오감’(교육 신청)"
    assert p.url == "https://modu.museum.go.kr/learn/detail/10621"
    assert (p.grade_min, p.grade_max) == (5, 6)
    assert (p.starts_on, p.ends_on) == (date(2026, 11, 3), date(2026, 11, 28))
    assert p.apply_starts_at is None  # 시작 시각 비공개 → 기간만
    assert p.apply_ends_at == datetime(2026, 11, 26, 23, 59, tzinfo=KST)
    assert p.fee == "무료"
    assert p.description == "다양한 감각을 활용한 8가지 주제 활동으로 문화유산을 입체적으로 감상"


def test_parse_detail_skips_group_only():
    assert parse_detail(GROUP, 10619, TODAY) is None


def test_collect_fetches_calendar_then_details():
    def fetch(url):
        if "calendar" in url:
            return CAL
        return OPEN if url.endswith("/10621") else GROUP
    progs = MuseumKorea().collect(fetch, TODAY)
    assert [p.source_id for p in progs] == ["10621"]


def test_registered():
    assert COLLECTORS["museum_korea"].institution.sigungu == "용산구"
