-- 0035: 그래프 조회본 · 조회 함수 · 그래프 제안 (ADR-0031, 백로그 G-2·G-3·G-4)
-- 실행: Supabase SQL 편집기 (사용자). 0034 뒤.
-- 원본은 Git(research/ecosystems/seed_graph.json). 이 테이블은 graph-sync 워크플로가 병합 때마다 덮어쓰는 조회본이다 — 직접 고치지 않는다.
-- 고칠 것은 ideas.put_graph_proposal 로 제안하고, 해석 작업이 그날 그래프 패치에 합친다.

create table if not exists core.graph_nodes (
  id               text primary key,
  kind             text not null,
  label            text not null,
  name             text,                       -- 라벨에서 괄호·설명을 뗀 이름
  ecosystem        text,
  also_in          text[] not null default '{}',
  status           text not null default 'active',   -- active | candidate
  maturity         jsonb,
  maturity_stage   text,
  maturity_history jsonb not null default '[]'::jsonb,
  first_seen       text,
  first_evidence   jsonb,
  codes            jsonb not null default '{}'::jsonb,
  ticker           text,
  exchange         text,
  cik              bigint,
  size_band        text,
  role             text,
  attrs            jsonb not null default '{}'::jsonb,
  graph_sha        text,
  synced_at        timestamptz not null default now()
);
create index if not exists graph_nodes_kind_idx on core.graph_nodes (kind);

create table if not exists core.graph_edges (
  id                     text primary key,
  src                    text not null,
  dst                    text not null,
  relation               text not null,
  direction              text,                 -- demand_to_supply | supply_to_demand | none (온톨로지 술어)
  evidence_tier          text,
  polarity               text,
  confidence             real,
  exposure               text,                 -- core | major | minor | unknown
  exposure_pct           real,                 -- 매출 비중 % (v0.5)
  exposure_year          int,
  exposure_source        text,
  position               text,
  about                  text,
  effective_date         text,
  content_usd_per_system real,
  lead_time_weeks        real,
  note                   text,
  first_evidence_date    text,
  evidence               jsonb not null default '[]'::jsonb,
  attrs                  jsonb not null default '{}'::jsonb,
  graph_sha              text,
  synced_at              timestamptz not null default now()
);
create index if not exists graph_edges_src_idx on core.graph_edges (src, relation);
create index if not exists graph_edges_dst_idx on core.graph_edges (dst, relation);

create table if not exists core.graph_terms (
  term           text not null,                -- 소문자
  node_id        text not null,
  source         text,                         -- alias | label | company_name | native | code | ticker
  raw            text,                         -- 원래 표기
  case_sensitive boolean not null default false,
  synced_at      timestamptz not null default now(),
  primary key (term, node_id)
);

alter table core.graph_nodes enable row level security;
alter table core.graph_edges enable row level security;
alter table core.graph_terms enable row level security;
grant all on core.graph_nodes, core.graph_edges, core.graph_terms to service_role;

-- ── 조회 함수 (예약 작업이 Supabase MCP 로 부른다) ────────────────────────────

