-- 0025 (ADR-0020): put_ideas 가 가설의 추론 단계를 받는다.
-- 첫 실행(2026-10-29)에서 발견: 엔진은 "(추론)" 단계(근거 없음, inference=true)를 허용하는데 DB 함수는 '근거 없는 단계'로 거부했다.
-- 규칙: 단계는 근거가 있거나(https·id 형식·차단 출처 검사) 추론 단계(inference=true 또는 claim 이 "(추론)" 으로 끝남)여야 하고,
--       근거 있는 단계가 1개 이상이어야 한다. 그 밖은 0021 과 같다. 다시 실행해도 안전하다.
create or replace function ideas.put_ideas(rows jsonb) returns jsonb language plpgsql as $$
declare
  r jsonb; i int := 0; ok int := 0; closed int := 0; rej jsonb := '[]'::jsonb; reason text; is_new boolean; step jsonb; ev jsonb;
  run_id bigint; n_fact int;
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
    elsif r ? 'assessment' and jsonb_typeof(r->'assessment') not in ('object', 'null') then reason := 'assessment 는 객체';
    end if;
    if reason is null then
      n_fact := 0;
      for step in select * from jsonb_array_elements(r->'chain') loop
        if nullif(btrim(step->>'claim'), '') is null or jsonb_typeof(step->'evidence') <> 'array' then
          reason := '단계 형식 (claim·evidence 배열)'; exit;
        end if;
        if jsonb_array_length(step->'evidence') = 0 then
          -- 추론 단계: 근거 없이 허용하되 표시가 있어야 한다 (ADR-0020)
          if coalesce((step->>'inference')::boolean, false) or btrim(step->>'claim') like '%(추론)' then continue; end if;
          reason := '근거 없는 단계 (추론이면 inference=true 또는 "(추론)")'; exit;
        end if;
        n_fact := n_fact + 1;
        for ev in select * from jsonb_array_elements(step->'evidence') loop
          if coalesce(ev->>'url', '') !~ '^https://' or coalesce(ev->>'id', '') !~ '^[SG][0-9]+$' then reason := '근거 URL·id 형식'; exit; end if;
          if ideas.url_blocked(ev->>'url') then reason := '차단 출처: ' || (ev->>'url'); exit; end if;
        end loop;
        exit when reason is not null;
      end loop;
      if reason is null and n_fact < 1 then reason := '근거 있는 단계가 없음 (사실 단계 1개 이상)'; end if;
    end if;
    if reason is not null then rej := rej || jsonb_build_object('i', i, 'key', r->>'idea_key', 'reason', reason); continue; end if;

    insert into ideas.investment_ideas as t (
      idea_key, status, trend, type, title, thesis, stars, stars_reason, primary_company, companies, chain, risks, watch, what_changed,
      nodes, ecosystems, signal_refs, evidence_count, last_signal_at, updated_at, model, method, usage, assessment)
    values (
      r->>'idea_key', 'active', r->>'trend', r->>'type', left(btrim(r->>'title'), 120), left(btrim(r->>'thesis'), 600), (r->>'stars')::int,
      left(r->>'stars_reason', 300), r->>'primary_company', r->'companies', r->'chain', coalesce(r->'risks', '[]'::jsonb), coalesce(r->'watch', '[]'::jsonb),
      nullif(r->>'what_changed', ''),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'nodes', '[]'::jsonb)) x), '{}'),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'ecosystems', '[]'::jsonb)) x), '{}'),
      coalesce((select array_agg(x) from jsonb_array_elements_text(coalesce(r->'signal_refs', '[]'::jsonb)) x), '{}'),
      coalesce((r->>'evidence_count')::int, 0), (r->>'last_signal_at')::date, now(), r->>'model', r->>'method', r->'usage',
      nullif(r->'assessment', 'null'::jsonb))
    on conflict (idea_key) do update set
      status = excluded.status, trend = excluded.trend, type = excluded.type, title = excluded.title, thesis = excluded.thesis,
      stars = excluded.stars, stars_reason = excluded.stars_reason, primary_company = excluded.primary_company, companies = excluded.companies,
      chain = excluded.chain, risks = excluded.risks, watch = excluded.watch, what_changed = excluded.what_changed, nodes = excluded.nodes,
      ecosystems = excluded.ecosystems, signal_refs = excluded.signal_refs, evidence_count = excluded.evidence_count,
      last_signal_at = excluded.last_signal_at, updated_at = excluded.updated_at, model = excluded.model, method = excluded.method,
      usage = excluded.usage, close_reason = null, assessment = coalesce(excluded.assessment, t.assessment);
    ok := ok + 1;
  end loop;
  update ops.collector_runs set status = 'succeeded', finished_at = now(), rows_upserted = ok + closed,
         watermark = jsonb_build_object('upserted', ok, 'closed', closed, 'rejected', jsonb_array_length(rej))
   where id = run_id;
  return jsonb_build_object('upserted', ok, 'closed', closed, 'rejected', rej);
end $$;
