-- 0027: 작업 분업 (ADR-0024) — 매일 아침 한 세션이 하던 일을 다섯 예약작업으로 나누고, 작업 사이 인계는 DB 큐 뷰로 한다.
--   수집 → 이슈별 영향 경로(paths) → 조사(research) → 리포트+목표주가(report) → 검증·보고(verify)
-- 각 작업은 자기 큐 뷰(v_q_*)에 있는 것만 처리하고, 끝나면 ops.put_agent_run 으로 실행 기록을 남긴다 (앞 작업이 실패하면 큐가 비어 조용히 끝난다).
-- 실행: Supabase SQL 편집기 (사용자). 예약작업은 put_* 함수로만 쓴다.

-- 1) 경로 조사 결과 — 조사 작업이 쓰고, 리포트 작업이 읽는다. (issue_key, path id, as_of) 는 ideas.issue_hypotheses 의 경로 하나를 가리킨다.
create table if not exists ideas.path_research (
  issue_key   text not null,
  path_id     text not null,                 -- issue_hypotheses.paths[].id (H1, H2 …)
  as_of       date not null,                 -- 그 경로 묶음의 as_of
  verdict     text not null check (verdict in ('confirmed', 'partial', 'unconfirmed', 'no_data', 'refuted')),
  summary     text not null,                 -- 확인한 사실 1~3문장 (숫자·날짜·상대방)
  event_ids   text[] not null default '{}',  -- 저장한 기업 소식(ideas.company_events.event_id)
  sources     jsonb not null default '[]',   -- [{title, url, date}]
  model       text,
  created_at  timestamptz not null default now(),
  primary key (issue_key, path_id, as_of),
  foreign key (issue_key, as_of) references ideas.issue_hypotheses (issue_key, as_of) on delete cascade
);
create index if not exists path_research_created_idx on ideas.path_research (created_at desc);

create or replace function ideas.put_path_research(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; pid text; d date; v text; ev text[];
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'issue_key'; pid := r->>'path_id'; v := r->>'verdict';
    begin d := (r->>'as_of')::date; exception when others then d := null; end;
    if k is null or pid is null or d is null then rej := rej || jsonb_build_object('i', i, 'reason', 'issue_key·path_id·as_of 필요'); continue; end if;
    if not exists (select 1 from ideas.issue_hypotheses h where h.issue_key = k and h.as_of = d
                   and exists (select 1 from jsonb_array_elements(h.paths) p where p->>'id' = pid)) then
      rej := rej || jsonb_build_object('i', i, 'reason', '경로 없음: ' || k || '/' || pid || '/' || d::text); continue;
    end if;
    if v is null or v not in ('confirmed', 'partial', 'unconfirmed', 'no_data', 'refuted') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'verdict 는 confirmed|partial|unconfirmed|no_data|refuted'); continue;
    end if;
    if length(coalesce(r->>'summary', '')) < 10 then rej := rej || jsonb_build_object('i', i, 'reason', 'summary 10자 이상'); continue; end if;
    if v in ('confirmed', 'partial', 'refuted') and (jsonb_typeof(r->'sources') <> 'array' or jsonb_array_length(r->'sources') < 1) then
      rej := rej || jsonb_build_object('i', i, 'reason', v || ' 는 sources 1개 이상 (원문 URL)'); continue;
    end if;
    ev := case when jsonb_typeof(r->'event_ids') = 'array' then array(select jsonb_array_elements_text(r->'event_ids')) else '{}' end;
    insert into ideas.path_research as t (issue_key, path_id, as_of, verdict, summary, event_ids, sources, model)
    values (k, pid, d, v, left(r->>'summary', 1200), ev, coalesce(r->'sources', '[]'::jsonb), left(r->>'model', 60))
    on conflict (issue_key, path_id, as_of) do update
      set verdict = excluded.verdict, summary = excluded.summary, event_ids = excluded.event_ids, sources = excluded.sources, model = excluded.model, created_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

create or replace view public.v_path_research
with (security_invoker = true) as
select issue_key, path_id, as_of, verdict, summary, event_ids, sources, model, created_at
from ideas.path_research;

