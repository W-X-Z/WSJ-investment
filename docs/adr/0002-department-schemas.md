# ADR-0002: 부서별 스키마 분리와 권한 방향

- 상태: accepted
- 날짜: 2026-10-26

## 맥락

"실제 회사처럼 부서를 나눈다"는 요구를 DB에 어떻게 옮길지. 테이블 접두사 vs 스키마 분리 vs 별도 DB.

## 결정

Postgres **스키마 = 부서**로 고정한다. Phase 1에서 모든 스키마를 만들어 구조를 선점하되, 채우는 것은 `raw`·`core`·`ops`뿐이다.

| 스키마 | 소유 부서 | 내용 | write | read |
|---|---|---|---|---|
| `raw` | Data Desk | 원천 데이터 미러 (가공 없음, 소스별 테이블) | Data Desk | 전체 |
| `core` | Data Desk | 정규화·엔티티 매칭 결과 (`companies`, `entity_aliases`) | Data Desk | 전체 |
| `ideas` | Analyst | 후보·투자논제·반증가능 예측 | Analyst | Strategy 이상 |
| `proposals` | Strategy | 포지션 제안·진입/청산 규칙 | Strategy | Risk 이상 |
| `decisions` | Risk | 승인/거부/조건부 심사 결과 (veto) | Risk | PM 이상 |
| `orders` | PM | 승인된 제안의 주문 큐 | PM | Execution |
| `fills` | Execution | 체결·체결통보 | Execution | Audit |
| `reviews` | Audit | 성과 귀인·논제 채점 | Audit | 전체 |
| `ops` | 시스템 | 수집기 실행 로그·워터마크 | 러너 | 전체 |

원칙: **하류 스키마는 상류를 read-only로만 본다.** Execution은 `decisions.status='approved'`만 읽을 수 있어야 한다.

권한 구현은 단계적으로:
- Phase 1: 서비스 롤 하나로 수집. 프론트는 publishable key + `raw`/`core`/`ops` SELECT RLS 정책.
- Phase 2: 에이전트가 생기면 스키마별 Postgres 롤(`agent_analyst` 등)과 `GRANT`로 분리. RLS보다 롤 `GRANT`가 "부서 간 경계"를 더 정직하게 표현한다.

PostgREST는 기본으로 `public`만 노출하므로 `raw, core, ops`를 노출 스키마에 추가한다 (`ALTER ROLE authenticator SET pgrst.db_schemas`).

## 결과

- 테이블 이름에 부서 접두사를 붙이지 않는다 (스키마가 그 역할).
- `raw.*` 테이블은 소스 필드명을 가능한 한 그대로 쓰고, 해석 컬럼을 추가하지 않는다.
