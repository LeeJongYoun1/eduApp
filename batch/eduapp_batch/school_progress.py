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
# 평가 시기 칸은 줄 전체가 `5월`·`3월~4월`이다. 평가 요소 설명 속 "5월 날씨 그래프" 같은 글은 월로 보지 않는다.
_MONTH = re.compile(r"\s*(\d{1,2})\s*월(?:\s*[~,\-·]\s*\d{1,2}\s*월)*\s*")
_NUMBERED = re.compile(r"\d+\s*[.\-]\s*\S.*|\d+\s*\.?")  # `2. 단원명` 또는 번호만(`6.`)


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
    raw = text.split("\n")  # 칸이 두 문단으로 감기면 앞 문단이 공백으로 끝나므로 원본 줄도 둔다
    lines = [x.strip() for x in raw]
    header = _HEADER.search("\n".join(lines[:20]))
    if not header:
        return None
    year, grade, semester = (int(g) for g in header.groups())
    band = (grade + 1) // 2 * 2  # 성취기준 코드의 학년군 숫자: 1~2학년=2, 3~4=4, 5~6=6
    starts = [(i, m) for i, x in enumerate(lines) if (m := _CODE.match(x))]
    # 칸이 합쳐진 표: 성취기준 줄이 연달아 나오면 단원·월은 마지막 코드 뒤에 한 번만 나온다 → 뒤에서부터 물려준다.
    found: list[tuple[str, int] | None] = [None] * len(starts)
    carry = None
    for n in range(len(starts) - 1, -1, -1):
        i = starts[n][0]
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        found[n] = _unit_and_month(raw, lines, i, end, bool(lines[i][_CODE.match(lines[i]).end():].strip())) or (
            carry if end == i + 1 else None)
        carry = found[n]
    rows: dict[str, ProgressRow] = {}
    dropped = 0
    for (i, m), got in zip(starts, found):
        subject = SUBJECT_BY_CODE_CHAR.get(m[2][0])
        code = f"[{m[1]}{m[2][0]}{m[3]}-{m[4]}]"
        if subject is None or got is None or int(m[1]) != band:  # 다른 학년군 코드는 틀린 데이터라 버린다
            dropped += 1
        elif code not in rows:
            rows[code] = ProgressRow(subject, code, got[0], got[1])
    return AssessmentPlan(year, grade, semester, list(rows.values()), dropped)


def _unit_and_month(raw: list[str], lines: list[str], i: int, end: int, desc_inline: bool) -> tuple[str, int] | None:
    """성취기준 줄(i) 다음부터 end 전까지에서 단원명과 평가 월을 찾는다."""
    month_at = next((k for k in range(i + 1, end) if _MONTH.fullmatch(lines[k])), None)
    if month_at is None:
        return None
    # 단원명: 월 앞에서 `2. 단원명` 꼴 첫 줄. 설명이 따로 문단으로 나뉘어도 번호 줄을 찾는다.
    # shortcut: 번호 없는 단원명은 설명이 코드 줄에 붙어 있을 때만 다음 줄을 쓴다, 번호 없는 표가 많은 학교가 나오면 규칙을 늘린다.
    k = next((k for k in range(i + 1, month_at) if _NUMBERED.fullmatch(lines[k])), None)
    if k is None:
        if not (desc_inline and i + 1 < month_at):
            return None
        k = i + 1
    unit = lines[k]
    # 단원 칸이 두 문단으로 감기면 앞 문단이 공백으로 끝나거나(`2. 물의 `) 번호만 있다(`6.`)
    if k + 1 < month_at and (raw[k].endswith((" ", "\u3000")) or re.fullmatch(r"\d+\.?", unit)):
        unit = f"{unit} {lines[k + 1]}".strip()
    month = int(_MONTH.fullmatch(lines[month_at]).group(1))
    return (unit, month) if unit and 1 <= month <= 12 else None
