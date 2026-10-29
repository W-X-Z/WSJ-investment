# 공통 규칙 — 아침 작업 다섯 개가 공유하는 전제·형식·엔진 명령 (ADR-0024)

아침 일은 한 세션이 아니라 다섯 예약작업이 나눠 한다 — 절차는 작업마다 `docs/agents/daily/<task>.md` 에 있고, 이 문서는 그 다섯이 공유하는 **전제·입력 형식·작성 규칙·검증·저장·알림 규칙**이다.
작업 문서가 "공통 §X" 라고 가리키면 여기의 그 절을 그대로 따른다. 두 곳이 어긋나면 작업 문서보다 이 문서가, 이 문서보다 사람이 승인한 PR 이 이긴다.

| 작업 | 문서 | 큐 | 쓰는 함수 |
|---|---|---|---|
| collect 05:23 | daily/collect.md | Actions `issues` 워크플로 | (없음) |
| paths 06:17 | daily/paths.md | `v_q_issues_needing_paths` | put_issue_hypotheses |
| research 06:49 | daily/research.md | `v_q_paths_needing_research` | put_company_events · put_observations · put_path_research |
| report 07:37 | daily/report.md | `v_q_candidates_needing_report` · `v_q_ideas_needing_valuation` | put_ideas · put_valuations · put_assessments |
| verify 08:11 | daily/verify.md | `v_q_predictions_due` | put_company_events · put_ideas · put_assessments · put_thesis_evidence |
| thesis 토 09:17 | thesis.md | `v_theses` (활성 구조 가설) | put_theses · put_thesis_evidence · put_observations · put_company_events |

모든 작업이 `ops.put_agent_run` 으로 실행 기록을 남긴다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다. 이 문서를 바꾸려면 사람이 승인한 PR 이어야 한다.

**이 시스템의 일은 좋은 가설을 세우는 것이다** (ADR-0020): 변화가 어떤 경로로 어느 기업의 숫자를 언제 얼마나 바꾸는지 — 시장이 아직 반영하지 않은 것을 — 추론으로 세우고,
날짜 있는 예측(watch)으로 검증하고, 가치평가로 기댓값(목표주가)을 낸다. 근거는 가설을 막는 문이 아니라 시험하는 도구다. ★ 는 확신이 아니라 검증 단계(★1 가설 · ★2 부분 확인 · ★3 확인).
주 기업은 미국·한국 상장사만 (ADR-0021). 영향의 크기·시점·확률은 LLM 의 판단이고, 엔진은 그 판단의 형식(경로·방향·effect_pct·반증 조건·예측·시나리오)만 검사한다 (ADR-0024).

