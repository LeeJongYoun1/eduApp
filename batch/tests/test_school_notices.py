import re
from pathlib import Path

import pytest

from eduapp_batch.school_notices import (
    Attachment,
    Post,
    UnsupportedSite,
    find_textbook_posts,
)

FX = Path(__file__).parent / "fixtures"
HOME = "https://kwiin-e.goeay.kr"
BASE = HOME + "/kwiin-e"
ROOT, MAIN, LIST = ((FX / f"school_{n}.html").read_text() for n in ("root", "main", "list"))
DETAIL = {"1307880": (FX / "school_detail_image.html").read_text(),  # 본문이 이미지뿐
          "1242644": (FX / "school_detail_pdf.html").read_text(),
          "218674": (FX / "school_detail_hwp.html").read_text()}
EMPTY_LIST = "<html><body><div class='BD_list'><table><tbody></tbody></table></div></body></html>"


def make_fetch(calls: list[str] | None = None, list_html: str = LIST):
    """학교 사이트 흉내: 공지사항(2799)만 픽스처 목록, 나머지 게시판은 빈 목록, 모르는 주소는 KeyError."""
    def fetch(url: str) -> str:
        if calls is not None:
            calls.append(url)
        if url == HOME:
            return ROOT
        if url == BASE + "/main.do":
            return MAIN
        if "/na/ntt/selectNttList.do" in url:
            return list_html if "bbsId=2799" in url else EMPTY_LIST
        m = re.search(r"/na/ntt/selectNttInfo\.do\?mi=\d+&bbsId=\d+&nttSn=(\d+)$", url)
        if m:
            return DETAIL[m[1]]
        raise KeyError(url)
    return fetch


def test_follows_js_redirect():
    calls: list[str] = []
    find_textbook_posts(HOME, make_fetch(calls))
    assert calls[:2] == [HOME, BASE + "/main.do"]


def test_accepts_homepage_without_scheme_or_with_main_path():
    assert find_textbook_posts("kwiin-e.goeay.kr", make_fetch())
    assert find_textbook_posts(BASE + "/main.do", make_fetch())


def test_picks_only_textbook_titles():
    posts = find_textbook_posts(HOME, make_fetch())
    assert sorted(p.title for p in posts) == sorted([
        "귀인초 검인정교과서 출판사 안내",
        "2025학년도 교과용 도서(3,4학년 검정 교과서) 선정 결과",
        "2023학년도 교과용 도서 선정 결과"])


def test_scans_only_notice_and_newsletter_boards_once_each():
    calls: list[str] = []
    find_textbook_posts(HOME, make_fetch(calls))
    lists = [c for c in calls if "selectNttList" in c]
    assert all("bbsId=5252" not in c for c in lists)  # 가정통신문(교육청)은 제외
    assert any("bbsId=2799" in c for c in lists) and any("bbsId=2800" in c for c in lists)
    assert len(lists) == len(set(lists))
    assert all("searchType=sj" in c for c in lists)
    # 같은 글이 여러 보드/검색어로 나와도 상세는 한 번만 읽는다
    details = [c for c in calls if "selectNttInfo" in c]
    assert len(details) == len(set(details))


def test_collects_attachment_urls_and_body():
    posts = {p.title: p for p in find_textbook_posts(HOME, make_fetch())}
    pdf = posts["2025학년도 교과용 도서(3,4학년 검정 교과서) 선정 결과"]
    assert pdf.url == BASE + "/na/ntt/selectNttInfo.do?mi=6183&bbsId=2799&nttSn=1242644"
    assert pdf.attachments == [Attachment(
        "2025학년도 귀인초 교과용도서(3,4학년 검정 교과서) 선정 결과.pdf",
        HOME + "/upload/kwiin-e/na/bbs_2799/2024/10/e4f33d2f-80cc-479c-9290-63e33a74d90e.pdf")]
    assert "교과협의회" in pdf.body and "<" not in pdf.body
    hwp = posts["2023학년도 교과용 도서 선정 결과"]
    assert hwp.attachments[0].name == "2023학년도_교과용_도서_선정_결과.hwp"
    assert hwp.attachments[0].url.startswith(HOME + "/upload/old_data/") and hwp.attachments[0].url.endswith(".hwp")
    assert isinstance(hwp, Post)
    img = posts["귀인초 검인정교과서 출판사 안내"]  # 본문은 이미지뿐, 첨부 PDF가 실제 내용
    assert img.body == "" and img.attachments[0].name.endswith(".pdf")


def test_unsupported_site_raises():
    with pytest.raises(UnsupportedSite):
        find_textbook_posts("https://x.sen.es.kr", make_fetch())


def test_no_match_returns_empty():
    assert find_textbook_posts(HOME, make_fetch(list_html=EMPTY_LIST)) == []
