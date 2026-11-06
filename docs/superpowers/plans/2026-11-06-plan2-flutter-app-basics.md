# 계획 2: Flutter 앱 기본 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 학부모가 Android 앱에서 로그인하고, 자녀(학교·학년)와 관심 지역을 등록한 뒤, 관심 지역의 진행 중/예정 체험 프로그램을 학년·날짜로 걸러 보고 관심 표시할 수 있게 한다.

**Architecture:** DB 쪽은 가입 시 `profiles` 자동 생성 트리거와 목록용 함수 `my_programs()`를 마이그레이션으로 추가한다. 학교 검색에 필요한 서울·경기 초등학교 목록은 배치가 나이스 API로 `schools`에 적재한다. 앱(`app/`)은 Flutter + `supabase_flutter`이고, 모든 데이터 접근은 `EduRepository` 한 계층에 모은다. 화면 테스트는 가짜 repository로 한다.

**Tech Stack:** Flutter stable(설치 시점 최신, Dart 3), `supabase_flutter` ^2, `url_launcher` ^6, flutter_test / PostgreSQL 16 + pytest(DB·배치) / 나이스 교육정보 Open API.

**Spec:** `docs/superpowers/specs/2026-11-06-eduapp-design.md` (+ `docs/02-prd.md` F1~F6, `docs/03-user-scenarios.md` S1·S2, `docs/09-style-guide.md`)

### 전체 계획 순서 (이 문서는 2번)
1. DB 기반 + 체험 프로그램 수집 (완료)
2. **Flutter 앱: 로그인, 자녀 등록, 지역 선택, 프로그램 목록** ← 이 문서
3. 학교 선택 → 교과서 수집, 학사일정(쉬는 날 필터), 우리 학교 화면
4. AI 생성: 연결 단원, 가기 전에 읽어요, 오늘의 질문, 집 실험 + 운영자 승인
5. 알림: FCM 토큰, 신청 시작/마감, 교과서 준비 완료

## Global Constraints

- 대상은 학부모, 지역은 `서울`·`경기`만, 학년은 초등 1~6.
- 로그인 없이 사용 불가 (F1). v1 로그인은 **이메일 + 비밀번호**(Supabase Auth). 카카오 로그인은 이 계획에서 하지 않는다.
- 앱에는 Supabase **anon 키만** 넣는다. URL·anon 키는 `--dart-define-from-file=env.json`으로 주입, `app/env.json`은 커밋하지 않는다(`.gitignore`).
- 자녀는 **별명**만 저장 (실명 금지 안내 문구 표시). 별명 1~10자.
- 마감·종료된 프로그램은 보이지 않는다 → 앱은 `upcoming_programs` 기반 `my_programs()`만 읽는다.
- 시간 표시는 **KST(UTC+9) 고정**: DB의 timestamptz를 `toUtc().add(Duration(hours: 9))`로 바꿔 벽시계 시각으로 쓴다(기기 시간대 무시, 테스트 결정적).
- 문구: 해요체. 날짜 `11/8(토)`, 다른 해면 `2027/1/5(화)`. 시간 `10:00`. 학년 `초3~6`, 한 학년이면 `초4`, 1~6 또는 정보 없음은 `초등 전체`.
- 스타일: `docs/09-style-guide.md`의 색 토큰·크기·간격 그대로. 글꼴은 시스템 기본(Pretendard 번들은 하지 않음). 라이트·다크는 시스템 설정 따름.
- 하단 탭은 이 계획에서 **홈 · 체험** 2개만. `우리 학교`·`집 실험`은 계획 3·4에서 추가.
- 이 계획에서 하지 않는 것: 쉬는 날 필터(계획 3), 연결 단원·가기 전에 읽어요(계획 4), 알림(계획 5).
- **사용자 준비 (Task 1 전에 확인받는다):** 나이스 Open API 인증키를 환경 시크릿 `NEIS_API_KEY`로 등록, Supabase Auth 이메일 로그인 사용 설정 확인. 확인 전에는 시작하지 않는다.
- **실행 환경 전제:** 네트워크 Full. Flutter SDK·Android SDK는 Task 3에서 설치. 에뮬레이터는 쓸 수 없음(`/dev/kvm` 없음) → 최종 확인은 사용자 휴대폰에 APK 설치(Task 9).

