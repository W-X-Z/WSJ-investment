# 데이터 소스 카탈로그

검증 기준일: **2026-10-26** (공식 문서 + 실제 호출 테스트). API 상태는 자주 바뀌므로 수집기가 깨지면 이 문서를 먼저 갱신한다.

범례 — 선행성: **L**(선행, 3~12개월 전) / **C**(동행, 0~2개월) / **T**(후행 확인) · 인증: 없음 / 키(무료) / 등록 / 스크래핑 · 상태: ✅ 사용 가능 / ⚠️ 제약 / ❌ 불가

## 1. SEC EDGAR (구조화)

| 소스 | 선행성 | 인증 | 갱신·지연 | 조인 키 | 상태 |
|---|---|---|---|---|---|
| `data.sec.gov/submissions/CIK##########.json` | C | 없음, UA 필수, 10 rps | 실시간(<1s) | CIK | ✅ |
| `api/xbrl/companyfacts`, `companyconcept`, `frames` | T | 동일 | <1분 | CIK | ✅ |
| `company_tickers.json`, `company_tickers_exchange.json` | — | 동일 | 일간 | CIK↔티커 (10,429개) | ✅ |
| EFTS 전문검색 `efts.sec.gov/LATEST/search-index` | C | 동일 (비공식) | 실시간 | `ciks`, `items`(8-K 항목), `form` | ✅ |
| Form 4 `primary_doc.xml` (ownershipDocument) | C | 동일 | 거래 후 2영업일 | CIK(issuer/owner) | ✅ |
| DERA Insider Transactions Data Sets (Form 3/4/5) | T | 없음 | 분기, 2006~2026Q3 | CIK | ✅ 백필용 |
| DERA 13F / Form D / N-PORT 데이터셋 | T | 없음 | 분기 (13F ~45–60일) | CIK/CUSIP | ✅ |
| 13D/13G | C | 없음 | 10일 내, XML 필수(2024-12~) | CIK | ⚠️ 벌크 없음, EFTS `SCHEDULE 13D`로 개별 파싱 |
| 8-K Item 1.01 (중요 계약) | C | EFTS `items` 필터 | 4영업일 내 | CIK | ✅ |

함정: 2026 Q2+ DERA zip 경로가 `/files/datastandardsinnovation/`로 이동. `RevenueRemainingPerformanceObligation`은 자산 <$1B 필러의 **7.4%**만 태깅 → 수주잔고 프록시 불가, 전문검색으로 대체. 벌크 nightly: `Archives/edgar/daily-index/xbrl/companyfacts.zip`, `bulkdata/submissions.zip`.

## 2. 시장 수급

| 소스 | 선행성 | 인증 | 갱신·지연 | 조인 키 | 상태 |
|---|---|---|---|---|---|
| FINRA `regShoDaily` (일별 공매도 거래량) | C | **없음**, 1,200/분 | T+1 | 티커 | ✅ |
| FINRA `consolidatedShortInterest` | C | 없음 | 월 2회, ~T+9영업일 | 티커 | ✅ |
| FINRA `weeklySummary` (ATS/OTC 종목·MPID별) | C | 없음 | Tier1 2주, Tier2 4주 지연 | 티커 | ✅ |
| FINRA `blocksSummary`, `thresholdList` | C | 없음 | 주간 | 티커 | ✅ |

함정: 정렬·limit에 **파티션 키 EQUAL 필터 필수** (`tradeReportDate`, `settlementDate`, `weekStartDate`+`tierIdentifier`). 날짜를 돌며 조회할 것. 동기 호출 5,000행/3MB, offset ≤500k.

## 3. 규제·승인 (바이오·의료기기)

