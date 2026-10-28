# Architecture Decision Records

되돌리기 어렵거나, 나중에 "왜 이렇게 했지?"라고 물을 만한 판단을 기록한다. 형식은 [MADR](https://adr.github.io/madr/) 축약형.

- 파일명: `NNNN-kebab-title.md`
- 상태: `proposed` → `accepted` → (`superseded by NNNN` | `deprecated`)
- 한 번 accepted된 ADR은 수정하지 않는다. 바뀌면 새 ADR을 쓰고 이전 것을 superseded로 표시한다.

| 번호 | 제목 | 상태 | 날짜 |
|---|---|---|---|
| [0001](0001-system-of-record.md) | 시스템 오브 레코드 = Supabase Postgres, 노션은 보류 | accepted | 2026-10-26 |
| [0002](0002-department-schemas.md) | 부서별 스키마 분리와 권한 방향 | accepted | 2026-10-26 |
| [0003](0003-collector-architecture.md) | 수집기 모듈 구조·멱등·워터마크·Store 어댑터 | accepted | 2026-10-26 |
| [0004](0004-initial-universe.md) | 초기 유니버스: 공개유동 <$1B, 바이오·의료기기·정부조달 | accepted | 2026-10-26 |
| [0005](0005-entity-resolution.md) | 엔티티 매칭: CIK 허브 + 소스별 별칭 테이블 | accepted | 2026-10-26 |
| [0006](0006-dev-console-frontend.md) | 개발용 조회 화면은 Next.js 최소 구성 | accepted | 2026-10-26 |
| [0007](0007-alpha-hypothesis-and-validation-order.md) | 알파 가설과 검증 순서 (백테스트 → 에이전트) | partially superseded by 0008 | 2026-10-26 |
| [0008](0008-product-is-the-brief.md) | 제품은 후보 브리프 — 백테스트·모의투자 제외, 섹터 확장 | accepted | 2026-10-26 |
| [0009](0009-brief-workflow.md) | 브리프 워크플로: 데이터팩 → 리서치 → 종합 → 비평, 날짜 박힌 예측 | accepted | 2026-10-26 |
| [0010](0010-technology-ecosystem-knowledge-graph.md) | 기술 생태계 온톨로지·증거 그래프·트리거 (설계안) | proposed | 2026-10-26 |
| [0011](0011-historical-evidence-linkage.md) | 과거 1차 자료 ↔ 그래프 연결 (리뷰 전용 인덱싱) | implemented | 2026-10-26 |
| [0012](0012-ontology-v03-closed-vocabulary.md) | 온톨로지 v0.3 — 닫힌 어휘, 수요 측 노드, 방향·근거 가중 영향 전파 | accepted | 2026-10-27 |
| [0013](0013-discovery-and-moat-cards.md) | 발굴 → 승격 → 해자 카드: 온톨로지가 유니버스를 만든다 | accepted | 2026-10-27 |
| [0014](0014-supply-chain-issue-feed.md) | 공급망 이슈 피드: 다출처 수집 → 온톨로지 태깅 → 선별 → DB | accepted | 2026-10-27 |
| [0017](0017-self-improving-research-system.md) | 스스로 판단하고 개선하는 리서치 시스템 — 가격·관측치·10점 근거 점수·채점·주간 개선 고리 | accepted | 2026-10-28 |
| [0018](0018-monitor-registry.md) | 모니터 레지스트리 — 품목 가격·R&D·IR·회의록·계통 데이터 트리거 (제안) | 제안 | 2026-10-28 |
| [0019](0019-valuation-as-the-result.md) | 결과는 가치평가, 점수는 계산기 — 이슈 → 영향 → 시나리오별 내재 주가와 기댓값, 재무 수집 | accepted | 2026-10-28 |
| [0020](0020-hypothesis-first.md) | 가설 우선 — 추론은 요구, 근거는 시험 도구, ★ = 검증 단계, watch = 예측 | accepted | 2026-10-29 |
| [0021](0021-market-scope-us-kr.md) | 시장 범위 — 주 기업은 미국·한국 상장사, 다른 시장은 신호·맥락으로만 | accepted | 2026-10-29 |
| [0022](0022-hypothesis-verification-loop.md) | 가설 검증 루프 — 2단계 생성(후보 → 선택·조사 → 작성)과 예측 채점이 움직이는 ★ | accepted | 2026-10-29 |
| [0023](0023-product-shape-reports-and-issues.md) | 제품 형태 — 기업 리서치 리포트 피드(목표주가·아이디어·근거)와 이슈 피드(이슈당 영향 경로 ≤3), 나머지는 수납 | accepted | 2026-10-29 |