## Review Focus

1. **학교 검색에 한 글자·공백·결과 없음** → 2글자 미만이면 검색하지 않고 "학교 이름을 두 글자 이상 입력해요", 결과 없으면 "검색 결과가 없어요. 서울·경기 초등학교만 찾을 수 있어요". (Task 6 `school search ignores short query and shows empty state`)
2. **관심 지역을 모두 해제** → 저장 버튼 비활성. 지역 0개로 목록이 영원히 빈 상태가 되면 안 된다. (Task 7 `save disabled when nothing selected`)
3. **목록 불러오기 실패(네트워크·서버 오류)** → 앱이 멈추지 않고 "프로그램을 불러오지 못했어요" + "다시 시도". (Task 8 `load error shows retry`)
4. **관심 표시 저장 실패** → 별이 원래 상태로 돌아가고 "관심 표시를 저장하지 못했어요" 스낵바. (Task 8 `favorite rollback on error`)
5. **시스템 글자 크기 200%** → 카드·상세에서 overflow가 나지 않는다(스타일 가이드). (Task 8·9 `no overflow at textScale 2.0`)

---

### Task 1: DB — 가입 시 프로필 생성, 목록 함수

**Files:**
- Create: `supabase/migrations/20261107000001_app_basics.sql`
- Modify: `supabase/schema.sql` (끝에 위 마이그레이션 내용을 그대로 덧붙임)
- Modify: `batch/tests/conftest.py` (적용 SQL = stub + `supabase/migrations/*.sql` 파일명 순)
- Test: `batch/tests/test_app_basics.py`

**Interfaces:**
- Produces:
  - 트리거 `on_auth_user_created` (`auth.users` after insert) → `profiles(id)` 행 생성. 함수 `handle_new_user()` security definer.
  - `my_programs(p_grade int default null, p_from date default null, p_to date default null) returns setof upcoming_programs`, `language sql stable` (security invoker → RLS 적용), `grant execute ... to authenticated`.
    - 지역: `exists (select 1 from user_regions r where r.user_id = auth.uid() and r.sido = p.sido and (r.sigungu = '' or r.sigungu = p.sigungu))`
    - 학년: `p_grade is null or (coalesce(grade_min,1) <= p_grade and coalesce(grade_max,6) >= p_grade)`
    - 날짜(기간 겹침, `p_from`·`p_to`는 함께 주거나 함께 null): `p_from is null or (coalesce(starts_on, ends_on) is null or (coalesce(starts_on, ends_on) <= p_to and coalesce(ends_on, starts_on) >= p_from))`
    - 정렬: `order by coalesce(starts_on, ends_on) nulls last, id`
  - 앱은 PostgREST `rpc('my_programs', params: {...})`로 호출.

- [ ] **Step 1: 실패하는 테스트** (`test_app_basics.py`, 기존 `db` 픽스처, `set request.jwt.claim.sub` + `set role authenticated`로 사용자 흉내)
  - `test_profile_created_on_signup`: `insert into auth.users(id)` → `profiles`에 같은 id 1행, `is_operator = false`.
  - `test_my_programs_filters_by_region`: 기관 경기/과천시, 서울/용산구 각 1개 프로그램. 사용자 지역 `('경기','과천시')` → 과천 1건. 지역 `('서울','')`(시도 전체) 추가 → 2건.
  - `test_my_programs_filters_by_grade`: 프로그램 A(3~4), B(5~6), C(null) → `p_grade=4` 결과 제목 {A, C}.
  - `test_my_programs_filters_by_dates`: `d = current_date`. A(d+1~d+2), B(d+8~d+9), C(날짜 null, apply_ends_at 내일) → `p_from=d+1, p_to=d+2` 결과 {A, C}.
  - `test_my_programs_hides_closed`: 종료일 어제인 프로그램은 지역·학년이 맞아도 결과에 없음.
  - `test_my_programs_other_user_regions_ignored`: 다른 사용자의 `user_regions`만 있으면 0건.
  - `test_schema_sql_matches_migrations`: `schema.sql` 내용 == `migrations/*.sql`을 파일명 순으로 이어 붙인 문자열.
