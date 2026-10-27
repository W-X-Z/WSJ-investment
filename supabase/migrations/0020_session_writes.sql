-- 0020: Claude 예약작업(세션)이 쓰는 두 경로 — 투자 아이디어 저장과 기업 소식 원문 확인. ADR-0016 개정 2.
-- 예약작업은 Supabase MCP 로 아래 두 함수만 호출한다. 함수가 형식·출처·날짜를 검사하고 맞지 않는 행은 버린 뒤 사유를 돌려준다.
-- 공개(anon·authenticated) 역할은 실행할 수 없다.

-- 1) 쓰지 않는 출처 (호스트 끝부분 일치: 'naver.com' 이면 blog.naver.com 도 막힌다)
create table if not exists ideas.source_blocklist (
  host     text primary key,
  reason   text,
  added_at timestamptz not null default now()
);
insert into ideas.source_blocklist (host, reason) values
  ('stockhub.kr', '자동 생성 시세·지표 요약'),
  ('mydailybyte.com', '자동 생성 시세·지표 요약'),
  ('etfshopping.com', '자동 생성 시세·지표 요약'),
  ('judal.co.kr', '자동 생성 시세·지표 요약'),
  ('xn--vj4b13a.com', '시세.com — 원 출처 없는 지표 모음'),
  ('cmoney.tw', '종목 토론 게시판(股市爆料同學會)'),
  ('blog.naver.com', '블로그'),
  ('cafe.naver.com', '카페'),
  ('tistory.com', '블로그'),
  ('youtube.com', '영상 요약'),
  ('thinkpool.com', '종목 토론방')
on conflict (host) do nothing;

create or replace function ideas.url_blocked(u text) returns boolean language sql stable as $$
  select exists (
    select 1 from ideas.source_blocklist b,
      lateral (select lower(regexp_replace(substring(u from '^https?://([^/:?#]+)'), '^www\.', '')) as h) x
    where x.h = b.host or x.h like '%.' || b.host
  )
$$;

