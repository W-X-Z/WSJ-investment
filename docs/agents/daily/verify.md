# verify (08:11, 월~토) — 기한이 온 예측을 채점해 ★ 를 움직이고, 하루를 보고한다

예약작업 "WSJ 5/5 검증 + 보고 (08:11)" 이 따른다. 큐 = `public.v_q_predictions_due` (활성 리포트의 watch 중 pending 이고 due 가 지난 것).
쓰는 함수: `ideas.put_company_events`, `ideas.put_ideas`, `ideas.put_assessments`, `ops.put_agent_run`. 공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다.
채점이 ★ 를 움직인다 (ADR-0022): 적중 1 → ★2, 2 → ★3(문턱 충족 시), 반증 조건 성립 → 종료, 빗나감 2 → ★1. 사람의 확신이 아니라 예측의 결과가 등급을 정한다.

## 1. 큐
`select idea_key, title, primary_company, stars, watch_index, what, due, metric, threshold, direction from public.v_q_predictions_due;`
- 비어 있으면 채점은 건너뛰고 4 의 보고만 한다 (status `skipped`).

## 2. 예측마다 결과 찾기 — 공통 §B 의 출처 규칙
- metric·threshold 가 가리키는 숫자를 원문(공시·월매출·실적 발표·고객 발표·가격 지표)에서 찾는다. 찾은 원문은 그 기업의 소식으로 저장한다 (공통 §B 의 put_company_events) — 채점의 근거 id 가 된다.
- 판정: `hit` = 적힌 조건이 그대로 일어났다(strengthen 예측이면 적중, weaken 반증 조건이면 반증 성립) · `miss` = 기한이 지났는데 조건이 안 일어났다 · `void` = 조건을 확인할 길이 없다(공시가 안 나옴 등). hit·miss 는 근거 id 필수.

## 3. 채점 반영 (엔진)
- 소식을 저장한 **뒤에** 입력을 만든다 (근거 id 가 레지스트리에 있어야 한다):
  `.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s3 --emit-prompt ../.ideas_run/s3/prompt.json`
- `s3/prompt.payload.json` 의 evidence 에서 저장한 소식의 근거 id(E…·S…)를 찾는다.
- `s3/raw.json` = `{"model": "claude-opus-5-5", "ideas": [], "grades": [{"idea_key": "…", "index": <watch_index>, "status": "hit|miss|void", "evidence": "S12", "note": "한 줄"}]}` — 리포트는 쓰지 않는다.
- `.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s3 --from-llm-json ../.ideas_run/s3/raw.json --method session --model claude-opus-5-5 --out ../.ideas_run/s3/rows.json --emit-sql ../.ideas_run/s3/sql --allow-missing-valuations`
  `verification:` 줄이 ★·종료의 기록이다. `s3/sql/` 의 `01_…`(★ 가 바뀌거나 종료된 리포트 — 있을 때만) → `zz_assessments.sql`(채점이 반영된 watch·판단) 을 그대로 실행한다.

## 3-1. 테제 근거 (0028 뒤, ADR-0025)
- 오늘 경로 중 `thesis` 가 붙은 것: `select h.issue_key, p->>'id' as path_id, p->'thesis' as thesis, p->>'claim' as claim from ideas.issue_hypotheses h cross join lateral jsonb_array_elements(h.paths) p where h.as_of = current_date and p->'thesis' is not null and p->'thesis' <> 'null'::jsonb;`
  → 경로마다 `select ideas.put_thesis_evidence($j$[{"thesis_key":"…","direction":"+","what":"<claim 한 줄>","ref":{"issue_key":"…","path_id":"…"},"weight":1}]$j$::jsonb);` (조사 verdict 가 refuted 인 경로는 direction '-', weight 2).
- 오늘 채점한 예측이 테제 수혜 기업의 것이면 hit=+ · miss=- 로 같은 함수에 기록한다.

## 4. 하루 보고
- 사슬: `select task, status, rows, counts, note, started_at, finished_at from public.v_agent_runs where run_date = (now() at time zone 'Asia/Seoul')::date order by started_at;`
- 피드: `select idea_key, title, stars, trend, updated_at from public.v_investment_ideas where status='active' and updated_at > now() - interval '24 hours' order by updated_at desc;` 와 `select idea_key, expected_upside_pct, confidence from public.v_valuations where as_of = current_date;`

## 5. 완료 조건과 기록
- `select count(*) as left_due from public.v_q_predictions_due;` — 0 (void 도 pending 에서 빠진다).
- `select ops.put_agent_run('{"task":"verify","status":"succeeded|skipped","rows":<채점 수>,"counts":{"due":…,"hit":…,"miss":…,"void":…,"promoted":…,"closed":…,"left_due":…},"note":"…"}'::jsonb);`

## 6. 보고와 알림
- 보고 7줄 이내: 채점 N(적중·빗나감·보류)과 그로 바뀐 ★·종료 · 오늘 사슬(collect/paths/research/report 의 status 와 건수) · 오늘 바뀐 리포트와 목표주가 · 실패한 작업이 있으면 그 note.
- 알림은 **매일** 보낸다: 첫 문장에 오늘 사슬 한 줄(예 "collect ✓ paths 3 research 5 report 2(목표주가 2/2) verify 1"), 이어서 반증 성립으로 종료된 리포트·★ 가 바뀐 리포트·실패한 작업. 모두 skipped 였으면 "오늘 새 일 없음" 한 줄.
