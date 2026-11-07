# 계획 3: 학교·교과서 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 학부모가 "우리 학교" 탭에서 자녀 학교·학년의 교과서(출판사)를 "확인됨/확인 중"으로 보고 직접 고칠 수 있고, 체험 목록을 "우리 학교 쉬는 날"로 거를 수 있게 한다. 교과서는 학교 홈페이지 공지에서 야간 배치가 수집한다.

**Architecture:** DB 함수 3개(수집 결과 반영, 내 자녀 교과서 조회, 쉬는 날 필터가 붙은 `my_programs`)를 마이그레이션으로 추가한다. 배치는 (a) 교과서 목록 CSV 적재, (b) 나이스 학사일정 적재, (c) 공지 첨부(pdf/hwpx/hwp) 텍스트 추출, (d) 수집 대기 학교 목록 출력과 결과 저장 CLI를 만든다. 공지 게시물을 찾고 출판사를 읽어내는 일은 Claude 예약 작업이 지침 문서대로 하고, 파이썬은 검증·저장만 한다. 저장은 기존 `Store`(PgStore/RestStore) 계층을 확장한다. 앱은 `EduRepository`에 메서드를 더하고 "우리 학교" 탭과 체험 필터 칩을 추가한다.

**Tech Stack:** Python 3.12 + psycopg/httpx(기존) + `pypdf`, `olefile` / PostgreSQL 16 + pytest / Flutter(기존 app) / 나이스 Open API(`SchoolSchedule`).

**Spec:** `docs/superpowers/specs/2026-11-06-eduapp-design.md` (§3 실패 조건, §6 학교 선택→교과서 수집 흐름, §8 사용자가 정한 것) + `docs/02-prd.md` F4·F7, `docs/03-user-scenarios.md` S1(4~6)·S3·S4

### 전체 계획 순서 (이 문서는 3번)
1. DB 기반 + 체험 프로그램 수집 (완료)
2. Flutter 앱 기본 (완료)
3. **학교 교과서 수집, 학사일정(쉬는 날 필터), 우리 학교 화면, 학부모 수정** ← 이 문서
4. AI 생성: 성취기준·단원 연결, 가기 전에 읽어요, 오늘의 질문, 집 실험 + 운영자 승인
5. 알림: FCM, 신청 시작/마감, **교과서 준비 완료 푸시(S1-5)**

## Global Constraints

- 틀린 교과서를 확신하듯 보여주지 않는다: 배치는 **확신한 것만** `confirmed`로 저장하고, 애매하면 저장하지 않는다(= 앱에서 "확인 중"). 사람 검토 없음(스펙 §8).
- 학부모가 고친 값(`source='parent'`)은 배치가 절대 덮어쓰지 않는다. 학부모 수정은 기존 함수 `correct_school_textbook`을 그대로 쓴다.
- 지역 서울·경기, 초등 1~6학년. 학교는 자녀가 등록된 곳만 수집한다(전체 선수집 안 함).
- 수집 상태 값은 기존 enum `collect_status`: `not_requested`, `pending`, `done`, `failed`, `not_found`. 실패(`failed`)는 다음 배치에서 재시도, 성공한 학교는 마지막 수집 후 365일이 지나면 재확인.
- 배치는 클라우드에서 DB 직접 연결이 막혀 **Supabase REST(HTTPS)** 로 저장한다 → 새 저장 동작은 PgStore·RestStore 양쪽에 같은 이름으로 만들고, 로직은 DB 함수에 둬서 두 경로가 같게 동작하게 한다.
- 시각·날짜 표시는 기존 `format.dart`(KST 고정)를 쓴다. 문구는 해요체.
- 앱에서 쓰는 새 DB 함수는 `authenticated`에만 열고, 배치 전용 함수 `apply_school_collection`은 `service_role` 외에는 실행 불가(기본 `public` 실행 권한을 반드시 회수).
- 개발 컨테이너에서는 학교 홈페이지·나이스에 접속할 수 없으므로 수집 코드는 저장된 샘플(fixtures)로 테스트한다.
- 이 계획에서 하지 않는 것: 단원·성취기준·진도(계획 4), 알림(계획 5), 방학 기간 계산(재량휴업일 등 나이스가 `휴업일`로 표시한 날만), 학부모가 출판사를 "모름"으로 되돌리기, 학교 홈페이지 자동 크롤링(공지 찾기는 예약 작업이 함), 홈 탭 배너.
- **결정됨(2026-11-07):** ① 교과서 목록은 사용자가 공공데이터포털 원본(csv/xlsx)을 올리면 이 세션이 변환 스크립트(`batch/scripts/convert_textbooks.py`)까지 만든다(Task 3). ② 시범 학교 5곳은 사용자가 이름을 알려준다. ③ 나이스 학사일정은 사용자가 실제 응답 JSON 샘플을 보내주면 그것을 `neis_school_schedule.json` fixture로 쓴다(Task 4, Step 5 불필요). ④ `.hwp` 실파일 확인은 Task 10에서. ⑤ 실행은 subagent-driven.
- **사용자 준비 (Task 3 전에 확인받는다, 위 결정 반영):** 교육부 교과서 목록을 `subject,grade,semester,publisher,title` 헤더의 CSV로 만들어 주기(공공데이터포털 원본 → 열 이름 변환은 사용자 또는 이 세션이 함, 원본 형식을 아직 모름). `NEIS_API_KEY`는 계획 2에서 등록됨. 시범 학교 5곳 선정(Task 10).

