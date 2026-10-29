# 백로그

우선순위: **P1** 지금 / **P2** 다음 / **P3** 나중 / **B** 백테스트·연구

## 수집기

| ID | 수집기 | 테이블 | 우선 | 상태 | 비고 |
|---|---|---|---|---|---|
| C-01 | `sec_universe` | `core.companies` | P1 | ✅ 구현 | 티커·SIC·거래소·공개유동 |
| C-02 | `sec_form4` | `raw.sec_form4_filings`, `raw.sec_form4_transactions` | P1 | ✅ 구현 | EFTS → primary_doc.xml |
| C-03 | `sec_filings` | `raw.sec_filings` | P1 | ✅ 구현 | 8-K(items), 10-K/Q, 13D 인덱스 |
| C-04 | `finra` | `raw.finra_short_daily`, `raw.finra_short_interest`, `raw.finra_ats_weekly` | P1 | ✅ 구현 | 파티션 키 EQUAL |
| C-05 | `clinicaltrials` | `raw.ct_studies`, `raw.ct_study_changes` | P1 | ✅ 구현 | 스냅샷 diff |
| C-06 | `openfda` | `raw.fda_drug_applications`, `raw.fda_device_510k` | P1 | ✅ 구현 | |
| C-07 | `usaspending` | `raw.gov_awards` | P1 | ✅ 구현 | 유니버스 수신자명 검색 |
| C-08 | `sec_form4_backfill` | `raw.sec_form4_transactions` | P3 | 보류 | ADR-0008: 백테스트 제외. 내부자 '루틴 매수' 판별용 1~2년치만 필요해지면 재검토 |
| C-09 | `federal_register` | `raw.fedreg_documents` | P2 | 미구현 | public inspection 포함 |
| C-10 | `war_gov_contracts` | `raw.dod_contract_announcements` | P2 | 미구현 | RSS 파싱 |
| C-11 | `cms_partd` | `raw.cms_partd_quarterly` | P2 | 미구현 | 분기 |
| C-12 | `gudid` | `raw.fda_gudid_devices` | P2 | 미구현 | 일별 델타 |
| C-13 | `ats_jobs` | `raw.jobs_postings` | P2 | 미구현 | 보드 슬러그 수동 매핑 필요 |
| C-14 | `uspto_trademarks_bulk` | `raw.uspto_trademark_apps` | P2 | 미구현 | ODP 키(ID.me) |
| C-15 | `uspto_odp` | `raw.uspto_applications` | P2 | 미구현 | ODP 키 |
| C-16 | `nih_nsf` | `raw.gov_grants` | P2 | 미구현 | |
| C-17 | `eia_860m` | `raw.eia_planned_generators` | P3 | 미구현 | PUDL changelog |
| C-18 | `fcc_eas` / `nist_cmvp` / `crtsh` | — | P3 | 미구현 | 스크래핑, 브라우저 필요 |
| C-19 | `nhplug_quotes` | `raw.px_daily` | P2 | 미구현 | 현재가·시총 보강용 (백테스트 아님). 사용신청 필요 |

## 플랫폼

| ID | 항목 | 우선 | 비고 |
|---|---|---|---|
| P-01 | GitHub Actions 스케줄 | P1 | ✅ `collect.yml` |
| P-02 | 엔티티 매칭 `wsj entities resolve` | P1 | ✅ 정규화 매칭(0.9/0.8)·동명 충돌 큐. 남은 것: 후보 없는 이름은 큐에 안 넣어 백로그가 과소집계, `seen_count` 미증가 |
| P-07 | 수집기 리뷰 잔여 (LOW) | P2 | sec_filings 정정(/A) 별도 수집, FINRA 202/HTML 응답 재시도 검증, usaspending 페이지 상한 시 창 분할 |
| P-03 | 에이전트별 Postgres 롤·GRANT | P2 | ADR-0002 Phase 2 |
| P-04 | 노션 단방향 동기화 | P3 | 사용자 보류 |
| P-05 | 알림(수집 실패) | P2 | Actions 실패 알림으로 우선 대체 |
| P-06 | 조회 화면 Vercel 배포 | P2 | |

## 연결·해석 (ADR-0008)

