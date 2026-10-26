# ADR-0012: 온톨로지 v0.3 — 닫힌 어휘, 수요 측 노드, 방향·근거 가중 영향 전파

- 상태: accepted
- 날짜: 2026-10-27
- 관련: [ADR-0010](0010-technology-ecosystem-knowledge-graph.md) (설계안, proposed), [ADR-0011](0011-historical-evidence-linkage.md). 0010 의 노드/관계 어휘를 **실제로 강제**하는 구현이며, 0010 의 "18 종 노드" 중 claim/evidence/event/hypothesis 는 그래프 노드가 아니라 별도 배열(events/watches)·테이블로 둔다.

## 맥락

피벗(2026-10-26): 3개 공급망(HBM4·첨단 패키징 / 800G·1.6T 광통신 / AI DC 800VDC 전력·냉각)의 기술·산업 온톨로지를 만들고, 새 이슈가 어디에 영향을 주는지 AI 로 분석해 투자 아이디어를 검증한다.

PR #3·#8 로 들어온 seed_graph v0.2(90 노드/105 관계)를 뜯어본 결과:

1. **"이슈 → 영향 기업" 을 답할 수 없는 구조.** 기업 노드 8개가 전부 차수 1(`offered_by` 하나), 수요 측(고객·제품 세대·표준) 노드가 0개, 생태계 간 교차 관계 0개. 영향 전파는 무방향 BFS 라 상류/하류·부정 극성을 구분하지 못했다.
2. **어휘가 열려 있었다.** 노드 kind 8종(ADR-0010 과 불일치), 관계 7종 중 `requires_component_or_material`·`uses_component_or_equipment` 는 정의역/치역 없이 쓰여 `requirement→requirement`, `bottleneck→bottleneck`, `process→process` 같은 의미 불명 관계가 섞였다. 근거 단계(stage)는 10개 임의 문자열.
3. **제품과 기술이 섞였다.** `tech:hawk`(Camtek 제품), `tech:lite_eml`(Lumentum 제품)이 하이브리드 본딩·CPO 같은 일반 기술과 같은 kind.
4. **근거가 얇다.** 105 관계의 출처 URL 이 13개, SK hynix 기술 노트 하나가 21 관계를 떠받침. 39 관계는 `technical_inference` 인데 evidence 필드에 같은 공식 URL 을 넣어 "출처 있음" 처럼 보였다.
5. 기업 노드에 CIK·상장 여부·유니버스 포함 여부가 없어 `core.companies` 와 이어지지 않았다.

## 결정

### 1. 닫힌 어휘 `research/ecosystems/ontology.json` + 검증기 `wsj.ecosystems.ontology`

| 항목 | 값 |
|---|---|
| 노드 kind (12) | ecosystem, **product_generation, standard**, requirement, bottleneck, technology, process, component, material, equipment, **product**, company |
| 관계 (16, 정의역→치역 강제) | drives_requirement, specified_by, succeeds, creates_bottleneck, mitigated_by, requires, implements, offered_by, **supplied_to, qualifying_with, adopts, defers**, substitutes_for, **displaces, competes_with, invests_in** |
| 근거 등급 (8, 사전확률) | independent_measurement .95 · standard_body .9 · official_issuer .8 · customer_statement .8 · third_party_report .6 · vendor_claim .55 · technical_inference .4 · hypothesis .25 |
| 극성 | positive / negative / conditional (conditional 은 신뢰도 ×0.8) |
| 기업 필수 필드 | role(supplier/customer/both), listing{ticker, exchange, cik, filer_type}, in_universe, size_band |

- `supplied_to` 는 official_issuer 이상 근거만 허용 (`min_tier`). `offered_by` = 판매 보유, `qualifying_with` = 인증·협업, `supplied_to` = 확인된 거래 — 세 단계를 섞지 않는다.
- 기업↔기업 관계에는 `about`(어느 기술/세대에 관한 관계인지)을 붙인다. 영향 전파는 `about` 노드를 지난 경로에서만 그 관계를 탄다 — CPO 이벤트가 NVIDIA 를 거쳐 800VDC 파트너(Navitas)로 새는 것을 막는다.
- 린트: 한 URL 이 12개 넘는 관계를 떠받치면 경고, 생태계마다 customer 역할 기업 필수, product 는 implements + offered_by 둘 다 필수, 추론·가설로만 연결된 기업 경고. `python -m wsj.ecosystems.ontology --check` 는 CI 에서 돈다.

### 2. v0.2 → v0.3 마이그레이션 (`wsj.ecosystems.migrate_v03`, 멱등)

