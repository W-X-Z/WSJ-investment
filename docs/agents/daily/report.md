# report (07:37, 월~토) — 낼 만한 것만 내고, 기존 아이디어를 고치고, 하루를 알린다 (ADR-0028)

예약작업 "WSJ 4/4 리포트 (07:37)" 이 따른다 (작업명 `report`). `docs/agents/daily-ideas.md` 의 목적·방향·꼭 지킬 것과 `docs/agents/writing.md` 를 먼저 읽고, §0·§B 로 시작하고 끝낸다 (앞 작업 enrich 를 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ops.put_agent_run`. 저장소는 수정하지 않는다.

## 맡은 일
사용자가 읽을 만한 것만 낸다. 무엇을 낼지, ★ 를 몇으로 할지, 기존 아이디어 중 무엇을 고칠지는 판단한다.
- 초안: `select opportunity_key, title, stars, idea, interpretation, companies, evidence, nodes, clue_refs, status_note from ideas.opportunities where status = 'draft' order by created_at;`
  writing.md 의 형태로 다듬어 같은 key 로 `"status": "active"` 를 보내 낸다. 같은 회사·같은 이야기의 active 아이디어가 있으면 그쪽에 합치고 초안은 `dropped`(status_note "→ <기존 key> 에 합침").
  결론이 기대는 사실이 확인되지 않았으면(status_note 의 `미확인 핵심 전제`, 보강 기록의 `unverified`) 내지 않는다.
- 검토자가 직접 쓰거나 결론을 바꾼 초안(status_note 가 `검토자 작성:` 으로 시작)은 쓴 사람이 아닌 눈으로 한 번 더 본다 — 결론을 고리로 나눠, 결론이 기대는 원문을 다시 열어 그 주장을 실제로 뒷받침하는지. 무너지는 고리가 있으면 내지 않고 이유를 status_note 에 적는다.
- 기존 아이디어: 오늘 들어온 그 회사의 소식이 이야기를 바꿨으면 고친다(★ 포함) — 그 소식은 `history` 에 날짜 항목으로 더한다(writing.md). 히스토리·brief 가 아직 비어 있는 활성 아이디어는 하루 한둘씩 채운다(근거·스레드의 날짜 있는 사실로). 고칠 때는 brief 칩의 숫자(배수·2배 조건)도 같이 맞추고, 제목이 아이디어 전체를 대표하는지도 본다. 참고 쿼리:
  `select o.opportunity_key, o.title, o.stars, e.title as news, e.url, e.published_at from ideas.opportunities o cross join lateral jsonb_array_elements(o.companies) c join public.v_company_events e on e.company_id = c->>'company' where o.status = 'active' and e.published_at > now() - interval '30 hours' and e.importance >= 2;`
- 정책·시장 사건 (사용자 2026-11-04: 중간선거 다음 날 AI 전력주 급락을 놓침). 아이디어에 그 회사 이름이 없어도 이야기를 바꾸는 바깥 사건을 잇는다.
  · 업종 동반 급변: 미국 장 마감 뒤 감지기(comove)가 남긴 단서 — `select title, summary, url, companies, extra->'comove' as move from ideas.clues where source_id = 'comove' and seen_at > now() - interval '20 hours';`
    와 원인 기사 `select title, url, source_name from ideas.clues where source_id = 'comove_cause' and seen_at > now() - interval '20 hours';`.
    급변 묶음에 든 기업의 활성 아이디어가 있으면 원인을 원문으로 확인해 `history` 에 그날 항목으로 더한다 — 원인이 정책·정치면 kind `external`, 수급·업종 매매면 `flow`.
    원인이 확인되지 않으면 "원인 미확인"으로 쓰지 않고 그날 나온 사실(지수 대비 폭, 같이 빠진 종목)만 적는다. 실적 같은 개별 원인이 섞였으면 가른다.
  · 정책 테마: 분류기가 정책 테마를 붙인 단서 — `select title, url, source_name, extra->'themes' as themes, published_at from ideas.clues where relevant and extra ? 'themes' and seen_at > now() - interval '30 hours';`
    활성 아이디어의 `brief.exposures` 와 테마가 겹치면 그 아이디어에 닿는 사건인지 판단한다. 닿으면 history(kind `external`)에 더하고, 리스크 칸이나 ★ 를 바꿀 만큼이면 고친다.
    참고 쿼리: `select o.opportunity_key, o.title, c.title as news, c.url from ideas.opportunities o join ideas.clues c on c.extra->'themes' ?| array(select jsonb_array_elements_text(o.brief->'exposures')) where o.status = 'active' and c.relevant and c.seen_at > now() - interval '30 hours';`
  · `brief.exposures` 가 비어 있는 활성 아이디어는 고칠 때 채운다 — 이 아이디어가 기대는 바깥 조건을 정책 테마 키로 (writing.md).
  이야기가 끝났으면(계약 해지, 사업 철수, 상장폐지) `status: closed` 와 이유.

## 기록
- `select ops.put_agent_run('{"task":"report","status":"succeeded|skipped","rows":<낸 것 + 고친 것>,"counts":{"published":…,"updated":…,"merged":…,"closed":…,"left_drafts":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`

## 하루 알림 (매일)
- 첫 줄: 오늘 사슬 한 줄 — `select task, status, rows from public.v_agent_runs where run_date = (now() at time zone 'Asia/Seoul')::date order by started_at;` (예 "수집 ✓ · 해석 3 · 보강 3(내림 1) · 리포트 2").
- 둘째 줄(이상이 있을 때만): 수집 이상 — `select level, what, detail from ops.v_collection_alerts order by level;` 의 error 는 모두, warn 은 세 개까지 한 줄로 (예 "⚠ 수집: facts 실패(미국 0/40) · 출처 jedec_jc42 3번 연속 실패"). 0036 전이면 건너뛴다. 비어 있으면 쓰지 않는다.
- 업종 동반 급변이 있었으면 한 줄 (예 "⚡ 전력 59곳 중앙값 -6.0% · S&P500 +1.6% — 중간선거 민주당 상·하원 승리 보도 (Forgent·Modine)").
- 이어서 오늘 낸 아이디어를 ★ 높은 순으로 `★★★★ 제목` + 한 줄 요지, 그다음 ★ 가 바뀌었거나 닫힌 아이디어, 실패한 작업의 note.
- 새로 낸 것도 바뀐 것도 없으면 "오늘 새 아이디어 없음" 한 줄.
