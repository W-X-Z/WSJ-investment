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
