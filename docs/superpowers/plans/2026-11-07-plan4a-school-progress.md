# 계획 4a: 학교 평가계획 기반 "예상 진도" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (이 저장소의 사용자 지시: 구현·수정 서브에이전트는 sonnet, 리뷰 서브에이전트는 opus.)

**Goal:** 학교 홈페이지에 공개된 학년·학기별 "학생평가계획" 첨부에서 과목·성취기준 코드·단원명·평가 월을 읽어 DB에 저장하고, 앱 "우리 학교" 탭이 1~6학년 자녀에게 "이번 달 예상 진도"를 보여준다. 1·2학년의 시기별 과정도 이것으로 채운다.

**Architecture:** 배치 `run_progress`가 평가계획 게시물을 찾아 첨부를 내려받고(계획 3의 공지 탐색 재사용) 글자로 바꾼 뒤, **코드로 직접 파싱**해(AI 판단 없음, 같은 입력에 같은 결과) DB 함수로 저장한다. hwp는 미리보기(약 1,000자에서 잘림) 대신 본문 전체를 읽도록 `extract_text`를 고친다. 앱은 `EduRepository`에 메서드를 더해 학기를 계산하고 이번 달·다음 달 항목을 보여준다. 전국 공통 기준선(NCIC 성취기준)과의 교차 검증은 이번 계획에 넣지 않는다(계획 4b).

**Tech Stack:** Python 3.13(`olefile`, `zlib`, `beautifulsoup4`, `httpx`), PostgreSQL 16 + pytest, Flutter + flutter_test.

**Spec:** `docs/superpowers/specs/2026-11-06-eduapp-design.md` ("학교 기준 교육과정 정보", "이번 주 진도는 추정치" — 스펙은 학사일정+성취기준 순서로 추정하라고 했으나, 학교가 공개한 평가계획이 더 직접적인 근거이므로 이를 1차 출처로 쓴다) + `docs/09-style-guide.md`

## 사전 조사 결과 (2026-11-07, 귀인초 kwiin-e.goeay.kr 실제 첨부)
- 학년별·학기별 파일(예: `2026학년도 1학년 1학기 평가계획.hwp`, `2026학년도 4학년 1학기 평가계획.hwpx`)이 `2022~2026학년도`에 걸쳐 있다. 한 게시물에 1~6학년 6개 첨부가 달린다. `수정 안내` 게시물이 따로 올라오기도 한다.
- 표 열: `과목 | 성취기준 | 단원명 | 평가영역 | 평가 요소 | 방법 | (평가 기준) | 평가 시기`. 성취기준은 `[2국01-04] 설명…` 형식이고 1·2학년은 `[2…]`, 3·4학년 `[4…]`, 5·6학년 `[6…]`. 평가 시기는 `5월`. 예: `국어 [2국01-04] 2. 받침이 있는 글자를 읽어요 … 5월`, `[2국04-03]`의 단원은 `6.`과 `또박또박 읽어요`가 두 줄로 갈라져 나온다.
- 표에는 성취기준 코드가 없는 창의적 체험활동(`자율·자치활동`, `동아리활동`) 표도 섞여 있다.
- 현재 `extract_text`는 hwp를 미리보기만 읽어 1,022~1,023자에서 잘린다(평가계획은 사실상 못 읽음). hwp 본문 전체 읽기를 시험했고(`olefile`+`zlib`, FileHeader 압축 비트, BodyText/Section 레코드 태그 67) 1학년 1학기 파일에서 1,805자가 끝까지 읽혔다. 현재 hwpx 읽기는 문단·셀을 붙여서 내보낸다(`사회[4사01-02]주변의…`) → 줄 구분이 필요하다.
- 연속 다운로드 중 서버가 연결을 한 번 끊었다 → 요청 간격과 재시도 필요.

## Global Constraints

