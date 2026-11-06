from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.gwacheon_science import GwacheonScience
from eduapp_batch.parse import KST

FIXTURE = (Path(__file__).parent / "fixtures/gwacheon_science_list.json").read_text()
URL = "https://www.sciencecenter.go.kr/edu/user/edu/eduList.json?srchCtgry=109&srchYear=2026&srchMonth=11"


def parse():
    return GwacheonScience().parse(FIXTURE, URL, date(2026, 11, 6))


def test_parses_all_elementary_programs():
    assert len(parse()) == 30


def test_first_program_fields():
    p = parse()[0]
    assert p.source_id == "4114"
    assert p.title == "내가 AI 전문가 - 1반 (토-오전)"
    assert (p.starts_on, p.ends_on) == (date(2026, 11, 7), date(2026, 12, 12))
    assert (p.grade_min, p.grade_max) == (4, 6)
    assert p.apply_starts_at == datetime(2026, 10, 28, 10, 0, tzinfo=KST)
    assert p.apply_ends_at == datetime(2026, 10, 29, 23, 50, tzinfo=KST)
    assert p.fee == "180,000원"
    assert p.url == "https://www.sciencecenter.go.kr/edu/user/edu/eduView.do?eduSeq=4114"


def test_description_is_plain_text():
    d = parse()[0].description
    assert "<" not in d and "초등 4~6학년만 접수 가능" in d


def test_list_urls_cover_this_and_next_month():
    urls = GwacheonScience(today=date(2026, 12, 3)).list_urls
    assert any("srchYear=2026&srchMonth=12" in u for u in urls)
    assert any("srchYear=2027&srchMonth=1" in u for u in urls)


def test_registered():
    assert COLLECTORS["gwacheon_science"].institution.sido == "경기"


def test_collect_reads_every_list_url():
    seen = []
    def fetch(url):
        seen.append(url)
        return FIXTURE
    progs = GwacheonScience(today=date(2026, 11, 6)).collect(fetch, date(2026, 11, 6))
    assert len(seen) == 2 and len(progs) == 60
