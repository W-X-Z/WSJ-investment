-- 0017: AI 투자 아이디어 피드 + 이슈 보호. ADR-0016 (ADR-0015 개정 1).
-- 사람이 보는 것은 아이디어(결론·★·근거 사슬)다. 그래프·이슈·지표는 AI 가 추론에 쓰는 재료라 별도 탐색용 미러를 만들지 않는다.

-- 1) 투자 아이디어 (wsj.ecosystems.ideas 가 매일 쓴다)
create table if not exists ideas.investment_ideas (
  idea_key        text primary key,                           -- 갱신 시 같은 key (LLM 이 기존 key 를 이어 씀)
  status          text not null default 'active' check (status in ('active', 'closed')),
  trend           text check (trend in ('new', 'strengthened', 'weakened', 'unchanged')),
  type            text check (type in ('bottleneck', 'transition', 'confirmation', 'risk')),
  title           text,                                       -- 직관적인 한 줄 (기업명 포함)
  thesis          text,                                       -- 두 문장: 변화 + 왜 이 기업
  stars           smallint check (stars between 1 and 3),
  stars_reason    text,
  primary_company text,                                       -- 그래프 기업 id (company:xxx)
  companies       jsonb not null default '[]',                -- [{id, name, ticker, exchange, size_band, role, why}]
  chain           jsonb not null default '[]',                -- [{claim, evidence: [{id, url, title, publisher, date, tier, tier_ko}]}]
  risks           jsonb not null default '[]',
  watch           jsonb not null default '[]',                -- 다음에 확인할 신호
  what_changed    text,
  close_reason    text,
  nodes           text[] not null default '{}',
  ecosystems      text[] not null default '{}',
  signal_refs     text[] not null default '{}',               -- 근거가 된 이슈 key · 지표 id
  evidence_count  integer not null default 0,
  last_signal_at  date,
  first_seen      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  revision        integer not null default 1,
  model           text,
  method          text,                                       -- llm | session
  usage           jsonb
);
create index if not exists investment_ideas_feed_idx on ideas.investment_ideas (status, stars desc, updated_at desc);
create index if not exists investment_ideas_company_idx on ideas.investment_ideas (primary_company);

create table if not exists ideas.idea_revisions (
  id         bigint generated always as identity primary key,
  idea_key   text not null references ideas.investment_ideas (idea_key) on delete cascade,
  revision   integer not null,
  revised_at timestamptz not null default now(),
  snapshot   jsonb not null                                   -- 바뀌기 전 행 전체
);
create index if not exists idea_revisions_key_idx on ideas.idea_revisions (idea_key, revision desc);

-- 내용이 바뀌면 이전 행을 남기고 revision 을 올린다. first_seen 은 처음 값 유지.
create or replace function ideas.guard_idea_update() returns trigger language plpgsql as $$
begin
  new.first_seen := least(old.first_seen, new.first_seen);
  if (new.status, new.title, new.thesis, new.stars, new.companies, new.chain, new.risks, new.watch)
     is distinct from (old.status, old.title, old.thesis, old.stars, old.companies, old.chain, old.risks, old.watch) then
    insert into ideas.idea_revisions (idea_key, revision, snapshot) values (old.idea_key, old.revision, to_jsonb(old));
    new.revision := old.revision + 1;
  else
    new.revision := old.revision;
  end if;
  return new;
end $$;
drop trigger if exists investment_ideas_guard on ideas.investment_ideas;
create trigger investment_ideas_guard before update on ideas.investment_ideas
  for each row execute function ideas.guard_idea_update();

-- 2) 이슈 보호: 세션에서 다듬은 이슈를 자동 실행이 덮어쓰지 않게 (잠금·이력·병합)
alter table ideas.supply_chain_issues add column if not exists locked boolean not null default false;
alter table ideas.supply_chain_issues add column if not exists revision integer not null default 1;
alter table ideas.supply_chain_issues add column if not exists merged_into text references ideas.supply_chain_issues (issue_key);
alter table ideas.supply_chain_issues drop constraint if exists supply_chain_issues_status_check;
alter table ideas.supply_chain_issues add constraint supply_chain_issues_status_check check (status in ('active', 'dismissed', 'merged'));
alter table ideas.supply_chain_issues add column if not exists stars smallint
  generated always as (case when importance >= 8 then 3 when importance >= 5 then 2 else 1 end) stored;

