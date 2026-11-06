"""기관 페이지의 한국식 날짜·학년 표기 해석."""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
_FULL = re.compile(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_SHORT = re.compile(r"(?<!\d)(\d{1,2})\s*[.\-/월]\s*(\d{1,2})(?!\d)")
_TIME = re.compile(r"(\d{1,2}):(\d{2})")


def _short_year(month: int, day: int, today: date) -> date:
    # 연도 없는 날짜: 오늘보다 2개월 넘게 지났으면 내년으로 본다.
    d = date(today.year, month, day)
    return date(today.year + 1, month, day) if d < today - timedelta(days=61) else d


def parse_date(text: str, today: date) -> date | None:
    if m := _FULL.search(text):
        return date(*map(int, m.groups()))
    if m := _SHORT.search(text):
        return _short_year(int(m[1]), int(m[2]), today)
    return None


def parse_date_range(text: str, today: date) -> tuple[date | None, date | None]:
    parts = re.split(r"[~∼〜]", text, maxsplit=1)
    start = parse_date(parts[0], today)
    if len(parts) == 1:
        return start, start
    end = parse_date(parts[1], today)
    if start and end and end < start:  # "12.20~1.10": 끝이 해를 넘긴다
        end = end.replace(year=start.year + 1) if end.year == start.year else end
    return start, end


def parse_datetime(text: str, today: date) -> datetime | None:
    d, t = parse_date(text, today), _TIME.search(text)
    if not d or not t:
        return None
    return datetime(d.year, d.month, d.day, int(t[1]), int(t[2]), tzinfo=KST)


def parse_grades(text: str) -> tuple[int, int] | None:
    t = text.replace(" ", "")
    if "전학년" in t or re.fullmatch(r"초등학생(전체)?", t):
        return 1, 6
    nums = [int(n) for n in re.findall(r"(?:초등?|^|[~\-])(\d)(?:학년)?", t) if 1 <= int(n) <= 6]
    if "초" not in t and "학년" not in t:
        return None
    if not nums:
        return (1, 6) if "초등" in t else None
    if "세" in t:  # "7세~초2": 유아부터 시작하면 초등 1학년부터
        return 1, max(nums)
    return min(nums), max(nums)
