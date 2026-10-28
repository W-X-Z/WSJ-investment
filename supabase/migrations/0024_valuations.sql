-- 0024 (ADR-0019): 결과는 가치평가, 점수는 계산기.
-- 매일 아침 LLM 이 이슈 → 영향 경로 → 기업 숫자 → 시나리오별 내재가치(시총 → 주가)와 기댓값을 쓰고, 화면은 그 결과만 보여 준다.
-- 근거·선행 점수(assessment)는 계속 계산하지만 표면에 올리지 않는다 (★ 규칙·알림·시스템 화면용).
-- 운영 DB 에는 사용자가 SQL 에디터에서 실행한다. 모두 idempotent.

-- 1) 재무 (가치평가의 분모): 매출·영업이익·순이익. ttm = 최근 4분기(또는 12개월) 합, fy = 회계연도, q = 분기.
--    금액은 현지 통화 '원 단위'(NT$·원·달러 그대로, 천·억 환산 끝낸 값).
create table if not exists raw.company_fundamentals (
  company_id        text not null,
  period            text not null check (period in ('ttm', 'fy', 'q')),
  period_end        date not null,
  currency          text not null,
  revenue           numeric,
  gross_profit      numeric,
  operating_income  numeric,
  net_income        numeric,
  source            text not null,                 -- sec_companyfacts | twse_monthly+t187ap06 | tpex_monthly+t187ap14 | naver_finance
  source_url        text,
  note              text,                          -- 예: '영업이익률은 YTD 비율 × TTM 매출'
  fetched_at        timestamptz not null default now(),
  primary key (company_id, period, period_end)
);
create index if not exists company_fundamentals_latest on raw.company_fundamentals (company_id, period, period_end desc);

-- 최신 TTM(없으면 FY) 한 줄 + 1년 전 같은 기간 → 성장률, 시총과 붙여 P/S·P/E
create or replace view public.v_company_fundamentals
with (security_invoker = true) as
with latest as (
  select distinct on (company_id) company_id, period, period_end, currency, revenue, gross_profit, operating_income, net_income, source, source_url, note
  from raw.company_fundamentals
  where period in ('ttm', 'fy')
  order by company_id, (period = 'ttm') desc, period_end desc
), prior as (
  select l.company_id, p.revenue as revenue_prev, p.operating_income as operating_income_prev
  from latest l
  join lateral (
    select revenue, operating_income from raw.company_fundamentals f
    where f.company_id = l.company_id and f.period = l.period
      and f.period_end between l.period_end - 400 and l.period_end - 330
    order by abs(f.period_end - (l.period_end - 365)) limit 1
  ) p on true
)
select l.company_id, l.period, l.period_end, l.currency, l.revenue, l.gross_profit, l.operating_income, l.net_income, l.source, l.source_url, l.note,
       case when l.revenue > 0 then round(100 * l.operating_income / l.revenue, 1) end as op_margin_pct,
       case when l.revenue > 0 then round(100 * l.net_income / l.revenue, 1) end as net_margin_pct,
       case when p.revenue_prev > 0 then round(100 * (l.revenue / p.revenue_prev - 1), 1) end as revenue_yoy_pct,
       round(l.revenue * x.usd_per_unit) as revenue_usd,
       c.market_cap_local, c.market_cap_usd, c.close, c.price_as_of, c.shares_outstanding,
       case when l.revenue > 0 then round(c.market_cap_local / l.revenue, 2) end as ps,
       case when l.net_income > 0 then round(c.market_cap_local / l.net_income, 1) end as pe
from latest l
left join prior p on p.company_id = l.company_id
left join public.v_company_facts c on c.company_id = l.company_id
left join ref.fx_rates x on x.currency = l.currency;

