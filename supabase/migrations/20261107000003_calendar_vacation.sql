-- 방학 날짜를 재량휴업일 등(is_holiday)과 따로 표시한다. 나이스는 방학을 날짜별 '휴업일' 행으로 준다.
alter table school_calendar add column is_vacation boolean not null default false;
comment on column school_calendar.is_holiday is '재량휴업일 등 학교가 쉬는 날 (방학·토요휴업일·공휴일 제외)';
comment on column school_calendar.is_vacation is '여름·겨울방학 기간의 날짜 (is_holiday와 겹치지 않음)';
