# 3단계 코드 도구 — `python -m wsj deep <cmd>` (결과는 JSON)

에이전트는 숫자를 글로 계산하지 않고 이 도구를 부른다. 미국은 SEC(EDGAR·XBRL), 한국은 공급망 지도(supply-map)와 Naver.

| 노드 | 명령 | 무엇을 돌려주나 |
|---|---|---|
| N10 | `deep target FPS` | 이름·거래소·섹터, 주가·시총(USD/KRW)·등락·52주, CIK, 최근 공시 목록 |
| N11 | `deep filings FPS [--text]` | 연차 3건(Item 1·1A·7)·10-Q MD&A·8-K EX-99·EX-10 목록 (`--text` 면 번호 문단) |
| N12 | `deep cards FPS [--plan] [--force]` | 연도별 구조 카드 7칸(조달·고객·핵심 의존·수주·잔고·경쟁·가격 요인·리스크) + 사업 개요·부문 + 확인 관계. 미국은 캐시 → 소형 모델(문서당 ≈$0.01) → `research.reports`, 한국은 공급망 지도 |
| N13 | `deep profile FPS` | 최신 카드 + 연도별 칸 변화(추가·삭제·값 변경) + 빈 칸 + 시세 + 최근 공시 |
| N14 | `deep story FPS [--days 365]` | 크게 움직인 날 상위 8개(번호 = 차트 표시), 초과 수익률·거래량 배수·같은 날 공시 |
| N15 | `deep fin FPS` | 연도별·TTM 매출·이익·FCF·ROIC·순차입·희석, 크게 튄 값 |
| N18 | `deep peers FPS VRT ETN POWL` | 피어 배수·성장·이익률, 피어 중앙값, 대상/중앙값 |
| N19 | `deep valuation FPS` | 현재 배수(P/S·P/E·EV/EBIT·FCF 수익률), 과거 회계연도 말 배수, 역DCF 내재 성장률 |
| N20 | `deep scenario --file s.json` | Bear/Base/Bull 가정 → 이익·지분가치·주당가치·지금 대비 배수, Base 배수에서 2·3배에 필요한 이익·매출 |
| N24 | `deep chart FPS --out fps.png` | 주가 PNG (story 번호 표시) |
| N24 | `deep notion --file report.json --image file-upload://… --market-cap … --candidate-page … --out page.md` | 노션 '리서치 리포트' 속성 + 본문 마크다운(`$`·`~` 이스케이프, 출처 접기, 사용자 메모) |
| N23 | `deep save --file report.json [--check]` | 직접 연 출처 → `ideas.clues`, 리포트 → `research.reports` kind=idea |

그 밖 조회: `python -m wsj tools quote|history|lookup|fx|rates|event|exposure|reverse-dcf|peers`.

## 주의
- `fin`·`valuation` 의 TTM 은 마지막으로 제출된 10-Q 까지다. 그 뒤 나온 실적 보도자료(8-K EX-99)·가이던스는 직접 열어 반영한다.
- Nasdaq 시총은 상장 주식 종류만 센다(Up-C·복수 주식 종류면 과소). 시나리오에는 전 종류 희석 주식 수를 쓴다.
- 카드 항목의 `loc` 은 근거 문단의 문서·절이다. 리포트 숫자는 카드가 아니라 원문을 다시 열어 확인하고 출처로 남긴다.
- 카드에 빈 칸이 있으면 그게 조사할 질문이다.
