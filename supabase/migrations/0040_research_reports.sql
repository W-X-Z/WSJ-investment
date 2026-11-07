-- 0040: 지식 세 구조의 데이터 바닥 — (1) 원천 = ideas.clues(+clue_texts) 와 행에 붙인 사실(facts)
--                                    (2) 산업 그래프 = core.graph_nodes·graph_edges (원본은 Git 패치, graph-sync 가 옮긴다 — 이 파일은 손대지 않는다)
--                                    (3) 리서치 리포트 = research.reports — AI 가 계산·해석·판단한 모든 것
-- 실행: Supabase SQL 편집기 (리드). 0039 뒤. 파이프라인 코드는 이 마이그레이션 전에도 돈다 (새 칸·함수가 없으면 옛 방식으로 쓴다).
--
-- 호출 경로 (기존 ideas.put_* 와 같다)
--   예약 Claude 세션: Supabase MCP execute_sql → select ideas.put_research_sources($j$[…]$j$::jsonb);  select research.put_reports(…);
--   GitHub Actions:   PostgREST RPC (SUPABASE_SECRET_KEY = service_role) → POST /rest/v1/rpc/put_reports  + 헤더 Content-Profile: research
--                     (ideas.* 는 Content-Profile: ideas). research 스키마는 아래 4) 에서 PostgREST 노출 목록에 더한다.
--   함수는 security invoker (기존 put_* 와 같음) — service_role 만 실행 권한, 웹(anon)은 public.v_reports·v_clues 로 읽기만.

-- ── 1) 원천: 단서 행의 사실 ─────────────────────────────────────────────────────────────
-- facts 원소: {"text": "필수, 빈 문자열 안 됨", "entity": "그래프 노드 id (company:be · segment:sofc)", "value": 숫자, "unit": "MW",
--             "as_of": "YYYY-MM-DD", "loc": "원문 위치 (p.12 · 표 3)", "by": "뽑은 주체 (작업·모델 이름)"} — text 밖은 모두 선택.
alter table ideas.clues add column if not exists facts jsonb not null default '[]'::jsonb;
create index if not exists clues_facts_idx on ideas.clues using gin (facts jsonb_path_ops);

-- 공개 읽기 뷰에 facts 를 끝에 더한다 (기존 칸 순서 그대로)
create or replace view public.v_clues
with (security_invoker = true) as
select clue_id, url, title, summary, published_at, seen_at, source_id, source_name, source_kind, lang, region, companies, nodes, note,
       facts
from ideas.clues
where relevant and seen_at > now() - interval '120 days';

-- 사실 하나 검사 — 문제가 없으면 null, 있으면 이유
create or replace function ideas.fact_error(f jsonb) returns text language sql immutable as $$
  select case
    when f is null or jsonb_typeof(f) <> 'object' then '사실은 객체'
    when jsonb_typeof(f->'text') is distinct from 'string' or btrim(f->>'text') = '' then 'text 필수 (빈 문자열 안 됨)'
    when f ? 'entity' and jsonb_typeof(f->'entity') <> 'null'
         and (jsonb_typeof(f->'entity') <> 'string' or (f->>'entity') !~ '^[a-z_]+:[A-Za-z0-9_.:-]+$') then 'entity 는 그래프 노드 id (kind:slug)'
    when f ? 'value' and jsonb_typeof(f->'value') not in ('number', 'null') then 'value 는 숫자'
    when f ? 'unit' and jsonb_typeof(f->'unit') not in ('string', 'null') then 'unit 은 문자열'
    when f ? 'as_of' and jsonb_typeof(f->'as_of') <> 'null' and coalesce(f->>'as_of', '') !~ '^\d{4}-\d{2}-\d{2}$' then 'as_of 는 YYYY-MM-DD'
    when f ? 'loc' and jsonb_typeof(f->'loc') not in ('string', 'null') then 'loc 은 문자열'
    when f ? 'by' and jsonb_typeof(f->'by') not in ('string', 'null') then 'by 는 문자열'
  end
$$;

-- 사실 배열 검사 — 첫 문제만 'facts[i]: 이유' 로
create or replace function ideas.facts_error(facts jsonb) returns text language sql immutable as $$
  select case
    when facts is null or jsonb_typeof(facts) <> 'array' then 'facts 는 배열'
    else (select format('facts[%s]: %s', t.o - 1, ideas.fact_error(t.f))
            from jsonb_array_elements(facts) with ordinality as t(f, o)
           where ideas.fact_error(t.f) is not null
           order by t.o limit 1)
  end
$$;

