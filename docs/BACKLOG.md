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
| S-2 | Analyst 에이전트 → `ideas.briefs` | P1 | 미구현 | 후보별 10-K 사업 섹션·8-K·신호 원문을 읽고 브리프(왜 지금·하드데이터·아이디어·리스크·반증·점수) 작성 |
| S-3 | Risk 에이전트 (리스크 섹션) | P1 | 미구현 | 자금 소진·희석·바이너리·유동성·집중 고객 — 근거 링크 필수 |
| S-4 | 브리프 화면 `/briefs` + 분기 채점 | P2 | 미구현 | predictions 채점 UI |
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
