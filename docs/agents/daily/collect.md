# collect (05:23, 월~토) — 오늘 수집이 끝났는지 확인하고, 안 됐으면 실행시킨다

예약작업 "WSJ 1/4 수집 (05:23)" 이 따른다 (이름은 옛 "1/5" 여도 같다). 큐는 없다 — GitHub Actions `issues` 워크플로(이슈·기업 소식·가격·재무·환율)를 오늘 한 번 돌게 하는 것이 일이다 (ADR-0024).
공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다. 쓰는 함수: `ops.put_agent_run` 뿐.

## 1. 오늘 수집됐나
`select collector, status, started_at, finished_at, rows_upserted from ops.collector_runs where collector in ('issues','company_feed','prices','facts','fundamentals') and started_at > now() - interval '12 hours' order by started_at desc;`
- 오늘(KST 00:00 이후) issues 와 company_feed 가 succeeded 면 3 으로.

## 2. 실행
- `gh api "repos/W-X-Z/WSJ-investment/actions/workflows/issues.yml/runs?per_page=3"` 로 본다. 진행 중이면 기다리고, 없거나 실패했으면
  `gh api -X POST repos/W-X-Z/WSJ-investment/actions/workflows/issues.yml/dispatches -f ref=main` 로 실행시킨다.
- `timeout 590 bash -c 'until <1 의 쿼리로 succeeded 확인>; do sleep 30; done'` 를 반복해 최대 45분 기다린다. GitHub 에서는 이 워크플로 실행(dispatch)만 한다.

## 3. 완료 조건과 기록
- 완료 조건: 1 의 쿼리에서 오늘 issues·company_feed 가 succeeded. prices·facts·fundamentals 는 실패해도 완료로 치되 note 에 적는다.
- 건수: `select (select count(*) from ideas.supply_chain_issues where first_seen > now() - interval '24 hours') as new_issues, (select count(*) from ideas.company_events where published_at > now() - interval '3 days') as recent_events;`
- `select ops.put_agent_run('{"task":"collect","status":"succeeded","rows":<new_issues>,"counts":{"new_issues":…,"recent_events":…},"note":"…"}'::jsonb);`
  45분 안에 끝나지 않았으면 status `failed`, note 에 마지막 워크플로 상태.

## 4. 보고와 알림
- 보고 2줄: 수집 상태(어느 수집기가 성공·실패) · 새 이슈 N · 최근 기업 소식 N.
- 알림은 실패했을 때만(45분 안에 issues 가 succeeded 가 아닐 때): 첫 문장에 무엇이 안 됐는지.
