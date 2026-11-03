# 아키텍처 (2026-11-02 현행)

옛 구조(브리프·부서 스키마·SEC 소형주 신호, ADR-0001~0013)는 결정 기록으로 남아 있지만 지금 흐름은 아래다. 바뀐 이유는 각 ADR 에.

## 1. 목표
미국 상장 소·중형사(시가총액 $1억~$150억, 한국은 보조)에서 **1년 안팎에 2~3배** 갈 수 있는 기회를 시장보다 먼저 찾는다.
판단은 구조적 추론 · 시장이 고려하지 못한 변수 · 주가로 내린다. 판정·채점·목표주가는 없다 (ADR-0028·0029·0030).
제품은 투자 아이디어 피드 — ★1~5 · 제목 · 아이디어 · 해석 · 근거 (`docs/agents/writing.md`).

## 2. 흐름
```
① 출처        research/sources/registry.json (층: raw·press·newsroom·disclosure) + 그래프 기업 이름 검색 + 공시·월매출 + 가격·재무
② 수집        GitHub Actions 'issues' (18:47 예약 + 04:23 예약 작업이 한 번 더 실행)
              issues → company_feed → clues(피드 + 원본 페이지 변화 감지, 원본 층 전문 출처는 분류기 예외, 남긴 단서는 본문 저장·본문 태깅)
              → candidates(그래프 밖 상장사·사전 밖 식별자 → 그래프 제안) → prices → facts → fundamentals
③ 저장        Supabase  ideas.clues · clue_texts(본문, 비공개) · company_events · supply_chain_issues · tech_* · opportunities · threads
              ops.collector_runs(수집기·예약 작업 실행 기록) · ops.v_input_quality · ops.v_source_use (In 점검) · ops.v_collection_alerts(수집 이상 → 리포트 알림)
④ 판단        Claude 예약 작업 (월~토)
              04:23 collect → 05:17 interpret(판단까지 + 열린 스레드 + 그래프 패치 PR) → 06:19 enrich(검토자 — 약한 고리는 그 자리에서 판다) → 07:37 report(공개·알림)
              시각은 순서일 뿐 마감이 아니다 — 각 작업은 앞 작업이 끝나기를 기다린다 (ADR-0032)
              일요일 10:23 주간 개선 (In 점검, 출처·그래프·도구 개선, 주간 매크로 배경 research/macro/)
⑤ 산출        ideas.opportunities(active) → 웹 https://wsj-investment.vercel.app · 하루 알림
```
- 수집은 코드(Actions, secret 키), 판단은 예약 작업(Supabase MCP + publishable 키 + 저장소 문서)이 맡는다 (ADR-0024·0028).
- 작업 문서는 목적·방향·꼭 지킬 것·연결 방법만 정한다 (ADR-0029): `docs/agents/daily-ideas.md`, `docs/agents/daily/*.md`, `docs/agents/weekly-improvement.md`.
- 판단은 그 자리에서 낸다. `ideas.threads` 는 판단과 근거를 다음 세션이 이어받는 기억이다 (ADR-0030·0032).
- 산업은 정하지 않는다. 분류기는 "기술 변화 → 부품·소재의 새 병목" 메커니즘으로 남기고 `scope`(core·frontier)를 적는다. 그래프 밖 산업의 후보는 `eco:frontier` 에 쌓이고, 뭉치면 주간 개선이 생태계로 승격한다 (ADR-0033).

## 3. 온톨로지
- 원본은 Git: `research/ecosystems/seed_graph.json`(노드·관계·근거), `ontology.json`(닫힌 어휘 v0.5), `node_aliases.json`·`native_names.json`, 패치 `research/ecosystems/patches/`.
- 바꾸는 길: 패치 JSON → PR → CI(`ontology --check`·pytest·web build) → 병합. 웹 사본 `apps/web/src/data/ecosystem-seed.json` 은 `export_web` 이 만든다.
- 쓰는 곳: 기업 소식 수집 범위(그래프 상장사 — 후보 포함), 단서 태깅(노드 codes·별칭·기업 이름, 원본 단서는 본문으로도), 해석의 `recall`(그래프 자리·같이 파는 회사·지난 단서), 가격·재무 대상.
- v0.5(ADR-0031): 규칙·결정 주체 노드, 시간 축(first_seen·first_evidence·maturity_history)·층별 식별자(codes)·후보 상태 노드 칸, 숫자 노출도·양 간선 칸.
- 후보 통로: 수집 단계 `candidates` 가 그래프 밖 상장사(최근 단서 2건 이상, 또는 원본·공시·뉴스룸 1건)와 사전 밖 식별자(기술 노드가 안 걸린 원본 단서의 JESD·802.3xx·NOGRR·CEI-… 꼴)를 `ideas.graph_proposals`(by=collect)에 올린다. 해석이 원문으로 확인해 후보 노드(`status: candidate`)·codes·별칭으로 합치거나 버린다.
- 조회본: 병합될 때마다 `graph-sync` 워크플로가 `core.graph_nodes`·`graph_edges`·`graph_terms` 로 덮어쓴다. 예약 작업은 `core.resolve_terms`·`graph_neighbors`·`suppliers_below`·`node_signals` 로 묻고, 확인한 것은 `ideas.put_graph_proposal` 로 제안한다 — 해석 작업이 패치에 합친다.

## 4. 저장소 레이아웃
| 경로 | 역할 |
|---|---|
| `supabase/migrations/*.sql` | 스키마. 사용자가 SQL 편집기로 적용 |
| `pipeline/wsj/ecosystems/` | 지금 쓰는 수집·도구 — `clues`·`pages`·`candidates`·`exposure`·`company_feed`·`issues`·`prices`·`facts`·`fundamentals`·`graph_sync`·`recall`·`textract`·`ontology`·`export_web` |
| `pipeline/wsj/collectors/`, `briefs/`, `signals/` | 옛 SEC·FINRA 수집기와 브리프 (토요일 `collect.yml`, 판단에는 안 쓴다) |
| `research/sources/` | 출처 목록과 형식 |
| `research/ecosystems/` | 그래프·어휘·패치 |
| `research/macro/` | 주간 매크로 배경 (주간 개선이 쓰고 해석이 읽는다) |
| `research/playbook/` | 렌즈·패턴 카드·사용자 지적 기록 (참고 자료) |
| `docs/agents/` | 예약 작업이 읽는 문서 |
| `apps/web/` | Next.js — 투자 아이디어·단서 화면 |

## 5. 운영
- 워크플로: `issues.yml`(매일), `graph-sync.yml`(그래프 병합 때·매일 05:07), `exposure-facts.yml`(일요일 07:13 — 공시 매출 구성 → `ideas.exposure_facts`), `pipeline-tests.yml`·`web-quality.yml`(CI), `source-probe.yml`·`clues-probe.yml`(출처 점검), `collect.yml`(토요일 옛 수집), `moat.yml`(수동 실행만 — 11/02 예약 끔).
- 시크릿: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `ANTHROPIC_API_KEY`(단서 분류 Haiku·이슈 선별), `OPENALEX_API_KEY`, `DART_API_KEY`(보류). 웹과 예약 작업은 publishable 키 + RLS.
- 장애: 수집기 하나가 실패해도 다음 단계는 돈다. 시도했는데 하나도 못 받은 시장(facts)은 실패로 기록한다. 들어오는 것의 구성은 `ops.v_input_quality`, 이상은 `ops.v_collection_alerts` 로 매일 보고 리포트 알림 둘째 줄에 붙인다.
- 할 일: `docs/BACKLOG.md` 맨 위 '지금 할 일' (노션 'WSJ 개발 백로그'와 같다).