- 제품 8개 분리: `tech:hawk → product:camt_hawk --implements--> process:microbump_metrology --offered_by--> company:camt`. POET·Lessengers 는 일반 기술(`tech:optical_interposer`, `tech:dow`)과 제품을 나눴다.
- `requires_component_or_material`/`uses_component_or_equipment` → `requires`; `bottleneck requires X` → `mitigated_by`; 정의역 밖 관계 2개 삭제(제품 implements 로 대체).
- stage → evidence_tier 매핑(`legacy_stage_to_tier`), 55개 노드에 생태계 부여(BFS), 기업 8개에 CIK·상장 정보.

### 3. 추가한 내용 (121 노드 / 153 관계 / 이벤트 12 / 감시 13) — 전부 2025~2026 출처

- **세대·표준**: HBM3E→HBM4→HBM4E→HBM5, JESD270-4(2025-04); 800G→1.6T, IEEE P802.3dj; 54VDC→800VDC, OCP LVDC v1.1.
- **수요 측**: SK hynix·Samsung·Micron(HBM4 공급사, NVIDIA 인증 진행), NVIDIA(세 생태계 공통 수요처, `also_in`).
- **핵심 부정 근거**: Hot Chips 2026 SK hynix — HBM4·HBM4E 는 microbump 유지, 하이브리드 본딩은 HBM5 (`company:skhynix --defers--> tech:hybrid_bond`, negative). 하이브리드 본딩 장비(BESI·AMAT) 논제를 약화시키고 범프 검사(Camtek·Onto) 수명을 늘리는 사건 — 이런 것이 "새 이슈 → 영향" 의 전형이다.
- **공급사·경쟁**: BESI(하이브리드 본더), AMAT→BESI 9% 지분(SEC 8-K), KLA(검사 경쟁), Credo AEC(단거리에서 pluggable 대체, 조건부), NVIDIA CPO 파트너(Coherent·Lumentum·Fabrinet, customer_statement), NVIDIA 800VDC 파트너 18사 중 SEC 필러(Navitas·onsemi·MPS·TI·Eaton·Vertiv) + Navitas 자체 공시.

### 4. 영향 전파 `wsj.ecosystems.impact` 재작성

- 방향: 술어별 `direction`(demand_to_supply / supply_to_demand / none). implements·supplied_to·qualifying_with 는 거꾸로 타고 제품·공급사에 닿고, adopts/defers 는 거꾸로 타서 채택 고객에 닿는다. competes_with·succeeds 는 경로가 아니다.
- 가중: 경로 신뢰도 = Π confidence, 부정 극성을 지나면 부호 반전. 기업별 집계(best path, net sign, 가장 약한 고리, 승격에 필요한 근거).
- 고객 기업에서는 `about` 이 경로에 있는 supplied_to/qualifying_with 만 거꾸로 타고 공급사까지 한 번 더 간다.
- 결과 예: `tech:hybrid_bond` 변화 → BESI (+, 0.64, 문서화) / SK hynix (−, 0.60, 채택 연기) / 대체: TCB, 잠식: microbump. `gen:800vdc` → NVIDIA(채택) → Navitas·onsemi·MPS·TI·Eaton·Vertiv (고객 경유 공급사, 0.64) / 부스바 구리 수요 역효과(−).
- 웹은 `impact-index.json`(기업 아닌 모든 노드의 사전 계산 결과)을 노드 패널에 보여 준다 (`wsj.ecosystems.export_web`).

## 결과와 한계

- 그래프가 이제 "세대 전환 → 요구 → 병목 → 기술 → 제품 → 공급사" 와 "고객 채택/연기" 를 한 구조에서 읽는다. 생태계 간 교차는 NVIDIA 한 노드뿐 — 하이퍼스케일러·TSMC(CoWoS)·OSAT 는 다음 추가 대상.
- **유니버스 불일치**: 공급사 전부 `in_universe=false`. 현재 유니버스 SIC 버킷(바이오·의료기기·정부조달·에너지·AI SW·반도체 3674 등)에 반도체 장비(3559/3825 는 있으나 Camtek 은 20-F, Onto 는 공개유동 $4.8B 초과)·광부품·전력부품이 거의 없다. 피벗 후 유니버스 정의를 "3개 공급망 노드에 연결된 기업" 으로 바꾸는 것이 ADR-0013 후보.
- 소형주 관점: 세 공급망의 상장 공급사 대부분이 대형주(Vertiv·Coherent·Lumentum·KLA·TI). 소형(공개유동 <$2B)은 AEHR·POET·NVTS·VICR·AAOI 정도. "텐배거" 는 공급망 노드 중 **독점적 병목을 쥔 소형사**에서만 나오므로, 다음 작업은 각 병목마다 "소형 전문 공급사가 있는가" 를 묻는 것이다.
- 근거 집중(SK hynix 노트 21, POET 보도자료 16, OCP 14)은 린트 경고로 남겨 두었다. 해소는 관계별 원문 발췌(excerpt) 추가로.
