# ADR-0003: 수집기 모듈 구조 — 멱등·증분·독립·Store 어댑터

- 상태: accepted
- 날짜: 2026-10-26

## 맥락

소스가 20개 이상이고 API 상태가 자주 바뀐다(2026년에만 PatentsView 오프라인, FPDS 종료 예고, GitHub 스타 API 변경). 하나가 깨져도 나머지는 돌아야 하고, 나중에 코드 리뷰·개선이 쉬워야 한다.

## 결정

1. **한 소스 = 한 모듈** (`wsj/collectors/<source>.py`). `Collector` 인터페이스만 구현:
   ```python
   class Collector(Protocol):
       name: str                 # CLI 이름
       tables: tuple[str, ...]   # 쓰는 테이블 (schema.table)
       schedule: str             # 권장 주기 (문서용)
       def run(self, ctx: RunContext) -> RunResult: ...
   ```
2. **멱등**: 모든 쓰기는 자연키 기준 `upsert`. 두 번 돌려도 결과가 같다.
3. **증분**: `ops.collector_runs.watermark(jsonb)`에 마지막 처리 지점을 저장하고, 다음 실행은 거기서 시작. `--since`로 강제 가능.
4. **파서 분리**: 네트워크 없이 테스트 가능한 순수 함수는 `wsj/parsers/`에 두고 단위 테스트를 붙인다. 수집기는 "fetch → parse → upsert" 조립만 한다.
5. **Store 어댑터**: `Store` 프로토콜(`upsert`, `select`, `get_watermark`, `set_watermark`)에 `PostgrestStore`(운영)와 `SqliteStore`(로컬 검증) 두 구현. 수집기는 Store만 안다.
6. **HTTP 정책 중앙화**: `wsj/http.py`에서 호스트별 토큰버킷(SEC 10 rps 등), 재시도, User-Agent(SEC 필수)를 처리. 수집기는 `ctx.http.get_json()`만 호출.
7. **실패 격리**: 러너는 수집기 예외를 잡아 `ops.collector_runs`에 `failed`로 기록하고 다음 수집기로 넘어간다. `--all`에서 하나의 실패가 전체를 멈추지 않는다.
8. **원문 보존**: raw 테이블에는 파싱 결과 외에 `payload jsonb`(원문)를 함께 저장해 재처리가 가능하게 한다. 단, 용량이 큰 벌크(DERA 백필)는 제외.

## 결과

- 새 소스 추가 = 파일 하나 + 마이그레이션 하나 + 레지스트리 한 줄.
- API가 죽으면 그 모듈만 `schedule='paused'`로 표시하고 러너에서 건너뛴다.
- 테스트는 파서 중심. 수집기 통합 테스트는 `--limit` 스모크로 대체한다.
