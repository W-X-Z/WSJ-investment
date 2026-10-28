-- 0021: 스스로 판단하고 개선하는 시스템 — 아이디어 판단(점수)·병목 관측치·가격 맥락·수집 상태. ADR-0017.
-- 적용 전에도 파이프라인·웹은 돈다 (점수·관측치·가격 맥락이 비어 보일 뿐). 다시 실행해도 안전하다.

-- 1) 아이디어 판단 기록: 10점 근거 점수와 내역, 노출 순도, 가격 맥락 스냅샷
alter table ideas.investment_ideas add column if not exists assessment jsonb;

-- 2) put_ideas 재정의 — 0020 과 같고 assessment 만 저장에 더한다
create or replace function ideas.put_ideas(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; closed int := 0; rej jsonb := '[]'::jsonb; reason text; is_new boolean; step jsonb; ev jsonb;
  run_id bigint;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  insert into ops.collector_runs (collector, status, params, runner_host) values ('ideas', 'running', jsonb_build_object('method', 'session'), 'claude-session')
  returning id into run_id;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1; reason := null;
    if coalesce(r->>'idea_key', '') !~ '^[0-9a-f]{12}$' then
      rej := rej || jsonb_build_object('i', i, 'reason', 'idea_key 형식'); continue;
    end if;

    if r->>'status' = 'closed' then
      update ideas.investment_ideas
         set status = 'closed', trend = 'weakened', close_reason = left(r->>'close_reason', 300), updated_at = now()
       where idea_key = r->>'idea_key' and status = 'active';
      if found then closed := closed + 1; else rej := rej || jsonb_build_object('i', i, 'reason', '닫을 활성 아이디어 없음'); end if;
      continue;
    end if;

    is_new := not exists (select 1 from ideas.investment_ideas where idea_key = r->>'idea_key');
    if coalesce(r->>'status', '') <> 'active' then reason := 'status';
    elsif coalesce(r->>'type', '') not in ('bottleneck', 'transition', 'confirmation', 'risk') then reason := 'type';
    elsif coalesce(r->>'trend', '') not in ('new', 'strengthened', 'weakened', 'unchanged') then reason := 'trend';
    elsif nullif(btrim(r->>'title'), '') is null or nullif(btrim(r->>'thesis'), '') is null then reason := 'title·thesis';
    elsif coalesce((r->>'stars')::int, 0) not between 1 and 3 then reason := 'stars';
    elsif coalesce(r->>'primary_company', '') !~ '^company:[a-z0-9_]+$' then reason := 'primary_company';
    elsif jsonb_typeof(r->'companies') <> 'array' or jsonb_array_length(r->'companies') = 0 then reason := 'companies';
    elsif jsonb_typeof(r->'chain') <> 'array' or jsonb_array_length(r->'chain') < 2 then reason := '근거 사슬 2단계 미만';
    elsif coalesce(r->>'method', '') not in ('session', 'llm') then reason := 'method';
    elsif (r->>'last_signal_at') is null or (r->>'last_signal_at')::date > current_date + 1 then reason := 'last_signal_at';
    elsif is_new and (r->>'last_signal_at')::date < current_date - 14 then reason := '새 아이디어는 14일 안의 최신 근거가 필요';
    elsif r ? 'assessment' and jsonb_typeof(r->'assessment') not in ('object', 'null') then reason := 'assessment 는 객체';
    end if;
    if reason is null then
      for step in select * from jsonb_array_elements(r->'chain') loop
        if nullif(btrim(step->>'claim'), '') is null or jsonb_typeof(step->'evidence') <> 'array' or jsonb_array_length(step->'evidence') = 0 then
          reason := '근거 없는 단계'; exit;
        end if;
        for ev in select * from jsonb_array_elements(step->'evidence') loop
          if coalesce(ev->>'url', '') !~ '^https://' or coalesce(ev->>'id', '') !~ '^[SG][0-9]+$' then reason := '근거 URL·id 형식'; exit; end if;
          if ideas.url_blocked(ev->>'url') then reason := '차단 출처: ' || (ev->>'url'); exit; end if;
        end loop;
        exit when reason is not null;
      end loop;
    end if;
    if reason is not null then rej := rej || jsonb_build_object('i', i, 'key', r->>'idea_key', 'reason', reason); continue; end if;

    insert into ideas.investment_ideas as t (
      idea_key, status, trend, type, title, thesis, stars, stars_reason, primary_company, companies, chain, risks, watch, what_changed,
      nodes, ecosystems, signal_refs, evidence_count, last_signal_at, updated_at, model, method, usage, assessment)
    values (
      r->>'idea_key', 'active', r->>'trend', r->>'type', left(btrim(r->>'title'), 120), left(btrim(r->>'thesis'), 600), (r->>'stars')::int,
      left(r->>'stars_reason', 300), r->>'primary_company', r->'companies', r->'chain', coalesce(r->'risks', '[]'::jsonb), coalesce(r->'watch', '[]'::jsonb),
      nullif(r->>'what_changed', ''),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'nodes', '[]'::jsonb)) x), '{}'),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'ecosystems', '[]'::jsonb)) x), '{}'),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'signal_refs', '[]'::jsonb)) x), '{}'),
      coalesce((r->>'evidence_count')::int, 0), (r->>'last_signal_at')::date, now(), r->>'model', r->>'method', r->'usage',
      nullif(r->'assessment', 'null'::jsonb))
    on conflict (idea_key) do update set
      status = excluded.status, trend = excluded.trend, type = excluded.type, title = excluded.title, thesis = excluded.thesis,
      stars = excluded.stars, stars_reason = excluded.stars_reason, primary_company = excluded.primary_company, companies = excluded.companies,
      chain = excluded.chain, risks = excluded.risks, watch = excluded.watch, what_changed = excluded.what_changed, nodes = excluded.nodes,
      ecosystems = excluded.ecosystems, signal_refs = excluded.signal_refs, evidence_count = excluded.evidence_count,
      last_signal_at = excluded.last_signal_at, updated_at = excluded.updated_at, model = excluded.model, method = excluded.method,
      usage = excluded.usage, close_reason = null, assessment = coalesce(excluded.assessment, t.assessment);
    ok := ok + 1;
  end loop;
  update ops.collector_runs set status = 'succeeded', finished_at = now(), rows_upserted = ok + closed,
         watermark = jsonb_build_object('upserted', ok, 'closed', closed, 'rejected', jsonb_array_length(rej))
   where id = run_id;
  return jsonb_build_object('upserted', ok, 'closed', closed, 'rejected', rej);
