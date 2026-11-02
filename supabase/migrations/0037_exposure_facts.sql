-- 0037: 노출도 재료 (ADR-0031, 백로그 G-8 무료 경로)
-- 실행: Supabase SQL 편집기 (사용자). 0036 뒤.
-- 미국 공시(10-K·20-F·40-F)의 매출 구성 숫자. exposure 수집기(exposure-facts 워크플로, 일요일 07:13 KST, LLM 없음)가 넣고,
-- 주간 개선·해석이 공급 관계(offered_by)의 exposure_pct·exposure_year·exposure_source 로 옮긴다.

-- 공시의 매출 구성 숫자. kind: revenue(차원별 매출과 그 해 총매출 대비 pct) | concentration(고객·제품 집중도 %) | text('매출의 N%' 문장) | total | none(숫자 못 찾음)
create table if not exists ideas.exposure_facts (
  fact_key    text primary key,                 -- md5(company|url|kind|concept|label)
  company_id  text not null,                    -- 그래프 기업 id
  cik         bigint,
  ticker      text,
  form        text,                             -- 10-K | 20-F | 40-F
  filed       date,
  url         text not null,                    -- 보고서 원문 (exposure_source 로 쓴다)
  period_end  date,
  kind        text not null check (kind in ('revenue', 'concentration', 'text', 'total', 'none')),
  concept     text,
  axes        jsonb not null default '{}'::jsonb,   -- {축: 멤버}
  label       text,                             -- 사람이 읽는 축=멤버 또는 문장
  value       numeric,
  pct         numeric,
  fetched_at  timestamptz not null default now()
);
create index if not exists exposure_facts_company_idx on ideas.exposure_facts (company_id, kind);
alter table ideas.exposure_facts enable row level security;
revoke all on ideas.exposure_facts from public, anon, authenticated;
grant all on ideas.exposure_facts to service_role;