- 지원 홈페이지는 `*.goeay.kr`뿐(계획 3과 같음). 그 밖은 `not_found`가 아니라 **건너뜀**(진도 없음)이고 사유를 `collect_runs`에 남긴다.
- 학년 1~6, 학기 1·2, 월 1~12. `standard_code`는 `[<학년군숫자><과목한글><2자리>-<2자리>]` 형식(예 `[2국01-04]`)으로 **정규화**해 저장한다(`[4도 01-01]`의 공백 제거).
- **정확성:** 앱 화면의 제목은 반드시 `이번 달 예상 진도`, 각 줄은 `<과목> · <단원명>` 아래 `<n>월 평가 예정`, 하단 한 줄 `학교 평가계획 기준이며 바뀔 수 있어요`. 평가 월은 수업 월이 아니라 단원 평가 월이므로 "수업"이라고 쓰지 않는다.
- 학년도/학기: 3~8월 = 그 해 1학기, 9~12월 = 그 해 2학기, 1~2월 = 직전 학년도 2학기. 달력은 KST.
- 쓰기는 service_role(배치)만. 앱은 읽기 전용(RLS `read_all`). 앱이 부르는 DB 함수 `child_progress`는 본인 자녀만.
- 실패는 학교 단위로 격리하고 `collect_runs`(`target = 'progress:<neis_code>'`)에 남긴다. DB 호출이 오류 처리 핸들러 안에서 다시 실패해도 다른 학교 처리를 멈추지 않는다(계획 3 최종 리뷰 교훈). 한 번에 최대 20개 학교(`shortcut:` 주석), 학교 사이 1.0초·내려받기 사이 0.5초 간격(테스트에서는 `sleep` 주입).
- 첨부를 하나도 못 내려받았으면(다운로드 실패만 있고 글자가 없음) 수집 완료로 표시하지 않고 `failed` 사유로 기록해 다음 실행에서 다시 시도한다.
- 마이그레이션은 새 파일 `supabase/migrations/20261109000001_school_progress.sql`, `schema.sql`은 마이그레이션 연결본과 같아야 한다(기존 테스트가 검사). **원격 DB 적용은 사용자 승인 후 Task 8에서만** 한다.
- **사용자 준비:** 원격 마이그레이션 적용 승인(Task 8 직전). 시범은 귀인초 1곳(id 760).

## Review Focus

1. **같은 학년·학기에 원본 + `수정 안내` 게시물** → 나중(번호가 큰) 게시물 값이 이긴다. (Task 4 `later post overwrites earlier for same key`)
2. **창의적 체험활동 표(코드 없음)와 평가 월이 비거나 `3월~4월` 범위** → 코드 없는 행은 무시, 월이 없는 행은 버리고 개수를 기록, 범위면 첫 달. (Task 2 `ignores rows without standard code`, `month range uses first month`)
3. **2월·1월·8/9월 경계** → 2월에는 직전 학년도 2학기, 3월 1일부터 새 학기. (Task 7 `school term boundaries`)
4. **평가계획을 공개하지 않는 학교** → 빈 화면 대신 `학교 평가계획을 아직 찾지 못했어요`. (Task 7 `empty progress shows notice`)
5. **자녀를 바꾸는 중에 늦게 온 응답** → 다른 자녀의 진도가 보이지 않는다(계획 3 `_loadId` 패턴). (Task 7 `stale progress load ignored`)

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `batch/eduapp_batch/extract_text.py` (수정) | hwp 본문 전체 읽기, hwpx 문단 줄바꿈 |
| `batch/eduapp_batch/school_progress.py` | 평가계획 글자 → 진도 행 파싱 |
| `batch/eduapp_batch/school_notices.py` (수정) | 공지 탐색을 검색어 인자로 일반화, 평가계획 게시물 선택 |
| `supabase/migrations/20261109000001_school_progress.sql` | 진도 테이블·함수 |
| `batch/eduapp_batch/store.py` (수정) | 진도 저장·대상 학교 조회 |
| `batch/eduapp_batch/run_progress.py` | 자동 수집 실행기 |
| `app/lib/**` (수정) | 학기 계산, 저장소 메서드, 우리 학교 탭 진도 구역 |

