-- 0033: 논문·특허 백필 (사용자 요청 2026-10-30) — 기술의 긴 시계열을 온톨로지 노드로 찾아보게 한다.
-- 사용자 PC 의 `python -m wsj.ecosystems.techdocs upload` 가 secret 키로 쓴다. 해석 작업·recall 은 공개 뷰로 읽는다 (특허·논문은 공개 정보).
-- node 열은 그래프 노드 id, 또는 노드가 안 붙은 문서의 묶음 단위 'cpc:<묶음>'(특허 CPC 묶음)·'topic:<OpenAlex 주제 id>'.
-- 실행: Supabase SQL 편집기 (사용자).

create table if not exists ideas.tech_docs (
  doc_id       text primary key,                       -- patent:<공개번호>(패밀리 대표) | paper:<OpenAlex W id>
  source       text not null check (source in ('patent', 'paper')),
  title        text not null,
  abstract     text,                                   -- 400자 안
  published_on date,                                   -- 특허: 패밀리 첫 공개일 · 논문: 출판일
  priority_on  date,                                   -- 특허 우선일 (발명 시점에 가장 가깝다)
  orgs         jsonb not null default '[]'::jsonb,     -- [{name, country, company}] 출원인·기업 소속 (company = 그래프 기업 id)
  countries    text[] not null default '{}',           -- 특허: 패밀리가 공개된 나라
  codes        text[] not null default '{}',           -- 특허 CPC · 논문 OpenAlex 주제
  nodes        text[] not null default '{}',
  url          text,
  cited_by     int,
  family_size  int,
  loaded_at    timestamptz not null default now()
);
create index if not exists tech_docs_nodes_idx on ideas.tech_docs using gin (nodes);
create index if not exists tech_docs_src_pub_idx on ideas.tech_docs (source, published_on desc);
create index if not exists tech_docs_orgs_idx on ideas.tech_docs using gin (orgs jsonb_path_ops);

create table if not exists ideas.tech_series (
  node      text not null,
  source    text not null check (source in ('patent', 'paper')),
  period    date not null,                             -- 분기 첫날 (묶음 단위는 연 첫날)
  n         int not null,
  n_company int,                                       -- 그래프 기업이 낸 것 (논문은 기업 소속 논문 수)
  loaded_at timestamptz not null default now(),
  primary key (node, source, period)
);

create table if not exists ideas.tech_orgs (
  node       text not null,
  source     text not null check (source in ('patent', 'paper')),
  span       text not null,                            -- ~2021 | 2022-2023 | 2024~
  rank       int not null,
  org        text not null,
  company    text,                                     -- 그래프 기업 id (있으면)
  n          int not null,
  first_year int,                                      -- 이 노드에 이 기관이 처음 나온 해 (새로 나타난 기관 찾기)
  loaded_at  timestamptz not null default now(),
  primary key (node, source, span, org)
);

-- 노드별 최근 2년(끝난 분기) vs 그 전 2년. 탐색용 — 화면에는 내지 않는다.
create or replace view public.v_tech_rising
with (security_invoker = true) as
with b as (
  select date_trunc('quarter', now())::date as cur
)
select s.node, s.source,
       sum(s.n) filter (where s.period >= (b.cur - interval '4 years') and s.period < (b.cur - interval '2 years'))::int as prior_2y,
       sum(s.n) filter (where s.period >= (b.cur - interval '2 years') and s.period < b.cur)::int as recent_2y
from ideas.tech_series s cross join b
where s.node not like 'cpc:%' and s.node not like 'topic:%'
group by s.node, s.source;

create or replace view public.v_tech_series with (security_invoker = true) as
  select node, source, period, n, n_company from ideas.tech_series;
create or replace view public.v_tech_orgs with (security_invoker = true) as
  select node, source, span, rank, org, company, n, first_year from ideas.tech_orgs;
create or replace view public.v_tech_docs with (security_invoker = true) as
  select doc_id, source, title, abstract, published_on, priority_on, orgs, countries, codes, nodes, url, cited_by, family_size from ideas.tech_docs;

alter table ideas.tech_docs enable row level security;
alter table ideas.tech_series enable row level security;
alter table ideas.tech_orgs enable row level security;
drop policy if exists tech_docs_read on ideas.tech_docs;
drop policy if exists tech_series_read on ideas.tech_series;
drop policy if exists tech_orgs_read on ideas.tech_orgs;
create policy tech_docs_read on ideas.tech_docs for select to anon, authenticated using (true);
create policy tech_series_read on ideas.tech_series for select to anon, authenticated using (true);
create policy tech_orgs_read on ideas.tech_orgs for select to anon, authenticated using (true);
grant select on ideas.tech_docs, ideas.tech_series, ideas.tech_orgs to anon, authenticated;
grant all on ideas.tech_docs, ideas.tech_series, ideas.tech_orgs to service_role;
grant select on public.v_tech_rising, public.v_tech_series, public.v_tech_orgs, public.v_tech_docs to anon, authenticated;
