"""학교 평가계획 → 예상 진도 수집: python -m eduapp_batch.run_progress
공지에서 학년·학기별 평가계획 첨부를 찾아 글자로 바꾸고, 코드로 파싱해 DB에 저장한다(AI 판단 없음)."""
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import date, datetime

import psycopg

from .extract_text import extract_text
from .parse import KST
from .run_programs import _fetch, _get
from .school_notices import UnsupportedSite, find_assessment_posts
from .school_progress import ProgressRow, parse_assessment_plan
from .store import PgStore, RestStore

# shortcut: 하루 20개 학교까지만 — 학교마다 요청이 수십 건이라 나머지는 다음 날 실행이 이어받는다.
MAX_SCHOOLS = 20
# shortcut: 학교당 첨부 24개까지만 내려받는다(최신 학년도 게시물 6개 × 학년별 첨부), 더 올리는 학교가 있으면 늘린다.
MAX_ATTACHMENTS = 24
SCHOOL_PAUSE, DOWNLOAD_PAUSE = 1.0, 0.5


def _err(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _collect(store, school: dict, fetch, fetch_bytes, sleep) -> tuple[int, str | None] | str:
    """(저장한 행 수, 비고) 또는 읽을 게 없는 사유 문자열. 다운로드가 전부 실패한 경우 등은 예외."""
    if not (school["homepage_url"] or "").strip():
        return "홈페이지 주소 없음"
    try:
        posts = find_assessment_posts(school["homepage_url"], fetch)
    except UnsupportedSite:
        return "지원하지 않는 홈페이지"
    if not posts:
        return "평가계획 공지 없음"
    entries: dict[tuple, tuple[int, int, int, ProgressRow, str]] = {}  # 같은 키는 더 최신 게시물이 이긴다
    downloads = failures = with_text = dropped = 0
    last_error: Exception | None = None
    for p in reversed(posts):  # 최신 게시물(수정 안내)부터 내려받는다 — 상한에 걸려도 수정본이 남고, 같은 키는 먼저 본 값이 이긴다
        for att in p.attachments:
            if downloads >= MAX_ATTACHMENTS:
                break
            if downloads:
                sleep(DOWNLOAD_PAUSE)
            downloads += 1
            try:
                text = extract_text(att.name, fetch_bytes(att.url))
            except Exception as e:  # noqa: BLE001 — 첨부 하나 실패는 건너뜀
                failures, last_error = failures + 1, e
                continue
            if not text.strip():
                continue
            with_text += 1
            plan = parse_assessment_plan(text)
            if plan is None:
                continue
            dropped += plan.dropped
            for r in plan.rows:
                entries.setdefault((plan.school_year, plan.grade, plan.semester, r.subject, r.standard_code), (
                    plan.school_year, plan.grade, plan.semester, r, p.url))
    if failures and not with_text:  # 파일을 못 받았을 뿐 공지가 없는 게 아니다 → 완료로 표시하지 않고 다시 시도
        raise last_error
    if not with_text:
        return "첨부에서 글자를 읽지 못함"
    if not entries:
        return "평가계획 형식을 읽지 못함"
    saved = rejected = 0
    for year, grade, semester, row, url in entries.values():
        try:
            store.apply_progress(school["id"], year, grade, semester, row, url)
            saved += 1
        except Exception as e:  # noqa: BLE001 — DB가 거부한 행 하나가 학교 전체를 막지 않게
            if saved == 0 and rejected == len(entries) - 1:
                raise  # 마지막 행까지 전부 거부됐다면 저장소 장애로 본다
            rejected += 1
    note = "; ".join(x for x in (f"월을 못 찾아 버린 행 {dropped}개" if dropped else "",
                                f"DB가 거부한 행 {rejected}개" if rejected else "") if x) or None
    return saved, note


def run(store, fetch: Callable[[str], str], fetch_bytes: Callable[[str], bytes], today: date,
        sleep: Callable[[float], None] = time.sleep) -> dict[str, str | int]:
    result: dict[str, str | int] = {}
    for i, s in enumerate(store.schools_needing_progress(today)[:MAX_SCHOOLS]):
        if i:
            sleep(SCHOOL_PAUSE)
        code, target = s["neis_code"], f"progress:{s['neis_code']}"
        try:
            try:
                out = _collect(store, s, fetch, fetch_bytes, sleep)
                if isinstance(out, str):
                    result[code] = out
                    store.record_run(target, False, None, out)
                else:
                    result[code] = out[0]
                    store.record_run(target, True, out[0], out[1])
                store.set_progress_collected(s["id"])  # 못 찾았어도 30일 뒤에 다시 본다
            except Exception as e:  # noqa: BLE001
                result[code] = msg = _err(e)
                store.record_run(target, False, None, msg)  # 수집 완료로 표시하지 않아 다음 실행에서 다시 시도
        except Exception as e:  # noqa: BLE001 — 오류 기록 중 DB 호출이 실패해도 이 학교만 오류로 남기고 계속
            result[code] = _err(e)
    return result


def main() -> int:
    def go(store):
        return run(store, _fetch, lambda u: _get(u).content, datetime.now(KST).date())
    try:
        if os.environ.get("SUPABASE_URL"):
            result = go(RestStore(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]))
        else:
            with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
                result = go(PgStore(conn))
    except Exception as e:  # noqa: BLE001 — 저장소 연결 불가 같은 전체 실패
        print(json.dumps({"error": _err(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