- [ ] **Step 2: 실패 확인** — `cd batch && python -m pytest tests/test_app_basics.py -v` / FAIL (함수 없음)
- [ ] **Step 3: 마이그레이션 작성, schema.sql에 덧붙임, conftest 수정**
- [ ] **Step 4: 통과 확인** — `cd batch && python -m pytest -q` / 기존 포함 전부 PASS
- [ ] **Step 5: 운영 DB 적용** — Supabase Management API(`POST /v1/projects/{ref}/database/query`, `SUPABASE_ACCESS_TOKEN`)로 마이그레이션 실행 후 `notify pgrst, 'reload schema'`. 확인: `select proname from pg_proc where proname in ('my_programs','handle_new_user')` 2행. (운영 DB 변경이므로 실행 전 사용자 확인)
- [ ] **Step 6: Commit** — `feat(db): profile on signup, my_programs filter function`

### Task 2: 배치 — 나이스 학교 목록 적재

**Files:**
- Create: `batch/eduapp_batch/schools_list.py` (`python -m eduapp_batch.schools_list`)
- Modify: `batch/eduapp_batch/models.py` (`School` 추가), `batch/eduapp_batch/store.py` (`upsert_schools`를 `PgStore`·`RestStore` 둘 다에)
- Create: `batch/tests/fixtures/neis_school_info.json` (실제 응답 샘플, 행 3~5개로 줄임)
- Test: `batch/tests/test_schools_list.py`

**Interfaces:**
- Consumes: `RestStore`/`PgStore` 패턴, `_fetch`와 같은 재시도 방식
- Produces:
  - `@dataclass(frozen=True) class School: neis_code: str; edu_office_code: str; name: str; sido: str; sigungu: str | None; homepage_url: str | None`
  - `parse_school_info(payload: dict) -> list[School]` — `payload["schoolInfo"][1]["row"]` 사용. 매핑: `SD_SCHUL_CODE→neis_code`, `ATPT_OFCDC_SC_CODE→edu_office_code`, `SCHUL_NM→name`, `LCTN_SC_NM`(`서울특별시`→`서울`, `경기도`→`경기`, 그 외는 행 제외), `ORG_RDNMA`의 두 번째 단어→`sigungu`(예 `경기도 성남시 분당구 …`→`성남시`), `HMPG_ADRES`(빈 문자열·`http://`만 있으면 None). 결과 없음 응답(`{"RESULT":{"CODE":"INFO-200"}}`)은 `[]`.
  - `store.upsert_schools(schools: list[School]) -> int` — `on conflict (neis_code)`이고 **보낸 컬럼만 갱신**(`collect_status` 등 수집 상태를 덮지 않음).
  - CLI: 환경변수 `NEIS_API_KEY`, 교육청 `B10`(서울)·`J10`(경기), `SCHUL_KND_SC_NM=초등학교`, `pSize=1000`, `pIndex`를 결과가 1000 미만일 때까지 증가. 마지막 줄 요약 JSON `{"B10": n, "J10": m}`. 저장소 선택은 `run_programs.main()`과 같은 규칙(`SUPABASE_URL` 있으면 REST).
