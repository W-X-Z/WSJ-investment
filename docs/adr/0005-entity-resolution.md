# ADR-0005: 엔티티 매칭 — CIK 허브 + 소스별 별칭 테이블

- 상태: accepted
- 날짜: 2026-10-26

## 맥락

소스별 식별자가 전부 다르고, **어디에도 CIK가 없다** (2026-10 검증).

| 소스 | 키 | 특성 |
|---|---|---|
| SEC | CIK, 티커 | `company_tickers.json`으로 매핑 (10,429개) |
| USAspending / NSF | UEI | 자회사마다 UEI가 다름 (Kratos S1/S2/RT Logic). `recipient/children`로 묶기 |
| openFDA | `sponsor_name`, `applicant` | 대문자 법인명 정확 일치 ("ARDELYX INC") |
| ClinicalTrials | `leadSponsor.name` | 변형 많음, 자회사·구 사명 |
| NIH RePORTER | 기관명 | UEI 없음 |
| CMS Part D | `Mftr_Name` | 제조사명 |
| FINRA | 티커 | 가장 깨끗 |
| USPTO (벌크) | `assignee_id` | 디스앰비규에이션된 ID는 벌크 테이블에만 |
| FCC | grantee code, FRN | grantee 목록 2021년 이후 갱신 없음 |
| DOL H-1B | 고용주명 | 퍼지 매칭만 |
| ATS 채용 | 보드 슬러그 | 수동 매핑 |

## 결정

1. **허브 키는 CIK.** `core.companies(cik pk)`.
2. `core.entity_aliases(source, alias_type, alias, cik, confidence, method, verified_at)`에 소스별 별칭을 쌓는다. `method`는 `exact | normalized | fuzzy | manual | llm`.
3. 수집기는 **매칭하지 않는다.** raw 테이블에 소스 원문 이름을 그대로 저장하고, 매칭은 `wsj entities resolve` 별도 단계가 한다. 이유: 매칭 규칙이 바뀌어도 raw를 다시 긁을 필요가 없어야 한다.
4. 매칭 순서: (a) 티커/UEI 등 정확 키 → (b) 법인명 정규화(접미사 INC/CORP/LTD 제거, 대문자, 구두점 제거) 정확 일치: **현재 사명 유일 일치 = 0.9, 구 사명 유일 일치 = 0.8** → (c) 같은 정규화 이름이 둘 이상의 CIK 를 가리키면(동명·사명 승계, 예: RXI PHARMACEUTICALS) 자동 매칭하지 않고 후보와 함께 `unresolved` 큐로 → (d) 그 외 업종어 제거 후보만 있는 경우도 큐. 퍼지 매칭 자동 승인은 하지 않는다 (오염이 모든 조인에 전파되므로).
5. 자회사는 모회사 CIK에 매핑하되 `alias_type='subsidiary'`로 구분한다.

## 결과

- 조인은 항상 `raw.x JOIN core.entity_aliases USING (alias) JOIN core.companies USING (cik)`.
- 매칭 품질은 `core.entity_aliases.confidence`와 `unresolved` 건수로 모니터링한다 (조회 화면 개요에 표시).