| ID | 항목 | 우선 | 상태 | 설계 요지 |
|---|---|---|---|---|
| S-1 | 신호 레이어 `core.signals` / `core.candidates` | P1 | ✅ 구현 | 규칙 기반 (`wsj/signals/rules.py`). 가족(family): insider / contract / clinical / fda / gov / flow / dilution / activist. 후보 = 독립 2계열 이상 90일 내 교차 |
| S-2 | Analyst 에이전트 → `ideas.briefs` | P1 | ✅ 구현 (ADR-0009) | `wsj briefs build`: 데이터팩(10-K Item 1/1A/7·10-Q MD&A·8-K·XBRL 12분기·1y 주가·신호·피어) → 웹 리서치(8회) → 종합 JSON(히스토리·시장맥락·사업변화·주가맥락·반대가설·왜지금·시나리오·텐배거 경로·리스크·반증·예측) |
| S-3 | Risk 에이전트 (비평) | P1 | ✅ 구현 (ADR-0009) | 근거 없는 주장·기저율·희석·바이너리·유동성·내부자 함정·확률 재조정·사전부검·판정(proceed/watch/pass). 브리프 옆에 저장, 덮어쓰지 않음 |
| S-4 | 브리프 화면 `/briefs`, `/briefs/[id]` | P1 | ✅ 구현 | 시나리오 3열·텐배거 경로·리스크·예측 표·비평. 채점 UI 는 S-5 |
| S-5 | 예측 분기 채점 | P2 | 미구현 | `ideas.predictions.outcome` 채우는 화면(또는 SQL) + due_date 지난 pending 알림. 이후 가격·공시 기반 자동 채점(Audit) |
| S-6 | 브리프 입력 보강 | P2 | 미구현 | 8-K 첨부(EX-99.1 보도자료) 본문, 10-K 가 없는 신규 상장사의 S-1 섹션 매핑, 피어 시총(주식수) 수집, 동일 테마 피어(SIC 밖) 선정, 분할 조정 주가 |
| S-7 | 프롬프트 평가 루프 | P2 | 미구현 | 같은 데이터팩에 프롬프트 버전별 출력 비교 (`--dry-run` 산출물 기준), 비평이 잡은 '근거 없는 주장' 수를 지표로 |
| B-2 | 13F 화이트리스트 기관 선정 | P2 | 미구현 | 소형주 전문·승률 기준 20~30개 — 신호 가족 'institution' |
| B-3 | 기술 변화량 점수 (10-K 연도별 diff) | P3 | 미구현 | ADR-0007: 수준이 아닌 변화량 |
| ~~B-1~~ | ~~Form 4 × 촉매 이벤트 스터디~~ | — | 취소 | ADR-0008 |

## 알려진 제약 (2026-10)

- `EntityPublicFloat` 일부 필링이 천 달러 단위로 잘못 태깅됨 (PTCT 3,350,589 등) → 하한 $10M 으로 걸러냄. 근본 해결은 C-19 가격×주식수.
- EFTS `forms` 에 `/A`(정정) 폼을 섞으면 0건 반환 → 정정은 별도 수집 필요 (C-03 후속).
- FINRA 미발행 파티션은 204/빈 본문 → `[]` 처리.
- ClinicalTrials `query.spons` 는 협력기관까지 매칭해 유니버스 562개 질의에 7,224건 → 스폰서 매칭(P-02)으로 걸러서 본다.
- 시드: 서비스 롤 키 없이 샌드박스에서 Supabase 에 전량 적재 불가. `pipeline/scripts/sqlite_to_sql.py` 로 변환 가능하나 평상시엔 GitHub Actions(시크릿) 가 정식 경로.

- SAM.gov 무료 키 10회/일 → 입찰 사전공고는 Grants.gov·DoD SBIR 토픽으로 대체.
- PatentsView API 오프라인 → 벌크만.
- RPO XBRL 태그 소형주 7% → 전문검색.
- EPA TRI 10개월+ 지연 → 선행 불가.

## 공급망 온톨로지 (피벗 2026-10-26, ADR-0012 · 리뷰 `docs/review/2026-10-27-pivot-review.md`)