- [ ] **Step 1: 샘플 저장** — `curl "https://open.neis.go.kr/hub/schoolInfo?KEY=$NEIS_API_KEY&Type=json&ATPT_OFCDC_SC_CODE=J10&SCHUL_KND_SC_NM=초등학교&pIndex=1&pSize=5"` 응답을 fixture로 저장. 첫 행의 학교명·시군구를 메모.
- [ ] **Step 2: 실패하는 테스트**
  - `test_parse_school_info_maps_fields`: fixture → 5건, 첫 행이 메모 값, 모든 `sido`가 `경기`.
  - `test_parse_school_info_no_data`: `{"RESULT":{"CODE":"INFO-200","MESSAGE":"해당하는 데이터가 없습니다."}}` → `[]`.
  - `test_parse_school_info_seoul_sigungu`: 행 하나를 `LCTN_SC_NM="서울특별시"`, `ORG_RDNMA="서울특별시 용산구 이촌로 1"`로 → `sido="서울"`, `sigungu="용산구"`.
  - `test_upsert_schools_keeps_collect_status` (PgStore, `db` 픽스처): 학교 저장 → `collect_status='pending'`로 바꿈 → 이름 바꿔 다시 저장 → 이름만 바뀌고 `pending` 유지, 행 1개.
  - `test_rest_upsert_schools_on_conflict_neis_code` (MockTransport): 요청 URL에 `on_conflict=neis_code`, Prefer에 `merge-duplicates`, 본문에 `collect_status` 키 없음.
- [ ] **Step 3: 실패 확인** / **Step 4: 구현** / **Step 5: 통과 확인** — `cd batch && python -m pytest -q`
- [ ] **Step 6: 운영 적재 1회** — `cd batch && python -m eduapp_batch.schools_list` / Expected: 요약 JSON 두 값 모두 500 이상. REST로 `schools?name=ilike.*분당*` 결과 1건 이상.
- [ ] **Step 7: Commit** — `feat(batch): load seoul/gyeonggi elementary schools from NEIS`

### Task 3: Flutter 프로젝트, 테마, 표시 형식

**Files:**
- Create: `app/` (`flutter create --org kr.eduapp --project-name eduapp --platforms android app`)
- Create: `app/lib/theme.dart`, `app/lib/format.dart`
- Modify: `.gitignore` (`app/env.json`, `app/build/`, `.dart_tool/`)
- Test: `app/test/format_test.dart`, `app/test/theme_test.dart`

**Interfaces:**
- Produces:
  - `ThemeData buildTheme(Brightness b)` — Material 3, 스타일 가이드 색 매핑(`primary`, `onPrimary`, `surface`, `error`=`danger`), `EduColors extends ThemeExtension<EduColors>` 필드 `info, warning, accent, danger, textMuted, border, card`.
  - `DateTime kst(DateTime t)` — `t.toUtc().add(const Duration(hours: 9))`
  - `String fmtDate(DateTime d, DateTime today)` · `String fmtTime(DateTime d)` · `String fmtPeriod(DateTime? start, DateTime? end, DateTime today)` · `String fmtGrades(int? min, int? max)` · `String fmtApply(DateTime? startsAt, DateTime? endsAt, DateTime now)` · `bool closingSoon(DateTime? endsAt, DateTime now)` · `(DateTime, DateTime) thisWeekend(DateTime today)` (모든 DateTime은 이미 KST 벽시계 값)
- [ ] **Step 1: 도구 설치** — Flutter stable을 `git clone --depth 1 -b stable https://github.com/flutter/flutter /opt/flutter`, Android cmdline-tools + `platform-tools`, `platforms;android-35`, `build-tools;35.0.0` 설치, `flutter doctor --android-licenses` 동의. 확인: `flutter doctor` 에서 Flutter·Android toolchain ✓ (Chrome·Android Studio 없음은 무시).
- [ ] **Step 2: 프로젝트 생성**, 의존성 `flutter pub add supabase_flutter url_launcher`
- [ ] **Step 3: 실패하는 테스트** (`today = DateTime(2026, 11, 6)` 금요일)
  - `fmtDate(DateTime(2026,11,8), today) == '11/8(일)'`, `fmtDate(DateTime(2027,1,5), today) == '2027/1/5(화)'`
  - `fmtPeriod(11/7, 11/7) == '11/7(토)'`, `fmtPeriod(11/7, 12/12) == '11/7(토)~12/12(토)'`, `fmtPeriod(null, null) == '기간 미정'`, `fmtPeriod(null, 11/20) == '~11/20(금)'`
  - `fmtGrades(3,6) == '초3~6'`, `fmtGrades(4,4) == '초4'`, `fmtGrades(1,6) == '초등 전체'`, `fmtGrades(null,null) == '초등 전체'`
  - `fmtApply(null, 11/26 23:59, now) == '신청 마감 11/26(목) 23:59'`; `fmtApply(11/10 10:00, 11/20 18:00, now) == '신청 11/10(화) 10:00 시작'`; 시작이 지났으면 `'신청 중 · 11/20(금) 18:00 마감'`
  - `closingSoon`: 마감 72시간 이내·미래 → true, 4일 뒤 → false, null → false
  - `thisWeekend(금 11/6) == (11/7, 11/8)`, `thisWeekend(토 11/7) == (11/7, 11/8)`, `thisWeekend(일 11/8) == (11/8, 11/8)`
  - `kst(DateTime.utc(2026,11,26,14,59))`의 `day == 26 && hour == 23 && minute == 59`
  - `theme_test`: 라이트 `colorScheme.primary == Color(0xFF2F6B4F)`, 다크 `Color(0xFF7FC4A0)`, `extension<EduColors>()!.warning == Color(0xFFB7791F)`(라이트)
