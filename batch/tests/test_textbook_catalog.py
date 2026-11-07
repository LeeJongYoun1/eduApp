import csv
from pathlib import Path

ROWS = list(csv.DictReader((Path(__file__).parents[1] / "data/textbooks_2022.csv").open(encoding="utf-8")))


def pubs(subject, grade):
    return {r["publisher"] for r in ROWS if r["subject"] == subject and r["grade"] == str(grade)}


def test_rows_are_well_formed_and_unique():
    keys = [(r["subject"], r["grade"], r["semester"], r["publisher"]) for r in ROWS]
    assert len(keys) == len(set(keys))
    assert all(r["grade"] in "3456" and r["semester"] in ("1", "2") and r["publisher"] and r["title"] for r in ROWS)
    assert not any("㈜" in r["publisher"] or "(주)" in r["publisher"] or " " in r["publisher"] for r in ROWS)


def test_known_counts_from_official_notices():
    assert len(pubs("수학", 3)) == len(pubs("수학", 6)) == 8
    assert len(pubs("과학", 4)) == 6 and len(pubs("과학", 5)) == 5  # 동아출판은 3~4학년만
    assert "미래엔" in pubs("음악", 3) and "미래엔" in pubs("음악", 4)  # 재검정 합격
    assert pubs("실과", 3) == set() and len(pubs("실과", 5)) == 9
    assert {r["semester"] for r in ROWS if r["subject"] == "영어"} == {"1"}  # 한 권짜리는 1학기로 저장
