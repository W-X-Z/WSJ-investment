# ADR-0014: 공급망 이슈 피드 — 다출처 수집 → 온톨로지 태깅 → 선별 → DB

- 상태: accepted
- 날짜: 2026-10-27
- 관련: [ADR-0012](0012-ontology-v03-closed-vocabulary.md) (노드·기업 어휘), [ADR-0013](0013-discovery-and-moat-cards.md) (발굴 구문 재사용), 기존 `technology-intelligence-monitor` 를 대체

## 맥락

사용자 (2026-10-27): *"웹앱을 봤을 때 데이터가 부족해 보이고, 특히 최근 주요 공급망 이슈를 모르겠다. 다양한 출처에서 선별해서 이슈를 알려주면 좋겠다."*

기존 모니터는 6시간 크론으로 돌았지만 산출물이 GitHub 이슈 코멘트뿐이라 웹에 보이지 않았다. 홈 피드는 Form 4·8-K 신호와 정적 이벤트만 보여 "이번 주 세 공급망에서 무슨 일이 있었나" 에 답하지 못했다.

## 결정

1. **출처 5종** (모두 무료·키 불필요): Google News RSS(생태계별·소형 기업명 질의), 업계지 RSS(Semiconductor Today 등), SEC EFTS 8-K/6-K 전문검색(발굴 구문 재사용), Federal Register(BIS·투자안보실·ITC·DOE, 기관별 + 제목 필터), DB `core.signals`(유니버스 기업 8-K·Form 4).
2. **처리**: 노이즈 정규식(주가·목표가·일정 공지·토큰 시세 등) → URL·제목 중복 제거 → 단어 경계 어휘 태깅(발굴 구문의 첫 인용구 우선, 범용어 제외) → 클러스터(공유 토큰 ≥3, 기업 집합이 다르면 병합 금지, 5일 창) → 규칙 점수(출처 가중·독립 출판사 수·노드 수·소형사 가산·최근성).
3. **SEC 공시는 원문을 연다**: 8-K/6-K 의 EX-99 헤드라인을 제목으로 쓰고, 구문이 "About 회사" 상용구에만 있으면 버린다 (예: POET 6-K 의 실적 발표일 공지가 'optical interposer' 로 잡히던 문제).
4. **선별·요약은 LLM, 어휘는 닫힌 카탈로그**: 상위 60개 후보 → Sonnet 1회 → 최대 15개 이슈. 노드·기업 id 는 그래프에 있는 것만 통과(`rows_from_picks`). 중요도 1~10 + 근거 한 문장, 기업별 방향(+/−/±)은 기사 근거가 있을 때만. 사실만, 주가 전망 금지. LLM 실패 시 규칙 결과로 저장.
5. **저장**: `ideas.supply_chain_issues` (마이그레이션 0015), 공개 뷰 `public.v_supply_chain_issues`. 재실행 시 출처 URL 이 겹치면 같은 `issue_key`·`first_seen` 을 이어 쓴다.
6. **운영**: `issues.yml` 매일 06:47 KST. `--picks` + `--cache` 로 수집 결과를 고정한 채 다른 선별(사람·다른 모델)을 적용할 수 있다.
7. **화면**: 홈 헤드라인 = 최근 이슈 중 중요도 최고. 피드 카드에 `n/10`·영향 기업 칩(방향 색), 상세에 왜 중요한가·영향 기업(지도 링크)·연결 노드·출처 전부.

## 첫 실행 (2026-10-27, 캐시 수집)

946건 → 관련 403 → 클러스터 310 → 후보 60 → 이슈 16. Actions 가 결제 문제로 시작되지 않아 세션에서 직접 선별(`--picks`)하고 DB 에 적재했다. 상위: AMAT 의 Besi 지분 20% 확대(8), MaxLinear Q3 +72%·AEC 진출(8), Wolfspeed–Infineon 200mm SiC(7), NVIDIA HBM4 사양 하향 보도(7).