-- 2) 실행 기록 — ops.collector_runs 를 그대로 쓴다 (collector = 'agent:<task>'). 같은 날 같은 작업은 한 행으로 (다시 돌리면 덮어쓴다).
create or replace function ops.put_agent_run(row_in jsonb) returns jsonb language plpgsql as $$
declare
  t text; st text; d date; rid bigint;
begin
  t := row_in->>'task'; st := coalesce(row_in->>'status', 'succeeded');
  if t is null or t !~ '^[a-z_]{3,24}$' then raise exception 'task 는 영문 소문자 (collect|paths|research|report|verify …)'; end if;
  if st not in ('running', 'succeeded', 'failed', 'skipped') then raise exception 'status 는 running|succeeded|failed|skipped'; end if;
  d := coalesce((row_in->>'run_date')::date, (now() at time zone 'Asia/Seoul')::date);
  select id into rid from ops.collector_runs
   where collector = 'agent:' || t and (started_at at time zone 'Asia/Seoul')::date = d
   order by started_at desc limit 1;
  if rid is null then
    insert into ops.collector_runs (collector, status, params, runner_host, started_at)
    values ('agent:' || t, st, jsonb_build_object('run_date', d), 'claude-session', coalesce((row_in->>'started_at')::timestamptz, now()))
    returning id into rid;
  end if;
  update ops.collector_runs
     set status = st,
         finished_at = case when st = 'running' then null else now() end,
         rows_upserted = coalesce((row_in->>'rows')::int, rows_upserted),
         watermark = coalesce(row_in->'counts', watermark),
         error = left(row_in->>'note', 600)
   where id = rid;
  return jsonb_build_object('id', rid, 'task', t, 'run_date', d, 'status', st);
end $$;

create or replace view public.v_agent_runs
with (security_invoker = true) as
select id, replace(collector, 'agent:', '') as task, (started_at at time zone 'Asia/Seoul')::date as run_date, status,
       started_at, finished_at, rows_upserted as rows, watermark as counts, left(error, 600) as note
from ops.collector_runs
where collector like 'agent:%' and started_at > now() - interval '45 days';

-- 3) 큐 뷰 — 각 작업의 '할 일'. 앞 작업의 결과에서 아직 다음 결과가 없는 것.
-- 3-1 경로가 없는 이슈 (paths 작업): 활성, 중요도 6+ (★2+), 최근 5일 안에 보도됐고, 경로 묶음이 하나도 없는 이슈.
create or replace view public.v_q_issues_needing_paths
with (security_invoker = true) as
select i.issue_key, i.title, i.ecosystem, i.event_type, i.importance, i.nodes, i.companies,
       coalesce(i.latest_published_at, i.first_seen) as published_at, i.sources
from ideas.supply_chain_issues i
where i.status = 'active' and i.importance >= 6
  and coalesce(i.latest_published_at, i.first_seen) > now() - interval '5 days'
  and not exists (select 1 from ideas.issue_hypotheses h where h.issue_key = i.issue_key)
order by i.importance desc, published_at desc;

-- 3-2 조사가 필요한 경로 (research 작업): 최근 7일 경로 묶음 중 '선택'됐고 기업이 있는데 조사 결과가 없는 경로.
create or replace view public.v_q_paths_needing_research
with (security_invoker = true) as
with latest as (
  select distinct on (h.issue_key) h.issue_key, h.as_of, h.paths
  from ideas.issue_hypotheses h
  where h.as_of >= current_date - 7
  order by h.issue_key, h.as_of desc
)
select l.issue_key, i.title as issue_title, l.as_of, p->>'id' as path_id, p->>'claim' as claim, p->>'company' as company,
       p->>'company_label' as company_label, p->'path' as path, p->'path_labels' as path_labels, p->'research' as research,
       p->>'falsifier' as falsifier, p->'flags' as flags, p->>'extends' as extends, (p->>'score')::int as score, p->'trigger' as trigger
from latest l
join ideas.supply_chain_issues i on i.issue_key = l.issue_key
cross join lateral jsonb_array_elements(l.paths) p
where (p->>'selected')::boolean and p->>'company' is not null
  and not exists (select 1 from ideas.path_research r where r.issue_key = l.issue_key and r.path_id = p->>'id' and r.as_of = l.as_of)
order by (p->>'score')::int desc nulls last, l.as_of desc;

