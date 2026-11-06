from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.seoul_science import SeoulScience, parse_list, parse_yeyak, yeyak_ids
from eduapp_batch.parse import KST

FIX = Path(__file__).parent / "fixtures"
LIST = (FIX / "seoul_science_list_experience.html").read_text()
DETAIL = (FIX / "seoul_science_detail_2358.html").read_text()
YEYAK = (FIX / "seoul_science_yeyak_S261020160014299910.html").read_text()
YEYAK_TEEN = (FIX / "seoul_science_yeyak_S260807112145128937.html").read_text()
TODAY = date(2026, 11, 6)


def test_list_keeps_programs_not_yet_ended():
    items = parse_list(LIST, TODAY)
    assert len(items) == 4
    assert items[0] == ("https://science.seoul.go.kr/sciEdu/experience/read?menuId=70&progMstId=2358", "5,000원")


def test_detail_links_to_reservation_services():
    assert yeyak_ids(DETAIL) == ["S261020160014299910", "S261020161744096983",
                                 "S261020162436562114", "S261020163009239965"]


def test_yeyak_fields():
    p = parse_yeyak(YEYAK, "S261020160014299910", "5,000원", TODAY)
    assert p.source_id == "S261020160014299910"
    assert p.title == "[과학X예술 워크숍] 돌은 언제 색이 되는가"
    assert (p.starts_on, p.ends_on) == (date(2026, 10, 20), date(2026, 11, 14))
    assert (p.grade_min, p.grade_max) == (4, 6)
    assert p.apply_starts_at == datetime(2026, 10, 20, 17, 0, tzinfo=KST)
    assert p.apply_ends_at == datetime(2026, 11, 14, 13, 0, tzinfo=KST)
    assert p.fee == "5,000원"
    assert p.url == "https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id=S261020160014299910"
    assert p.description and "<" not in p.description


def test_non_elementary_excluded():
    assert parse_yeyak(YEYAK_TEEN, "S260807112145128937", "강좌 당 1만원", TODAY) is None


def test_collect_follows_list_detail_reservation():
    def fetch(url):
        if "experience?" in url:
            return LIST
        if "progMstId=2358" in url:
            return DETAIL
        if "yeyak" in url:
            return YEYAK
        return "<html></html>"  # 다른 목록·상세: 비어 있음
    progs = SeoulScience().collect(fetch, TODAY)
    assert [p.source_id for p in progs] == yeyak_ids(DETAIL)


def test_registered():
    assert COLLECTORS["seoul_science"].institution.sigungu == "노원구"
