# 계획 3: 학교 교과서 · 학사일정 · 우리 학교 화면 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자녀를 등록한 학교의 학사일정(쉬는 날)과 과목별 교과서 출판사를 배치가 수집해 DB에 저장하고, 앱이 "우리 학교" 탭에서 보여주며(확인 중 표시, 학부모 수정), 체험 목록을 "우리 학교 쉬는 날"로 걸러 보게 한다.

**Architecture:** 배치(`run_schools`)가 두 단계로 나뉜다. `prepare`는 코드가 하는 일(나이스 학사일정 저장, 학교 공지 게시판에서 교과서 선정 게시물을 찾고 첨부 hwp/pdf/hwpx를 글자로 바꿔 `work/` 폴더에 저장)을 하고, Claude 예약 작업이 그 글자를 읽어 과목별 출판사를 JSON 답안으로 쓰면, `apply`가 답안을 검증해 DB 함수 `apply_school_textbook()`으로 저장하고 학교 상태를 바꾼다. 교과서 목록(`textbooks`)은 비어 있으므로 별도 적재 없이 저장할 때 DB 함수가 필요한 행을 만든다. 앱은 `EduRepository`에 메서드를 더해 쓰고, 쉬는 날 필터는 앱에서 걸러낸다.

**Tech Stack:** PostgreSQL 16 + pytest / Python 3.12(`httpx`, `beautifulsoup4`, `pypdf`, `pyhwp`) / Flutter + flutter_test.

**Spec:** `docs/superpowers/specs/2026-11-06-eduapp-design.md` (학교 선택 → 교과서 수집 흐름 1~8번, 정확성 원칙) + `docs/02-prd.md` F7 · `docs/03-user-scenarios.md` S1(4~5번)·S3·S4 · `docs/06-architecture.md` 배치 순서

### 전체 계획 순서 (이 문서는 3번)
1. DB 기반 + 체험 프로그램 수집 (완료)
2. Flutter 앱 기본 (완료)
3. **학교 교과서 · 학사일정 · 우리 학교 화면** ← 이 문서
4. AI 생성(연결 단원, 가기 전에 읽어요, 오늘의 질문, 집 실험)
5. 알림 (교과서 준비 알림 포함)

## Global Constraints

- 지역은 `서울`·`경기`, 학년은 초등 1~6. 교과서 출판사는 **초3~6, 과목 `수학`·`사회`·`과학`·`영어`** 만 다룬다(스펙: 이 과목들이 검정 교과서). 과목 목록의 기준은 DB 함수 한 곳(`ensure_textbook`)이다.
- **확인 안 된 정보는 확신하듯 보이지 않는다.** 화면에는 `확인 중` 표시. AI 답안은 `certain: true`인 항목만 저장한다(애매하면 저장하지 않아 `확인 중`으로 남는다).
- 학부모가 고친 값(`source = 'parent'`)은 배치가 다시 덮어쓰지 않는다.
- 앱은 `school_textbooks`·`textbooks`·`collect_runs`를 직접 쓰지 않는다. 쓰기는 DB 함수(학부모)와 service role(배치)만.
- 실패는 학교 단위로 격리하고 `collect_runs`(`target = 'school:<neis_code>'`)에 남긴다. `failed` 학교는 다음 배치에서 다시 시도한다. `done` 학교는 마지막 수집 후 330일이 지나면 다시 수집한다(연 1회 재확인).
- 지원하는 학교 홈페이지는 **경기 공통 플랫폼(`*.goeay.kr`)** 뿐이다. 그 밖의 홈페이지(서울 등)는 `not_found` + `collect_runs.error = '지원하지 않는 홈페이지'`로 두고 학부모 직접 선택에 맡긴다.
- 문구: 해요체. 상태 문구는 정확히 — 수집 대기 `교과서 정보를 확인하고 있어요 (내일 아침까지)`, 못 찾음 `학교 공지에서 찾지 못했어요. 알고 계시면 알려주세요`, 쉬는 날 정보 없음 `쉬는 날 정보가 아직 없어요`.
- 마이그레이션은 `supabase/migrations/`에 새 파일로 추가한다(`20261108000001_school_info.sql`). 원격 DB에는 이력 테이블이 없으므로 Management API SQL 쿼리로 적용하고, 같은 파일을 두 번 적용하지 않는다.
- **사용자 준비 (Task 1 전에 확인받는다):** 시범 학교 5곳(경기 `goeay.kr` 4곳 이상)을 정해 알려준다. 나이스 키 `NEIS_API_KEY`는 이미 등록돼 있다.
- **실행 환경 전제:** DB 테스트는 `pg_ctlcluster 16 main start`로 로컬 Postgres를 먼저 켠다. Flutter SDK가 없으면 계획 2 Task 3의 설치 방법을 따른다.

