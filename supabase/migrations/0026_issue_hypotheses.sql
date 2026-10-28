-- 0026: 이슈별 영향 경로 (ADR-0023) — 1단계 가설 "이 이슈가 업계에 어떤 영향을 주나, 경로 최대 3개" 를 이슈 단위로 저장한다.
-- 이슈 탭이 "이 이슈가 공급망에 갖는 의미"를 경로로 보여 주고, 기업이 있는 경로는 2단계(리포트)의 후보가 된다.
-- 실행: Supabase SQL 편집기 (사용자). 예약작업은 ideas.put_issue_hypotheses 로만 쓴다.

create table if not exists ideas.issue_hypotheses (
  issue_key   text not null references ideas.supply_chain_issues (issue_key) on delete cascade,
  as_of       date not null,
  paths       jsonb not null,   -- [{id, claim, path: [node id…], path_labels: […], company: 'company:…'|null, company_label, effect_pct, lead_quarters,
                                --   why_unpriced, falsifier, research: […], score, criteria, flags, selected: 리포트 후보로 뽑혔나, rank}] — 최대 3개
  model       text,
  method      text,
  created_at  timestamptz not null default now(),
  primary key (issue_key, as_of)
);
create index if not exists issue_hypotheses_as_of on ideas.issue_hypotheses (as_of desc);

create or replace function ideas.put_issue_hypotheses(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; d date; ps jsonb; p jsonb; bad text;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'issue_key';
    if k is null or not exists (select 1 from ideas.supply_chain_issues where issue_key = k) then
      rej := rej || jsonb_build_object('i', i, 'reason', '이슈 없음: ' || coalesce(k, '')); continue;
    end if;
    begin
      d := coalesce((r->>'as_of')::date, current_date);
    exception when others then
      rej := rej || jsonb_build_object('i', i, 'reason', 'as_of 형식'); continue;
    end;
    ps := r->'paths';
    if jsonb_typeof(ps) <> 'array' or jsonb_array_length(ps) < 1 or jsonb_array_length(ps) > 3 then
      rej := rej || jsonb_build_object('i', i, 'reason', 'paths 1~3개'); continue;
    end if;
    bad := null;
    for p in select * from jsonb_array_elements(ps) loop
      if length(coalesce(p->>'claim', '')) < 10 then bad := 'claim 10자 이상'; exit; end if;
      if jsonb_typeof(p->'path') <> 'array' or jsonb_array_length(p->'path') < 1 then bad := 'path 는 노드 id 배열'; exit; end if;
      if p ? 'company' and jsonb_typeof(p->'company') = 'string' and (p->>'company') !~ '^company:[a-z0-9_]+$' then bad := 'company 형식'; exit; end if;
    end loop;
    if bad is not null then rej := rej || jsonb_build_object('i', i, 'key', k, 'reason', bad); continue; end if;
    insert into ideas.issue_hypotheses as t (issue_key, as_of, paths, model, method)
    values (k, d, ps, r->>'model', r->>'method')
    on conflict (issue_key, as_of) do update set paths = excluded.paths, model = excluded.model, method = excluded.method, created_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

-- 읽기 뷰: 이슈마다 가장 최근 경로 묶음 (이슈 탭)
create or replace view public.v_issue_hypotheses
with (security_invoker = true) as
select distinct on (h.issue_key) h.issue_key, h.as_of, h.paths, h.model, h.method, h.created_at
from ideas.issue_hypotheses h
order by h.issue_key, h.as_of desc;

-- 권한
revoke all on function ideas.put_issue_hypotheses(jsonb) from public;
revoke all on function ideas.put_issue_hypotheses(jsonb) from anon, authenticated;
grant execute on function ideas.put_issue_hypotheses(jsonb) to service_role;
grant select on public.v_issue_hypotheses to anon, authenticated;
grant select on ideas.issue_hypotheses to anon, authenticated;
grant all on ideas.issue_hypotheses to service_role;
alter table ideas.issue_hypotheses enable row level security;
drop policy if exists issue_hypotheses_read on ideas.issue_hypotheses;
create policy issue_hypotheses_read on ideas.issue_hypotheses for select to anon, authenticated using (true);

-- 덧붙임: 환율 갱신 경로. ref 스키마는 PostgREST 에 노출되지 않아 facts 수집기의 `ref.fx_rates` upsert 가 406 (PGRST106) 으로 실패했다
-- (10/28 두 번). 노출된 raw 스키마의 함수로 쓴다 — 발행주식수는 그 전에 저장되므로 시총은 살아 있었고, 환율만 10/28 에 멈춰 있었다.
create or replace function raw.put_fx_rates(rows jsonb) returns jsonb language plpgsql security definer set search_path = ref, pg_temp as $$
declare r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; cur text; v numeric;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    cur := upper(nullif(btrim(r->>'currency'), ''));
    begin v := (r->>'usd_per_unit')::numeric; exception when others then v := null; end;
    if cur is null or cur !~ '^[A-Z]{3}$' or v is null or v <= 0 then
      rej := rej || jsonb_build_object('i', i, 'reason', 'currency(3자)·usd_per_unit(>0) 필요'); continue;
    end if;
    insert into ref.fx_rates (currency, usd_per_unit, as_of, updated_at)
    values (cur, v, nullif(r->>'as_of', '')::date, now())
    on conflict (currency) do update set usd_per_unit = excluded.usd_per_unit, as_of = excluded.as_of, updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;
revoke all on function raw.put_fx_rates(jsonb) from public;
revoke all on function raw.put_fx_rates(jsonb) from anon, authenticated;
grant execute on function raw.put_fx_rates(jsonb) to service_role;
