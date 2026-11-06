# 계획 1: DB 기반 + 체험 프로그램 수집 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 서울·경기 기관의 체험 프로그램을 매일 수집해 Supabase DB에 쌓고, 앱이 "진행 중/예정" 프로그램을 읽을 수 있게 한다.

**Architecture:** DB 테이블과 RLS는 `supabase/migrations/`의 SQL로 정의한다. 수집은 `batch/`의 Python 스크립트가 기관별 파서로 HTML을 읽어 `programs`에 upsert한다. Claude 예약 작업이 매일 이 스크립트를 실행한다.

**Tech Stack:** PostgreSQL 16(로컬 테스트) / Supabase(운영), Python 3.13, psycopg 3, httpx, beautifulsoup4, pytest.

**Spec:** `docs/superpowers/specs/2026-11-06-eduapp-design.md`

### 전체 계획 순서 (이 문서는 1번)
1. **DB 기반 + 체험 프로그램 수집** ← 이 문서
2. Flutter 앱: 로그인, 자녀 등록, 지역 선택, 프로그램 목록
3. 학교 선택 → 교과서 수집 (수집 대기 목록, 공지 첨부 hwp/pdf 추출)
4. AI 생성: 성취기준 연결, 체험 전 책, 오늘의 질문, 집 실험 + 운영자 승인
5. 알림: 신청 시작/마감, 교과서 준비 완료 (pg_cron + Edge Function + FCM)

## Global Constraints

- 지역은 `서울`, `경기`만 (스펙 §4).
- 초기 대상 기관 10~20곳. 이 계획은 수집기 구조와 첫 기관 2곳까지 (나머지 기관은 같은 패턴으로 추가).
- 앱(anon/authenticated)은 프로그램을 **읽기만**. 쓰기는 배치(서비스 키/DB 직접 연결)만.
- 신청 시작 시각을 공개하지 않는 기관은 `apply_starts_at`을 NULL로 두고 신청 기간(`apply_ends_at`)만 저장 (스펙 §6 체험 프로그램).
- 마감된 프로그램은 앱에 보이면 안 된다 (스펙 §3 실패 조건).
- 학년은 초등 1~6 정수. "전 학년"은 1~6.
- **실행 환경 전제:** 실제 기관 페이지를 가져오는 단계(Task 4·5의 Step 1)는 네트워크 접근이 Full인 환경에서 한다. 그 외 테스트는 저장된 HTML 샘플과 로컬 Postgres로 오프라인 실행.

## Review Focus

1. **같은 프로그램을 매일 다시 수집** → 중복 행이 생기지 않고 내용만 갱신돼야 한다. (Task 3 `test_upsert_is_idempotent`)
2. **한 기관 페이지가 바뀌어 파싱 실패** → 그 기관만 실패 기록, 나머지 기관 수집은 계속. (Task 6 `test_one_collector_failure_does_not_stop_others`)
3. **한국식 날짜 표기** (`2026. 11. 6.(목)`, `2026-11-06 10:00`, `11.6~11.20`) → 올바른 날짜, 연도 없는 표기는 수집일 기준 연도. (Task 2)
4. **학년 표기 다양함** (`초등 3~4학년`, `초3-6`, `전학년`, `유아`, `중학생 이상`) → 1~6 범위로, 초등 해당 없으면 제외. (Task 2)
5. **종료일 지난 프로그램** → `upcoming_programs` 뷰에서 빠진다. (Task 1 `test_upcoming_view_hides_ended`)

---

### Task 1: DB 스키마와 접근 규칙

**Files:**
- Use: `supabase/schema.sql` (전체 스키마, 이미 작성·검증됨 — `supabase/tests/schema_check.sql`)
- Create: `supabase/migrations/20261106000001_init.sql` (= `schema.sql` 복사, 운영 DB 적용용)
- Use: `supabase/tests/supabase_stub.sql` (로컬 전용 Supabase 흉내)
- Create: `batch/tests/conftest.py`
- Create: `batch/tests/test_schema.py`
- Create: `batch/pyproject.toml` (의존성: psycopg[binary], httpx, beautifulsoup4, pytest)

