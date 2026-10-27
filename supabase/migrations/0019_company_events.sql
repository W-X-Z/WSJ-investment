-- 0019: 기업별 최신 소식(공시·월매출·뉴스). ADR-0016 개정 1.
-- wsj.ecosystems.company_feed 가 하루 두 번 모으고, 아이디어 엔진이 최근 14일치를 신호로 쓴다.
-- 대만 중대공시 OpenAPI 는 당일분만 주므로 매 실행 결과를 쌓아야 2주 창을 볼 수 있다.

create table if not exists ideas.company_events (
  event_id      text primary key,                              -- sha1(company_id|url|title) 앞 20자
  company_id    text not null,                                 -- 그래프 기업 id (company:xxx)
  kind          text not null check (kind in ('filing', 'disclosure', 'revenue', 'news')),
  published_at  timestamptz not null,
  title         text not null,
  url           text not null,
  publisher     text,
  tier          text,                                          -- official_issuer | third_party_report
  importance    smallint not null default 1 check (importance between 1 and 3),
  lang          text,
  text          text,
  extra         jsonb,
  first_seen    timestamptz not null default now()
);
create index if not exists company_events_company_idx on ideas.company_events (company_id, published_at desc);
create index if not exists company_events_recent_idx on ideas.company_events (published_at desc);

-- 아이디어 상세 화면의 '관련 기업 최근 소식' (최근 30일)
create or replace view public.v_company_events
with (security_invoker = true) as
select event_id, company_id, kind, published_at, title, url, publisher, tier, importance, lang
from ideas.company_events
where published_at > now() - interval '30 days';

-- stale = 근거가 낡았다 (마지막 최신 근거가 21일 넘음). 갱신 시각이 아니라 근거 날짜로 본다.
create or replace view public.v_investment_ideas
with (security_invoker = true) as
select idea_key, status, trend, type, title, thesis, stars, stars_reason, primary_company, companies, chain, risks, watch,
       what_changed, nodes, ecosystems, signal_refs, evidence_count, last_signal_at, first_seen, updated_at, revision, model, method,
       coalesce(last_signal_at, updated_at::date) < current_date - 21 as stale
from ideas.investment_ideas
where status = 'active';

alter table ideas.company_events enable row level security;
drop policy if exists "read all" on ideas.company_events;
create policy "read all" on ideas.company_events for select to anon, authenticated using (true);
grant select on ideas.company_events to anon, authenticated;
grant all on ideas.company_events to service_role;
grant select on public.v_company_events, public.v_investment_ideas to anon, authenticated;
