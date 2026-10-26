# Ecosystem Research Book — 3 technology systems (2026-10-26)

> **목적:** 주가/밸류에이션을 입력으로 사용하지 않는다. 기술 요구 변화 → 소재·공정·부품의 새로운 병목 → 해결 기술 → 회사의 경제적 노출을 추적하는 실험.
>
> **검증상태 범례:** 사실=공식 문서로 확인; 회사주장=원문 수치지만 독립 성능 검증 부족; 가설=기술 인과·경제 효과의 추가 증거 필요.
>
> 실제 노드·엣지·관찰 이벤트·감시 대상은 `seed_graph.json`에 구조화. 이 문서는 가설의 기술적 해석과 분석 경계 조건을 설명한다.

## A. HBM4/차세대 첨단 패키징과 검사 생태계

### 중요 변화 / 정량
- SK hynix (2026 기술 노트)는 HBM3E의 I/O 1,024개 대비 HBM4에서 2,048개를 언급한다. 더 많은 I/O·높은 DRAM 적층은 연결·열·두께·수율 이슈를 확대한다.
- SK hynix는 기존 TCB(열압착)에서 접합 피치 약 7µm 이하의 변형·응력 문제와 고적층 열 누적을 설명한다. 이 판단은 기술 공급자 설명이며 제조사별 공정/세대가 다르다. **HBM4에서 모든 제조사가 하이브리드 본딩을 채택한다는 주장은 사실이 아님**. HBM4E 이후/차차세대에 적용 가능성에 대한 시나리오로 취급.
- Camtek Hawk 공개 사양: 결함 감도 최대 0.1µm (조건 별도), Eagle G5 대비 최대 2배 처리량, 웨이퍼당 5억개 이상 범프, bump pitch <10µm 측정, IR overlay 반복 정밀도 <15nm 등의 수치를 제시한다. 이들은 **제조사 제품 사양**이지 독립적인 고객 양산 측정치가 아니다.
- Camtek 2024-11-27 Hawk 초기 주문 >$50M; 2026-02-10 특정 IDM 누적 주문 $45M; 2026-06-02 HBM 제조사·OSAT로부터 합계 >$105M, 2027년 납품 예정. 2월의 누적 주문과 6월 신규 주문을 합산하거나 2026 회계 매출로 바로 환산하면 안 됨.

### 제조 단계별 물리량
| 공정/재료 | 병목 | 우선 수집 정량 데이터 | 관계/영향 가설 |
|---|---|---|---|
| DRAM 적층 | 층간 열 축적·높이/변형 | 층수, stack height µm, 열저항 K/W, warpage µm | hybrid bond/몰딩/열관리 대체 |
| microbump/접합 | 접합 피치 축소, 미접합/결함 | bump pitch µm, overlay nm, defect size nm, bond yield % | 고성능 2D/3D/IR 검사 필요 |
| wafer-level 검사 | 검사 영역/빈도·시간 비용 | WPH, false positive rate, throughput vs sensitivity curve | 생산능력 증가 시 검사 CAPEX 또는 대체 방법 변화 |
| 소재·underfill | 충진/박리/열팽창 차 | CTE, 접착력, 계면 voids, dielectric losses | 소재 공급자 중 대체/도태 업체 발생 |

### 핵심 그래프 경로 및 반증
`HBM4 I/O/적층 증가 -> 미세 접합·열관리 요구 -> 결함 검사/하이브리드 본딩 -> CAMT(Hawk)`
- 공식 연결: Camtek이 Hawk 제품을 개발·주문 받았다는 사실.
- 미확인: 특정 메모리 제조사의 총 증설 중 Hawk 채택 비율, 주문당 마진, 검사 단계/설비당 소요량.
- 반대 가설: 하이브리드 본딩이 미세범프를 일부 대체하여 **기존 bump 검사**를 약화시키면서 새로운 overlay inspection을 발생시킬 수 있다. 검사 수요가 단순히 증가한다는 한 문장은 불충분.
- 기술 경쟁: KLA/ONTO 등 제품별 경쟁사·측정 방식 비교 필요. 단독 업체 공급 독점 가정 금지.

### 감시/강도
1. SK/JEDEC/OEM의 stack/pitch/입출력 세대별 표준 갱신 -> **기술 요구 변화**.
2. 계측기 vendor의 새 결함 감도 + 처리량 조건 -> **기술 적합성** (조건 다르면 비교 불가).
3. 메모리/OSAT 고객 양산 검증/반복 주문/인도 -> **상업 증거** (독립 출처 선호).
4. 대체 검사 방식·새로운 본딩이 incumbent 장비 수요를 잠식 -> **역방향 영향**.

