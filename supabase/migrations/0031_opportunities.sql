-- 0031: 투자 아이디어 (ADR-0028) — 리포트는 ★1~5 · 제목 · 투자 아이디어 · 해석 · 기업 · 근거만.
-- 목표주가·시나리오·예측·채점은 쓰지 않는다 (기존 ideas.investment_ideas·valuations 는 남기되 화면에서 숨긴다).
-- 흐름: 해석 작업이 draft 로 쓰고 → 원문 보강 작업이 사실을 채우거나 dropped 로 → 리포트 작업이 active 로 낸다.
-- 실행: Supabase SQL 편집기 (사용자). 0030 뒤.

create table if not exists ideas.opportunities (
  opportunity_key text primary key check (opportunity_key ~ '^[a-z0-9_]{6,60}$'),
  title          text not null,                         -- 명사형 제목: '[원인]에 따른 [대상] [변화]'
  stars          smallint not null check (stars between 1 and 5),   -- 나에게 얼마나 큰 투자 기회인가 (해석자의 판단)
  idea           text not null,                         -- 투자 아이디어: 무엇이 바뀌어 어느 회사의 무엇이 얼마나
  interpretation text,                                  -- 해석: 왜 그렇게 읽었나 (결론 문장으로)
  companies      jsonb not null default '[]'::jsonb,    -- [{company: 'company:x'|null, name, ticker, exchange, role: 'primary'|'related'}]
  evidence       jsonb not null default '[]'::jsonb,    -- [{title, url, date, publisher}]
  nodes          text[] not null default '{}',          -- 지나는 그래프 노드 (같은 부품·병목 아이디어 묶기용, 화면에 노드 id 는 안 보인다)
  clue_refs      jsonb not null default '[]'::jsonb,    -- 출발 단서 (2단계 뒤 clue id; 지금은 {title, url, date})
  status         text not null default 'draft' check (status in ('draft', 'active', 'dropped', 'closed')),
  status_note    text,
  model          text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  published_at   timestamptz
);
create index if not exists opportunities_status_idx on ideas.opportunities (status, updated_at desc);
create index if not exists opportunities_nodes_idx on ideas.opportunities using gin (nodes);

create or replace function ideas.put_opportunities(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; k text; st text; exists_ boolean;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    k := r->>'opportunity_key';
    if k is null or k !~ '^[a-z0-9_]{6,60}$' then rej := rej || jsonb_build_object('i', i, 'reason', 'opportunity_key 는 영문 소문자·숫자·_ 6~60자'); continue; end if;
    exists_ := exists (select 1 from ideas.opportunities where opportunity_key = k);
    st := coalesce(r->>'status', case when exists_ then null else 'draft' end);
    if st is not null and st not in ('draft', 'active', 'dropped', 'closed') then rej := rej || jsonb_build_object('i', i, 'reason', 'status 는 draft|active|dropped|closed'); continue; end if;
    -- 상태만 바꾸기 (제목·아이디어 없이)
    if exists_ and not (r ? 'title') and not (r ? 'idea') then
      update ideas.opportunities set status = coalesce(st, status), status_note = coalesce(r->>'status_note', status_note),
             published_at = case when st = 'active' and published_at is null then now() else published_at end, updated_at = now()
       where opportunity_key = k;
      ok := ok + 1; continue;
    end if;
    if length(coalesce(r->>'title', '')) not between 5 and 80 then rej := rej || jsonb_build_object('i', i, 'reason', 'title 5~80자'); continue; end if;
    if coalesce((r->>'stars')::int, 0) not between 1 and 5 then rej := rej || jsonb_build_object('i', i, 'reason', 'stars 1~5'); continue; end if;
    if length(coalesce(r->>'idea', '')) < 30 then rej := rej || jsonb_build_object('i', i, 'reason', 'idea 30자 이상'); continue; end if;
    if jsonb_typeof(r->'companies') <> 'array' or jsonb_array_length(r->'companies') < 1
       or exists (select 1 from jsonb_array_elements(r->'companies') c where length(coalesce(c->>'name', '')) < 1) then
      rej := rej || jsonb_build_object('i', i, 'reason', 'companies 1개 이상, 각각 name'); continue;
    end if;
    if jsonb_typeof(r->'evidence') <> 'array' or jsonb_array_length(r->'evidence') < 1
       or exists (select 1 from jsonb_array_elements(r->'evidence') e where coalesce(e->>'url', '') !~ '^https?://') then
      rej := rej || jsonb_build_object('i', i, 'reason', 'evidence 1개 이상, 각각 url'); continue;
    end if;
    insert into ideas.opportunities as o (opportunity_key, title, stars, idea, interpretation, companies, evidence, nodes, clue_refs, status, status_note, model, published_at, updated_at)
    values (k, r->>'title', (r->>'stars')::smallint, r->>'idea', r->>'interpretation', r->'companies', r->'evidence',
            coalesce((select array_agg(distinct x) from jsonb_array_elements_text(coalesce(r->'nodes', '[]'::jsonb)) x), '{}'),
            coalesce(r->'clue_refs', '[]'::jsonb), coalesce(st, 'draft'), r->>'status_note', left(r->>'model', 60),
            case when coalesce(st, 'draft') = 'active' then now() end, now())
    on conflict (opportunity_key) do update set
      title = excluded.title, stars = excluded.stars, idea = excluded.idea, interpretation = coalesce(excluded.interpretation, o.interpretation),
      companies = excluded.companies, evidence = excluded.evidence,
      nodes = case when r ? 'nodes' then excluded.nodes else o.nodes end,
      clue_refs = case when r ? 'clue_refs' then excluded.clue_refs else o.clue_refs end,
      status = coalesce(st, o.status), status_note = coalesce(excluded.status_note, o.status_note), model = coalesce(excluded.model, o.model),
      published_at = case when coalesce(st, o.status) = 'active' and o.published_at is null then now() else o.published_at end,
      updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $$;

-- 공개 읽기: 낸 것(active)과 닫은 것(closed)만. draft·dropped 는 작업 사이의 상태라 화면에 없다.
create or replace view public.v_opportunities
with (security_invoker = true) as
select opportunity_key, title, stars, idea, interpretation, companies, evidence, nodes, clue_refs, status, status_note,
       created_at, updated_at, published_at
from ideas.opportunities
where status in ('active', 'closed');

alter table ideas.opportunities enable row level security;
drop policy if exists opportunities_read on ideas.opportunities;
create policy opportunities_read on ideas.opportunities for select to anon, authenticated using (status in ('active', 'closed'));
grant select on ideas.opportunities to anon, authenticated;
grant all on ideas.opportunities to service_role;
grant select on public.v_opportunities to anon, authenticated;
revoke all on function ideas.put_opportunities(jsonb) from public;
revoke all on function ideas.put_opportunities(jsonb) from anon, authenticated;
grant execute on function ideas.put_opportunities(jsonb) to service_role;
