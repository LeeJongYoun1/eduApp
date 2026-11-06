from datetime import date
from pathlib import Path

from eduapp_batch.collectors import COLLECTORS
from eduapp_batch.collectors.gg_museum import GgMuseum, parse_list

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 6)
LIST = (FX / "gg_museum_list.html").read_text()  # 어린이 분류 전체(지난 교육 포함)


def test_parse_list_keeps_elementary_targets():
    progs = parse_list(LIST, TODAY)
    # '대상: 어린이'처럼 학년이 없는 항목은 제외
    assert [p.source_id for p in progs] == ["403", "373", "372"]
    p = progs[0]
    assert p.title == "2026년 여름방학 어린이 특별 프로그램 '동동하하 冬冬夏夏'"
    assert p.url == "https://musenet.ggcf.kr/edus/403"
    assert (p.grade_min, p.grade_max) == (1, 6)
    assert (p.starts_on, p.ends_on) == (date(2026, 7, 30), date(2026, 8, 9))
    assert p.apply_starts_at is None and p.apply_ends_at is None and p.fee is None  # 목록에 없음
    assert (progs[2].grade_min, progs[2].grade_max) == (4, 6)


def test_collect_reads_now_and_upcoming():
    urls = []

    def fetch(url):
        urls.append(url)
        return LIST if "progress=now" in url else "<html></html>"
    progs = GgMuseum().collect(fetch, TODAY)
    assert len(progs) == 3 and len(urls) == 2
    assert all("category=01" in u for u in urls)


def test_registered():
    assert COLLECTORS["gg_museum"].institution.sigungu == "용인시"