| ID | 항목 | 우선 | 상태 | 설계 요지 |
|---|---|---|---|---|
| O-1 | 온톨로지 v0.3 닫힌 어휘·검증기·린트 | P1 | ✅ | `ontology.json`, `wsj.ecosystems.ontology --check` |
| O-2 | 수요 측 노드(세대·표준·고객)·경쟁·대체·연기 관계 | P1 | ✅ 1차 | 121 노드/153 관계. 다음: TSMC CoWoS·OSAT·하이퍼스케일러, 병목별 소형 전문 공급사 |
| O-3 | 방향·근거 가중 영향 전파 + 웹 패널 | P1 | ✅ | `impact.py`, `impact-index.json` |
| O-4 | 유니버스 재정의 — 온톨로지 기업이 유니버스 | P1 | ✅ (ADR-0013) | `wsj.ecosystems.universe sync`, `sec_universe` 가 ontology 행 보존. 22사 편입 |
| O-10 | 발굴 `wsj.ecosystems.discover` + 승격 `promote` + `/discovery` | P1 | ✅ | 46 노드·79 구문, 188사, 소형사 있는 병목 30/46. CURATED 19사 승격 |
| O-11 | 해자 카드 `wsj moat build` + `moat.yml` + 카드 화면 | P1 | ✅ 22사 실행 | 종합 3/5 최고(AEHR·MXL·NVMI·ADEA·ASYS), 텐배거 후보 0. 다음: 카드 fit=product → offered_by 등급 승격 자동화, mention_only → CURATED 재검토(ALMU·VECO·ASYS·INTT·COHU) |
| O-12 | 20-F 필러 공개유동 보강 (주가×주식수), 발굴 구문 확장(특허·학회), 노이즈 구문 제거 | P2 | 미구현 | CAMT·NVMI·POET 크기 미상 |
| O-13 | 데이터팩 정합성: 회계연도 변경 기업의 TTM YoY(분기 합) 가 MD&A 연간 성장률과 어긋남(AEHR +9.1% vs −15.2%) → 연간 행 기준 YoY 병기, 런웨이 OCF≈0 이면 표시 생략 | P2 | 미구현 | 해자 카드가 스스로 잡아냈음 |
| O-14 | 이슈 피드에 비상장·해외 상장 핵심 플레이어(Infineon·Delta·Heron·BizLink·Amperesand 등) 기업 노드 추가 — 지금은 영향 기업 칩에 안 나와 800VDC 이슈가 'NVIDIA ±' 하나로만 연결됨 | P1 | 미구현 | ADR-0014 첫 실행 |
| O-15 | 이슈 → 해자 카드 재생성 트리거: 중요도 ≥7 이슈의 + 방향 소형사(MXL·WOLF·IPWR 등)는 해자 카드 재생성 큐에 넣기 | P1 | 미구현 | O-9 의 구체화 |
| O-16 | 이슈 피드 후보 품질: 규칙 단계 후보 60개 중 ~1/3 이 여전히 주가 기사 → 출판사 블랙리스트(TradingView·MarketBeat·24/7 Wall St. 개별종목 페이지) 또는 제목 분류기 | P2 | 미구현 | |
| O-17 | 이슈 피드 주간 다이제스트: 지난 7일 이슈를 생태계·노드별로 묶어 '병목 상태 변화' 한 장 (홈 상단) | P2 | 미구현 | |
| O-18 | 한국 공급사 실적·공시: DART OpenAPI(무료 키 필요 — 사용자 발급) — 한미반도체(TCB)·ISC·리노공업·SK hynix·삼성 분기/수시공시를 지표·이슈로 | P1 | 사용자 키 대기 | ADR-0014 개정 1 |
| O-19 | 특허 출원 추세: USPTO PatentsView API(무료 키) — 노드 구문별 월간 출원 수, 소형사 출원 급증 감지 | P2 | 미구현 | |
| O-20 | 일본 공급사(TDnet 적시공시: Advantest·Disco·Ibiden·Resonac·Shinko) 월간·분기 지표 | P2 | 미구현 | |
| O-21 | 지표 → 노드 패널: 캔버스 인스펙터에 연결 지표(스파크라인) 표시, 지표 임계치 이벤트를 영향 전파 입력으로 | P2 | 미구현 | |
| O-5 | 백필 재생성(단어 경계 필터)·별칭 유일성·웹 번들 제거 | P1 | 미구현 | 노이즈 hbm 52%·optics 34%·power 84% |
| O-6 | 모니터 운영화: 상태 커밋, daily 판정 cron 슬롯, 리포트 덮어쓰기 수정 | P2 | 미구현 | 또는 크론 중지 |
| O-7 | 관계별 원문 발췌(excerpt)로 단일 출처 집중 해소 | P2 | 미구현 | 린트 경고 3건 |
| O-8 | 웹: 홈 피드 생태계 필터, 캔버스 초기 fit·관계 라벨, 키보드, JSON 서버 슬라이스 | P2 | 완료 (2026-10-27, React Flow 재작성 — 초기 fit·관계 라벨·키보드·큰 JSON 지연 로딩) · 남음: 전체 범위 개요 라벨 ~8px, 영향 모드 허브 라벨 겹침 | 리뷰 §4 |
| O-9 | 이벤트 → 영향 → 브리프 연결 (이벤트 대상 노드의 impact 결과를 브리프 데이터팩에 포함) | P2 | 미구현 | 기존 `wsj briefs build` 와 접합 |

## 기회 발굴 — 시장보다 먼저 보기 위한 아이디어 (2026-10-29, ADR-0024 뒤)

뉴스에서 출발하는 이슈는 정의상 시장이 이미 본 것이다. "먼저"는 네 갈래에서만 나온다: ① 시장이 잇지 못한 2차·3차 고리 ② 남이 안 읽는 이른 출처 ③ 숫자 이상 신호 ④ 시차(선행·후행 쌍). 지금 데이터로 바로 되는 것부터.

