-- 0030: 매일 테제 사슬 (ADR-0027) — 주간 테제 작업과 매일 사슬을 합친다. 테제에 크기(macro · micro)·부모·가장 약한 고리·조사 결과를 두고,
-- 매일 발굴한 micro 테제를 조사(반박 우선)하는 큐와, 반증 기한·첫 신호가 다가온 테제를 감시하는 큐를 만든다.
-- 실행: Supabase SQL 편집기 (사용자). 0029 뒤.

-- 1. theses 확장 ----------------------------------------------------------------------------------------------
alter table ideas.theses
  add column if not exists scale         text not null default 'macro' check (scale in ('macro', 'micro')),
  add column if not exists parent_key    text references ideas.theses (thesis_key) on delete set null,
  add column if not exists weakest_link  text,      -- 조사가 가장 먼저 깨 보아야 할 고리 한 문장 (micro 필수)
  add column if not exists research      jsonb,     -- {verdict, summary, sources[], event_ids[], checked_at}
  add column if not exists researched_at timestamptz,
  add column if not exists origin        text check (origin in ('decompose', 'weak_signal', 'issue_path', 'filing', 'residual', 'manual'));  -- 출발점 (성적표: 출발점별 정밀도)

create or replace function ideas.put_theses(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; kind_ text; st smallint; is_new boolean; scale_ text; cur ideas.theses%rowtype;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'thesis_key';
    if k is null or k !~ '^[a-z0-9_]{6,60}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'thesis_key 는 영문 소문자·숫자·_ 6~60자'); continue; end if;
    select * into cur from ideas.theses t where t.thesis_key = k;
    is_new := not found;
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
    kind_ := coalesce(r->>'kind', cur.kind, 'thesis');
    if kind_ not in ('thesis', 'regime') then rej := rej || jsonb_build_object('i', i, 'reason', 'kind 는 thesis | regime'); continue; end if;
    scale_ := coalesce(r->>'scale', cur.scale, 'macro');
    if scale_ not in ('macro', 'micro') then rej := rej || jsonb_build_object('i', i, 'reason', 'scale 은 macro | micro'); continue; end if;
    st := coalesce((r->>'stage')::smallint, 0);
    if is_new and kind_ = 'thesis' and st > 1 then
      rej := rej || jsonb_build_object('i', i, 'reason', '새 테제는 stage 0~1 — 공급 반응이 이미 보이면 kind=regime (체제 기록) 으로'); continue;
    end if;
    if kind_ = 'thesis' and (
         coalesce(r->>'novelty', cur.novelty, '') not in ('new_technology', 'new_data', 'new_issue', 'new_structure', 'analog')
      or length(coalesce(r->>'novelty_reason', cur.novelty_reason, '')) < 10
      or length(coalesce(r->>'what_market_misses', cur.what_market_misses, '')) < 10) then
      rej := rej || jsonb_build_object('i', i, 'reason', 'kind=thesis 는 novelty(new_technology|new_data|new_issue|new_structure|analog)·novelty_reason·what_market_misses 필수'); continue;
    end if;
    -- micro: 가장 약한 고리 + 소·중형 primary 1개 이상(size_band micro|small|mid) + 6개월 안의 반증 기한 1개 이상 (작은 테제는 빨리 판정한다)
    if scale_ = 'micro' and kind_ = 'thesis' and (
         length(coalesce(r->>'weakest_link', cur.weakest_link, '')) < 10
      or not exists (select 1 from jsonb_array_elements(r->'beneficiaries') b
                      where b->>'role' = 'primary' and b->>'company' like 'company:%' and b->>'size_band' in ('micro', 'small', 'mid'))
      or not exists (select 1 from jsonb_array_elements(r->'falsifiers') f where (f->>'due')::date <= current_date + 190)) then
      rej := rej || jsonb_build_object('i', i, 'reason', 'micro 테제는 weakest_link(10자+)·소·중형 primary 1개+(size_band micro|small|mid)·6개월 안 반증 기한 1개+ 필수'); continue;
    end if;
    if r->>'origin' is not null and r->>'origin' not in ('decompose', 'weak_signal', 'issue_path', 'filing', 'residual', 'manual') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'origin 은 decompose|weak_signal|issue_path|filing|residual|manual'); continue;
    end if;
    if r->>'parent_key' is not null and not exists (select 1 from ideas.theses p where p.thesis_key = r->>'parent_key') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'parent_key 테제 없음'); continue;
    end if;
    insert into ideas.theses as t (thesis_key, title, statement, ecosystem, chain, drivers, beneficiaries, losers, falsifiers, stage, stage_reason, status, close_reason, benchmark, model, method,
                                   kind, novelty, novelty_reason, what_market_misses, lag_months, first_signal, quiet_check, scale, parent_key, weakest_link, origin, updated_at)
    values (k, left(r->>'title', 160), r->>'statement', r->>'ecosystem', r->'chain', r->'drivers', r->'beneficiaries', coalesce(r->'losers', '[]'::jsonb), r->'falsifiers',
            st, r->>'stage_reason', coalesce(r->>'status', 'active'), r->>'close_reason', r->>'benchmark', left(r->>'model', 60), left(r->>'method', 20),
            kind_, r->>'novelty', r->>'novelty_reason', r->>'what_market_misses', (r->>'lag_months')::smallint, r->'first_signal', r->'quiet_check',
            scale_, r->>'parent_key', r->>'weakest_link', r->>'origin', now())
    on conflict (thesis_key) do update set title = excluded.title, statement = excluded.statement, ecosystem = excluded.ecosystem, chain = excluded.chain, drivers = excluded.drivers,
      beneficiaries = excluded.beneficiaries, losers = excluded.losers, falsifiers = excluded.falsifiers, stage = excluded.stage, stage_reason = excluded.stage_reason,
      status = excluded.status, close_reason = excluded.close_reason, benchmark = excluded.benchmark, model = excluded.model, method = excluded.method,
      kind = excluded.kind, novelty = coalesce(excluded.novelty, t.novelty), novelty_reason = coalesce(excluded.novelty_reason, t.novelty_reason),
      what_market_misses = coalesce(excluded.what_market_misses, t.what_market_misses), lag_months = coalesce(excluded.lag_months, t.lag_months),
      first_signal = coalesce(excluded.first_signal, t.first_signal), quiet_check = coalesce(excluded.quiet_check, t.quiet_check),
      scale = excluded.scale, parent_key = coalesce(excluded.parent_key, t.parent_key), weakest_link = coalesce(excluded.weakest_link, t.weakest_link),
      origin = coalesce(excluded.origin, t.origin), updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