## Review Focus

1. **학교 홈페이지가 JS로 리다이렉트** (`goeay.kr` 첫 페이지는 `location.href=`만 있는 빈 페이지) → 따라가서 본문을 읽는다. (Task 3 `follows js redirect`)
2. **첨부가 스캔 이미지 PDF라 글자가 없음** → `failed`가 아니라 `not_found` + 이유 `첨부에서 글자를 읽지 못함`. (Task 4 `image only pdf gives empty text`, Task 6 `empty text marks not_found`)
3. **학부모가 고친 뒤 배치가 다시 돎** → 학부모 값 유지. (Task 1 `batch does not overwrite parent`)
4. **새 학교·방학 직후라 학사일정이 비어 있음** → 쉬는 날 필터를 켜도 빈 화면 대신 `쉬는 날 정보가 아직 없어요`. (Task 9 `no holidays shows notice`)
5. **여러 날에 걸친 프로그램이 쉬는 날 하루와 겹침** → 시작일·종료일 사이에 쉬는 날이 하루라도 있으면 보인다. 종료일 없는 프로그램은 시작일 하루로 본다. (Task 9 `multi day program overlapping holiday is kept`)

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `supabase/migrations/20261108000001_school_info.sql` | 교과서 저장·수정·조회 DB 함수 |
| `batch/eduapp_batch/school_calendar.py` | 나이스 학사일정 → 쉬는 날 행 |
| `batch/eduapp_batch/school_notices.py` | 학교 홈페이지 공지에서 교과서 게시물·첨부 찾기 |
| `batch/eduapp_batch/extract_text.py` | 첨부(pdf/hwpx/hwp) → 글자 |
| `batch/eduapp_batch/run_schools.py` | `prepare` / `apply` 실행기 |
| `batch/eduapp_batch/store.py` (수정) | 학교용 저장·조회 메서드 (PgStore·RestStore) |
| `app/lib/data/*` (수정) | 모델·repository 확장 |
| `app/lib/screens/school_tab.dart` | 우리 학교 탭 |
| `app/lib/screens/programs_tab.dart` (수정) | 쉬는 날 필터 |

---

### Task 1: DB 함수

**Files:**
- Create: `supabase/migrations/20261108000001_school_info.sql`
- Test: `batch/tests/test_school_info.py`

**Interfaces:**
- Produces (SQL):
  - `ensure_textbook(p_subject text, p_grade int, p_publisher text) returns bigint` — 내부용. 과목이 수학·사회·과학·영어가 아니거나 학년이 3~6이 아니거나 출판사가 공백 제외 1~20자가 아니면 예외. `textbooks`에 `(curriculum '2022', subject, grade, semester null, publisher)` 행을 없으면 만들고 id를 돌려준다(title은 `<과목> <학년>학년`).
  - `apply_school_textbook(p_school_id bigint, p_grade int, p_subject text, p_publisher text, p_source_url text) returns void` — 배치용(service role만 실행). `confidence 'confirmed'`, `source 'auto'`로 저장. 이미 `source = 'parent'`인 행이면 아무것도 하지 않는다.
  - `correct_school_publisher(p_child_id bigint, p_subject text, p_publisher text) returns void` — 학부모용(authenticated). 본인 자녀가 아니면 예외 `not your child`. `confirmed`/`parent`로 덮어쓴다.
  - `child_textbooks(p_child_id bigint) returns table(subject text, publisher text, confidence info_confidence, source info_source, source_url text, is_guess boolean)` — 본인 자녀만. 자녀 학년이 3~6이면 네 과목 모두 한 줄씩(수학·사회·과학·영어 순). 학교에 저장된 값이 있으면 그 출판사(`is_guess false`), 없으면 같은 학년·과목에서 전체 학교가 가장 많이 쓰는 출판사(`mode()`, `confidence 'unverified'`, `is_guess true`), 그것도 없으면 `publisher null`. 학년이 3 미만이면 0줄.
