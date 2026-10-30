# thesis — 테제 절차서 (참고서)

> **ADR-0028(2026-10-30) 이후 매일 사슬은 이 문서를 쓰지 않는다.** 해석 지침은 `research/playbook/`, 작성 규칙은 `docs/agents/writing.md`. 아래 1부의 출처 목록은 2단계 출처 수집기(`research/sources/`)로 옮겨 간다. 큰 테제(ideas.theses)는 해석의 배경 자료로만 남는다.

주간 thesis 예약작업은 없다. 이 문서는 매일 사슬이 따르는 테제 절차의 기준이다 (ADR-0025 → 0026 → 0027):
- **1부 약한 신호** → discover §B 가 요일별 출처로 매일 (토요일은 전 유형 + 1-1′ 계수표).
- **2부 2-1 ~ 2-3 큰 테제 점검**(드라이버·근거·조용함·단계) → 토요일 verify §3-3.
- **2부 2-4 새 테제** → 작은 테제(micro)는 discover §C 가 매일 최대 3개, 큰 테제(macro)는 토요일 discover §C 에서 주 1개까지.
리포트가 "이 기업 + 이 이슈" 라면 테제는 "사용 방식의 변화 → 자원 요구 → 공급 병목 → 누가 리레이팅되나" 다. macro 는 여러 달에 걸쳐 쌓고 대형주도 받는다; micro 는 한 기업의 한 제품·고객·계약을 6개월 안에 판정한다.
쓰는 함수(작업 문서가 나눠 쓴다): `ideas.put_weak_signals`, `ideas.put_theses`, `ideas.put_thesis_evidence`, `ideas.put_thesis_research`, `ideas.put_observations`, `ideas.put_company_events`.

**원칙 (ADR-0026)**: 새 테제는 과거 사례의 다음 판이 아니라 **새 기술·새 데이터·새 이슈** 에서 나온다. 벤치마크는 크기·시차를 보정할 때만 쓴다. 뉴스(`issues` 테이블)는 **macro** 의 출발점으로 쓰지 않는다 — 시장이 지금 읽고 있는 것이기 때문이다.
**micro 는 예외가 하나 있다** (ADR-0027): 뉴스가 이름을 부르지 않은 2단계 아래 소·중형 공급사가 primary 이면 뉴스에서 출발해도 된다 — 시장이 읽는 것은 헤드라인 기업이다. 알아차리는 것(1부)과 이론화하는 것(2부)을 분리한다.

## 1부 — 약한 신호 스캔 (discover §B, 하루 한 유형 15~20분)
선행 시간이 긴 출처만 훑어 **온톨로지에 없거나 새로 빨라지는 것** 을 관찰로 남긴다. 테제를 쓰려 하지 않는다.

### 1-1. 출처 (요일별로 하나씩 — discover §B 의 표; 토요일은 전부 가볍게)
| 출처 유형 | source_type | 선행 | 어디를 보나 |
|---|---|---|---|
| 논문 | paper | 24~48개월 | arXiv cs.AR·cs.DC·cs.ET 최근 2주 (`https://export.arxiv.org/api/query?search_query=…&sortBy=submittedDate`): 추론 서빙 메모리·KV 캐시·CXL·PIM·플래시 계층, 광 스케일업, 800V·SST·전력 평활, 2상 냉각 |
| 표준·컨소시엄 | standard | 12~36개월 | OCP contributions, OIF, UEC, UALink, JEDEC, CXL, PCI-SIG, IEEE 802.3 — 새 work item·스펙 발표 |
| 학회 프로그램 | conference | 12~24개월 | Hot Chips·OCP Summit·SC·ISSCC·IEDM·ECTC·OFC·ECOC·APEC·VLSI 의 프로그램/하이라이트 — 처음 나온 세션, 갑자기 늘어난 주제 |
| 채용 | hiring | 6~18개월 | 하이퍼스케일러·모델사·NVIDIA 의 인프라 채용 공고 — 직무명에 박힌 기술 용어 |
| 플랫폼 릴리스 | platform_release | 3~12개월 | vLLM·SGLang·Dynamo·TensorRT-LLM·Mooncake·LMCache 릴리스 노트의 하드웨어 기능 (오프로드 계층·분리 서빙·정밀도·전송) |
| 모델·API 변경 | model_release | 3~12개월 | 컨텍스트 길이·캐시 가격비·출력 토큰 한도·에이전트 제품 — 요청당 하드웨어 강도를 바꾸는 숫자 |
| 공시·컨콜 | filing | 0~6개월 | 하이퍼스케일러 capex, 메모리·패키징·광·전력사의 신제품 범주·공급계약 |

### 1-1′. 계수표 갱신 (`research/coefficients/`)
- 새 프런티어 모델의 토큰당 KV(config 또는 서빙 엔진 원문), 토큰 처리량 발표, API 가격 인상·배급·시간대 가격·인하를 `workload_hardware.json` 에 더한다 (원문을 열었으면 `verified`).
- `cd pipeline && .venv/bin/python -m wsj.ecosystems.coefficients` 의 "순 KV 트래픽 방향" 과 희소성 지수를 보고에 적는다. 메모리 테제의 드라이버다 — 1 아래로 내려가 있으면 반박 근거(weight 2)로 기록한다.