-- 2) 가치평가 — 아이디어마다, 평가일마다 한 행 (이력이 남아 다음 주 '적중 점검'의 재료가 된다)
create table if not exists ideas.valuations (
  idea_key             text not null references ideas.investment_ideas (idea_key) on delete cascade,
  as_of                date not null,
  company_id           text not null,
  currency             text not null,
  price                numeric not null check (price > 0),          -- 평가 시점 종가 (현지 통화)
  price_as_of          date,
  shares               numeric,                                     -- 발행주식수 (내재 시총 → 주가)
  market_cap_usd       numeric,
  horizon_months       smallint not null default 12 check (horizon_months between 3 and 36),
  scenarios            jsonb not null,  -- [{name: bear|base|bull, prob, story, revenue, margin_pct, metric: ps|pe, multiple, implied_mcap_local, implied_price, upside_pct, evidence: [...]}]
  expected_price       numeric not null check (expected_price > 0), -- Σ prob × implied_price (서버가 다시 계산)
  expected_upside_pct  numeric not null,                             -- expected_price ÷ price − 1
  confidence           text not null check (confidence in ('low', 'mid', 'high')),
  verdict              text not null,                               -- 한 단락: 이슈 → 영향 → 이 기업 숫자 → 가격
  assumptions          jsonb not null default '[]',                  -- [{kind: fact|estimate, claim, basis?, evidence: [{id, url, title, date, …}]}] — 추정은 LLM 의 판단(basis), 사실은 근거
  breaks               jsonb not null default '[]',                  -- 깨지는 조건
  path                 jsonb,                                        -- {labels: [...], mechanism} — 선행 추론의 경로 (점수 없이 글로)
  calculator           jsonb,                                        -- 참고로 쓴 엔진 점수 {evidence_score, anticipation_score, priced_in, tenbagger} — 표면에 안 올림
  model                text,
  method               text,
  created_at           timestamptz not null default now(),
  primary key (idea_key, as_of)
);
create index if not exists valuations_latest on ideas.valuations (idea_key, as_of desc);

