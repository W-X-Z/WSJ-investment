-- 투자 아이디어 상세를 "핵심 요약 콜아웃 → 주가 차트(이슈 포인트) → 날짜별 히스토리 → 근거"로 바꾼다 (사용자 2026-11-04).
-- history: [{"date":"2026-07-23","title":"NVIDIA 와 $15억 다년 계약","body":"…자세한 설명…","url":"https://…"}] — 날짜순 이슈. 차트의 점 하나 = 항목 하나.

alter table ideas.opportunities add column if not exists history jsonb not null default '[]'::jsonb;

create or replace view public.v_opportunities
with (security_invoker = true) as
select opportunity_key, title, stars, idea, interpretation, companies, evidence, nodes, clue_refs, status, status_note, created_at, updated_at, published_at,
       history
from ideas.opportunities
where status = any (array['active'::text, 'closed'::text]);

-- 웹이 아이디어 차트에 쓰는 일봉 (최근 400일). raw.px_daily 는 이미 anon 읽기 정책이 있다.
create or replace view public.v_px_daily
with (security_invoker = true) as
select ticker, trade_date, close
from raw.px_daily
where close is not null and trade_date > current_date - 400;
grant select on public.v_px_daily to anon, authenticated;

-- put_opportunities: history 를 받는다 (있을 때만 바꾼다). 각 항목은 date(YYYY-MM-DD)·title 필수, body·url 선택.
create or replace function ideas.put_opportunities(rows jsonb)
 returns jsonb
 language plpgsql
as $function$
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
    if r ? 'history' and (jsonb_typeof(r->'history') <> 'array'
       or exists (select 1 from jsonb_array_elements(r->'history') h where coalesce(h->>'date', '') !~ '^\d{4}-\d{2}-\d{2}$' or length(coalesce(h->>'title', '')) < 3)) then
      rej := rej || jsonb_build_object('i', i, 'reason', 'history 는 배열, 각각 date(YYYY-MM-DD)·title'); continue;
    end if;
    -- 상태·히스토리만 바꾸기 (제목·아이디어 없이)
    if exists_ and not (r ? 'title') and not (r ? 'idea') then
      update ideas.opportunities set status = coalesce(st, status), status_note = coalesce(r->>'status_note', status_note),
             history = case when r ? 'history' then r->'history' else history end,
             interpretation = coalesce(r->>'interpretation', interpretation),
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
    insert into ideas.opportunities as o (opportunity_key, title, stars, idea, interpretation, companies, evidence, nodes, clue_refs, history, status, status_note, model, published_at, updated_at)
    values (k, r->>'title', (r->>'stars')::smallint, r->>'idea', r->>'interpretation', r->'companies', r->'evidence',
            coalesce((select array_agg(distinct x) from jsonb_array_elements_text(coalesce(r->'nodes', '[]'::jsonb)) x), '{}'),
            coalesce(r->'clue_refs', '[]'::jsonb), coalesce(r->'history', '[]'::jsonb), coalesce(st, 'draft'), r->>'status_note', left(r->>'model', 60),
            case when coalesce(st, 'draft') = 'active' then now() end, now())
    on conflict (opportunity_key) do update set
      title = excluded.title, stars = excluded.stars, idea = excluded.idea, interpretation = coalesce(excluded.interpretation, o.interpretation),
      companies = excluded.companies, evidence = excluded.evidence,
      nodes = case when r ? 'nodes' then excluded.nodes else o.nodes end,
      clue_refs = case when r ? 'clue_refs' then excluded.clue_refs else o.clue_refs end,
      history = case when r ? 'history' then excluded.history else o.history end,
      status = coalesce(st, o.status), status_note = coalesce(excluded.status_note, o.status_note), model = coalesce(excluded.model, o.model),
      published_at = case when coalesce(st, o.status) = 'active' and o.published_at is null then now() else o.published_at end,
      updated_at = now();
    ok := ok + 1;
  end loop;
  return jsonb_build_object('upserted', ok, 'rejected', rej);
end $function$;
