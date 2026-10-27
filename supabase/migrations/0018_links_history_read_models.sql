-- 0018: 연결 테이블 유지 트리거, 이슈 잠금·이력, 정리, 읽기 모델(뷰). ADR-0015.
-- 전제: 0017 적용 + wsj.ecosystems.sync_db 1회 실행(엔티티·노드 채움).

-- 1) 배열 컬럼(쓰기 인터페이스) → 연결 테이블(FK) 유지. 없는 노드·기업 id 를 쓰면 저장이 실패한다.
create or replace function ideas.sync_issue_links() returns trigger language plpgsql as $$
begin
  delete from ideas.issue_nodes where issue_key = new.issue_key;
  insert into ideas.issue_nodes (issue_key, node_id)
    select new.issue_key, n from unnest(coalesce(new.nodes, '{}')) n on conflict do nothing;
  delete from ideas.issue_entities where issue_key = new.issue_key;
  insert into ideas.issue_entities (issue_key, entity_id, ord, direction, basis)
    select new.issue_key, c->>'company_id', (o - 1)::smallint, nullif(c->>'direction', ''), c->>'basis'
    from jsonb_array_elements(coalesce(new.companies, '[]'::jsonb)) with ordinality t(c, o)
    where c->>'company_id' is not null
    on conflict do nothing;
  return null;
end $$;
drop trigger if exists supply_chain_issues_links on ideas.supply_chain_issues;
create trigger supply_chain_issues_links after insert or update of nodes, companies on ideas.supply_chain_issues
  for each row execute function ideas.sync_issue_links();

create or replace function ideas.sync_indicator_links() returns trigger language plpgsql as $$
begin
  delete from ideas.indicator_nodes where indicator_id = new.indicator_id;
  insert into ideas.indicator_nodes (indicator_id, node_id)
    select new.indicator_id, n from unnest(coalesce(new.nodes, '{}')) n on conflict do nothing;
  delete from ideas.indicator_entities where indicator_id = new.indicator_id;
  insert into ideas.indicator_entities (indicator_id, entity_id)
    select new.indicator_id, c from unnest(coalesce(new.companies, '{}')) c on conflict do nothing;
  return null;
end $$;
drop trigger if exists indicators_links on ideas.indicators;
create trigger indicators_links after insert or update of nodes, companies on ideas.indicators
  for each row execute function ideas.sync_indicator_links();

create or replace function ideas.sync_brief_links() returns trigger language plpgsql as $$
begin
  delete from ideas.brief_nodes where brief_id = new.id;
  insert into ideas.brief_nodes (brief_id, node_id)
    select new.id, n from unnest(coalesce(new.ontology_nodes, '{}')) n on conflict do nothing;
  return null;
end $$;
drop trigger if exists briefs_links on ideas.briefs;
create trigger briefs_links after insert or update of ontology_nodes on ideas.briefs
  for each row execute function ideas.sync_brief_links();

-- 2) 잠금·이력: 잠긴 이슈는 자동 실행이 내용(제목·요약·중요도·노드·기업)을 바꾸지 못하고 출처·시각만 갱신된다.
--    내용이 바뀌면 이전 행을 issue_revisions 에 남긴다. merged/dismissed 는 자동 실행이 되살리지 못한다.
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

-- 3) 기존 행을 연결 테이블로 (트리거 생성 전 데이터)
insert into ideas.issue_nodes (issue_key, node_id)
  select i.issue_key, n from ideas.supply_chain_issues i, unnest(i.nodes) n on conflict do nothing;
insert into ideas.issue_entities (issue_key, entity_id, ord, direction, basis)
  select i.issue_key, c->>'company_id', (o - 1)::smallint, nullif(c->>'direction', ''), c->>'basis'
  from ideas.supply_chain_issues i, jsonb_array_elements(i.companies) with ordinality t(c, o)
  where c->>'company_id' is not null on conflict do nothing;
delete from ideas.indicators where indicator_id like 'fred:PCU%' or indicator_id = 'bls:PCU335921335921';  -- 데이터 없는 옛 정의
insert into ideas.indicator_nodes (indicator_id, node_id)
  select i.indicator_id, n from ideas.indicators i, unnest(i.nodes) n on conflict do nothing;
insert into ideas.indicator_entities (indicator_id, entity_id)
  select i.indicator_id, c from ideas.indicators i, unnest(i.companies) c on conflict do nothing;
insert into ideas.brief_nodes (brief_id, node_id)
  select b.id, n from ideas.briefs b, unnest(b.ontology_nodes) n on conflict do nothing;

