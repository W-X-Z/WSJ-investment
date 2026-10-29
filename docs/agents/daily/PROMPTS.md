# 예약작업 프롬프트 (ADR-0027 — 2026-10-31 부터)

예약작업 화면에서 아래 네 작업의 프롬프트를 통째로 바꾼다 (시각·모델은 그대로). collect(1/5)와 주간 개선 작업은 바꾸지 않는다.
전환기 작업 "WSJ (전환기) 아침 한 세션 작업 (06:41)" 은 0027 뒤로 매일 한 줄로 끝나므로 꺼도 된다.

## 2/5 — 이름: `WSJ 2/5 발굴 — 이슈 경로 + 약한 신호 + 작은 테제 (06:17)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 2/5 — **discover(발굴)** 작업이다 (ADR-0024 → ADR-0027, 작업명 `discover`, 옛 paths). 세 가지를 한다: ① 새 이슈마다 영향 경로 ≤3 ② 오늘 요일의 선행 출처(월 논문·화 표준·수 학회·IR·목 플랫폼·모델 API·금 채용·소형주 공시·토 전부)에서 약한 신호 ③ **작은 테제(micro) 최대 3개** — 한 기업의 한 제품·고객·계약에서 생기는 변화를 미국·한국 소·중형주(primary)에서 찾아, 6개월 안에 판정되는 형태로 쓴다. 큰 테제를 쪼개 2단계 아래 공급사를 찾는 것이 첫 출발점이다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜와 요일을 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ops.put_agent_run(jsonb)') is not null as p27, to_regprocedure('ideas.put_thesis_research(jsonb)') is not null as p30;` — p27 이 false 면 "0027 미적용" 한 줄로 끝낸다 (알림 없음). p30 이 false 면 문서대로 이슈 경로(A)만 한다.
3. add_repo 로 W-X-Z/WSJ-investment 를 access=push 로 붙이고 안내된 clone 명령으로 `--depth 20` clone 한다. `docs/agents/daily/discover.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다 — A 이슈 경로(v_q_issues_needing_paths → 1단계 입력 → 경로 → 엔진 검사 → zx_issue_hypotheses.sql) → B 오늘의 약한 신호(put_weak_signals) → C 작은 테제(후보 → 크기·노출·조용함·리레이팅 → put_theses) → D 새 기업은 JSON 그래프 패치 + PR → E 완료 조건·실행 기록. 공통 규칙은 `docs/agents/daily-ideas.md`(§0·§A·§B), 출처·네 질문·조용함·리레이팅 규칙은 `docs/agents/thesis.md`. 절차의 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계:
   - Supabase 쓰기는 `ideas.put_issue_hypotheses`, `ideas.put_weak_signals`, `ideas.put_theses`, `ops.put_agent_run` 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 리포트·목표주가는 쓰지 않는다(4/5 작업의 일).
   - 저장소 변경은 `research/`(theses·weak_signals·ecosystems/patches 와 패치가 바꾸는 그래프 파일)와 생성 파일 `apps/web/src/data/` 뿐이다. 브랜치 `auto/discover-YYYYMMDD` 로 PR 을 올리고, CI(pytest · typecheck-build · Vercel)가 모두 통과하고 바뀐 파일이 전부 그 두 경로 안이면 스스로 병합한다. 그 밖의 경로가 바뀌면 병합하지 않는다. main 직접 push·강제 push 금지.
   - 근거는 WebFetch 로 직접 연 원문만. 거부된 도구·URL 은 다른 수단(curl·미러·캐시)으로 우회하지 않고 건너뛰어 기록한다. 단편 단서는 출처 종류(rumor)를 밝히고 쓴다. 매수/매도 권유·시점 예측은 쓰지 않는다.
5. 커밋 메시지 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>` 를, PR 본문 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)` 를 붙인다.
6. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 문서의 규칙대로(실패일 때만 — 새 테제는 5/5 의 하루 알림에 들어간다).
```

## 3/5 — 이름: `WSJ 3/5 조사 — 작은 테제 반박 우선 + 경로 (06:49)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment)의 아침 사슬 3/5 — **research(조사)** 작업이다 (ADR-0024 → ADR-0027). 오늘 발굴된 작은 테제(micro)의 가장 약한 고리(weakest_link)를 **반박 우선으로** 원문에서 확인하고(반박되면 그 테제는 그날 닫힌다), 남은 칸에 리포트 후보 경로의 마지막 고리(이 기업이 정말 그 부품을 그 고객에게 공급하는지, 비중, 숫자로 나타났는지)를 확인한다. 합쳐 최대 8개. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ops.put_agent_run(jsonb)') is not null as p27, to_regprocedure('ideas.put_thesis_research(jsonb)') is not null as p30;` — p27 이 false 면 "0027 미적용" 한 줄로 끝낸다 (알림 없음). p30 이 false 면 문서대로 경로만 한다.
3. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 안내된 clone 명령으로 `--depth 1` clone 한다. `docs/agents/daily/research.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다 — 앞 작업(discover) 기다리기 → 큐(v_q_theses_needing_research 최대 3 → v_q_paths_needing_research) → 원문 확인 → 기업 소식(put_company_events)·관측치(put_observations) → 판정(put_thesis_research · put_path_research) → 완료 조건 → 실행 기록. 공통 규칙은 `docs/agents/daily-ideas.md`(§0·§B·§C). 절차의 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계: Supabase 쓰기는 `ideas.put_company_events`, `ideas.put_observations`, `ideas.put_thesis_research`, `ideas.put_path_research`, `ops.put_agent_run` 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 저장소는 수정·커밋하지 않는다. 근거는 WebFetch 로 직접 연 원문 — 단편 단서(소문·채용 공고·전시회 후기)는 출처 종류를 밝히고 쓰되 자동 생성 시세 요약·날짜 없는 글·출처 없는 숫자는 쓰지 않는다. 거부된 도구·URL 은 우회하지 않고 기록한다. 리포트·목표주가는 쓰지 않는다(4/5 작업의 일).
5. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 문서의 규칙대로(실패일 때만).
```

