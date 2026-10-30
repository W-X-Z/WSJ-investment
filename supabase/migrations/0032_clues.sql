-- 0032: 단서 저장소 (ADR-0028 2단계) — 출처 목록의 새 글을 원문 그대로 쌓는다. 등급·점수 없음.
-- 수집기(GitHub Actions, secret 키)가 쓰고, 해석 작업이 v_clues 로 읽는다. 시세·특징주 기사는 수집기가 버린다(relevant=false 로 남겨 집계만).
-- 실행: Supabase SQL 편집기 (사용자). 0031 뒤.

create table if not exists ideas.clues (
  clue_id      bigint generated always as identity primary key,
  url          text not null unique,
  title        text not null,
  summary      text,                                   -- RSS 요약·발췌 (500자 안)
  published_at timestamptz,
  seen_at      timestamptz not null default now(),     -- 처음 본 때 (해석 작업의 '새 단서' 기준)
  source_id    text not null,                          -- research/sources/registry.json 의 id | company_feed | issues
  source_name  text,
  source_kind  text,                                   -- trade_press|company_newsroom|disclosure|standards|conference|research|release_notes|market_data|policy|company_feed|issue
  lang         text,
  region       text,
  companies    jsonb not null default '[]'::jsonb,     -- [{name, ticker, exchange, company}] — 그래프 밖 기업도 이름·티커로
  nodes        text[] not null default '{}',           -- 걸린 그래프 노드 (태깅일 뿐, 거르지 않는다)
  relevant     boolean not null default true,          -- false = 시세 기사·주제 밖 (집계용으로만 남김)
  note         text,                                   -- 한 줄 (무엇에 관한 글인가)
  extra        jsonb
);
create index if not exists clues_seen_idx on ideas.clues (seen_at desc);
create index if not exists clues_relevant_pub_idx on ideas.clues (relevant, published_at desc);
create index if not exists clues_nodes_idx on ideas.clues using gin (nodes);
create index if not exists clues_companies_idx on ideas.clues using gin (companies jsonb_path_ops);

-- 공개 읽기: 관련 있는 단서, 최근 120일
create or replace view public.v_clues
with (security_invoker = true) as
select clue_id, url, title, summary, published_at, seen_at, source_id, source_name, source_kind, lang, region, companies, nodes, note
from ideas.clues
where relevant and seen_at > now() - interval '120 days';

alter table ideas.clues enable row level security;
drop policy if exists clues_read on ideas.clues;
create policy clues_read on ideas.clues for select to anon, authenticated using (relevant);
grant select on ideas.clues to anon, authenticated;
grant all on ideas.clues to service_role;
grant select on public.v_clues to anon, authenticated;
