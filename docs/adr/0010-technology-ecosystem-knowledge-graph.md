# ADR-0010 (proposal): 기술 생태계 온톨로지 · 증거 그래프 · 트리거 모니터링

- 상태: proposed / **운영 반영 전**
- 작성: 2026-10-26
- 기존: [ADR-0008 브리프](0008-product-is-the-brief.md)와 [ADR-0003 수집기](0003-collector-architecture.md)를 보완. 기존 Data Desk/Analyst/Risk와 현재 core.signals는 유지.

## 1. 문제 정의
기업 단위 SEC/FDA/계약 시그널만 취합하면 차세대 제품/공정의 **물리 병목**이 소재·부품·계측·장비·에너지 공급기업에 전달되는 구조를 놓치기 쉽다. 선행 기술 문서/표준/논문/특허/사양서에서 먼저 병목 변화를 탐지하고, 상장기업의 경제적 노출을 단계적으로 검증해야 한다.

## 2. 시스템 구성과 역할
- **위키 문서:** 인간이 읽는 기술 맥락, 로드맵·대안·핵심 실험값·중요한 불확실성. 원본은 Git Markdown, Vercel은 렌더링.
- **온톨로지:** 개념과 의미적 제약. Node: `ecosystem, product_generation, requirement, bottleneck, material, component, process, equipment, technology, standard, experiment, facility, company, customer, claim, evidence, event, hypothesis`. Edge: `drives_requirement, creates_bottleneck, mitigated_by, depends_on, substitutes_for, offered_by, qualified_by, supplied_to, validated_by, owned_by`. 공급관계와 기술 상관관계는 다른 타입으로 취급.
- **근거 그래프:** 주장과 관계를 연결한 출처 URL, 발췌 위치, 수치/단위, 초록/본문 여부, 검증 상태.
- **변화 로그:** 각 소스에서 검출된 사건과 이전 스냅샷의 Delta.
- **트리거:** 어떤 변화가 생기면 어느 가설·기술·상장기업 영향 경로를 재평가해야 하는지 정의.
- **User-facing:** 생태계 맵 + 선택 노드의 연결 근거 + 관측 타임라인 + 감시 룰 + 후보 기업별 투자 가설 + 반론.

## 3. 저장소 결정
**1단계:** 현행 Supabase PostgreSQL을 source-of-truth로 확장하는 adjacency graph model 권고. graph DB와 문서 위키의 양자택일이 아니다.
- `core.tech_nodes`: id, type, canonical_name, aliases, properties_jsonb, status, last_verified_at
- `core.tech_edges`: id, from_id, to_id, predicate, polarity, relationship_state, effective_from/to, asserted_at, observed_at, promoted_at, confidence_band, supersedes_id
- `raw.research_sources`: id, source_group, URL, content_hash, archive_url, published_at, first_seen_at, fetched_at, license/robots, raw_hash, original_raw_pointer
- `core.tech_claims`: id, subject, predicate, object_or_value, unit, condition, evidence_id, page/paragraph, quality, published_at, verified_at, interpretation_vs_fact
- `core.tech_metrics`: subject, measured_name, value, unit, test_condition, period_start/end, original_publication, source_id
- `core.tech_events`: event id, type, target_id, published_at, first_seen_at, valid_at, observed_at, value_delta, novelty, source_group, dedupe_sha256
- `ideas.tech_hypotheses`: id, thesis, economic_mechanism, beneficiary_candidates, competitors, falsifiers, next_milestone, states, version
- `ops.tech_watch_specs/runs/alerts`: 룰 + 버전, watermarks, evaluation status, human ack, resolved_by_event
- `core.tech_company_exposures`: technology_id, cik, product_id, supply_role, customer_relationship_evidence_id, revenue_exposure_if_disclosed, confidence

**중요:** 위 스키마는 설계안일 뿐, 이 PR에서 Supabase DB에 DDL을 실행하지 않는다. 구현 시 core/raw/ops/ideas의 기존 스키마 권한과 통일한다.
**안전:** 연구 원문/사내 추론을 익명 공개 SELECT 정책으로 노출하지 않는다. 현재 앱의 일반 공개 anon 정책을 그대로 복제하지 말고 사용자 인증·RLS를 명확히 설계한다.

