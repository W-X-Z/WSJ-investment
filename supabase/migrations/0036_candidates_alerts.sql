-- 0036: 후보 노드 통로 · 수집 이상 알림 (ADR-0031 G-7·T-8, 백로그 M-3)
-- 실행: Supabase SQL 편집기 (사용자). 0035 뒤.
-- 1) 그래프 제안에 'term'(사전 밖 식별자) 종류를 더하고, 후보 기업 노드는 size_band 를 unknown 으로 받는다.
--    수집 단계 candidates(파이썬)가 by='collect' 로 올리고, 해석 작업이 원문을 열어 별칭·codes·후보 노드로 합치거나 rejected 로 둔다.
-- 2) ops.v_collection_alerts: 리포트(07:37)가 알림 첫머리에 붙이는 수집 이상 — 안 돈 수집기·실패·계속 죽는 출처·줄어든 층·본문 0%·DB 크기.
-- 3) ideas.exposure_facts: 미국 공시(10-K·20-F·40-F)의 매출 구성 숫자 (G-8 무료 경로). exposure 수집기(주 1회)가 넣고,
--    주간 개선·해석이 공급 관계의 exposure_pct 로 옮긴다.

alter table ideas.graph_proposals drop constraint if exists graph_proposals_kind_check;
alter table ideas.graph_proposals add constraint graph_proposals_kind_check
  check (kind in ('edge', 'node', 'node_update', 'alias', 'term'));