-- 중복 판정 키: 앞뒤 공백·연속 공백·대소문자를 무시한 text
create or replace function ideas.fact_key(t text) returns text language sql immutable as $$
  select nullif(lower(regexp_replace(btrim(coalesce(t, '')), '\s+', ' ', 'g')), '')
$$;

-- cur 뒤에 add 를 붙인다. text 가 이미 있는 사실은 건너뛴다 (add 안의 중복도). null 칸은 빼고 text 는 다듬어 저장한다.
create or replace function ideas.merge_facts(cur jsonb, add jsonb) returns jsonb language plpgsql immutable as $$
declare
  out_ jsonb := case when jsonb_typeof(cur) = 'array' then cur else '[]'::jsonb end;
  seen text[];
  f jsonb; k text;
begin
  select coalesce(array_agg(ideas.fact_key(x->>'text')), '{}') into seen from jsonb_array_elements(out_) x;
  if add is null or jsonb_typeof(add) <> 'array' then return out_; end if;
  for f in select * from jsonb_array_elements(add) loop
    k := ideas.fact_key(f->>'text');
    if k is null or k = any (seen) then continue; end if;
    out_ := out_ || jsonb_build_array(jsonb_strip_nulls(f) || jsonb_build_object('text', btrim(f->>'text')));
    seen := seen || k;
  end loop;
  return out_;
end $$;

-- 사실의 entity 중 그래프 노드 id 모양인 것 → 단서 nodes 태그로 (태깅일 뿐, 거르지 않는다)
create or replace function ideas.fact_nodes(facts jsonb) returns text[] language sql immutable as $$
  select coalesce(array_agg(distinct f->>'entity' order by f->>'entity'), '{}')
    from jsonb_array_elements(case when jsonb_typeof(facts) = 'array' then facts else '[]'::jsonb end) f
   where (f->>'entity') ~ '^[a-z_]+:[A-Za-z0-9_.:-]+$'
$$;

