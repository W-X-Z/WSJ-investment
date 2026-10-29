-- 0029: 생성과 보정의 분리 (ADR-0026) — 테제에 novelty·시장이 놓친 것·시차·첫 신호·조용함 검사를 더하고, 신규 테제는 stage 0~1 만 받는다
-- (stage 2 이상은 kind=regime 체제 기록). 약한 신호 관찰(ideas.weak_signals)과 수집기 잔차(ideas.unmapped_terms)를 새로 둔다.
-- 실행: Supabase SQL 편집기 (사용자). 작업은 put_* 함수로만 쓴다.

-- 1. theses 확장 ------------------------------------------------------------------------------------------
alter table ideas.theses
  add column if not exists kind               text not null default 'thesis' check (kind in ('thesis', 'regime')),
  add column if not exists novelty            text check (novelty in ('new_technology', 'new_data', 'new_issue', 'new_structure', 'analog')),
  add column if not exists novelty_reason     text,     -- 왜 전례가 없는가 / 어떤 전례의 재현인가
  add column if not exists what_market_misses text,     -- 시장이 놓치고 있는 것 한 문장
  add column if not exists lag_months         smallint, -- 첫 신호 → 리레이팅까지 (벤치마크 또는 추정)
  add column if not exists first_signal       jsonb,    -- {metric, where, expected_by}
  add column if not exists quiet_check        jsonb;    -- {companies: [{company, px_6m_pct, px_12m_pct, eps_rev_90d}], verdict, as_of}

-- 10/29 의 stage 2 네 개는 체제 기록으로 (ADR-0026 결정 6)
update ideas.theses set kind = 'regime', novelty = coalesce(novelty, 'analog'), updated_at = now()
 where thesis_key in ('packaging_capacity_premium_2026', 'rack_power_800vdc_2027', 'onsite_power_grid_bypass_2026', 'inp_laser_supply_regime_2026')
   and kind = 'thesis';

