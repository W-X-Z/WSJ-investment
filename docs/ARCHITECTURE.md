# 아키텍처

## 1. 목표와 가설

- **목표**: 공개 하드데이터 교차검증으로 미국 소형주(시총/공개유동 < $1B) 중 사업 변곡 종목을 찾아, 3~5년 보유로 텐배거를 노리는 바벨 포트폴리오를 운용한다.
- **제품**: 텐배거 후보 **브리프** — 왜 지금 / 하드데이터·원문 링크 / 투자 아이디어 / 리스크 / 반증 조건 / 점수 ([ADR-0008](adr/0008-product-is-the-brief.md)). 매매는 사용자가 직접. 백테스트·모의투자 없음, 브리프 예측을 분기마다 채점.
- **알파 가설**: 신호 하나(예: 내부자 매수)는 반영돼 있다. 알파는 (a) 서로 독립적인 데이터셋의 **교집합**, (b) 기관이 못 들어가는 **용량 제약 구간**, (c) 승자를 안 파는 **시간 지평**에서 나온다 ([ADR-0007](adr/0007-alpha-hypothesis-and-validation-order.md)).
- **유니버스**: 공개유동 $10M~$1B 소형주, 섹터 버킷 biotech · medtech · gov_procurement · energy · ai_software · semis ([ADR-0004](adr/0004-initial-universe.md), [ADR-0008](adr/0008-product-is-the-brief.md)).

## 2. 부서 = 에이전트 = 스키마

실제 운용사 조직을 그대로 DB 스키마와 권한에 옮긴다. 각 부서는 **자기 스키마에만 write**, 상류 스키마는 read-only.

```
 Data Desk ──write──▶ raw ──read──▶ core ◀──write── Data Desk (정규화·엔티티 매칭)
                                     │
                       Analyst ──read─┘─write──▶ ideas        (후보·투자논제·반증가능 예측)
                       Strategy ──read ideas ──write──▶ proposals (포지션 사이즈·진입/청산 규칙)
                       Risk ──read proposals ──write──▶ decisions (승인/거부/조건부, veto)
                       PM ──read decisions(approved) ──write──▶ orders
                       Execution ──read orders ──write──▶ fills   (NH PLUG API, 체결통보 WS)
                       Audit ──read all ──write──▶ reviews        (성과 귀인·논제 채점)
                       ops: 수집기 실행 로그·워터마크
```

Phase 1에서는 `raw`, `core`, `ops`만 채운다. Phase 2 는 `core.signals`/`core.candidates`(연결)와 `ideas.briefs`/`ideas.predictions`(해석, [ADR-0009](adr/0009-brief-workflow.md)). `orders`/`fills`/`decisions` 는 ADR-0008 로 보류 ([ADR-0002](adr/0002-department-schemas.md)).

브리프 파이프라인 (`wsj briefs build`): ① 데이터팩 (코드, LLM 없음: 10-K Item 1/1A/7 · 10-Q MD&A · 8-K ≤3 · XBRL 12분기 · 1y 주가 · 신호 · 내부자 · 피어) → ② 리서치 (Claude + web_search ≤8회: 매크로·섹터·테마·경쟁·뉴스, 출처 URL) → ③ 종합 (Claude, 검색 없음: 히스토리 → 현재 → 시장맥락 → 사업변화 → 주가맥락 → 반대가설 → 왜 지금 → 시나리오 → 텐배거 경로 → 리스크 → 반증·예측) → ④ 비평 (Risk 프롬프트: 근거 없는 주장·기저율·희석·바이너리·유동성·확률 재조정·사전부검·판정). 원문·주가는 `raw.sec_documents`/`raw.px_daily` 에 캐시.

## 3. 데이터 흐름

```
[공개 API/벌크] ─▶ collectors/<source>.py ─▶ Store.upsert() ─▶ raw.<source>_<table>
                        │                                           │
                        └─ ops.collector_runs (watermark, rows, error)
                                                                    ▼
                                     core.companies / core.entity_aliases (조인 키)
                                                                    ▼
                                            apps/web (Next.js) — 개발용 조회
```

- **수집기**는 `Collector` 인터페이스(`name`, `tables`, `run(ctx)`)를 구현하는 독립 모듈. 러너가 레지스트리에서 찾아 실행하고 `ops.collector_runs`에 기록한다 ([ADR-0003](adr/0003-collector-architecture.md)).
- **Store**는 PostgREST(HTTPS)와 SQLite 두 구현. 샌드박스·CI처럼 HTTPS만 되는 환경에서도 돌아야 해서 PostgREST를 기본으로 한다 ([ADR-0001](adr/0001-system-of-record.md)).
- **엔티티 매칭**: 소스마다 키가 다르고 어디에도 CIK가 없다. `core.entity_aliases(source, alias_type, alias, cik)`에 소스별 별칭을 쌓고, 수집기는 raw에 원문 이름을 그대로 두며 매칭은 별도 단계에서 한다 ([ADR-0005](adr/0005-entity-resolution.md)).

## 4. 저장소 레이아웃

| 경로 | 역할 |
|---|---|
| `supabase/migrations/*.sql` | 스키마의 단일 진실. Supabase MCP/CLI로 적용 |
| `pipeline/wsj/config.py` | 환경변수 → Settings |
| `pipeline/wsj/http.py` | httpx 클라이언트, 호스트별 토큰버킷, 재시도, User-Agent |
| `pipeline/wsj/db/` | `Store` 프로토콜, `postgrest.py`, `sqlite.py` |
| `pipeline/wsj/collectors/` | 소스별 수집기 (한 파일 = 한 소스) |
| `pipeline/wsj/parsers/` | 순수 함수 파서 (Form 4 XML 등). 테스트 대상 |
| `pipeline/wsj/runner.py` | CLI: `python -m wsj run <name> [--since] [--limit]` |
| `apps/web/` | Next.js App Router, 서버 컴포넌트에서 supabase-js로 조회 |

## 5. 운영

- 스케줄: GitHub Actions cron ([.github/workflows/collect.yml](../.github/workflows/collect.yml)). 소스별 주기는 [DATA_SOURCES](DATA_SOURCES.md)의 갱신 주기를 따른다.
- 시크릿: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`(서비스 롤). 프론트는 publishable key + RLS SELECT 정책.
- 장애: 수집기 하나의 실패는 `ops.collector_runs.status='failed'`로 남고 다른 수집기는 계속 돈다.

## 6. 아직 안 한 것 (의도적)

- 노션 동기화 — Phase 1 범위 밖 (사용자 결정).
- 에이전트별 DB 롤/RLS 분리 — 에이전트가 생길 때 ([BACKLOG](BACKLOG.md) P2).
- NH PLUG 매매 연동 — 모의투자 도메인부터, Risk 에이전트 이후.