## 0. 모든 작업의 시작과 끝
시작:
- `date` 로 KST(UTC+9) 오늘 날짜를 구한다. 일요일이면 "일요일" 한 줄로 끝낸다.
- add_repo 로 W-X-Z/WSJ-investment 를 붙이고 `--depth 1` clone. `cd pipeline && python3 -m venv .venv && .venv/bin/pip install -q -e .` 작업 폴더는 `../.ideas_run/` (커밋하지 않는다).
- Supabase MCP get_project_url · get_publishable_keys 로 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`(sb_publishable_…)를 export 한다. secret 키는 쓰지 않는다.
- Supabase MCP execute_sql (project_id: dcatgfivsvbktylmtvgf):
  `select to_regprocedure('ops.put_agent_run(jsonb)') is not null as p27, to_regprocedure('ideas.put_issue_hypotheses(jsonb)') is not null as p26, to_regprocedure('ideas.put_valuations(jsonb)') is not null as p23;`
  p27 이 false 면 "0027 미적용" 을 보고하고 알림을 보낸 뒤 끝낸다 (큐가 없다). p26·p23 은 작업 문서가 말하는 대로.
- `select ops.put_agent_run('{"task":"<작업>","status":"running"}'::jsonb);`
끝:
- 작업 문서의 **완료 조건** 쿼리를 실행해 결과를 보고에 적는다. 큐가 비어 할 일이 없었으면 status 는 `skipped`.
- `select ops.put_agent_run('{"task":"<작업>","status":"succeeded|skipped|failed","rows":N,"counts":{…},"note":"한 줄"}'::jsonb);` — 같은 날 같은 작업은 한 행(다시 돌리면 덮어쓴다).
- 보고는 작업 문서의 줄 수 안에서. 알림은 작업 문서의 규칙일 때만.
- 공통 경계: DB 쓰기는 작업 문서에 적힌 함수와 `ops.put_agent_run`, 읽기용 select 뿐이다. 저장소는 수정·커밋하지 않는다. 주가에 대한 판단은 valuation 의 시나리오로만 — 매수/매도 권유·시점 예측은 쓰지 않는다 (목표주가는 모형 산출이지 권유가 아니다).

## A. 1단계 — 가설 후보(이슈별 영향 경로)의 형식
- 입력은 `.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s1 --emit-prompt ../.ideas_run/s1/prompt.json --emit-research ../.ideas_run/s1/research.json --leads-out ../.ideas_run/s1/leads.json --emit-hypotheses ../.ideas_run/s1/hypo.json`
  (`--emit-hypotheses` 가 있으면 1단계 프롬프트까지 쓰고 끝난다.) `s1/hypo.system.md` 를 읽고 `s1/hypo.payload.json` 을 Read 로 2,000줄씩 끝까지 읽는다. payload.signals 의 이슈 신호에는 `issue_key` 가 있다.
- `s1/hypotheses.json` = `{"model": "claude-opus-5-5", "issues": [{"trigger": "S12", "change": "…", "paths": [...]}]}` — **이슈마다 경로 최대 3개**.
  경로 = 변화 근거 id → 그래프 경로(노드 id) → (있으면) 미국·한국 기업 → effect_pct·lead_quarters → why_unpriced → falsifier → research(확인할 것).
  적당한 미국·한국 기업이 없으면 company 를 null 로 두고 경로만 — 이슈 탭에 '업계 영향'으로 남는다. 안전한 것만 모으지 말고 대담한 2차·3차 고리를 섞는다; 걸러내는 것은 엔진의 일이다. existing 과 같은 논리면 extends 에 idea_key.
- 검사·선택: `.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s1 --from-hypotheses ../.ideas_run/s1/hypotheses.json --hypotheses-out ../.ideas_run/s1/selected.json --emit-research-plan ../.ideas_run/s1/research_plan.json --emit-sql ../.ideas_run/s1/sql`
  엔진이 검사(근거 id·노드·시장 범위)하고 채점(구체·대담·반증 가능·설명력 각 3점, 경로 끊김·기업 중복 감점)해 기업이 있는 경로 중 상위 max_ideas 개를 리포트 후보로 고른다(기업당 1개, 생태계마다 1개 이상).
  `hypothesis rejected:` 가 절반 넘으면 사유대로 hypotheses.json 을 고쳐 한 번 더. `s1/sql/zx_issue_hypotheses*.sql` 이 이슈별 경로(≤3, selected·rank·trigger·change 포함) 저장문이다 (이슈 5개씩 파일을 나눈다).

## B. 원문 확인(기업 소식)의 규칙
- WebFetch 로 원문을 연다(news.google.com 은 원문 주소로). 안 열리면 WebSearch 로 같은 사건의 다른 기사를 찾는다. 네이버 증권·KIND·DART 본문은 막혀 있다 — 같은 내용을 옮긴 기사를 찾는다.
- 출처의 신뢰도는 **표시하되 문턱은 아니다** (사용자, 10/29): 기업 소식(put_company_events)의 근거는 공식·고객·업계지·언론 원문이 기본이지만, 조사 판정(put_path_research)에는 소문·커뮤니티·채용 공고·전시회 후기 같은 단편 단서도 kind=rumor 로 밝히고 쓴다.
  빼는 것은 문제 있는 데이터뿐 — 자동 생성 시세 요약, 날짜 없는 글, 출처 없는 숫자.
- 확인한 사실은 한국어 1~3문장, 400자 이내: 날짜 + 숫자(금액·%·수량·생산능력·가이던스·부문 매출 비중) + 상대방·기간. 원문에서 읽은 것만. 그 기업 이야기가 아니거나 시세 기사면 importance 1, "관련 없음: 이유".
- 저장: `select ideas.put_company_events($j$[{"event_id":"…","text":"…","importance":2}, …]$j$::jsonb);` — research.json 에 같은 기업의 event_id 가 있으면 그 id 로, 없으면 새 행
  `{"company_id":"company:…","kind":"filing|disclosure|revenue|news","published_at":"YYYY-MM-DD","title":"…","url":"https://…","text":"…","importance":2}` (45일 안의 날짜, https 원문).
  새 행의 event_id 는 함수가 만든다 — 저장 뒤 `select event_id, title from public.v_company_events where company_id = 'company:…' and url in ('…');` 로 받는다.

## C. 병목 상태 관측치 (최대 8개/실행)
읽은 원문이나 leads.json 의 bottlenecks 에서 **병목이 조여지는지 풀리는지를 보여 주는 숫자**를 찾으면 기록한다: 현물가·계약가 배수나 %, 리드타임, 가동률, 재고, 수주잔고, 평균단가, 증설 완공 시점과 규모.
- 지표 id 는 `obs:<병목·부품>_<측정>`; 같은 측정은 같은 id — `select indicator_id, label, unit, as_of, value from public.v_indicators where category='observation' order by indicator_id;` 로 먼저 확인.
- nodes 는 그래프 노드 id(`research/ecosystems/seed_graph.json`). 원문 날짜를 as_of 로, 숫자 하나를 value 로.
- `select ideas.put_observations($j$[{"indicator_id":"obs:…","label":"…","unit":"…","ecosystem":"optics","nodes":["bottleneck:…"],"source":"TrendForce","source_url":"https://…","as_of":"2026-10-19","value":5,"note":"원문 한 줄","meta":{"quote":"원문 발췌"}}]$j$::jsonb);`
- FRED 지표(구리·알루미늄)가 30일 넘게 비어 있으면 `.venv/bin/python -m wsj.ecosystems.indicators fred-sql --out ../.ideas_run/fred.sql` 후 그 파일을 그대로 실행한다.

## D. 2단계 — 리포트(아이디어)와 목표주가의 작성 규칙
- 입력: `.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s2 --hypotheses-from-db ../.ideas_run/s2/queue.json --emit-prompt ../.ideas_run/s2/prompt.json`
  (`--hypotheses-from-db` 가 조사 끝난 후보를 DB 큐에서 읽어 payload.hypotheses 에 넣는다 — id 는 Q1, Q2 …, research_result 에 조사 결론, existing_idea 에 이어 쓸 리포트.)
- `s2/prompt.system.md` 를 끝까지 읽는다 — 작성 규칙(근거 세 층, ★, 노출 순도, 날짜 있는 확인 일정, 채점, 선행 추론, 가치평가, hypotheses, states·leads·prices 사용법). `s2/prompt.payload.json` 을 Read 로 2,000줄씩 끝까지 읽는다.
- `s2/raw.json` 에 `{"model": "claude-opus-5-5", "ideas": [...], "grades": [...]}` 를 쓴다.
  - **새 리포트는 payload.hypotheses 의 후보에서 쓴다** (`"hypothesis": "Q3"`). research_result 가 confirmed·partial 이면 그 event_ids 의 근거 id 로 chain 을 잇고, no_data·unconfirmed 는 "(추론)" 단계로만. flags(경로 끊김·이미 움직임)는 risks·bear 에. existing_idea 가 있으면 그 idea_key 의 update 로.
  - 제목은 30자 안팎의 짧은 한 문장 — 기업명·티커·숫자·괄호·줄표 없이 무엇이 어디로 움직이는지만.
  - 아이디어 = 가설: 구체적(경로·기업·숫자·시점) · 대담(시장이 아직 반영하지 않은 것) · 반증 가능 · 설명력. chain 의 추론 단계는 "(추론)" 으로(사실 단계 1개 이상). watch 는 예측 2~3개 + 반증 조건 1개(direction=weaken), 날짜(due)·기준(metric·threshold)·방향 있음. ★1 은 결함이 아니다.
  - 시장 범위 (ADR-0021): primary 는 미국(NYSE·Nasdaq)·한국(KRX·KOSDAQ) 상장사만. 대만·일본·유럽·중국 기업은 출발점·고객·경쟁·동종으로만. existing 의 scope 가 '범위 밖'이면 종료되니 그 가설의 미국·한국 고리를 new 로.
  - 기존 아이디어는 빠짐없이 update / weaken / keep / close 중 하나. 주 기업 자신의 새 사실이 없으면 '강화'하지 않는다. 노출 순도(exposure)는 부문 매출 근거가 있을 때만.
  - existing 의 watch 중 기한이 지났거나 결과가 나온 항목을 grades 로 채점한다 (hit·miss 는 근거 id 필수). 채점이 ★ 를 움직인다(적중 1 → ★2, 2 → ★3(문턱 충족 시), 반증 성립 → 종료, 빗나감 2 → ★1).
  - prices 의 시총·저점 대비·tenbagger 판정을 본다: 같은 논리에 **시총이 작고 덜 오른 공급사**가 있으면 그쪽을 primary 로. 저점 대비 3배 이상 오른 기업은 risks 에 "이미 알려진 정도".
  - **아이디어마다 anticipation**: trigger · path(그래프 노드 id) · mechanism · lead_quarters · effect{pct_of_revenue, basis, evidence} · priced_in. 하루에 선행 아이디어(priced_in=none·partial) 1건 이상.
  - **아이디어마다 valuation** (p23 일 때): 시나리오 bear·base·bull(확률 합 1) 각각 매출·마진·배수(ps|pe) → 내재 시총, 가정(사실 kind=fact 근거 id 1개+ · 추정 kind=estimate basis), 깨지는 조건, confidence, verdict 3~5문장.
    영향 추정은 LLM 의 판단이다 — 추정은 금지가 아니라 표시다. 재료는 prices[primary] 의 close·currency·shares·fundamentals. close 가 없으면 valuation_skipped 에 이유. 검증기가 산수를 다시 한다.
    **가격·주식수가 있는 아이디어는 valuation 을 생략할 수 없다.** new·update·weaken 행은 이번에 다시 쓴다(리포트를 고쳐 썼으면 목표주가도 다시). keep 은 existing.valuation 이 있으면 생략 가능, 없으면 쓴다. 검증기가 누락을 exit 2 로 막는다.
  - 숫자·날짜는 payload 에 있는 것만. "목표가"·"매수" 같은 말은 쓰지 않는다 — 주가 판단은 valuation 의 시나리오로만.

## E. 검증 (엔진)
`.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s2 --hypotheses ../.ideas_run/s2/queue.json --from-llm-json ../.ideas_run/s2/raw.json --method session --model claude-opus-5-5 --out ../.ideas_run/s2/rows.json --emit-sql ../.ideas_run/s2/sql`
- `rejected:` 줄을 보고 raw.json 을 고쳐 다시 (최대 2번). `valuation rejected:` 는 아이디어는 받되 가치평가만 거부된 것 — 사유대로 고친다. `valuation skipped:` 는 주가가 없어 평가를 안 쓴 것 — 보고에 적는다.
- `verification:` 줄은 예측 채점이 ★·상태를 움직인 기록 — 보고에 그대로.
- **exit 2 (`valuation missing`)**: 가격·주식수가 있는데 목표주가가 없는 아이디어 목록이다. raw.json 의 그 아이디어에 valuation 을 채우고 다시 돌린다. 끝까지 못 채우면 `--allow-missing-valuations` 로 넘기되 보고에 "목표주가 누락 N건: 사유". (verify 작업은 리포트를 쓰지 않으므로 늘 `--allow-missing-valuations`.)
- DB 가 `근거 없는 단계` 로 거부하면 0025 미적용 — 추론 단계를 바로 앞 사실 단계의 claim 끝에 합쳐 다시 만든다.

## F. 저장 (엔진이 만든 SQL 을 그대로)
- `s2/sql/` 의 파일을 이름순으로 Read 해서 그대로 execute_sql 로 실행한다: `01_…`(아이디어) → `zy_valuations.sql`(가치평가; rejected 가 있으면 raw.json 의 그 valuation 을 고쳐 E 부터 다시) → `zz_assessments.sql`(손대지 않은 아이디어의 판단·채점 갱신). SQL 을 손으로 고치지 않는다.
- zy_valuations.sql 뒤 **확인**: `select count(*) from ideas.valuations where as_of = current_date;` 가 rows.valuations.json 의 건수와 같아야 한다. 적으면 E 부터 다시 — 목표주가 없이 리포트만 저장하고 끝내지 않는다.
- `s1/sql/zx_issue_hypotheses.sql`(이슈별 경로)은 paths 작업이 실행한다 (p26 일 때).

## G. 알림 규칙 (작업별 문서가 가리킨다)
- 실패 알림: 0027 미적용, 수집 미완료, DB 쓰기 실패, 큐가 있는데 하나도 처리하지 못했을 때.
- 결과 알림(report): **기대 상승여력 +50% 이상이고 확신 mid 이상이며 시총 $3B 이하인 새 가치평가**(제목·현재 → 기대 주가·여력·확신·verdict 첫 문장), 기존 평가의 기대 상승여력이 ±30%p 넘게 바뀐 아이디어. 첫 문장에 `목표주가 저장 N/M`.
- 결과 알림(verify): 반증 성립으로 종료된 리포트, ★3 의 예측이 빗나갔을 때, 하루 사슬 요약(어느 작업이 skipped·failed 인지).
