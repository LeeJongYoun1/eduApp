-- eduApp v1 전체 스키마 (Supabase Postgres)
-- 스펙: docs/superpowers/specs/2026-11-06-eduapp-design.md
-- 앱(anon/authenticated)은 참조 데이터 읽기 + 본인 데이터 읽기/쓰기만.
-- 수집·AI 결과 쓰기는 배치(DB 직접 연결, RLS 우회)만.

-- ───────── 타입 ─────────
create type sido as enum ('서울', '경기');
create type collect_status as enum ('not_requested', 'pending', 'done', 'failed', 'not_found');
create type info_confidence as enum ('confirmed', 'unverified');
create type info_source as enum ('auto', 'parent');
create type review_status as enum ('pending', 'approved', 'rejected');
create type notification_kind as enum ('apply_open_1d', 'apply_open_1h', 'deadline_soon', 'textbook_ready');

-- ───────── 사용자 ─────────
create table profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text,
  is_operator boolean not null default false,
  created_at timestamptz not null default now()
);

create table schools (
  id bigint generated always as identity primary key,
  neis_code text not null unique,            -- 나이스 표준학교코드
  edu_office_code text not null,             -- 시도교육청코드 (나이스 API 호출용)
  name text not null,
  sido sido not null,
  sigungu text,
  homepage_url text,
  collect_status collect_status not null default 'not_requested',
  collect_requested_at timestamptz,
  last_collected_at timestamptz
);
create index schools_name_idx on schools (name);

create table children (
  id bigint generated always as identity primary key,
  parent_id uuid not null references profiles on delete cascade,
  nickname text not null,
  school_id bigint not null references schools,
  grade int not null check (grade between 1 and 6),
  created_at timestamptz not null default now()
);
create index children_parent_idx on children (parent_id);

create table user_regions (
  user_id uuid not null references profiles on delete cascade,
  sido sido not null,
  sigungu text not null default '',          -- '' = 시도 전체
  primary key (user_id, sido, sigungu)
);

create table device_tokens (
  token text primary key,                    -- FCM 토큰
  user_id uuid not null references profiles on delete cascade,
  platform text not null check (platform in ('android', 'ios')),
  updated_at timestamptz not null default now()
);

-- ───────── 교육과정 · 교과서 ─────────
create table achievement_standards (
  code text primary key,                     -- 예: '[4과05-01]'
  subject text not null,
  grade_min int not null check (grade_min between 1 and 6),
  grade_max int not null check (grade_max between grade_min and 6),
  content text not null,
  seq int not null                           -- 학년군·교과 안의 순서 (진도 추정용)
);

create table textbooks (
  id bigint generated always as identity primary key,
  curriculum text not null default '2022',
  subject text not null,
  grade int not null check (grade between 1 and 6),
  semester int check (semester in (1, 2)),
  publisher text not null,
  title text not null,
  unique (curriculum, subject, grade, semester, publisher)
);

create table textbook_units (
  id bigint generated always as identity primary key,
  textbook_id bigint not null references textbooks on delete cascade,
  seq int not null,
  title text not null,
  unique (textbook_id, seq)
);

create table unit_standards (
  unit_id bigint not null references textbook_units on delete cascade,
  standard_code text not null references achievement_standards,
  primary key (unit_id, standard_code)
);

create table school_textbooks (
  school_id bigint not null references schools on delete cascade,
  grade int not null check (grade between 1 and 6),
  subject text not null,
  textbook_id bigint references textbooks,   -- null = 아직 모름
  confidence info_confidence not null default 'unverified',
  source info_source not null default 'auto',
  source_url text,                           -- 학교 공지 URL
  updated_at timestamptz not null default now(),
  primary key (school_id, grade, subject)
);

create table school_calendar (
  school_id bigint not null references schools on delete cascade,
  day date not null,
  event_name text not null,
  is_holiday boolean not null default false, -- 방학·재량휴업일 등
  primary key (school_id, day, event_name)
);

-- ───────── 체험 프로그램 ─────────
create table institutions (
  id bigint generated always as identity primary key,
  key text not null unique,                  -- 수집기 키
  name text not null,
  sido sido not null,
  sigungu text,
  homepage_url text not null
);

create table programs (
  id bigint generated always as identity primary key,
  institution_id bigint not null references institutions on delete cascade,
  source_id text not null,
  title text not null,
  description text,
  url text not null,
  grade_min int check (grade_min between 1 and 6),
  grade_max int check (grade_max between 1 and 6 and grade_max >= grade_min),
  starts_on date,
  ends_on date,
  apply_starts_at timestamptz,               -- 기관이 공개 안 하면 null
  apply_ends_at timestamptz,
  fee text,
  collected_at timestamptz not null default now(),
  unique (institution_id, source_id)
);

create table collect_runs (
  id bigint generated always as identity primary key,
  target text not null,                      -- 기관 key 또는 'school:<neis_code>'
  started_at timestamptz not null default now(),
  ok boolean not null,
  item_count int,
  error text
);

-- ───────── 추천 (AI 배치 생성) ─────────
create table books (
  id bigint generated always as identity primary key,
  isbn text unique,
  title text not null,
  author text,
  publisher text,
  grade_min int check (grade_min between 1 and 6),
  grade_max int check (grade_max between 1 and 6 and grade_max >= grade_min)
);

create table program_standards (
  program_id bigint not null references programs on delete cascade,
  standard_code text not null references achievement_standards,
  reason text not null,
  primary key (program_id, standard_code)
);

