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
    try:
        if m := _FULL.search(text):
            return date(*map(int, m.groups()))
        if m := _SHORT.search(text):
            return _short_year(int(m[1]), int(m[2]), today)
    except ValueError:  # "2.30" 같은 없는 날짜
        pass
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
    i = t.find("초")
    if i < 0:  # 초등 언급 없음: 중·고·유아 대상
        return (1, 6) if t == "전학년" else None
    parts = re.split(r"중|고(?!학년)", t[i:], maxsplit=1)  # 초등 부분만, 뒤에 중·고가 이어지는지
    nums = [int(n) for n in re.findall(r"(?<!\d)([1-6])(?![\d세년])", parts[0])]
    if not nums:
        return (1, 3) if "저학년" in t else (4, 6) if "고학년" in t else (1, 6)
    lo, hi = min(nums), max(nums)
    if "세" in t[:i] or "이하" in t:  # "7세~초2", "초등 2학년 이하"
        lo = 1
    if "이상" in t or len(parts) > 1:  # "초등 5학년 이상", "초등 4학년~중등 2학년"
        hi = 6
    return lo, hi