create or replace function ideas.put_graph_proposal(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; p jsonb; k text; i int := 0; ok int := 0; rej jsonb := '[]'::jsonb; why text;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1; k := r->>'kind'; p := r->'payload'; why := null;
    if k not in ('edge', 'node', 'node_update', 'alias', 'term') or jsonb_typeof(p) <> 'object' then
      why := 'kind 는 edge|node|node_update|alias|term, payload 는 객체';
    elsif k = 'edge' and (p->>'from' is null or p->>'relation' is null or p->>'to' is null or p->>'tier' is null
          or jsonb_typeof(p->'evidence') <> 'array' or jsonb_array_length(p->'evidence') < 1
          or exists (select 1 from jsonb_array_elements(p->'evidence') e where coalesce(e->>'url', '') !~ '^https://' or e->>'source_type' is null)) then
      why := 'edge: from·relation·to·tier, evidence 1개 이상(각각 https url·source_type)';
    elsif k = 'node' and (p->>'id' is null or p->>'kind' is null or p->>'label' is null or p->>'ecosystem' is null
          or (p->>'kind' = 'company' and (p->>'ticker' is null or p->>'exchange' is null
              or (p->>'size_band' is null and coalesce(p->>'status', '') <> 'candidate')))) then
      why := 'node: id·kind·label·ecosystem (기업은 ticker·exchange·size_band — 후보 status=candidate 는 size_band unknown 가능)';
    elsif k in ('node_update', 'alias') and p->>'id' is null then
      why := k || ': id 필수';
    elsif k = 'alias' and jsonb_typeof(p->'aliases') <> 'array' then
      why := 'alias: aliases 배열';
    elsif k = 'term' and coalesce(p->>'term', '') = '' then
      why := 'term: term 필수';
    elsif coalesce(r->>'by', '') = '' then
      why := 'by 필수 (작업 이름)';
    end if;
    if why is not null then rej := rej || jsonb_build_object('i', i, 'reason', why); continue; end if;
    insert into ideas.graph_proposals (by, kind, payload, reason) values (r->>'by', k, p, r->>'reason');
    ok := ok + 1;
  end loop;
  return jsonb_build_object('inserted', ok, 'rejected', rej);
end $$;
revoke all on function ideas.put_graph_proposal(jsonb) from public, anon, authenticated;
grant execute on function ideas.put_graph_proposal(jsonb) to service_role;

-- 수집 이상. level: error(사람이 봐야 함) | warn(눈여겨볼 것) | info. 비어 있으면 이상 없음.
create or replace view ops.v_collection_alerts as
with expected(collector, max_age) as (
  values ('issues', interval '30 hours'), ('company_feed', interval '30 hours'), ('clues', interval '30 hours'),
         ('prices', interval '30 hours'), ('facts', interval '30 hours'), ('fundamentals', interval '30 hours'),
         ('candidates', interval '30 hours'), ('graph_sync', interval '30 hours')
), latest as (
  select distinct on (collector) collector, status, started_at, error
  from ops.collector_runs where started_at > now() - interval '7 days'
  order by collector, started_at desc
), run_alerts as (
  select 'error'::text as level, e.collector as what,
         case when l.collector is null then '7일 동안 실행 기록 없음'
              when l.status = 'failed' then '실패: ' || left(coalesce(l.error, ''), 160)
              when l.status = 'running' and l.started_at < now() - interval '2 hours' then '2시간 넘게 running (중단?)'
              when l.started_at < now() - e.max_age then '마지막 실행 ' || to_char(l.started_at at time zone 'Asia/Seoul', 'MM-DD HH24:MI') || ' KST'
         end as detail
  from expected e left join latest l using (collector)
), clue_runs as (
  select watermark, row_number() over (order by started_at desc) as rn
  from ops.collector_runs where collector = 'clues' and status = 'succeeded' and started_at > now() - interval '4 days'
), src_fail as (   -- 최근 clues 실행 3번 모두에서 죽은 출처 (한 번 실패는 흔하다)
  select f->>'id' as id, count(distinct rn) as n, max(left(f->>'error', 70)) as err
  from clue_runs, jsonb_array_elements(coalesce(watermark->'failed', '[]'::jsonb) || coalesce(watermark->'pages'->'failed', '[]'::jsonb)) f
  where rn <= 3
  group by 1
  having count(distinct rn) >= least(3, (select count(*) from clue_runs where rn <= 3))
), buckets as (    -- 24시간 칸: 0 = 지난 24시간, 1~7 = 그 전 날들
  select floor(extract(epoch from (now() - seen_at)) / 86400)::int as b, coalesce(extra->>'layer', 'press') as layer, relevant, url
  from ideas.clues where seen_at > now() - interval '8 days'
), layer_day as (
  select l.layer, g.b, count(x.url) filter (where x.relevant) as kept
  from (select distinct layer from buckets) l cross join generate_series(0, 7) g(b)
  left join buckets x on x.layer = l.layer and x.b = g.b
  group by 1, 2
), layer_drop as (
  select t.layer, t.kept as today, (select percentile_cont(0.5) within group (order by p.kept) from layer_day p where p.layer = t.layer and p.b between 1 and 7) as med
  from layer_day t where t.b = 0
), body as (
  select count(*) filter (where c.relevant and coalesce(c.extra->>'layer', '') = 'raw') as raw_kept,
         count(t.url) filter (where c.relevant and coalesce(c.extra->>'layer', '') = 'raw' and t.status = 'ok') as raw_body
  from ideas.clues c left join ideas.clue_texts t on t.url = c.url
  where c.seen_at > now() - interval '24 hours'
)
select level, what, detail from run_alerts where detail is not null
union all
select 'warn', '출처 ' || id, '최근 수집 ' || n || '번 연속 실패: ' || coalesce(err, '') from src_fail
union all
select 'warn', '단서 층 ' || layer, '지난 24시간 남긴 ' || today || '건 — 그 전 7일 중앙값 ' || round(med::numeric) || '건의 40% 아래'
from layer_drop where med >= 5 and today < 0.4 * med
union all
select 'warn', '본문', '지난 24시간 원본 층 단서 ' || raw_kept || '건 중 본문을 받은 것 0건' from body where raw_kept >= 5 and raw_body = 0
union all
select 'warn', 'DB 크기', round(pg_database_size(current_database()) / 1048576.0) || 'MB (무료 한도 500MB)'
where pg_database_size(current_database()) > 400 * 1048576::bigint
union all
select 'info', '그래프 제안', count(*) || '건이 3일 넘게 대기 중'
from ideas.graph_proposals where status = 'pending' and created_at < now() - interval '3 days' having count(*) > 0;

revoke all on ops.v_collection_alerts from public, anon, authenticated;
grant select on ops.v_collection_alerts to service_role;

-- 공시의 매출 구성 숫자. kind: revenue(차원별 매출과 그 해 총매출 대비 pct) | concentration(고객·제품 집중도 %) | text('매출의 N%' 문장) | total | none(숫자 못 찾음)
create table if not exists ideas.exposure_facts (
  fact_key    text primary key,                 -- md5(company|url|kind|concept|label)
  company_id  text not null,                    -- 그래프 기업 id
  cik         bigint,
  ticker      text,
  form        text,                             -- 10-K | 20-F | 40-F
  filed       date,
  url         text not null,                    -- 보고서 원문 (exposure_source 로 쓴다)
  period_end  date,
  kind        text not null check (kind in ('revenue', 'concentration', 'text', 'total', 'none')),
  concept     text,
  axes        jsonb not null default '{}'::jsonb,   -- {축: 멤버}
  label       text,                             -- 사람이 읽는 축=멤버 또는 문장
  value       numeric,
  pct         numeric,
  fetched_at  timestamptz not null default now()
);
create index if not exists exposure_facts_company_idx on ideas.exposure_facts (company_id, kind);
alter table ideas.exposure_facts enable row level security;
revoke all on ideas.exposure_facts from public, anon, authenticated;
grant all on ideas.exposure_facts to service_role;
