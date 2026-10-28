-- 0022 (ADR-0017 개정 1): 주가·시가총액을 판단의 중심에 — 발행주식수·환율·시가총액 뷰, 저점 대비 폭, 심층 분석 메모.
-- 운영 DB 에는 사용자가 SQL 에디터에서 실행한다. 모두 idempotent.

create schema if not exists ref;

-- 1) 발행주식수 (시장별 공식·공개 출처, wsj.ecosystems.facts) — 시총은 저장하지 않고 뷰가 종가 × 주식수 × 환율로 계산한다
create table if not exists raw.company_facts (
  company_id text primary key,
  ticker text not null,                 -- 가격 키 (US 티커 또는 '거래소:코드')
  exchange text,
  currency text not null,
  shares_outstanding numeric not null check (shares_outstanding > 0),
  shares_as_of date,
  source text not null,
  fetched_at timestamptz not null default now()
);
create index if not exists company_facts_ticker on raw.company_facts (ticker);

create table if not exists ref.fx_rates (
  currency text primary key,
  usd_per_unit numeric not null check (usd_per_unit > 0),
  as_of date,
  updated_at timestamptz not null default now()
);

-- 2) 가격 맥락에 '저점 대비' 추가 (텐배거의 둘째 조건: 아직 안 갔는가) — 열은 끝에만 추가
create or replace view public.v_price_context
with (security_invoker = true) as
with p as (
  select ticker, trade_date, close, volume, row_number() over (partition by ticker order by trade_date desc) as rn
  from raw.px_daily
  where trade_date > current_date - 400 and close is not null
)
select ticker,
       max(trade_date) filter (where rn = 1) as as_of,
       max(close) filter (where rn = 1) as close,
       round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn = 22), 0) - 1), 1) as r1m,
       round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn = 64), 0) - 1), 1) as r3m,
       round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn = 248), 0) - 1), 1) as r12m,
       round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn <= 250), 0) - 1), 1) as from_high,
       round(avg(volume) filter (where rn <= 5) / nullif(avg(volume) filter (where rn between 6 and 65), 0), 2) as vol_ratio,
       count(*) as points,
       round(100 * (max(close) filter (where rn = 1) / nullif(min(close) filter (where rn <= 250), 0) - 1), 1) as from_low
from p
group by ticker;

-- 3) 상장사 밸류에이션 맥락: 시가총액(현지·USD) — 주가가 갱신되면 시총도 따라간다
create or replace view public.v_company_facts
with (security_invoker = true) as
select f.company_id, f.ticker, f.exchange, f.currency, f.shares_outstanding, f.shares_as_of, f.source,
       p.as_of as price_as_of, p.close,
       round(f.shares_outstanding * p.close) as market_cap_local,
       round(f.shares_outstanding * p.close * x.usd_per_unit) as market_cap_usd,
       x.as_of as fx_as_of, p.r1m, p.r3m, p.r12m, p.from_high, p.from_low
from raw.company_facts f
left join public.v_price_context p on p.ticker = f.ticker
left join ref.fx_rates x on x.currency = f.currency;

-- 4) 심층 분석 메모 (아이디어마다 기술·시장·공급 구조·밸류에이션·반대 근거·확인 일정) — 예약작업이 쓴다
create table if not exists ideas.idea_notes (
  idea_key text not null references ideas.investment_ideas (idea_key) on delete cascade,
  kind text not null default 'deep' check (kind in ('deep')),
  content jsonb not null,               -- {sections: [{id, title, body, sources: [{title, url, date}]}], summary, computed_at}
  model text,
  method text,
  updated_at timestamptz not null default now(),
  primary key (idea_key, kind)
);

create or replace function ideas.put_idea_notes(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; n_sec int;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'idea_key';
    if k is null or not exists (select 1 from ideas.investment_ideas where idea_key = k) then
      rej := rej || jsonb_build_object('i', i, 'reason', 'idea_key 없음'); continue;
    end if;
    if jsonb_typeof(r->'content'->'sections') <> 'array' then
      rej := rej || jsonb_build_object('i', i, 'reason', 'content.sections 배열 필요'); continue;
    end if;
    select count(*) into n_sec from jsonb_array_elements(r->'content'->'sections') s
     where nullif(btrim(s->>'body'), '') is not null and jsonb_typeof(s->'sources') = 'array' and jsonb_array_length(s->'sources') >= 1;
    if n_sec < 3 then
      rej := rej || jsonb_build_object('i', i, 'reason', '출처 있는 문단이 3개 미만'); continue;
    end if;
    insert into ideas.idea_notes (idea_key, kind, content, model, method, updated_at)
    values (k, coalesce(r->>'kind', 'deep'), r->'content' || jsonb_build_object('computed_at', now()), left(r->>'model', 60), left(r->>'method', 20), now())
    on conflict (idea_key, kind) do update set content = excluded.content, model = excluded.model, method = excluded.method, updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

create or replace view public.v_idea_notes
with (security_invoker = true) as
select n.idea_key, n.kind, n.content, n.model, n.method, n.updated_at
from ideas.idea_notes n
join ideas.investment_ideas i on i.idea_key = n.idea_key
where i.status = 'active';

-- 권한
grant usage on schema ref to anon, authenticated, service_role;
revoke all on function ideas.put_idea_notes(jsonb) from public;
revoke all on function ideas.put_idea_notes(jsonb) from anon, authenticated;
grant execute on function ideas.put_idea_notes(jsonb) to service_role;
grant select on public.v_price_context, public.v_company_facts, public.v_idea_notes to anon, authenticated;
grant select on raw.company_facts, ref.fx_rates to anon, authenticated;
grant all on raw.company_facts, ref.fx_rates, ideas.idea_notes to service_role;
alter table raw.company_facts enable row level security;
alter table ref.fx_rates enable row level security;
alter table ideas.idea_notes enable row level security;
drop policy if exists company_facts_read on raw.company_facts;
create policy company_facts_read on raw.company_facts for select to anon, authenticated using (true);
drop policy if exists fx_rates_read on ref.fx_rates;
create policy fx_rates_read on ref.fx_rates for select to anon, authenticated using (true);
drop policy if exists idea_notes_read on ideas.idea_notes;
create policy idea_notes_read on ideas.idea_notes for select to anon, authenticated using (true);