-- put_research_sources: 에이전트가 조사하며 읽은 원천 문서를 단서로 남긴다.
-- rows: [{url(필수 http/https), title(필수), published_at, source_name, summary, source_kind(기본 'agent_research'), facts[]}]
-- 새 URL → 단서 한 행 (source_id 'agent_research', relevant true). 같은 URL 단서가 있으면 facts 를 합친다 (같은 text 는 건너뜀),
-- 비어 있던 summary·published_at 만 채우고, 리포트가 인용할 수 있게 relevant 를 true 로 둔다 (수집기가 버린 글도 에이전트가 근거로 쓰면 공개된다).
-- 반환: {ok, rejected:[{i, reason}], ids:[{i, clue_id}]} — i 는 1부터.
create or replace function ideas.put_research_sources(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; ids jsonb := '[]'::jsonb;
  u text; t text; sk text; ts timestamptz; fs jsonb; why text; bad boolean; cid bigint;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    if jsonb_typeof(r) <> 'object' then rej := rej || jsonb_build_object('i', i, 'reason', '행은 객체'); continue; end if;
    u := btrim(coalesce(r->>'url', ''));
    if u !~* '^https?://[^\s/]+' then rej := rej || jsonb_build_object('i', i, 'reason', 'url 필수 (http/https 주소)'); continue; end if;
    t := btrim(coalesce(r->>'title', ''));
    if t = '' then rej := rej || jsonb_build_object('i', i, 'reason', 'title 필수'); continue; end if;
    sk := coalesce(nullif(btrim(r->>'source_kind'), ''), 'agent_research');
    if sk !~ '^[a-z_]{2,40}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'source_kind 는 영문 소문자·_ 2~40자'); continue; end if;
    ts := null; bad := false;
    if nullif(btrim(r->>'published_at'), '') is not null then
      bad := btrim(r->>'published_at') !~ '^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}(:?\d{2})?)?$';
    end if;
    if not bad and nullif(btrim(r->>'published_at'), '') is not null then
      begin
        ts := (r->>'published_at')::timestamptz;
      exception when others then
        bad := true;
      end;
    end if;
    if bad then rej := rej || jsonb_build_object('i', i, 'reason', 'published_at 은 날짜 (YYYY-MM-DD 또는 ISO 시각)'); continue; end if;
    fs := case when r ? 'facts' and jsonb_typeof(r->'facts') <> 'null' then r->'facts' else '[]'::jsonb end;
    why := ideas.facts_error(fs);
    if why is not null then rej := rej || jsonb_build_object('i', i, 'reason', why); continue; end if;
    insert into ideas.clues as c (url, title, summary, published_at, source_id, source_name, source_kind, relevant, nodes, facts, extra)
    values (u, left(t, 400), left(nullif(btrim(r->>'summary'), ''), 2000), ts, 'agent_research',
            coalesce(nullif(btrim(r->>'source_name'), ''), split_part(split_part(u, '://', 2), '/', 1)), sk, true,
            ideas.fact_nodes(fs), ideas.merge_facts('[]'::jsonb, fs), jsonb_build_object('layer', 'agent_research'))
    on conflict (url) do update set
      facts        = ideas.merge_facts(c.facts, excluded.facts),
      nodes        = array(select distinct x from unnest(c.nodes || excluded.nodes) x order by x),
      summary      = coalesce(c.summary, excluded.summary),
      published_at = coalesce(c.published_at, excluded.published_at),
      relevant     = true
    returning c.clue_id into cid;
    ok := ok + 1;
    ids := ids || jsonb_build_object('i', i, 'clue_id', cid);
  end loop;
  return jsonb_build_object('ok', ok, 'rejected', rej, 'ids', ids);
end $$;

-- put_clue_facts: 이미 있는 단서에 사실을 덧붙인다 (같은 text 는 건너뜀). rows: [{clue_id, facts[]}]
-- 반환: {ok, rejected:[{i, reason}], added: 새로 붙은 사실 수}
create or replace function ideas.put_clue_facts(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; added int := 0; rej jsonb := '[]'::jsonb;
  cid bigint; fs jsonb; why text; before_n int; after_n int;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    if jsonb_typeof(r) <> 'object' then rej := rej || jsonb_build_object('i', i, 'reason', '행은 객체'); continue; end if;
    if coalesce(r->>'clue_id', '') !~ '^\d{1,18}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'clue_id 는 정수'); continue; end if;
    cid := (r->>'clue_id')::bigint;
    fs := r->'facts';
    why := ideas.facts_error(fs);
    if why is not null then rej := rej || jsonb_build_object('i', i, 'reason', why); continue; end if;
    select jsonb_array_length(facts) into before_n from ideas.clues where clue_id = cid for update;
    if not found then rej := rej || jsonb_build_object('i', i, 'reason', 'clue_id 없음'); continue; end if;
    update ideas.clues set facts = ideas.merge_facts(facts, fs),
                           nodes = array(select distinct x from unnest(nodes || ideas.fact_nodes(fs)) x order by x)
     where clue_id = cid
     returning jsonb_array_length(facts) into after_n;
    ok := ok + 1;
    added := added + (after_n - before_n);
  end loop;
  return jsonb_build_object('ok', ok, 'rejected', rej, 'added', added);
end $$;

revoke all on function ideas.fact_error(jsonb), ideas.facts_error(jsonb), ideas.fact_key(text), ideas.merge_facts(jsonb, jsonb),
                       ideas.fact_nodes(jsonb), ideas.put_research_sources(jsonb), ideas.put_clue_facts(jsonb) from public, anon, authenticated;
grant execute on function ideas.fact_error(jsonb), ideas.facts_error(jsonb), ideas.fact_key(text), ideas.merge_facts(jsonb, jsonb),
                          ideas.fact_nodes(jsonb), ideas.put_research_sources(jsonb), ideas.put_clue_facts(jsonb) to service_role;
grant select on public.v_clues to anon, authenticated;

-- ── 2) 재무: 현금흐름·재무상태·주식수 칸 (SEC companyfacts · OpenDART) ───────────────────────────
-- 기존 칸·기본키 그대로 — 새 칸은 모두 null 허용이라 옛 수집기 행도 그대로 들어간다.
alter table raw.company_fundamentals
  add column if not exists operating_cash_flow numeric,   -- 영업활동 현금흐름 (기간: ttm·fy·q)
  add column if not exists capex               numeric,   -- 유형자산 취득 (양수 = 지출)
  add column if not exists cash                numeric,   -- 현금및현금성자산 (기말)
  add column if not exists total_debt          numeric,   -- 단기+장기 차입금·사채 (기말, 리스부채 제외)
  add column if not exists diluted_shares      numeric,   -- 희석 가중평균 주식수 (기간, 미국)
  add column if not exists shares_outstanding  numeric;   -- 기말 유통 보통주식수 (미국 dei · 한국 DART 주식총수 현황)

-- v_company_fundamentals: 끝에 새 칸을 더한다 (앞 칸 순서·이름 그대로 — 웹·파이프라인 호환)
create or replace view public.v_company_fundamentals
with (security_invoker = true) as
with latest as (
  select distinct on (company_id) company_id, period, period_end, currency, revenue, gross_profit, operating_income, net_income, source, source_url, note,
         operating_cash_flow, capex, cash, total_debt, diluted_shares
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
       case when l.net_income > 0 then round(c.market_cap_local / l.net_income, 1) end as pe,
       l.operating_cash_flow, l.capex,
       l.operating_cash_flow - l.capex as free_cash_flow,
       l.cash, l.total_debt, l.diluted_shares
from latest l
left join prior p on p.company_id = l.company_id
left join public.v_company_facts c on c.company_id = l.company_id
left join ref.fx_rates x on x.currency = l.currency;
grant select on public.v_company_fundamentals to anon, authenticated;

-- ── 3) 리서치 리포트 ────────────────────────────────────────────────────────────────────
create schema if not exists research;
comment on schema research is '리서치 리포트 — AI 가 계산·해석·판단한 모든 것 (스크린·산업·기업·아이디어·검증). 원천(ideas.clues)과 산업 그래프(core.graph_*)를 인용한다.';
grant usage on schema research to anon, authenticated, service_role;
alter default privileges in schema research grant select on tables to anon, authenticated;
alter default privileges in schema research grant all on tables to service_role;
alter default privileges in schema research grant all on sequences to service_role;

create table if not exists research.reports (
  report_id   text primary key check (report_id ~ '^[a-z0-9_:.-]{6,80}$'),   -- 예: idea:be_sofc_2026q4 · screen:2026-11-08
  kind        text not null check (kind in ('screen', 'industry', 'company', 'idea', 'verification')),
  title       text not null,
  subjects    text[] not null default '{}',                                  -- 그래프 노드 id (company:be · segment:sofc)
  as_of       date not null,                                                 -- 리포트가 기준으로 삼은 날
  stars       smallint check (stars between 1 and 5),                        -- idea 는 필수
  verdict     text,                                                          -- 한 줄 판단 (idea 는 필수)
  body        jsonb not null check (jsonb_typeof(body) = 'object'),          -- 본문 (형식은 kind 마다 작업 문서가 정한다)
  cites       bigint[] not null default '{}',                                -- 인용한 원천 ideas.clues.clue_id
  notion_url  text,
  created_by  text,                                                          -- 쓴 작업·모델
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists reports_subjects_idx on research.reports using gin (subjects);
create index if not exists reports_kind_asof_idx on research.reports (kind, as_of desc);
create index if not exists reports_cites_idx on research.reports using gin (cites);
alter table research.reports enable row level security;
drop policy if exists reports_read on research.reports;
create policy reports_read on research.reports for select to anon, authenticated using (true);
grant select on research.reports to anon, authenticated;
grant all on research.reports to service_role;

-- put_reports: report_id 로 upsert. rows: [{report_id, kind, title, subjects[], as_of, stars, verdict, body{}, cites[], notion_url, created_by}]
-- 검사: report_id 형식 · kind · title · as_of(날짜) · body 객체 · stars 1~5 · kind='idea' 면 stars·verdict 필수 · subjects 문자열 배열 · cites 는 있는 clue_id.
-- 고칠 때 빠진 선택 칸(subjects·stars·verdict·cites·notion_url·created_by)은 이전 값을 둔다. 반환: {ok, rejected:[{i, reason}]}
create or replace function research.put_reports(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb;
  k text; kd text; t text; d date; st smallint; vd text; subj text[]; cts bigint[]; nu text; bad boolean;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    if jsonb_typeof(r) <> 'object' then rej := rej || jsonb_build_object('i', i, 'reason', '행은 객체'); continue; end if;
    k := r->>'report_id';
    if k is null or k !~ '^[a-z0-9_:.-]{6,80}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'report_id 는 영문 소문자·숫자·_:.- 6~80자'); continue; end if;
    kd := r->>'kind';
    if kd is null or kd not in ('screen', 'industry', 'company', 'idea', 'verification') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'kind 는 screen|industry|company|idea|verification'); continue;
    end if;
    t := btrim(coalesce(r->>'title', ''));
    if t = '' or length(t) > 200 then rej := rej || jsonb_build_object('i', i, 'reason', 'title 1~200자'); continue; end if;
    d := null; bad := coalesce(r->>'as_of', '') !~ '^\d{4}-\d{2}-\d{2}$';
    if not bad then
      begin
        d := (r->>'as_of')::date;
      exception when others then
        bad := true;
      end;
    end if;
    if bad then rej := rej || jsonb_build_object('i', i, 'reason', 'as_of 는 YYYY-MM-DD'); continue; end if;
    if jsonb_typeof(r->'body') is distinct from 'object' then rej := rej || jsonb_build_object('i', i, 'reason', 'body 는 객체'); continue; end if;
    st := null;
    if r ? 'stars' and jsonb_typeof(r->'stars') <> 'null' then
      if jsonb_typeof(r->'stars') <> 'number' or (r->>'stars') !~ '^[1-5](\.0+)?$' then
        rej := rej || jsonb_build_object('i', i, 'reason', 'stars 는 1~5 정수'); continue;
      end if;
      st := (r->>'stars')::numeric::smallint;
    end if;
    vd := nullif(btrim(r->>'verdict'), '');
    if kd = 'idea' and (st is null or vd is null) then rej := rej || jsonb_build_object('i', i, 'reason', 'idea 는 stars·verdict 필수'); continue; end if;
    subj := null;
    if r ? 'subjects' and jsonb_typeof(r->'subjects') <> 'null' then
      if jsonb_typeof(r->'subjects') <> 'array'
         or exists (select 1 from jsonb_array_elements(r->'subjects') x where jsonb_typeof(x) <> 'string' or btrim(x #>> '{}') = '') then
        rej := rej || jsonb_build_object('i', i, 'reason', 'subjects 는 문자열 배열 (그래프 노드 id)'); continue;
      end if;
      subj := array(select distinct btrim(x) from jsonb_array_elements_text(r->'subjects') x order by 1);
    end if;
    cts := null;
    if r ? 'cites' and jsonb_typeof(r->'cites') <> 'null' then
      if jsonb_typeof(r->'cites') <> 'array'
         or exists (select 1 from jsonb_array_elements(r->'cites') x where jsonb_typeof(x) <> 'number' or (x #>> '{}') !~ '^\d{1,18}$') then
        rej := rej || jsonb_build_object('i', i, 'reason', 'cites 는 clue_id 정수 배열'); continue;
      end if;
      cts := array(select distinct (x)::bigint from jsonb_array_elements_text(r->'cites') x order by 1);
      if exists (select 1 from unnest(cts) c where not exists (select 1 from ideas.clues cl where cl.clue_id = c)) then
        rej := rej || jsonb_build_object('i', i, 'reason', 'cites 에 없는 clue_id (ideas.put_research_sources 로 먼저 남긴다)'); continue;
      end if;
    end if;
    nu := nullif(btrim(r->>'notion_url'), '');
    if nu is not null and nu !~* '^https?://' then rej := rej || jsonb_build_object('i', i, 'reason', 'notion_url 은 http/https 주소'); continue; end if;
    insert into research.reports as o (report_id, kind, title, subjects, as_of, stars, verdict, body, cites, notion_url, created_by, updated_at)
    values (k, kd, t, coalesce(subj, '{}'), d, st, vd, r->'body', coalesce(cts, '{}'), nu, left(nullif(btrim(r->>'created_by'), ''), 80), now())
    on conflict (report_id) do update set
      kind       = excluded.kind,
      title      = excluded.title,
      as_of      = excluded.as_of,
      body       = excluded.body,
      subjects   = case when r ? 'subjects' then excluded.subjects else o.subjects end,
      stars      = case when r ? 'stars' then excluded.stars else o.stars end,
      verdict    = case when r ? 'verdict' then excluded.verdict else o.verdict end,
      cites      = case when r ? 'cites' then excluded.cites else o.cites end,
      notion_url = case when r ? 'notion_url' then excluded.notion_url else o.notion_url end,
      created_by = case when r ? 'created_by' then excluded.created_by else o.created_by end,
      updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('ok', ok, 'rejected', rej);
end $$;
revoke all on function research.put_reports(jsonb) from public, anon, authenticated;
grant execute on function research.put_reports(jsonb) to service_role;

-- 읽기 뷰 (웹·작업 공용)
create or replace view public.v_reports
with (security_invoker = true) as
select report_id, kind, title, subjects, as_of, stars, verdict, body, cites, notion_url, created_by, created_at, updated_at
from research.reports;
grant select on public.v_reports to anon, authenticated;

-- ── 4) PostgREST 노출: research 스키마를 더한다 (0010 이 ideas 를 더한 방식 그대로) ───────────────────
-- 적용 전 값(2026-11-08 확인): 'public, graphql_public, raw, core, ops, ideas'
alter role authenticator set pgrst.db_schemas = 'public, graphql_public, raw, core, ops, ideas, research';
notify pgrst, 'reload config';
notify pgrst, 'reload schema';