create table book_standards (
  book_id bigint not null references books on delete cascade,
  standard_code text not null references achievement_standards,
  reason text not null,
  primary key (book_id, standard_code)
);

create table program_prereads (
  program_id bigint not null references programs on delete cascade,
  book_id bigint not null references books on delete cascade,
  reason text not null,                      -- "가기 전에 읽어요" 이유 1~2문장
  primary key (program_id, book_id)
);

create table daily_questions (
  id bigint generated always as identity primary key,
  standard_code text not null references achievement_standards,
  question text not null,
  hint text not null
);

create table home_activities (
  id bigint generated always as identity primary key,
  standard_code text not null references achievement_standards,
  title text not null,
  materials text[] not null,
  steps text[] not null,
  safety_note text,
  status review_status not null default 'pending',
  reviewed_by uuid references profiles,
  reviewed_at timestamptz
);

-- ───────── 관심 · 알림 ─────────
create table favorites (
  user_id uuid not null references profiles on delete cascade,
  program_id bigint not null references programs on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, program_id)
);

create table notifications (
  id bigint generated always as identity primary key,
  user_id uuid not null references profiles on delete cascade,
  kind notification_kind not null,
  program_id bigint references programs on delete cascade,
  school_id bigint references schools on delete cascade,
  send_at timestamptz not null,
  sent_at timestamptz,
  unique nulls not distinct (user_id, kind, program_id, school_id)
);
create index notifications_due_idx on notifications (send_at) where sent_at is null;

-- ───────── 뷰 ─────────
-- 종료됐거나 접수가 마감된 프로그램은 앱에 보이지 않는다.
create view upcoming_programs with (security_invoker = true) as
select p.*, i.name as institution_name, i.sido, i.sigungu
from programs p join institutions i on i.id = p.institution_id
where (coalesce(p.ends_on, p.starts_on) >= current_date
       or (p.ends_on is null and p.starts_on is null and p.apply_ends_at >= now()))
  and (p.apply_ends_at is null or p.apply_ends_at >= now());  -- 접수 마감도 숨김

-- ───────── 트리거: 자녀 등록 시 학교 수집 요청 ─────────
create function request_school_collect() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  update schools set collect_status = 'pending', collect_requested_at = now()
  where id = new.school_id and collect_status = 'not_requested';
  return new;
end $$;
create trigger children_request_collect after insert or update of school_id on children
for each row execute function request_school_collect();

-- ───────── 함수: 운영자 여부, 학부모의 교과서 수정 ─────────
create function is_operator() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select is_operator from profiles where id = auth.uid()), false)
$$;

-- 우리 아이 학교·학년의 교과서만 고칠 수 있다.
create function correct_school_textbook(p_child_id bigint, p_subject text, p_textbook_id bigint)
returns void language plpgsql security definer set search_path = public as $$
declare c children;
begin
  select * into c from children where id = p_child_id and parent_id = auth.uid();
  if not found then raise exception 'not your child'; end if;
  if p_textbook_id is not null and not exists (
    select 1 from textbooks where id = p_textbook_id and subject = p_subject and grade = c.grade) then
    raise exception 'textbook does not match subject and grade';
  end if;
  insert into school_textbooks (school_id, grade, subject, textbook_id, confidence, source, updated_at)
  values (c.school_id, c.grade, p_subject, p_textbook_id, 'confirmed', 'parent', now())
  on conflict (school_id, grade, subject) do update
    set textbook_id = excluded.textbook_id, confidence = 'confirmed', source = 'parent', updated_at = now();
end $$;

-- ───────── RLS ─────────
alter table profiles enable row level security;
alter table children enable row level security;
alter table user_regions enable row level security;
alter table device_tokens enable row level security;
alter table favorites enable row level security;
alter table notifications enable row level security;
alter table home_activities enable row level security;
alter table collect_runs enable row level security;  -- 정책 없음 = 앱 접근 불가

-- 참조 데이터: 누구나 읽기
do $$ declare t text; begin
  foreach t in array array['schools','achievement_standards','textbooks','textbook_units','unit_standards',
    'school_textbooks','school_calendar','institutions','programs','books','program_standards',
    'book_standards','program_prereads','daily_questions'] loop
    execute format('alter table %I enable row level security', t);
    execute format('create policy read_all on %I for select to anon, authenticated using (true)', t);
  end loop;
end $$;

-- 본인 데이터
create policy own on profiles for all to authenticated using (id = auth.uid()) with check (id = auth.uid() and not is_operator);
create policy own on children for all to authenticated using (parent_id = auth.uid()) with check (parent_id = auth.uid());
create policy own on user_regions for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own on device_tokens for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own on favorites for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_read on notifications for select to authenticated using (user_id = auth.uid());

-- 집 실험: 승인된 것만 공개, 운영자는 전체 보기·승인
create policy approved_read on home_activities for select to anon, authenticated using (status = 'approved' or is_operator());
create policy operator_review on home_activities for update to authenticated using (is_operator()) with check (is_operator());

grant usage on schema public to anon, authenticated;
grant select on all tables in schema public to anon, authenticated;
grant insert, update, delete on profiles, children, user_regions, device_tokens, favorites to authenticated;
grant update on home_activities to authenticated;
grant usage on all sequences in schema public to authenticated;
grant execute on function correct_school_textbook(bigint, text, bigint) to authenticated;
