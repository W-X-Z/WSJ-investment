-- 0034: 원본 입력과 이어받기 (ADR-0030) — 단서 본문 · In 점검 뷰 · 조사 스레드.
-- 실행: Supabase SQL 편집기 (사용자). 0033 뒤. 수집기 코드는 이 마이그레이션 전에도 돈다 (본문 저장만 건너뛴다).

-- 1) 단서 본문: 수집기가 남긴 단서의 원문 본문을 받아 둔다. 해석·검토 작업이 주소를 다시 열지 않고 읽는다.
--    원문 전문은 공개하지 않는다 (anon 정책 없음 — 웹 화면은 쓰지 않는다. 작업은 Supabase MCP 로 읽는다).
--    보존·정리 규칙은 데이터가 쌓인 뒤에 정한다 (사용자, 2026-11-02).
create table if not exists ideas.clue_texts (
  url          text primary key references ideas.clues (url) on delete cascade,
  body         text,                                   -- 본문 (최대 2만 자)
  chars        int not null default 0,
  status       text not null,                          -- ok | short | not_html | http_4xx | error:*
  http_status  int,
  fetched_at   timestamptz not null default now()
);
alter table ideas.clue_texts enable row level security;
grant all on ideas.clue_texts to service_role;

-- 2) In 점검: 날마다 무엇이 들어왔고 무엇이 걸러졌나. 05:23 수집 작업이 한 줄, 주간 개선이 표로 본다.
--    layer 는 수집기가 extra.layer 에 적는다 (0034 이전 단서는 source_kind 로 추정).
create or replace view ops.v_input_quality as
with c as (
  select (cl.seen_at at time zone 'Asia/Seoul')::date as day,
         coalesce(cl.extra->>'layer',
                  case when cl.source_kind in ('company_feed') then 'company'
                       when cl.source_kind in ('disclosure') then 'disclosure'
                       when cl.source_kind in ('issue') then 'issue'
                       when cl.source_kind in ('company_newsroom') then 'newsroom'
                       when cl.source_kind in ('standards', 'conference', 'research', 'policy', 'release_notes', 'tech_signal') then 'raw'
                       else 'press' end) as layer,
         cl.relevant,
         coalesce(cl.extra->>'screen',
                  case when cl.note = '시세·지분 기사' then 'noise' when cl.note = '같은 제목 중복' then 'duplicate'
                       when not cl.relevant then 'topic_drop' else 'kept' end) as screen,
         exists (select 1 from jsonb_array_elements(cl.companies) x where coalesce(x->>'company', '') <> '') as in_graph,
         t.status as body_status
  from ideas.clues cl
  left join ideas.clue_texts t on t.url = cl.url
  where cl.seen_at > now() - interval '35 days'
)
select day,
       count(*)                                                        as collected,
       count(*) filter (where relevant)                                as kept,
       count(*) filter (where screen = 'noise')                        as dropped_noise,
       count(*) filter (where screen = 'duplicate')                    as dropped_duplicate,
       count(*) filter (where screen = 'topic_drop')                   as dropped_topic,
       count(*) filter (where screen = 'raw_exempt')                   as raw_exempt,
       round(100.0 * count(*) filter (where relevant and layer = 'raw') / nullif(count(*) filter (where relevant), 0), 1)       as raw_pct,
       round(100.0 * count(*) filter (where relevant and not in_graph) / nullif(count(*) filter (where relevant), 0), 1)    as outside_graph_pct,
       round(100.0 * count(*) filter (where relevant and body_status = 'ok') / nullif(count(*) filter (where relevant), 0), 1) as body_pct,
       jsonb_build_object(
         'raw',        count(*) filter (where relevant and layer = 'raw'),
         'press',      count(*) filter (where relevant and layer = 'press'),
         'newsroom',   count(*) filter (where relevant and layer = 'newsroom'),
         'company',    count(*) filter (where relevant and layer = 'company'),
         'disclosure', count(*) filter (where relevant and layer = 'disclosure'),
         'issue',      count(*) filter (where relevant and layer = 'issue'))                                                  as kept_by_layer,
       round(pg_database_size(current_database()) / 1048576.0)          as db_mb
from c
group by day
order by day desc;

-- 출처별로 지난 30일 남긴 단서 수와 투자 아이디어(초안·내린 것 포함)가 근거·출발 단서로 쓴 수 — 출처를 더하고 빼는 근거.
create or replace view ops.v_source_use as
with kept as (
  select source_id, url from ideas.clues where relevant and seen_at > now() - interval '30 days'
), cited as (
  select distinct coalesce(e->>'url', '') as url
  from ideas.opportunities o, jsonb_array_elements(o.evidence || o.clue_refs) e
  where o.created_at > now() - interval '45 days'
)
select k.source_id, count(*) as kept_30d, count(*) filter (where c.url is not null) as cited
from kept k left join cited c on c.url = k.url
group by k.source_id
order by cited desc, kept_30d desc;

revoke all on ops.v_input_quality, ops.v_source_use from public, anon, authenticated;
grant select on ops.v_input_quality, ops.v_source_use to service_role;