- 기존 `correct_school_textbook`은 그대로 둔다. `textbooks`의 유일 제약을 `nulls not distinct`로 바꾼다(semester가 null이라 중복이 생기므로).

- [ ] **Step 1: 실패하는 테스트 작성** — `batch/tests/test_school_info.py`. `test_app_basics.py`의 `add_user`·`as_user` 패턴을 쓴다. 테스트 이름과 단언:
  - `test_apply_creates_textbook_and_school_row`: `apply_school_textbook(school, 4, '과학', '천재교육', 'https://x')` 후 `school_textbooks`에 `(confirmed, auto, 'https://x')` 1행, `textbooks` 1행. 같은 인자로 다시 호출해도 `textbooks`는 1행.
  - `test_apply_rejects_bad_input`: 과목 `'체육'`, 학년 2, 출판사 `'  '`, 출판사 21자 각각 예외.
  - `test_batch_does_not_overwrite_parent`: 학부모가 `correct_school_publisher(child, '과학', '비상교육')` 한 뒤 `apply_school_textbook(..., '천재교육', ...)` → 출판사는 `비상교육`, `source = 'parent'` 그대로.
  - `test_correct_requires_own_child`: 다른 사용자의 자녀로 호출하면 `not your child`.
  - `test_child_textbooks_uses_school_row_then_guess`: 학교 A에 과학=천재교육 2곳(A, B)·비상교육 1곳(C)을 저장 → 학교 D 자녀(4학년)의 과학은 `천재교육, is_guess true, unverified`, 수학은 `publisher null`. 학교 A 자녀는 과학이 `is_guess false, confirmed`.
  - `test_child_textbooks_empty_for_grade_under_3`.
- [ ] **Step 2: 실패 확인** — Run: `cd batch && pytest tests/test_school_info.py -v` / Expected: FAIL (`function ... does not exist`)
- [ ] **Step 3: 마이그레이션 작성** — 위 인터페이스 그대로. `security definer set search_path = public`. `apply_school_textbook`·`ensure_textbook`은 `revoke execute ... from public, anon, authenticated` 후 `service_role`에만 `grant`. `correct_school_publisher`·`child_textbooks`는 `authenticated`에 `grant`.
- [ ] **Step 4: 통과 확인** — Run: `cd batch && pytest tests/test_school_info.py tests/test_app_basics.py tests/test_schema.py -v` / Expected: PASS (기존 테스트 포함)
- [ ] **Step 5: Commit** — `git add supabase/migrations batch/tests/test_school_info.py && git commit -m "feat(db): school textbook apply/correct/list functions"`

---

### Task 2: 나이스 학사일정

**Files:**
- Create: `batch/eduapp_batch/school_calendar.py`, `batch/tests/fixtures/neis_school_schedule.json`
- Test: `batch/tests/test_school_calendar.py`

**Interfaces:**
- Consumes: `models.School`(기존)
- Produces: 
  - `@dataclass(frozen=True) CalendarDay(day: date, event_name: str, is_holiday: bool)` — `models.py`에 추가
  - `parse_schedule(payload: dict) -> list[CalendarDay]`
  - `fetch_schedule(edu_office_code: str, neis_code: str, key: str, today: date) -> list[CalendarDay]` — `https://open.neis.go.kr/hub/SchoolSchedule`, 오늘부터 365일 구간. 결과 없음(`INFO-200`)은 빈 리스트, 그 밖의 오류는 예외(`schools_list.fetch_office`와 같은 방식).

- [ ] **Step 1: 픽스처 저장** — 실제 API를 한 번 호출해(예: 경기 J10, 시범 학교 한 곳, 11월~다음 해 2월) 응답 JSON을 `neis_school_schedule.json`으로 저장한다. 휴업일·공휴일·평범한 행사가 모두 들어 있어야 한다.
- [ ] **Step 2: 실패하는 테스트 작성**
  - `test_parse_marks_holidays`: `SBTR_DD_SC_NM`이 `휴업일`·`공휴일`인 날은 `is_holiday True`, `해당없음`인 날은 `False`. 날짜는 `AA_YMD`(`YYYYMMDD`)를 `date`로.
  - `test_parse_skips_rows_not_for_any_grade_1_to_6`: `ONE_GRADE_EVENT_YN`~`SIX_GRADE_EVENT_YN`이 모두 `N`/`*`인 행은 제외(고등학교 전용 행사 방지).
  - `test_parse_no_result_is_empty`: `{"RESULT": {"CODE": "INFO-200"}}` → `[]`.