## Review Focus

1. **출판사 이름 표기가 목록과 다름**(`천재교육` vs `(주)천재교육`, 공백) → 정규화 후에도 못 맞추면 저장하지 않고 "확인 중" 유지, 틀린 출판사로 대체하지 않는다. (Task 6 `unmatched publisher is skipped not guessed`)
2. **학부모가 고친 뒤 배치가 같은 학교를 다시 수집** → 학부모 값 유지. (Task 1 `auto collection never overwrites parent correction`)
3. **앱 사용자가 배치 전용 함수를 호출** → 거부. (Task 1 `apply_school_collection is not callable by authenticated`)
4. **학사일정이 아직 없는 학교에서 "쉬는 날" 필터** → 빈 화면이 아니라 "학교 학사일정을 아직 받지 못했어요". 쉬는 날은 있는데 프로그램이 없으면 다른 문구. (Task 9 `holiday filter explains missing calendar`)
5. **한 과목에 출판사가 하나뿐**(국정 등) → "확인 중"이 아니라 `confirmed`. 출판사 후보가 여럿이고 수집 전이면 최다 사용 출판사를 `unverified`로, 정보가 전혀 없으면 `unknown`. (Task 1 `single publisher subject is confirmed`, `tentative uses most used publisher`)

---

### Task 1: DB — 수집 결과 반영, 내 자녀 교과서, 쉬는 날 필터

**Files:**
- Create: `supabase/migrations/20261107000002_school_textbooks.sql`
- Modify: `supabase/schema.sql` (끝에 위 마이그레이션 내용을 그대로 덧붙임)
- Test: `batch/tests/test_school_textbooks_db.py` (헬퍼는 `test_app_basics.py`의 `add_user`, `as_user` 재사용: `from test_app_basics import ...` 가능한 방식으로 import, 안 되면 `conftest.py`로 옮김)

**Interfaces:**
- Produces:
  - `apply_school_collection(p_school_id bigint, p_status collect_status, p_source_url text, p_items jsonb) returns int` — `p_items`는 `[{"grade":4,"subject":"과학","textbook_id":12}, ...]`. 효과: 항목마다 `school_textbooks`를 `confidence='confirmed', source='auto', source_url=p_source_url`로 upsert하되 **기존 행의 `source='parent'`이면 건드리지 않음**; 그 학교의 `collect_status=p_status`, `last_collected_at=now()`. 반환값은 실제 쓴 행 수. `p_status`가 `done`·`not_found`·`failed` 외이면 예외. 항목의 textbook이 같은 grade·subject가 아니면 예외(전체 롤백). `language plpgsql security definer set search_path = public`. `revoke execute ... from public, anon, authenticated; grant execute ... to service_role`.
  - `my_school_textbooks(p_child_id bigint) returns table (subject text, textbook_id bigint, publisher text, title text, status text, source text)` — `status`는 `'confirmed'|'unverified'|'unknown'`. 내 자녀가 아니면 빈 결과. 과목 목록 = 그 학년 `textbooks`에 존재하는 과목 전부(과목명 오름차순). 과목마다:
    1. 그 학교·학년 `school_textbooks`에 `textbook_id`가 있으면 그 행의 출판사·`confidence`·`source`.
    2. 없고 그 과목·학년의 출판사가 **하나뿐**이면 그 출판사, `confirmed`, source `'auto'`.
    3. 없고 같은 학년·과목에서 다른 학교들의 `school_textbooks` 중 `confirmed`인 것이 있으면 가장 많이 쓰인 출판사(동수면 출판사 이름 오름차순), `unverified`, source `'auto'`.
    4. 그 외 `publisher null`, `unknown`.
    - 한 출판사에 학기 행이 여럿이면 `textbook_id`·`title`은 **학기 번호가 가장 작은 행**(null 학기가 있으면 그 행). `security invoker`, `language sql stable`, `grant execute ... to authenticated`.
  - `my_programs(p_grade int default null, p_from date default null, p_to date default null, p_off_school bigint default null) returns setof upcoming_programs` — 기존 함수를 `drop function my_programs(int, date, date)` 후 4인자로 재생성(기존 조건·정렬 그대로). 추가 조건: `p_off_school is null or exists (select 1 from school_calendar c where c.school_id = p_off_school and c.is_holiday and c.day between coalesce(p.starts_on, p.ends_on) and coalesce(p.ends_on, p.starts_on))` (날짜 없는 프로그램은 필터가 켜지면 제외). `grant execute ... (int, date, date, bigint) to authenticated`.

