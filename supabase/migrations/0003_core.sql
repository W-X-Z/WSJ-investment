-- 0003: core — CIK 허브와 소스별 별칭. ADR-0004, ADR-0005 참조.

create table if not exists core.companies (
  cik                     bigint primary key,
  name                    text not null,
  ticker                  text,
  exchange                text,                 -- Nasdaq | NYSE | OTC | CBOE | TXSE
  sic                     integer,
  sic_description         text,
  entity_type             text,                 -- operating | ...
  filer_category          text,                 -- SEC category 문자열
  state_of_incorporation  text,
  business_state          text,
  fiscal_year_end         text,                 -- 'MMDD'
  former_names            jsonb,
  public_float            numeric,              -- dei:EntityPublicFloat (USD)
  public_float_asof       date,                 -- 해당 10-K의 측정일(end)
  public_float_accn       text,
  sector_bucket           text,                 -- biotech | medtech | gov_procurement | other
  in_universe             boolean not null default false,
  universe_reason         text,
  submissions_synced_at   timestamptz,
  updated_at              timestamptz not null default now()
);
create index if not exists companies_ticker_idx on core.companies (ticker);
create index if not exists companies_universe_idx on core.companies (in_universe) where in_universe;
create index if not exists companies_sic_idx on core.companies (sic);

comment on column core.companies.public_float is '최근 10-K 기준 비계열 보유 시가총액. 시총 프록시. 최대 1년 오래될 수 있음.';
comment on column core.companies.sector_bucket is 'ADR-0004의 SIC 집합으로 산출. biotech | medtech | gov_procurement | other';

create table if not exists core.entity_aliases (
  id           bigint generated always as identity primary key,
  source       text not null,     -- sec | fda | clinicaltrials | usaspending | finra | cms | ...
  alias_type   text not null,     -- ticker | legal_name | sponsor_name | applicant | uei | recipient_name | subsidiary
  alias        text not null,     -- 소스 원문 그대로
  alias_norm   text not null,     -- 정규화 (대문자, 접미사·구두점 제거)
  cik          bigint references core.companies (cik),
  confidence   numeric not null default 1.0 check (confidence between 0 and 1),
  method       text not null check (method in ('exact','normalized','fuzzy','manual','llm')),
  verified_at  timestamptz,
  created_at   timestamptz not null default now(),
  unique (source, alias_type, alias)
);
create index if not exists entity_aliases_norm_idx on core.entity_aliases (alias_norm);
create index if not exists entity_aliases_cik_idx  on core.entity_aliases (cik);

-- 매칭 안 된 소스 이름 큐. 사람/LLM이 처리한 뒤 entity_aliases로 옮긴다.
create table if not exists core.entity_unresolved (
  id          bigint generated always as identity primary key,
  source      text not null,
  alias_type  text not null,
  alias       text not null,
  alias_norm  text not null,
  seen_count  integer not null default 1,
  first_seen  timestamptz not null default now(),
  last_seen   timestamptz not null default now(),
  candidates  jsonb,            -- 정규화 매칭 후보 [{cik, name, score}]
  unique (source, alias_type, alias)
);

alter table core.companies        enable row level security;
alter table core.entity_aliases   enable row level security;
alter table core.entity_unresolved enable row level security;
create policy "read core" on core.companies         for select to anon, authenticated using (true);
create policy "read core" on core.entity_aliases    for select to anon, authenticated using (true);
create policy "read core" on core.entity_unresolved for select to anon, authenticated using (true);