### bitemporal + evidence discipline
- `valid_at`: 어떤 사건/성능이 실제 발생한 시점
- `published_at`: 출처가 외부 공개한 일시
- `first_seen_at`: 소스 모니터가 **처음 실측**한 일시(현대 API의 역사적 record date로 대체 불가)
- `observed_at`: 우리의 수집/보관일시
- `ingested_at`, `verified_at`: 해석·인간 승인 일시
- 임의로 불확실한 날짜를 day precision으로 채우지 않는다. 월 precision은 보수적으로 월말 공개로 간주.
- 사후 변경된 원문을 불변의 과거 공시로 취급하면 lookahead bias가 발생함. 당시 snapshot/hash가 없으면 historical uncertainty를 기록한다.

### 신뢰도 분리
- `fact/documented_vendor_claim/independent_measurement/technical_inference/market_hypothesis` 구분.
- **신뢰도는 출처 개수가 아니라 이해관계와 검증 방법 기반.** 회사 IR 10개를 10개 독립 증거로 세지 않는다.
- `offered_by`는 공급 가능한 기술/제품 보유. `supplied_to`는 특정 고객의 확인된 거래. `qualifies_for`와 `paid_shipment`는 서로 다른 단계.
- 실제 양산/반복매출이 미확인인 `offered_by`만으로 `beneficiary`를 확정하지 않는다.
- 부정·대체관계도 기록한다. CPO와 pluggable의 공존, HBM 세대별 TCB/Hybrid 대응, native 800VDC vs sidecar 등.

## 4. 트리거 처리 상태 머신

`collect -> normalized_delta -> candidate_event -> contextualized_hypothesis -> corroborated_event -> impact_paths -> user_review -> tracking / invalidated / resolved`

세부:
1. **cheap watch**: 표준 버전, 수치/단위, 공식 공시 날짜, 신규 프로젝트/제품 모델 등 exact diff를 우선. 단순 페이지 레이아웃 변경은 제외.
2. **entity + metric extraction**: 필요할 때만 저비용 LLM이 문서의 수치·맥락·claim을 추출하되 citation span을 강제.
3. **claim verification**: 수치 단위, 비교군, 기준일·원본 링크 확인. 성능이 14Mbps라도 user/위성 수/지역/환경이 달라 직접 비교하지 않음.
4. **impact traversal**: `requirement -> bottleneck -> solution process -> supplier` 경로를 탐색. "상장기업 관련 가능"과 "직접 납품"을 구분한다.
5. **red-team / falsification**: 기존 대체 기술·반증자료 및 역효과(구형 공정/소재 수요 감소) 탐색.
6. **alert gate**: 기술적으로 실질적 Delta, 첫 독립 확인, 새 고객사의 검증, 설계 채택, 양산 시점의 개선 등으로 제한. 명백한 PR 재배포·키워드 중복·낙관적 수식은 알림 제외.
7. **event lifecycle**: `detected, triaged, corroborated, under_review, promoted, retracted, dismissed`; 투자 가설 `proposed, monitoring, strengthened, weakened, invalidated, realized`와 별도.
8. **follow-up watch**: 중요한 이벤트마다 추적할 KPI/예상 발표 범위/실패 기준과 **다음 데이터 확인일** 생성.

중요: 이 PR의 `watches`는 감시 정의와 수동 재현 도구이며 자동 크롤링, 지속 실행, 알림 전송 기능은 없다. 운영 스케줄은 정책·저장소·호출 제한 확인 후 별도 PR로 제공한다.

## 5. 도메인 전문 스킬
공통 프레임만으로 깊은 분석 불가. Ecosystem마다 `/research/ecosystems/<name>/wiki.md`에:
1. 전체 제품 아키텍처/BOM과 기술 로드맵
2. 부품, 소재, 공정, 계측, 에너지 계층별 주요 물리량/단위·시험 조건
3. 병목 후보, 병목을 해결하는 기술, 상호 대체/보완 경로
4. 자료의 독립성 기준·우선 수집처·비공개 지표·정보 지연
5. 공급업체와 CIK/브랜드/자회사 연결
6. 유효한 트리거(실측) vs 마케팅 발표(보류)
7. 반례 및 최소 1개 경쟁 기술
8. 다음 실험, 기술 경제성(ASP x unit content x adoption x yield / gross margin), **주가 입력 없이** 설명

