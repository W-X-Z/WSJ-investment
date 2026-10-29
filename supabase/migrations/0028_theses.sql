-- 0028: 구조 가설 (ADR-0025) — "사용 방식의 변화 → 자원 요구 → 공급 병목 → 기업 리레이팅" 같은 테제를 주 단위로 세우고,
-- 매일 사슬(이슈 경로·조사)이 그 테제의 근거·반증을 쌓는다. 리포트(기업 1개 + 이슈 1개)와 달리 여러 달에 걸치고 대형주도 받는다.
-- 실행: Supabase SQL 편집기 (사용자). 작업은 ideas.put_theses · ideas.put_thesis_evidence 로만 쓴다.

create table if not exists ideas.theses (
  thesis_key    text primary key,                       -- 짧은 슬러그 (예 memory_inference_rerating_2026)
  title         text not null,                          -- 한 줄
  statement     text not null,                          -- 한 문단: 무엇이 무엇을 어떻게 바꾸고 누가 리레이팅되나
  ecosystem     text,                                   -- hbm | optics | power | cross
  chain         jsonb not null default '[]',            -- [{node, claim, evidence: [{url, title, date, kind}]}] — 수요 동인부터 기업까지
  drivers       jsonb not null default '[]',            -- [{id, label, metric, latest: {value, as_of, source}, threshold, direction, indicator_id?}] — 관측 가능한 수치
  beneficiaries jsonb not null default '[]',            -- [{company, role, basis, size_band, rerating: {from, to, why}}]
  losers        jsonb not null default '[]',            -- [{company|node, why}]
  falsifiers    jsonb not null default '[]',            -- [{what, metric, threshold, due}] — 날짜 있는 반증 조건
  stage         smallint not null default 0 check (stage between 0 and 3),  -- 0 가설 · 1 동인이 움직임 · 2 공급 반응이 보임 · 3 시장이 반영
  stage_reason  text,
  status        text not null default 'active' check (status in ('active', 'closed')),
  close_reason  text,
  benchmark     text,                                   -- research/benchmarks/regime_cases.json 의 case id (유사 과거 사례)
  model         text,
  method        text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create table if not exists ideas.thesis_evidence (
  id          bigint generated always as identity primary key,
  thesis_key  text not null references ideas.theses (thesis_key) on delete cascade,
  as_of       date not null default current_date,
  direction   text not null check (direction in ('+', '-', '0')),   -- 지지 · 반박 · 중립
  what        text not null,                                        -- 한 줄
  ref         jsonb not null default '{}',                           -- {issue_key?, path_id?, event_id?, indicator_id?, url?}
  weight      smallint not null default 1 check (weight between 1 and 3),
  created_at  timestamptz not null default now()
);
create index if not exists thesis_evidence_key_idx on ideas.thesis_evidence (thesis_key, as_of desc);

create or replace function ideas.put_theses(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text;
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
    insert into ideas.theses as t (thesis_key, title, statement, ecosystem, chain, drivers, beneficiaries, losers, falsifiers, stage, stage_reason, status, close_reason, benchmark, model, method, updated_at)
    values (k, left(r->>'title', 160), r->>'statement', r->>'ecosystem', r->'chain', r->'drivers', r->'beneficiaries', coalesce(r->'losers', '[]'::jsonb), r->'falsifiers',
            coalesce((r->>'stage')::smallint, 0), r->>'stage_reason', coalesce(r->>'status', 'active'), r->>'close_reason', r->>'benchmark', left(r->>'model', 60), left(r->>'method', 20), now())
    on conflict (thesis_key) do update set title = excluded.title, statement = excluded.statement, ecosystem = excluded.ecosystem, chain = excluded.chain, drivers = excluded.drivers,
      beneficiaries = excluded.beneficiaries, losers = excluded.losers, falsifiers = excluded.falsifiers, stage = excluded.stage, stage_reason = excluded.stage_reason,
      status = excluded.status, close_reason = excluded.close_reason, benchmark = excluded.benchmark, model = excluded.model, method = excluded.method, updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

create or replace function ideas.put_thesis_evidence(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    if not exists (select 1 from ideas.theses where thesis_key = r->>'thesis_key') then rej := rej || jsonb_build_object('i', i, 'reason', '테제 없음'); continue; end if;
    if coalesce(r->>'direction', '') not in ('+', '-', '0') then rej := rej || jsonb_build_object('i', i, 'reason', 'direction 은 + - 0'); continue; end if;
    if length(coalesce(r->>'what', '')) < 10 then rej := rej || jsonb_build_object('i', i, 'reason', 'what 10자 이상'); continue; end if;
    insert into ideas.thesis_evidence (thesis_key, as_of, direction, what, ref, weight)
    values (r->>'thesis_key', coalesce((r->>'as_of')::date, current_date), r->>'direction', left(r->>'what', 400), coalesce(r->'ref', '{}'::jsonb), coalesce((r->>'weight')::smallint, 1));
    ok := ok + 1;
  end loop;
  return jsonb_build_object('inserted', ok, 'rejected', rej);
end $$;

create or replace view public.v_theses
with (security_invoker = true) as
select t.*,
       (select count(*) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key and e.direction = '+') as n_support,
       (select count(*) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key and e.direction = '-') as n_against,
       (select max(as_of) from ideas.thesis_evidence e where e.thesis_key = t.thesis_key) as last_evidence_at
from ideas.theses t;

create or replace view public.v_thesis_evidence
with (security_invoker = true) as
select id, thesis_key, as_of, direction, what, ref, weight, created_at from ideas.thesis_evidence;

revoke all on function ideas.put_theses(jsonb), ideas.put_thesis_evidence(jsonb) from public;
revoke all on function ideas.put_theses(jsonb), ideas.put_thesis_evidence(jsonb) from anon, authenticated;
grant execute on function ideas.put_theses(jsonb), ideas.put_thesis_evidence(jsonb) to service_role;
grant select on public.v_theses, public.v_thesis_evidence to anon, authenticated;
grant select on ideas.theses, ideas.thesis_evidence to anon, authenticated;
grant all on ideas.theses, ideas.thesis_evidence to service_role;
alter table ideas.theses enable row level security;
alter table ideas.thesis_evidence enable row level security;
drop policy if exists theses_read on ideas.theses;
create policy theses_read on ideas.theses for select to anon, authenticated using (true);
drop policy if exists thesis_evidence_read on ideas.thesis_evidence;
create policy thesis_evidence_read on ideas.thesis_evidence for select to anon, authenticated using (true);