- [ ] **Step 1: 실패하는 테스트 작성** — 테스트 이름과 단언:
  - `test_apply_marks_confirmed_auto_rows_and_status`: 교과서 2행(과학 4학년 천재/비상), 학교 `pending` → 항목 1개 적용 → 반환 1, `school_textbooks` 행이 `confirmed/auto/source_url`, 학교 `collect_status='done'`, `last_collected_at` not null.
  - `test_auto_collection_never_overwrites_parent_correction`: `correct_school_textbook`로 비상 지정(학부모) → 배치가 천재로 적용 → 반환 0, 행은 여전히 비상·`parent`.
  - `test_apply_rejects_status_and_mismatch`: `pending` 상태값 예외, 학년 다른 textbook 예외이고 학교 상태 안 바뀜.
  - `test_apply_is_not_callable_by_authenticated`: `set role authenticated` 후 호출 시 `psycopg.errors.InsufficientPrivilege`.
  - `test_single_publisher_subject_is_confirmed`, `test_tentative_uses_most_used_publisher`(다른 두 학교가 천재 확인 → 우리 학교 `unverified` 천재), `test_unknown_when_no_data`, `test_school_row_wins_over_tentative`, `test_not_my_child_returns_nothing`, `test_picks_lowest_semester_row`.
  - `test_my_programs_off_school_filters_by_holiday`: 쉬는 날 `current_date+3`인 학교, 프로그램 A(+2~+4)·B(+10~+12)·C(날짜 없음) → 필터 켜면 A만, 끄면 셋 다. `test_my_programs_old_three_arg_call_still_works`.
- [ ] **Step 2: 실패 확인** — `cd batch && pytest tests/test_school_textbooks_db.py -v` → 함수 없음으로 FAIL.
- [ ] **Step 3: 마이그레이션 작성** — 위 Interfaces 그대로 SQL로. `my_school_textbooks`의 후보 순위는 `window`/`distinct on`으로 구현(방식은 구현자 선택).
- [ ] **Step 4: 통과 확인** — 위 명령 → 전부 PASS. 이어서 `pytest -q` 전체 통과(기존 `test_app_basics`의 `my_programs` 호출이 깨지지 않아야 함). DB 테스트는 `TEST_PG_ADMIN_URL` 필요.
- [ ] **Step 5: Commit** — `git add supabase batch/tests && git commit -m "feat(db): school textbook collection, per-child textbooks, holiday filter"`

---

### Task 2: 저장 계층 — 교과서 목록, 학사일정, 수집 대기

**Files:**
- Modify: `batch/eduapp_batch/models.py` (아래 dataclass 추가), `batch/eduapp_batch/store.py` (PgStore·RestStore에 메서드 추가)
- Test: `batch/tests/test_store.py`(PgStore, 기존 `db` 픽스처), `batch/tests/test_store_rest.py`(RestStore, 기존 `store_with` 패턴)

**Interfaces:**
- Produces (models):
  - `Textbook(subject: str, grade: int, semester: int, publisher: str, title: str)` frozen
  - `CalendarDay(day: date, event_name: str, is_holiday: bool)` frozen
  - `PendingSchool(id: int, neis_code: str, edu_office_code: str, name: str, homepage_url: str | None)` frozen
- Produces (두 Store 공통 메서드):
  - `upsert_textbooks(textbooks: list[Textbook]) -> int` — `(curriculum='2022', subject, grade, semester, publisher)` 충돌 시 `title`만 갱신. REST는 `on_conflict=curriculum,subject,grade,semester,publisher`. `Textbook.semester`는 항상 1 또는 2여야 한다(null이면 unique가 중복을 막지 못해 재적재가 멱등이 아니게 되므로 `ValueError`).
  - `textbook_candidates(grade: int, subject: str) -> list[dict]` — `{id, publisher, semester}` 목록.
  - `schools_to_collect(limit: int, today: date) -> list[PendingSchool]` — `collect_status in ('pending','failed')` 또는 (`done`/`not_found`이고 `last_collected_at < today - 365일`) 이면서 **`children`에 등록된 학교**. 정렬: `pending` 먼저, 그다음 `collect_requested_at`.
  - `schools_with_children() -> list[PendingSchool]` — 학사일정 갱신 대상.
  - `upsert_school_calendar(school_id: int, days: list[CalendarDay]) -> int` — `(school_id, day, event_name)` 충돌 시 `is_holiday` 갱신.
  - `apply_school_collection(school_id: int, status: str, source_url: str | None, items: list[dict]) -> int` — Task 1의 SQL 함수 호출(Pg는 `select apply_school_collection(...)`, REST는 `POST /rest/v1/rpc/apply_school_collection`, 본문 키는 `p_` 접두 인자명).

