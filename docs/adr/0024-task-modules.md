# ADR-0024: 아침 작업의 분업 — 한 세션 대신 DB 큐로 이어지는 다섯 예약작업

상태: accepted (2026-10-29). ADR-0016 개정 2(아침 한 세션이 수집 확인부터 저장까지)·0022·0023 을 실행 구조에서 고친다.

## 문제
- 06:41 예약작업 하나가 수집 확인 → 가설 후보 → 조사 → 리포트 → 목표주가 → 채점 → 저장 → 보고를 42분짜리 한 세션에서 했다.
  세션 끝자락(저장·목표주가)이 가장 품질이 낮았고, 예약작업 프롬프트가 문서보다 먼저 늙어 **목표주가를 쓰지 말라는 옛 경계**를 그대로 들고 있었다(10/29, 새 리포트 4건이 목표주가 없이 저장됨).
- 사용자: "정량 로직으로 애초에 커버가 불가능한 영역일 수 있어 — 작업을 모듈화해서 여러 번의 예약작업으로 분업화가 필요하지 않을까".
  판단(이슈가 어느 경로로 어느 기업 숫자를 바꾸나, 얼마짜리 회사인가)은 LLM 이 한다. 엔진이 할 일은 그 판단을 **구조화된 형식**으로 받아 거르고·줄 세우고·채점하고, 단계 사이를 **DB 로 잇는** 것이다.

## 결정
1. **다섯 작업** (월~토, KST). 각 작업은 자기 큐 뷰에 있는 것만 처리하고, 끝나면 확인 쿼리로 자기 결과를 검사하고, `ops.put_agent_run` 으로 실행 기록을 남긴다.

   | 시각 | 작업 | 큐 (입력) | 출력 | 완료 조건 |
   |---|---|---|---|---|
   | 05:30 | collect | Actions `issues` 워크플로 | 이슈·공시·가격·재무·환율 | 오늘 issues·company_feed succeeded |
   | 06:20 | paths | `v_q_issues_needing_paths` (중요도 6+, 5일 안, 경로 없음) | `ideas.issue_hypotheses` (이슈당 ≤3, 선택 표시) | 큐 0 |
   | 06:50 | research | `v_q_paths_needing_research` (선택된 기업 경로, 7일 안, 조사 없음) | 기업 소식·관측치·`ideas.path_research`(verdict) | 처리한 경로마다 조사 행 |
   | 07:30 | report | `v_q_candidates_needing_report` (조사 끝난 경로) + `v_q_ideas_needing_valuation` | 리포트 + **목표주가 (한 몸)** | 두 큐 0, 오늘 valuations ≥ 바뀐 리포트 수 |
   | 08:05 | verify | `v_q_predictions_due` (기한 지난 예측) | 채점 → ★·종료, 하루 보고 | 큐 0 |

   주 1회 시스템 개선(일요일)은 그대로. ★2 이상 리포트의 심층 리서치(deep-dive)는 토요일 작업으로 뺀다 — 이 PR 에서는 만들지 않고 다음에.
2. **인계는 DB 로만** (0027). 세션 사이에 파일은 남지 않는다. 경로(`issue_hypotheses.paths`)에 `trigger`·`change` 를 함께 저장해 다음 날 리포트 작업이
   `--hypotheses-from-db` 로 2단계 후보를 되살린다(`hypotheses.from_queue`: 이슈마다 H1 부터 세는 id 는 Q1, Q2 … 로 다시 매기고 `source` 에 출처를 둔다).
   조사 결과는 `ideas.path_research`(verdict confirmed|partial|unconfirmed|no_data|refuted, summary, sources, event_ids)에 쓰고, 리포트 작업은 그것을 `research_result` 로 받는다.
3. **실패는 고립된다.** 앞 작업이 실패하면 다음 작업의 큐가 비어 `skipped` 로 끝난다. 다시 돌리면 같은 날 같은 작업의 기록을 덮어쓴다(멱등). 시스템 점검 화면이 `v_agent_runs` 로 오늘의 사슬을 보여 준다.
4. **문서가 기준, 프롬프트는 포인터.** 예약작업 프롬프트는 "그 작업의 문서를 읽고 따른다 + 쓰기 함수 목록" 만 담는다. 절차·규칙은 `docs/agents/daily/<task>.md` 에,
   형식·엔진 규칙은 `docs/agents/daily-ideas.md`(공통 규칙)에 둔다. 두 곳이 어긋나면 문서가 이긴다. 쓰기 함수는 작업마다 다르다:
   collect 없음 · paths `put_issue_hypotheses` · research `put_company_events`·`put_observations`·`put_path_research` · report `put_ideas`·`put_valuations`·`put_assessments` · verify `put_company_events`·`put_ideas`·`put_assessments`. 모두 `ops.put_agent_run`.
5. **정량 계산은 하지 않는다.** 온톨로지에 매출 비중·수량 변수를 넣어 영향을 계산하는 설계는 보류한다(소형주일수록 공시가 없어 입력이 안 생긴다).
   대신 LLM 의 판단은 형식이 있다: 경로(노드 사슬) · 방향 · effect_pct · lead_quarters · why_unpriced · falsifier · 날짜 있는 예측 · 시나리오별 내재 주가와 확률. 엔진은 그 형식으로 거르고 채점한다.

## 결과
- 0027: `ideas.path_research` + `put_path_research`, `ops.put_agent_run` + `v_agent_runs`, 큐 뷰 5개.
- 엔진: `by_issue` 가 trigger·change 를 저장, `hypotheses.from_queue`, `--hypotheses-from-db`, 페이로드 이슈 신호에 `issue_key`.
- 문서: `docs/agents/daily/{collect,paths,research,report,verify}.md`, `daily-ideas.md` 는 공통 규칙으로.
- 예약작업: 06:41 하나 → 05:30·06:20·06:50·07:30·08:05 다섯 (0027 적용 뒤 전환; 그 전엔 06:41 이 옛 절차로 돈다).
- 비용: 세션 수는 늘지만 세션마다 컨텍스트가 비어 있는 상태에서 시작한다. 구독 사용량 한도에 닿으면 수집+경로 / 조사 / 리포트+검증 3회로 묶는다.