- [ ] **Step 3: 실패 확인** — Run: `cd batch && pytest tests/test_school_calendar.py -v` / Expected: FAIL (module not found)
- [ ] **Step 4: 구현** — `parse_schedule`, `fetch_schedule`. 같은 날 같은 `EVENT_NM`이 두 번 나오면 하나만(기본키 `(school_id, day, event_name)`).
- [ ] **Step 5: 통과 확인** — Run: `cd batch && pytest tests/test_school_calendar.py -v` / Expected: PASS
- [ ] **Step 6: Commit** — `git commit -m "feat(batch): neis school schedule parser"`

---

### Task 3: 학교 공지에서 교과서 게시물 찾기

**Files:**
- Create: `batch/eduapp_batch/school_notices.py`, `batch/tests/fixtures/school_*.html`
- Test: `batch/tests/test_school_notices.py`

**Interfaces:**
- Consumes: `fetch: Callable[[str], str]`(기존 `run_programs._fetch`와 같은 시그니처)
- Produces:
  - `@dataclass(frozen=True) Attachment(name: str, url: str)`, `@dataclass(frozen=True) Post(title: str, url: str, body: str, attachments: list[Attachment])`
  - `find_textbook_posts(homepage_url: str, fetch: Callable[[str], str]) -> list[Post]` — 지원하지 않는 홈페이지(`goeay.kr`이 아님)는 `UnsupportedSite` 예외. 관련 게시물이 없으면 `[]`.
  - `class UnsupportedSite(Exception)`

**알려진 사실(2026-11-07 조사):** `https://<학교>.goeay.kr` 첫 페이지는 `location.href="…/main.do"`만 있는 빈 페이지다. `main.do`의 메뉴에 `selectNttList.do?mi=…&bbsId=…` 링크가 있고 링크 글자는 `공지사항`·`가정통신문` 등이다. 목록 행은 `<a class="nttInfoBtn" data-id="<nttSn>">제목</a>`이며 상세는 `selectNttInfo.do?mi=…&bbsId=…&nttSn=<id>` 로 열린다. 페이지 이동은 `currPage`. 첨부는 JS 업로더(`DEXT5UPLOAD`)로 노출되어 `file_url`·`file_name` 값이 상세 페이지 스크립트에 들어 있다. **제목 검색(`searchCnd=SJ&searchKrwd=`)은 목록을 거르지 않았다** → 목록을 직접 훑어 제목에 `교과용도서`·`교과서`·`교재` 중 하나가 있는 글만 고른다. 게시판당 앞쪽 3쪽까지만 본다.

- [ ] **Step 1: 픽스처 저장** — 시범 학교 한 곳에서 실제 응답을 저장한다: 첫 페이지(리다이렉트), `main.do`, 공지사항 목록(제목에 `교과용도서`가 든 글이 있는 쪽), 그 글의 상세. 시범 학교 공지에 해당 글이 하나도 없으면 다른 `goeay.kr` 학교에서 찾아 저장하고, 어느 학교 것인지 파일 첫 줄 주석에 적는다. 상세의 첨부 스크립트 모양(어디에 `file_url`이 있는지)을 보고 아래 Step 3의 파서 방식을 정한다.
- [ ] **Step 2: 실패하는 테스트 작성** (가짜 `fetch`는 URL → 픽스처 딕셔너리)
  - `test_follows_js_redirect`: 첫 페이지의 `location.href`를 따라 `main.do`를 읽는다.
  - `test_picks_only_textbook_titles`: 목록의 다른 제목(`수익자부담금`)은 제외하고 `교과용도서` 글만 `Post`로.
  - `test_collects_attachment_urls`: 상세에서 첨부 이름·절대 URL 추출.
  - `test_unsupported_site_raises`: `https://x.sen.es.kr` → `UnsupportedSite`.
  - `test_no_match_returns_empty`.
- [ ] **Step 3: 실패 확인 후 구현** — Run: `cd batch && pytest tests/test_school_notices.py -v` / Expected: FAIL → 구현 후 PASS. 파싱은 `beautifulsoup4` + 정규식. 첨부 URL이 상대경로면 학교 도메인 기준으로 절대화.
- [ ] **Step 4: Commit** — `git commit -m "feat(batch): find textbook notices on goeay school sites"`

