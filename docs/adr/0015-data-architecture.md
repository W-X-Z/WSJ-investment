# ADR-0015: 데이터 아키텍처 — 목적에서 출발한 마스터·연결·읽기 모델

- 상태: accepted
- 날짜: 2026-10-27
- 관련: [ADR-0012](0012-ontology-v03-closed-vocabulary.md) (온톨로지 어휘), [ADR-0013](0013-discovery-and-moat-cards.md) (유니버스·해자 카드), [ADR-0014](0014-supply-chain-issue-feed.md) (이슈·지표). 0011~0013 마이그레이션 설계안(미적용)을 대체.

## 1. 목적과 의도 (설계의 기준)

**찾는 것.** 성장 공급망 3개(HBM4·첨단 패키징 / 800G·1.6T 광통신 / AI 데이터센터 800VDC 전력·냉각)의 **소재·부품·공정·테스트·IP 층**에서 병목을 쥐었거나 쥘 수 있는 **소형 상장사**(텐배거 후보). 대형사는 수요·경쟁 맥락으로만 다룬다.

**방법.** 기술 온톨로지(세대·요구 → 병목 → 해결 기술 → 공정·부품·소재 → 기업)를 뼈대로 두고, 공시·뉴스·정책·가격·실적·논문을 매일 붙여 **"무엇이 바뀌었고, 어느 병목에, 어느 소형사에 닿는가, 근거는 무엇인가"** 를 판정한다. AI 는 수집·태깅·선별·요약(이슈 중요도 1~10 + 근거)과 기업별 해자 카드(점수 + 반증)를 맡고, **투자 판단은 사람**이 한다.

**하지 않는 것.** 자동매매·백테스트·모의투자, 주가 전망. 사실과 출처 중심.

**데이터가 답해야 하는 질문 (모든 테이블·뷰는 이 경로를 위해 존재한다)**

| # | 질문 | 경로 |
|---|---|---|
| Q1 | 이번 주 세 공급망에서 무엇이 바뀌었나 | 이슈(중요도·생태계·시점) |
| Q2 | 그 변화는 어느 병목·노드에 닿나 | 이슈 → 노드 |
| Q3 | 그 노드에 노출된 소형사는 누구이고 근거 등급은 | 노드 → 관계 → 기업(크기·근거 등급) |
| Q4 | 그 기업의 해자·재무·최근 신호는 | 기업 → 해자 카드·공시·내부자·지표·이슈 |
| Q5 | 병목 상태는 시간에 따라 어떻게 변하나 | 노드 → 이슈·지표 시계열 |
| Q6 | 내 가설(반증 조건)은 맞았나 | 해자 카드 → 예측 → 채점 |

## 2. 원칙

1. **원본은 하나.**
   - 기업 = `core.entities` (그래프 기업 노드와 같은 id `company:xxx`. SEC 필러는 `core.companies` 와 `cik` 로 1:1, 한국·대만·유럽·비상장도 포함).
   - 기술 온톨로지 = git 의 `research/ecosystems/seed_graph.json` 이 원본(변경을 커밋으로 검토·되돌림) → `core.ontology_nodes` · `core.ontology_edges` 로 **단방향 동기화** (`wsj.ecosystems.sync_db`, 그래프 변경 push 와 매일 이슈 실행 직전).
   - 그래프에서 빠진 노드는 지우지 않고 `active=false` — 과거 이슈·카드의 참조가 깨지지 않는다.
2. **사실 테이블은 마스터 id 로만 참조하고, 무결성은 DB 가 지킨다.** 이슈·지표·해자 카드는 기존 배열 컬럼(`nodes`, `companies`, `ontology_nodes`)을 쓰기 인터페이스로 유지하고, 트리거가 연결 테이블(`issue_nodes`, `issue_entities`, `indicator_nodes`, `indicator_entities`, `brief_nodes`)을 FK 와 함께 유지한다 → 존재하지 않는 노드·기업을 쓰면 저장이 실패한다. 파이프라인·프론트 코드 변경을 최소화하면서 정규화의 이점(역방향 조회 Q3·Q5, 무결성)을 얻는다.
3. **프론트는 `public.v_*` 뷰(읽기 모델)만 읽는다 = 계약.** 테이블 구조를 바꿔도 뷰의 열 이름·타입·순서를 지키면 화면 영향은 0 이다. 새 화면이 필요하면 새 뷰를 만든다 (`v_entities`, `v_node_activity`). 열 추가는 끝에만.
4. **사람(또는 세션 큐레이션)의 판단은 자동 실행이 덮어쓰지 않는다.** `supply_chain_issues.locked` + `issue_revisions` (내용이 바뀔 때마다 이전 행 스냅숏). 잠긴 이슈는 출처·최종 확인 시각만 갱신된다. 같은 사건의 중복은 `status='merged'` + `merged_into`.
5. **목적에 없는 데이터는 모으지 않는다.** 피벗 전 SIC 버킷(바이오·의료기기·AI 소프트웨어·에너지·반도체 일반·정부조달)은 유니버스에서 내리고 임상·FDA 수집기를 끈다(기존 원자료는 보존). SEC 공시·Form 4·FINRA 는 공급망 유니버스로 범위를 좁혀 유지. **정부 조달은 공급망 기업의 연방 R&D·SBIR·CHIPS·DOE 수주로 재조준** — 매출 전 소형사(Aeluma·POET·Lightwave Logic 등)에는 비희석 자금원이자 기술 검증 신호다. 방산 통합업체 위주였던 기존 2,021건(테마 관련 6건)은 목적과 무관.
6. **실행 기록은 한 곳.** 수집기뿐 아니라 동기화·이슈·지표 파이프라인도 `ops.collector_runs` 에 남긴다.

## 3. 구조

```
git seed_graph.json ──sync──▶ core.ontology_nodes ◀── ontology_edges
                                   │  (company 노드)
core.companies (SEC, cik) ◀─cik─ core.entities ◀── indicators.TW_ENTITIES 등 그래프 밖 기업
                                   ▲        ▲
ideas.supply_chain_issues ─▶ issue_entities / issue_nodes (트리거 유지, FK)
ideas.indicators          ─▶ indicator_entities / indicator_nodes
ideas.briefs (moat)       ─▶ brief_nodes        (기업은 cik → entities.cik)
ideas.issue_revisions (이력), core.signals·raw.* (SEC·FINRA·연방 수주, cik 기준)
                 └──────────▶ public.v_* (읽기 모델 = 프론트 계약)
```

## 4. 결과와 비용

- 기존 화면은 그대로 동작해야 한다 (뷰 모양 유지). 검증: 배포 후 홈·피드·지표·해자 카드 화면 확인.
- 그래프 노드 이름(id)을 바꾸려면 새 id 추가 → 참조 이전 → 옛 id 비활성 순서가 필요하다 (FK 가 깨진 참조를 막는다).
- 웹의 캔버스는 여전히 정적 JSON(`ecosystem-seed.json`)을 번들한다 — 같은 git 원본이라 불일치는 없다. 노드 패널에 최근 이슈·지표를 붙일 때는 `v_node_activity` 를 읽는다.
- 마이그레이션 기록: 0011~0013 설계안은 `supabase/migrations/_unapplied/` 로 옮긴다. 0014 는 적용됐지만 기록이 없었다 → 0017 에서 기록을 보정한다.