### 1-2. 네 질문
각 후보에 대해: (a) 10배가 되면 무엇이 묶이나 (b) 무엇이 무가치해지나 (c) 가격 결정력이 어디로 옮겨가나 (d) 누가 비용을 떠안나. 답을 `mechanism`·`consumes_more`·`consumes_less` 에 적는다.

### 1-3. 온톨로지 대조
`research/ecosystems/seed_graph.json` 의 노드 id·label·aliases(`node_aliases.json`)와 맞춰 본다. 있으면 `mapped_node`, 없으면 null (= 잔차). 수집기 잔차 `select * from public.v_unmapped_terms where status='open' order by n_seen desc limit 40;` 도 같이 본다 — 거기 있는 용어가 1부 출처에서도 나오면 가장 강한 신호다.

### 1-4. 저장
```sql
select ideas.put_weak_signals($j$[{"signal_key":"hbf","term":"HBF (high-bandwidth flash)","kind_guess":"technology","ecosystem":"hbm",
 "mechanism":"NAND 를 TSV 적층해 HBM 아래 용량 계층 — 컨텍스트·KV 캐시 상주용 (SanDisk·SK hynix)","consumes_more":["NAND TSV","하이브리드 본딩"],"consumes_less":["서버 DRAM 일부"],
 "mapped_node":null,"lead_months":18,"sources":[{"url":"https://…","title":"…","date":"2026-08-25","source_type":"conference"}],"seen_on":"2026-11-01"}]$j$::jsonb);
```
같은 `signal_key` 는 횟수·출처·출처 유형이 누적된다. 원자료(목록·초록·세션 덤프)는 `research/weak_signals/raw/YYYYMMDD/` 에 남긴다. **WebFetch 가 거부한 URL 은 다른 수단(curl 등)으로 우회하지 않는다 — 건너뛰고 note 에 적는다.** 지난주에 본 것을 다시 봤으면 다시 넣는다 (재등장이 신호다). 하루 3~10개.
- **승격**: `select * from public.v_weak_signals where status='watch' and promotable;` — 출처 유형 둘 이상 또는 3주 안 재등장. 승격된 것은 2부의 테제 후보가 되거나(`status=promoted, promoted_to=<thesis_key>`), 온톨로지 패치 후보가 된다(`promoted_to=<node id>`; 주간 개선 작업에 넘긴다).
- 두 달 넘게 혼자인 것은 `dropped`.

## 2부 — 테제 (2-1 ~ 2-3: 토요일 verify · 2-4: discover)

### 2-1. 읽기
- 활성 테제: `select thesis_key, kind, title, stage, stage_reason, novelty, drivers, falsifiers, n_support, n_against, last_evidence_at from public.v_theses where status='active' order by kind, stage desc;` — `kind=thesis` 가 발굴 대상, `kind=regime` 은 체제 기록(맥락).
- 지난 7일 근거: `select thesis_key, as_of, direction, what, ref from public.v_thesis_evidence where as_of > current_date - 7 order by as_of;`
- 승격된 약한 신호: `select * from public.v_weak_signals where promotable and status='watch';`
- 벤치마크: `research/benchmarks/regime_cases.json` — 크기·시차를 잴 때만.

### 2-1′. 조용함 다시 재기
- `cd pipeline && .venv/bin/python -m wsj.ecosystems.quiet --sql` 의 출력 한 줄을 execute_sql 로 실행한다 (활성 테제 전부의 quiet_check 갱신). 판정이 바뀐 테제는 보고에 적는다.

### 2-2. 테제마다 드라이버 갱신 — 출처는 수요가 만들어지는 곳
각 driver 의 최신값을 1부 출처와 메모리 3사·하이퍼스케일러 컨콜, TrendForce 류 데이터에서 찾는다.
- 찾은 값은 관측치로도 저장한다 (공통 §C, nodes 에 demand_driver·bottleneck 노드 id).
- 근거를 기록한다: `select ideas.put_thesis_evidence($j$[{"thesis_key":"…","direction":"+|-|0","what":"한 줄 (숫자·날짜)","ref":{"url":"https://…","indicator_id":"obs:…"},"weight":1}]$j$::jsonb);`
- falsifier 의 due 가 지났으면 결과를 적고(direction -, weight 3) 성립이면 status=closed.
- `first_signal.expected_by` 가 지났으면 그 지표가 나타났는지 적는다 — 안 나타났으면 stage_reason 에 쓰고 lag 를 다시 잰다.

### 2-3. 단계 판정
- stage 0 가설 → 1: 드라이버 중 둘 이상이 임계 방향으로 움직임 (수치 근거).
- 1 → 2: 공급 반응이 보임 — 증설·할당·가격(계약가·리드타임) 중 둘 이상이 원문으로 확인.
- 2 → 3: 시장이 반영 — 수혜 기업의 배수가 사이클 밴드를 벗어남. 3 은 '맞았다' 지 '사라' 가 아니다. 이때 하류(2차 파동)의 새 테제 후보를 적는다.
- 내려가는 쪽도 같은 규칙. 갱신은 `put_theses` 로 전체를 다시 보낸다 (ADR-0026 항목은 빠뜨려도 지워지지 않는다).