-- 글 → 노드. 한·중·일 글자는 포함 여부로, 영문은 단어 경계로, 짧은 이름·티커는 대소문자까지 본다.
create or replace function core.resolve_terms(txt text, max_n int default 40)
returns table (node_id text, kind text, label text, matched text, source text)
language sql stable as $$
  with src as (select coalesce(txt, '') as s, lower(coalesce(txt, '')) as ls),
  hit as (
    select g.node_id, g.term, g.raw, g.source
    from core.graph_terms g, src
    where position(g.term in src.ls) > 0
      and (
        g.term ~ '[^\x01-\x7f]'
        or (not g.case_sensitive and src.ls ~ ('(^|[^a-z0-9])' || regexp_replace(g.term, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') || '($|[^a-z0-9])'))
        or (g.case_sensitive and src.s ~ ('(^|[^A-Za-z0-9])' || regexp_replace(g.raw, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') || '($|[^A-Za-z0-9])'))
      )
  ),
  best as (select distinct on (h.node_id) h.node_id, h.term, h.source from hit h order by h.node_id, length(h.term) desc)
  select b.node_id, n.kind, n.label, b.term, b.source
  from best b join core.graph_nodes n on n.id = b.node_id
  order by length(b.term) desc, n.kind
  limit max_n
$$;

-- 이웃: depth 단계(최대 3)까지 양방향. rels 를 주면 그 관계만.
create or replace function core.graph_neighbors(node text, depth int default 1, rels text[] default null)
returns table (hop int, node_id text, kind text, label text, relation text, dir text, via text, edge_id text,
               exposure text, exposure_pct real, evidence_tier text)
language sql stable as $$
  with recursive walk(hop, node_id, via, relation, dir, edge_id, path) as (
    select 0, node, null::text, null::text, null::text, null::text, array[node]
    union all
    select w.hop + 1,
           case when e.src = w.node_id then e.dst else e.src end,
           w.node_id, e.relation,
           case when e.src = w.node_id then 'out' else 'in' end,
           e.id,
           w.path || (case when e.src = w.node_id then e.dst else e.src end)
    from walk w
    join core.graph_edges e on (e.src = w.node_id or e.dst = w.node_id)
    where w.hop < least(greatest(depth, 1), 3)
      and (rels is null or e.relation = any (rels))
      and not ((case when e.src = w.node_id then e.dst else e.src end) = any (w.path))
  )
  select distinct on (w.node_id) w.hop, w.node_id, n.kind, n.label, w.relation, w.dir, w.via, w.edge_id,
         e.exposure, e.exposure_pct, e.evidence_tier
  from walk w
  join core.graph_nodes n on n.id = w.node_id
  left join core.graph_edges e on e.id = w.edge_id
  where w.hop > 0
  order by w.node_id, w.hop
$$;

-- 아래로 내려가며 공급사 찾기: 노드에서 수요→공급 방향(요구·병목·완화 수단·필요 부품·규칙이 강제하는 것, 기술을 구현한 제품)으로
-- depth 단계(최대 4)까지 내려가고, 닿은 노드마다 그것을 파는(offered_by)·개발하는(develops·holds_ip) 회사.
-- min_exposure_pct: 매출 비중 하한 (숫자가 없으면 범주로 — core 50 · major 10 · minor 0). bands: 규모 (예: {small,mid}).
create or replace function core.suppliers_below(node text, depth int default 2, min_exposure_pct real default null, bands text[] default null)
returns table (company_id text, company text, ticker text, exchange text, size_band text, via_node text, via_label text, hops int,
               relation text, exposure text, exposure_pct real, exposure_year int, "position" text, evidence_tier text, path text[])
language sql stable as $$
  with recursive down(hop, node_id, path) as (
    select 0, node, array[node]
    union all
    select d.hop + 1, nx.nid, d.path || nx.nid
    from down d
    cross join lateral (
      select e.dst as nid from core.graph_edges e
       where e.src = d.node_id and e.relation in ('drives_requirement', 'creates_bottleneck', 'mitigated_by', 'requires', 'raises_content', 'mandates')
      union
      select e.src from core.graph_edges e where e.dst = d.node_id and e.relation = 'implements'
    ) nx
    join core.graph_nodes gn on gn.id = nx.nid and gn.kind <> 'company'
    where d.hop < least(greatest(depth, 0), 4) and not (nx.nid = any (d.path))
  ),
  reach as (select distinct on (node_id) node_id, hop, path from down order by node_id, hop),
  sup as (
    select r.node_id as via, r.hop, r.path, e.dst as cid, e.relation, e.exposure, e.exposure_pct, e.exposure_year, e.position, e.evidence_tier
    from reach r join core.graph_edges e on e.src = r.node_id and e.relation = 'offered_by'
    union all
    select r.node_id, r.hop, r.path, e.src, e.relation, e.exposure, e.exposure_pct, e.exposure_year, e.position, e.evidence_tier
    from reach r join core.graph_edges e on e.dst = r.node_id and e.relation in ('develops', 'holds_ip')
  )
  select s.cid, c.name, c.ticker, c.exchange, c.size_band, s.via, v.label, s.hop, s.relation, s.exposure, s.exposure_pct,
         s.exposure_year, s.position, s.evidence_tier, s.path
  from sup s
  join core.graph_nodes c on c.id = s.cid and c.kind = 'company'
  join core.graph_nodes v on v.id = s.via
  where (min_exposure_pct is null
         or coalesce(s.exposure_pct, case s.exposure when 'core' then 50 when 'major' then 10 when 'minor' then 0 end) >= min_exposure_pct)
    and (bands is null or c.size_band = any (bands))
  order by s.exposure_pct desc nulls last,
           case s.exposure when 'core' then 0 when 'major' then 1 when 'minor' then 2 else 3 end,
           s.hop, c.name
$$;

-- 노드 한 장: 노드 칸, 최근 단서, 층별 첫 등장(단서 기준), 걸린 투자 아이디어·조사 스레드.
create or replace function core.node_signals(node text, n_days int default 30)
returns jsonb
language sql stable as $$
  select jsonb_build_object(
    'node', (select jsonb_build_object('id', g.id, 'kind', g.kind, 'label', g.label, 'status', g.status, 'maturity', g.maturity,
                                       'maturity_history', g.maturity_history, 'first_evidence', g.first_evidence, 'codes', g.codes)
               from core.graph_nodes g where g.id = node),
    'clues', coalesce((select jsonb_agg(q.x) from (
                select jsonb_build_object('title', c.title, 'url', c.url, 'layer', c.extra->>'layer', 'source', c.source_name,
                                          'seen_at', c.seen_at) as x
                from ideas.clues c
                where c.relevant and node = any (c.nodes) and c.seen_at > now() - make_interval(days => n_days)
                order by c.seen_at desc limit 40) q), '[]'::jsonb),
    'first_by_layer', coalesce((select jsonb_object_agg(q.layer, q.first_at) from (
                select coalesce(c.extra->>'layer', 'press') as layer, min(coalesce(c.published_at, c.seen_at)) as first_at
                from ideas.clues c where c.relevant and node = any (c.nodes) group by 1) q), '{}'::jsonb),
    'opportunities', coalesce((select jsonb_agg(jsonb_build_object('key', o.opportunity_key, 'title', o.title, 'stars', o.stars, 'status', o.status))
                from ideas.opportunities o where node = any (o.nodes)), '[]'::jsonb),
    'threads', coalesce((select jsonb_agg(jsonb_build_object('key', t.thread_key, 'title', t.title, 'status', t.status))
                from ideas.threads t where node = any (t.nodes)), '[]'::jsonb)
  )
$$;

revoke all on function core.resolve_terms(text, int), core.graph_neighbors(text, int, text[]),
                       core.suppliers_below(text, int, real, text[]), core.node_signals(text, int) from public, anon, authenticated;
grant execute on function core.resolve_terms(text, int), core.graph_neighbors(text, int, text[]),
                          core.suppliers_below(text, int, real, text[]), core.node_signals(text, int) to service_role;

-- ── 그래프 제안 ────────────────────────────────────────────────────────────────
-- 저장소를 못 바꾸는 작업(검토자 등)도 확인한 관계·노출도·식별자를 근거와 함께 남긴다. 형식은 그래프 패치 JSON 의 한 항목과 같다
-- (pipeline/wsj/ecosystems/graph_patches/from_json.py). 해석 작업이 pending 을 그날 패치에 합치고, graph-sync 가 들어간 것을 applied 로 바꾼다.
create table if not exists ideas.graph_proposals (
  proposal_id bigint generated by default as identity primary key,
  created_at  timestamptz not null default now(),
  by          text not null,                              -- interpret | enrich | report | weekly | user
  kind        text not null check (kind in ('edge', 'node', 'node_update', 'alias')),
  payload     jsonb not null,
  reason      text,                                       -- 왜 (어떤 조사에서)
  status      text not null default 'pending' check (status in ('pending', 'applied', 'rejected')),
  note        text,
  applied_at  timestamptz
);
create index if not exists graph_proposals_status_idx on ideas.graph_proposals (status, created_at);

create or replace function ideas.put_graph_proposal(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; p jsonb; k text; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; why text;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1; k := r->>'kind'; p := r->'payload'; why := null;
    if k not in ('edge', 'node', 'node_update', 'alias') or jsonb_typeof(p) <> 'object' then
      why := 'kind 는 edge|node|node_update|alias, payload 는 객체';
    elsif k = 'edge' and (p->>'from' is null or p->>'relation' is null or p->>'to' is null or p->>'tier' is null
          or jsonb_typeof(p->'evidence') <> 'array' or jsonb_array_length(p->'evidence') < 1
          or exists (select 1 from jsonb_array_elements(p->'evidence') e where coalesce(e->>'url', '') !~ '^https://' or e->>'source_type' is null)) then
      why := 'edge: from·relation·to·tier, evidence 1개 이상(각각 https url·source_type)';
    elsif k = 'node' and (p->>'id' is null or p->>'kind' is null or p->>'label' is null or p->>'ecosystem' is null
          or (p->>'kind' = 'company' and (p->>'ticker' is null or p->>'exchange' is null or p->>'size_band' is null))) then
      why := 'node: id·kind·label·ecosystem (기업은 ticker·exchange·size_band)';
    elsif k in ('node_update', 'alias') and p->>'id' is null then
      why := k || ': id 필수';
    elsif k = 'alias' and jsonb_typeof(p->'aliases') <> 'array' then
      why := 'alias: aliases 배열';
    elsif coalesce(r->>'by', '') = '' then
      why := 'by 필수 (작업 이름)';
    end if;
    if why is not null then rej := rej || jsonb_build_object('i', i, 'reason', why); continue; end if;
    insert into ideas.graph_proposals (by, kind, payload, reason) values (r->>'by', k, p, r->>'reason');
    ok := ok + 1;
  end loop;
  return jsonb_build_object('inserted', ok, 'rejected', rej);
end $$;

alter table ideas.graph_proposals enable row level security;
grant all on ideas.graph_proposals to service_role;
revoke all on function ideas.put_graph_proposal(jsonb) from public, anon, authenticated;
grant execute on function ideas.put_graph_proposal(jsonb) to service_role;