-- 4) 목적 밖 유니버스 정리 (원자료는 보존): 피벗 전 SIC 버킷은 신호·브리프 대상에서 내린다
update core.companies set in_universe = false, universe_reason = 'retired:legacy-sic-bucket', updated_at = now()
where in_universe and coalesce(universe_reason, '') not like 'ontology%';

-- 5) 세션 큐레이션 이슈 잠금, 중복 병합, 자동 실행에 덮인 큐레이션 1건 복원
update ideas.supply_chain_issues set locked = true, method = 'curated' where model like 'claude-opus%';
update ideas.supply_chain_issues set status = 'merged',
  merged_into = (select issue_key from ideas.supply_chain_issues where title like 'HBM4 사양 하향%' and status = 'active' order by importance desc limit 1)
where title like 'Samsung, NVIDIA용 HBM 베이스다이%' and status = 'active'
  and exists (select 1 from ideas.supply_chain_issues where title like 'HBM4 사양 하향%' and status = 'active');
update ideas.supply_chain_issues set
  title = 'MaxLinear 3분기 매출 +72%, 1.6T·AEC 로 확장',
  summary = 'MaxLinear 3분기 매출은 2억 1,810만 달러로 전년 대비 72%, 인프라 부문은 210% 늘었다(8-K EX-99.1). 회사는 Keystone PAM4 DSP 양산 확대와 1.6T 대응 Rushmore·Annapurna 제품군을 성장 동력으로 꼽았다. 같은 주 MaxLinear 가 AEC(능동 전기 케이블) 시장 진출을 밝히자 Credo 주가가 하루 약 10% 하락했다는 보도가 나왔다.',
  why_it_matters = '광 DSP 는 800G→1.6T 전환의 핵심 칩이고, 소형사 MaxLinear 가 Marvell·Broadcom 이 쥔 영역에서 매출로 확인되기 시작했다. AEC 진입은 Credo 의 독점적 지위에 대한 첫 경쟁 신호다.',
  event_type = 'earnings', ecosystem = 'optics', importance = 8,
  importance_rationale = '1차 출처(8-K) + 독립 출판사 6곳 이상, 소형 공급사의 실적으로 확인된 병목 진입, 경쟁사(Credo) 영향까지 포함.',
  nodes = array['component:optical_dsp','gen:1p6t','component:aec','product:credo_aec'],
  companies = '[{"company_id":"company:mxl","direction":"+","basis":"Q3 매출 YoY +72%, 인프라 +210%, Keystone PAM4 DSP 양산 확대 (8-K)"},{"company_id":"company:crdo","direction":"-","basis":"MaxLinear 가 Credo 주력 AEC 시장 진출을 밝혔다는 보도"}]'::jsonb,
  method = 'curated', model = 'claude-opus-5-5 (session curation)', locked = true
where issue_key = '3fcc15c9b7c92474b124';

-- 6) 읽기 모델 (프론트 계약). 기존 뷰는 열 이름·타입·순서를 유지하고 끝에만 덧붙인다.
create or replace view public.v_supply_chain_issues
with (security_invoker = true) as
select i.issue_key, i.ecosystem, i.event_type, i.title, i.summary, i.why_it_matters, i.importance, i.importance_rationale,
       i.nodes,
       coalesce((select jsonb_agg(jsonb_build_object(
                  'company_id', e.entity_id,
                  'label', e.name || coalesce(' (' || coalesce(e.ticker, e.local_code) || ')', ''),
                  'ticker', coalesce(e.ticker, e.local_code),
                  'direction', ie.direction, 'size_band', e.size_band, 'in_universe', e.in_universe, 'basis', ie.basis)
                  order by ie.ord)
                 from ideas.issue_entities ie join core.entities e on e.entity_id = ie.entity_id
                 where ie.issue_key = i.issue_key), '[]'::jsonb) as companies,
       i.sources, i.source_count, i.publisher_count, i.first_seen, i.last_seen, i.latest_published_at, i.method, i.model,
       i.locked, i.revision
from ideas.supply_chain_issues i
where i.status = 'active';
grant select on public.v_supply_chain_issues to anon, authenticated;