create or replace function ideas.put_theses(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; kind_ text; st smallint; is_new boolean;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'thesis_key';
    if k is null or k !~ '^[a-z0-9_]{6,60}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'thesis_key 는 영문 소문자·숫자·_ 6~60자'); continue; end if;
    if length(coalesce(r->>'title', '')) < 5 or length(coalesce(r->>'statement', '')) < 80 then
      rej := rej || jsonb_build_object('i', i, 'reason', 'title 5자·statement 80자 이상'); continue;
    end if;
    if jsonb_typeof(r->'chain') <> 'array' or jsonb_array_length(r->'chain') < 3 then rej := rej || jsonb_build_object('i', i, 'reason', 'chain 3단계 이상'); continue; end if;
    if jsonb_typeof(r->'drivers') <> 'array' or jsonb_array_length(r->'drivers') < 1 then rej := rej || jsonb_build_object('i', i, 'reason', 'drivers 1개 이상 (관측 가능한 수치)'); continue; end if;
    if jsonb_typeof(r->'falsifiers') <> 'array' or jsonb_array_length(r->'falsifiers') < 1
       or exists (select 1 from jsonb_array_elements(r->'falsifiers') f where (f->>'due') !~ '^\d{4}-\d{2}-\d{2}$') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'falsifiers 1개 이상, 각각 due(YYYY-MM-DD)'); continue;
    end if;
    if jsonb_typeof(r->'beneficiaries') <> 'array' or jsonb_array_length(r->'beneficiaries') < 1 then rej := rej || jsonb_build_object('i', i, 'reason', 'beneficiaries 1개 이상'); continue; end if;
    kind_ := coalesce(r->>'kind', (select t.kind from ideas.theses t where t.thesis_key = k), 'thesis');  -- 안 보내면 저장된 kind 유지
    if kind_ not in ('thesis', 'regime') then rej := rej || jsonb_build_object('i', i, 'reason', 'kind 는 thesis | regime'); continue; end if;
    st := coalesce((r->>'stage')::smallint, 0);
    is_new := not exists (select 1 from ideas.theses t where t.thesis_key = k);
    if is_new and kind_ = 'thesis' and st > 1 then
      rej := rej || jsonb_build_object('i', i, 'reason', '새 테제는 stage 0~1 — 공급 반응이 이미 보이면 kind=regime (체제 기록) 으로'); continue;
    end if;
    -- kind=thesis 의 필수 항목: 보낸 값 또는 이미 저장된 값
    if kind_ = 'thesis' and (
         coalesce(r->>'novelty', (select t.novelty from ideas.theses t where t.thesis_key = k), '') not in ('new_technology', 'new_data', 'new_issue', 'new_structure', 'analog')
      or length(coalesce(r->>'novelty_reason', (select t.novelty_reason from ideas.theses t where t.thesis_key = k), '')) < 10
      or length(coalesce(r->>'what_market_misses', (select t.what_market_misses from ideas.theses t where t.thesis_key = k), '')) < 10) then
      rej := rej || jsonb_build_object('i', i, 'reason', 'kind=thesis 는 novelty(new_technology|new_data|new_issue|new_structure|analog)·novelty_reason·what_market_misses 필수'); continue;
    end if;
    insert into ideas.theses as t (thesis_key, title, statement, ecosystem, chain, drivers, beneficiaries, losers, falsifiers, stage, stage_reason, status, close_reason, benchmark, model, method,
                                   kind, novelty, novelty_reason, what_market_misses, lag_months, first_signal, quiet_check, updated_at)
    values (k, left(r->>'title', 160), r->>'statement', r->>'ecosystem', r->'chain', r->'drivers', r->'beneficiaries', coalesce(r->'losers', '[]'::jsonb), r->'falsifiers',
            st, r->>'stage_reason', coalesce(r->>'status', 'active'), r->>'close_reason', r->>'benchmark', left(r->>'model', 60), left(r->>'method', 20),
            kind_, r->>'novelty', r->>'novelty_reason', r->>'what_market_misses', (r->>'lag_months')::smallint, r->'first_signal', r->'quiet_check', now())
    on conflict (thesis_key) do update set title = excluded.title, statement = excluded.statement, ecosystem = excluded.ecosystem, chain = excluded.chain, drivers = excluded.drivers,
      beneficiaries = excluded.beneficiaries, losers = excluded.losers, falsifiers = excluded.falsifiers, stage = excluded.stage, stage_reason = excluded.stage_reason,
      status = excluded.status, close_reason = excluded.close_reason, benchmark = excluded.benchmark, model = excluded.model, method = excluded.method,
      -- ADR-0026 항목은 빠뜨리고 보내도 지워지지 않는다 (stage 만 고치는 갱신을 위해)
      kind = excluded.kind, novelty = coalesce(excluded.novelty, t.novelty), novelty_reason = coalesce(excluded.novelty_reason, t.novelty_reason),
      what_market_misses = coalesce(excluded.what_market_misses, t.what_market_misses), lag_months = coalesce(excluded.lag_months, t.lag_months),
      first_signal = coalesce(excluded.first_signal, t.first_signal), quiet_check = coalesce(excluded.quiet_check, t.quiet_check), updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

drop view if exists public.v_theses;
create view public.v_theses
with (security_invoker = true) as
select t.*,
       (select count(*) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key and e.direction = '+') as n_support,
       (select count(*) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key and e.direction = '-') as n_against,
       (select max(as_of) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key) as last_evidence_at
from ideas.theses t;