- [ ] **Step 1: 실패하는 테스트** — Pg: `test_upsert_textbooks_is_idempotent_and_updates_title`, `test_schools_to_collect_only_registered_schools_in_priority_order`(pending·failed·오래된 done·최근 done·자녀 없는 pending 학교 → 앞의 셋만, pending 먼저), `test_upsert_school_calendar_updates_holiday_flag`, `test_apply_school_collection_roundtrip`. REST(MockTransport): 각 메서드가 올바른 경로·`on_conflict`/rpc 본문을 보내는지, `schools_to_collect`가 PostgREST 필터로 같은 결과를 내도록 한 번의 요청으로 가져오는지(학교 대기 조건은 `or=` 필터, 자녀 등록 여부는 `children!inner(id)` 임베드 사용, 한도는 `limit`).
- [ ] **Step 2: 실패 확인** — `pytest tests/test_store.py tests/test_store_rest.py -v` → FAIL(메서드 없음).
- [ ] **Step 3: 구현** — 위 시그니처대로. 기존 `upsert_schools`·`upsert_programs` 스타일(psycopg `executemany`, REST `_post`)을 따른다. RPC·GET 도우미가 없으면 `RestStore`에 `_get`/`_rpc` 한두 줄 추가.
- [ ] **Step 4: 통과 확인** — `pytest -q` 전체 통과.
- [ ] **Step 5: Commit** — `feat(batch): store methods for textbooks, calendar, collect queue`

---

### Task 3: 교과서 목록 적재

**Files:**
- Create: `batch/eduapp_batch/textbooks_load.py`
- Create: `batch/scripts/convert_textbooks.py` (사용자가 올린 공공데이터포털 원본 → 아래 헤더 CSV. 원본 열 이름은 파일을 받은 뒤 정하고, 원본 일부(10행 내외)를 `batch/tests/fixtures/textbooks_raw_sample.*`로 두어 변환 테스트에 쓴다. 학기를 못 구하는 행은 버리지 말고 변환 결과 요약에 건수를 출력)
- Create: `batch/tests/fixtures/textbooks_sample.csv`
- Test: `batch/tests/test_textbooks_load.py`

**Interfaces:**
- Consumes: `Store.upsert_textbooks`, `Textbook`
- Produces: `parse_textbooks_csv(text: str) -> list[Textbook]` (헤더 `subject,grade,semester,publisher,title`, 학년·학기는 정수, 공백 제거, 학년이 1~6 밖이거나 학기가 1·2 밖이거나 필수값이 비면 `ValueError`에 행 번호 포함), `main() -> int` (`python -m eduapp_batch.textbooks_load path.csv`, 환경변수로 Pg/Rest 선택은 `schools_list.main` 방식, 마지막 줄에 `{"textbooks": N}` JSON 출력)

- [ ] **Step 1: 실패하는 테스트** — `test_parse_basic_rows`(fixture 3행: 과학 4학년 1학기 천재교육, 과학 4학년 1학기 비상교육, 국어 3학년 2학기 → 3개), `test_parse_rejects_bad_grade_with_row_number`(7학년 → `ValueError`, 메시지에 `3`행), `test_parse_rejects_missing_semester`(학기 빈칸 → `ValueError`), `test_parse_dedupes_same_key`.
- [ ] **Step 2: 실패 확인** — `pytest tests/test_textbooks_load.py -v`
- [ ] **Step 3: 구현** — `csv.DictReader`, 중복은 `(subject,grade,semester,publisher)` 기준으로 마지막 값 유지.
- [ ] **Step 4: 통과 확인** — 위 명령 PASS
- [ ] **Step 5: Commit** — `feat(batch): load textbook catalog from CSV`

---

### Task 4: 나이스 학사일정 수집

**Files:**
- Create: `batch/eduapp_batch/neis_calendar.py`
- Create: `batch/tests/fixtures/neis_school_schedule.json`
- Test: `batch/tests/test_neis_calendar.py`

**Interfaces:**
- Consumes: `Store.schools_with_children`, `Store.upsert_school_calendar`, `CalendarDay`, `PendingSchool`
- Produces:
  - `parse_schedule(payload: dict) -> list[CalendarDay]` — 나이스 `SchoolSchedule` 응답. 결과 없음(`{"RESULT":{"CODE":"INFO-200"}}`)이면 `[]`. 행 필드 `AA_YMD`(YYYYMMDD), `EVENT_NM`, `SBTR_DD_SC_NM`; **`SBTR_DD_SC_NM == "휴업일"` 이면 `is_holiday=True`**, 그 외 False.
  - `fetch_schedule(school: PendingSchool, key: str, start: date, end: date) -> list[CalendarDay]` — `https://open.neis.go.kr/hub/SchoolSchedule`, 파라미터 `ATPT_OFCDC_SC_CODE`, `SD_SCHUL_CODE`, `AA_FROM_YMD`, `AA_TO_YMD`, `pIndex`/`pSize=1000` 페이지 순회(`schools_list.fetch_office` 방식, 인증 오류는 `RuntimeError`).
  - `main() -> int` — `python -m eduapp_batch.neis_calendar`: 오늘(KST)부터 +180일, 학교별로 try/except 후 `collect_runs`에 `target=f"calendar:{school.id}"`로 성공·실패 기록, 마지막 줄에 학교별 건수/오류 JSON. 학교가 하나도 성공하지 못하면 종료코드 1.

