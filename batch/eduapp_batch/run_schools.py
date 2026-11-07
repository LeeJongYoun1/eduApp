"""학교 교과서·학사일정 수집: python -m eduapp_batch.run_schools prepare|apply [--work DIR]
prepare가 첨부 글자를 work/<neis_code>/에 쓰면 Claude 세션이 answer.json을 쓰고, apply가 DB에 반영한다."""
import argparse
import json
import os
import shutil
import sys
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import psycopg

from .extract_text import extract_text
from .parse import KST
from .run_programs import _fetch, _get
from .school_calendar import fetch_schedule
from .school_notices import UnsupportedSite, find_textbook_posts
from .store import PgStore, RestStore

# shortcut: 게시물에 날짜가 없어 최근순을 못 가리므로 앞에서 8개 게시물·12개 첨부까지만 읽는다 — 학교가 더 많이 올리면 늘린다.
MAX_POSTS, MAX_ATTACHMENTS = 8, 12
# shortcut: 하루 20개 학교까지만 수집 — Claude 세션이 학교마다 파일을 최대 12개 읽어야 해서, 나머지는 다음 날 실행이 이어받는다.
MAX_SCHOOLS = 20
SCHOOL_PAUSE, DOWNLOAD_PAUSE = 1.0, 0.5
NO_CERTAIN = "답안에 확신하는 출판사 없음"


def _err(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _collect(school: dict, fetch, fetch_bytes, work: Path, sleep) -> int | str:
    """글자 파일 수를 돌려주고, 수집할 게 없으면 not_found 사유 문자열, 그 밖엔 예외."""
    if not (school["homepage_url"] or "").strip():
        return "홈페이지 주소 없음"
    try:
        posts = find_textbook_posts(school["homepage_url"], fetch)[:MAX_POSTS]
    except UnsupportedSite:
        return "지원하지 않는 홈페이지"
    if not posts:
        return "교과서 선정 공지 없음"
    texts: list[tuple[str, str, str, str]] = []  # (게시물 제목, 이름, 글자, 게시물 주소)
    downloads = failures = att_texts = 0
    last_error: Exception | None = None
    for p in posts:
        if p.body.strip():
            texts.append((p.title, "(본문)", p.body, p.url))
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
            if text.strip():
                att_texts += 1
                texts.append((p.title, att.name, text, p.url))
    if failures and not att_texts:  # 파일을 못 받은 것은 '공지 없음'이 아니라 재시도 대상 (본문이 "붙임 참조"뿐일 수 있다)
        raise last_error  # type: ignore[misc]
    if not texts:
        return "첨부에서 글자를 읽지 못함"
    out = work / school["neis_code"]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("text_*.txt"):
        old.unlink()
    (out / "answer.json").unlink(missing_ok=True)  # 어제 답안이 오늘 글과 짝지어 반영되지 않게
    for n, (title, name, text, _) in enumerate(texts, 1):
        (out / f"text_{n}.txt").write_text(f"# {title} | {name}\n{text}\n", encoding="utf-8")
    (out / "meta.json").write_text(json.dumps({"school_id": school["id"], "source_url": texts[0][3]},
                                              ensure_ascii=False), encoding="utf-8")
    return len(texts)


def prepare(store, fetch: Callable[[str], str], fetch_bytes: Callable[[str], bytes], key: str, work: Path,
            today: date, sleep: Callable[[float], None] = time.sleep) -> dict[str, str | int]:
    for s in store.schools_with_children():  # ① 학사일정: 실패해도 교과서 수집·다음 학교는 계속
        target = f"calendar:{s['neis_code']}"
        try:
            try:
                n = store.upsert_calendar(s["id"], fetch_schedule(s["edu_office_code"], s["neis_code"], key, today))
                store.record_run(target, True, n, None)
            except Exception as e:  # noqa: BLE001
                store.record_run(target, False, None, _err(e))
        except Exception:  # noqa: BLE001 — 기록 자체가 실패해도(저장소 5xx) 다음 학교로
            pass
    result: dict[str, str | int] = {}
    for i, s in enumerate(store.schools_to_collect(today)[:MAX_SCHOOLS]):  # ② 교과서
        if i:
            sleep(SCHOOL_PAUSE)
        code, target = s["neis_code"], f"school:{s['neis_code']}"
        try:
            try:
                result[code] = out = _collect(s, fetch, fetch_bytes, work, sleep)
                if isinstance(out, str):
                    store.set_school_status(s["id"], "not_found")
                    store.record_run(target, False, None, out)
            except Exception as e:  # noqa: BLE001
                result[code] = msg = _err(e)
                store.set_school_status(s["id"], "failed")
                store.record_run(target, False, None, msg)
        except Exception as e:  # noqa: BLE001 — 오류 처리 중 DB 호출이 실패해도 이 학교만 오류로 남기고 계속
            result[code] = _err(e)
    return result


def _items(answer) -> list[dict]:
    items = answer["items"] if isinstance(answer, dict) else None
    ok = isinstance(items, list) and all(
        isinstance(i, dict) and type(i.get("grade")) is int and isinstance(i.get("subject"), str)
        and isinstance(i.get("publisher"), str) and isinstance(i.get("certain"), bool) for i in items)
    if not ok:
        raise ValueError("answer.json 형식 오류")
    return items


def _apply_dir(store, work: Path, d: Path) -> int | str:
    code, target = d.name, f"school:{d.name}"
    try:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        school_id, source_url = meta["school_id"], meta["source_url"]
        items = _items(json.loads((d / "answer.json").read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001 — 형식이 틀리면 아무것도 저장하지 않고 폴더도 그대로 둔다
        msg = _err(e)
        store.record_run(target, False, None, msg)
        return msg
    saved = 0
    for it in (i for i in items if i["certain"]):
        try:
            store.apply_textbook(school_id, it["grade"], it["subject"], it["publisher"].strip(), source_url)
            saved += 1
        except Exception as e:  # noqa: BLE001 — 잘못된 항목만 건너뜀
            store.record_run(target, False, None, f"{it['grade']}학년 {it['subject']}: {_err(e)}")
    if saved:
        store.set_school_status(school_id, "done")
        store.record_run(target, True, saved, None)
    else:
        store.set_school_status(school_id, "not_found")
        store.record_run(target, False, None, NO_CERTAIN)
    dest = work / "_done" / code
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(exist_ok=True)
    shutil.move(d, dest)
    return saved


def apply(store, work: Path) -> dict[str, str | int]:
    result: dict[str, str | int] = {}
    for answer in sorted(work.glob("*/answer.json")):
        try:
            result[answer.parent.name] = _apply_dir(store, work, answer.parent)
        except Exception as e:  # noqa: BLE001 — DB 오류는 그 학교만 오류로 남긴다(폴더는 그대로라 다음 실행에서 멱등 재시도)
            result[answer.parent.name] = _err(e)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prepare", "apply"])
    ap.add_argument("--work", type=Path, default=Path("work"))
    args = ap.parse_args()

    def run(store):
        if args.command == "apply":
            return apply(store, args.work)
        return prepare(store, _fetch, lambda u: _get(u).content, os.environ["NEIS_API_KEY"], args.work,
                       datetime.now(KST).date())
    try:
        if os.environ.get("SUPABASE_URL"):
            result = run(RestStore(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]))
        else:
            with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
                result = run(PgStore(conn))
    except Exception as e:  # noqa: BLE001 — 저장소 연결 불가 같은 전체 실패
        print(json.dumps({"error": _err(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