-- 2. 약한 신호 관찰 (테제 작업 1부) ---------------------------------------------------------------------------
create table if not exists ideas.weak_signals (
  signal_key     text primary key,                 -- 용어 슬러그 (예 hbf, cxl_kv_offload)
  term           text not null,                    -- 사람이 읽는 용어
  kind_guess     text,                             -- technology | component | material | standard | mechanism | data | structure | other
  ecosystem      text,                             -- hbm | optics | power | cross | other
  mechanism      text,                             -- 한 줄: 무엇이 어떻게 바뀌나 (숫자 있으면 숫자)
  consumes_more  text[] not null default '{}',     -- 늘리는 것 (부품·소재·장비, 자유 텍스트 또는 노드 id)
  consumes_less  text[] not null default '{}',     -- 줄이는 것
  mapped_node    text,                             -- 온톨로지 노드 id (없으면 null = 잔차)
  source_types   text[] not null default '{}',     -- paper | standard | conference | hiring | platform_release | model_release | filing | other
  lead_months    smallint,                         -- 이 출처 유형이 제품 수량에 앞서는 개월 (논문 24~48 · 표준 12~36 · 학회 12~24 · 채용 6~18 · 릴리스 3~12 · 공시 0~6)
  sources        jsonb not null default '[]',      -- [{url, title, date, source_type}]
  first_seen     date not null default current_date,
  last_seen      date not null default current_date,
  n_seen         integer not null default 1,
  status         text not null default 'watch' check (status in ('watch', 'promoted', 'dropped')),
  promoted_to    text,                             -- thesis_key 또는 온톨로지 노드 id
  note           text,
  model          text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index if not exists weak_signals_recent_idx on ideas.weak_signals (last_seen desc, n_seen desc);

-- 같은 signal_key 는 횟수·출처·출처 유형을 누적하고 마지막 본 날을 갱신한다. 상태는 명시했을 때만 바뀐다.
create or replace function ideas.put_weak_signals(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; seen date;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'signal_key';
    if k is null or k !~ '^[a-z0-9_]{2,60}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'signal_key 는 영문 소문자·숫자·_ 2~60자'); continue; end if;
    if length(coalesce(r->>'term', '')) < 2 or length(coalesce(r->>'mechanism', '')) < 10 then rej := rej || jsonb_build_object('i', i, 'reason', 'term·mechanism(10자 이상) 필수'); continue; end if;
    if jsonb_typeof(r->'sources') <> 'array' or jsonb_array_length(r->'sources') < 1
       or exists (select 1 from jsonb_array_elements(r->'sources') s where coalesce(s->>'url', '') !~ '^https?://') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'sources 1개 이상, 각각 url'); continue;
    end if;
    if coalesce(r->>'status', 'watch') not in ('watch', 'promoted', 'dropped') then rej := rej || jsonb_build_object('i', i, 'reason', 'status 는 watch | promoted | dropped'); continue; end if;
    seen := coalesce((r->>'seen_on')::date, current_date);
    insert into ideas.weak_signals as w (signal_key, term, kind_guess, ecosystem, mechanism, consumes_more, consumes_less, mapped_node, source_types, lead_months, sources,
                                         first_seen, last_seen, n_seen, status, promoted_to, note, model, updated_at)
    values (k, left(r->>'term', 120), r->>'kind_guess', r->>'ecosystem', left(r->>'mechanism', 400),
            coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'consumes_more', '[]'::jsonb)) x), '{}'),
            coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'consumes_less', '[]'::jsonb)) x), '{}'),
            r->>'mapped_node',
            coalesce((select array_agg(distinct s->>'source_type') from jsonb_array_elements(r->'sources') s where s->>'source_type' is not null), '{}'),
            (r->>'lead_months')::smallint, r->'sources', seen, seen, 1, coalesce(r->>'status', 'watch'), r->>'promoted_to', r->>'note', left(r->>'model', 60), now())
    on conflict (signal_key) do update set
      term = excluded.term, kind_guess = coalesce(excluded.kind_guess, w.kind_guess), ecosystem = coalesce(excluded.ecosystem, w.ecosystem),
      mechanism = excluded.mechanism,
      consumes_more = (select coalesce(array_agg(distinct x), '{}') from unnest(w.consumes_more || excluded.consumes_more) x),
      consumes_less = (select coalesce(array_agg(distinct x), '{}') from unnest(w.consumes_less || excluded.consumes_less) x),
      mapped_node = coalesce(excluded.mapped_node, w.mapped_node),
      source_types = (select coalesce(array_agg(distinct x), '{}') from unnest(w.source_types || excluded.source_types) x),
      lead_months = coalesce(least(w.lead_months, excluded.lead_months), w.lead_months, excluded.lead_months),
      sources = (select coalesce(jsonb_agg(distinct s), '[]'::jsonb) from jsonb_array_elements(w.sources || excluded.sources) s),
      first_seen = least(w.first_seen, excluded.first_seen), last_seen = greatest(w.last_seen, excluded.last_seen),
      n_seen = w.n_seen + 1,
      status = case when r ? 'status' then excluded.status else w.status end,
      promoted_to = coalesce(excluded.promoted_to, w.promoted_to), note = coalesce(excluded.note, w.note), model = coalesce(excluded.model, w.model), updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

create or replace view public.v_weak_signals
with (security_invoker = true) as
select signal_key, term, kind_guess, ecosystem, mechanism, consumes_more, consumes_less, mapped_node, source_types, lead_months, sources,
       first_seen, last_seen, n_seen, status, promoted_to, note,
       -- 승격 조건 (ADR-0026 결정 4): 출처 유형 둘 이상 또는 3주 안 재등장
       (cardinality(source_types) >= 2 or (n_seen >= 2 and last_seen - first_seen <= 21)) as promotable,
       mapped_node is null as unmapped
