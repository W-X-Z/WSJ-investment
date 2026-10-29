# paths (06:17, 월~토) — 새 이슈마다 영향 경로를 최대 3개 세운다 (1단계 가설)

예약작업 "WSJ 2/5 이슈 → 영향 경로 (06:17)" 이 따른다. 큐 = `public.v_q_issues_needing_paths` (활성 · 중요도 6+ · 5일 안 · 경로 묶음 없음). 쓰는 함수: `ideas.put_issue_hypotheses`, `ops.put_agent_run`.
공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다. p26 이 false 면 "0026 미적용" 을 보고·알림하고 `skipped` 로 끝낸다.

## 1. 큐
`select issue_key, title, importance, ecosystem, published_at from public.v_q_issues_needing_paths;`
- 비어 있으면 `skipped` 로 기록하고 끝낸다 (보고 1줄).
- 오늘 수집이 아직 안 끝났으면(`select status from ops.collector_runs where collector='issues' and started_at > now() - interval '6 hours' order by started_at desc limit 1;` 가 succeeded 가 아님)
  `timeout 590 bash -c 'until …; do sleep 30; done'` 로 최대 20분 기다린 뒤 큐를 다시 읽는다. 그래도 안 끝났으면 쌓인 것으로 진행하고 note 에 "수집 미완료".

## 2. 1단계 입력과 가설 후보 — 공통 §A
- 공통 §A 의 첫 명령으로 입력을 만들고 `s1/hypo.system.md`·`s1/hypo.payload.json` 을 끝까지 읽는다.
- **큐에 있는 이슈만 쓴다**: payload.signals 의 이슈 신호(kind=issue)에서 `issue_key` 가 큐에 있는 것을 고르고, 그 신호의 evidence 첫 id 를 trigger 로 이슈마다 경로 ≤3 을 `s1/hypotheses.json` 에 쓴다.
  큐의 이슈가 payload 에 없으면(출처 URL 없음 등) 보고에 "신호 없음: issue_key" 로 남긴다 — 5일이 지나면 큐에서 빠진다.
- 공통 §A 의 검사·선택 명령을 돌린다. `hypothesis rejected:` 가 절반 넘으면 사유대로 고쳐 한 번 더 (최대 2번).

## 3. 저장
- `s1/sql/zx_issue_hypotheses.sql` 을 Read 해서 그대로 execute_sql 로 실행한다. 결과의 rejected(이슈 없음·claim 10자 미만·paths 1~3개)가 있으면 hypotheses.json 을 고쳐 2 의 검사부터 다시.

## 4. 완료 조건과 기록
- `select count(*) as left_in_queue from public.v_q_issues_needing_paths;` — 0 이어야 한다 (신호 없음으로 남긴 이슈는 note 에).
- `select count(*) as paths_today, sum((select count(*) from jsonb_array_elements(paths) p where (p->>'selected')::boolean)) as selected from ideas.issue_hypotheses where as_of = current_date;`
- `select ops.put_agent_run('{"task":"paths","status":"succeeded","rows":<이슈 수>,"counts":{"issues":…,"paths":…,"selected":…,"rejected":…,"left_in_queue":…},"note":"…"}'::jsonb);`

## 5. 보고와 알림
- 보고 4줄 이내: 큐 N → 경로 쓴 이슈 N(경로 N, 그중 리포트 후보 N) · 거부 N(사유 한 줄) · 신호 없음 N · 남은 큐 N.
- 알림은 실패했을 때만: 큐가 있는데 하나도 저장하지 못했을 때, DB 쓰기 실패.
