# ADR-0018: 모니터 레지스트리 — 이슈·기업 소식 밖의 트리거 (품목 가격, R&D, IR, 회의록, 계통 데이터)

상태: 제안 (2026-10-28). 사용자: "트리거도 더 다양한 데이터(특정 품목 일별 가격, R&D 성과발표, IR, 회의록 등)를 모니터링할 수 있을까."

## 문제
지금 트리거는 세 가지뿐이다 — 뉴스·공시로 선별한 **이슈**, 기업별 **소식**(SEC·MOPS·DART·뉴스), 월 단위 **지표**(PPI·월매출·FRED·메모리 현물가).
병목이 조여지는 신호는 더 빨리, 다른 곳에서 나온다: 품목 현물가(일별), 학회·논문(세대 전환의 6~18개월 선행), 법설회·실적 발표 원문(수주잔고·리드타임·가동률),
계통 운영자 보고서(대형 부하 대기열), 정부 통계(수출입·광물). 이것을 **모니터**로 등록해 매일 한 번씩 읽고, 숫자는 `ideas.put_observations`(obs: 지표)로,
문서는 `ideas.put_company_events` 또는 이슈 후보로 흘려보낸다.

## 모니터 = (출처, 주기, 파서, 그래프 노드, 쓰는 곳)
`pipeline/wsj/ecosystems/monitors/<name>.py` 하나가 모니터 하나. 공통 인터페이스 `fetch(http) -> list[Observation | Event]`. 레지스트리 `monitors/__init__.py` 가 주기별로 돌리고 `ops.collector_runs` 에 'monitor:<name>' 으로 남긴다.
새 모니터는 주간 개선 작업이 아래 목록에서 하나씩 붙인다 (출처 도달은 `source-probe` 로 먼저 확인).

## 후보 목록 — 2026-10-28 개발 컨테이너에서 도달 확인
| 분류 | 출처 | 무엇 | 도달 | 쓰는 곳 | 우선순위 |
|---|---|---|---|---|---|
| 품목 가격 | 生意社 100ppi.com (게르마늄·인듐·갈륨·구리 일별) | 일별 현물가 | 200 (본문 636B — JS 렌더링, 상세 페이지 확인 필요) | obs:germanium_cny 등 | 1 |
| 품목 가격 | SMM metal.com 주간 리뷰 기사 | 게르마늄·인듐 주간가 | 기사 200, 가격표 404 | obs | 1 |
| 품목 가격 | USGS Mineral Commodity (게르마늄·갈륨·인듐 연간) | 생산·수입 의존도 | 200 | 그래프 근거 | 3 |
| 품목 가격 | TrendForce 보도자료 (광섬유·DRAM·NAND 현물) | 분기·월 | 200 (이미 수집) | obs | — |
| 계통·전력 | LBNL Queued Up (연 1회) · EIA 860M 신규 발전설비 (월) | 대기열·가스발전 신규 | 200 | obs:interconnection_* | 2 |
| 계통·전력 | ERCOT 대형 부하 보고서 · PJM 대형 부하 큐 | 데이터센터 부하 신청 GW | ERCOT 경로 변경(404) — 재탐색 | obs | 2 |
| IR·회의록 | TWSE `t187ap38_L` · TPEx `t187ap38_O` 법설회 일정 → MOPS 중대공시 법설회 요약 | 수주잔고·가동률·납기 원문 | 200 (437KB JSON) | company_events(kind=ir) | 1 |
| IR·회의록 | SEC 8-K Ex.99 실적 발표 + fool.com 콜 트랜스크립트 | 리드타임·수주·설비투자 발언 | 200 (이미 일부) | company_events + obs | 1 |
| IR·회의록 | TDnet 적시공시 (일본) | 決算·受注 | 200 | company_events | 2 |
| IR·회의록 | DART (한국) | 수주·투자 공시 | API 키 필요 | company_events | 2 (키) |
| R&D | arXiv API (`co-packaged optics`, `hybrid bonding`, `glass core substrate`, `800 VDC`) | 논문 제목·초록 | 200 | 이슈 후보(기술 전환) | 2 |
| R&D | IEEE IEDM·ECTC·OFC·ECOC·Hot Chips 프로그램 | 발표 제목(기업·기관) | IEDM 200, OFC 경로 변경 | 이슈 후보 | 2 |
| R&D | 특허 (Google Patents·PatentsView) | 출원 동향 | 미확인 (PatentsView 키) | 그래프 근거 | 3 |
| 표준 | OIF·OCP·JEDEC 발표 | 규격 확정 시점 | 미확인 | 이슈 후보 | 3 |
| 수출입 | 관세청 품목별 수출(HS 8541·8542·9001) · 대만 재정부 수출 | 월별 수출액 | 미확인 | 지표 | 2 |

## 결정 (제안)
1. 첫 3개: **TWSE/TPEx 법설회 → MOPS 요약(IR)**, **SEC 8-K 실적 발표 본문에서 숫자 추출(수주잔고·리드타임)**, **生意社/SMM 게르마늄·인듐 가격**. 모두 도달이 확인됐고 지금 아이디어(기판·InP·현장 발전)에 바로 걸린다.
2. 모니터가 만든 관측치는 기존 `obs:` 규칙(https 출처·날짜·단위)을 그대로 따른다. 문서형(IR·논문)은 `company_events` 의 새 kind(`ir`, `paper`)로 넣고, 이슈 선별기가 후보로 읽는다.
3. 주간 개선 작업 2단계 목록에 "7. 모니터 1개 붙이기 (ADR-0018 우선순위 순)"을 더한다.

## 열린 문제
- 生意社 가격표는 JS 렌더링일 수 있다 — 상세 페이지(`/mprice/detail-…`) 또는 모바일 경로를 probe 로 확인.
- 학회 프로그램은 구조가 해마다 바뀐다 — 제목·소속만 긁고 나머지는 LLM 선별에 맡긴다.
- 한국 DART 는 사용자가 API 키를 주면 바로 붙는다 (`DART_API_KEY` 시크릿은 워크플로에 이미 있음).