create table if not exists ideas.issue_revisions (
  id         bigint generated always as identity primary key,
  issue_key  text not null references ideas.supply_chain_issues (issue_key) on delete cascade,
  revision   integer not null,
  revised_at timestamptz not null default now(),
  method     text,
  model      text,
  snapshot   jsonb not null
);
create index if not exists issue_revisions_key_idx on ideas.issue_revisions (issue_key, revision desc);

create or replace function ideas.guard_issue_update() returns trigger language plpgsql as $$
begin
  if old.locked and new.locked then
    new.ecosystem := old.ecosystem; new.event_type := old.event_type; new.title := old.title; new.summary := old.summary;
    new.why_it_matters := old.why_it_matters; new.importance := old.importance; new.importance_rationale := old.importance_rationale;
    new.nodes := old.nodes; new.companies := old.companies; new.method := old.method; new.model := old.model;
  end if;
  if old.status in ('merged', 'dismissed') and new.status = 'active' and new.method is distinct from 'manual' then
    new.status := old.status; new.merged_into := old.merged_into;
  end if;
  new.first_seen := least(old.first_seen, new.first_seen);
  if (new.ecosystem, new.event_type, new.title, new.summary, new.why_it_matters, new.importance, new.importance_rationale,
      new.nodes, new.companies, new.status, new.merged_into)
     is distinct from
     (old.ecosystem, old.event_type, old.title, old.summary, old.why_it_matters, old.importance, old.importance_rationale,
      old.nodes, old.companies, old.status, old.merged_into) then
    insert into ideas.issue_revisions (issue_key, revision, method, model, snapshot)
      values (old.issue_key, old.revision, old.method, old.model, to_jsonb(old));
    new.revision := old.revision + 1;
  else
    new.revision := old.revision;
  end if;
  return new;
end $$;
drop trigger if exists supply_chain_issues_guard on ideas.supply_chain_issues;
create trigger supply_chain_issues_guard before update on ideas.supply_chain_issues
  for each row execute function ideas.guard_issue_update();

-- 3) 읽기 모델 (프론트 계약: 열은 끝에만 추가)
create or replace view public.v_investment_ideas
with (security_invoker = true) as
select idea_key, status, trend, type, title, thesis, stars, stars_reason, primary_company, companies, chain, risks, watch,
       what_changed, nodes, ecosystems, signal_refs, evidence_count, last_signal_at, first_seen, updated_at, revision, model, method,
       (now() - updated_at) > interval '21 days' as stale
from ideas.investment_ideas
where status = 'active';

create or replace view public.v_supply_chain_issues
with (security_invoker = true) as
select issue_key, ecosystem, event_type, title, summary, why_it_matters, importance, importance_rationale,
       nodes, companies, sources, source_count, publisher_count, first_seen, last_seen, latest_published_at, method, model,
       locked, revision, stars
from ideas.supply_chain_issues
where status = 'active';

-- 해자 카드 상세 (지금은 /briefs/[id] 가 테이블을 직접 읽는다 → 뷰로 분리)
create or replace view public.v_brief_detail
with (security_invoker = true) as
select b.id, b.cik, co.ticker, co.name, b.kind, b.as_of, b.version, b.status, b.title, b.brief, b.research, b.critique,
       b.datapack_summary, b.scores, b.model, b.prompt_version, b.usage, b.error, b.created_at, b.ontology_nodes,
       coalesce((select jsonb_agg(to_jsonb(p) - 'brief_id' order by p.due_date nulls last) from ideas.predictions p where p.brief_id = b.id), '[]'::jsonb) as predictions
from ideas.briefs b
join core.companies co on co.cik = b.cik;

-- 권한: 읽기는 공개, 쓰기는 service_role 만
do $$
declare t text;
begin
  foreach t in array array['ideas.investment_ideas', 'ideas.idea_revisions', 'ideas.issue_revisions'] loop
    execute format('alter table %s enable row level security', t);
    execute format('drop policy if exists "read all" on %s', t);
    execute format('create policy "read all" on %s for select to anon, authenticated using (true)', t);
    execute format('grant select on %s to anon, authenticated', t);
    execute format('grant all on %s to service_role', t);
  end loop;
end $$;
grant select on public.v_investment_ideas, public.v_supply_chain_issues, public.v_brief_detail to anon, authenticated;