---

### Task 1: hwp 본문 전체 읽기, hwpx 문단 구분

**Files:**
- Modify: `batch/eduapp_batch/extract_text.py`
- Create: `batch/tests/fixtures/assessment_1_1.hwp`, `assessment_4_1.hwpx` (귀인초 2026학년도 1학기 1·4학년 평가계획 실제 파일)
- Test: `batch/tests/test_extract_text.py` (기존 파일에 추가)

**Interfaces:**
- Consumes/Produces: `extract_text(name: str, data: bytes) -> str` (시그니처 불변). hwp는 BodyText 전체(압축 비트가 켜져 있으면 `zlib.decompress(raw, -15)`)를 읽어 문단(태그 67) 사이를 `\n`으로 잇고, BodyText가 없거나 암호화·배포용 문서면 기존 `PrvText` 미리보기로 대체하며 그것도 안 되면 `""`. hwpx는 문단(`p`)마다 `\n`, 같은 문단 안의 `t`는 이어 붙인다. 기존 `shortcut:` 주석(미리보기 한계)은 제거한다.

- [ ] **Step 1: 픽스처 확보** — 귀인초 공지에서 위 두 파일을 받아 `tests/fixtures/`에 저장(경로는 `school_notices`로 찾는 공지 `2026학년도 1학기 학생평가계획`의 첨부). 개인정보(교사 이름 외 학생·학부모 정보)가 없는지 추출 글자로 확인하고, 있으면 다른 학년 파일로 바꾼다. 각 파일 500KB 이하.
- [ ] **Step 2: 실패하는 테스트 작성**
  - `test_hwp_full_body_not_truncated`: `assessment_1_1.hwp` 결과가 1,500자 이상이고 `[2국01-04]`와 마지막 줄 `위 평가계획은 교육과정에 의해 변경 운영될 수 있습니다`를 포함.
  - `test_hwp_falls_back_to_preview_without_bodytext`: BodyText가 없는 OLE 파일(테스트 안에서 `olefile`로 만들 수 없으면 `PrvText`만 있는 기존 `sample.hwp`와 같은 방식)에서 빈 문자열이 아니라 미리보기 글자.
  - `test_hwpx_paragraphs_on_separate_lines`: 메모리에서 만든 hwpx(`hp:p` 두 개)가 `"가\n나"`로 나옴. 실제 `assessment_4_1.hwpx`에서는 `[4국02-04]`가 줄의 맨 앞에 옴.
  - 기존 테스트(`test_hwp_text` 등)는 계속 통과.
- [ ] **Step 3: 실패 확인 → 구현 → 통과 확인** — Run: `cd batch && TEST_PG_ADMIN_URL='postgresql://root@/postgres?host=/var/run/postgresql' python -m pytest tests/test_extract_text.py -q`. hwp 레코드는 4바이트 헤더(`tag = h & 0x3FF`, `size = (h >> 20) & 0xFFF`, size가 0xFFF면 다음 4바이트가 실제 크기), 제어문자 `\x00-\x08\x0b-\x1f`는 공백으로 바꾼다. 어떤 예외도 밖으로 내지 않는다.
- [ ] **Step 4: Commit** — `git commit -m "feat(batch): read full hwp body and keep hwpx paragraph breaks"`

---

### Task 2: 평가계획 파서

**Files:**
- Create: `batch/eduapp_batch/school_progress.py`
- Test: `batch/tests/test_school_progress.py` (Task 1의 두 픽스처를 `extract_text`로 읽어 사용, 추가로 3학년용 hwpx 한 개를 `assessment_3_1.hwpx`로 저장해 줄 구분이 달라도 같은 결과가 나오는지 본다)