- [ ] **Step 1: 실패하는 테스트** — fixture는 나이스 응답 형식(`{"SchoolSchedule":[{"head":[...]},{"row":[...]}]}`)으로 3행: 재량휴업일(`휴업일`), 개교기념일 등 일반 행(`해당없음`), 공휴일 한 행(`공휴일`). `test_parse_flags_only_closure_days`(휴업일만 `is_holiday`), `test_parse_no_result_returns_empty`, `test_fetch_paginates_and_raises_on_auth_error`(httpx 모킹: 1000행+1행 두 페이지 / `INFO-300` 인증 오류).
- [ ] **Step 2: 실패 확인** — `pytest tests/test_neis_calendar.py -v`
- [ ] **Step 3: 구현** — 시그니처대로. 요청 필드명은 위 값으로 쓰되, 실제 응답과 다르면 fixture와 함께 고친다(Step 5에서 확인).
- [ ] **Step 4: 통과 확인** — PASS
- [ ] **Step 5: (결정됨) fixture는 사용자가 보낸 실제 응답** — 구현 전에 샘플을 받아 필드명·`SBTR_DD_SC_NM` 값을 확인하고, 위 Interfaces와 다르면 이 Task의 시그니처 설명과 파서를 샘플에 맞춘다. 샘플이 오기 전에는 Task 4를 시작하지 않는다.
- [ ] **Step 6: Commit** — `feat(batch): NEIS school calendar collector`

---

### Task 5: 공지 첨부 텍스트 추출

**Files:**
- Create: `batch/eduapp_batch/attachment_text.py`
- Modify: `batch/pyproject.toml` (dependencies에 `pypdf>=4`, `olefile>=0.47`)
- Test: `batch/tests/test_attachment_text.py`

**Interfaces:**
- Produces:
  - `extract_text(data: bytes, filename: str) -> str` — 확장자(`.pdf`, `.hwpx`, `.hwp`, `.txt`, 대소문자 무시)로 분기, 그 외는 `ValueError("unsupported: <ext>")`. 결과의 연속 공백·빈 줄은 정리.
  - `pdf_text(data: bytes) -> str` (pypdf), `hwpx_text(data: bytes) -> str` (zip 안 `Contents/section*.xml`의 `<hp:t>` 텍스트를 문단 단위로 이음), `hwp_text(data: bytes) -> str` (`olefile`로 `BodyText/Section*` 스트림을 열어, 압축 플래그가 켜져 있으면 `zlib.decompress(..., -15)` 후 `hwp_section_text`로 이음; 암호화된 파일이면 `ValueError("encrypted hwp")`), `hwp_section_text(section: bytes) -> str`: 레코드는 4바이트 헤더(하위 10비트 태그, 10비트 레벨, 상위 12비트 크기, 크기가 0xFFF면 뒤 4바이트가 실제 크기); **태그 67(`HWPTAG_PARA_TEXT`)의 페이로드만** UTF-16LE로 읽고, 0x20 미만 제어 문자 중 줄바꿈(10, 13)만 `\n`으로 남기며, 확장 제어 문자(1~8, 11, 12, 14~23)는 뒤따르는 14바이트까지 건너뛴다.
  - CLI: `python -m eduapp_batch.attachment_text <URL 또는 파일경로>` → 텍스트를 표준출력으로. URL이면 `httpx`(리다이렉트 허용, 20MB 초과·타임아웃은 오류), 파일명은 `Content-Disposition`이 있으면 거기서, 없으면 URL 경로에서.

- [ ] **Step 1: 실패하는 테스트** — 테스트 코드에서 만든 입력으로: `test_hwpx_text_joins_paragraphs`(zip을 메모리에서 만들어 `<hp:t>` 두 문단), `test_hwp_section_text_reads_para_text_records`(레코드 바이트를 손으로 조립: 태그 67 레코드 2개 + 다른 태그 1개 → 앞 둘의 텍스트만, 확장 제어 문자 건너뛰기 포함), `test_pdf_text`(pypdf `PdfWriter`로 만든 빈 페이지가 아닌 텍스트 PDF는 만들기 번거로우므로 **`pypdf` 호출을 monkeypatch한 단위 테스트** + 아래 실파일 확인), `test_extract_text_rejects_unknown_extension`, `test_extract_text_collapses_whitespace`.
- [ ] **Step 2: 실패 확인** — `pytest tests/test_attachment_text.py -v`
- [ ] **Step 3: 구현** — 위 시그니처대로.
- [ ] **Step 4: 통과 확인** — PASS
- [ ] **Step 5: 실파일 확인(Task 10에서 같이 해도 됨)** — 실제 학교 공지의 `.hwp`·`.pdf` 한 개씩으로 CLI를 돌려 교과서 표 내용이 글자로 나오는지 확인. `.hwp`가 깨지면 `hwp_text`만 `pyhwp` 등으로 바꾼다(함수 시그니처는 유지).
- [ ] **Step 6: Commit** — `feat(batch): extract text from school notice attachments`