### 우선 원천
- SK hynix: https://news.skhynix.com/en/tech-note-series-ep2/
- Camtek 기술 사양: https://www.camtek.com/products/hawk/
- Camtek 2024 주문: https://www.camtek.com/news-and-events/camtek-receives-orders-for-over-50-million-for-its-new-product-line-hawk/
- Camtek 2026 반복: https://www.camtek.com/news-and-events/camtek-receives-over-105-million-multi-system-orders-from-a-tier-1-osat-and-a-leading-hbm-manufacturer/
- Semiconductor Engineering HBM 기술과 테스트 공정: https://semiengineering.com/knowledge_centers/memory/volatile-memory/high-bandwidth-memory/

## B. AI 클러스터 800G/1.6T 광통신과 포토닉스

### 기술 로드맵 / 구조
- IEEE P802.3dj는 1.6Tb/s Ethernet와 200/400/800Gbps 계층을 포함하며 **2026-10-26 기준 Draft/Active PAR**. 승인된 최종 규격이라고 쓰지 않는다.
- 별도 P802.3dv의 400Gbps/lane 프로젝트가 2026-09-25 PAR 승인을 받은 것은 더 다음 세대 요구가 시작된 정황이다. 기술 상용화가 곧 발생했다는 증거는 아니다.
- 광모듈은 DSP/SerDes, 레이저, 변조기, 포토다이오드, 광도파로·커플링, 패키징, 광섬유와 같은 연쇄 부품으로 이루어진다. 광속도가 빨라질수록 신호 손실·전력·열·정렬 편차가 시스템 난제를 만든다.
- 2026-03-17 POET와 Lessengers가 1.6T 2×DR4 트랜시버 공동 개발을 공식 발표. POET 광인터포저/광엔진과 Lessengers DOW 결합을 설명한다. **공동개발 ≠ 고객 양산 인증 / 반복 주문 / 매출**.

### 세부 비교할 데이터
| 레이어 | 물리량/공정 | 관측할 수 있는 원문 | 잠재 기업 연결 |
|---|---|---|---|
| 광인터페이스 | Gb/s/lane, BER, FEC 요구, 링크 길이 | IEEE draft·회의 슬라이드 | 전송 부품 설계 변경 |
| 광원·변조기 | laser output mW, extinction ratio dB, 온도 안정성 | vendor datasheet, independent measurements | 레이저·변조기 공급자 후보 |
| 인터포저·정렬 | coupling insertion loss dB, 조립 정렬 허용 오차 µm, 수율 | packaging 논문, 공정 사양 | POET 광엔진, 연결 부품 |
| 신호처리 | W/bit, DSP power, BER vs reach | 벤치마크·스위치 OEM | 디지털/아날로그·광 부품 수혜 변화 |
| 방식 전환 | CPO vs pluggable, 회수·수리·냉각 비용 | 독립적 customer architecture | 부품 수량/지리적 분포 재편 |

### 경로와 트리거
`1.6T speed requirement -> 광정렬 손실/열 -> interposer/조립 공정 -> POET`
- 회사 기술 적합성까지는 설명할 수 있다. 실제 고객 채택 수준은 미확인.
- 트리거: IEEE 공식 규격 변경; 고객의 1.6T 정식 qualification; 생산 라인/패키징 수율; 명시적 volume supply agreement; DSP W/Tbps 개선; CPO 도입에 따른 pluggable 감소.
- 반증: 차세대 CPO 채택이 광모듈 비즈니스의 BOM·마진 구조를 바꾼다. POET이 양쪽 로드맵에 투자한다는 홍보를 실제 성공으로 오해하지 않는다.

### 우선 원천
- IEEE P802.3dj: https://standards.ieee.org/ieee/802.3dj/11115/
- IEEE P802.3dv: https://standards.ieee.org/ieee/802.3dv/12772/
- POET + Lessengers: https://www.poet-technologies.com/news/poet-technologies-and-lessengers-expand-partnership-to-deliver-1-6t-2xdr4-optical-transceivers-for-ai-network-connectivity

## C. AI 데이터센터 800VDC · 전력변환 · 고신뢰 장비

### 표준 변화
- OCP에서 Google, Microsoft, NVIDIA 등을 포함한 기업들이 800VDC 차세대 인터페이스를 협업 중이라고 밝혔다 (2026년). 이는 전체 데이터센터가 즉시 교체된다는 뜻이 아니라 업계 공통의 **기술 요구·레퍼런스 아키텍처**에 관한 근거.
- OCP Power Distribution의 LVDC White Paper는 2026년 3월 v1.0, 9월 v1.1.0이 공개됐다.
- 단기에는 480VAC를 Power Sidecar에서 ±400/800VDC로 변환하는 구성이, 장기에는 MVAC→800VDC 직접 전환 구조가 모두 고려된다. 어느 방식이 더 유리한지는 기존 건물 전력 인입/공간/비용·안전에 따라 달라진다.