## 4/5 — 이름: `WSJ 4/5 리포트 + 목표주가 (07:37)` (이름 그대로)
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 4/5 — **report(리포트 + 목표주가)** 작업이다 (ADR-0024 → ADR-0027). 조사가 끝난 후보 — 이슈 경로와 **조사에서 살아남은 작은 테제(micro)의 소·중형 primary** — 로 기업 리서치 리포트를 쓰고 목표주가를 함께 낸다 — **리포트와 목표주가는 한 몸이다**. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ops.put_agent_run(jsonb)') is not null as p27;` — false 면 "0027 미적용" 한 줄로 끝낸다 (알림 없음).
3. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 안내된 clone 명령으로 `--depth 1` clone 한다. `docs/agents/daily/report.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다 — 앞 작업(research) 기다리기 → 큐 세 개(v_q_candidates_needing_report · v_q_thesis_candidates_needing_report · v_q_ideas_needing_valuation) → 2단계 입력(--hypotheses-from-db, 작은 테제 후보가 이어 붙는다) → raw.json(리포트·예측·**valuation 필수**) → 엔진 검증(exit 2 `valuation missing` 이면 valuation 을 채워 다시) → 저장(01_ → zy_valuations → zz_assessments) → 확인 쿼리 → 완료 조건 → 실행 기록. 공통 규칙은 `docs/agents/daily-ideas.md`(§0·§D·§E·§F·§G). 절차의 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계: Supabase 쓰기는 `ideas.put_ideas`, `ideas.put_valuations`, `ideas.put_assessments`, `ops.put_agent_run` 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 저장소는 수정·커밋하지 않는다.
   목표주가는 ADR-0023 대로 **쓴다**: 약세·기본·강세 시나리오의 내재 주가를 확률로 가중한 12개월 기대 주가(모형 산출)이고, 매수/매도 권유·시점 예측은 쓰지 않는다. 가격·주식수가 있는 new/update/weaken 리포트에 valuation 을 빼고 저장하는 것은 이 작업의 실패다.
5. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다.
6. 알림은 문서 §G 의 규칙대로. 보낼 때 첫 문장에 `목표주가 저장 N/M` (M = 이번에 새로 쓰거나 고친 리포트 수).
```

## 5/5 — 이름: `WSJ 5/5 검증 + 테제 감시 + 보고 (08:11)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 5/5 — **verify(검증 + 테제 감시 + 하루 보고)** 작업이다 (ADR-0024 → ADR-0027). 기한이 온 예측을 채점해 ★ 를 움직이고(적중 → ★ 상향, 반증 성립 → 종료), 테제의 반증 기한·첫 신호를 확인해 단계를 옮기거나 닫고(토요일은 큰 테제 점검과 작은 테제 성적표까지), 오늘 사슬(수집 → 발굴 → 조사 → 리포트 → 검증)을 한 번 보고한다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜와 요일을 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ops.put_agent_run(jsonb)') is not null as p27, to_regprocedure('ideas.put_thesis_research(jsonb)') is not null as p30;` — p27 이 false 면 "0027 미적용" 한 줄로 끝낸다 (알림 없음). p30 이 false 면 테제 감시는 건너뛴다.
3. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 안내된 clone 명령으로 `--depth 1` clone 한다. `docs/agents/daily/verify.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다 — 앞 작업(report) 기다리기 → 큐(v_q_predictions_due · v_q_thesis_watch) → 예측마다 결과 원문 확인·소식 저장 → s3 입력 → raw.json 의 grades(리포트는 쓰지 않는다) → 엔진 검증(--allow-missing-valuations) → 01_(있으면)·zz_assessments 실행 → 테제 근거·감시·판정(토요일: 큰 테제 점검, thesis.md 2부) → 하루 보고 → 완료 조건 → 실행 기록. 공통 규칙은 `docs/agents/daily-ideas.md`(§0·§B·§C·§E·§F·§G). 절차의 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계: Supabase 쓰기는 `ideas.put_company_events`, `ideas.put_ideas`(엔진이 만든 ★·종료 행만), `ideas.put_assessments`, `ideas.put_thesis_evidence`, `ideas.put_theses`(단계·종료·조용함 갱신만), `ideas.put_observations`, `ops.put_agent_run` 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 저장소는 수정·커밋하지 않는다. 새 리포트·목표주가·새 테제는 쓰지 않는다. hit·miss·반증 성립은 원문 근거가 있을 때만. 거부된 도구·URL 은 우회하지 않고 기록한다.
5. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다.
6. 알림은 **매일** 보낸다: 첫 문장에 오늘 사슬 한 줄(예 "collect ✓ discover 경로 3·테제 2 research 5(반박 1) report 2(목표주가 2/2) verify 1"), 이어서 새 작은 테제(제목 · primary · 크기 · 조사 판정), 반증 성립으로 종료된 리포트·테제, stage 가 바뀐 테제, ★ 가 바뀐 리포트, 실패한 작업과 그 note. 토요일은 작은 테제 성적 한 줄. 모두 skipped 였으면 "오늘 새 일 없음" 한 줄.
```
