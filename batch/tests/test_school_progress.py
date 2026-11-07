import re
from pathlib import Path

from eduapp_batch.extract_text import extract_text
from eduapp_batch.school_progress import AssessmentPlan, ProgressRow, parse_assessment_plan

FIX = Path(__file__).parent / "fixtures"


def plan(name: str) -> AssessmentPlan:
    p = parse_assessment_plan(extract_text(name, (FIX / name).read_bytes()))
    assert p is not None
    return p


def test_grade1_hwp_rows():
    p = plan("assessment_1_1.hwp")
    assert (p.school_year, p.grade, p.semester) == (2026, 1, 1)
    assert ProgressRow("국어", "[2국01-04]", "2. 받침이 있는 글자를 읽어요", 5) in p.rows
    assert ProgressRow("국어", "[2국04-03]", "6. 또박또박 읽어요", 7) in p.rows
    assert ProgressRow("수학", "[2수03-01]", "2. 여러 가지 모양", 5) in p.rows
    assert any(r.standard_code == "[2바01-01]" and r.subject == "바른 생활" for r in p.rows)


def test_grade4_hwpx_rows_and_code_variants():
    p = plan("assessment_4_1.hwpx")
    assert (p.school_year, p.grade, p.semester) == (2026, 4, 1)
    by = {r.standard_code: r for r in p.rows}
    assert by["[4국02-04]"].month == 4 and by["[4국02-04]"].subject == "국어"
    assert by["[4사05-01]"].month == 4
    assert "[4영01-07]" in by  # 여는 괄호가 빠진 표기
    assert "[4영02-04]" in by  # [4영어02-04] 표기
    assert all(re.fullmatch(r"\[4[가-힣]\d{2}-\d{2}\]", c) for c in by)


def test_glued_text_still_yields_rows():
    p = plan("assessment_3_1.hwpx")
    assert p.grade == 3 and "[4영02-01]" in {r.standard_code for r in p.rows}  # [4영 02-01] 정규화
    assert p.dropped < 0.3 * (len(p.rows) + p.dropped)


def test_ignores_rows_without_standard_code():
    p = plan("assessment_4_1.hwpx")
    assert not any("자율" in r.unit_title or "동아리" in r.unit_title for r in p.rows)
    assert 20 <= len(p.rows) <= 26


def test_month_range_uses_first_month_and_missing_month_is_dropped():
    text = "2026학년도 귀인초 3학년 1학기 학생평가 계획\n국어\n[4국01-01] 설명\n1. 단원\n읽기\n3월~4월\n[4국01-02] 설명2\n2. 둘째\n수시\n"
    p = parse_assessment_plan(text)
    assert p.rows == [ProgressRow("국어", "[4국01-01]", "1. 단원", 3)]
    assert p.dropped == 1


def test_standard_code_spaces_normalized():
    text = "2026학년도 귀인초 3학년 2학기 학생평가 계획\n[4도 01-01] 설명\n1. 나\n4월\n"
    assert parse_assessment_plan(text).rows[0].standard_code == "[4도01-01]"


def test_paren_grade_header_and_no_header():
    p = parse_assessment_plan("2025학년도 귀인초 ( 2 )학년 2학기 학생평가 계획\n[2국05-03] 설명\n4. 마음을 전해요\n10월\n")
    assert (p.school_year, p.grade, p.semester) == (2025, 2, 2)
    assert parse_assessment_plan("아무 글") is None
