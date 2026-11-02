# enrich (06:49, 월~토) — 검토자: 초안을 다른 눈으로 다시 검토하고, 확인되지 않은 고리는 더 조사한다 (ADR-0028)

예약작업 "WSJ 3/4 검토 (06:49)" 이 따른다 (옛 이름 "원문 보강") (작업명 `enrich`). `docs/agents/daily-ideas.md` 의 목적·방향·꼭 지킬 것을 먼저 읽고, §0·§B 로 시작하고 끝낸다 (앞 작업 interpret 을 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ideas.put_company_events`, `ideas.put_thread`, `ideas.put_graph_proposal`, `ops.put_agent_run`. 저장소는 수정하지 않는다.

## 맡은 일
해석은 빠르게 쓰였다. 이 작업은 그 해석을 쓴 사람이 아닌 눈으로 초안을 다시 검토하는 **검토자**다 (사용자, 2026-11-01: "다시 검토하는 역할자가 필요하다").
- 결론을 고리로 나눠 각 고리가 원문 사실인지, 추론인지, 과장인지 가른다. 인용한 원문을 다시 열어 그 주장을 실제로 뒷받침하는지 본다 — 같은 원문 안의 반대 내용, 다른 맥락의 사건을 증거로 끌어온 것, "아무도 연결하지 않았다"가 "검색에서 못 찾았다"인 것.
- 확인되지 않은 고리는 "확인 필요"로 남기지 않는다. 직접 더 조사해서 확인하거나 반증한다 — 규정 조문, 제품 사양, 업계·연구 자료, 경쟁사 제품까지.
- 시장의 믿음과 다르게 본 근거가 정말 서는지, 돈이 정말 그 회사로 가는지(같은 일을 하는 다른 회사, 더 싼 대안), 지금 가격이 무엇을 반영하는지를 다시 본다. 같은 부품을 파는 다른 회사와 매출 비중은 그래프에 먼저 묻는다 (`daily-ideas.md` §D — `core.suppliers_below`·`core.graph_neighbors`).
- 검토하며 확인한 매출 비중·고객·자리·식별자는 그래프 제안(`ideas.put_graph_proposal`)으로 남긴다 — 다음 날 해석이 그래프에 합친다.
- 결론과 ★ 의 강도를 가장 약한 고리에 맞춰 고친다. 고리가 무너지면 내린다.
무엇을 의심하고 어디서 확인할지는 초안마다 판단한다. 판정 라벨은 붙이지 않는다.

대상:
- 초안: `select opportunity_key, title, stars, idea, interpretation, companies, evidence, clue_refs, status_note from ideas.opportunities where status = 'draft' order by created_at;`
- 해석이 건너뛴 결정: `select watermark->'skipped' as skipped, watermark->'picked' as picked from ops.collector_runs where collector = 'agent:interpret' and started_at > now() - interval '12 hours' order by started_at desc limit 1;`
  초안이 없어도 끝내지 않는다. 건너뛴 결정 중 몇 개를 골라 그 이유가 목적·방향에 맞는지 본다 — 특히 오래됨·공시·숫자·많이 오름·회사 크기만으로 내린 것. 이유가 틀렸으면 직접 조사해 초안을 쓰거나(draft) 스레드로 연다.

## 결과를 남기는 법
- 고칠 것이 있으면: idea·interpretation 을 고치고 evidence 에 연 원문을 더해 같은 key 로 `put_opportunities` (status 는 draft 그대로).
- 핵심이 틀렸으면: `select ideas.put_opportunities('[{"opportunity_key":"…","status":"dropped","status_note":"… (출처 URL)"}]'::jsonb);`
- 더 조사해도 결론이 기대는 사실을 확인도 반증도 못 했으면: 무엇을 어디까지 찾아봤는지와 함께 status_note 에 `미확인 핵심 전제: …` 로 적는다 — report 는 그런 초안을 내지 않는다. 그 고리는 스레드로 되돌린다 (`kind: returned`, `opportunity_key` 연결) — 다음 날 해석이 이어서 판다.
- 그래프에 있는 회사의 확인한 사실은 기업 소식으로도 남길 수 있다 (공통 §B).

## 기록과 보고
- `select ops.put_agent_run('{"task":"enrich","status":"succeeded|skipped","rows":<손댄 초안>,"counts":{"drafts":…,"updated":…,"dropped":…,"events":…,"left":…,"skips_reviewed":…,"skips_reversed":…,"threads_returned":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`
- 보고는 짧게: 손댄 초안, 내린 것과 이유, 남은 의심. 알림은 실패했을 때만.