## 6. 예시 3개 생태계와 상호 영향
- HBM4 고적층: 요구 I/O 확대 → 변형/접합 정밀도/미세 결함 → Hybrid bond/검사/계측 → Camtek Hawk 등. **HBM4 전체가 즉시 hybrid bond 채택이라고 쓰지 않는다.**
- 광통신 1.6T: IEEE P802.3dj의 1.6T/200G/lane 목표 → 광 결합/전력밀도 → optical interposer/DOW 등 → POET/Lessengers. 공동개발 ≠ 양산 검증.
- AI 랙 전력 800VDC: LVDC 아키텍처 고도화 → 변환·보호·버스바 → 800V sidecar/직접 MVAC 및 SiC 채택 가능성. **표준화가 특정 SiC 업체 주문을 보증하지 않는다**.
- **공급망 간 공통 하위 노드:** 광통신·전력·HBM 전부 신뢰성/열관리·고밀도 패키징 역량을 필요로 하지만 기술별 시험 조건은 다르다. '공통 단어'만으로 수혜를 합치지 않는다.

## 7. 단계와 수용 기준
| 단계 | 범위 | 수용 기준 |
|---|---|---|
| P0 본 PR | 스키마 초안, 3 생태계 지식 seed, 감시 룰 9개, 순수 분석 CLI | 관계 타입/출처 검증, 불확실성 표시, 과거 시점 오염 방지 단위 테스트 통과 |
| P1 | 기술 노드 20~40개/생태계, 원문·표준·수치 추출, 사실/가설 승인 UX | 핵심 관계마다 원문 근거; 독립 출처 구분; 2-hop 이상 경로가 사람에게 설명 가능 |
| P2 | 공식 자료 수집·snapshot diff·명시적 트리거 평가, DB 이력/재실행 | 동일 이벤트 중복 알림 0, 날짜/수치 비교 테스트 통과, 소스 실패/빈 결과 구분 |
| P3 | 규칙 기반 영향 전파 + 소형기업 매칭 + 경쟁기술 검증 | 실제 고객/매출로 오인한 결론 0; 새 자료가 기존 논제를 강화/약화한 이력 재현 |
| P4 | Vercel 지식 지도·알림·분석 요청, 30~90일 운영 채점 | 주요 알림의 유의미성, 근거 문장 단위 추적, 자료 무효화 시 재계산 |

**독립/오탐 검증:** 단순 신호 수가 아니라 `true incremental insight`, `false association rate`, `source lag`, `traceable claims`, `confirmed supply/revenue attribution`, `user actionable events`를 추적한다.

## 8. GraphDB 전환 판단
- 시작: PostgreSQL adjacency + recursive CTE + JSONB + FTS/pgvector (선택). Supabase 기존 운영과 일치.
- 나중: 복잡한 variable-length relationship, 빈번한 N-hop/중앙성 질의의 지연이 실제 한계를 넘었을 때 Neo4j/Memgraph/Apache AGE 등을 비교. 도입 전에 Supabase 호환성·배포·동기화 비용·이력 모델을 평가.
- 위키는 정의/해석 인터페이스, 그래프는 구조와 계산, 원천 증거는 검증 가능한 사실로 서로 역할을 구분.

## 외부 자료
- SK hynix hybrid bonding 설명: https://news.skhynix.com/en/tech-note-series-ep2/
- Camtek Hawk: https://www.camtek.com/products/hawk/
- IEEE P802.3dj (진행 중): https://standards.ieee.org/ieee/802.3dj/11115/
- POET + Lessengers 공동개발: https://www.poet-technologies.com/news/poet-technologies-and-lessengers-expand-partnership-to-deliver-1-6t-2xdr4-optical-transceivers-for-ai-network-connectivity
- OCP LVDC 전력 아키텍처: https://www.opencompute.org/news/powering-the-next-era-of-ai-how-google-microsoft-and-nvidia-are-standardizing-and-accelerating-the-industry-transition-to-lvdc/
- OCP White Paper 업데이트: https://www.opencompute.org/projects/data-center-facility/power-distribution/
- Supabase/Postgres: https://www.postgresql.org/docs/current/queries-with.html
