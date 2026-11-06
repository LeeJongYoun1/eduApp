
-- ───────── 계획 2: 앱 기본 ─────────
-- 가입하면 profiles 행을 만든다 (children 등이 profiles를 참조).
create function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id) values (new.id) on conflict (id) do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
for each row execute function handle_new_user();

-- 내 관심 지역의 진행 중/예정 프로그램. p_from·p_to는 함께 주거나 함께 null.
create function my_programs(p_grade int default null, p_from date default null, p_to date default null)
returns setof upcoming_programs language sql stable set search_path = public as $$
  select p.* from upcoming_programs p
  where exists (select 1 from user_regions r where r.user_id = auth.uid() and r.sido = p.sido
                  and (r.sigungu = '' or r.sigungu = p.sigungu))
    and (p_grade is null or (coalesce(p.grade_min, 1) <= p_grade and coalesce(p.grade_max, 6) >= p_grade))
    and (p_from is null or coalesce(p.starts_on, p.ends_on) is null
         or (coalesce(p.starts_on, p.ends_on) <= p_to and coalesce(p.ends_on, p.starts_on) >= p_from))
  order by coalesce(p.starts_on, p.ends_on) nulls last, p.id
$$;
grant execute on function my_programs(int, date, date) to authenticated;
