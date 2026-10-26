# 소형 기술주 리레이팅: 공개 데이터 가설 검증·수집실험
기준일 **2026-10-26** · 연구 형태: 과거 사건의 원천 복원 · 실제 API 실험 GitHub Actions run [40300246153](https://github.com/W-X-Z/WSJ-investment/actions/runs/40300246153)

## 연구 질문
주가를 입력으로 삼지 않고, **시장이 기술 기업을 보는 관점이 바뀌기 전에 공개되어 있던 관측 가능한 증거**는 무엇이었는가?

사후 시장가치/주가를 설명하는 것이 아니라, 아래 네 가지 원인 후보를 검증:
1. 성능의 임계점 도달: 실험실 수준에서 실제 환경으로
2. 독립적인 검증: 기업의 주장 → 규제기관/고객/학술 논문으로 확인
3. 상업적 확장: 테스트 → 사용량·계약·고객의 반복적 구매
4. 경제성/위험: 성능 향상이 단위경제성과 조달/생존 가능성으로 연결되는가?

## 데이터 원천 범위
| 종류 | 사용한 실제 데이터 | 가설에 대한 역할 | 신뢰상의 함정 |
|---|---|---|---|
| 규제·의료 | openFDA PMA 원승인/확대 | 사용 가능 적응증/시장 확대 | 현재 JSON은 과거 snapshot 아님 |
| 임상 | ClinicalTrials.gov NCT | 임상 존재/설계/사전 등록 | 사후 결과를 과거 프로토콜과 혼동 |
| 학술·비정형 | Europe PMC 초록·OpenAlex 논문 메타 | 기술 검증·메커니즘·반대 논문 | 키워드 관련 논문 != 회사 제품 검증 |
| SEC 하드데이터 | EDGAR submissions·원문 8-K·10-Q | 계약·제품별 매출·상용화 단계 | 보고기간 종료일 != 실제 공시 공개일 |
| 정부 수주 | USAspending | 정부 고객 매출/계약 확인 | OTA 등 수록되지 않을 수 있음; 공시 지연 |
| 정부 규제 | Federal Register | 통신기술 정부 공개 문서 | FCC 라이선스 정보는 여기에 없을 수 있음 |
| 기업 기술 원문 | ASTS 2023 보도자료·IONQ 2023 기술 블로그 | 회사가 공개한 정량 기술 목표·성능 | 회사 자체 검증과 외부 검증 구분 |
| 개발자 활동 | GitHub 공개 저장소 검색 | 서드파티 실험/SDK 사용 가능성 | 해커톤 저장소 != 유료 채택, 현재 stars는 사후 정보 |
| 역사 웹 | Internet Archive CDX | 과거 기업 페이지의 존재 및 시점 | snapshot 날짜만으로 당시 주장 내용은 모름 |

### 수집 실험 결과
- 공개 API/페이지 **16개** 실제 요청 (기본 요청당 12초 타임아웃, 응답 상한 1.5MB).
- 성공적으로 후보 레코드를 추출: **15개**, 검색 결과 없음: **1개 (ASTS Federal Register)**, 접속/요청 오류: **0개**.
- 성공은 API 접근·파싱 성공을 뜻함. **투자 가설 입증 성공 15개가 아님**.
- 현재 조회한 자료는 대부분 2026년의 API 상태다. 각 자료의 출처 원문 최초 공개일을 별도 재검증해야 한다.
- 원천별 제한·조회 지연·빈 결과를 포함한 JSON 결과는 [해당 실행](https://github.com/W-X-Z/WSJ-investment/actions/runs/40300246153)의 `tech-evidence-public-sample` artifact로 보관(7일).
- 현 시점 학습용 샘플이므로 Supabase 운영 DB에는 아직 입력하지 않음.

## 가장 중요한 4개 사례

### TMDX — FDA + 무작위 임상시험 + 제품별 매출
1. **2021-09-03** FDA OCS Heart 원승인 P180051.
2. **2021-09-28** FDA OCS Liver 원승인 P200031.
3. **2022-01-05** JAMA Surgery 'OCS Liver PROTECT' 다기관 무작위 대조시험 논문 온라인 발표: 초기 이식 간 기능장애(EAD) **18% 대 31%**, DCD 기증 간 이용률 **51% 대 26%**. 결과는 조건/집단 정의를 같이 저장해야 하며, 기술 우위가 모든 환자·모든 장기에 일반화되는 것은 아니다.
4. **2022-04-27** FDA OCS Heart 사용 범위 DCD 심장까지 확장 P180051/S001.
5. **2022-11-03** 회사 3Q22 실적 발표: $25.7M 매출(+378% YoY), 추정치 변경 +$1.4M을 빼면 **$24.3M(+349%)**. 미국 매출의 약 **90%**가 NOP 고객에서 발생; 3Q OCS Heart $11.541M vs 전년 $2.848M, OCS Liver $12.543M vs 전년 미미한 매출.
6. 기업가치 리레이팅 가설: **FDA 적응증 승인 → 동료심사 임상 우위 → 실제 병원·시술 채택**의 연속 검증으로 '장비 제품'에서 '이식당 소모품+서비스 플랫폼'으로 시장의 평가 범위가 바뀔 수 있다.
7. 반증: 논문 설계의 외적 타당성, 비용편익/병원 경제성, DCD 실제 시술당 사용 비중, 경쟁사 임상 실적, 신규 고객 vs 기존 NOP 고객.
- FDA: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P180051
- FDA Liver: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P200031
- FDA DCD 확대: https://www.fda.gov/medical-devices/recently-approved-devices/organ-care-system-ocs-heart-system-p180051s001
- 논문: https://jamanetwork.com/journals/jamasurgery/fullarticle/2787486
- 2022-11-03 실적: https://www.sec.gov/Archives/edgar/data/1756262/000156459022036614/tmdx-ex991_6.htm
- 2022 Q3 공시: https://www.sec.gov/Archives/edgar/data/1756262/000156459022036772/tmdx-10q_20220930.htm
- API 스모크: FDA Liver 1건, Heart 2건, ClinicalTrials 1건, EuropePMC 5건, OpenAlex 5건.

### ASTS — 실제 링크 성능과 외부 통신사 검증
1. 2022-09-10: BlueWalker 3 시험 위성 발사.
2. 2023-04-25: 수정 없는 일반 스마트폰과 위성 양방향 음성통화 발표.
3. 2023-06-21: 일반 스마트폰 4G **10Mbps 초과** 시연 발표.
4. 2023-09-19: Vodafone·AT&T·Nokia 협업 5G 및 **약 14Mbps** 시연 발표. 실물 사업과 연결할 경우 커버리지/품질/주파수 효율/통신사 비용을 검증해야 한다.
5. 2024-05: AT&T 계약은 2023년 당시 알려지지 않은 **후속 검증**이다.
6. 외부 Nokia 공식 사례 소개는 조회 가능하나 현재 페이지의 최초 게시 시점을 별도 확인하지 않았으므로 **2023년에 투자자가 봤던 증거라고 주장할 수 없음**.
7. Federal Register 검색: **0건**. FCC 실험 허가가 없었다는 뜻이 아니다. FCC ICFS/ELS 문서와 FRN 필드 별도 수집이 필요.
- 원 발표: https://ast-science.com/ast-spacemobile-achieves-space-based-5g-cellular-broadband-connectivity-from-everyday-smartphones-another-historic-world-first/
- Nokia: https://www.nokia.com/customer-success/ast-spacemobile-and-nokia-achieve-worlds-first-space-based-5g-cellular-broadband-connectivity/
- SEC 제출 목록 API: https://data.sec.gov/submissions/CIK0001780312.json
- 핵심 반증: 특정 지역/수초 시연과 수백만 가입자 상용 서비스 간 용량·주파수·위성 생산 속도 차이.

### RKLB — 핵심은 추상적인 '우주 성장'이 아니라 사업 형태의 변화
1. 2023-12-21 SEC 8-K: 정부 고객에 **18개 우주선 제조·운용, 총 최대 $515M (확정 기본 $489M + 옵션/인센티브 $26M)** 계약 공개.
2. 2024-01-08 Space Development Agency에서 공급기업과 18기 계약 공개. **2023-12-21 투자자에게 SDA 고객 신원은 8-K만으로 확정되지 않았음**.
3. USAspending API는 Rocket Lab의 **NASA VADR 태스크오더 약 $51.6M**을 별도로 반환했다. 2023-12 SEC $515M과 **전혀 다른 계약**; 계약 ID/고객/금액/시점으로 매칭해야 한다.
4. 미국 국방부 계약은 공개 지연이 있고, OTA 조달은 표준 연방 조달 DB에 동일 방식으로 기록되지 않을 수 있음.
5. 기업가치 리레이팅 가설: **소형 발사 서비스 → 군용 위성의 제조·운용 프라임 계약자**로 경쟁 지위와 매출 기회 구조 전환.
6. 반증: 실제 수주잔고의 이익률/집행 리스크, 소형 발사 실적이 위성 하드웨어 납품 경쟁력으로 이어지는지, 약정 금액 중 옵션 비중.
- 8-K: https://www.sec.gov/Archives/edgar/data/1819994/000095017023072224/rklb-20231221.htm
- SDA: https://www.sda.mil/space-development-agency-makes-third-award-to-build-18-additional-beta-variant-satellites-for-tranche-2-transport-layer/
- USAspending: https://api.usaspending.gov/docs/intro-tutorial

### IONQ — 기술 홍보와 독립적인 성능 검증 사이의 간극
1. 2023-06-22 회사 기술 블로그: Forte에서 **29 algorithmic qubits(#AQ)** 달성을 발표.
2. 2022~23년 당시 학술자료 및 iQuHACK 연계 공개 GitHub 저장소 존재 확인.
3. **문제:** 논문이 trapped-ion 기술 일반을 다룬다고 IonQ 고유 하드웨어의 29 AQ를 독립적으로 검증했다는 뜻이 아님. 해커톤용 저장소가 있다는 것도 산업 고객 지불 의사를 입증하지 못한다.
4. 스스로 선정한 벤치마크 단위와 물리 qubit, 오류보정된 logical qubit을 동일하게 취급하지 않음. 특히 독립 벤치마크에서 재현된 회로 깊이·2큐비트 게이트 오류율·활용비용의 검증이 핵심.
5. 여기서는 **불확실성 해소 확인 미완료**, 기술 기대감형 사례로 분리.
- 2023 발표: https://ionq.com/blog/ionq-achieves-new-performance-milestone-of-29-algorithmic-qubits-aq-on-ionq
- 2023 해커톤: https://github.com/iQuHACK/2023_IonQ
- OpenAlex: https://api.openalex.org

### SERV — 수집 가능한 과거 흔적과 핵심 KPI 부재
- Wayback CDX에서 2022-01~ 웹페이지 캡처 날짜 확인. 그러나 아직 **그날의 콘텐츠/로봇당 배송 건수/원격개입률**은 추출하지 않았다.
- 과거 기업 웹페이지를 열어 실제 설치·고객·실사용 주장과 신뢰도 검증 필요. '자료 없음'은 사업 부재와 다르다.

## 리레이팅 발굴에 사용할 가설 기반 파이프라인
1. **기술 변화 사실** (what changed): 원시 실험 수치·임상 endpoint·규제 decision·유상 계약.
2. **변화가 제거하는 병목** (what uncertainty fell): 성능, 비용, 규제, 고객, 생산 능력, 재무.
3. **독립된 증거 수** (not source count): 회사 발표/언론 재인용은 하나의 계열; 규제 기관+고객+논문+실사용처럼 이해관계 분리된 증거가 필요.
4. **사업 효과 연결**: 사람/기술 지표 → 구매/사용량 → 단위경제성 → 확장성. 매출이 아직 없다면 적어도 유상 고객, 기술 실증의 객관적 문턱이 있어야 한다.
5. **대안 가설과 반증 조건**: 경쟁 기술/타제품 동시 성장, 시장 공통 트렌드, 일회성 수주, 실험 환경 부풀림.
6. **사전 공개 시점 검증**: `source_first_seen_at`, `original_published_at`, `observed_at`, `public_release_lag_days` 별도 필드. 현재 수정된 문서의 과거 날짜는 무조건 과거의 공개 정보로 취급하지 않음.
7. **후속 검증 이벤트**만 등록. 주가·밸류에이션은 별도 사후 성과 분석 때만 붙인다.

## 중요 추가 수집 1순위
- **기술 제3자 검증**: 논문 실험군/대조군 endpoint 수치 및 동종 경쟁기술 논문 비교. 논문 출처와 기업 자금지원 관계를 분리.
- **원문 내용과 공개 시점**: SEC 8-K 계약문서 원문 Diff, clinicaltrials.gov Study History, Wayback 당시 snapshot body, FDA PMA 신청·승인·supplements.
- **고객사 출처 교차검증**: 고객사 실적 컨콜·CAPEX·기술 채택 기록, 실사용량 공개.
- **특허/기술 선행성**: USPTO ODP API 키 연결, 출원 우선일→공개일→인용 시차, 핵심 claim vs 건수만 센 홍보.
- **현장 사용/조직 변화**: 센터별 이식 실적, 정부 수주 ID와 실제 지급, 회사 ATS 채용 스냅샷, 클라우드 SDK 사용·릴리즈·실제 고객 전환.
- **데이터 부재 기록**: 소스가 공개하지 않는 핵심 기술 지표 및 그로 인해 해소되지 않은 투자 불확실성을 같이 기록한다.

## 재현 및 운영 영향
- `research/technology_hypotheses.json` 가설 12개, falsifier·원천·as-of 포함
- `pipeline/wsj/studies/technology_evidence.py` 외부 API 16개 스모크·정규화·시점 필터·실패 기록
- `pipeline/tests/test_technology_evidence.py` 시점 오류/경계·금액·출처 무결성 단위 테스트
- `.github/workflows/historical-tech-evidence-probe.yml`: API 실험 결과를 GitHub Artifact에만 보관, 별도의 DB/LLM/모델 호출 없음.
- 실제 데이터 자동 수집과 Supabase 적재는 설계·테스트 이후에 도입한다. 현재 PR은 주가/거래 로직과 기존 스키마를 변경하지 않는다.
