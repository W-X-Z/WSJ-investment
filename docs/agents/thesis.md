# thesis (토요일 09:17) — 약한 신호를 모으고, 구조 가설을 세우고, 드라이버를 재고, 단계를 옮긴다

예약작업 "WSJ 구조 가설 (토 09:17)" 이 따른다 (ADR-0025 → ADR-0026). 리포트가 "이 기업 + 이 이슈" 라면 테제는 "사용 방식의 변화 → 자원 요구 → 공급 병목 → 누가 리레이팅되나" 를 여러 달에 걸쳐 쌓는 단위다. 대형주도 받는다.
공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다 (작업명 `thesis`). 쓰는 함수: `ideas.put_weak_signals`, `ideas.put_theses`, `ideas.put_thesis_evidence`, `ideas.put_observations`, `ideas.put_company_events`, `ops.put_agent_run`.
p29 확인: `select to_regprocedure('ideas.put_weak_signals(jsonb)') is not null as p29;` — false 면 "0029 미적용" 보고·알림 후 끝.

**원칙 (ADR-0026)**: 새 테제는 과거 사례의 다음 판이 아니라 **새 기술·새 데이터·새 이슈** 에서 나온다. 벤치마크는 크기·시차를 보정할 때만 쓴다. 뉴스(`issues` 테이블)는 새 테제의 출발점으로 쓰지 않는다 — 시장이 지금 읽고 있는 것이기 때문이다. 거꾸로 "이미 읽힌 것" 을 걸러내는 데 쓴다. 알아차리는 것(1부)과 이론화하는 것(2부)을 분리한다.

## 1부 — 약한 신호 스캔 (60~90분)
선행 시간이 긴 출처만 훑어 **온톨로지에 없거나 새로 빨라지는 것** 을 관찰로 남긴다. 테제를 쓰려 하지 않는다.

### 1-1. 출처 (매주 전부, 각 10~20분)
| 출처 유형 | source_type | 선행 | 어디를 보나 |
|---|---|---|---|
| 논문 | paper | 24~48개월 | arXiv cs.AR·cs.DC·cs.ET 최근 2주 (`https://export.arxiv.org/api/query?search_query=…&sortBy=submittedDate`): 추론 서빙 메모리·KV 캐시·CXL·PIM·플래시 계층, 광 스케일업, 800V·SST·전력 평활, 2상 냉각 |
| 표준·컨소시엄 | standard | 12~36개월 | OCP contributions, OIF, UEC, UALink, JEDEC, CXL, PCI-SIG, IEEE 802.3 — 새 work item·스펙 발표 |
| 학회 프로그램 | conference | 12~24개월 | Hot Chips·OCP Summit·SC·ISSCC·IEDM·ECTC·OFC·ECOC·APEC·VLSI 의 프로그램/하이라이트 — 처음 나온 세션, 갑자기 늘어난 주제 |
| 채용 | hiring | 6~18개월 | 하이퍼스케일러·모델사·NVIDIA 의 인프라 채용 공고 — 직무명에 박힌 기술 용어 |
| 플랫폼 릴리스 | platform_release | 3~12개월 | vLLM·SGLang·Dynamo·TensorRT-LLM·Mooncake·LMCache 릴리스 노트의 하드웨어 기능 (오프로드 계층·분리 서빙·정밀도·전송) |
| 모델·API 변경 | model_release | 3~12개월 | 컨텍스트 길이·캐시 가격비·출력 토큰 한도·에이전트 제품 — 요청당 하드웨어 강도를 바꾸는 숫자 |
| 공시·컨콜 | filing | 0~6개월 | 하이퍼스케일러 capex, 메모리·패키징·광·전력사의 신제품 범주·공급계약 |

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
같은 `signal_key` 는 횟수·출처·출처 유형이 누적된다. 원자료(목록·초록·세션 덤프)는 `research/weak_signals/raw/YYYYMMDD/` 에 남긴다. **WebFetch 가 거부한 URL 은 다른 수단(curl 등)으로 우회하지 않는다 — 건너뛰고 note 에 적는다.** 지난주에 본 것을 다시 봤으면 다시 넣는다 (재등장이 신호다). 주당 10~30개.
- **승격**: `select * from public.v_weak_signals where status='watch' and promotable;` — 출처 유형 둘 이상 또는 3주 안 재등장. 승격된 것은 2부의 테제 후보가 되거나(`status=promoted, promoted_to=<thesis_key>`), 온톨로지 패치 후보가 된다(`promoted_to=<node id>`; 주간 개선 작업에 넘긴다).
- 두 달 넘게 혼자인 것은 `dropped`.

## 2부 — 테제 (60분)

### 2-1. 읽기
- 활성 테제: `select thesis_key, kind, title, stage, stage_reason, novelty, drivers, falsifiers, n_support, n_against, last_evidence_at from public.v_theses where status='active' order by kind, stage desc;` — `kind=thesis` 가 발굴 대상, `kind=regime` 은 체제 기록(맥락).
- 지난 7일 근거: `select thesis_key, as_of, direction, what, ref from public.v_thesis_evidence where as_of > current_date - 7 order by as_of;`
- 승격된 약한 신호: `select * from public.v_weak_signals where promotable and status='watch';`
- 벤치마크: `research/benchmarks/regime_cases.json` — 크기·시차를 잴 때만.

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

