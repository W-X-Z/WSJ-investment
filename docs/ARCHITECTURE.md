# 아키텍처 (2026-11-02 현행)

옛 구조(브리프·부서 스키마·SEC 소형주 신호, ADR-0001~0013)는 결정 기록으로 남아 있지만 지금 흐름은 아래다. 바뀐 이유는 각 ADR 에.

## 1. 목표
미국 상장 소·중형사(시가총액 $1억~$150억, 한국은 보조)에서 **1년 안팎에 2~3배** 갈 수 있는 기회를 시장보다 먼저 찾는다.
판단은 구조적 추론 · 시장이 고려하지 못한 변수 · 주가로 내린다. 판정·채점·목표주가는 없다 (ADR-0028·0029·0030).
제품은 투자 아이디어 피드 — ★1~5 · 제목 · 아이디어 · 해석 · 근거 (`docs/agents/writing.md`).

## 2. 흐름
```
① 출처        research/sources/registry.json (층: raw·press·newsroom·disclosure) + 그래프 기업 이름 검색 + 공시·월매출 + 가격·재무
② 수집        GitHub Actions 'issues' (18:47 예약 + 05:23 예약 작업이 한 번 더 실행)
              issues → company_feed → clues(피드 + 원본 페이지 변화 감지, 원본 층 전문 출처는 분류기 예외, 남긴 단서는 본문 저장) → prices → facts → fundamentals
③ 저장        Supabase  ideas.clues · clue_texts(본문, 비공개) · company_events · supply_chain_issues · tech_* · opportunities · threads
              ops.collector_runs(수집기·예약 작업 실행 기록) · ops.v_input_quality · ops.v_source_use (In 점검)
④ 판단        Claude 예약 작업 (월~토)
              05:23 collect → 06:17 interpret(해석 + 열린 스레드 이어 조사 + 그래프 패치 PR) → 06:49 enrich(검토자) → 07:37 report(공개·알림)
              일요일 10:23 주간 개선 (In 점검, 출처·그래프·도구 개선)
⑤ 산출        ideas.opportunities(active) → 웹 https://wsj-investment.vercel.app · 하루 알림
```
- 수집은 코드(Actions, secret 키), 판단은 예약 작업(Supabase MCP + publishable 키 + 저장소 문서)이 맡는다 (ADR-0024·0028).
- 작업 문서는 목적·방향·꼭 지킬 것·연결 방법만 정한다 (ADR-0029): `docs/agents/daily-ideas.md`, `docs/agents/daily/*.md`, `docs/agents/weekly-improvement.md`.
- 하루에 끝나지 않는 조사는 `ideas.threads` 로 이어받는다 — 해석이 남는 시간에 이어서 판다 (ADR-0030).

## 3. 온톨로지
- 원본은 Git: `research/ecosystems/seed_graph.json`(노드·관계·근거), `ontology.json`(닫힌 어휘 v0.4), `node_aliases.json`·`native_names.json`, 패치 `research/ecosystems/patches/`.
- 바꾸는 길: 패치 JSON → PR → CI(`ontology --check`·pytest·web build) → 병합. 웹 사본 `apps/web/src/data/ecosystem-seed.json` 은 `export_web` 이 만든다.
- 쓰는 곳: 기업 소식 수집 범위(그래프 상장사), 단서 태깅(노드·기업), 해석의 `recall`(그래프 자리·같이 파는 회사·지난 단서), 가격·재무 대상.
- 다음(백로그 G-1~G-8): v0.5 스키마(시간 축·층별 코드·규칙·결정 주체·숫자 노출도·후보 상태), Supabase 조회본과 조회 함수, 제안 테이블.

## 4. 저장소 레이아웃
| 경로 | 역할 |
|---|---|
| `supabase/migrations/*.sql` | 스키마. 사용자가 SQL 편집기로 적용 |
| `pipeline/wsj/ecosystems/` | 지금 쓰는 수집·도구 — `clues`·`company_feed`·`issues`·`prices`·`facts`·`fundamentals`·`recall`·`textract`·`ontology`·`export_web` |
| `pipeline/wsj/collectors/`, `briefs/`, `signals/` | 옛 SEC·FINRA 수집기와 브리프 (토요일 `collect.yml`, 판단에는 안 쓴다) |
| `research/sources/` | 출처 목록과 형식 |
| `research/ecosystems/` | 그래프·어휘·패치 |
| `research/playbook/` | 렌즈·패턴 카드·사용자 지적 기록 (참고 자료) |
| `docs/agents/` | 예약 작업이 읽는 문서 |
| `apps/web/` | Next.js — 투자 아이디어·단서 화면 |

## 5. 운영
- 워크플로: `issues.yml`(매일), `pipeline-tests.yml`·`web-quality.yml`(CI), `source-probe.yml`·`clues-probe.yml`(출처 점검), `collect.yml`(토요일 옛 수집), `moat.yml`(화요일).
- 시크릿: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `ANTHROPIC_API_KEY`(단서 분류 Haiku·이슈 선별), `OPENALEX_API_KEY`, `DART_API_KEY`(보류). 웹과 예약 작업은 publishable 키 + RLS.
- 장애: 수집기 하나가 실패해도 다음 단계는 돈다. 시도했는데 하나도 못 받은 시장(facts)은 실패로 기록한다. 들어오는 것의 구성은 `ops.v_input_quality` 로 매일 본다.
- 할 일: `docs/BACKLOG.md` 맨 위 '지금 할 일' (노션 'WSJ 개발 백로그'와 같다).
