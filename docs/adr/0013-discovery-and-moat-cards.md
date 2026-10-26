# ADR-0013: 발굴 → 승격 → 해자 카드 — 온톨로지가 유니버스를 만든다

- 상태: accepted
- 날짜: 2026-10-27
- 관련: [ADR-0012](0012-ontology-v03-closed-vocabulary.md) (온톨로지 v0.3), [ADR-0009](0009-brief-workflow.md) (브리프 데이터팩 재사용), [ADR-0004](0004-initial-universe.md) 를 부분 대체 (유니버스 정의)

## 맥락

사용자 정의 (2026-10-27): *"공급망 분석의 계기는 성장성이 큰 도메인 내 텐배거 발굴. 큰 기업도 중요하지만 소재·부품·공정·테스트·기술 층의 작은 기업에 혁신이 있을 수 있다. 그런 기업의 기술·해자·잠재성을 온톨로지와 데이터로 파악하는 건 AI 가 잘할 수 있다."*

리서치 (EDGAR 전문검색, 10-K/20-F/40-F 본문, 2025-08 ~ 2026-10, 46 노드 × 79 구문):
- 188개사 매칭. 공개유동 기준 micro 38 / small 29 / mid 24 / large 35 / 미상(20-F 등) 62.
- **소형사가 있는 병목 30개, 없는 병목 16개.** 없는 쪽은 하이브리드 본더·범프 계측·TSV 도금·EML·광 DSP·DC 차단기·DC 커패시터 등 — 대형사(BESI·KLA·Lumentum·Marvell·Eaton)가 쥐었거나 미국 상장 소형사가 없다.
- 소형 전문사로 볼 만한 것: AEHR(SiC·AI 프로세서 웨이퍼 번인), LWLG(EO 폴리머 변조기), ADEA(하이브리드 본딩 IP), ALMU(InP-on-Si), AXTI(InP 기판), KLIC(TCB 본더), NVTS(GaN·SiC, 800V 파트너), AOSL(전력 디스크리트), IPWR(B-TRAN 스위치), ASYS(SiC 가공·CMP), FORM·COHU(KGD 테스트), NVMI(계측), VECO·ICHR(장비 서브시스템), MXL(PAM4 DSP), AAOI(트랜시버), WOLF·CVV·INTT.
- 노이즈도 분명하다: "cold plate", "coolant pump", "sidecar", "busbar" 같은 구문은 원자로·EV·채굴업체를 끌어온다 (PALX·HYLN·NNE·PUMP 등). 발굴은 자동, 승격은 사람.

기존 유니버스(SIC 버킷 764사)에는 이 25개사 중 0개가 들어 있었다.

## 결정

1. **유니버스는 온톨로지에서 나온다.** `core.companies.in_universe` 의 두 번째 원천: 그래프 기업 노드 중 `in_universe=true` 인 SEC 필러 → `universe_reason='ontology:<eco>:<nodes>'`, `sector_bucket='supply_chain'`. `sec_universe` 주간 재구축은 이 행을 건드리지 않는다. 기존 SIC 유니버스는 유지하되 신호·브리프 우선순위는 온톨로지 유니버스가 앞선다.
2. **발굴은 자동, 승격은 사람.** `wsj.ecosystems.discover` (EFTS 구문 검색 → 특정성 점수 → 크기 밴드) → `research/ecosystems/discovery.json` → `wsj.ecosystems.promote` 의 `CURATED` (티커 → 노드) 만 그래프에 들어간다. 승격 관계는 `offered_by` / `technical_inference` / 출처 = 해당 10-K 색인. 해자 카드가 "제품으로 판매" 를 확인하면 등급을 올린다.
3. **해자 카드 (`wsj moat build`)** = 브리프 데이터팩(10-K Item 1/1A/7·10-Q MD&A·8-K·XBRL·주가) + 온톨로지 맥락(위치 노드, 같은 노드의 다른 회사, 상류 요구·세대·표준, 대체·잠식·연기 위협, 영향 전파 결과, 생태계 이벤트) → Sonnet 1회 (검색 없음, ≈ 25~35k 입력 토큰, 건당 $0.2~0.4). 출력: 공급망 위치(제품/역량/언급 구분), 해자 유형·강도·근거, 고객 증거, 재무 포착, 타이밍, 경쟁, 텐배거 역산, 반증, 데이터 공백, 점수(해자·타이밍·재무·데이터 품질·종합). 저장: `ideas.briefs(kind='moat')`, 반증은 `ideas.predictions`.
4. **파이프라인 순서**: 발굴(수동, 분기) → 승격(수동) → `universe sync` → 해자 카드(주 1회, `moat.yml`) → 후보 브리프(기존) → 이벤트 모니터가 노드 변화를 감지하면 해당 노드의 영향 기업 카드를 재생성 (BACKLOG O-9).
5. **화면**: `/discovery` (병목별 소형사 유무, 후보 표, 승격·카드 여부), `/briefs?kind=moat` + 카드 상세. 설명·면책 문구는 페이지당 한 줄 이하로 줄인다.

## 결과와 한계

- 발굴 구문은 `discover.QUERIES` 에 손으로 관리한다 — 노드 별칭(node_aliases.json)은 백필용이라 범용어가 많아 그대로 쓰지 않는다.
- 공개유동이 없는 20-F 필러(CAMT·NVMI·POET·IMOS·HIMX)는 크기 미상으로 남는다. companyfacts `EntityPublicFloat` 가 없기 때문 — 주가×주식수로 보강(BACKLOG S-6).
- 특정성 점수는 "희귀 구문이 10-K 에 등장" 이지 해자가 아니다. 해자 판정은 카드가 한다.
- 해자 카드 첫 실행은 LWLG·AEHR·ADEA 3건으로 프롬프트를 검증한 뒤 전체(22사)로 확대.
