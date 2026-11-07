"""경기도 학교 홈페이지(*.goeay.kr)의 공지사항·가정통신문에서 교과용도서 선정 게시물과 첨부 주소를 찾는다."""
import html as htmllib
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

BOARD_NAMES = ("공지사항", "가정통신문")  # 가정통신문(교육청) 같은 다른 게시판은 제외
TITLE_WORDS = ("교과용도서", "교과서", "교재")
# 제목 검색어: '교과용 도서'처럼 띄어 쓴 제목도 잡도록 '교과'로 넓게 찾고 제목은 아래에서 다시 거른다.
SEARCH_WORDS = ("교과", "교재")
MAX_REDIRECTS = 3
_REDIRECT = re.compile(r"""location\.href\s*=\s*["']([^"']+)["']""")
_ATTACH = re.compile(r"""AddUploadedFile\(\s*"[^"]*"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)\"""")  # (키, 파일명, 경로, ...)


class UnsupportedSite(Exception):
    pass


@dataclass(frozen=True)
class Attachment:
    name: str
    url: str


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    body: str
    attachments: list[Attachment]


def _text(el) -> str:
    return " ".join(el.get_text(" ").split()) if el else ""


def _boards(html: str, base: str) -> list[str]:
    links = BeautifulSoup(html, "html.parser").find_all("a", href=re.compile("selectNttList.do"))
    return list(dict.fromkeys(urljoin(base, a["href"]) for a in links if _text(a) in BOARD_NAMES))


def _menu(home: str, fetch: Callable[[str], str]) -> tuple[str, list[str]]:
    """첫 페이지는 location.href 한 줄짜리 JS 리다이렉트라 직접 따라간다(httpx도 따라가지 않는다)."""
    url = home
    for _ in range(MAX_REDIRECTS + 1):
        html = fetch(url)
        boards = _boards(html, url)
        redirect = _REDIRECT.search(html)
        if boards or not redirect:
            return url, boards
        url = urljoin(url, redirect[1])
    return url, []


def _candidates(homepage_url: str, fetch: Callable[[str], str], search_words: tuple[str, ...],
                title_words: tuple[str, ...]) -> dict[str, str]:
    """공지사항·가정통신문을 검색어로 훑어 제목이 맞는 글의 상세 주소 → 제목."""
    home = homepage_url.strip() if "//" in homepage_url else "https://" + homepage_url.strip()
    if not (urlparse(home).hostname or "").endswith(".goeay.kr"):
        raise UnsupportedSite(homepage_url)
    _, boards = _menu(home, fetch)
    found: dict[str, str] = {}  # 상세 주소 -> 제목 (게시판·검색어가 겹쳐도 한 번만)
    for board in boards:
        for word in search_words:
            # shortcut: 검색 결과 첫 쪽만 본다(제목 일치 글은 소수), 모자라면 currPage로 더 넘긴다.
            listing = fetch(f"{board}&searchType=sj&searchValue={quote(word)}")
            for a in BeautifulSoup(listing, "html.parser").select("a.nttInfoBtn"):
                title = htmllib.unescape(_text(a))  # 학교 CMS가 괄호를 &#40; 로 이중 이스케이프하기도 한다
                if any(w in title.replace(" ", "") for w in title_words):
                    found.setdefault(board.replace("selectNttList", "selectNttInfo") + f"&nttSn={a['data-id']}", title)
    return found


def find_posts(homepage_url: str, fetch: Callable[[str], str], search_words: tuple[str, ...],
               title_words: tuple[str, ...]) -> list[Post]:
    found = _candidates(homepage_url, fetch, search_words, title_words)
    return [_read_post(url, title, fetch) for url, title in found.items()]


def find_textbook_posts(homepage_url: str, fetch: Callable[[str], str]) -> list[Post]:
    return find_posts(homepage_url, fetch, SEARCH_WORDS, TITLE_WORDS)


ASSESSMENT_SEARCH = ("평가계획", "평가 계획")  # 띄어 쓴 제목도 잡는다
MAX_ASSESSMENT_POSTS = 6
_YEAR = re.compile(r"(\d{4})\s*학년도")


def _post_number(url: str) -> int:
    return int(url.rsplit("nttSn=", 1)[1])


def find_assessment_posts(homepage_url: str, fetch: Callable[[str], str]) -> list[Post]:
    """학생평가계획 글 중 가장 최근 학년도 것만, 글 번호 오름차순(나중 글이 수정본이면 뒤에 온다)으로."""
    found = _candidates(homepage_url, fetch, ASSESSMENT_SEARCH, ("평가계획",))
    years = {url: int(m[1]) for url, title in found.items() if (m := _YEAR.search(title))}
    if not years:
        return []
    newest = max(years.values())
    # shortcut: 최근 학년도 글 중 번호가 큰 6개만 읽는다(학년도당 학기별 1~2개 + 수정 안내), 모자라면 상한을 올린다.
    keep = sorted((u for u, y in years.items() if y == newest), key=_post_number)[-MAX_ASSESSMENT_POSTS:]
    return [_read_post(u, found[u], fetch) for u in keep]


def _read_post(url: str, title: str, fetch: Callable[[str], str]) -> Post:
    html = fetch(url)
    body = _text(BeautifulSoup(html, "html.parser").select_one(".bbsV_cont"))
    # 첨부는 링크가 아니라 DEXT5 업로더 스크립트의 AddUploadedFile("키", "파일명", "/upload/...경로", ...)에 있다.
    files = [Attachment(name, urljoin(url, path)) for name, path in _ATTACH.findall(html)]
    return Post(title=title, url=url, body=body, attachments=files)