- [ ] **Step 4: 실패 확인** — `cd app && flutter test` / FAIL
- [ ] **Step 5: 구현** / **Step 6: 통과 확인** — `cd app && flutter test && flutter analyze` / 오류 0
- [ ] **Step 7: Commit** — `feat(app): flutter project, theme, korean display formats`

### Task 4: 데이터 계층 (repository)

**Files:**
- Create: `app/lib/data/models.dart`, `app/lib/data/repository.dart`, `app/lib/data/supabase_repository.dart`
- Create: `app/test/fake_repository.dart` (이후 화면 테스트 공용)
- Test: `app/test/models_test.dart`

**Interfaces:**
- Produces:
  - `class School { int id; String name; String sido; String? sigungu; }`
  - `class Child { int id; String nickname; int grade; School school; }` — `Child.fromJson`은 `select('id,nickname,grade,school:schools(id,name,sido,sigungu)')` 결과를 받음
  - `class Region { String sido; String sigungu; }` (`sigungu == ''`이면 시도 전체), `==`/`hashCode` 구현
  - `class ProgramItem { int id; String title; String institutionName; String url; String? description; String? fee; int? gradeMin; int? gradeMax; DateTime? startsOn; DateTime? endsOn; DateTime? applyStartsAt; DateTime? applyEndsAt; }` — `fromJson`은 `my_programs` 행, timestamptz는 `kst()` 적용
  - ```dart
    abstract class EduRepository {
      bool get signedIn;
      Future<void> signIn(String email, String password);
      Future<void> signUp(String email, String password);
      Future<void> signOut();
      Future<List<Child>> children();
      Future<void> saveChild({int? id, required String nickname, required int schoolId, required int grade});
      Future<void> deleteChild(int id);
      Future<List<School>> searchSchools(String query);   // name ilike %query%, limit 20, 이름순
      Future<Set<Region>> regions();
      Future<void> saveRegions(Set<Region> regions);       // 전부 지우고 다시 넣음
      Future<List<ProgramItem>> programs({int? grade, DateTime? from, DateTime? to});  // rpc my_programs
      Future<Set<int>> favoriteIds();
      Future<void> setFavorite(int programId, bool on);
    }
    ```
  - `FakeRepository implements EduRepository` — 메모리 목록, 호출 기록(`calls`), `Object? failWith` 설정 시 다음 호출이 그 예외를 던짐.
- [ ] **Step 1: 실패하는 테스트** (`models_test.dart`)
  - `ProgramItem.fromJson`: `apply_ends_at: '2026-11-26T14:59:00+00:00'` → `applyEndsAt` 11/26 23:59, `starts_on: '2026-11-07'` → `DateTime(2026,11,7)`, null 필드는 null, `institution_name` → `institutionName`.
  - `Child.fromJson`: 중첩 `school` → `child.school.name`.
  - `Region('서울','') == Region('서울','')`, Set 중복 제거.
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** (`SupabaseRepository`는 `Supabase.instance.client` 사용, 얇게) / **Step 4: 통과 확인** — `flutter test && flutter analyze`
- [ ] **Step 5: Commit** — `feat(app): repository layer and models`