| 소스 | 선행성 | 인증 | 갱신·지연 | 조인 키 | 상태 |
|---|---|---|---|---|---|
| ClinicalTrials.gov API v2 | **L** | 없음 | 일간 09:00 UTC | `leadSponsor.name` | ✅ 이력 API 없음 → 스냅샷 diff |
| openFDA `drug/drugsfda` | C | 키(120k/일) | 일간(평일) | `sponsor_name` (대문자 정확) | ✅ |
| openFDA `drug/orangebook` (신규) | T | 키 | 일간 | 신청자명 | ✅ |
| openFDA `transparency/crl` (승인거부서 전문, 458건) | C | 키 | 부정기 | 신청자명 | ✅ |
| openFDA `device/510k`, `device/pma` | C | 키 | **월간** | `applicant` | ✅ |
| openFDA `device/recall`, `enforcement` | C | 키 | 주간, 시작→보고 ~8주 | `recalling_firm` | ✅ |
| openFDA FAERS | T | 키 | 분기 +1개월 | — | ✅ |
| AccessGUDID (기기 식별자 DI) | **C** | 없음 | 일/주/월 델타 | `company_name` | ✅ 출시 신호 |
| CMS Part D/B 분기 지출 (브랜드·제조사별) | T | 없음 | 분기, ~4개월 | `Mftr_Name`, `Brnd_Name` | ✅ 처방 볼륨 프록시 |
| CMS Open Payments | T | 없음 | 연 1회(6월) | 제조사명 | ✅ |
| FDA Data Dashboard (실사·수입거부) | C | 등록 | 일간 | 시설명 | ✅ |
| FDA Warning Letters | C | — | — | — | ❌ API 없음 (XLSX 수동) |

## 4. 정부 수주·자금

| 소스 | 선행성 | 인증 | 갱신·지연 | 조인 키 | 상태 |
|---|---|---|---|---|---|
| USAspending API v2 | T | 없음 | FPDS +2일, **국방부 +90일** | UEI, `recipient/children` | ✅ |
| USAspending 월간 벌크 (Full/Delta) | T | 없음 | 매월 ~6일 | UEI | ✅ |
| FPDS ATOM 피드 | C | 없음 | 수일 | 벤더명 | ⚠️ FY2026 중 종료 예고 |
| war.gov 일일 계약 RSS (≥$7.5M) | **C** | 없음 | 당일 21:00 UTC | 벤더명(텍스트) | ✅ 국방 최속 |
| SAM.gov Opportunities (입찰 사전 공고) | **L** | 키 | 일간 | NAICS/PSC | ⚠️ **역할 없는 키 10회/일** |
| SAM.gov Contract Awards / Entity | T | 키 | — | UEI | ⚠️ 동일 제약, 모회사 계층 FOUO |
| Grants.gov 신규 API (`api.simpler.grants.gov`) | **L** | Login.gov 키, 60/분 | 일간 | — | ✅ 공고(NOFO) 선행 |
| SBIR.gov | T | — | 월간 CSV | UEI | ⚠️ API 403 다운 |
| DoD SBIR/STTR 토픽 사전공개 | **L** | 없음 | 회차별 | 토픽 텍스트 | ⚠️ 비공식 엔드포인트 |
| NIH RePORTER v2 | T | 없음, POST만, 1 rps | 주간 | 기관명 | ✅ |
| NSF Awards v1 | T | 없음, rpp ≤25 | — | `ueiNumber` | ✅ |
| Federal Register v1 + Public Inspection | **L** | 없음 | 게재 1일 전 | 텍스트 | ✅ |
| regulations.gov v4 | C | 키(1,000/시) | 수일~수주 | 코멘트 조직명 | ✅ |
| 상원 LDA 로비 공시 | **L** | 토큰 | 분기(LD-2), 신규등록 45일 | 클라이언트명 | ✅ |

## 5. IP·기술