-- 쓰기 함수 (예약작업). 검증: 활성 아이디어 · 시나리오 2~4개(bear/base/bull, 확률 합 1±0.02, 내재 주가 > 0) · 가정(사실 https 출처 1개+, 추정은 basis, 전체 2개+) · verdict 120자 이상.
-- expected_price·expected_upside_pct·시나리오별 upside_pct 는 서버가 다시 계산한다 (LLM 산수를 믿지 않는다).
create or replace function ideas.put_valuations(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; px numeric; sh numeric; d date;
  sc jsonb; sc2 jsonb := '[]'::jsonb; s jsonb; p numeric; psum numeric; ip numeric; ep numeric; n_assume int; n_fact int; nm text;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'idea_key';
    if k is null or not exists (select 1 from ideas.investment_ideas where idea_key = k and status = 'active') then
      rej := rej || jsonb_build_object('i', i, 'reason', '활성 아이디어 없음: ' || coalesce(k, '')); continue;
    end if;
    begin
      px := (r->>'price')::numeric; sh := nullif(r->>'shares', '')::numeric; d := coalesce((r->>'as_of')::date, current_date);
    exception when others then
      rej := rej || jsonb_build_object('i', i, 'reason', 'price·shares·as_of 형식'); continue;
    end;
    if px is null or px <= 0 then rej := rej || jsonb_build_object('i', i, 'reason', 'price 필요'); continue; end if;
    if r->>'confidence' not in ('low', 'mid', 'high') then rej := rej || jsonb_build_object('i', i, 'reason', 'confidence 는 low|mid|high'); continue; end if;
    if length(coalesce(r->>'verdict', '')) < 120 then rej := rej || jsonb_build_object('i', i, 'reason', 'verdict 120자 이상'); continue; end if;
    if nullif(btrim(r->>'company_id'), '') is null or nullif(btrim(r->>'currency'), '') is null then
      rej := rej || jsonb_build_object('i', i, 'reason', 'company_id·currency 필요'); continue;
    end if;
    sc := r->'scenarios';
    if jsonb_typeof(sc) <> 'array' or jsonb_array_length(sc) < 2 or jsonb_array_length(sc) > 4 then
      rej := rej || jsonb_build_object('i', i, 'reason', 'scenarios 2~4개'); continue;
    end if;
    psum := 0; ep := 0; sc2 := '[]'::jsonb; nm := null;
    for s in select * from jsonb_array_elements(sc) loop
      if s->>'name' not in ('bear', 'base', 'bull') then nm := '시나리오 name 은 bear|base|bull'; exit; end if;
      begin
        p := (s->>'prob')::numeric; ip := (s->>'implied_price')::numeric;
      exception when others then
        nm := 'prob·implied_price 숫자'; exit;
      end;
      if p is null or p < 0 or p > 1 or ip is null or ip <= 0 then nm := 'prob 0~1 · implied_price > 0'; exit; end if;
      psum := psum + p; ep := ep + p * ip;
      sc2 := sc2 || (s || jsonb_build_object('upside_pct', round(100 * (ip / px - 1), 1)));
    end loop;
    if nm is not null then rej := rej || jsonb_build_object('i', i, 'reason', nm); continue; end if;
    if abs(psum - 1) > 0.02 then rej := rej || jsonb_build_object('i', i, 'reason', '확률 합이 1 이 아님: ' || psum::text); continue; end if;
    ep := ep / psum;
    -- 가정 = 사실(https 출처) 또는 추정(basis). 사실 1개 이상, 전체 2개 이상.
    select count(*) filter (where ok_fact) + count(*) filter (where not ok_fact and ok_est), count(*) filter (where ok_fact) into n_assume, n_fact
    from (select nullif(btrim(a->>'claim'), '') is not null and jsonb_typeof(a->'evidence') = 'array'
                 and exists (select 1 from jsonb_array_elements(a->'evidence') e where (e->>'url') ~ '^https://') as ok_fact,
                 nullif(btrim(a->>'claim'), '') is not null and length(coalesce(a->>'basis', '')) >= 6 as ok_est
          from jsonb_array_elements(coalesce(r->'assumptions', '[]'::jsonb)) a) t;
    if n_assume < 2 or n_fact < 1 then rej := rej || jsonb_build_object('i', i, 'reason', '가정은 사실(출처) 1개 이상, 전체 2개 이상 (추정은 basis 필수)'); continue; end if;
    insert into ideas.valuations (idea_key, as_of, company_id, currency, price, price_as_of, shares, market_cap_usd, horizon_months, scenarios,
                                  expected_price, expected_upside_pct, confidence, verdict, assumptions, breaks, path, calculator, model, method)
    values (k, d, r->>'company_id', r->>'currency', px, nullif(r->>'price_as_of', '')::date, sh, nullif(r->>'market_cap_usd', '')::numeric,
            coalesce(nullif(r->>'horizon_months', '')::int, 12), sc2, round(ep, 4), round(100 * (ep / px - 1), 1), r->>'confidence',
            left(r->>'verdict', 2000), coalesce(r->'assumptions', '[]'::jsonb), coalesce(r->'breaks', '[]'::jsonb), r->'path', r->'calculator',
            left(r->>'model', 60), left(r->>'method', 20))
    on conflict (idea_key, as_of) do update
      set company_id = excluded.company_id, currency = excluded.currency, price = excluded.price, price_as_of = excluded.price_as_of,
          shares = excluded.shares, market_cap_usd = excluded.market_cap_usd, horizon_months = excluded.horizon_months, scenarios = excluded.scenarios,
          expected_price = excluded.expected_price, expected_upside_pct = excluded.expected_upside_pct, confidence = excluded.confidence,
          verdict = excluded.verdict, assumptions = excluded.assumptions, breaks = excluded.breaks, path = excluded.path, calculator = excluded.calculator,
          model = excluded.model, method = excluded.method, created_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

-- 최신 평가 (활성 아이디어마다 한 줄) + 직전 평가와의 차이
create or replace view public.v_valuations
with (security_invoker = true) as
with v as (
  select v.*, lag(expected_upside_pct) over (partition by idea_key order by as_of) as prev_expected_upside_pct,
         lag(as_of) over (partition by idea_key order by as_of) as prev_as_of,
         count(*) over (partition by idea_key) as n_valuations,
         row_number() over (partition by idea_key order by as_of desc) as rn
  from ideas.valuations v
)
select v.idea_key, v.as_of, v.company_id, v.currency, v.price, v.price_as_of, v.shares, v.market_cap_usd, v.horizon_months, v.scenarios,
       v.expected_price, v.expected_upside_pct, v.confidence, v.verdict, v.assumptions, v.breaks, v.path, v.model, v.method, v.created_at,
       v.prev_expected_upside_pct, v.prev_as_of, v.n_valuations
from v
join ideas.investment_ideas i on i.idea_key = v.idea_key
where v.rn = 1 and i.status = 'active';

-- 이력 (주간 적중 점검: 평가 당시 기대 상승여력 vs 그 뒤 실제 주가)
create or replace view public.v_valuation_history
with (security_invoker = true) as
select v.idea_key, v.as_of, v.company_id, v.currency, v.price, v.expected_price, v.expected_upside_pct, v.confidence, v.horizon_months, v.created_at
from ideas.valuations v
join ideas.investment_ideas i on i.idea_key = v.idea_key
where i.status = 'active';

-- 권한
revoke all on function ideas.put_valuations(jsonb) from public;
revoke all on function ideas.put_valuations(jsonb) from anon, authenticated;
grant execute on function ideas.put_valuations(jsonb) to service_role;
grant select on public.v_company_fundamentals, public.v_valuations, public.v_valuation_history to anon, authenticated;
grant select on raw.company_fundamentals, ideas.valuations to anon, authenticated;
grant all on raw.company_fundamentals, ideas.valuations to service_role;
alter table raw.company_fundamentals enable row level security;
alter table ideas.valuations enable row level security;
drop policy if exists company_fundamentals_read on raw.company_fundamentals;
create policy company_fundamentals_read on raw.company_fundamentals for select to anon, authenticated using (true);
drop policy if exists valuations_read on ideas.valuations;
create policy valuations_read on ideas.valuations for select to anon, authenticated using (true);