### Task 5: 로그인과 앱 골격

**Files:**
- Create: `app/lib/main.dart`(교체), `app/lib/app.dart`, `app/lib/screens/login_screen.dart`, `app/lib/screens/home_shell.dart`
- Test: `app/test/login_test.dart`, `app/test/app_flow_test.dart`

**Interfaces:**
- Consumes: `EduRepository`, `buildTheme`
- Produces:
  - `main()`: `Supabase.initialize(url: String.fromEnvironment('SUPABASE_URL'), anonKey: String.fromEnvironment('SUPABASE_ANON_KEY'))` → `runApp(EduApp(repo: SupabaseRepository()))`
  - `EduApp({required EduRepository repo})` — 로그인 안 됨 → `LoginScreen`; 로그인 됨 → 자녀 0명이면 `ChildEditScreen`(Task 6), 지역 0개면 `RegionScreen`(Task 7), 아니면 `HomeShell`.
  - `HomeShell` — 하단 탭 `홈`·`체험`. 홈 탭(`HomeTab`): 자녀 목록(별명 · 학교 · N학년, 누르면 수정), "자녀 추가", 관심 지역 요약 + "지역 바꾸기", "로그아웃".
  - `LoginScreen` — 이메일·비밀번호, "로그인"(주요 버튼), "처음이에요 · 가입하기"(보조). 가입 성공 시 "가입 확인 메일을 보냈어요. 메일의 링크를 누른 뒤 로그인해요."
- [ ] **Step 1: 실패하는 테스트**
  - `login_test`: 이메일 형식 아님 → "이메일 주소를 확인해요", 비밀번호 6자 미만 → "비밀번호는 6자 이상이에요", repo 호출 없음. 올바른 입력 → `signIn` 1회. `failWith` 설정 → "로그인하지 못했어요. 이메일과 비밀번호를 확인해요."
  - `app_flow_test`: 로그인 안 됨 → 로그인 화면; 로그인·자녀 0 → 자녀 추가 화면; 자녀 1·지역 0 → 지역 화면; 둘 다 있음 → 하단 탭 `홈`·`체험` 보임.
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인** — `flutter test && flutter analyze`
- [ ] **Step 5: Commit** — `feat(app): login and app shell`

### Task 6: 자녀 등록·수정·삭제, 학교 검색

**Files:**
- Create: `app/lib/screens/child_edit_screen.dart`
- Test: `app/test/child_edit_test.dart`

**Interfaces:**
- Consumes: `EduRepository.saveChild/deleteChild/searchSchools`
- Produces: `ChildEditScreen({required EduRepository repo, Child? child})` — 저장·삭제 후 `Navigator.pop(true)`.
  - 별명 입력 + 안내 "실명 대신 별명을 써 주세요". 학교 검색 입력(300ms 디바운스) → 결과 목록 "학교명 · 시군구" → 선택. 학년 1~6 선택(칩). "저장"은 별명·학교·학년이 모두 있을 때만 활성. 수정 모드에만 "삭제"(확인 대화상자 "○○ 정보를 지울까요?").
- [ ] **Step 1: 실패하는 테스트**
  - `school search ignores short query and shows empty state`: "분" 입력 → `searchSchools` 호출 없음, "학교 이름을 두 글자 이상 입력해요". 공백 "  " → 호출 없음. "없는학교" → 결과 0 → "검색 결과가 없어요. 서울·경기 초등학교만 찾을 수 있어요".
  - `save enabled only when complete`: 별명만 → 저장 비활성; 별명 11자 → "별명은 10자까지예요"; 별명·학교·학년 → 저장 → `saveChild(nickname:'서준', schoolId:.., grade:4)`.
  - `edit and delete`: 기존 자녀로 열면 값 채워짐, 삭제 → 확인 → `deleteChild(id)`.
  - `save error shows message`: `failWith` → "저장하지 못했어요. 다시 시도해 주세요", 화면 유지.
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** — `feat(app): child registration with school search`