---

### Task 4: 첨부 → 글자

**Files:**
- Create: `batch/eduapp_batch/extract_text.py`, `batch/tests/fixtures/sample.pdf`, `batch/tests/fixtures/sample.hwp`
- Modify: `batch/pyproject.toml` (dependencies에 `pypdf>=4`, `pyhwp>=0.1b15`)
- Test: `batch/tests/test_extract_text.py`

**Interfaces:**
- Produces: `extract_text(name: str, data: bytes) -> str` — 확장자(소문자)가 `.pdf`·`.hwpx`·`.hwp`면 글자 반환, 그 밖의 확장자는 `""`. 파싱 오류는 예외를 밖으로 내지 않고 `""`.

- [ ] **Step 1: 픽스처 준비** — `sample.pdf`: 글자가 든 한 쪽짜리 PDF(`교과용도서 선정 결과 과학 4학년 천재교육` 포함). `sample.hwp`: 시범 학교 공지에서 받은 실제 hwp 중 개인정보 없는 것(없으면 이 테스트만 `pytest.mark.skip(reason=…)`로 표시하고 계획 끝의 "남은 일"에 적는다). `hwpx`는 테스트 안에서 `zipfile`로 만든다(`Contents/section0.xml`에 `<hp:t>` 글자).
- [ ] **Step 2: 실패하는 테스트 작성**
  - `test_pdf_text`: `"천재교육"`이 결과에 포함.
  - `test_hwpx_text`: 메모리에서 만든 hwpx에서 글자 추출.
  - `test_hwp_text`: `sample.hwp`에서 `"교과"` 포함.
  - `test_image_only_pdf_gives_empty_text`: 글자 없는 PDF(빈 페이지만) → `""`.
  - `test_unknown_extension_and_corrupt_bytes_give_empty`: `("a.zip", b"x")`, `("a.pdf", b"not a pdf")` → `""`.
- [ ] **Step 3: 실패 확인** — Run: `cd batch && pip install -q -e '.[test]' && pytest tests/test_extract_text.py -v` / Expected: FAIL
- [ ] **Step 4: 구현** — pdf는 `pypdf.PdfReader`, hwpx는 zip 안 `Contents/section*.xml`의 `t` 요소 글자, hwp는 `pyhwp`의 텍스트 추출. 
- [ ] **Step 5: 통과 확인 → Commit** — `git commit -m "feat(batch): extract text from pdf/hwp/hwpx attachments"`

---

### Task 5: 저장소 메서드

**Files:**
- Modify: `batch/eduapp_batch/store.py`
- Test: `batch/tests/test_store.py`, `batch/tests/test_store_rest.py` (기존 파일에 추가)

**Interfaces:**
- Consumes: `CalendarDay`(Task 2), DB 함수 `apply_school_textbook`(Task 1)
- Produces — `PgStore`와 `RestStore` 양쪽에 같은 이름·시그니처:
  - `schools_to_collect(today: date) -> list[dict]` — 키 `id, neis_code, edu_office_code, name, homepage_url, collect_status`. 조건: 상태가 `pending`·`failed`이거나, `done`이면서 `last_collected_at`이 330일보다 오래됨.
  - `schools_with_children() -> list[dict]` — 같은 키. 자녀가 한 명이라도 있는 학교(학사일정 갱신 대상).
  - `upsert_calendar(school_id: int, days: list[CalendarDay]) -> int`
  - `apply_textbook(school_id: int, grade: int, subject: str, publisher: str, source_url: str | None) -> None` — `apply_school_textbook` 호출.
  - `set_school_status(school_id: int, status: str) -> None` — `done`이면 `last_collected_at = now()`도 갱신. 상태는 `done`·`failed`·`not_found`만 허용.

