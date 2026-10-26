# ADR-0001: 시스템 오브 레코드는 Supabase Postgres, 노션은 보류

- 상태: accepted
- 날짜: 2026-10-26

## 맥락

에이전트 간 데이터 분리, 공시·시계열 대량 적재, 감사 추적이 필요하다. 후보는 노션 DB와 Supabase(Postgres)였다.

| 관점 | Notion | Supabase |
|---|---|---|
| 에이전트별 권한 분리 | 페이지 권한으로는 애매 | 스키마 + 롤 + RLS |
| 대량 시계열·공시 | API 3 req/s, 트랜잭션 없음 | Postgres 그대로, pgvector 가능 |
| 감사 추적 | 수동 | 트리거로 append-only |
| 사람이 읽기 | 압도적 | 별도 화면 필요 |

## 결정

1. Supabase Postgres를 유일한 시스템 오브 레코드로 쓴다.
2. 노션은 사람용 대시보드·의사결정 로그 용도로 **나중에** 단방향 동기화한다. Phase 1에서는 연동하지 않는다 (사용자 결정, 2026-10-26).
3. 프로젝트 리전은 `ap-northeast-2`(서울). 수집은 배치 쓰기라 리전 영향이 작고, 사용자가 서울에서 대화형으로 조회하는 지연이 더 중요하다. (초기 논의에서 us-east를 언급했으나 위 이유로 변경.)
4. 파이프라인의 DB 접근은 **PostgREST(HTTPS)**를 기본으로 한다. 샌드박스·CI 등 HTTPS만 허용되는 환경에서도 수집이 돌아야 하기 때문. 대량 백필이 병목이 되면 `Store` 어댑터만 psycopg 구현으로 교체한다.

## 결과

- 사람이 보는 화면은 `apps/web`으로 따로 만든다 ([ADR-0006](0006-dev-console-frontend.md)).
- Supabase 프로젝트: `wsj-investment` (ref `dcatgfivsvbktylmtvgf`).
