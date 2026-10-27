-- 0017: 기업·온톨로지 마스터와 연결 테이블, 이슈 이력·잠금 (추가만 — 기존 쓰기·화면에 영향 없음). ADR-0015.
-- 채우기는 wsj.ecosystems.sync_db (git seed_graph.json → DB). 트리거·뷰 전환·정리는 0018.

-- 기업 마스터: 그래프 기업 노드와 같은 id. SEC 필러는 core.companies 와 cik 로 1:1, 그 밖(한국·대만·유럽·비상장)도 포함.
create table if not exists core.entities (
  entity_id    text primary key,                         -- company:mxl, company:delta_electronics
  name         text not null,
  cik          bigint unique references core.companies (cik),
  ticker       text,
  exchange     text,                                     -- Nasdaq | NYSE | KRX | TWSE | TPEx | Euronext ...
  local_code   text,                                     -- 비미국 상장 코드 (005930, 2308)
  listing      text,                                     -- 10-K | 20-F | 40-F | non_sec_listed | private
  size_band    text,                                     -- micro | small | mid | large | mega | private | unknown
  ecosystems   text[] not null default '{}',
  role         text,                                     -- supplier | customer | both
  in_graph     boolean not null default false,           -- 온톨로지 기업 노드인가
  in_universe  boolean not null default false,           -- 공급망 유니버스(해자 카드·신호 대상)인가
  source       text not null default 'ontology',         -- ontology | indicator | manual
  attrs        jsonb not null default '{}',
  updated_at   timestamptz not null default now()
);
create index if not exists entities_ticker_idx on core.entities (upper(ticker));

-- 온톨로지 (원본 = git research/ecosystems/seed_graph.json). 그래프에서 빠지면 active=false — 참조는 남는다.
create table if not exists core.ontology_nodes (
  node_id      text primary key,
  kind         text not null,
  label        text not null,
  ecosystem    text,
  entity_id    text references core.entities (entity_id),  -- kind=company 일 때
  attrs        jsonb not null default '{}',
  graph_as_of  text,
  active       boolean not null default true,
  updated_at   timestamptz not null default now()
);
create index if not exists ontology_nodes_kind_idx on core.ontology_nodes (kind, ecosystem);

create table if not exists core.ontology_edges (
  edge_id       text primary key,
  src           text not null references core.ontology_nodes (node_id),
  dst           text not null references core.ontology_nodes (node_id),
  predicate     text not null,
  evidence_tier text,
  confidence    numeric,
  polarity      text,
  about         text[] not null default '{}',
  evidence      jsonb not null default '[]',
  note          text,
  graph_as_of   text,
  active        boolean not null default true,
  updated_at    timestamptz not null default now()
);
create index if not exists ontology_edges_src_idx on core.ontology_edges (src);
create index if not exists ontology_edges_dst_idx on core.ontology_edges (dst);

-- 사실 → 마스터 연결 (0018 의 트리거가 배열 컬럼에서 유지한다)
create table if not exists ideas.issue_nodes (
  issue_key text not null references ideas.supply_chain_issues (issue_key) on delete cascade,
  node_id   text not null references core.ontology_nodes (node_id),
  primary key (issue_key, node_id)
);
create index if not exists issue_nodes_node_idx on ideas.issue_nodes (node_id);

create table if not exists ideas.issue_entities (
  issue_key text not null references ideas.supply_chain_issues (issue_key) on delete cascade,
  entity_id text not null references core.entities (entity_id),
  ord       smallint not null default 0,
  direction text check (direction in ('+', '-', '±')),
  basis     text,
  primary key (issue_key, entity_id)
);
create index if not exists issue_entities_entity_idx on ideas.issue_entities (entity_id);

create table if not exists ideas.indicator_nodes (
  indicator_id text not null references ideas.indicators (indicator_id) on delete cascade,
  node_id      text not null references core.ontology_nodes (node_id),
  primary key (indicator_id, node_id)
);
create table if not exists ideas.indicator_entities (
  indicator_id text not null references ideas.indicators (indicator_id) on delete cascade,
  entity_id    text not null references core.entities (entity_id),
  primary key (indicator_id, entity_id)
);
create table if not exists ideas.brief_nodes (
  brief_id bigint not null references ideas.briefs (id) on delete cascade,
  node_id  text not null references core.ontology_nodes (node_id),
  primary key (brief_id, node_id)
);

