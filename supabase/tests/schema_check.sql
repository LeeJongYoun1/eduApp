-- schema.sql 자체 검증: psql -v ON_ERROR_STOP=1 로 실행, 실패 시 예외
\set ON_ERROR_STOP 1
insert into auth.users values ('00000000-0000-0000-0000-00000000000a'), ('00000000-0000-0000-0000-00000000000b');
insert into profiles (id) values ('00000000-0000-0000-0000-00000000000a'), ('00000000-0000-0000-0000-00000000000b');
insert into schools (neis_code, edu_office_code, name, sido) values ('7010001', 'B10', '테스트초', '서울');
insert into institutions (key, name, sido, homepage_url) values ('t', '테스트관', '경기', 'https://x');
insert into programs (institution_id, source_id, title, url, ends_on) values
  (1, 'old', '지난것', 'https://x/1', current_date - 1),
  (1, 'new', '예정', 'https://x/2', current_date + 1);
insert into achievement_standards values ('[4과05-01]', '과학', 3, 4, '지층', 1);
insert into home_activities (standard_code, title, materials, steps) values
  ('[4과05-01]', '대기', '{a}', '{b}');
insert into home_activities (standard_code, title, materials, steps, status) values
  ('[4과05-01]', '승인', '{a}', '{b}', 'approved');

do $$ begin
  -- 마감된 프로그램 숨김
  assert (select count(*) from upcoming_programs) = 1 and (select title from upcoming_programs) = '예정', 'upcoming view';
end $$;

-- 학부모 A 로그인
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', false);
insert into children (parent_id, nickname, school_id, grade) values ('00000000-0000-0000-0000-00000000000a', '첫째', 1, 4);
do $$ begin
  assert (select count(*) from home_activities) = 1, 'only approved activities visible';
  assert (select count(*) from programs) = 2, 'programs readable';
end $$;
select correct_school_textbook(1, '과학', null);
reset role;

do $$ begin
  assert (select collect_status from schools where id = 1) = 'pending', 'child insert requests collect';
  assert (select source from school_textbooks) = 'parent', 'parent correction stored';
end $$;

-- 학부모 B: A의 자녀가 안 보이고, A 자녀로 교과서 수정 불가, 프로그램 쓰기 불가, 스스로 운영자 불가
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000b', false);
do $$ begin
  assert (select count(*) from children) = 0, 'other parent child hidden';
  begin perform correct_school_textbook(1, '과학', null); assert false, 'should fail';
  exception when raise_exception then null; end;
  begin insert into programs (institution_id, source_id, title, url) values (1, 'z', 'z', 'z'); assert false, 'should fail';
  exception when insufficient_privilege then null; end;
  update profiles set is_operator = true where id = auth.uid();
  assert not (select is_operator from profiles where id = auth.uid()), 'self-promote blocked';
exception when check_violation or insufficient_privilege then null;
end $$;
reset role;
select 'schema_check OK';
