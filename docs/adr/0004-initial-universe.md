# ADR-0004: 초기 유니버스 — 공개유동 < $1B, 바이오·의료기기·정부조달

- 상태: accepted
- 날짜: 2026-10-26

## 맥락

텐배거는 거의 전부 기관이 용량 제약으로 못 들어가는 소형주 구간에서 나온다. 그러나 섹터마다 Phase 1 데이터 소스의 두께가 다르다 (2026-10 검증, [DATA_SOURCES](../DATA_SOURCES.md)).

| 섹터 | 무인증·실시간 소스 | 비고 |
|---|---|---|
| 바이오·제약 | ClinicalTrials, openFDA(drugsfda/CRL/Orange Book), CMS Part D, Form 4, 8-K | 가장 두터움 |
| 의료기기 | openFDA 510(k)/PMA(월간), AccessGUDID, Form 4 | 두터움 |
| 정부조달(방산·우주·인프라) | USAspending, FPDS ATOM, war.gov RSS, NSF/NIH, Form 4 | 두터움 (SAM.gov는 키 제약) |
| 하드웨어·통신 | FCC(스크래핑), 상표 벌크(Phase 2), NIST CMVP(스크래핑) | 얇음 |
| 소프트웨어 | npm/PyPI/GitHub, ATS 채용 | 커버리지 선택적 |

시총 데이터는 무료 공식 소스가 없다. SEC XBRL `dei:EntityPublicFloat`(10-K 공개유동)로 대체 가능.

## 결정

1. 유니버스 기준: **`EntityPublicFloat` < $1B** (최근 10-K), NYSE/Nasdaq/NYSE American 상장, SIC 코드가 아래 집합.
   - 바이오·제약: 2834, 2835, 2836, 8731
   - 의료기기: 3841, 3842, 3845, 3826, 5047
   - 정부조달: 3812, 3720, 3721, 3724, 3728, 3760, 3764, 3769, 3663, 3669, 7373, 8711
2. 유니버스는 `core.companies`에 저장하고 `in_universe` 플래그로 관리. 플래그 밖 종목도 `companies`에는 남긴다(소스 조인용).
3. 섹터 확장은 해당 섹터의 선행 소스가 Phase 2로 올라올 때 한다.

## 결과

- `sec_universe` 수집기가 `company_tickers_exchange.json` → `submissions`(SIC·거래소) → `frames/dei/EntityPublicFloat` 순으로 만든다.
- 공개유동은 10-K 시점 값이라 최대 1년 오래될 수 있다. 가격 기반 시총이 필요해지면 NH PLUG 시세 API로 보강한다 (BACKLOG P2).
