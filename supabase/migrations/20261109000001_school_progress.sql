
-- ───────── 계획 4a: 학교 평가계획 기반 예상 진도 ─────────
-- 학교가 공개한 학년·학기별 학생평가계획에서 읽은 과목·성취기준·단원명·평가 월. 평가 월은 수업 월이 아니다(근사치).
-- standard_code는 achievement_standards와 아직 연결하지 않는다(그 테이블은 계획 4b에서 적재).
create table school_progress (
  school_id bigint not null references schools on delete cascade,
  school_year int not null,
  grade int not null check (grade between 1 and 6),
  semester int not null check (semester in (1, 2)),
  subject text not null,
  standard_code text not null,
  unit_title text not null,
  month int not null check (month between 1 and 12),
  source_url text,
  updated_at timestamptz not null default now(),
  primary key (school_id, school_year, grade, semester, subject, standard_code)
);
alter table school_progress enable row level security;
create policy read_all on school_progress for select to anon, authenticated using (true);
grant select on school_progress to anon, authenticated;

alter table schools add column progress_collected_at timestamptz;

-- 배치용(service_role): 한 행 저장. 같은 키면 갱신.
create function apply_school_progress(p_school_id bigint, p_school_year int, p_grade int, p_semester int,
  p_subject text, p_standard_code text, p_unit_title text, p_month int, p_source_url text)
returns void language plpgsql security definer set search_path = public as $$
declare subj text := btrim(coalesce(p_subject, '')); unit text := btrim(coalesce(p_unit_title, ''));
begin
  if char_length(subj) not between 1 and 60 or char_length(unit) not between 1 and 60 then
    raise exception 'bad subject or unit';
  end if;
  if p_standard_code is null or p_standard_code !~ '^\[\d[가-힣]+\d{2}-\d{2}\]$' then
    raise exception 'bad standard code';
  end if;
  insert into school_progress (school_id, school_year, grade, semester, subject, standard_code, unit_title, month, source_url, updated_at)
  values (p_school_id, p_school_year, p_grade, p_semester, subj, p_standard_code, unit, p_month, p_source_url, now())
  on conflict (school_id, school_year, grade, semester, subject, standard_code) do update
    set unit_title = excluded.unit_title, month = excluded.month, source_url = excluded.source_url, updated_at = now();
end $$;
revoke execute on function apply_school_progress(bigint, int, int, int, text, text, text, int, text) from public, anon, authenticated;
grant execute on function apply_school_progress(bigint, int, int, int, text, text, text, int, text) to service_role;

-- 학부모용: 우리 아이 학교·학년의 그 학년도·학기 진도(평가 월 순).
create function child_progress(p_child_id bigint, p_school_year int, p_semester int)
returns table(subject text, standard_code text, unit_title text, month int)
language plpgsql stable security definer set search_path = public as $$
#variable_conflict use_column
declare c children;
begin
  select * into c from children where id = p_child_id and parent_id = auth.uid();
  if not found then raise exception 'not your child'; end if;
  return query
    select sp.subject, sp.standard_code, sp.unit_title, sp.month from school_progress sp
    where sp.school_id = c.school_id and sp.grade = c.grade
      and sp.school_year = p_school_year and sp.semester = p_semester
    order by sp.month, sp.subject, sp.standard_code;
end $$;
revoke execute on function child_progress(bigint, int, int) from public, anon;
grant execute on function child_progress(bigint, int, int) to authenticated;