-- 2) 기업 소식 원문 확인·추가
-- 행: {event_id?, company_id, kind, published_at, title, url, publisher, tier, importance, lang, text}
--  · event_id 가 있으면(이미 수집된 소식) text(확인한 사실 요약)와 importance 만 고치고 verified 로 표시한다.
--  · 없으면 새 소식으로 넣는다. 같은 기업·같은 URL 이 이미 있으면 그 행을 고친다.
create or replace function ideas.put_company_events(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ins int := 0; upd int := 0; rej jsonb := '[]'::jsonb;
  eid text; cid text; u text; pub timestamptz; imp int; txt text; existing_id text;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1;
    eid := nullif(r->>'event_id', '');
    txt := nullif(btrim(r->>'text'), '');
    imp := coalesce((r->>'importance')::int, null);
    if imp is not null and imp not between 1 and 3 then
      rej := rej || jsonb_build_object('i', i, 'reason', 'importance 는 1~3'); continue;
    end if;
    if txt is not null and length(txt) > 1200 then txt := left(txt, 1200); end if;

    if eid is not null then
      update ideas.company_events
         set text = coalesce(txt, text),
             importance = coalesce(imp, importance),
             extra = coalesce(extra, '{}'::jsonb) || jsonb_build_object('verified_by', 'claude', 'verified_at', now())
       where event_id = eid;
      if found then upd := upd + 1; else rej := rej || jsonb_build_object('i', i, 'reason', 'event_id 없음: ' || eid); end if;
      continue;
    end if;

    cid := r->>'company_id'; u := r->>'url';
    begin
      pub := (r->>'published_at')::timestamptz;
    exception when others then
      rej := rej || jsonb_build_object('i', i, 'reason', 'published_at 형식'); continue;
    end;
    if cid !~ '^company:[a-z0-9_]+$' then rej := rej || jsonb_build_object('i', i, 'reason', 'company_id 형식'); continue; end if;
    if coalesce(r->>'kind', '') not in ('filing', 'disclosure', 'revenue', 'news') then rej := rej || jsonb_build_object('i', i, 'reason', 'kind'); continue; end if;
    if u is null or u !~ '^https://' then rej := rej || jsonb_build_object('i', i, 'reason', 'https URL 필요'); continue; end if;
    if ideas.url_blocked(u) then rej := rej || jsonb_build_object('i', i, 'reason', '차단 출처: ' || u); continue; end if;
    if nullif(btrim(r->>'title'), '') is null then rej := rej || jsonb_build_object('i', i, 'reason', 'title 필요'); continue; end if;
    if pub > now() + interval '1 day' or pub < now() - interval '45 days' then
      rej := rej || jsonb_build_object('i', i, 'reason', 'published_at 은 최근 45일 안'); continue;
    end if;

    select event_id into existing_id from ideas.company_events where company_id = cid and url = u limit 1;
    if existing_id is not null then
      update ideas.company_events
         set text = coalesce(txt, text), importance = coalesce(imp, importance),
             extra = coalesce(extra, '{}'::jsonb) || jsonb_build_object('verified_by', 'claude', 'verified_at', now())
       where event_id = existing_id;
      upd := upd + 1;
    else
      insert into ideas.company_events (event_id, company_id, kind, published_at, title, url, publisher, tier, importance, lang, text, extra)
      values ('c' || left(md5(cid || '|' || u || '|' || left(r->>'title', 120)), 19), cid, r->>'kind', pub, left(btrim(r->>'title'), 300), u,
              left(r->>'publisher', 120), coalesce(nullif(r->>'tier', ''), 'third_party_report'), coalesce(imp, 2), left(r->>'lang', 8), txt,
              jsonb_build_object('verified_by', 'claude', 'verified_at', now(), 'added_by', 'claude'))
      on conflict (event_id) do nothing;
      ins := ins + 1;
    end if;
  end loop;
  return jsonb_build_object('inserted', ins, 'updated', upd, 'rejected', rej);
end $$;

-- 3) 투자 아이디어 저장 (엔진 검증을 통과한 행 = python -m wsj.ecosystems.ideas --emit-sql 의 출력)
-- 활성 행: 형식·★·기업·근거 사슬(단계 2개 이상, 단계마다 https 근거)·최신 근거 날짜를 다시 검사한다.
-- 종료 행({idea_key, status:'closed', trend, close_reason, updated_at}): 있는 아이디어의 상태·사유만 바꾼다.
create or replace function ideas.put_ideas(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; closed int := 0; rej jsonb := '[]'::jsonb; reason text; is_new boolean; step jsonb; ev jsonb;
  run_id bigint;
begin
  if jsonb_typeof(rows) <> 'array' then raise exception 'rows 는 JSON 배열이어야 한다'; end if;
  insert into ops.collector_runs (collector, status, params, runner_host) values ('ideas', 'running', jsonb_build_object('method', 'session'), 'claude-session')
  returning id into run_id;
  for r in select * from jsonb_array_elements(rows) loop
    i := i + 1; reason := null;
    if coalesce(r->>'idea_key', '') !~ '^[0-9a-f]{12}$' then
      rej := rej || jsonb_build_object('i', i, 'reason', 'idea_key 형식'); continue;
    end if;

    if r->>'status' = 'closed' then
      update ideas.investment_ideas
         set status = 'closed', trend = 'weakened', close_reason = left(r->>'close_reason', 300), updated_at = now()
       where idea_key = r->>'idea_key' and status = 'active';
      if found then closed := closed + 1; else rej := rej || jsonb_build_object('i', i, 'reason', '닫을 활성 아이디어 없음'); end if;
      continue;
    end if;

    is_new := not exists (select 1 from ideas.investment_ideas where idea_key = r->>'idea_key');
    if coalesce(r->>'status', '') <> 'active' then reason := 'status';
    elsif coalesce(r->>'type', '') not in ('bottleneck', 'transition', 'confirmation', 'risk') then reason := 'type';
    elsif coalesce(r->>'trend', '') not in ('new', 'strengthened', 'weakened', 'unchanged') then reason := 'trend';
    elsif nullif(btrim(r->>'title'), '') is null or nullif(btrim(r->>'thesis'), '') is null then reason := 'title·thesis';
    elsif coalesce((r->>'stars')::int, 0) not between 1 and 3 then reason := 'stars';
    elsif coalesce(r->>'primary_company', '') !~ '^company:[a-z0-9_]+$' then reason := 'primary_company';
    elsif jsonb_typeof(r->'companies') <> 'array' or jsonb_array_length(r->'companies') = 0 then reason := 'companies';
    elsif jsonb_typeof(r->'chain') <> 'array' or jsonb_array_length(r->'chain') < 2 then reason := '근거 사슬 2단계 미만';
    elsif coalesce(r->>'method', '') not in ('session', 'llm') then reason := 'method';
    elsif (r->>'last_signal_at') is null or (r->>'last_signal_at')::date > current_date + 1 then reason := 'last_signal_at';
    elsif is_new and (r->>'last_signal_at')::date < current_date - 14 then reason := '새 아이디어는 14일 안의 최신 근거가 필요';
    end if;
    if reason is null then
      for step in select * from jsonb_array_elements(r->'chain') loop
        if nullif(btrim(step->>'claim'), '') is null or jsonb_typeof(step->'evidence') <> 'array' or jsonb_array_length(step->'evidence') = 0 then
          reason := '근거 없는 단계'; exit;
        end if;
        for ev in select * from jsonb_array_elements(step->'evidence') loop
          if coalesce(ev->>'url', '') !~ '^https://' or coalesce(ev->>'id', '') !~ '^[SG][0-9]+$' then reason := '근거 URL·id 형식'; exit; end if;
          if ideas.url_blocked(ev->>'url') then reason := '차단 출처: ' || (ev->>'url'); exit; end if;
        end loop;
        exit when reason is not null;
      end loop;
    end if;
    if reason is not null then rej := rej || jsonb_build_object('i', i, 'key', r->>'idea_key', 'reason', reason); continue; end if;

    insert into ideas.investment_ideas as t (
      idea_key, status, trend, type, title, thesis, stars, stars_reason, primary_company, companies, chain, risks, watch, what_changed,
      nodes, ecosystems, signal_refs, evidence_count, last_signal_at, updated_at, model, method, usage)
    values (
      r->>'idea_key', 'active', r->>'trend', r->>'type', left(btrim(r->>'title'), 120), left(btrim(r->>'thesis'), 600), (r->>'stars')::int,
      left(r->>'stars_reason', 300), r->>'primary_company', r->'companies', r->'chain', coalesce(r->'risks', '[]'::jsonb), coalesce(r->'watch', '[]'::jsonb),
      nullif(r->>'what_changed', ''),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'nodes', '[]'::jsonb)) x), '{}'),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'ecosystems', '[]'::jsonb)) x), '{}'),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'signal_refs', '[]'::jsonb)) x), '{}'),
      coalesce((r->>'evidence_count')::int, 0), (r->>'last_signal_at')::date, now(), r->>'model', r->>'method', r->'usage')
    on conflict (idea_key) do update set
      status = excluded.status, trend = excluded.trend, type = excluded.type, title = excluded.title, thesis = excluded.thesis,
      stars = excluded.stars, stars_reason = excluded.stars_reason, primary_company = excluded.primary_company, companies = excluded.companies,
      chain = excluded.chain, risks = excluded.risks, watch = excluded.watch, what_changed = excluded.what_changed, nodes = excluded.nodes,
      ecosystems = excluded.ecosystems, signal_refs = excluded.signal_refs, evidence_count = excluded.evidence_count,
      last_signal_at = excluded.last_signal_at, updated_at = excluded.updated_at, model = excluded.model, method = excluded.method,
      usage = excluded.usage, close_reason = null;
    ok := ok + 1;
  end loop;
  update ops.collector_runs set status = 'succeeded', finished_at = now(), rows_upserted = ok + closed,
         watermark = jsonb_build_object('upserted', ok, 'closed', closed, 'rejected', jsonb_array_length(rej))
   where id = run_id;
  return jsonb_build_object('upserted', ok, 'closed', closed, 'rejected', rej);
