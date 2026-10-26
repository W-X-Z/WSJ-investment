-- 0001: 부서(에이전트)별 스키마. ADR-0002 참조.
-- Phase 1에서는 raw / core / ops만 채운다. 나머지는 구조 선점용.

create schema if not exists raw;        -- Data Desk: 원천 데이터 미러 (가공 없음)
create schema if not exists core;       -- Data Desk: 정규화·엔티티 매칭
create schema if not exists ideas;      -- Analyst: 후보·투자논제·반증가능 예측
create schema if not exists proposals;  -- Strategy: 포지션 제안·진입/청산 규칙
create schema if not exists decisions;  -- Risk: 승인/거부/조건부 (veto)
create schema if not exists orders;     -- PM: 승인된 제안의 주문 큐
create schema if not exists fills;      -- Execution: 체결·체결통보
create schema if not exists reviews;    -- Audit: 성과 귀인·논제 채점
create schema if not exists ops;        -- 시스템: 수집기 실행 로그·워터마크

comment on schema raw       is 'Data Desk가 쓰는 원천 데이터 미러. 소스 필드명 유지, 해석 컬럼 금지.';
comment on schema core      is 'Data Desk가 쓰는 정규화 레이어. companies(CIK 허브), entity_aliases.';
comment on schema ideas     is 'Analyst 전용 write. 후보·투자논제·날짜 박힌 예측.';
comment on schema proposals is 'Strategy 전용 write. ideas를 읽어 포지션 제안.';
comment on schema decisions is 'Risk 전용 write. proposals 심사. approved 외에는 하류에서 보이지 않아야 함.';
comment on schema orders    is 'PM 전용 write. decisions.approved만 읽어 주문 큐 생성.';
comment on schema fills     is 'Execution 전용 write. NH PLUG 체결·체결통보.';
comment on schema reviews   is 'Audit 전용 write. 성과 귀인·논제 채점.';
comment on schema ops       is '수집기 실행 로그와 워터마크.';

-- PostgREST 노출 스키마 (Supabase 기본은 public, graphql_public).
-- 파이프라인(서비스 롤)과 조회 화면(publishable key + RLS)이 raw/core/ops에 접근해야 한다.
alter role authenticator set pgrst.db_schemas = 'public, graphql_public, raw, core, ops';
notify pgrst, 'reload config';

-- 서비스 롤·anon·authenticated가 스키마를 볼 수 있어야 PostgREST가 노출한다.
grant usage on schema raw, core, ops to anon, authenticated, service_role;
alter default privileges in schema raw  grant select on tables to anon, authenticated;
alter default privileges in schema core grant select on tables to anon, authenticated;
alter default privileges in schema ops  grant select on tables to anon, authenticated;
alter default privileges in schema raw  grant all on tables to service_role;
alter default privileges in schema core grant all on tables to service_role;
alter default privileges in schema ops  grant all on tables to service_role;
alter default privileges in schema raw  grant all on sequences to service_role;
alter default privileges in schema core grant all on sequences to service_role;
alter default privileges in schema ops  grant all on sequences to service_role;
