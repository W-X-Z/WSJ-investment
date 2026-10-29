# report (07:37, 월~토) — 조사가 끝난 후보로 리포트를 쓰고, 목표주가를 함께 낸다

예약작업 "WSJ 4/5 리포트 + 목표주가 (07:37)" 이 따른다. 큐 두 개: `public.v_q_candidates_needing_report`(조사 끝난 선택 경로 — 그 기업의 활성 리포트가 조사 뒤 갱신되지 않은 것)와
`public.v_q_ideas_needing_valuation`(평가가 없거나 리포트를 고쳐 쓴 뒤 산출하지 않은 활성 리포트). 쓰는 함수: `ideas.put_ideas`, `ideas.put_valuations`, `ideas.put_assessments`, `ops.put_agent_run`.
공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다. p23 이 false 면 "0024 미적용" 을 보고·알림하고 `failed` 로 끝낸다 — 목표주가 없는 리포트는 쓰지 않는다.
**리포트와 목표주가는 한 몸이다.** 가격·주식수가 있는 리포트를 목표주가 없이 저장하는 것은 이 작업의 실패다.

## 1. 큐
- `select issue_key, issue_title, path_id, company, company_label, claim, verdict, research_summary, event_ids, existing_idea, score from public.v_q_candidates_needing_report;`
- `select idea_key, title, primary_company, stars, reason, last_valuation_as_of from public.v_q_ideas_needing_valuation;`
- 둘 다 비어 있으면 `skipped` 로 기록하고 끝낸다 (보고 1줄). 기존 리포트의 날마다 재판단은 하지 않는다 — 조사·채점이 들어왔을 때만 손댄다.

## 2. 2단계 입력과 작성 — 공통 §D
- 공통 §D 의 입력 명령(`--hypotheses-from-db ../.ideas_run/s2/queue.json`)으로 s2 를 만든다. `s2/queue.json` 의 selected 가 1 의 첫 큐와 같은 수인지 본다(적으면 note 에 "경로 상세 없음 N").
- `s2/prompt.system.md`·`s2/prompt.payload.json` 을 끝까지 읽고 `s2/raw.json` 을 쓴다 — 공통 §D 의 규칙 전부. 특히:
  - 새 리포트는 payload.hypotheses(Q1, Q2 …)에서. research_result 가 confirmed·partial 이면 event_ids 의 근거 id 로 chain 을 잇는다.
  - 두 번째 큐의 리포트(평가 없음·재산출 전)는 action=update(새 사실이 있으면) 또는 keep 으로 두되 **valuation 을 쓴다** — keep 이어도 existing.valuation 이 없거나 낡았으면 쓴다.
  - 그 밖의 기존 리포트는 keep (새 사실이 없으면). 주 기업 자신의 새 사실이 없으면 강화하지 않는다.
  - existing 의 watch 채점(grades)은 verify 작업의 일이다 — 여기서는 이번에 고쳐 쓰는 리포트의 것만 채점한다.

## 3. 검증 — 공통 §E
- 공통 §E 의 명령(`--hypotheses ../.ideas_run/s2/queue.json`). `rejected:` 는 고쳐 다시(최대 2번). **exit 2 (`valuation missing`) 면 raw.json 의 그 아이디어에 valuation 을 채우고 다시** — `--allow-missing-valuations` 는 close 가 없는 주가(valuation_skipped)일 때만, 사유를 note 에.

## 4. 저장 — 공통 §F
- `s2/sql/01_…` → `zy_valuations.sql` → `zz_assessments.sql` 순서로 그대로 실행. zy 뒤 `select count(*) from ideas.valuations where as_of = current_date;` 가 rows.valuations.json 의 건수와 같은지 확인한다.

## 5. 완료 조건과 기록
- `select count(*) as left_candidates from public.v_q_candidates_needing_report;` — 0 (refuted 나 범위 밖으로 쓰지 못한 후보는 note 에 사유).
- `select count(*) as left_valuations from public.v_q_ideas_needing_valuation;` — 0 (close 가 없는 기업만 남을 수 있다 — note 에).
- `select count(*) as valuations_today from ideas.valuations where as_of = current_date;`
- `select ops.put_agent_run('{"task":"report","status":"succeeded","rows":<new+update+weaken>,"counts":{"queue_candidates":…,"queue_valuations":…,"new":…,"update":…,"weaken":…,"keep":…,"close":…,"valuations_today":…,"left_candidates":…,"left_valuations":…},"note":"…"}'::jsonb);`
  리포트는 저장했는데 목표주가 수가 바뀐 리포트 수보다 적으면 status `failed` (note 에 어느 리포트가 빠졌는지).

## 6. 보고와 알림
- 보고 7줄 이내: 큐(후보 N·재산출 N) · 아이디어 new/update/weaken/close/keep · **목표주가 저장 N/M (확인 쿼리 결과)** 과 바뀐 리포트(제목 · 현재 → 기대 주가 · 여력 · 확신 · 시총) · 평가 못 쓴 리포트(사유) · 남은 큐.
- 알림: 공통 §G 의 결과 알림(report) — 첫 문장에 `목표주가 저장 N/M`. 실패 알림은 §G.