end $$;

-- 3) 판단만 다시 쓰기 — 손대지 않은 아이디어의 점수(근거 나이·가격 맥락)와 확인 일정 채점을 매일 고친다.
--    updated_at 을 바꾸지 않는다 (피드의 '바뀐 아이디어'에 끼지 않게). 행: {idea_key, assessment, watch?}
create or replace function ideas.put_assessments(rows jsonb) returns jsonb language plpgsql as $$
declare r jsonb; ok int := 0; rej jsonb := '[]'::jsonb; i int := 0;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    if jsonb_typeof(r->'assessment') <> 'object' then rej := rej || jsonb_build_object('i', i, 'reason', 'assessment 는 객체'); continue; end if;
    if r ? 'watch' and jsonb_typeof(r->'watch') <> 'array' then rej := rej || jsonb_build_object('i', i, 'reason', 'watch 는 배열'); continue; end if;
    update ideas.investment_ideas
       set assessment = r->'assessment', watch = coalesce(r->'watch', watch)
     where idea_key = r->>'idea_key' and status = 'active';
    if found then ok := ok + 1; else rej := rej || jsonb_build_object('i', i, 'reason', '활성 아이디어 없음: ' || coalesce(r->>'idea_key', '')); end if;
  end loop;
  return jsonb_build_object('updated', ok, 'rejected', rej);
end $$;