end $$;

-- 4) 기업 소식 뷰: 확인 내용(text)과 확인 여부를 끝에 붙인다 (프론트 계약: 열은 끝에만 추가)
create or replace view public.v_company_events
with (security_invoker = true) as
select event_id, company_id, kind, published_at, title, url, publisher, tier, importance, lang,
       text, (extra ? 'verified_by') as verified
from ideas.company_events
where published_at > now() - interval '30 days';

-- 권한: 함수는 서비스 역할(=MCP·파이프라인)만. 차단 목록은 공개 읽기.
revoke all on function ideas.put_ideas(jsonb), ideas.put_company_events(jsonb), ideas.url_blocked(text) from public;
revoke all on function ideas.put_ideas(jsonb), ideas.put_company_events(jsonb) from anon, authenticated;
grant execute on function ideas.put_ideas(jsonb), ideas.put_company_events(jsonb), ideas.url_blocked(text) to service_role;
alter table ideas.source_blocklist enable row level security;
drop policy if exists "read all" on ideas.source_blocklist;
create policy "read all" on ideas.source_blocklist for select to anon, authenticated using (true);
grant select on ideas.source_blocklist to anon, authenticated;
grant all on ideas.source_blocklist to service_role;
grant select on public.v_company_events to anon, authenticated;