---

### Task 6: 수집 대기 목록·결과 저장 CLI와 예약 작업 지침

**Files:**
- Create: `batch/eduapp_batch/school_collect.py`
- Create: `batch/SCHOOL_COLLECT_TASK.md`
- Modify: `batch/SCHEDULED_TASK.md` (순서에 학사일정·교과서 수집 단계 추가)
- Test: `batch/tests/test_school_collect.py`

**Interfaces:**
- Consumes: `Store.schools_to_collect`, `Store.textbook_candidates`, `Store.apply_school_collection`
- Produces:
  - `normalize_publisher(name: str) -> str` — 공백·`(주)`·`㈜`·`주식회사` 제거, 소문자화.
  - `build_items(store, items: list[dict]) -> tuple[list[dict], list[dict]]` — 입력 항목 `{"grade":int,"subject":str,"publisher":str,"certain":bool}`. `certain`이 False이거나 `textbook_candidates(grade, subject)`에서 정규화한 출판사가 **정확히 하나** 일치하지 않으면 건너뛴다. 일치하면 후보 중 학기 번호가 가장 작은 행(null 학기 우선)의 id로 `{"grade","subject","textbook_id"}`. 반환 `(저장할 항목, 건너뛴 항목 + "reason")`.
  - `save_result(store, result: dict) -> dict` — 입력 `{"school_id":int,"status":"done"|"not_found"|"failed","source_url":str|None,"items":[...]}`. `status`가 `done`인데 저장 가능한 항목이 0개면 `not_found`로 바꿔 저장한다(확신 못 하면 "찾지 못함"). 반환 `{"school_id", "status", "saved": n, "skipped": [...]}`.
  - CLI: `python -m eduapp_batch.school_collect next [--limit 10]` → `schools_to_collect` 결과를 JSON 배열로 출력(`id, name, homepage_url, neis_code`); `python -m eduapp_batch.school_collect save result.json` → `save_result` 결과 JSON 출력. 저장소 선택은 `run_programs.main` 방식.
  - `SCHOOL_COLLECT_TASK.md`: 예약 작업 지침 — ① `next` 실행 ② 학교마다 홈페이지 공지에서 "교과용도서 선정" 계열 게시물을 찾고(게시판 이름·검색어 예시 포함), 첨부는 `attachment_text`로 읽기 ③ 학년·과목별 출판사를 읽어 `result.json` 작성(**표에 명시된 것만 `certain:true`, 추측·다른 학교 정보·이전 연도 표는 `certain:false`**; 3~6학년 검정 과목 중 읽은 것만 포함) ④ 못 찾으면 `status:"not_found"`, 접속·파싱 오류는 `status:"failed"` ⑤ `save` 실행 ⑥ 학교별 한 줄 요약(성공/찾지 못함/실패와 원인). 하지 않는 것: 코드 수정, 커밋, `certain`을 사람 눈으로 추측해 올리기. 알림 푸시는 계획 5.

- [ ] **Step 1: 실패하는 테스트** — fake store(메서드 두 개를 가진 간단한 클래스) 사용: `test_normalize_publisher_variants`(`(주)천재교육`·`천재 교육`·`㈜천재교육` 모두 같은 값), `test_certain_exact_match_saves_lowest_semester_row`, `test_uncertain_item_is_skipped`, `test_unmatched_publisher_is_skipped_not_guessed`(후보에 없는 출판사 → 저장 0, skipped에 reason), `test_ambiguous_normalized_match_is_skipped`(정규화 후 두 후보가 같음), `test_done_with_zero_saved_becomes_not_found`, `test_failed_and_not_found_pass_through_without_items`.
- [ ] **Step 2: 실패 확인** — `pytest tests/test_school_collect.py -v`
- [ ] **Step 3: 구현** — 시그니처대로. 순수 함수 위주로 두고 CLI는 얇게.
- [ ] **Step 4: 통과 확인** — `pytest -q` 전체 통과. 지침 문서가 위 ①~⑥과 "하지 않는 것"을 모두 담았는지 눈으로 확인.
- [ ] **Step 5: Commit** — `feat(batch): school textbook collection CLI and scheduled-task instructions`

---

### Task 7: 앱 데이터 계층

