-- 0014: ideas.briefs 에 kind 추가 — 'brief'(후보 브리프, ADR-0009) | 'moat'(공급망 해자 카드, ADR-0013).
-- 뷰는 열을 끝에 덧붙여 create or replace (열 이름 변경은 Postgres 가 거부한다).
alter table ideas.briefs add column if not exists kind text not null default 'brief' check (kind in ('brief','moat'));
alter table ideas.briefs add column if not exists ontology_nodes text[] not null default '{}';
create index if not exists briefs_kind_idx on ideas.briefs (kind, created_at desc);

create or replace view public.v_briefs
with (security_invoker = true) as
select b.id, b.cik, co.ticker, co.name, co.sector_bucket, b.as_of, b.version, b.status, b.title,
       b.scores, b.model, b.prompt_version, b.usage, b.error, b.created_at,
       (select count(*) from ideas.predictions p where p.brief_id = b.id) as prediction_count,
       b.kind, b.ontology_nodes
from ideas.briefs b join core.companies co on co.cik = b.cik;
-- 적용 중 임시로 만든 public.v_briefs_v2 가 남아 있으면 수동으로 drop (MCP 자동 모드가 drop 을 막음).