- [ ] **Step 1: 실패하는 테스트 작성** (PgStore는 `db` 픽스처, RestStore는 기존 `test_store_rest.py`의 `httpx.MockTransport` 방식)
  - `test_schools_to_collect_selects_pending_failed_and_stale_done`: pending·failed·330일 지난 done은 포함, 방금 done·not_requested·not_found는 제외.
  - `test_schools_with_children_only`.
  - `test_upsert_calendar_is_idempotent`: 같은 입력 두 번 → 행 수 그대로.
  - `test_apply_textbook_and_set_status`: 행이 저장되고, `done`이면 `last_collected_at`이 채워진다. 잘못된 상태 문자열은 `ValueError`.
  - REST: `apply_textbook`이 `POST /rest/v1/rpc/apply_school_textbook`에 인자 이름 그대로(`p_school_id` …) 보낸다, `set_school_status`가 `PATCH /rest/v1/schools?id=eq.<id>`를 보낸다, `schools_to_collect`가 조건을 쿼리로 보낸다.
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `cd batch && pytest tests/test_store.py tests/test_store_rest.py -v`
- [ ] **Step 3: Commit** — `git commit -m "feat(batch): school collection store methods"`

---

### Task 6: `run_schools` 실행기

**Files:**
- Create: `batch/eduapp_batch/run_schools.py`
- Test: `batch/tests/test_run_schools.py`

**Interfaces:**
- Consumes: Task 2~5의 함수들
- Produces:
  - `prepare(store, fetch, fetch_bytes, key: str, work: Path, today: date) -> dict[str, str | int]` — 학교별 결과(`neis_code` → 글자 파일 수 또는 오류/사유 문자열).
  - `apply(store, work: Path) -> dict[str, str | int]` — 학교별 저장 건수 또는 오류.
  - 명령줄: `python -m eduapp_batch.run_schools prepare|apply [--work DIR]` (기본 `work`). 마지막 줄에 결과 JSON.
- **파일 약속:** `prepare`는 `work/<neis_code>/text_<n>.txt`(첨부별 글자, 첫 줄에 `# <게시물 제목> | <첨부 이름>`)와 `work/<neis_code>/meta.json`(`{"school_id": …, "source_url": "<게시물 URL>"}`)을 쓴다. Claude가 `work/<neis_code>/answer.json`을 쓴다:
  `{"items": [{"grade": 4, "subject": "과학", "publisher": "천재교육", "certain": true}]}` — 못 찾았으면 `{"items": []}`.

동작 규칙:
- `prepare`: ① `schools_with_children()` 각 학교의 학사일정을 `upsert_calendar`(학교별 try, 실패해도 다음 학교). ② `schools_to_collect()` 각 학교: 홈페이지 없음 → `not_found`(사유 `홈페이지 주소 없음`); `UnsupportedSite` → `not_found`(사유 `지원하지 않는 홈페이지`); 게시물 없음 → `not_found`(사유 `교과서 선정 공지 없음`); 게시물은 있으나 모든 첨부·본문 글자가 비어 있음 → `not_found`(사유 `첨부에서 글자를 읽지 못함`); 글자가 있으면 `work/`에 쓰고 상태는 그대로 둔다. 그 밖의 예외 → `failed` + `collect_runs`. 사유는 모두 `collect_runs`에도 남긴다.
- `apply`: `work/*/answer.json`이 있는 학교만 처리. `certain`이 true인 항목만 `apply_textbook`. 저장된 항목이 1개 이상이면 `done`, 0개면 `not_found`. 항목 하나가 DB 예외(잘못된 과목·학년)면 그 항목만 건너뛰고 사유를 `collect_runs`에 남긴다. 처리한 학교 폴더는 `work/_done/`으로 옮긴다.

- [ ] **Step 1: 실패하는 테스트 작성** (가짜 store: Task 5의 메서드를 흉내 내는 메모리 객체, 가짜 fetch는 Task 3 픽스처 사용)
  - `test_prepare_writes_text_and_meta`
  - `test_prepare_isolates_failures`: 학교 둘 중 하나의 fetch가 예외 → 그 학교는 `failed`, 다른 학교는 정상.
  - `test_prepare_unsupported_and_missing_homepage_mark_not_found`
  - `test_empty_text_marks_not_found`: 첨부가 이미지 PDF → `not_found`, 사유 `첨부에서 글자를 읽지 못함`.
  - `test_prepare_refreshes_calendar_for_schools_with_children`
  - `test_apply_saves_only_certain_items_and_marks_done`
  - `test_apply_empty_items_marks_not_found`
  - `test_apply_skips_invalid_item_and_keeps_others`
  - `test_apply_moves_processed_dirs`
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `cd batch && pytest tests/test_run_schools.py -v`. `main()`은 `run_programs.main`과 같이 `SUPABASE_URL` 유무로 RestStore/PgStore를 고르고, 첨부 다운로드용 `fetch_bytes`는 `run_programs._fetch`처럼 일시 오류만 재시도한다.
- [ ] **Step 3: Commit** — `git commit -m "feat(batch): run_schools prepare/apply"`