**Interfaces:**
- Produces: `@dataclass(frozen=True) ProgressRow(subject: str, standard_code: str, unit_title: str, month: int)`, `@dataclass(frozen=True) AssessmentPlan(school_year: int, grade: int, semester: int, rows: list[ProgressRow], dropped: int)`, `parse_assessment_plan(text: str) -> AssessmentPlan | None`.
- 규칙: 머리글에서 `(\d{4})학년도`, `(\d)\s*\)?\s*학년`(`( 2 )학년` 포함), `(\d)학기`를 찾고 하나라도 없으면 `None`. 성취기준 줄은 `\[\s*(\d)\s*([가-힣]+)\s*(\d{2})\s*-\s*(\d{2})\s*\]`로 찾아 `[4도01-01]` 형태로 정규화. 과목 = 그 줄 앞쪽에서 가장 가까운, 줄 전체가 과목명인 줄(과목명 집합은 픽스처에서 확인해 상수로 둔다: 최소 국어·수학·사회·도덕·과학·영어·음악·미술·체육·실과와 1·2학년 통합교과 계열; 집합에 없는 줄은 건너뛰고 직전 과목을 이어받는다). 단원명 = 성취기준 줄 다음 줄이고, 그 줄이 `^\d+\.?$`(번호만)이면 다음 줄을 공백으로 이어 붙인다(`6.` + `또박또박 읽어요`). 월 = 다음 성취기준 줄 전까지에서 `(\d{1,2})월`이 처음 나오는 곳(1~12). 월을 못 찾은 행은 버리고 `dropped`를 센다. 같은 `(과목, 코드)`는 첫 행만.
  `# shortcut: 단원명은 성취기준 다음 한 줄(번호만 있으면 두 줄)로 본다, 단원명이 여러 줄로 갈라지는 학교가 나오면 영역 단어 목록으로 끊는다`

- [ ] **Step 1: 실패하는 테스트 작성** (실제 픽스처 값으로)
  - `test_grade1_hwp_rows`: 1학년 1학기 → `school_year 2026, grade 1, semester 1`; 행 `ProgressRow("국어","[2국01-04]","2. 받침이 있는 글자를 읽어요",5)`, `ProgressRow("국어","[2국04-03]","6. 또박또박 읽어요",7)`, 수학 `[2수03-01]` 단원 `2. 여러 가지 모양` 월 5가 포함.
  - `test_grade4_hwpx_rows`: 4학년 1학기 → grade 4, `[4국02-04]` 월 4, 사회 `[4사05-01]` 월 4가 포함, 모든 코드가 `^\[4`로 시작(`[6…]` 없음).
  - `test_glued_text_still_yields_rows`: 3학년 파일에서 `dropped`가 전체의 30% 미만.
  - `test_ignores_rows_without_standard_code`: 체험활동 표(`자율·자치활동`)에서 행이 만들어지지 않음.
  - `test_month_range_uses_first_month`: 입력 조각 `…[4국01-01]\n단원\n3월~4월` → 월 3.
  - `test_standard_code_spaces_normalized`: `[4도 01-01]` → `[4도01-01]`.
  - `test_no_header_returns_none`: `"아무 글"` → `None`.
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `cd batch && TEST_PG_ADMIN_URL='postgresql://root@/postgres?host=/var/run/postgresql' python -m pytest tests/test_school_progress.py -q`
- [ ] **Step 3: Commit** — `git commit -m "feat(batch): parse school assessment plans into progress rows"`

---

### Task 3: DB — 진도 테이블과 함수

**Files:**
- Create: `supabase/migrations/20261109000001_school_progress.sql`
- Modify: `supabase/schema.sql` (`cat supabase/migrations/*.sql > supabase/schema.sql`)
- Test: `batch/tests/test_school_progress_db.py`