-- 2. 테제 조사 (가장 약한 고리를 반박 우선으로) --------------------------------------------------------------------
-- verdict: confirmed · partial · unconfirmed · no_data · refuted. refuted 이고 stage 0 인 micro 는 닫는다 (작은 테제는 빨리 죽인다). macro 는 근거(−)만 남고 단계 판정은 verify 가.
create or replace function ideas.put_thesis_research(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; closed int := 0; rej jsonb := '[]'::jsonb; k text; v text;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'thesis_key'; v := r->>'verdict';
    if not exists (select 1 from ideas.theses where thesis_key = k) then rej := rej || jsonb_build_object('i', i, 'reason', '테제 없음'); continue; end if;
    if coalesce(v, '') not in ('confirmed', 'partial', 'unconfirmed', 'no_data', 'refuted') then rej := rej || jsonb_build_object('i', i, 'reason', 'verdict 는 confirmed|partial|unconfirmed|no_data|refuted'); continue; end if;
    if length(coalesce(r->>'summary', '')) < 10 then rej := rej || jsonb_build_object('i', i, 'reason', 'summary 10자 이상'); continue; end if;
    if v in ('confirmed', 'partial', 'refuted') and (jsonb_typeof(r->'sources') <> 'array' or jsonb_array_length(r->'sources') < 1) then
      rej := rej || jsonb_build_object('i', i, 'reason', 'confirmed·partial·refuted 는 sources 1개 이상'); continue;
    end if;
    update ideas.theses set research = jsonb_build_object('verdict', v, 'summary', left(r->>'summary', 1200), 'sources', coalesce(r->'sources', '[]'::jsonb),
                                                          'event_ids', coalesce(r->'event_ids', '[]'::jsonb), 'checked_at', now(), 'model', r->>'model'),
                            researched_at = now(), updated_at = now()
     where thesis_key = k;
    insert into ideas.thesis_evidence (thesis_key, as_of, direction, what, ref, weight)
    values (k, current_date, case v when 'refuted' then '-' when 'confirmed' then '+' when 'partial' then '+' else '0' end,
            left('조사: ' || v || ' — ' || (r->>'summary'), 400), jsonb_build_object('research', true, 'url', coalesce(r->'sources'->0->>'url', '')),
            case v when 'refuted' then 3 when 'confirmed' then 2 else 1 end);
    if v = 'refuted' then
      update ideas.theses set status = 'closed', close_reason = left('조사에서 반박: ' || (r->>'summary'), 400), updated_at = now()
       where thesis_key = k and stage = 0 and kind = 'thesis' and scale = 'micro';
      if found then closed := closed + 1; end if;
    end if;
    ok := ok + 1;
  end loop;
  return jsonb_build_object('updated', ok, 'closed', closed, 'rejected', rej);
end $$;

-- 3. 약한 신호: 상태만 바꾸는 갱신은 n_seen 을 늘리지 않는다 ---------------------------------------------------------
create or replace function ideas.put_weak_signals(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; seen date;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'signal_key';
    if k is null or k !~ '^[a-z0-9_]{2,60}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'signal_key 는 영문 소문자·숫자·_ 2~60자'); continue; end if;
    if coalesce(r->>'status', 'watch') not in ('watch', 'promoted', 'dropped') then rej := rej || jsonb_build_object('i', i, 'reason', 'status 는 watch | promoted | dropped'); continue; end if;
    -- 상태 갱신만 (sources 없음): 승격·폐기 표시
    if not (r ? 'sources') then
      update ideas.weak_signals set status = coalesce(r->>'status', status), promoted_to = coalesce(r->>'promoted_to', promoted_to), note = coalesce(r->>'note', note), updated_at = now()
       where signal_key = k;
      if found then ok := ok + 1; else rej := rej || jsonb_build_object('i', i, 'reason', '상태 갱신인데 신호 없음'); end if;
      continue;
    end if;
    if length(coalesce(r->>'term', '')) < 2 or length(coalesce(r->>'mechanism', '')) < 10 then rej := rej || jsonb_build_object('i', i, 'reason', 'term·mechanism(10자 이상) 필수'); continue; end if;
    if jsonb_typeof(r->'sources') <> 'array' or jsonb_array_length(r->'sources') < 1
       or exists (select 1 from jsonb_array_elements(r->'sources') s where coalesce(s->>'url', '') !~ '^https?://') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'sources 1개 이상, 각각 url'); continue;
    end if;
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

-- 4. 뷰 ----------------------------------------------------------------------------------------------------------
drop view if exists public.v_theses;
create view public.v_theses
with (security_invoker = true) as
select t.*,
       (select count(*) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key and e.direction = '+') as n_support,
       (select count(*) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key and e.direction = '-') as n_against,
       (select max(as_of) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key) as last_evidence_at,
       (select count(*) from ideas.theses c where c.parent_key = t.thesis_key and c.status = 'active') as n_children
from ideas.theses t;

-- 조사 큐: 아직 조사하지 않은 활성 micro 테제 (새것 먼저). macro 는 토요일 verify 의 큰 테제 점검이 본다.
create or replace view public.v_q_theses_needing_research
with (security_invoker = true) as
select thesis_key, scale, parent_key, title, weakest_link, beneficiaries, stage, created_at
from ideas.theses
where status = 'active' and kind = 'thesis' and scale = 'micro' and research is null
order by created_at desc;

-- 감시 큐: 반증 기한이 7일 안에 오거나 지난 것, 첫 신호 예상 시점이 14일 안인 것
create or replace view public.v_q_thesis_watch
with (security_invoker = true) as
select t.thesis_key, t.scale, t.title, 'falsifier' as kind, f->>'what' as what, (f->>'due')::date as due, f->>'metric' as metric, f->>'threshold' as threshold
from ideas.theses t cross join lateral jsonb_array_elements(t.falsifiers) f
where t.status = 'active' and (f->>'due') ~ '^\d{4}-\d{2}-\d{2}$' and (f->>'due')::date <= current_date + 7
union all
select t.thesis_key, t.scale, t.title, 'first_signal', t.first_signal->>'metric',
       (case when (t.first_signal->>'expected_by') ~ '^\d{4}-\d{2}$' then (t.first_signal->>'expected_by') || '-28'
             else t.first_signal->>'expected_by' end)::date,
       t.first_signal->>'where', null
from ideas.theses t
where t.status = 'active' and (t.first_signal->>'expected_by') ~ '^\d{4}-\d{2}(-\d{2})?$'
  and (case when (t.first_signal->>'expected_by') ~ '^\d{4}-\d{2}$' then (t.first_signal->>'expected_by') || '-28'
            else t.first_signal->>'expected_by' end)::date <= current_date + 14;

-- 리포트 큐: 조사에서 살아남은(confirmed·partial) micro 테제의 primary — 그 기업의 활성 리포트가 조사 뒤 갱신되지 않은 것.
-- 엔진(--hypotheses-from-db)이 이슈 경로 후보 뒤에 이어 붙인다 (ADR-0027). primary 가 여럿이면 가장 작은 것 하나.
create or replace view public.v_q_thesis_candidates_needing_report
with (security_invoker = true) as
select t.thesis_key, t.parent_key, t.title, t.statement, t.chain, t.weakest_link, t.what_market_misses, t.lag_months, t.falsifiers,
       pb.b->>'company' as company, pb.b->>'label' as company_label, pb.b->>'basis' as basis, pb.b->>'size_band' as size_band, pb.b->'rerating' as rerating,
       t.research->>'verdict' as verdict, t.research->>'summary' as research_summary, t.research->'event_ids' as event_ids, t.research->'sources' as sources,
       t.researched_at, x.idea_key as existing_idea, x.updated_at as existing_updated_at
from ideas.theses t
cross join lateral (
  select b from jsonb_array_elements(t.beneficiaries) b
  where b->>'role' = 'primary' and b->>'company' like 'company:%'
  order by case b->>'size_band' when 'micro' then 0 when 'small' then 1 when 'mid' then 2 else 3 end
  limit 1
) pb
left join lateral (
  select idea_key, updated_at from ideas.investment_ideas
  where status = 'active' and primary_company = pb.b->>'company'
  order by updated_at desc limit 1
) x on true
where t.status = 'active' and t.kind = 'thesis' and t.scale = 'micro' and t.research->>'verdict' in ('confirmed', 'partial')
  and (x.idea_key is null or x.updated_at < t.researched_at)
order by t.researched_at desc;

-- 5. 권한 ---------------------------------------------------------------------------------------------------------
revoke all on function ideas.put_theses(jsonb), ideas.put_thesis_research(jsonb), ideas.put_weak_signals(jsonb) from public;
revoke all on function ideas.put_theses(jsonb), ideas.put_thesis_research(jsonb), ideas.put_weak_signals(jsonb) from anon, authenticated;
grant execute on function ideas.put_theses(jsonb), ideas.put_thesis_research(jsonb), ideas.put_weak_signals(jsonb) to service_role;
grant select on public.v_theses, public.v_q_theses_needing_research, public.v_q_thesis_watch, public.v_q_thesis_candidates_needing_report to anon, authenticated;