### Task 7: 관심 지역 선택

**Files:**
- Create: `app/lib/regions.dart` (시군구 상수), `app/lib/screens/region_screen.dart`
- Test: `app/test/region_test.dart`

**Interfaces:**
- Produces:
  - `const Map<String, List<String>> kSigungu` — `'서울'`: 서울특별시 25개 자치구, `'경기'`: 경기도 31개 시·군(시 단위, 예 `성남시`, `과천시`; 일반구로 나누지 않음 — 기관·학교 `sigungu`와 같은 규칙).
  - `RegionScreen({required EduRepository repo})` — 시도 탭(서울/경기), 각 시도 "전체" 칩(`sigungu ''`, 켜면 그 시도의 개별 칩 해제) + 시군구 칩 복수 선택. "저장" → `saveRegions` → pop(true).
- [ ] **Step 1: 실패하는 테스트**
  - `sigungu lists`: `kSigungu['서울']!.length == 25`, `kSigungu['경기']!.length == 31`, `과천시`·`성남시`·`용산구` 포함.
  - `save disabled when nothing selected`: 처음(지역 0) 저장 비활성; 하나 켜고 끄면 다시 비활성.
  - `pick multiple and save`: 성남시·과천시(경기), 용산구(서울) → `saveRegions({Region('경기','성남시'), Region('경기','과천시'), Region('서울','용산구')})`.
  - `whole sido replaces individual`: 용산구 선택 후 서울 "전체" → 저장 값 `{Region('서울','')}`.
  - 기존 지역이 있으면 그 칩이 켜진 상태로 열림.
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** — `feat(app): region picker`

### Task 8: 체험 목록, 필터, 관심 표시

**Files:**
- Create: `app/lib/screens/programs_tab.dart`, `app/lib/widgets/program_card.dart`, `app/lib/widgets/edu_chip.dart`
- Test: `app/test/programs_tab_test.dart`

**Interfaces:**
- Consumes: `programs`, `favoriteIds`, `setFavorite`, `children`, 형식 함수
- Produces:
  - `ProgramsTab({required EduRepository repo, DateTime Function()? now})` — `now` 기본 `() => kst(DateTime.now())`.
  - 필터 줄: 자녀 칩(자녀별 "서준 4학년" + "모든 학년"; 기본 = 첫 자녀), 날짜 칩(`전체`·`이번 주말`·`날짜 선택`(showDateRangePicker); 기본 `전체`), `관심만` 토글(클라이언트에서 `favoriteIds`로 거름).
  - `ProgramCard` — 스타일 가이드 순서: 기관명(caption) → 제목(heading) → `fmtPeriod · fmtGrades`(label) → `closingSoon`이면 danger 칩 "마감 임박" → 오른쪽 위 ☆/★(accent, 터치 48×48, semanticLabel "관심 표시"/"관심 해제"). 카드 누르면 상세(Task 9).
  - 빈 화면: "관심 지역에 진행 중인 프로그램이 없어요" + 보조 버튼 "지역 바꾸기"(RegionScreen). `관심만`이 켜져 비면 "관심 표시한 프로그램이 없어요".
- [ ] **Step 1: 실패하는 테스트** (`now = DateTime(2026,11,6,20)`)
  - `default filter uses first child grade`: 자녀 서준(4) → `programs(grade:4, from:null, to:null)` 호출.
  - `weekend filter`: "이번 주말" → `programs(grade:4, from:11/7, to:11/8)`. "모든 학년" → `grade:null`.
  - `card shows formatted fields`: 프로그램(과천과학관, 11/7~12/12, 3~6, 마감 11/8 18:00) → "국립과천과학관", "11/7(토)~12/12(토) · 초3~6", "마감 임박" 보임.
  - `favorite toggle`: ☆ 누름 → `setFavorite(id, true)`, ★로 바뀜. `관심만` 켜면 그 카드만.
  - `favorite rollback on error`: `failWith` 후 ☆ 누름 → ☆로 돌아오고 "관심 표시를 저장하지 못했어요".
  - `load error shows retry`: `failWith` → "프로그램을 불러오지 못했어요" + "다시 시도" → 누르면 재호출, 목록 표시.
  - `empty state`: 0건 → 빈 화면 문구와 "지역 바꾸기".
  - `no overflow at textScale 2.0`: `MediaQuery(textScaler: TextScaler.linear(2.0))`, 긴 제목(40자) 카드 → `tester.takeException()` null.
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** — `feat(app): program list with grade/date filters and favorites`