**Interfaces:**
- Produces:
  - 테이블 `institutions(id bigint identity pk, key text unique not null, name text not null, sido text not null check (sido in ('서울','경기')), sigungu text, homepage_url text not null)`
  - 테이블 `programs(id bigint identity pk, institution_id bigint not null references institutions, source_id text not null, title text not null, description text, url text not null, grade_min int check 1..6, grade_max int check 1..6 and >= grade_min, starts_on date, ends_on date, apply_starts_at timestamptz, apply_ends_at timestamptz, fee text, collected_at timestamptz not null default now(), unique (institution_id, source_id))`
  - 테이블 `collect_runs(id bigint identity pk, target text not null, started_at timestamptz not null default now(), ok boolean not null, item_count int, error text)`
  - `institutions.sido`는 enum `sido`('서울','경기'). 나머지 전체 테이블은 `schema.sql` 참고
  - 뷰 `upcoming_programs`: `programs` join `institutions`, `coalesce(ends_on, starts_on) >= current_date` 또는 둘 다 NULL이면 `apply_ends_at >= now()`.
  - RLS: `institutions`, `programs`는 anon·authenticated `select` 허용, 쓰기 정책 없음. `collect_runs`는 정책 없음(앱 접근 불가).
  - pytest 픽스처 `db` (psycopg 연결, 테스트마다 새 DB에 stub+마이그레이션 적용). 환경변수 `TEST_PG_ADMIN_URL` (기본 `postgresql://postgres@localhost:5432/postgres`).

- [ ] **Step 1: 로컬 Postgres 띄우기**
  Run: `/usr/lib/postgresql/16/bin/initdb -D /tmp/pg -U postgres --auth=trust && /usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pg -l /tmp/pg.log start`
  Expected: `server started`

- [ ] **Step 2: 실패하는 테스트 작성** (`batch/tests/test_schema.py`)
  - `test_upcoming_view_hides_ended`: 종료일 어제 1건, 내일 1건 insert → 뷰 결과 제목이 내일 것 1건.
  - `test_sido_rejects_other_region`: `sido='부산'` insert → `psycopg.errors.InvalidTextRepresentation`.
  - `test_anon_can_read_but_not_write`: `set role anon` 후 `select` 성공, `insert into programs` → `InsufficientPrivilege` 또는 RLS 위반.
  - `test_grade_range_check`: `grade_min=5, grade_max=3` → `CheckViolation`.

- [ ] **Step 3: 실패 확인** — Run: `cd batch && pytest tests/test_schema.py -v` / Expected: FAIL (테이블 없음)

- [ ] **Step 4: conftest 작성** (stub + `schema.sql` 적용), 마이그레이션 파일 복사

- [ ] **Step 5: 통과 확인** — Run: `cd batch && pytest tests/test_schema.py -v` / Expected: 4 passed

- [ ] **Step 6: Commit** — `git add supabase batch && git commit -m "feat(db): programs schema, RLS, upcoming view"`

### Task 2: 날짜·학년 파싱 도우미

**Files:**
- Create: `batch/eduapp_batch/parse.py`
- Test: `batch/tests/test_parse.py`

**Interfaces:**
- Produces:
  - `parse_date(text: str, today: date) -> date | None`
  - `parse_date_range(text: str, today: date) -> tuple[date | None, date | None]`
  - `parse_datetime(text: str, today: date) -> datetime | None` (시간대 Asia/Seoul)
  - `parse_grades(text: str) -> tuple[int, int] | None` (초등 해당 없으면 None)