## 개정 1 (2026-10-27 오후) — 출처 확장·지표

사용자: *"출처를 더 늘리고 싶어 — 논문·기술연구, 반도체 가격, 부품 가격, 기업 IR, 관련 정책 등."*

- **출처 레지스트리 `sources.py`** — 한 줄 추가로 늘릴 수 있는 RSS/Atom 공통 파서.
  - 업계지: EE Times, Semiconductor Engineering, eeNews Europe, Power Electronics News, DCD, ServeTheHome, Tom's Hardware, DigiTimes
  - 회사 뉴스룸·IR(`newsroom`): Samsung, SK hynix, NVIDIA, PR Newswire 반도체 (미국 상장사는 SEC 8-K EX-99 로 이미 들어온다)
  - 정책(`policy`): 백악관 대통령 조치·NIST(CHIPS) — 반도체·관세·232·핵심광물·데이터센터 제목 필터. Federal Register 기관에 상무부(232)·USTR(301)·FERC(대형 부하)·NIST 추가
  - 리서치 기관(`analyst`): TrendForce 보도자료 (메모리 계약가·광섬유 현물가·CPO 테스트 등)
  - 논문(`research`): arXiv API(3초 1회), OpenAlex(IEEE 학회 포함) — 발굴 구문의 첫 인용구로 노드별 검색, 최근 30일. 저자 소속에 산업체가 있으면 표시
  - Google News 질의에 표준(JEDEC·802.3dj·OCP·OIF)·가격(DRAM 계약가·광섬유·변압기 리드타임·CoWoS·ABF)·정책(232·CHIPS·FERC·수출규칙) 추가
- **지표 `indicators.py` + 마이그레이션 0016** (`ideas.indicators`, `ideas.indicator_points`, 뷰 `v_indicators`·`v_indicator_points`):
  - 메모리 현물가 6종 (DRAMeXchange 홈페이지 표, 세션 평균만 저장)
  - 미국 PPI·원자재 8종 (FRED fredgraph.csv: 반도체·변압기·커넥터·광섬유 케이블·PCB·개폐기 PPI, 구리·알루미늄)
  - 대만 공급사 월매출 17사 (TWSE·TPEx OpenAPI: TSMC·ASE·Unimicron·KYEC·WinWay·MPI·CHPT·Accton·LandMark·Luxnet·FOCI·Browave·Delta·Lite-On·BizLink·AVC·Auras) — 미국 실적보다 2~3개월 빠른 수요 신호
  - 임계치(현물 1주 ±8%, 월매출 YoY ≥60%·≤−15%·MoM ±25%, PPI 전월 ±1.5%·전년 ±10%)를 넘으면 `data` 후보 → LLM 이 기사와 묶거나 단독 이슈로
- **후보 선정**: 규칙 점수 상위 + 유형별 최소치(논문 6·지표 8·리서치 기관 5·정책 4·관보 4·뉴스룸 4). 논문은 이슈 최대 3개(`event_type=research`).
- **화면**: `/indicators` (그룹별 표·스파크라인·연결 노드), 홈 "가격·실적 지표 변화" 상위 6.
- 보류: 한국 DART(키 필요), 일본 TDnet, 특허(PatentsView 키 필요), JEDEC·Micron IR(봇 차단), FRED API(키 없이 CSV 사용).

## 한계

- Google News 링크는 리다이렉트 URL 이라 본문 스니펫이 비어 있다. 요약은 제목·업계지 본문·공시 원문에 기댄다.
- 규칙 점수만으로는 주가 기사가 여전히 후보 상위에 섞인다(60개 중 약 1/3). LLM 선별 단계가 필요한 이유.
- 비상장·해외 상장사(Infineon·Delta·Heron 등)는 그래프 기업 노드가 없어 영향 기업 칩에 나오지 않는다 → BACKLOG O-14.
