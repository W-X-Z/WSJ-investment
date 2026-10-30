# report (07:37, 월~토) — 초안을 다듬어 내고, 기존 아이디어를 고치고, 하루를 알린다 (ADR-0028)

예약작업 "WSJ 4/4 리포트 (07:37)" 이 따른다 (작업명 `report`). 공통 규칙 `docs/agents/daily-ideas.md` §0·§B 로 시작하고 끝낸다 (앞 작업 enrich 를 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ops.put_agent_run`. 저장소는 수정하지 않는다.

사용자가 보는 것은 **★1~5 · 제목 · 투자 아이디어 · 해석 · 근거** 뿐이다. 작성 규칙 `docs/agents/writing.md` 를 끝까지 읽고 시작한다.

## 1. 초안을 낸다
`select opportunity_key, title, stars, idea, interpretation, companies, evidence, nodes, clue_refs from ideas.opportunities where status = 'draft' order by created_at;`
초안마다:
- **제목**을 규칙대로 고친다 — '[원인]에 따른 [대상] [변화]' 명사형, 80자 이내.
- **아이디어·해석**을 읽기 쉬운 한국어로 다듬는다. 내부 용어(writing.md 목록)와 노드 id 를 지운다. 숫자는 원문에 있는 것만.
- **★** 를 다시 매긴다 — "나에게 얼마나 큰 투자 기회인가" (writing.md 의 ★ 뜻). 이미 같은 이야기로 크게 오른 회사는 낮게.
- **같은 회사·같은 이야기**의 active 아이디어가 이미 있으면 새로 내지 말고 그것을 고친다(근거·해석 합치기, ★ 다시) — 초안은 `dropped`, status_note "→ <기존 key> 에 합침".
- 근거가 1개도 열리지 않는 초안은 내지 않는다 — draft 로 두고 note 에.
- 내기: 같은 key 로 전체를 다시 보내며 `"status": "active"`.

## 2. 기존 아이디어를 고친다
- 오늘 들어온 그 회사의 공시·실적·큰 소식이 이야기를 바꿨으면 active 아이디어를 고친다(★ 포함):
  `select o.opportunity_key, o.title, o.stars, e.title as news, e.url, e.published_at from ideas.opportunities o cross join lateral jsonb_array_elements(o.companies) c join public.v_company_events e on e.company_id = c->>'company' where o.status = 'active' and e.published_at > now() - interval '30 hours' and e.importance >= 2;`
- 이야기가 끝났으면(계약 해지, 사업 철수, 인수로 상장폐지) `status: closed`, status_note 에 이유. 판정·채점은 하지 않는다.

## 3. 기록
- `select status, count(*) from ideas.opportunities group by 1;` 와 `select opportunity_key, title, stars from ideas.opportunities where published_at > now() - interval '24 hours' order by stars desc;`
- `select ops.put_agent_run('{"task":"report","status":"succeeded|skipped","rows":<낸 것 + 고친 것>,"counts":{"published":…,"updated":…,"merged":…,"closed":…,"left_drafts":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`

## 4. 하루 알림 (매일)
- 첫 줄: 오늘 사슬 한 줄 — `select task, status, rows from public.v_agent_runs where run_date = (now() at time zone 'Asia/Seoul')::date order by started_at;` (예 "수집 ✓ · 해석 3 · 보강 3(내림 1) · 리포트 2").
- 이어서 **오늘 낸 아이디어** ★ 높은 순: `★★★★ 제목` + 한 줄 요지. 그다음 ★ 가 바뀌었거나 닫힌 아이디어. 실패한 작업이 있으면 그 note.
- 새로 낸 것도 바뀐 것도 없으면 "오늘 새 아이디어 없음" 한 줄.
