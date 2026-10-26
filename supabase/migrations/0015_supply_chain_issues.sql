-- 0015: 공급망 이슈 피드 — 다출처(뉴스 RSS·SEC 8-K·Federal Register·업계지·DB 신호)에서 선별한 이슈. ADR-0014.
create table if not exists ideas.supply_chain_issues (
  issue_key            text primary key,                 -- 대표 출처 URL 집합 해시 (재실행 시 같은 이슈를 이어 씀)
  ecosystem            text,                             -- hbm | optics | power | cross
  event_type           text,                             -- capacity | technology | standard | regulation | order | earnings | m_and_a | supply_disruption | pricing | other
  title                text not null,
  summary              text,
  why_it_matters       text,
  importance           smallint not null default 1 check (importance between 1 and 10),
  importance_rationale text,
  nodes                text[] not null default '{}',     -- 온톨로지 노드 id
  companies            jsonb,                            -- [{company_id, label, ticker, direction(+|-|±), size_band, in_universe, basis}]
  sources              jsonb not null,                   -- [{url, title, publisher, published_at, source_type}]
  source_count         integer not null default 1,
  publisher_count      integer not null default 1,
  first_seen           timestamptz not null default now(),
  last_seen            timestamptz not null default now(),
  latest_published_at  timestamptz,
  method               text not null default 'rule',     -- rule | llm
  model                text,
  status               text not null default 'active' check (status in ('active','dismissed'))
);
create index if not exists sci_recent_idx on ideas.supply_chain_issues (latest_published_at desc);
create index if not exists sci_importance_idx on ideas.supply_chain_issues (importance desc, latest_published_at desc);
create index if not exists sci_nodes_idx on ideas.supply_chain_issues using gin (nodes);

alter table ideas.supply_chain_issues enable row level security;
create policy "read ideas" on ideas.supply_chain_issues for select to anon, authenticated using (true);
grant select on ideas.supply_chain_issues to anon, authenticated;
grant all on ideas.supply_chain_issues to service_role;

create or replace view public.v_supply_chain_issues
with (security_invoker = true) as
select issue_key, ecosystem, event_type, title, summary, why_it_matters, importance, importance_rationale,
       nodes, companies, sources, source_count, publisher_count, first_seen, last_seen, latest_published_at, method, model
from ideas.supply_chain_issues
where status = 'active';
grant select on public.v_supply_chain_issues to anon, authenticated;