### Task 9: 체험 상세

**Files:**
- Create: `app/lib/screens/program_detail_screen.dart`
- Test: `app/test/program_detail_test.dart`

**Interfaces:**
- Consumes: `ProgramItem`, `setFavorite`, 형식 함수, `url_launcher`의 `launchUrl(Uri, mode: LaunchMode.externalApplication)`
- Produces: `ProgramDetailScreen({required EduRepository repo, required ProgramItem program, required bool favorite, Future<bool> Function(Uri)? open})` — `open` 기본은 `launchUrl`(테스트에서 바꿔 끼움). pop할 때 바뀐 관심 상태를 돌려줌.
  - 항목(빈 값은 줄 생략): 기관, 기간(`fmtPeriod`), 대상(`fmtGrades`), 신청(`fmtApply`; 시작 시각 없으면 마감만), 비용(`fee`, 없으면 "기관 페이지에서 확인해요"), 소개(`description`). 앱바 ☆. 주요 버튼 1개 "기관 페이지에서 신청".
- [ ] **Step 1: 실패하는 테스트**
  - `shows fields`: 시작 시각 null, 마감 11/26 23:59 → "신청 마감 11/26(목) 23:59", "신청 … 시작" 문구 없음. fee null → "기관 페이지에서 확인해요".
  - `apply button opens institution page`: 누르면 `open(Uri.parse(program.url))` 1회.
  - `open failure`: `open`이 false → "기관 페이지를 열지 못했어요".
  - `no overflow at textScale 2.0`: 긴 description(500자) → 예외 없음(스크롤).
- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** — `feat(app): program detail`

### Task 10: APK 빌드와 실기기 확인

**Files:**
- Create: `app/README.md` (실행·빌드 명령, `env.json` 형식 `{"SUPABASE_URL": "...", "SUPABASE_ANON_KEY": "..."}`)
- Modify: `docs/08-plan.md` (2단계 상세 계획 링크, 학교 목록 적재를 2단계로 옮긴 것 반영, "사용자가 해야 할 일"에 "2단계 전: 나이스 Open API 인증키" 추가)

**Interfaces:**
- Consumes: 전체 앱, 운영 Supabase(Task 1·2 적용 완료)

- [ ] **Step 1: anon 키 준비** — Management API `GET /v1/projects/{ref}/api-keys`(`SUPABASE_ACCESS_TOKEN`)로 anon 키를 받아 `app/env.json` 작성. 확인: `curl $SUPABASE_URL/rest/v1/institutions?select=id -H "apikey: <anon>"` 200.
- [ ] **Step 2: 빌드** — `cd app && flutter build apk --release --dart-define-from-file=env.json` / Expected: `build/app/outputs/flutter-apk/app-release.apk` 생성 (디버그 서명 그대로, 시범 배포용).
- [ ] **Step 3: APK 전달** — 사용자에게 파일로 보낸다(SendUserFile). 저장소에는 커밋하지 않는다.
- [ ] **Step 4: 사용자 실기기 확인 (S1·S2, 알림 제외)** — 체크리스트를 사용자에게 주고 결과를 받는다: 가입·메일 확인·로그인 / 자녀 2명 추가(학교 검색 "분당") / 지역 성남시·과천시·용산구 / 체험 탭에 박물관 프로그램 보임 / 이번 주말 필터 / ☆ 관심 표시 후 앱 재시작해도 유지 / 상세 → "기관 페이지에서 신청"이 브라우저로 열림 / 글자 크기 최대에서 잘림 없음. 실패 항목은 고친 뒤 이 단계를 반복.
- [ ] **Step 5: Commit** — `docs(app): build instructions, roadmap update`
