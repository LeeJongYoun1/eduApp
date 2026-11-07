"""학교 학생평가계획 글자 → 과목·성취기준·단원명·평가 월. 줄 단위 파서(AI 판단 없음)."""
import re
from dataclasses import dataclass

# 성취기준 코드의 과목 글자 → 과목명. 코드는 모든 행에 있어 표 모양(칸이 한 글자씩 갈라지거나 약어로 적힘)에 흔들리지 않는다.
SUBJECT_BY_CODE_CHAR = {
    "국": "국어", "수": "수학", "사": "사회", "도": "도덕", "과": "과학", "체": "체육", "음": "음악",
    "미": "미술", "영": "영어", "실": "실과", "바": "바른 생활", "슬": "슬기로운 생활", "즐": "즐거운 생활",
}
# 여는 괄호가 빠지거나(`4영01-07]`) 공백이 끼거나(`[4영 02-01]`) 과목이 두 글자(`[4영어02-04]`)인 표기도 받는다.
_CODE = re.compile(r"^\[?\s*(\d)\s*([가-힣]+)\s*(\d{2})\s*-\s*(\d{2})\s*\]")
_HEADER = re.compile(r"(\d{4})\s*학년도[^\n]*?(\d)\s*\)?\s*학년\s*(\d)\s*학기")
_MONTH = re.compile(r"(\d{1,2})\s*월")
_ONLY_NUMBER = re.compile(r"^\d+\.?$")


@dataclass(frozen=True)
class ProgressRow:
    subject: str
    standard_code: str
    unit_title: str
    month: int


@dataclass(frozen=True)
class AssessmentPlan:
    school_year: int
    grade: int
    semester: int
    rows: list[ProgressRow]
    dropped: int  # 월을 못 찾아 버린 행 수


def parse_assessment_plan(text: str) -> AssessmentPlan | None:
    lines = [x.strip() for x in text.split("\n")]
    header = _HEADER.search("\n".join(lines[:20]))
    if not header:
        return None
    year, grade, semester = (int(g) for g in header.groups())
    starts = [(i, m) for i, x in enumerate(lines) if (m := _CODE.match(x))]
    # 칸이 합쳐진 표: 성취기준 줄이 연달아 나오면 단원·월은 마지막 코드 뒤에 한 번만 나온다 → 뒤에서부터 물려준다.
    found: list[tuple[str, int] | None] = [None] * len(starts)
    carry = None
    for n in range(len(starts) - 1, -1, -1):
        i = starts[n][0]
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        found[n] = _unit_and_month(lines, i, end) or (carry if end == i + 1 else None)
        carry = found[n]
    rows: dict[str, ProgressRow] = {}
    dropped = 0
    for (i, m), got in zip(starts, found):
        subject = SUBJECT_BY_CODE_CHAR.get(m[2][0])
        code = f"[{m[1]}{m[2][0]}{m[3]}-{m[4]}]"
        if subject is None or got is None:
            dropped += 1
        elif code not in rows:
            rows[code] = ProgressRow(subject, code, got[0], got[1])
    return AssessmentPlan(year, grade, semester, list(rows.values()), dropped)


def _unit_and_month(lines: list[str], i: int, end: int) -> tuple[str, int] | None:
    """성취기준 줄(i) 다음부터 end 전까지에서 단원명과 평가 월을 찾는다."""
    # shortcut: 단원명은 성취기준 다음 한 줄(번호만 있으면 두 줄)로 본다, 여러 줄로 갈라지는 학교가 나오면 영역 단어 목록으로 끊는다
    j = i + 1
    unit = lines[j] if j < end else ""
    if _ONLY_NUMBER.match(unit) and j + 1 < end:
        unit = f"{unit} {lines[j + 1]}"
        j += 1
    month = next((int(mo[1]) for x in lines[j + 1:end] if (mo := _MONTH.search(x)) and 1 <= int(mo[1]) <= 12), None)
    return (unit, month) if unit and month is not None else None