### 2-4. 새 테제 (주 최대 1개, `kind=thesis`)
- 후보는 **1부에서 승격된 약한 신호** 또는 수집기 잔차에서만. 뉴스 제목에서 출발하지 않는다.
- `novelty` 를 정한다: `new_technology`(온톨로지에 없던 기술·부품) · `new_data`(2년 전엔 없던 데이터가 처음 보여주는 것) · `new_issue`(규제·수출통제·관세·사고) · `new_structure`(거래·계약 구조의 변화) · `analog`(과거 사례의 재현 — 이것만으로는 약하다). `novelty_reason` 에 왜 전례가 없는지(또는 어떤 전례의 재현인지).
- `what_market_misses` 한 문장. `lag_months`(벤치마크 또는 추정 + 근거). `first_signal` {metric, where, expected_by} — 첫 공급망 신호가 어디에 언제 나타날지.
- `quiet_check`: 수혜 기업마다 `select * from public.v_price_context where ticker in (…)` 의 r3m·r12m 과 from_high, 그리고 최근 이익 컨센서스 수정(있으면). 이미 움직였으면(12개월 +50% 이상이고 되돌림 없음) 테제가 아니라 `kind=regime` 으로 저장한다. 한국 종목은 v_price_context 에 없으면 `note` 에 "미수집" 이라 적는다.
- **새 테제는 stage 0~1 만** 받는다. 공급 반응이 이미 보이면 `kind=regime`.
- 형식은 `research/theses/memory_inference_rerating_2026.json` 과 같다: statement 80자 이상, chain 3단계 이상(수요 동인 → 요구 → 병목 → 부품 → 기업, 노드 id — 없는 노드는 먼저 온톨로지 패치 후보로), drivers 1개 이상(수치·출처·임계치), beneficiaries(리레이팅 근거 from→to), losers, falsifiers(due 날짜), benchmark(선택).
- `select ideas.put_theses($j$[{…}]$j$::jsonb);` 거부되면 사유대로 고쳐 한 번 더. 저장한 테제는 `research/theses/<key>.json` 에 같은 내용으로, 1부 결과는 `research/weak_signals/YYYYMMDD.md` 에 남기고 PR 로 올린다 (research/ 안만 스스로 병합). 승격된 신호는 `put_weak_signals` 로 `status=promoted, promoted_to` 를 적는다.

## 3. 완료 조건과 기록
- `select kind, count(*), sum(n_support), sum(n_against) from public.v_theses where status='active' group by kind;` 와 이번 주 근거 수, `select count(*) filter (where last_seen = current_date), count(*) filter (where promotable and status='watch') from public.v_weak_signals;`
- `select ops.put_agent_run('{"task":"thesis","status":"succeeded","rows":<근거 수>,"counts":{"theses":…,"regimes":…,"evidence":…,"stage_changes":…,"new":…,"weak_signals":…,"promotable":…},"note":"…"}'::jsonb);`

## 4. 보고와 알림
- 보고 9줄 이내: 약한 신호(새로 본 것·승격 후보) 2줄 · 테제마다 (stage · 드라이버 최신값 · 이번 주 근거 ± · 바뀐 것) · 새 테제 · 닫은 테제.
- 알림은 매주: 첫 문장에 stage 가 바뀐 테제 또는 승격된 약한 신호, 이어서 드라이버가 임계를 넘은 것, 반증이 성립한 것.

## 부록 — 예약작업 프롬프트 (등록용, 토 09:17 KST)
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 주간 thesis(구조 가설) 작업이다 (ADR-0025·0026). 리포트가 "이 기업 + 이 이슈" 라면 테제는 "사용 방식의 변화 → 자원 요구 → 공급 병목 → 누가 리레이팅되나" 를 여러 달에 걸쳐 쌓는 단위다. 새 테제는 과거 사례의 다음 판이 아니라 새 기술·새 데이터·새 이슈에서 나온다 — 1부에서 선행 시간이 긴 출처(논문·표준·학회·채용·플랫폼 릴리스·모델 API·공시)만 훑어 약한 신호를 모으고, 2부에서 승격된 신호로만 테제를 세운다. 뉴스는 출발점이 아니다. 대형주도 받는다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ideas.put_weak_signals(jsonb)') is not null as p29;` — false 면 "0029 미적용" 한 줄로 끝낸다 (알림 없음).
3. add_repo 로 W-X-Z/WSJ-investment 를 push 권한으로 붙이고 안내된 clone 명령으로 `--depth 20` clone 한다. `docs/agents/thesis.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다. 공통 규칙은 `docs/agents/daily-ideas.md` §0·§B·§C. 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계: Supabase 쓰기는 ideas.put_weak_signals, ideas.put_theses, ideas.put_thesis_evidence, ideas.put_observations, ideas.put_company_events, ops.put_agent_run 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 저장소 변경은 research/theses/ 와 research/weak_signals/ 안뿐이며 브랜치 auto/thesis-YYYYMMDD 로 PR 을 올리고 CI 통과 + 바뀐 파일이 전부 research/ 안이면 스스로 병합한다. 그 밖의 경로는 바꾸지 않는다. main 직접 push·강제 push 금지. 근거는 WebFetch 로 직접 연 원문만. 매수/매도 권유·시점 예측은 쓰지 않는다.
5. 커밋 메시지 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>` 를, PR 본문 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)` 를 붙인다.
6. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 알림은 매주: 첫 문장에 stage 가 바뀐 테제 또는 승격된 약한 신호, 이어서 드라이버가 임계를 넘은 것·반증이 성립한 것·새 테제.
```