### 2-4. 새 테제 (`kind=thesis` — macro 는 토요일 주 1개, micro 는 매일 ≤3: discover §C 의 형식이 더 붙는다)
- macro 후보는 **1부에서 승격된 약한 신호** 또는 수집기 잔차에서만. 뉴스 제목에서 출발하지 않는다. micro 후보의 출발점은 discover §C-1.
- `novelty` 를 정한다: `new_technology`(온톨로지에 없던 기술·부품) · `new_data`(2년 전엔 없던 데이터가 처음 보여주는 것) · `new_issue`(규제·수출통제·관세·사고) · `new_structure`(거래·계약 구조의 변화) · `analog`(과거 사례의 재현 — 이것만으로는 약하다). `novelty_reason` 에 왜 전례가 없는지(또는 어떤 전례의 재현인지).
- `what_market_misses` 한 문장. `lag_months`(벤치마크 또는 추정 + 근거). `first_signal` {metric, where, expected_by} — 첫 공급망 신호가 어디에 언제 나타날지.
- `quiet_check`: `cd pipeline && .venv/bin/python -m wsj.ecosystems.quiet --companies company:a,company:b` 로 잰다 (그래프 listing → v_price_context, 우주 중앙값 포함). 판정: `moved`(12개월 +100%↑ 또는 +50%↑·고점 −20% 안) → 테제가 아니라 `kind=regime` · `moved_reset`(+50%↑ 후 고점 −35% 이하 — 시장이 반영했다가 되돌림) → 테제로 둘 수 있지만 what_market_misses 를 "재평가가 지속되나/2차 파동" 으로 좁히고 stage_reason 에 적는다 · `sold_off`(고점 −50% 이하 — 시장이 보고 버린 것) → 왜 버렸는지를 반증 후보로 먼저 적는다 · `quiet` · `mixed` · `unmeasured`(가격 미수집 — note 그대로). 우주 중앙값이 고점 −40% 같은 때는 절대 판정만 읽지 않는다. 기존 테제 전부는 `--sql` 이 내는 한 줄(`put_theses` 로 quiet_check 만 갈아 끼움)을 그대로 실행한다.
- `rerating`: 수혜 기업마다 `cd pipeline && .venv/bin/python -m wsj.ecosystems.rerating company:a company:b --band memory|substrate|equipment` 로 **시장 내재 지속 마진**(배수 8·12·16 일 때 지금 가격이 영원히 간다고 보는 영업이익률)과 trough·mid·regime 가격, **필요 매출 배수**를 잰다. beneficiaries[].rerating 의 from·to 를 이 숫자로 쓴다 (예: "from: 내재 지속 마진 62% @12배 / to: regime 45%×14배 = 현재가 −15%"). 밴드는 가정이므로 업종 근거가 있으면 덮어쓰고 근거를 적는다. **가격으로 조용해도(quiet) 배수로 비싸면(필요 매출 ×4 이상) 조용한 게 아니다** — 둘 다 보고에 쓴다.
- **하류를 훑는다** (재현 교훈, 2026-10-30): 수혜 기업을 정하기 전에 chain 의 부품 노드에서 그래프 하류(`requires`·`offered_by`)를 두 단계 더 내려가 기판·패키징·장비·소재 병목을 확인한다. 2025-09-30 재현에서 메모리 테제는 맞혔지만 삼성전기 FC-BGA(+1,015%)를 놓쳤다 — 수요측 스캔은 하류 병목을 자연히 보지 않는다.
- **새 테제는 stage 0~1 만** 받는다. 공급 반응이 이미 보이면 `kind=regime`.
- 형식은 `research/theses/memory_inference_rerating_2026.json` 과 같다: statement 80자 이상, chain 3단계 이상(수요 동인 → 요구 → 병목 → 부품 → 기업, 노드 id — 없는 노드는 먼저 온톨로지 패치 후보로), drivers 1개 이상(수치·출처·임계치), beneficiaries(리레이팅 근거 from→to), losers, falsifiers(due 날짜), benchmark(선택).
- `select ideas.put_theses($j$[{…}]$j$::jsonb);` 거부되면 사유대로 고쳐 한 번 더. 저장한 테제는 `research/theses/<key>.json` 에 같은 내용으로, 1부 결과는 `research/weak_signals/YYYYMMDD.md` 에 남기고 discover §D 의 PR 로 올린다. 승격된 신호는 `put_weak_signals` 로 `status=promoted, promoted_to` 를 적는다.

## 3. 기록
- 약한 신호의 하루 결과는 `research/weak_signals/YYYYMMDD.md`, 테제는 `research/theses/<key>.json`, 새 기업은 `research/ecosystems/patches/YYYYMMDD_discover.json` — discover §D 의 PR 로 올린다.
- 실행 기록·보고·알림은 그 일을 한 작업(discover · verify)의 문서를 따른다.
