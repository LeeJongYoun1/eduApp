-- ───────── 계획 3: 학교 교과서 ─────────
-- semester가 null인 행도 (과목, 학년, 출판사)당 하나만 있게 한다.
alter table textbooks drop constraint textbooks_curriculum_subject_grade_semester_publisher_key;
alter table textbooks add unique nulls not distinct (curriculum, subject, grade, semester, publisher);

-- 내부용: 과목·학년·출판사를 검사하고 교과서 행을 (없으면) 만들어 id를 돌려준다.
create function ensure_textbook(p_subject text, p_grade int, p_publisher text)
returns bigint language plpgsql security definer set search_path = public as $$
declare pub text := btrim(p_publisher); tid bigint;
begin
  if p_subject is null or p_subject not in ('수학', '사회', '과학', '영어') then raise exception 'bad subject'; end if;
  if p_grade is null or p_grade not between 3 and 6 then raise exception 'bad grade'; end if;
  if pub is null or char_length(pub) not between 1 and 20 then raise exception 'bad publisher'; end if;
  insert into textbooks (curriculum, subject, grade, semester, publisher, title)
  values ('2022', p_subject, p_grade, null, pub, p_subject || ' ' || p_grade || '학년')
  on conflict (curriculum, subject, grade, semester, publisher) do nothing;
  select id into tid from textbooks
  where curriculum = '2022' and subject = p_subject and grade = p_grade and semester is null and publisher = pub;
  return tid;
end $$;
revoke execute on function ensure_textbook(text, int, text) from public, anon, authenticated;
grant execute on function ensure_textbook(text, int, text) to service_role;

-- 배치용: 학교 공지에서 찾은 출판사를 저장. 학부모가 고친 값(parent)은 덮어쓰지 않는다.
create function apply_school_textbook(p_school_id bigint, p_grade int, p_subject text, p_publisher text, p_source_url text)
returns void language plpgsql security definer set search_path = public as $$
declare tid bigint := ensure_textbook(p_subject, p_grade, p_publisher);
begin
  insert into school_textbooks (school_id, grade, subject, textbook_id, confidence, source, source_url, updated_at)
  values (p_school_id, p_grade, p_subject, tid, 'confirmed', 'auto', p_source_url, now())
  on conflict (school_id, grade, subject) do update
    set textbook_id = excluded.textbook_id, confidence = 'confirmed', source = 'auto',
        source_url = excluded.source_url, updated_at = now()
    where school_textbooks.source <> 'parent';
end $$;
revoke execute on function apply_school_textbook(bigint, int, text, text, text) from public, anon, authenticated;
grant execute on function apply_school_textbook(bigint, int, text, text, text) to service_role;

-- 학부모용: 우리 아이 학교·학년의 출판사를 직접 고친다.
create function correct_school_publisher(p_child_id bigint, p_subject text, p_publisher text)
returns void language plpgsql security definer set search_path = public as $$
declare c children; tid bigint;
begin
  select * into c from children where id = p_child_id and parent_id = auth.uid();
  if not found then raise exception 'not your child'; end if;
  tid := ensure_textbook(p_subject, c.grade, p_publisher);
  insert into school_textbooks (school_id, grade, subject, textbook_id, confidence, source, updated_at)
  values (c.school_id, c.grade, p_subject, tid, 'confirmed', 'parent', now())
  on conflict (school_id, grade, subject) do update
    set textbook_id = excluded.textbook_id, confidence = 'confirmed', source = 'parent', updated_at = now();
end $$;
revoke execute on function correct_school_publisher(bigint, text, text) from public, anon;
grant execute on function correct_school_publisher(bigint, text, text) to authenticated;

-- 학부모용: 우리 아이 학년의 네 과목 출판사. 학교 값이 없으면 전체 학교(배치 수집분) 최다 출판사를 추정으로 보여준다.
create function child_textbooks(p_child_id bigint)
returns table(subject text, publisher text, confidence info_confidence, source info_source, source_url text, is_guess boolean)
language plpgsql stable security definer set search_path = public as $$
#variable_conflict use_column
declare c children;
begin
  select * into c from children where id = p_child_id and parent_id = auth.uid();
  if not found then raise exception 'not your child'; end if;
  if c.grade < 3 then return; end if;
  return query
  select s.subject, coalesce(t.publisher, g.publisher),
         case when st.textbook_id is not null then st.confidence else 'unverified'::info_confidence end,
         case when st.textbook_id is not null then st.source else null end,
         case when st.textbook_id is not null then st.source_url else null end,
         st.textbook_id is null and g.publisher is not null
  from unnest(array['수학', '사회', '과학', '영어']) with ordinality as s(subject, ord)
  left join school_textbooks st on st.school_id = c.school_id and st.grade = c.grade and st.subject = s.subject
  left join textbooks t on t.id = st.textbook_id
  left join lateral (
    select mode() within group (order by t2.publisher) as publisher
    from school_textbooks st2 join textbooks t2 on t2.id = st2.textbook_id
    where st2.grade = c.grade and st2.subject = s.subject and st2.source = 'auto'  -- 학부모 입력은 다른 학교의 추정에 쓰지 않는다
  ) g on true
  order by s.ord;
end $$;
revoke execute on function child_textbooks(bigint) from public, anon;
grant execute on function child_textbooks(bigint) to authenticated;