- [ ] **Step 1: 실패하는 테스트** (`today = date(2026, 11, 6)`)
  - `parse_date("2026. 11. 6.(목)") == date(2026,11,6)`, `parse_date("2026-11-06") == date(2026,11,6)`, `parse_date("11.20") == date(2026,11,20)`, `parse_date("1.5") == date(2027,1,5)` (오늘보다 2개월 넘게 이전이면 다음 해), `parse_date("상시") is None`
  - `parse_date_range("2026.11.6 ~ 2026.11.20") == (date(2026,11,6), date(2026,11,20))`, `parse_date_range("11.6~11.20") == (date(2026,11,6), date(2026,11,20))`
  - `parse_datetime("2026-11-10 10:00", today)` == 2026-11-10 10:00 KST
  - `parse_grades("초등 3~4학년") == (3,4)`, `parse_grades("초3-6") == (3,6)`, `parse_grades("전학년") == (1,6)`, `parse_grades("초등학생") == (1,6)`, `parse_grades("유아") is None`, `parse_grades("중학생 이상") is None`, `parse_grades("7세~초2") == (1,2)`

- [ ] **Step 2: 실패 확인** — `pytest tests/test_parse.py -v` / FAIL (import 오류)
- [ ] **Step 3: 구현** — 정규식 기반. 연도 없는 날짜 규칙은 위 테스트가 정함.
- [ ] **Step 4: 통과 확인** — 모든 케이스 PASS
- [ ] **Step 5: Commit** — `feat(batch): korean date and grade parsers`

### Task 3: 수집 결과 저장 (upsert)

**Files:**
- Create: `batch/eduapp_batch/models.py`, `batch/eduapp_batch/store.py`
- Test: `batch/tests/test_store.py`

**Interfaces:**
- Consumes: Task 1 테이블, `db` 픽스처
- Produces:
  - `@dataclass(frozen=True) class Program: source_id: str; title: str; url: str; description: str | None = None; grade_min: int | None = None; grade_max: int | None = None; starts_on: date | None = None; ends_on: date | None = None; apply_starts_at: datetime | None = None; apply_ends_at: datetime | None = None; fee: str | None = None`
  - `@dataclass(frozen=True) class Institution: key: str; name: str; sido: str; sigungu: str | None; homepage_url: str`
  - `ensure_institution(conn, inst: Institution) -> int` (id 반환, 있으면 갱신)
  - `upsert_programs(conn, institution_id: int, programs: list[Program]) -> int` (`on conflict (institution_id, source_id) do update`, 반환값 = 처리 건수)
  - `record_run(conn, target: str, ok: bool, item_count: int | None, error: str | None) -> None`

- [ ] **Step 1: 실패하는 테스트**
  - `test_upsert_is_idempotent`: 같은 2건을 두 번 upsert → `programs` 2행, 두 번째에 바꾼 제목이 반영.
  - `test_ensure_institution_returns_same_id`: 두 번 호출 → 같은 id.
  - `test_record_run_stores_error`: `ok=False, error="boom"` → `collect_runs`에 1행.
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** — `feat(batch): idempotent program upsert`

### Task 4: 첫 기관 수집기 — 국립과천과학관

**Files:**
- Create: `batch/eduapp_batch/collectors/__init__.py` (레지스트리 `COLLECTORS: dict[str, Collector]`)
- Create: `batch/eduapp_batch/collectors/gwacheon_science.py`
- Create: `batch/tests/fixtures/gwacheon_science_list.html`
- Test: `batch/tests/test_gwacheon_science.py`

**Interfaces:**
- Consumes: `Program`, `Institution`, Task 2 파서
- Produces (모든 수집기 공통 계약):
  - `class Collector(Protocol): institution: Institution; list_urls: list[str]; def parse(self, html: str, page_url: str, today: date) -> list[Program]: ...`
  - `source_id`는 기관 페이지의 프로그램 고유번호(URL 쿼리 등)에서 만든다. 고유번호가 없으면 `제목|시작일` 문자열.