-- 기업 한 곳의 모든 것 (Q4): 마스터 + SEC 정보 + 그래프 위치 + 최신 해자 카드 + 최근 이슈·지표
create or replace view public.v_entities
with (security_invoker = true) as
select e.entity_id, e.name, e.ticker, e.exchange, e.local_code, e.listing, e.size_band, e.ecosystems, e.role,
       e.in_graph, e.in_universe, e.source, e.cik, c.public_float, c.public_float_asof,
       (select array_agg(distinct x.node_id) from (
          select ed.src as node_id from core.ontology_edges ed where ed.dst = e.entity_id and ed.active
          union select ed.dst from core.ontology_edges ed where ed.src = e.entity_id and ed.active) x) as node_ids,
       m.id as moat_brief_id, m.as_of as moat_as_of, m.scores as moat_scores,
       (select count(*) from ideas.issue_entities ie join ideas.supply_chain_issues i on i.issue_key = ie.issue_key
         where ie.entity_id = e.entity_id and i.status = 'active' and i.latest_published_at >= now() - interval '30 days') as issues_30d,
       (select max(i.latest_published_at) from ideas.issue_entities ie join ideas.supply_chain_issues i on i.issue_key = ie.issue_key
         where ie.entity_id = e.entity_id and i.status = 'active') as last_issue_at,
       (select array_agg(x.indicator_id order by x.indicator_id) from ideas.indicator_entities x where x.entity_id = e.entity_id) as indicator_ids
from core.entities e
left join core.companies c on c.cik = e.cik
left join lateral (
  select b.id, b.as_of, b.scores from ideas.briefs b
  where b.cik = e.cik and b.kind = 'moat' and b.status = 'final' order by b.created_at desc limit 1) m on true;
grant select on public.v_entities to anon, authenticated;

-- 노드(병목·기술·부품…)의 활동 (Q2·Q3·Q5)
create or replace view public.v_node_activity
with (security_invoker = true) as
select n.node_id, n.kind, n.label, n.ecosystem, n.active,
       (select count(*) from ideas.issue_nodes x join ideas.supply_chain_issues i on i.issue_key = x.issue_key
         where x.node_id = n.node_id and i.status = 'active' and i.latest_published_at >= now() - interval '30 days') as issues_30d,
       (select count(*) from ideas.issue_nodes x join ideas.supply_chain_issues i on i.issue_key = x.issue_key
         where x.node_id = n.node_id and i.status = 'active' and i.latest_published_at >= now() - interval '90 days') as issues_90d,
       (select max(i.importance) from ideas.issue_nodes x join ideas.supply_chain_issues i on i.issue_key = x.issue_key
         where x.node_id = n.node_id and i.status = 'active' and i.latest_published_at >= now() - interval '30 days') as max_importance_30d,
       (select max(i.latest_published_at) from ideas.issue_nodes x join ideas.supply_chain_issues i on i.issue_key = x.issue_key
         where x.node_id = n.node_id and i.status = 'active') as last_issue_at,
       (select array_agg(x.indicator_id order by x.indicator_id) from ideas.indicator_nodes x where x.node_id = n.node_id) as indicator_ids,
       (select array_agg(distinct y.entity_id) from (
          select ed.dst as entity_id from core.ontology_edges ed join core.entities en on en.entity_id = ed.dst where ed.src = n.node_id and ed.active
          union select ed.src from core.ontology_edges ed join core.entities en on en.entity_id = ed.src where ed.dst = n.node_id and ed.active) y) as entity_ids
from core.ontology_nodes n
where n.kind <> 'company';
grant select on public.v_node_activity to anon, authenticated;

create or replace view public.v_entity_issues
with (security_invoker = true) as
select ie.entity_id, i.issue_key, i.title, i.importance, i.ecosystem, i.event_type, i.latest_published_at, ie.direction, ie.basis
from ideas.issue_entities ie join ideas.supply_chain_issues i on i.issue_key = ie.issue_key
where i.status = 'active';
grant select on public.v_entity_issues to anon, authenticated;

create or replace view public.v_node_issues
with (security_invoker = true) as
select x.node_id, i.issue_key, i.title, i.importance, i.ecosystem, i.event_type, i.latest_published_at
from ideas.issue_nodes x join ideas.supply_chain_issues i on i.issue_key = x.issue_key
where i.status = 'active';
grant select on public.v_node_issues to anon, authenticated;

-- 해자 카드 상세 (지금은 /briefs/[id] 가 ideas.briefs 를 직접 읽는다 → 이 뷰로 옮기면 테이블 변경과 분리된다)
create or replace view public.v_brief_detail
with (security_invoker = true) as
select b.id, b.cik, co.ticker, co.name, e.entity_id, b.kind, b.as_of, b.version, b.status, b.title, b.brief, b.research, b.critique,
       b.datapack_summary, b.scores, b.model, b.prompt_version, b.usage, b.error, b.created_at, b.ontology_nodes,
       coalesce((select jsonb_agg(to_jsonb(p) - 'brief_id' order by p.due_date nulls last) from ideas.predictions p where p.brief_id = b.id), '[]'::jsonb) as predictions
from ideas.briefs b
join core.companies co on co.cik = b.cik
left join core.entities e on e.cik = b.cik;
grant select on public.v_brief_detail to anon, authenticated;