**Interfaces:**
- Produces (SQL):
  - 테이블 `school_progress(school_id bigint references schools on delete cascade, school_year int, grade int check (grade between 1 and 6), semester int check (semester in (1,2)), subject text, standard_code text, unit_title text, month int check (month between 1 and 12), source_url text, updated_at timestamptz default now(), primary key (school_id, school_year, grade, semester, subject, standard_code))`. 기존 참조 테이블과 같은 방식으로 RLS를 켜고 `read_all` 정책(select to anon, authenticated).
  - `alter table schools add column progress_collected_at timestamptz`.
  - `apply_school_progress(p_school_id bigint, p_school_year int, p_grade int, p_semester int, p_subject text, p_standard_code text, p_unit_title text, p_month int, p_source_url text) returns void` — service_role만. 과목·단원명은 공백 제거 후 1~60자, `standard_code`는 `^\[\d[가-힣]+\d{2}-\d{2}\]$`가 아니면 예외, 월·학년·학기 범위 밖이면 예외. `on conflict … do update`.
  - `child_progress(p_child_id bigint, p_school_year int, p_semester int) returns table(subject text, standard_code text, unit_title text, month int)` — 본인 자녀만(`not your child`), 그 자녀 학교·학년·학년도·학기 행을 `month, subject, standard_code` 순으로. authenticated에 grant, public/anon revoke. 모든 함수 `security definer set search_path = public`.

- [ ] **Step 1: 실패하는 테스트 작성** (`test_school_info.py`의 사용자·자녀 만들기 패턴 재사용)
  - `test_apply_inserts_and_updates_in_place`: 같은 키로 단원명을 바꿔 두 번 호출 → 1행, 단원명은 새 값.
  - `test_apply_rejects_bad_input`: 코드 `[abc]`, 월 13, 학기 3, 공백 단원명, 61자 단원명.
  - `test_child_progress_scopes_to_child_school_grade_and_term`: 같은 학교 다른 학년·다른 학기·다른 학교 행이 섞여도 자녀 학교·학년·지정 학년도·학기 행만, 월 순서로.
  - `test_child_progress_requires_own_child`
  - `test_apply_not_executable_by_authenticated`: `set role authenticated` 후 `apply_school_progress` 호출 시 권한 오류.
- [ ] **Step 2: 실패 확인 → 마이그레이션 작성 → 통과 확인** — Run: `cd batch && TEST_PG_ADMIN_URL='postgresql://root@/postgres?host=/var/run/postgresql' python -m pytest tests/test_school_progress_db.py tests/test_app_basics.py -q`
- [ ] **Step 3: Commit** — `git commit -m "feat(db): school progress table and functions"`

---

### Task 4: 평가계획 게시물 찾기

**Files:**
- Modify: `batch/eduapp_batch/school_notices.py`
- Create: `batch/tests/fixtures/school_progress_list.html`, `school_progress_detail.html` (귀인초 실제 응답)
- Test: `batch/tests/test_school_notices.py` (기존 파일에 추가)

**Interfaces:**
- Consumes: 기존 `_menu`, `_read_post`, `Post`, `Attachment`, `UnsupportedSite`.
- Produces: `find_posts(homepage_url, fetch, search_words: tuple[str, ...], title_words: tuple[str, ...]) -> list[Post]`(기존 `find_textbook_posts` 본문을 일반화; `find_textbook_posts`는 이를 `SEARCH_WORDS/TITLE_WORDS`로 부르는 한 줄 래퍼로 동작이 같아야 한다) 와 `find_assessment_posts(homepage_url, fetch) -> list[Post]` = 검색어 `("평가",)`, 제목어 `("평가계획",)`(공백 제거 후 비교)로 부르고, 제목에서 `(\d{4})학년도`를 읽어 **가장 큰 학년도의 게시물만** 남기며, 게시물 번호(`nttSn`) 오름차순(나중 글이 뒤)으로 정렬해 돌려준다. 게시물은 최대 6개.
- 게시물 번호는 상세 URL의 `nttSn=` 값(정수)이다.