**Files:**
- Modify: `app/lib/data/models.dart`, `app/lib/data/repository.dart`, `app/lib/data/supabase_repository.dart`, `app/test/fake_repository.dart`
- Test: `app/test/models_test.dart`

**Interfaces:**
- Produces (models):
  - `enum TextbookStatus { confirmed, unverified, unknown }` + `TextbookStatus.parse(String)`
  - `SchoolTextbook({required String subject, int? textbookId, String? publisher, String? title, required TextbookStatus status, required String source})` + `fromJson`(`my_school_textbooks` 행: `subject, textbook_id, publisher, title, status, source`)
  - `TextbookOption({required int id, required String publisher, String? title})`
  - `enum SchoolCollectStatus { notRequested, pending, done, failed, notFound }` + `parse`(DB 값 `not_requested`, `pending`, `done`, `failed`, `not_found`)
- Produces (EduRepository 추가 메서드):
  - `Future<SchoolCollectStatus> schoolCollectStatus(int schoolId)` — `schools.collect_status` 조회
  - `Future<List<SchoolTextbook>> schoolTextbooks(int childId)` — rpc `my_school_textbooks`
  - `Future<List<TextbookOption>> textbookOptions(int grade, String subject)` — `textbooks`를 읽어 **출판사별로 학기 번호가 가장 작은 행 하나**만, 출판사 이름 순
  - `Future<void> correctTextbook(int childId, String subject, int textbookId)` — rpc `correct_school_textbook`
  - `Future<List<DateTime>> schoolHolidays(int schoolId)` — `school_calendar`에서 `is_holiday` 이고 `day >= 오늘(KST)`, 날짜 오름차순, 날짜 중복 제거
  - `programs({..., int? offSchoolId})` — 기존 `programs`에 `p_off_school` 전달
- 가짜 repository: 위 메서드 전부, 호출 기록(`calls`)과 `failWith` 규칙을 기존 메서드와 동일하게 따른다. 필드 `schoolStatus: Map<int, SchoolCollectStatus>`, `textbooks: Map<int, List<SchoolTextbook>>`(자녀 id별), `options: List<TextbookOption>`, `holidays: Map<int, List<DateTime>>`.

- [ ] **Step 1: 실패하는 테스트** — `models_test.dart`에: `SchoolTextbook.fromJson` 3가지 상태 파싱, `SchoolCollectStatus.parse('not_found') == notFound`, 알 수 없는 값은 `ArgumentError`.
- [ ] **Step 2: 실패 확인** — `cd app && flutter test test/models_test.dart`
- [ ] **Step 3: 구현** — 위대로. `textbookOptions`의 출판사 중복 제거와 `schoolHolidays`의 날짜 변환(`DateTime.parse(day)`, 시각 없는 날짜)은 repository 안에서 처리.
- [ ] **Step 4: 통과 확인** — `flutter test && flutter analyze` 통과(기존 47개 포함).
- [ ] **Step 5: Commit** — `feat(app): repository methods for school textbooks and holidays`

---

### Task 8: "우리 학교" 탭

**Files:**
- Create: `app/lib/screens/school_tab.dart`
- Modify: `app/lib/screens/home_shell.dart` (탭 3개: 홈 · 체험 · 우리 학교, 앱바 제목, 아이콘 `Icons.school_outlined`/`Icons.school`)
- Test: `app/test/school_tab_test.dart`, `app/test/app_flow_test.dart`(탭 3개 확인으로 수정)

**Interfaces:**
- Consumes: Task 7 repository 메서드, 기존 `programs_tab.dart`의 자녀 선택 칩 패턴, `format.dart`(날짜 표시), 스타일 가이드 색
- Produces: `SchoolTab({required EduRepository repo})`. 구성:
  - 자녀 선택 칩(자녀 없으면 "자녀를 먼저 등록해 주세요" + 홈으로 안내 문구), 선택 자녀의 `학교 이름 · N학년`.
  - 수집 상태 안내 문구: `pending`·`notRequested`·`failed` → "교과서 정보를 확인하고 있어요 (내일 아침까지)", `notFound` → "학교 공지에서 찾지 못했어요. 알고 계시면 알려주세요", `done` → 문구 없음.
  - 과목 목록: 과목명, 출판사(없으면 "출판사 확인 중"), 배지 `확인됨`/`확인 중`(`unverified`·`unknown`). 항목 탭 → 바텀시트에 `textbookOptions`(현재 출판사 표시) → 선택하면 `correctTextbook` 후 목록 새로고침.
  - "다가오는 쉬는 날" 최대 5개(`11/21(금)` 형식, 없으면 "학사일정 정보가 아직 없어요").
  - 오류: 불러오기 실패 → "정보를 불러오지 못했어요" + "다시 시도"; 수정 저장 실패 → 스낵바 "출판사를 저장하지 못했어요"이고 화면 값은 그대로.