---

### Task 7: 예약 작업 지침 + 시범 학교 실행

**Files:**
- Modify: `batch/SCHEDULED_TASK.md`, `docs/08-plan.md`(3단계 상태)
- 사용: 원격 Supabase (Management API SQL 쿼리)

- [ ] **Step 1: 지침 갱신** — `SCHEDULED_TASK.md`에 학교 단계 추가: ① `python -m eduapp_batch.run_schools prepare` ② `work/<neis_code>/text_*.txt`를 읽고 과목(수학·사회·과학·영어)별·학년(3~6)별 출판사를 `answer.json`으로 쓴다. 글에 명시되어 있지 않거나 헷갈리면 그 항목은 `certain: false`로 쓰거나 빼고, 추측으로 채우지 않는다 ③ `python -m eduapp_batch.run_schools apply` ④ 결과 JSON에서 `failed`·`not_found` 학교와 사유를 요약. "하지 않는 것"에 `answer.json 외 파일 수정`을 추가.
- [ ] **Step 2: 마이그레이션 적용** — 원격에 `20261108000001_school_info.sql`을 Management API로 한 번 적용하고, 함수 4개가 있는지 `pg_proc`로 확인한다.
- [ ] **Step 3: 시범 학교 실행** — 시범 학교 5곳에 임시 자녀 없이 `collect_status = 'pending'`을 직접 설정하고(`update schools …`), `prepare` → (Claude가 `answer.json` 작성) → `apply`를 돌린다. Expected: 5곳 중 4곳 이상이 `done`. 못 찾은 곳은 사유를 `collect_runs`에서 확인해 기록한다.
- [ ] **Step 4: 문서 갱신 → Commit** — `docs/08-plan.md` 3단계 칸에 계획 링크를 걸고 결과(성공 학교 수)를 적는다. `git commit -m "docs: plan 3 scheduled task and pilot result"`

---

### Task 8: 앱 — 우리 학교 탭

**Files:**
- Modify: `app/lib/data/models.dart`, `app/lib/data/repository.dart`, `app/lib/data/supabase_repository.dart`, `app/lib/screens/home_shell.dart`, `app/test/fake_repository.dart`
- Create: `app/lib/screens/school_tab.dart`
- Test: `app/test/school_tab_test.dart`

**Interfaces:**
- Produces:
  - `class SchoolTextbook { String subject; String? publisher; bool confirmed; bool isGuess; String? sourceUrl; }` (`models.dart`)
  - `enum SchoolStatus { notRequested, pending, done, failed, notFound }` + `Child.school.status` (기존 `School`에 `final SchoolStatus status` 추가, `fromJson`은 `collect_status`)
  - `EduRepository.schoolTextbooks(int childId) -> Future<List<SchoolTextbook>>` (RPC `child_textbooks`)
  - `EduRepository.correctPublisher(int childId, String subject, String publisher) -> Future<void>` (RPC `correct_school_publisher`)
  - `FakeRepository`에 같은 메서드와 `textbooks` 맵 필드.
- 화면: 하단 탭 3개(`홈 · 체험 · 우리 학교`). 자녀가 둘 이상이면 위쪽에 자녀 칩 선택. 상단 상태 문구는 Global Constraints의 정확한 문구(대기 `pending`/`failed`/`notRequested`, 못 찾음 `notFound`; `done`이면 문구 없음). 과목 줄: 과목 · 출판사(없으면 `확인 중`), `isGuess` 또는 미확정이면 `확인 중` 칩. 줄을 누르면 하단 시트: 출판사 글자 입력(1~20자) + `저장` → `correctPublisher` → 목록 새로고침. 자녀가 3학년 미만이면 `3학년부터 출판사를 볼 수 있어요`. 자녀가 없으면 `자녀를 먼저 등록해요`.

