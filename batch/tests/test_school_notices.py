import re
from pathlib import Path

import pytest

from eduapp_batch.school_notices import (
    Attachment,
    Post,
    UnsupportedSite,
    find_assessment_posts,
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


PROG_LIST = {b: (FX / f"school_progress_list_{b}.html").read_text() for b in ("2799", "2800")}
PROG_DETAIL = {n: (FX / f"school_progress_detail_{n}.html").read_text() for n in ("1330352", "1312210")}


def prog_fetch(calls=None, extra_rows: str = "", detail=PROG_DETAIL):
    """평가계획 검색: 공지사항(2799)·가정통신문(2800)만 실제 목록, 다른 게시판은 빈 목록."""
    def fetch(url: str) -> str:
        if calls is not None:
            calls.append(url)
        if url == HOME:
            return ROOT
        if url == BASE + "/main.do":
            return MAIN
        if "/na/ntt/selectNttList.do" in url:
            b = re.search(r"bbsId=(\d+)", url)[1]
            html = PROG_LIST.get(b, EMPTY_LIST)
            return html.replace("</tbody>", extra_rows + "</tbody>") if b == "2799" else html
        m = re.search(r"selectNttInfo\.do\?mi=\d+&bbsId=\d+&nttSn=(\d+)$", url)
        if m:
            return detail[m[1]]
        raise KeyError(url)
    return fetch


def row(n: int, title: str) -> str:
    return f'<tr><td class="ta_l"><a href="javascript:" data-id="{n}" class="nttInfoBtn">{title}</a></td></tr>'


def test_find_assessment_posts_keeps_newest_school_year_only():
    calls: list[str] = []
    posts = find_assessment_posts(HOME, prog_fetch(calls))
    assert sorted(p.title for p in posts) == ["2026학년도 1학기 학생평가계획", "2026학년도 2학기 학생평가계획"]
    assert not any(n in c for c in calls for n in ("nttSn=1242644",))  # 지난 학년도 상세는 읽지 않는다


def test_find_assessment_posts_orders_by_post_number_ascending():
    posts = find_assessment_posts(HOME, prog_fetch())
    assert [int(p.url.rsplit("nttSn=", 1)[1]) for p in posts] == [1312210, 1330352]
    assert len(posts[0].attachments) == 7 and posts[0].attachments[1].name == "2026학년도 1학년 1학기 평가계획.hwp"


def test_find_assessment_posts_drops_non_plan_titles():
    posts = find_assessment_posts(HOME, prog_fetch(extra_rows=row(9999999, "2026 학부모 총회 및 교육과정 설명회")))
    assert all("설명회" not in p.title for p in posts)


def test_find_assessment_posts_matches_title_with_space():
    detail = PROG_DETAIL | {"1400000": PROG_DETAIL["1330352"]}
    posts = find_assessment_posts(HOME, prog_fetch(extra_rows=row(1400000, "2026학년도 2학기 학생 평가 계획 안내"), detail=detail))
    assert any(p.url.endswith("nttSn=1400000") for p in posts)


def test_find_assessment_posts_caps_at_six_newest():
    rows = "".join(row(2000000 + i, f"2026학년도 {i}학기 학생평가계획") for i in range(8))
    detail = {str(2000000 + i): PROG_DETAIL["1330352"] for i in range(8)} | PROG_DETAIL
    posts = find_assessment_posts(HOME, prog_fetch(extra_rows=rows, detail=detail))
    nums = [int(p.url.rsplit("nttSn=", 1)[1]) for p in posts]
    assert len(posts) == 6 and nums == sorted(nums) and nums[-1] == 2000007


def test_find_assessment_posts_unsupported_site_raises():
    with pytest.raises(UnsupportedSite):
        find_assessment_posts("https://x.sen.es.kr", prog_fetch())