- [ ] **Step 1: 실패하는 테스트** (`school_tab_test.dart`, 가짜 repository) — `shows confirmed and checking badges`(한 과목 confirmed 천재교육, 한 과목 unknown → "출판사 확인 중"+`확인 중`), `pending school shows checking banner`, `not found school shows ask-parent banner`, `correct publisher through sheet calls correctTextbook and refreshes`(시트에서 비상교육 선택 → `calls`에 `correctTextbook`, 새로고침 후 `확인됨 · 비상교육`), `correction failure shows snackbar and keeps value`, `load error shows retry`, `shows upcoming holidays or empty note`, `no overflow at textScale 2.0`, `no children shows guidance`.
- [ ] **Step 2: 실패 확인** — `flutter test test/school_tab_test.dart`
- [ ] **Step 3: 구현** — 위 구성. 상태 관리는 `ProgramsTab`처럼 `StatefulWidget` + `FutureBuilder` 없이 `_load()` 패턴(기존 코드 스타일 유지).
- [ ] **Step 4: 통과 확인** — `flutter test && flutter analyze` 전체 통과.
- [ ] **Step 5: Commit** — `feat(app): school tab with textbook status and parent correction`

---

### Task 9: 체험 목록 "우리 학교 쉬는 날" 필터

**Files:**
- Modify: `app/lib/screens/programs_tab.dart`
- Test: `app/test/programs_tab_test.dart`

**Interfaces:**
- Consumes: `repo.programs(offSchoolId:)`, `repo.schoolHolidays(schoolId)`
- Produces: 필터 칩 `우리 학교 쉬는 날`(`FilterChip`, 자녀가 선택된 경우에만 표시, "모든 학년"이면 숨김). 켜면 `programs(..., offSchoolId: child.school.id)`. 빈 결과 문구: `schoolHolidays`가 비어 있으면 "학교 학사일정을 아직 받지 못했어요", 아니면 "쉬는 날에 열리는 프로그램이 없어요" + "필터 끄기" 버튼. 자녀를 바꾸거나 "모든 학년"으로 바꾸면 필터는 꺼진다.

- [ ] **Step 1: 실패하는 테스트** — `holiday chip hidden without a selected child`, `holiday filter passes school id to repository`, `holiday filter explains missing calendar`, `holiday filter empty with calendar shows other message and can be turned off`, `changing child resets holiday filter`.
- [ ] **Step 2: 실패 확인** — `flutter test test/programs_tab_test.dart`
- [ ] **Step 3: 구현** — 기존 `_favOnly` 칩 옆에 같은 방식으로 상태 하나 추가.
- [ ] **Step 4: 통과 확인** — `flutter test && flutter analyze` 전체 통과.
- [ ] **Step 5: Commit** — `feat(app): school holiday filter on program list`

---

### Task 10: 통합 확인과 문서

**Files:**
- Modify: `docs/08-plan.md` (3단계 행 상세 계획 링크, 사용자 할 일 표에 "3단계 전: 교과서 목록 CSV, 시범 학교 5곳"), `app/README.md`(구조에 우리 학교 탭), `batch/SCHEDULED_TASK.md`(Task 6에서 수정한 것 최종 확인)

- [ ] **Step 1: 전체 자동 검사** — `cd batch && TEST_PG_ADMIN_URL=postgresql://postgres:test@localhost:5432/postgres pytest -q` 전부 통과, `cd app && flutter analyze && flutter test` 전부 통과.
- [ ] **Step 2: 운영 DB 적용(사용자 확인 후)** — 새 마이그레이션 `20261107000002_school_textbooks.sql`을 Supabase에 적용. 적용 전 사용자에게 알린다.
- [ ] **Step 3: 목록 적재(사용자 환경)** — 교과서 CSV로 `python -m eduapp_batch.textbooks_load <csv>` 실행, `textbooks` 행 수 확인.
- [ ] **Step 4: 시범 학교 5곳 실수집(사용자 환경, 네트워크 Full)** — 학교 5곳에 자녀를 등록해 대기로 만들고 `neis_calendar`와 `SCHOOL_COLLECT_TASK.md` 절차를 한 번 실행. Task 4·5의 실제 응답·실파일 확인 단계를 여기서 끝낸다. **완료 기준: 5곳 중 4곳에서 교과서 `confirmed`가 하나 이상 저장**되고, 저장된 값이 학교 공지 원문과 일치(사람이 5곳 모두 대조), 틀린 값이 하나라도 있으면 지침(`certain` 기준)을 고쳐 다시 실행.
- [ ] **Step 5: 실기기 확인** — APK를 사용자 휴대폰에 설치(`app/README.md` 절차)해 S3(쉬는 날 필터)·S4(교과서 고치기)를 따라 해보고, S1 4~5의 안내 문구(확인 중 → 수집 후 확인됨)를 확인. 푸시는 계획 5.
- [ ] **Step 6: Commit** — `docs: plan 3 roadmap and readme updates`