-- 3-3 리포트가 필요한 후보 (report 작업): 조사 결과가 있는 선택 경로 중, 그 기업의 활성 리포트가 조사 뒤에 갱신되지 않은 것.
--     refuted 는 리포트 대상이 아니다 (조사 작업이 보고에만 적는다). no_data 는 '(추론)' 으로만 쓸 수 있으니 포함한다.
create or replace view public.v_q_candidates_needing_report
with (security_invoker = true) as
with latest as (
  select distinct on (h.issue_key) h.issue_key, h.as_of, h.paths
  from ideas.issue_hypotheses h
  where h.as_of >= current_date - 7
  order by h.issue_key, h.as_of desc
)
select l.issue_key, i.title as issue_title, l.as_of, p->>'id' as path_id, p->>'claim' as claim, p->>'company' as company,
       p->>'company_label' as company_label, p->>'extends' as extends, (p->>'score')::int as score,
       r.verdict, r.summary as research_summary, r.event_ids, r.created_at as researched_at,
       x.idea_key as existing_idea, x.updated_at as existing_updated_at
from latest l
join ideas.supply_chain_issues i on i.issue_key = l.issue_key
cross join lateral jsonb_array_elements(l.paths) p
join ideas.path_research r on r.issue_key = l.issue_key and r.path_id = p->>'id' and r.as_of = l.as_of
left join lateral (
  select idea_key, updated_at from ideas.investment_ideas
  where status = 'active' and primary_company = p->>'company'
  order by updated_at desc limit 1
) x on true
where (p->>'selected')::boolean and p->>'company' is not null and r.verdict <> 'refuted'
  and (x.idea_key is null or x.updated_at < r.created_at)
order by (p->>'score')::int desc nulls last;

-- 3-4 목표주가가 필요한 리포트 (report 작업, 두 번째 큐): 활성인데 평가가 없거나, 리포트를 고쳐 쓴 뒤 산출하지 않았다.
create or replace view public.v_q_ideas_needing_valuation
with (security_invoker = true) as
select i.idea_key, i.title, i.primary_company, i.stars, i.updated_at, v.as_of as last_valuation_as_of, v.created_at as last_valuation_at,
       case when v.idea_key is null then '평가 없음' else '리포트 갱신 뒤 재산출 전' end as reason
from ideas.investment_ideas i
left join lateral (
  select idea_key, as_of, created_at from ideas.valuations where idea_key = i.idea_key order by as_of desc, created_at desc limit 1
) v on true
where i.status = 'active' and (v.idea_key is null or v.created_at < i.updated_at - interval '60 seconds')
order by i.updated_at desc;

-- 3-5 채점할 예측 (verify 작업): 활성 리포트의 watch 중 pending 이고 기한이 지난 것.
create or replace view public.v_q_predictions_due
with (security_invoker = true) as
select i.idea_key, i.title, i.primary_company, i.stars, w.ordinality - 1 as watch_index, w.item->>'what' as what,
       (w.item->>'due')::date as due, w.item->>'metric' as metric, w.item->>'threshold' as threshold, coalesce(w.item->>'direction', 'strengthen') as direction
from ideas.investment_ideas i
cross join lateral jsonb_array_elements(i.watch) with ordinality as w(item, ordinality)
where i.status = 'active' and coalesce(w.item->>'status', 'pending') = 'pending'
  and (w.item->>'due') ~ '^\d{4}-\d{2}-\d{2}$' and (w.item->>'due')::date <= current_date
order by due, i.idea_key;

-- 4) 권한
revoke all on function ideas.put_path_research(jsonb), ops.put_agent_run(jsonb) from public;
revoke all on function ideas.put_path_research(jsonb), ops.put_agent_run(jsonb) from anon, authenticated;
grant execute on function ideas.put_path_research(jsonb), ops.put_agent_run(jsonb) to service_role;
grant select on public.v_path_research, public.v_agent_runs, public.v_q_issues_needing_paths, public.v_q_paths_needing_research,
  public.v_q_candidates_needing_report, public.v_q_ideas_needing_valuation, public.v_q_predictions_due to anon, authenticated;
grant select on ideas.path_research to anon, authenticated;
grant all on ideas.path_research to service_role;
alter table ideas.path_research enable row level security;
drop policy if exists path_research_read on ideas.path_research;
create policy path_research_read on ideas.path_research for select to anon, authenticated using (true);
