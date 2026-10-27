-- 0016: 공급망 가격·실적 지표 — 메모리 현물가(DRAMeXchange), 미국 PPI·원자재(FRED), 대만 공급사 월매출(TWSE·TPEx). ADR-0014 개정.
create table if not exists ideas.indicators (
  indicator_id  text primary key,                 -- dx:ddr5_16gb | fred:PCU335311335311 | tw:2308
  label         text not null,
  category      text not null,                    -- memory_spot | ppi | commodity | tw_revenue
  unit          text,
  frequency     text not null default 'daily',    -- daily | weekly | monthly
  source        text not null,
  source_url    text,
  ecosystem     text,                             -- hbm | optics | power | cross
  nodes         text[] not null default '{}',
  companies     text[] not null default '{}',
  note          text,
  updated_at    timestamptz not null default now()
);

create table if not exists ideas.indicator_points (
  indicator_id  text not null references ideas.indicators (indicator_id) on delete cascade,
  as_of         date not null,
  value         numeric not null,
  change_pct    numeric,                          -- 출처가 주는 직전 대비 변화율 (현물: 전일, 월매출: 전월)
  yoy_pct       numeric,
  meta          jsonb,
  fetched_at    timestamptz not null default now(),
  primary key (indicator_id, as_of)
);
create index if not exists ip_recent_idx on ideas.indicator_points (as_of desc);

alter table ideas.indicators enable row level security;
alter table ideas.indicator_points enable row level security;
create policy "read ideas" on ideas.indicators for select to anon, authenticated using (true);
create policy "read ideas" on ideas.indicator_points for select to anon, authenticated using (true);
grant select on ideas.indicators, ideas.indicator_points to anon, authenticated;
grant all on ideas.indicators, ideas.indicator_points to service_role;

-- 지표별 최신값 + 직전값 + 약 1주·1개월 전 값
create or replace view public.v_indicators
with (security_invoker = true) as
with ranked as (
  select p.*, row_number() over (partition by p.indicator_id order by p.as_of desc) as rn
  from ideas.indicator_points p
)
select i.indicator_id, i.label, i.category, i.unit, i.frequency, i.source, i.source_url, i.ecosystem, i.nodes, i.companies, i.note,
       l.as_of, l.value, l.change_pct, l.yoy_pct, l.meta,
       (select p.value from ideas.indicator_points p where p.indicator_id = i.indicator_id and p.as_of <= l.as_of - 6 order by p.as_of desc limit 1) as value_1w,
       (select p.value from ideas.indicator_points p where p.indicator_id = i.indicator_id and p.as_of <= l.as_of - 28 order by p.as_of desc limit 1) as value_1m
from ideas.indicators i
join ranked l on l.indicator_id = i.indicator_id and l.rn = 1;
grant select on public.v_indicators to anon, authenticated;

-- 스파크라인용 최근 점 (지표당 최대 120개)
create or replace view public.v_indicator_points
with (security_invoker = true) as
select indicator_id, as_of, value, change_pct, yoy_pct
from (
  select p.*, row_number() over (partition by p.indicator_id order by p.as_of desc) as rn
  from ideas.indicator_points p
) t
where rn <= 120;
grant select on public.v_indicator_points to anon, authenticated;
