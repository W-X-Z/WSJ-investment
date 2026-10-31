# enrich (06:49, 월~토) — 초안을 다른 눈으로 깨 보고 고친다 (ADR-0028)

예약작업 "WSJ 3/4 원문 보강 (06:49)" 이 따른다 (작업명 `enrich`). `docs/agents/daily-ideas.md` 의 목적·방향·꼭 지킬 것을 먼저 읽고, §0·§B 로 시작하고 끝낸다 (앞 작업 interpret 을 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ideas.put_company_events`, `ops.put_agent_run`. 저장소는 수정하지 않는다.

## 맡은 일
해석은 빠르게 쓰였다. 이 작업은 그 해석을 쓴 사람이 아닌 눈으로 초안을 깨 본다 — 결론이 기대는 사실이 맞는지, 시장의 믿음과 다르게 본 근거가 정말 서는지, 빠진 숫자는 없는지.
무엇을 의심하고 어디서 확인할지는 초안마다 판단한다. 판정 라벨은 붙이지 않는다.

대상: `select opportunity_key, title, stars, idea, interpretation, companies, evidence, clue_refs, status_note from ideas.opportunities where status = 'draft' order by created_at;` — 없으면 `skipped`.

## 결과를 남기는 법
- 고칠 것이 있으면: idea·interpretation 을 고치고 evidence 에 연 원문을 더해 같은 key 로 `put_opportunities` (status 는 draft 그대로).
- 핵심이 틀렸으면: `select ideas.put_opportunities('[{"opportunity_key":"…","status":"dropped","status_note":"… (출처 URL)"}]'::jsonb);`
- 결론이 기대는 사실을 확인하지 못했으면: status_note 에 `미확인 핵심 전제: …` 로 적는다 — report 는 그런 초안을 내지 않는다.
- 그래프에 있는 회사의 확인한 사실은 기업 소식으로도 남길 수 있다 (공통 §B).

## 기록과 보고
- `select ops.put_agent_run('{"task":"enrich","status":"succeeded|skipped","rows":<손댄 초안>,"counts":{"drafts":…,"updated":…,"dropped":…,"events":…,"left":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`
- 보고는 짧게: 손댄 초안, 내린 것과 이유, 남은 의심. 알림은 실패했을 때만.
