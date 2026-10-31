# enrich (06:49, 월~토) — 초안의 사실을 원문으로 채우고 고친다 (ADR-0028)

예약작업 "WSJ 3/4 원문 보강 (06:49)" 이 따른다 (작업명 `enrich`). 공통 규칙 `docs/agents/daily-ideas.md` §0·§B 로 시작하고 끝낸다 (앞 작업 interpret 을 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ideas.put_company_events`, `ops.put_agent_run`. 저장소는 수정하지 않는다.

해석은 빠르게 쓰였다. 이 작업은 **그 해석이 기대는 사실이 맞는지, 숫자가 빠지지 않았는지** 원문으로 본다. 판정 라벨은 붙이지 않는다 — 틀린 것은 고치고, 핵심이 틀렸으면 내리지 않는다(dropped).

## 1. 대상
`select opportunity_key, title, stars, idea, interpretation, companies, evidence, clue_refs from ideas.opportunities where status = 'draft' order by created_at;`
— 없으면 `skipped`. 한 실행에 최대 8개(오래된 것부터), 나머지는 다음 날.

## 2. 초안마다
1. **핵심 사실 하나를 먼저 깨 본다**: 아이디어가 무너지는 사실(예: "이 회사가 그 고객에게 그 부품을 공급한다", "계약 규모가 매출의 N% 다")을 원문에서 확인한다.
   반대 증거부터 찾는다 — 경쟁사가 그 자리를 가져갔다는 보도, 고객의 다른 공급사, 매출 비중이 작다는 공시, 양산이 늦다는 원문, 같은 이야기로 이미 크게 오른 주가.
   **당사자 자료만으로 확인하지 않는다**: 회사·파트너의 보도자료·공시·콜은 그 이야기를 하는 쪽이다. 핵심 전제마다 당사자가 아닌 출처 1개 이상 — 표준·플랫폼 주인의 로드맵(예: NVIDIA 800V 로드맵은 고체변압기를 2029년 선택지로 둔다), 고객, 경쟁사의 일정, 분석기관.
2. **빠진 숫자와 근거를 채운다**: 그 제품의 매출 비중, 고객·계약 규모, 시총, 최근 12개월 주가 흐름, 그리고 이 이야기가 언제부터 알려졌고 주가·증권사가 어떻게 반응했는지 — 아이디어 3·4번 문장(회사 크기에 비해 얼마나 큰가, 시장이 이미 아는가)이 원문으로 서도록. 원문에서 읽은 것만. 멀티플로 주가를 계산하지 않는다.
3. **결과**
   - 맞으면: idea·interpretation 의 숫자·문장을 고치고 evidence 에 원문을 더해 `put_opportunities` 로 다시 보낸다(status 는 draft 그대로, ★ 는 바꿀 이유가 있을 때만).
   - 핵심이 틀렸으면: `select ideas.put_opportunities('[{"opportunity_key":"…","status":"dropped","status_note":"원문에서 …가 아님 (출처 URL)"}]'::jsonb);`
   - 확인할 길이 없으면(공시·IR 없음): 결론이 그 사실에 기대지 않으면 idea 의 '틀릴 수 있는 지점' 에 적는다. **결론이 기대는 사실(핵심 전제)이면** status_note 에 `미확인 핵심 전제: …` 로 적는다 — report 는 그런 초안을 내지 않는다.
4. 그래프에 있는 회사의 확인한 사실은 기업 소식으로도 남긴다 (공통 §B).

## 3. 기록과 보고
- `select ops.put_agent_run('{"task":"enrich","status":"succeeded|skipped","rows":<손댄 초안>,"counts":{"drafts":…,"updated":…,"dropped":…,"events":…,"left":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`
- 보고 4줄 이내: 손댄 초안 수 · 내린 것(제목 · 이유) · 채운 핵심 숫자 · 남은 초안.
- 알림은 실패했을 때만.