from ideas.weak_signals;

-- 3. 수집기 잔차: node_catalog 에 없던 용어 ------------------------------------------------------------------
create table if not exists ideas.unmapped_terms (
  term_key    text primary key,                    -- 소문자 슬러그
  term        text not null,
  kind_guess  text,                                -- technology | component | material | standard | company | mechanism | other
  ecosystem   text,
  context     text,                                -- 처음 본 문맥 한 줄
  issue_keys  text[] not null default '{}',
  first_seen  date not null default current_date,
  last_seen   date not null default current_date,
  n_seen      integer not null default 1,
  status      text not null default 'open' check (status in ('open', 'mapped', 'ignored')),
  mapped_node text,
  updated_at  timestamptz not null default now()
);
create index if not exists unmapped_terms_recent_idx on ideas.unmapped_terms (status, n_seen desc, last_seen desc);

create or replace function ideas.put_unmapped_terms(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; seen date;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := lower(regexp_replace(coalesce(r->>'term_key', r->>'term', ''), '[^a-zA-Z0-9가-힣]+', '_', 'g'));
    k := trim(both '_' from k);
    if length(k) < 2 or length(k) > 80 then rej := rej || jsonb_build_object('i', i, 'reason', 'term 2~80자'); continue; end if;
    if coalesce(r->>'status', 'open') not in ('open', 'mapped', 'ignored') then rej := rej || jsonb_build_object('i', i, 'reason', 'status 는 open | mapped | ignored'); continue; end if;
    seen := coalesce((r->>'seen_on')::date, current_date);
    insert into ideas.unmapped_terms as u (term_key, term, kind_guess, ecosystem, context, issue_keys, first_seen, last_seen, n_seen, status, mapped_node, updated_at)
    values (k, left(coalesce(r->>'term', k), 120), r->>'kind_guess', r->>'ecosystem', left(r->>'context', 300),
            coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'issue_keys', '[]'::jsonb)) x), '{}'),
            seen, seen, 1, coalesce(r->>'status', 'open'), r->>'mapped_node', now())
    on conflict (term_key) do update set
      kind_guess = coalesce(excluded.kind_guess, u.kind_guess), ecosystem = coalesce(excluded.ecosystem, u.ecosystem), context = coalesce(u.context, excluded.context),
      issue_keys = (select coalesce(array_agg(distinct x), '{}') from unnest(u.issue_keys || excluded.issue_keys) x),
      first_seen = least(u.first_seen, excluded.first_seen), last_seen = greatest(u.last_seen, excluded.last_seen), n_seen = u.n_seen + 1,
      status = case when r ? 'status' then excluded.status else u.status end, mapped_node = coalesce(excluded.mapped_node, u.mapped_node), updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

create or replace view public.v_unmapped_terms
with (security_invoker = true) as
select term_key, term, kind_guess, ecosystem, context, issue_keys, first_seen, last_seen, n_seen, status, mapped_node
from ideas.unmapped_terms;

-- 4. 권한 ----------------------------------------------------------------------------------------------------
revoke all on function ideas.put_theses(jsonb), ideas.put_weak_signals(jsonb), ideas.put_unmapped_terms(jsonb) from public;
revoke all on function ideas.put_theses(jsonb), ideas.put_weak_signals(jsonb), ideas.put_unmapped_terms(jsonb) from anon, authenticated;
grant execute on function ideas.put_theses(jsonb), ideas.put_weak_signals(jsonb), ideas.put_unmapped_terms(jsonb) to service_role;
grant select on public.v_theses, public.v_weak_signals, public.v_unmapped_terms to anon, authenticated;
grant select on ideas.weak_signals, ideas.unmapped_terms to anon, authenticated;
grant all on ideas.weak_signals, ideas.unmapped_terms to service_role;
alter table ideas.weak_signals enable row level security;
alter table ideas.unmapped_terms enable row level security;
drop policy if exists weak_signals_read on ideas.weak_signals;
create policy weak_signals_read on ideas.weak_signals for select to anon, authenticated using (true);
drop policy if exists unmapped_terms_read on ideas.unmapped_terms;
create policy unmapped_terms_read on ideas.unmapped_terms for select to anon, authenticated using (true);
