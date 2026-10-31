# report (07:37, 월~토) — 낼 만한 것만 내고, 기존 아이디어를 고치고, 하루를 알린다 (ADR-0028)

예약작업 "WSJ 4/4 리포트 (07:37)" 이 따른다 (작업명 `report`). `docs/agents/daily-ideas.md` 의 목적·방향·꼭 지킬 것과 `docs/agents/writing.md` 를 먼저 읽고, §0·§B 로 시작하고 끝낸다 (앞 작업 enrich 를 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ops.put_agent_run`. 저장소는 수정하지 않는다.

## 맡은 일
사용자가 읽을 만한 것만 낸다. 무엇을 낼지, ★ 를 몇으로 할지, 기존 아이디어 중 무엇을 고칠지는 판단한다.
- 초안: `select opportunity_key, title, stars, idea, interpretation, companies, evidence, nodes, clue_refs, status_note from ideas.opportunities where status = 'draft' order by created_at;`
  writing.md 의 형태로 다듬어 같은 key 로 `"status": "active"` 를 보내 낸다. 같은 회사·같은 이야기의 active 아이디어가 있으면 그쪽에 합치고 초안은 `dropped`(status_note "→ <기존 key> 에 합침").
  결론이 기대는 사실이 확인되지 않았으면(status_note 의 `미확인 핵심 전제`, 보강 기록의 `unverified`) 내지 않는다.
- 기존 아이디어: 오늘 들어온 그 회사의 소식이 이야기를 바꿨으면 고친다(★ 포함). 참고 쿼리:
  `select o.opportunity_key, o.title, o.stars, e.title as news, e.url, e.published_at from ideas.opportunities o cross join lateral jsonb_array_elements(o.companies) c join public.v_company_events e on e.company_id = c->>'company' where o.status = 'active' and e.published_at > now() - interval '30 hours' and e.importance >= 2;`
  이야기가 끝났으면(계약 해지, 사업 철수, 상장폐지) `status: closed` 와 이유.

## 기록
- `select ops.put_agent_run('{"task":"report","status":"succeeded|skipped","rows":<낸 것 + 고친 것>,"counts":{"published":…,"updated":…,"merged":…,"closed":…,"left_drafts":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`

## 하루 알림 (매일)
- 첫 줄: 오늘 사슬 한 줄 — `select task, status, rows from public.v_agent_runs where run_date = (now() at time zone 'Asia/Seoul')::date order by started_at;` (예 "수집 ✓ · 해석 3 · 보강 3(내림 1) · 리포트 2").
- 이어서 오늘 낸 아이디어를 ★ 높은 순으로 `★★★★ 제목` + 한 줄 요지, 그다음 ★ 가 바뀌었거나 닫힌 아이디어, 실패한 작업의 note.
- 새로 낸 것도 바뀐 것도 없으면 "오늘 새 아이디어 없음" 한 줄.