- [ ] **Step 1: 샘플 저장 (네트워크 Full 환경)** — 과학관 교육·행사 프로그램 목록 페이지를 `curl`로 받아 fixture로 저장하고, 그 URL을 `list_urls`에 적는다. 화면에 보이는 첫 프로그램의 제목·기간·대상을 메모해 둔다.
- [ ] **Step 2: 실패하는 테스트** — `parse(fixture, url, date(2026,11,6))` 결과가 1건 이상. 첫 항목의 `title`, `starts_on`, `ends_on`, `grade_min/max`가 Step 1 메모 값과 같다. 모든 항목의 `url`이 `http`로 시작하는 절대 URL이다. 초등 대상이 아닌 항목(`parse_grades`가 None)은 빠진다.
- [ ] **Step 3: 실패 확인** / **Step 4: BeautifulSoup으로 구현** / **Step 5: 통과 확인**
- [ ] **Step 6: Commit** — `feat(batch): gwacheon science collector`

### Task 5: 두 번째 기관 수집기 — 국립중앙박물관

**Files:**
- Create: `batch/eduapp_batch/collectors/museum_korea.py`, `batch/tests/fixtures/museum_korea_list.html`
- Test: `batch/tests/test_museum_korea.py`

**Interfaces:** Task 4의 `Collector` 계약 그대로. `COLLECTORS`에 등록.

- [ ] Step 1~6: Task 4와 같은 순서 (샘플 저장 → 테스트 → 구현 → 통과 → 커밋 `feat(batch): national museum collector`)

### Task 6: 수집 실행기

**Files:**
- Create: `batch/eduapp_batch/run_programs.py` (`python -m eduapp_batch.run_programs`)
- Test: `batch/tests/test_run_programs.py`

**Interfaces:**
- Consumes: `COLLECTORS`, `ensure_institution`, `upsert_programs`, `record_run`
- Produces:
  - `run(conn, collectors: dict[str, Collector], fetch: Callable[[str], str], today: date) -> dict[str, int | str]` (기관 key → 저장 건수 또는 오류 메시지)
  - CLI: 환경변수 `DATABASE_URL` 사용, `fetch`는 httpx(타임아웃 20초, User-Agent `eduApp-collector`). 종료 코드: 모든 기관 실패 시 1, 그 외 0. 마지막 줄에 결과 요약 JSON 출력.

- [ ] **Step 1: 실패하는 테스트** (가짜 fetch와 가짜 collector 사용)
  - `test_one_collector_failure_does_not_stop_others`: collector A는 parse에서 예외, B는 1건 → 결과 `{"a": "<오류>", "b": 1}`, `programs` 1행, `collect_runs`에 A 실패·B 성공.
  - `test_each_institution_commits_separately`: B 저장 후 A 실패해도 B 데이터가 남는다.
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** (기관마다 트랜잭션 분리) / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** — `feat(batch): program collection runner`

### Task 7: Claude 예약 작업 연결

**Files:**
- Create: `batch/SCHEDULED_TASK.md` (예약 작업이 매일 따르는 지침: 의존성 설치 → `python -m eduapp_batch.run_programs` → 결과 요약 확인 → 실패 기관이 있으면 원인 기록)

**Interfaces:**
- Consumes: Task 6 CLI, 환경변수 `DATABASE_URL` (Supabase 프로젝트의 DB 연결 문자열, 환경 시크릿으로 등록)

- [ ] **Step 1: 사용자 준비 확인** — Supabase 프로젝트 생성, 마이그레이션 적용, `DATABASE_URL` 환경변수 등록, 환경 네트워크 Full. 사용자에게 확인받기 전에는 다음 단계로 가지 않는다.
- [ ] **Step 2: 수동 1회 실행** — Run: `cd batch && python -m eduapp_batch.run_programs` / Expected: 요약 JSON에 두 기관 모두 숫자, `select count(*) from upcoming_programs` > 0
- [ ] **Step 3: 예약 작업 생성** — 매일 새벽(KST) 1회, 새 세션, 지침 = `batch/SCHEDULED_TASK.md`. 사용자 확인 후 생성.
- [ ] **Step 4: Commit** — `docs(batch): scheduled task instructions`
