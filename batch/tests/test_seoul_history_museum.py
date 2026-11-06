from datetime import date, datetime
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.seoul_history_museum import SeoulHistoryMuseum, list_url, parse_detail, parse_list
from eduapp_batch.parse import KST

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
LIST = (FX / "seoul_history_museum_list.html").read_text()            # 접수중 9건
FAMILY = (FX / "seoul_history_museum_detail_family.html").read_text()  # 한밤의 역사기행, 초등 자녀 가족
GROUP = (FX / "seoul_history_museum_detail_group.html").read_text()    # 초등5~6학년 학급단체


def test_list_url_filters_apply_state():
    assert list_url("1002") == ("https://museum.seoul.go.kr/www/board/NR_boardList.do"
                                "?bbsCd=1005&q_applyState=1002&rowPerPage=50&sso=ok")


def test_parse_list_rows():
    rows = parse_list(LIST, TODAY)
    assert len(rows) == 9
    r = rows[0]
    assert r["seq"] == "20261021153443848"
    assert r["title"] == "2026년 겨울학기 '한밤의 역사기행' 모집"
    assert (r["starts_on"], r["ends_on"]) == (date(2026, 11, 6), date(2026, 11, 27))
    assert r["apply_ends_on"] == date(2026, 11, 20)


def test_parse_detail_family_program():
    p = parse_detail(parse_list(LIST, TODAY)[0], FAMILY)
    assert p.source_id == "20261021153443848"
    assert p.title == "2026년 겨울학기 '한밤의 역사기행' 모집"
    assert p.url == "https://museum.seoul.go.kr/www/board/NR_boardView.do?bbsCd=1005&seq=20261021153443848"
    assert (p.grade_min, p.grade_max) == (1, 6)
    assert (p.starts_on, p.ends_on) == (date(2026, 11, 6), date(2026, 11, 27))
    assert p.apply_starts_at is None  # 접수 시작 시각 비공개
    assert p.apply_ends_at == datetime(2026, 11, 20, 23, 59, tzinfo=KST)
    assert p.fee is None  # 수강료 칸이 없다
    assert p.description == "초등학생 자녀를 둔 가족 (미취학 아동, 중고생 동반 불가)"


def test_parse_detail_skips_group_only():
    row = next(r for r in parse_list(LIST, TODAY) if r["seq"] == "20261015152427523")
    assert parse_detail(row, GROUP) is None


def test_collect_fetches_lists_then_details():
    def fetch(url):
        if "NR_boardList" in url:
            return LIST if "q_applyState=1002" in url else ""
        return FAMILY if "20261021153443848" in url else GROUP
    progs = SeoulHistoryMuseum().collect(fetch, TODAY)
    assert [p.source_id for p in progs] == ["20261021153443848"]


def test_not_registered_while_site_blocks_python():
    assert "seoul_history_museum" not in COLLECTORS  # 사이트가 자동 접속을 끊어 등록 보류 (collectors/__init__.py)