-- 4) 병목 상태 관측치 — 원문에서 확인한 숫자(가격 배수·리드타임·가동률·재고·수주잔고·평균단가)를 시계열로.
--    행: {indicator_id:'obs:…', label, unit, ecosystem, nodes[], companies[], source, source_url, note, as_of, value, change_pct?, yoy_pct?, meta?}
--    obs: 지표는 만들고 고칠 수 있다. 다른 지표는 출처가 FRED 인 것만 점을 더할 수 있다 (Actions 에서 막히는 출처를 세션이 채운다).
create or replace function ideas.put_observations(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; iid text; d date; v numeric; src text; u text; run_id bigint;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  insert into ops.collector_runs (collector, status, params, runner_host) values ('observations', 'running', '{}'::jsonb, 'claude-session')
  returning id into run_id;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    iid := r->>'indicator_id'; u := r->>'source_url';
    begin
      d := (r->>'as_of')::date; v := (r->>'value')::numeric;
    exception when others then
      rej := rej || jsonb_build_object('i', i, 'reason', 'as_of·value 형식'); continue;
    end;
    if d is null or v is null then rej := rej || jsonb_build_object('i', i, 'reason', 'as_of·value 필요'); continue; end if;
    if d > current_date + 1 or d < current_date - 1100 then rej := rej || jsonb_build_object('i', i, 'reason', 'as_of 는 최근 3년 안'); continue; end if;
    if coalesce(iid, '') ~ '^obs:[a-z0-9_]{3,60}$' then
      if nullif(btrim(r->>'label'), '') is null or nullif(btrim(r->>'source'), '') is null then
        rej := rej || jsonb_build_object('i', i, 'reason', 'label·source 필요'); continue;
      end if;
      if u is null or u !~ '^https://' then rej := rej || jsonb_build_object('i', i, 'reason', 'https source_url 필요'); continue; end if;
      if ideas.url_blocked(u) then rej := rej || jsonb_build_object('i', i, 'reason', '차단 출처: ' || u); continue; end if;
      if coalesce(r->>'ecosystem', 'cross') not in ('hbm', 'optics', 'power', 'cross') then rej := rej || jsonb_build_object('i', i, 'reason', 'ecosystem'); continue; end if;
      insert into ideas.indicators (indicator_id, label, category, unit, frequency, source, source_url, ecosystem, nodes, companies, note, updated_at)
      values (iid, left(btrim(r->>'label'), 120), 'observation', left(r->>'unit', 40), coalesce(nullif(r->>'frequency', ''), 'irregular'),
              left(r->>'source', 80), u, coalesce(r->>'ecosystem', 'cross'),
              coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'nodes', '[]'::jsonb)) x where x ~ '^[a-z_]+:[a-z0-9_]+$'), '{}'),
              coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'companies', '[]'::jsonb)) x where x ~ '^company:[a-z0-9_]+$'), '{}'),
              left(r->>'note', 300), now())
      on conflict (indicator_id) do update set
        label = excluded.label, unit = excluded.unit, source = excluded.source, source_url = excluded.source_url, ecosystem = excluded.ecosystem,
        nodes = excluded.nodes, companies = excluded.companies, note = coalesce(excluded.note, ideas.indicators.note), updated_at = now()
      where ideas.indicators.category = 'observation';
    else
      select source into src from ideas.indicators where indicator_id = iid;
      if src is null or src <> 'FRED' then rej := rej || jsonb_build_object('i', i, 'reason', 'obs: 지표 또는 FRED 지표만: ' || coalesce(iid, '')); continue; end if;
    end if;
    insert into ideas.indicator_points (indicator_id, as_of, value, change_pct, yoy_pct, meta)
    values (iid, d, v, nullif(r->>'change_pct', '')::numeric, nullif(r->>'yoy_pct', '')::numeric,
            coalesce(r->'meta', '{}'::jsonb) || jsonb_build_object('source_url', u, 'recorded_by', 'claude', 'recorded_at', now()))
    on conflict (indicator_id, as_of) do update set value = excluded.value, change_pct = excluded.change_pct, yoy_pct = excluded.yoy_pct,
      meta = excluded.meta, fetched_at = now();
    ok := ok + 1;
  end loop;
  update ops.collector_runs set status = 'succeeded', finished_at = now(), rows_upserted = ok,
         watermark = jsonb_build_object('points', ok, 'rejected', jsonb_array_length(rej))
   where id = run_id;
  return jsonb_build_object('points', ok, 'rejected', rej);
end $$;

-- 5) 공개 뷰: 아이디어에 판단을 끝에 붙인다 (프론트 계약: 열은 끝에만 추가)
create or replace view public.v_investment_ideas
with (security_invoker = true) as
select idea_key, status, trend, type, title, thesis, stars, stars_reason, primary_company, companies, chain, risks, watch,
       what_changed, nodes, ecosystems, signal_refs, evidence_count, last_signal_at, first_seen, updated_at, revision, model, method,
       coalesce(last_signal_at, updated_at::date) < current_date - 21 as stale,
       assessment
from ideas.investment_ideas
where status = 'active';

-- 6) 가격 맥락: 종목별 최근 종가와 1·3·12개월 수익률, 1년 고점 대비, 거래량 배수 (5일 / 이전 60일).
--    ticker = 미국은 티커, 그 밖은 '거래소:코드' (예 TWSE:2467, KOSDAQ:086390, TSE:5803, SSE:603256, HKEX:6869).
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
       count(*) as points
from p
group by ticker;

-- 7) 수집 상태 (최근 45일) — 시스템 점검 화면
create or replace view public.v_collector_runs
with (security_invoker = true) as
select id, collector, status, started_at, finished_at, rows_upserted, left(error, 300) as error
from ops.collector_runs
where started_at > now() - interval '45 days';

-- 8) 등록된 지표 전체 (값이 없는 지표도) — 점검이 '빈 지표'를 찾는다
create or replace view public.v_indicator_registry
with (security_invoker = true) as
select indicator_id, label, category, unit, frequency, source, source_url, ecosystem, nodes, companies, updated_at
from ideas.indicators;

-- 권한
revoke all on function ideas.put_ideas(jsonb), ideas.put_assessments(jsonb), ideas.put_observations(jsonb) from public;
revoke all on function ideas.put_ideas(jsonb), ideas.put_assessments(jsonb), ideas.put_observations(jsonb) from anon, authenticated;
grant execute on function ideas.put_ideas(jsonb), ideas.put_assessments(jsonb), ideas.put_observations(jsonb) to service_role;
grant select on public.v_investment_ideas, public.v_price_context, public.v_collector_runs, public.v_indicator_registry to anon, authenticated;