- [ ] **Step 1: 픽스처 저장** — 귀인초 `공지사항`·`가정통신문` 게시판에서 `평가` 검색 목록 한 쪽과 `2026학년도 1학기 학생평가계획` 상세 한 건(첨부 6개가 보이는 것)을 저장하고 첫 줄 주석에 출처·날짜를 적는다.
- [ ] **Step 2: 실패하는 테스트 작성**
  - `test_find_assessment_posts_keeps_newest_school_year_only`: 2026학년도와 2025학년도 제목이 섞인 목록에서 2026만.
  - `test_find_assessment_posts_orders_by_post_number_ascending`
  - `test_find_assessment_posts_drops_non_plan_titles`: `교육과정 설명회` 같은 제목 제외.
  - `test_find_textbook_posts_behaviour_unchanged`: 기존 교과서 테스트가 그대로 통과(래퍼).
  - `test_find_assessment_posts_unsupported_site_raises`
- [ ] **Step 3: 실패 확인 → 구현 → 통과 확인** — Run: `cd batch && TEST_PG_ADMIN_URL='postgresql://root@/postgres?host=/var/run/postgresql' python -m pytest tests/test_school_notices.py -q`
- [ ] **Step 4: Commit** — `git commit -m "feat(batch): find assessment plan posts"`

---

### Task 5: 저장소 메서드

**Files:**
- Modify: `batch/eduapp_batch/store.py`
- Test: `batch/tests/test_store.py`, `batch/tests/test_store_rest.py` (기존 파일에 추가)

**Interfaces:**
- Produces — `PgStore`와 `RestStore` 양쪽 같은 시그니처:
  - `schools_needing_progress(today: date) -> list[dict]` — 키 `id, neis_code, edu_office_code, name, homepage_url, collect_status`. 자녀가 한 명이라도 있고 `progress_collected_at`이 `null`이거나 `today` 기준 30일보다 오래된 학교, `id` 순.
  - `apply_progress(school_id: int, school_year: int, grade: int, semester: int, row: ProgressRow, source_url: str | None) -> None` — `apply_school_progress` 호출.
  - `set_progress_collected(school_id: int) -> None` — `progress_collected_at = now()`.
- REST: `apply_progress` = `POST /rest/v1/rpc/apply_school_progress`(키 `p_school_id,p_school_year,p_grade,p_semester,p_subject,p_standard_code,p_unit_title,p_month,p_source_url`), `set_progress_collected` = `PATCH /rest/v1/schools?id=eq.<id>`, `schools_needing_progress`는 `schools?select=…,children!inner(id)`에 `or=(progress_collected_at.is.null,progress_collected_at.lt.<ISO>)`를 쓴다(계획 3 `schools_with_children`과 같은 임베딩). 요청 모양은 실제 서버에서 읽기 전용으로 한 번 확인한다.

- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_schools_needing_progress_filters`: 자녀 없음 제외, 방금 수집 제외, 31일 전 포함, null 포함, 29일 전 제외.
  - `test_apply_progress_and_mark_collected`: 행 저장 후 `progress_collected_at`이 채워짐.
  - REST: RPC 본문 키, PATCH 경로, 조회 쿼리 문자열을 정확히 검사.
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `cd batch && TEST_PG_ADMIN_URL='postgresql://root@/postgres?host=/var/run/postgresql' python -m pytest tests/test_store.py tests/test_store_rest.py -q`
- [ ] **Step 3: Commit** — `git commit -m "feat(batch): progress store methods"`

---

### Task 6: `run_progress` 실행기

**Files:**
- Create: `batch/eduapp_batch/run_progress.py`
- Test: `batch/tests/test_run_progress.py`

**Interfaces:**
- Consumes: `find_assessment_posts`(Task 4), `extract_text`(Task 1), `parse_assessment_plan`(Task 2), store 메서드(Task 5), `record_run`.
- Produces: `run(store, fetch, fetch_bytes, today, sleep=time.sleep) -> dict[str, int | str]`(학교 `neis_code` → 저장한 행 수 또는 오류/사유 문자열). 명령줄 `python -m eduapp_batch.run_progress`(저장소 선택·`print(json)`·종료코드는 `run_schools.main`과 같게).
- 동작: 학교마다 ①`find_assessment_posts` ②게시물(번호 오름차순) 첨부를 내려받아 `extract_text`→`parse_assessment_plan` ③같은 `(school_year, grade, semester, subject, standard_code)`는 **나중 게시물 값이 이긴다**(딕셔너리 덮어쓰기) ④`apply_progress` ⑤`set_progress_collected`. 계획을 하나도 못 읽으면(게시물 없음 `평가계획 공지 없음`, 글자 없음 `첨부에서 글자를 읽지 못함`, 파서 `None` `평가계획 형식을 읽지 못함`) 행 0개이며 `progress_collected_at`은 채우고(30일 뒤 재시도) 사유를 `collect_runs`에 ok=False로 남긴다. 다운로드가 모두 실패하고 글자가 없으면 예외(수집 완료 표시 없음). 학교 상한 20, 간격 1.0/0.5초. 학교별 처리 전체를 보호해 DB 오류가 다른 학교를 멈추지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성** (메모리 가짜 store, Task 1·4 픽스처, 가짜 fetch/fetch_bytes, `sleep` 주입)
  - `test_saves_rows_and_marks_collected`
  - `test_later_post_overwrites_earlier_for_same_key`: 같은 키 두 게시물 → 나중 값.
  - `test_no_posts_marks_collected_with_reason`
  - `test_all_downloads_fail_does_not_mark_collected`
  - `test_unreadable_format_records_reason`
  - `test_one_school_db_error_does_not_stop_others`
  - `test_caps_at_20_schools_and_throttles`
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `cd batch && TEST_PG_ADMIN_URL='postgresql://root@/postgres?host=/var/run/postgresql' python -m pytest tests/test_run_progress.py -q`
- [ ] **Step 3: Commit** — `git commit -m "feat(batch): run_progress collector"`

---

### Task 7: 앱 — "이번 달 예상 진도"

**Files:**
- Modify: `app/lib/format.dart`, `app/lib/data/models.dart`, `app/lib/data/repository.dart`, `app/lib/data/supabase_repository.dart`, `app/lib/screens/school_tab.dart`, `app/test/fake_repository.dart`
- Test: `app/test/format_test.dart`, `app/test/school_tab_test.dart` (기존 파일에 추가)

**Interfaces:**
- Produces: `(int, int) schoolTerm(DateTime today)` → `(학년도, 학기)`(Global Constraints의 경계 규칙, 인자는 이미 KST 벽시계 값). `class ProgressItem { String subject; String standardCode; String unitTitle; int month; }`. `EduRepository.childProgress(int childId, int schoolYear, int semester) -> Future<List<ProgressItem>>`(RPC `child_progress`). `FakeRepository`에 `progressByChild` 맵, `holdProgress`(Completer) 훅, `failWith` 지원, `calls` 기록(`childProgress`).
- 화면: 우리 학교 탭 출판사 구역 아래(또는 3학년 미만이면 그것 대신)에 `이번 달 예상 진도` 구역. 이번 달 항목은 `<과목> · <단원명>` + `<n>월 평가 예정`, 비어 있고 다음 달 항목이 있으면 `다음 달` 소제목으로 다음 달 항목. 이번·다음 달 모두 없으면 `이번 달 평가 예정 단원이 없어요`. 학기 전체가 비어 있으면(학교가 평가계획을 공개하지 않음) `학교 평가계획을 아직 찾지 못했어요`. 구역 맨 아래 `학교 평가계획 기준이며 바뀔 수 있어요`. 3학년 미만 자녀는 기존 `3학년부터 출판사를 볼 수 있어요` 대신 `1·2학년은 모든 학교가 같은 국정교과서를 써요`를 상단에 보이고 진도 구역은 그대로 보인다. 자녀 전환 중 늦게 온 응답은 기존 `_loadId`로 버린다(진도도 같은 로드 안에서 가져온다). 진도 로드 실패는 출판사 구역을 막지 않고 진도 구역만 `불러오지 못했어요` + `다시 시도`.

- [ ] **Step 1: 실패하는 테스트 작성**
  - `school term boundaries` (format_test): 2026-02-28 → (2025,2), 2026-03-01 → (2026,1), 2026-08-31 → (2026,1), 2026-09-01 → (2026,2), 2026-12-31 → (2026,2), 2027-01-01 → (2026,2).
  - `shows this month items with assessment month label`: 오늘 2026-11-07, 항목 11월 → 해당 줄과 `11월 평가 예정` 표시, 12월 항목은 `다음 달` 아래.
  - `empty progress shows notice`: 학기 행 0개 → `학교 평가계획을 아직 찾지 못했어요`.
  - `no items this and next month shows no-exam notice`
  - `grade under 3 shows national textbook notice and progress`
  - `stale progress load ignored`(Completer로 늦게 온 이전 자녀 응답)
  - `progress failure does not hide publishers`
  - `no overflow at textScale 2.0` (진도 구역 포함, 행이 실제로 보이는지도 단언)
  - 기존 테스트 중 3학년 미만 문구에 의존하는 것은 갱신(삭제하지 않는다).
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인** — Run: `export PATH=/opt/flutter/bin:$PATH; cd app && flutter test test/format_test.dart test/school_tab_test.dart` 후 전체 `flutter test`와 `flutter analyze`. 기존 파일 전체에 `dart format`을 돌리지 않는다.
- [ ] **Step 3: Commit** — `git commit -m "feat(app): this month's expected progress on school tab"`

---

### Task 8: 운영 연결과 시범 실행

**Files:**
- Modify: `batch/SCHEDULED_TASK.md`, `docs/08-plan.md`
- 사용: 원격 Supabase (Management API)

- [ ] **Step 1: 지침 갱신** — `SCHEDULED_TASK.md`에 `python -m eduapp_batch.run_progress` 단계(Claude 판단 없음, 결과 JSON 해석: 정수=저장 행 수, 문자열=사유)를 추가한다. `docs/08-plan.md`의 4단계 행에 이 계획(4a)을 링크하고 "AI 추천 이전 단계: 학교 진도"로 적는다.
- [ ] **Step 2: 사용자 승인 확인 후 마이그레이션 적용** — 원격에 `20261109000001_school_progress.sql`을 Management API로 한 번 적용하고 테이블·함수·RLS 정책을 `pg_proc`/`pg_policies`로 확인한다.
- [ ] **Step 3: 귀인초 시범 실행** — `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` 설정 후 `python -m eduapp_batch.run_progress`. Expected: 귀인초에서 1~6학년 현재 학기 행이 저장됨(학년당 수십 행). `school_progress`를 학년별로 세고 `[2국01-04]` 등 몇 행을 눈으로 대조한다.
- [ ] **Step 4: 배포 확인** — `main` 병합으로 Vercel 재배포 후 Playwright로 3~4학년 자녀 계정에서 "우리 학교" 탭의 진도 구역을 확인한다(테스트 계정은 사용자가 지운다).
- [ ] **Step 5: Commit** — `git commit -m "docs: plan 4a scheduled task and roadmap"`

---

## 남은 일 · 알려진 한계
- 전국 공통 기준선(NCIC 성취기준)과 교차 검증은 계획 4b. 학교가 평가계획을 공개하지 않으면 진도 구역은 안내 문구만 보인다.
- 평가 월은 수업 월이 아니다(근사치). 학교가 평가계획을 수정해 올리면 번호가 큰 게시물이 이기지만, 삭제된 항목은 남는다.
- 단원명이 세 줄 이상으로 갈라지거나 표 형식이 다른 학교는 일부 행이 비거나 단원명이 잘릴 수 있다(`shortcut:`).
- `goeay.kr`이 아닌 학교(서울 등)는 진도가 없다.
- 첨부가 이미지 PDF/스캔이거나 배포용 암호화 hwp인 학교는 읽지 못한다.