-- 3) 조사 스레드: 하루에 끝나지 않는 조사를 다음 날 이어받는다.
--    해석(06:17)이 고른 단서 중 결론까지 못 간 것, 검토자(06:49)가 되돌린 약한 고리를 연다.
--    다음 날 해석이 남는 시간에 열린 스레드 하나를 이어서 판다. 결론(산다·안 산다·가장 약한 고리)이 나면 닫는다.
create table if not exists ideas.threads (
  thread_key      text primary key check (thread_key ~ '^[a-z0-9_]{6,60}$'),
  title           text not null,                       -- 무엇을 확인하려는가 (명사형)
  question        text,                                -- 결론을 내려면 답해야 할 것
  status          text not null default 'open' check (status in ('open', 'concluded', 'dropped')),
  conclusion      text,
  weakest_link    text,
  opportunity_key text references ideas.opportunities (opportunity_key) on delete set null,
  companies       jsonb not null default '[]'::jsonb,  -- [{company, name, ticker}]
  nodes           text[] not null default '{}',
  clue_urls       text[] not null default '{}',
  opened_by       text,                                -- interpret | enrich | report | weekly | user
  returns         int not null default 0,              -- 검토자가 되돌린 횟수
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  closed_at       timestamptz
);
create index if not exists threads_status_idx on ideas.threads (status, updated_at desc);

create table if not exists ideas.thread_entries (
  entry_id    bigint generated always as identity primary key,
  thread_key  text not null references ideas.threads (thread_key) on delete cascade,
  at          timestamptz not null default now(),
  by          text not null,                           -- interpret | enrich | report | weekly | user
  kind        text not null check (kind in ('note', 'finding', 'returned', 'concluded', 'dropped')),
  body        text not null,
  sources     jsonb not null default '[]'::jsonb       -- [{title, url, date}]
);
create index if not exists thread_entries_thread_idx on ideas.thread_entries (thread_key, at);

-- 쓰기: 스레드 열기·고치기와 기록 한 줄을 한 번에.
-- {"thread_key", "title"(새로 열 때), "question", "companies", "nodes", "clue_urls", "opportunity_key", "opened_by",
--  "entry": {"by", "kind", "body", "sources"}}
-- entry.kind = returned → returns+1, 다시 open / concluded·dropped → 닫고 conclusion·weakest_link 를 남긴다.
create or replace function ideas.put_thread(r jsonb) returns jsonb language plpgsql as $$
declare
  k text := r->>'thread_key'; e jsonb := r->'entry'; kind text; exists_ boolean;
begin
  if k is null or k !~ '^[a-z0-9_]{6,60}$' then raise exception 'thread_key 는 영문 소문자·숫자·_ 6~60자'; end if;
  exists_ := exists (select 1 from ideas.threads where thread_key = k);
  if not exists_ and length(coalesce(r->>'title', '')) < 5 then raise exception '새 스레드는 title 5자 이상'; end if;
  insert into ideas.threads as t (thread_key, title, question, companies, nodes, clue_urls, opportunity_key, opened_by)
  values (k, coalesce(r->>'title', k), r->>'question', coalesce(r->'companies', '[]'::jsonb),
          coalesce((select array_agg(distinct x) from jsonb_array_elements_text(coalesce(r->'nodes', '[]'::jsonb)) x), '{}'),
          coalesce((select array_agg(distinct x) from jsonb_array_elements_text(coalesce(r->'clue_urls', '[]'::jsonb)) x), '{}'),
          r->>'opportunity_key', r->>'opened_by')
  on conflict (thread_key) do update set
    title = coalesce(r->>'title', t.title), question = coalesce(r->>'question', t.question),
    companies = case when r ? 'companies' then excluded.companies else t.companies end,
    nodes = case when r ? 'nodes' then coalesce((select array_agg(distinct x) from unnest(t.nodes || excluded.nodes) x), '{}') else t.nodes end,
    clue_urls = case when r ? 'clue_urls' then coalesce((select array_agg(distinct x) from unnest(t.clue_urls || excluded.clue_urls) x), '{}') else t.clue_urls end,
    opportunity_key = coalesce(r->>'opportunity_key', t.opportunity_key),
    updated_at = now();
  if e is not null then
    kind := coalesce(e->>'kind', 'note');
    if kind not in ('note', 'finding', 'returned', 'concluded', 'dropped') then raise exception 'entry.kind 는 note|finding|returned|concluded|dropped'; end if;
    if length(coalesce(e->>'body', '')) < 5 then raise exception 'entry.body 5자 이상'; end if;
    insert into ideas.thread_entries (thread_key, by, kind, body, sources)
    values (k, coalesce(e->>'by', 'unknown'), kind, e->>'body', coalesce(e->'sources', '[]'::jsonb));
    update ideas.threads set
      status = case when kind in ('concluded', 'dropped') then kind when kind = 'returned' then 'open' else status end,
      returns = returns + case when kind = 'returned' then 1 else 0 end,
      conclusion = case when kind in ('concluded', 'dropped') then coalesce(r->>'conclusion', e->>'body') else conclusion end,
      weakest_link = coalesce(r->>'weakest_link', weakest_link),
      closed_at = case when kind in ('concluded', 'dropped') then now() when kind = 'returned' then null else closed_at end,
      updated_at = now()
    where thread_key = k;
  end if;
  return (select to_jsonb(t) - 'companies' from ideas.threads t where thread_key = k);
end $$;

alter table ideas.threads enable row level security;
alter table ideas.thread_entries enable row level security;
grant all on ideas.threads, ideas.thread_entries to service_role;
revoke all on function ideas.put_thread(jsonb) from public, anon, authenticated;
grant execute on function ideas.put_thread(jsonb) to service_role;