- [ ] **Step 1: 실패하는 위젯 테스트 작성** (`FakeRepository` 사용, `home_shell_test`·`programs_tab_test` 패턴)
  - `shows four subjects with confirming chip for guesses`
  - `pending school shows waiting message` / `not found school shows ask-parent message`
  - `correct publisher saves and refreshes`: 줄 탭 → `비상교육` 입력 → 저장 → `calls`에 `correctPublisher` → 화면에 `비상교육`, `확인 중` 칩 없음.
  - `publisher input rejects empty and over 20 chars` (저장 버튼 비활성)
  - `correct failure shows snackbar and keeps old value`: 문구 `저장하지 못했어요. 다시 시도해 주세요`.
  - `grade under 3 shows notice`, `no child shows register prompt`
  - `load error shows retry`: 문구 `불러오지 못했어요` + `다시 시도`.
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `cd app && flutter test test/school_tab_test.dart` 후 `flutter test`(전체) / Expected: PASS
- [ ] **Step 3: Commit** — `git commit -m "feat(app): school tab with textbook publishers and parent correction"`

---

### Task 9: 앱 — 체험 목록 쉬는 날 필터 (S3)

**Files:**
- Modify: `app/lib/data/repository.dart`, `supabase_repository.dart`, `app/test/fake_repository.dart`, `app/lib/screens/programs_tab.dart`
- Test: `app/test/programs_tab_test.dart` (기존 파일에 추가)

**Interfaces:**
- Produces: `EduRepository.holidays(int schoolId, DateTime from, DateTime to) -> Future<Set<DateTime>>` — `school_calendar`에서 `is_holiday = true`인 날(날짜만, 시각 없음). `FakeRepository`에 `holidaySet` 필드.
- 화면: 기존 `관심만` 칩 옆에 `우리 학교 쉬는 날` 필터 칩. 자녀가 둘 이상이면 기존 학년 필터의 선택 자녀를 따른다(없으면 첫 자녀). 칩을 켜면 시작일(없으면 종료일)부터 종료일(없으면 시작일)까지 사이에 쉬는 날이 하루라도 있는 프로그램만 보인다. 날짜가 전혀 없는 프로그램은 제외. 자녀가 없으면 칩을 숨긴다.

- [ ] **Step 1: 실패하는 테스트 작성**
  - `holiday filter keeps only programs on holidays`
  - `multi day program overlapping holiday is kept`: 11/20~11/23 프로그램, 쉬는 날 11/21 → 보인다. 11/22~11/23만 있으면(쉬는 날 11/21) 안 보인다. 종료일 없는 프로그램은 시작일 하루로 판단.
  - `no holidays shows notice`: `holidaySet`이 비면 `쉬는 날 정보가 아직 없어요`(빈 목록 안내 대신).
  - `holiday load error does not break list`: `holidays` 실패 시 칩을 껐다 켠 상태로 돌아가고 `쉬는 날 정보를 불러오지 못했어요` 스낵바.
  - `chip hidden without child`
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `cd app && flutter test`
- [ ] **Step 3: Commit** — `git commit -m "feat(app): filter programs by school holidays"`

---

### Task 10: 마무리

- [ ] **Step 1: 전체 검증** — Run: `cd batch && pytest -q` 와 `cd app && flutter test && flutter analyze` / Expected: 모두 통과.
- [ ] **Step 2: 휴대폰 확인용 APK** — 계획 2 Task 9와 같은 방법으로 APK를 빌드해 사용자가 S3·S4(`docs/03-user-scenarios.md`)를 실기기에서 확인할 수 있게 한다. 사용자가 확인하기 전에는 3단계를 "완료"로 표시하지 않는다.
- [ ] **Step 3: Commit** — 남은 변경이 있으면 `git commit -m "chore: plan 3 wrap-up"`

---

## 남은 일 · 알려진 한계
- 서울 학교 홈페이지는 지원하지 않는다(학부모 직접 입력). 서울 시범이 필요하면 별도 수집기를 계획 3-2로 추가한다.
- 출판사 목록은 수집·학부모 입력으로 쌓이는 자유 입력 문자열이다(오타 중복 가능). 교육부 공공데이터 목록 적재는 계획 4(성취기준·교과서 목록)에서 한다.
- `textbook_ready` 알림 행 생성은 계획 5에서 한다(학교 상태가 `done`으로 바뀐 것을 기준으로).
- 학사일정은 덮어쓰기가 아닌 upsert라, 학교가 일정을 삭제한 경우 옛 행이 남는다.
- `sample.hwp` 확보 전에는 hwp 추출 테스트가 건너뛰어진다.