### 수요가 생기는 기술
| 위치 | 모니터링 물리량 | 공급망 기회 후보 | 주요 반증 |
|---|---|---|---|
| Medium-voltage 접속 | 변압/정류 손실, MW/rack group | Transformer Rectifier, Solid State Transformer | 설치·유지보수비, 인증 장애 |
| Rack 전력 변환 | power density W/cm3, 효율 vs 부하 %, 역률 | GaN/SiC 디바이스, DC/DC·콘버터 | 실사용 스위칭/보호 요구와 부품 불일치 |
| Busbar/Connector | 800V 안전 규격, 온도 상승, arc safety, 전류 정격 | 커넥터·절연·스위치/퓨즈 | 통합 모듈이 분리 부품을 대체 |
| 대형 서버 냉각 | 냉각 유량 L/min, CDU ∆T, 압력 손실 | Cold plate, CDU, 펌프·필터 | 밀도 증가가 판매 수량에 그대로 반영되지 않음 |
| SiC 신뢰성 공정 | 불량율, burn-in 시간, 검사 적용 단계 | Wafer-level burn-in 장비 | 실제 800V 변환 설계에 SiC 사용 미확인 |

### 경로와 트리거
`AI rack density up -> higher current/copper burden -> 800VDC distribution -> conversion/busbar/protection technologies -> eligible component suppliers`
- 현 단계에서는 800V 요구→특정 SiC 장비 업체 `AEHR`의 연결을 반드시 **조건부/미검증**으로 표시. 특정 Power System BoM·수주·장비용량 등의 원천 증거 없이 기대 수익을 계산하지 않는다.
- 트리거: 공식 OCP reference revision; 실가동 고객의 800V site commissioning; equipment-level qualification; 부품 공급사/제조사 공개; 장기 공급계약; 800V 보급이 legacy AC/48V 부품 수요에 미치는 역효과.

### 원천
- OCP LVDC: https://www.opencompute.org/projects/data-center-facility/power-distribution/
- OCP 공동 표준화: https://www.opencompute.org/news/powering-the-next-era-of-ai-how-google-microsoft-and-nvidia-are-standardizing-and-accelerating-the-industry-transition-to-lvdc/
- ASHRAE 전력·냉각 통합: https://www.ashrae.org/technical-resources/topics-and-initiatives/ai-data-center/integrated-design-principles

## D. 세 분야 연결: 같은 AI 수요, 서로 다른 인과/타이밍
1. AI 모델 컴퓨팅 용량 증가가 HBM 접합·검사, 광통신 링크 및 데이터센터 전력 분야 각각 요구 조건을 강화할 **수는 있다**.
2. 그러나 **기술계층마다 제품/기업 연결과 고객 투자·양산 타이밍이 다르다**. GPU/HBM 출하량, 스위치 광포트 수, 데이터센터 전력 투자 모두 같은 배수로 늘어난다고 가정하지 않는다.
3. 상관/동일 매크로 요인 vs 독립된 기술 해소 이벤트를 구분한다. 같은 고객의 IR 여러 장을 독립 증거 3개로 세지 않는다.
4. 회사가 특정 기술을 제공한다는 확인과, 고객 양산 시스템에 실제 쓰인다는 확인은 엄격히 분리. 최종 수혜 판단은 **매출 노출·수량·단가·마진·점유율**로 이어질 때만 가능하다.

## E. MVP 탐색 UX (정보 과잉 방지)
- 왼쪽: 생태계와 기술 계층 필터, 아직 해결되지 않은 3대 병목
- 중앙: node graph, 경로의 방향/관계 유형, 확인 상태(사실·주장·가설), 단계별 날짜
- 오른쪽: 선택한 관계의 근거 원문/기술 수치/비교조건/반례/원문 공개일/AI 분석 메모
- 아래: 이벤트 타임라인 + 지난번 평가 대비 `new/strengthened/weakened/retracted` 변화 + watch status
- 후보기업 페이지: `why this company / why this material or process / what must become true / next independent evidence / contradictory evidence / financial capture`
- **원문 0개인 기술 관계는 그래프를 사실처럼 시각화하지 않는다.**

## F. 앞으로의 실제 데이터 수집 백로그
1. IEEE 회의 슬라이드·revision history / OCP GitHub·white paper 변경 (사양 차분).
2. 기업 기술사양 PDF의 숫자·단위/온도/시험 조건 정규화, 전후 버전 차분.
3. TSMC/DRAM·OSAT/스위치 OEM/전력사업자의 제조·납품·qualification 문서.
4. USPTO 특허 공개일·청구항의 대응기술과 원 논문 시험 조건, 제품별 매칭.
5. 발표를 실제 수익화로 잇는 기업 매출 노출(소재 사용량·웨이퍼 검사 횟수·광포트 사용량·rack MW 등). 자료 없음은 missing으로 기록.
6. 과거 시점 복원용 Wayback/SEC 실제 수신시간 + 실물 자료 hash.

## 재현
```bash
cd pipeline
python -m wsj.ecosystems.impact --as-of 2026-10-26 --out ../research/ecosystems/impact_preview.json
pytest -q tests/test_ecosystem_impact.py
```