| 소스 | 선행성 | 인증 | 갱신·지연 | 조인 키 | 상태 |
|---|---|---|---|---|---|
| USPTO ODP (파일래퍼·거래이력·PTAB) | C | 키(**ID.me** 필요, 90일 미사용 삭제) | 실시간(공개 출원만) | 출원인 문자열 | ✅ |
| PatentsView 벌크 (ODP 이전) | T | 키 | — | `assignee_id` | ⚠️ **API 2026-03 오프라인** |
| Google Patents BigQuery | T | GCP | 부정기(~분기) | `assignee_harmonized` | ⚠️ 백필 전용 |
| USPTO 상표 **일별 벌크 XML** | **L** | ODP | 출원 1~5일 후 | 소유자명 | ✅ 제품명 선행 |
| TSDR API | — | 키, 60/분 | — | 일련번호만 | ⚠️ 소유자 검색 불가 |
| FCC 장비인증 (EAS) | **L** | 스크래핑 | TCB 발급일 | grantee code | ⚠️ API·피드 없음, WAF |
| FCC 실험 라이선스 (ELS) | **L** | 스크래핑 | — | 신청자명 | ⚠️ |
| FCC ULS 벌크 | C | 없음 | 주간+일간 | FRN | ✅ |
| NIST CMVP 심사중 목록 | **L** | 스크래핑 | 거의 일간 | 벤더명 | ✅ 인증 6~18개월 전 |
| crt.sh 인증서 투명성 | **L** | 없음 | 실시간 | 도메인 | ✅ |
| Bluetooth SIG / Wi-Fi Alliance 인증 | **L** | 스크래핑 | — | 회사명 | ⚠️ |
| CourtListener v4 (특허소송) | C | 토큰, **무료 125/일** | — | 당사자명 | ⚠️ $10/월 티어 권장 |
| ITC §337 (EDIS/IDS) | C | — | — | — | ⚠️ 불안정 |

## 6. 물리 생산·에너지·환경

| 소스 | 선행성 | 인증 | 갱신·지연 | 조인 키 | 상태 |
|---|---|---|---|---|---|
| EIA-860M (계획 발전설비·소유주) | **L** | 없음(xlsx) / 키(API) | ~7주 | Entity ID | ✅ PUDL changelog 활용 |
| NRC ADAMS REST API (신규) | C | 키 | 수일 | 도킷, `AuthorAffiliation` | ✅ |
| FERC eLibrary | C | — | — | 도킷 | ❌ API 없음 (이메일 구독) |
| EPA ECHO | C | 없음 | 주간 | FRS ID | ✅ (실사·위반) |
| EPA TRI | T | 없음 | 연간, **10~16개월** | 모회사명 | ⚠️ 선행 불가 |
| MSHA 분기 생산·인력 | T | 없음 | 1분기 지연, 금요일 갱신 | controller | ✅ 석탄만 톤수, 그 외 `HOURS_WORKED` |
| Texas RRC / ND DMR / NM OCD | T | 없음 | ~2개월 | operator | ⚠️ 클라우드 TLS 실패(TX) |
| NHTSA 리콜·불만 | C | 없음 | 일간 | 제조사 | ✅ |
| FAA 항공기 등록 | T | 없음(zip) | 일간 | 제조사 코드·등록자 | ✅ |

## 7. 인력·웹 사용량

| 소스 | 선행성 | 인증 | 갱신·지연 | 조인 키 | 상태 |
|---|---|---|---|---|---|
| ATS 공개 채용 API (Greenhouse/Lever/Ashby) | **L** | 없음 | 실시간 | 보드 슬러그 | ✅ |
| DOL H-1B LCA / PERM | T | 없음(xlsx) | 분기, ~6주, 누적 | 고용주명 | ✅ 봇 차단 주의 |
| WARN 공고 | C | 없음 | — | 회사명 | ⚠️ 무료 피드 1개월 정체, `warn-scraper` 직접 실행 |
| GitHub `/stargazers/history` (신규) | C | 없음(60/시) | 주간 집계 | 레포 | ✅ 기존 stargazers 타임스탬프는 제한됨 |
| npm range API, pypistats, Docker Hub pull | C | 없음 | 일간 | 패키지명 | ✅ |
| Census EITS (M3 등) | T | **키 필요** | ~25일 | NAICS | ✅ 섹터 확인용 |
| BLS QCEW | T | 없음 | 5~6개월 | FIPS/NAICS | ✅ |

## 8. 매매 (NH PLUG)

- OAuth 접근토큰, 해외주식 주문/조회/시세, 체결통보 WebSocket, **모의투자 도메인 별도**. 사용신청은 나무증권 MTS QR 로그인. 샘플: github.com/PLUG-OpenAPI. 상세 스펙은 JS 렌더링 페이지라 로그인 후 확인 필요.

## 변경 이력

- 2026-10-26 최초 작성. 조사 원문은 `docs/log/2026-10-26.md` 참조.