| ID | 아이디어 | 갈래 | 우선 | 데이터 | 요지 |
|---|---|---|---|---|---|
| K-1 | **대만 월매출 → 한국 동종사 선행 스크린** | ④ | P1 | 있음 (tw_revenue 지표 + 그래프 offered_by) | 같은 노드를 공급하는 대만사(월매출, 매달 10일)와 한국사(분기) 쌍을 그래프에서 자동으로 만들고, 대만 월매출 YoY 가 한국사의 최근 분기 YoY 보다 크게 앞서면 '선행 단서'로 큐에 넣는다. 가장 빠른 공개 숫자를 가장 느린 공개 숫자와 잇는 것. |
| K-2 | **조용한 노출 큐** `v_q_silent_exposure` | ① | P1 | 있음 (impact-index, prices, company_events) | 관측치가 조여지는 병목에서 2~3홉 안의 미국·한국 소형사 중 최근 30일 소식이 없고(r1m 평탄) 주가가 안 움직인 곳. 점수 = 병목 조임 × 경로 신뢰도 × (1 − 주가 반응) × 소형. `leads.second_order` 를 매일 큐로 승격. |
| K-3 | **지표 → 합성 이슈** | ③ | P1 | 있음 (indicators, observations) | 지표 신호(월매출 급등·관측치 임계 통과)는 지금 큐에 못 들어온다(issue_key 없음 → 경로가 저장 안 됨). 수집기가 임계 통과를 이슈 행으로 만들어 같은 사슬을 타게 한다. |
| K-4 | **한국 관세청 HS코드 월별 수출** | ②③ | P1 | 새 수집기 (무료, TRASS/관세청) | 반도체 장비·기판·프로브카드 등 좁은 HS 코드의 대만·미국향 월 수출액이 뛰면, 그 코드의 한국 상장 수출사를 온톨로지로 역추적. 분기 실적보다 1~2개월 빠르고 아무도 안 읽는다. 노드 ↔ HS 코드 매핑을 온톨로지에 추가. |
| K-5 | **공시 텍스트 diff (10-K/10-Q · 사업보고서)** | ② | P2 | 있음 (raw.sec_filings) + 텍스트 | 소형사 공시의 '주요 고객 집중도·수주잔고·캐파' 문단을 이전 공시와 비교해 새 10% 고객·캐파 증설 문장이 생기면 이벤트로. 설계 승인(design-win)이 숫자로 나타나기 전의 유일한 공개 흔적. |
| K-6 | **내부자 매수 × 활성 경로** | ③ | P2 | 있음 (raw.sec_form4) | 활성 경로 끝의 소형사에서 임원 공개매수가 나오면 그 경로의 우선순위를 올린다. 두 독립 신호의 교집합. |
| K-7 | **노드 안 밸류에이션 분산** | ① | P2 | 있음 (fundamentals) | 같은 노드의 공급사들끼리 P/S·성장률을 비교해 같은 노출인데 가장 싼 곳을 상대적 선행으로. 리포트 작성 때 '같은 논리에 더 싼 기업' 규칙을 숫자로. |
| K-8 | **손해 보는 쪽 경로** | ① | P2 | 있음 (transitions polarity) | CPO 가 플러거블을, 800VDC 가 54V PSU 를 대체하면 지는 쪽을 명시한다. 지는 쪽 목록이 '누가 대신하나' 를 드러내고, 피해 기업은 피해야 할 목록이 된다. |
| K-9 | **생태계 교차점 기업** | ① | P3 | 있음 (also_in) | 두 생태계 이상에 걸친 노드(TIM, 고전압 커넥터 등)의 공급사는 수요가 겹친다. 그래프 중심성으로 매주 뽑는다. |
| K-10 | **예정 이벤트 달력** | ④ | P2 | 일부 | 대만 월매출(10일), 분기 실적, GTC·SEMICON·JEDEC 일정 앞에 조사 큐를 미리 채우고, 예측 due 를 그 날짜에 맞춘다. |
| K-11 | **경로 종류별 적중률로 점수 보정** | — | P2 | 있음 (verification) | 1단계 점수(구체·대담·반증·설명력)는 형식 점수다. 생태계·경로 길이·verdict 별 적중률을 주간에 계산해 선택 가중치를 바꾼다 (주간 9단계). |
| K-12 | **공시 캘린더 기반 '첫 숫자' 포착** | ②④ | P2 | DART (사용자 키, O-18) | 한국 소형사의 단일판매·공급계약 공시를 수집해, 활성 경로의 기업이 그 노드 고객과 계약을 공시하면 자동으로 예측 적중(hit)으로 채점. |

먼저 할 것: K-3(사슬의 구멍), K-1·K-2(기존 데이터로 큐 두 개 추가), K-4(새 수집기 하나로 한국 소형주 선행 신호).