-- 이슈 이력·잠금·병합
alter table ideas.supply_chain_issues add column if not exists locked boolean not null default false;
alter table ideas.supply_chain_issues add column if not exists revision integer not null default 1;
alter table ideas.supply_chain_issues add column if not exists merged_into text references ideas.supply_chain_issues (issue_key);
alter table ideas.supply_chain_issues drop constraint if exists supply_chain_issues_status_check;
alter table ideas.supply_chain_issues add constraint supply_chain_issues_status_check check (status in ('active', 'dismissed', 'merged'));

create table if not exists ideas.issue_revisions (
  id         bigint generated always as identity primary key,
  issue_key  text not null references ideas.supply_chain_issues (issue_key) on delete cascade,
  revision   integer not null,
  revised_at timestamptz not null default now(),
  method     text,
  model      text,
  snapshot   jsonb not null                              -- 바뀌기 전 행 전체
);
create index if not exists issue_revisions_key_idx on ideas.issue_revisions (issue_key, revision desc);

-- 기술 전환 (ADR-0015 §3-1): 신기술이 상용화되면 누가 해자를 얻고 누가 대체되며 어떤 새 병목이 생기나.
-- 표시는 단순하게: 결론 한 문장 + ★1~3 + 근거 목록. 단계는 3단계(early 연구·시제품 / near 샘플·인증 / commercial 양산)만.
create table if not exists ideas.tech_evidence (            -- 기술 진척의 근거가 된 사실 (날짜·출처)
  id            bigint generated always as identity primary key,
  node_id       text not null references core.ontology_nodes (node_id),
  observed_at   date not null,
  entity_id     text references core.entities (entity_id),
  fact          text not null,
  evidence_url  text not null,
  evidence_tier text,
  stage         text check (stage in ('early','near','commercial')),
  issue_key     text references ideas.supply_chain_issues (issue_key),
  created_at    timestamptz not null default now(),
  unique (node_id, evidence_url)
);
create index if not exists tech_evidence_node_idx on ideas.tech_evidence (node_id, observed_at desc);

create table if not exists ideas.tech_transitions (          -- 전환 카드 (기술 1개당 버전 이력)
  id          bigint generated always as identity primary key,
  node_id     text not null references core.ontology_nodes (node_id),
  as_of       date not null,
  stage       text check (stage in ('early','near','commercial')),
  stars       smallint check (stars between 1 and 3),        -- 투자 관점의 중요도
  conclusion  text not null,                                 -- 결론 한두 문장 (먼저 보여 줄 것)
  card        jsonb not null,                                -- winners, losers, new_bottlenecks, watch, evidence
  model       text,
  usage       jsonb,
  status      text not null default 'final' check (status in ('draft','final','superseded')),
  created_at  timestamptz not null default now()
);
create index if not exists tech_transitions_node_idx on ideas.tech_transitions (node_id, created_at desc);

create table if not exists ideas.transition_exposures (      -- "이 기업을 위협/수혜하는 신기술은?"
  transition_id bigint not null references ideas.tech_transitions (id) on delete cascade,
  entity_id     text not null references core.entities (entity_id),
  role          text not null check (role in ('developer','ip_holder','enabler','new_bottleneck_supplier','displaced_incumbent','adopter')),
  effect        text not null check (effect in ('+','-','±')),
  mechanism     text,
  primary key (transition_id, entity_id, role)
);
create index if not exists transition_exposures_entity_idx on ideas.transition_exposures (entity_id);

-- 이슈 표시용 별점 (1~3): 기존 importance(1~10)에서 파생 — 저장된 값과 항상 일치
alter table ideas.supply_chain_issues add column if not exists stars smallint
  generated always as (case when importance >= 8 then 3 when importance >= 5 then 2 else 1 end) stored;

-- 읽기 권한 (쓰기는 service_role 만)
do $$
declare t text;
begin
  foreach t in array array['core.entities','core.ontology_nodes','core.ontology_edges','ideas.issue_nodes','ideas.issue_entities',
                           'ideas.indicator_nodes','ideas.indicator_entities','ideas.brief_nodes','ideas.issue_revisions',
                           'ideas.tech_evidence','ideas.tech_transitions','ideas.transition_exposures'] loop
    execute format('alter table %s enable row level security', t);
    execute format('drop policy if exists "read all" on %s', t);
    execute format('create policy "read all" on %s for select to anon, authenticated using (true)', t);
    execute format('grant select on %s to anon, authenticated', t);
    execute format('grant all on %s to service_role', t);
  end loop;
end $$;
