# (전환기) 매일 아침 한 세션 작업 — 0027 적용 전까지만

ADR-0024 로 아침 일은 다섯 작업(`docs/agents/daily/*.md`)으로 나뉘었다. 이 문서는 **마이그레이션 0027 이 운영 DB 에 적용되기 전까지** 06:41 예약작업이 따르는 옛 절차다.
§0 의 첫 확인에서 0027 이 적용돼 있으면 이 작업은 "분업 전환됨" 한 줄로 끝난다 — 그 뒤로는 다섯 작업이 한다. 형식·규칙의 최신본은 `docs/agents/daily-ideas.md`(공통 규칙)다.

Claude 예약작업 "WSJ 수집 실행 + 투자 아이디어 작성 (06:41)"이 월~토 06:41 KST 에 이 문서를 그대로 따른다 (ADR-0016 개정 2, ADR-0017, ADR-0019).
사람이 보는 결과는 **가치평가**(이슈 → 영향 경로 → 기업 숫자 → 시나리오별 내재 주가와 기댓값)다. 근거·선행 점수는 계산기로만 쓰고 화면에 올리지 않는다.
**이 시스템의 일은 좋은 가설을 세우는 것이다** (ADR-0020): 변화가 어떤 경로로 어느 기업의 숫자를 언제 얼마나 바꾸는지 — 시장이 아직 반영하지 않은 것을 — 추론으로 세우고,
날짜 있는 예측(watch)으로 검증하고, 가치평가로 기댓값을 낸다. 근거는 가설을 막는 문이 아니라 시험하는 도구다. ★ 는 확신이 아니라 검증 단계(★1 가설 · ★2 부분 확인 · ★3 확인).
흐름은 두 단계다 (ADR-0022): 가설 후보를 넓게 연다 → 엔진이 걸러 조사 대상을 정한다 → 조사한다 → 고른 후보만 아이디어로 쓴다 → 예측 채점이 ★ 를 움직인다. 주 기업은 미국·한국 상장사만 (ADR-0021).
사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다. 이 문서를 바꾸려면 사람이 승인한 PR 이어야 한다 (개선 예약작업은 고치지 않는다).

## 0. 날짜와 전제
- `date` 로 KST(UTC+9) 오늘 날짜를 구한다. 일요일이면 "일요일" 한 줄로 끝낸다.
- **전환 확인**: `select to_regprocedure('ops.put_agent_run(jsonb)') is not null as p27;` 가 true 면 "분업 전환됨 — 다섯 작업이 한다 (ADR-0024)" 한 줄로 끝낸다. 알림 없음.
- Supabase MCP execute_sql (project_id: dcatgfivsvbktylmtvgf):
  `select to_regprocedure('ideas.put_ideas(jsonb)') is not null as p20, to_regprocedure('ideas.put_assessments(jsonb)') is not null as p21, to_regprocedure('ideas.put_idea_notes(jsonb)') is not null as p22, to_regprocedure('ideas.put_valuations(jsonb)') is not null as p23, position('추론' in pg_get_functiondef('ideas.put_ideas(jsonb)'::regprocedure)) > 0 as p24, to_regprocedure('ideas.put_issue_hypotheses(jsonb)') is not null as p26;`
  - p20 이 false 면 "0020 미적용"으로 알리고 끝낸다.
  - p21 이 false 면 "0021 미적용"을 보고에 적고, 아래의 관측치(3-2)·판단 갱신(zz_assessments.sql) 단계는 건너뛴다.
  - p22 가 false 면 "0022 미적용"을 보고에 적고, 심층 분석(6-2)은 건너뛴다.
  - p23 이 false 면 "0024 미적용"을 보고에 적고, 가치평가(4 의 valuation, 6-1 의 zy_valuations.sql)는 건너뛴다.
  - p24 가 false 면 "0025 미적용"을 보고에 적는다 — DB 가 추론 단계를 거부하므로 raw.json 의 추론 단계(근거 없는 "(추론)")를 바로 앞 사실 단계의 claim 끝에 합쳐 넣는다 (추론 자체는 버리지 않는다).
  - p26 이 false 면 "0026 미적용"을 보고에 적고, 이슈별 영향 경로 저장(6-1 의 zx_issue_hypotheses.sql)은 건너뛴다 — 가설 후보·선택은 그대로 한다.
- add_repo 로 W-X-Z/WSJ-investment 를 붙이고 `--depth 1` clone. `cd pipeline && python3 -m venv .venv && .venv/bin/pip install -q -e .`
- 작업 폴더는 `../.ideas_run/` (저장소에 커밋하지 않는다).
- Supabase MCP get_project_url · get_publishable_keys 로 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`(sb_publishable_…)를 export 한다. secret 키는 쓰지 않는다.

## 1. 오늘 수집 실행
- `select collector, status, started_at from ops.collector_runs where collector in ('issues','company_feed','prices') and started_at > now() - interval '20 hours' order by started_at desc;`
- 오늘(KST 06:00 이후) issues 와 company_feed 가 succeeded 면 2 로 간다. prices 는 실패해도 진행한다(보고에만 적는다).
- 아니면 `gh api "repos/W-X-Z/WSJ-investment/actions/workflows/issues.yml/runs?per_page=3"` 로 본다. 진행 중이면 기다리고, 없거나 실패했으면
  `gh api -X POST repos/W-X-Z/WSJ-investment/actions/workflows/issues.yml/dispatches -f ref=main` 로 실행시킨다.
- `timeout 590 bash -c 'until <확인>; do sleep 30; done'` 으로 최대 45분 기다린다. 넘으면 쌓인 데이터로 진행하고 "오늘 수집 미완료"를 적는다.

## 2. 1차 입력
`.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s1 --emit-prompt ../.ideas_run/s1/prompt.json --emit-research ../.ideas_run/s1/research.json --leads-out ../.ideas_run/s1/leads.json --emit-hypotheses ../.ideas_run/s1/hypo.json`
(`--emit-hypotheses` 가 있으면 1단계 프롬프트까지 쓰고 끝난다. research.json·leads.json 은 먼저 쓰인다.)

## 2-1. 가설 후보 (1단계, ADR-0022)
아이디어를 바로 쓰지 않는다. 먼저 가설을 넓게 연 뒤 엔진이 걸러 준 것만 조사하고 쓴다.
- `s1/hypo.system.md` 를 읽고 `s1/hypo.payload.json` 을 Read 로 2,000줄씩 끝까지 읽는다 (아이디어 단계와 같은 입력).
- `s1/hypotheses.json` 에 `{"model": "claude-opus-5-5", "issues": [{"trigger": "S12", "change": "…", "paths": [...]}]}` 를 쓴다 — **이슈마다 "이 변화가 업계에 어떤 영향을 주나" 경로 최대 3개**, 전체 8~15개.
  경로 = 변화 근거 id → 그래프 경로 → (있으면) 미국·한국 기업 → 숫자·시점 → 왜 시장이 모르나 → 반증 조건 → 확인할 것. 적당한 미국·한국 기업이 없으면 company 를 null 로 두고 경로만 — 이슈 탭에 '업계 영향'으로 남는다.
  안전한 것만 모으지 말고 대담한 2차·3차 고리를 섞는다. 걸러내는 것은 엔진의 일이다. existing 과 같은 논리면 extends 에 idea_key.
- `.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s1 --from-hypotheses ../.ideas_run/s1/hypotheses.json --hypotheses-out ../.ideas_run/s1/selected.json --emit-research-plan ../.ideas_run/s1/research_plan.json --emit-sql ../.ideas_run/s1/sql`
  - 엔진이 검사(근거 id·노드·시장 범위)하고 채점(구체·대담·반증 가능·설명력 각 3점, 경로 끊김·기업 중복 감점)해 기업이 있는 경로 중 상위 max_ideas 개를 리포트 후보로 고른다(기업당 1개, 생태계마다 1개 이상).
  - `hypothesis rejected:` 가 절반 넘으면 사유대로 hypotheses.json 을 고쳐 한 번 더 돌린다. 고른 후보가 3개 미만이면 후보를 더 써서 다시.
  - research_plan.json = 고른 후보마다 확인할 것(confirm)·반증 조건·경고(flags)·이미 아는 그 기업 소식.
  - `s1/sql/zx_issue_hypotheses.sql` = 이슈별 경로(≤3) 저장문 — 6-1 에서 실행한다 (p26 일 때). 이슈 탭이 이것을 보여 준다.

## 3. 원문 확인
### 3-1. 기업 소식 (최대 12건)
- **가설 조사(research_plan.json)가 먼저다**: 고른 후보마다 confirm 항목을 원문(IR 자료·공시·제품 페이지·고객의 증설 발표)에서 확인한다.
  확인한 사실은 그 기업의 소식으로 저장한다 — research.json 에 같은 기업의 event_id 가 있으면 그 id 로, 없으면 새 event 로
  (`put_company_events` 는 event_id 가 없는 새 행도 받는다 — kind 는 filing|disclosure|revenue|news, 45일 안의 날짜, https 원문:
  `{"company_id":"company:…","kind":"news","published_at":"YYYY-MM-DD","title":"…","url":"https://…","text":"확인한 사실 1~3문장","importance":2}`).
  확인이 안 되면 보고에 "가설 미확인: H번호 회사명 — 무엇을 못 찾았나" 로 남기고, 4단계에서 그 가설은 추론 단계로만 쓴다.
- 그다음 research.json(미확인 ★2+ 소식)에서 ★3, 기존 아이디어의 기업, leads.json 의 company_leads 기업을 고른다.
- **선행 단서(leads.json 의 second_order 상위 5곳)**: 이 기업들은 소식이 없는 게 정상이다(그래서 단서다). 회사 IR·제품 페이지를 WebFetch 로 열어
  경로의 마지막 고리(이 회사가 정말 그 부품·장비를 공급하는지, 매출 비중)를 확인하고, 확인되면 4단계에서 선행 아이디어의 근거로 쓴다
  (그래프 간선 G 근거 + 변화 이슈 I 근거). 확인이 안 되면 보고에 "경로 미확인: 회사명" 으로 남긴다.
- WebFetch 로 원문을 연다(news.google.com 은 원문 주소로). 안 열리면 WebSearch 로 같은 사건의 다른 기사를 찾는다.
- 확인한 사실을 한국어 1~3문장, 400자 이내: 날짜 + 숫자(금액·%·수량·생산능력·가이던스·부문 매출 비중) + 상대방·기간. 원문에서 읽은 것만.
- 그 기업 이야기가 아니거나 시세 기사면 importance 1, "관련 없음: 이유".
- 한 번에: `select ideas.put_company_events($j$[{"event_id":"…","text":"…","importance":2}, …]$j$::jsonb);`
- 쓰지 않는 출처: 자동 생성 시세 요약, 토론방·블로그·카페·유튜브. 네이버 증권·KIND·DART 본문은 막혀 있다 — 같은 내용을 옮긴 기사를 찾는다.

### 3-2. 병목 상태 관측치 (최대 8개, p21 일 때만)
읽은 원문이나 leads.json 의 bottlenecks(활동 많은 병목)에서 **병목이 조여지는지 풀리는지를 보여 주는 숫자**를 찾으면 기록한다:
현물가·계약가 배수나 %, 리드타임(주·개월), 가동률, 재고(주·개월), 수주잔고, 평균단가 변화, 증설 완공 시점과 규모.
- 지표 id 는 `obs:<병목·부품>_<측정>` (예 `obs:fiber_bif_spot_multiple`, `obs:glass_cloth_asp_yoy`, `obs:substrate_equipment_backlog`). 같은 측정은 같은 id 를 계속 쓴다 —
  `select indicator_id, label, unit, as_of, value from public.v_indicators where category='observation' order by indicator_id;` 로 먼저 확인한다.
- nodes 에는 그래프 노드 id 를 넣는다 (`research/ecosystems/seed_graph.json` 에서 찾는다). 원문 날짜를 as_of 로, 숫자 하나를 value 로.
- `select ideas.put_observations($j$[{"indicator_id":"obs:…","label":"…","unit":"…","ecosystem":"optics","nodes":["bottleneck:…"],"source":"TrendForce","source_url":"https://…","as_of":"2026-10-19","value":5,"note":"원문 한 줄","meta":{"quote":"원문 발췌"}}]$j$::jsonb);`
- FRED 지표(구리·알루미늄)가 30일 넘게 비어 있으면 `.venv/bin/python -m wsj.ecosystems.indicators fred-sql --out ../.ideas_run/fred.sql` 후 그 파일을 그대로 실행한다.

## 4. 2차 입력과 아이디어 작성 (2단계)
- `.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s2 --hypotheses ../.ideas_run/s1/selected.json --emit-prompt ../.ideas_run/s2/prompt.json`
  (`--hypotheses` 가 고른 후보를 payload.hypotheses 에 넣는다 — trigger 는 2차 레지스트리의 근거 id 로 다시 맞춰진다.)
- `s2/prompt.system.md` 를 끝까지 읽는다 — 작성 규칙(근거 세 층, ★, 노출 순도, 날짜 있는 확인 일정, 채점, 선행 추론, **가치평가**, hypotheses, states·leads·prices 사용법).
- `s2/prompt.payload.json` 을 Read 로 2,000줄씩 끝까지 읽는다.
- **새 아이디어는 payload.hypotheses 의 후보에서 쓴다** (`"hypothesis": "H3"`). 조사(3-1)로 확인된 것은 근거 id 로, 못 한 것은 "(추론)" 으로. flags(경로 끊김·이미 움직임)는 risks·bear 에.
  extends 가 있는 후보는 그 idea_key 의 update 로. 후보 밖 새 아이디어는 조사에서 새 변화가 드러났을 때만.
- `s2/raw.json` 에 `{"model": "claude-opus-5-5", "ideas": [...], "grades": [...]}` 를 쓴다.
  - 제목은 30자 안팎의 짧은 한 문장 — 기업명·티커·숫자·괄호·줄표(—) 없이 무엇이 어디로 움직이는지만 (예 "전력망 연결을 못 기다리는 데이터센터는 현장 가스엔진으로"). 피드 카드는 제목·관련 기업·생성일·관련 이슈만 보여 준다.
  - 아이디어 = 가설. 좋은 가설의 조건: 구체적(경로·기업·숫자·시점) · 대담(시장이 아직 반영하지 않은 것) · 반증 가능(틀리면 어느 날짜에 어떤 숫자로 드러나는지) · 설명력.
    chain 의 추론 단계는 근거 없이 "(추론)" 으로 쓴다 (사실 단계 1개 이상). watch 는 가설에서 도출한 예측 2~3개 + 반증 조건 1개(direction=weaken).
    anticipation.effect 는 근거가 없어도 basis 에 논리를 적어 추정한다. ★1 은 결함이 아니다 — 모든 좋은 가설은 ★1 에서 시작한다.
  - **시장 범위 (ADR-0021)**: 주 기업(primary)은 미국(NYSE·Nasdaq)·한국(KRX·KOSDAQ) 상장사만 — candidates·leads 는 이미 그 범위이고, 범위 밖 주 기업은 검증기가 거부한다.
    대만·일본·유럽·중국 기업은 변화의 출발점·고객·경쟁·동종(peers 의 '범위 밖' 표시)으로 companies 와 근거에 쓴다. 변화가 그런 기업에서 시작됐으면
    같은 경로의 미국·한국 고리(그 기업의 고객·장비·소재 공급사, 같은 부품의 미국·한국 동종사, 대체·보완 기술의 미국·한국 기업)를 찾고, 없으면 states·leads 로만 남긴다.
    existing 의 scope 가 '범위 밖(…)'인 아이디어는 이번 실행에서 종료된다(keep·weaken 이 자동으로 close) — 그 가설의 미국·한국 고리가 있으면 action=new 로 새로 쓴다.
  - 기존 아이디어는 빠짐없이 update / weaken / keep / close 중 하나.
  - 주 기업 자신의 새 사실이 없으면 '강화'하지 않는다.
  - 노출 순도(exposure)는 부문 매출을 근거로 계산할 수 있을 때만, 근거 id 와 함께.
  - watch 는 날짜(due)·기준(metric·threshold)·방향(direction)이 있는 확인 일정 2~3개.
  - existing 의 watch 중 기한이 지났거나 결과가 나온 항목을 grades 로 채점한다 (hit·miss 는 근거 id 필수). hit = 적힌 조건이 그대로 일어났다
    (strengthen 예측이면 적중, weaken 반증 조건이면 반증 성립). 채점이 ★ 를 움직인다(엔진 자동, ADR-0022): 적중 1 → ★2, 2 → ★3(문턱 충족 시), 반증 성립 → 종료, 빗나감 2 → ★1.
    existing.verification(hits·misses·pending·falsified)을 보고 빗나간 가설은 왜 빗나갔는지 risks 에, 적중한 가설은 다음 예측을 더 구체적으로.
  - leads 의 company_leads·uncovered 공급사는 원문 확인(3-1)으로 근거가 생겼을 때만 새 아이디어로.
  - prices 의 시총(market_cap_usd)·저점 대비(from_low)·tenbagger 판정을 본다: 같은 논리에 **시총이 작고 덜 오른 공급사**가 있으면 그쪽을 primary 로. 저점 대비 3배 이상 오른 기업은 risks 에 "이미 알려진 정도".
  - **아이디어마다 anticipation 을 쓴다** (프롬프트의 '선행 추론' 절): trigger(변화 근거 id) · path(그래프 노드 id, candidates.chains.path_ids 그대로) ·
    mechanism · lead_quarters · effect{pct_of_revenue, basis, evidence} · priced_in. 수주·계약이 이미 나온 기업은 priced_in=full 로 적고,
    같은 논리의 다음 고리(아직 조용한 공급사)가 있으면 그쪽을 primary 로 한 아이디어를 따로 쓴다. 하루에 **선행 아이디어(priced_in=none·partial) 1건 이상**.
  - **아이디어마다 valuation 을 쓴다** (프롬프트의 '가치평가' 절, p23 일 때). 질문은 하나 — 이 변화가 이 기업 숫자를 바꾸면 12개월 뒤 얼마짜리 회사인가:
    시나리오 bear·base·bull(확률 합 1) 각각 매출(현지 통화 원 단위)·마진·배수(ps|pe) → 내재 시총, 가정(사실 kind=fact 근거 id 1개+ · 추정 kind=estimate basis — 변화의 크기·닿는 비율·시점·배수), 깨지는 조건, confidence, verdict 3~5문장.
    **영향 추정은 LLM 의 판단이다** — 변화가 이 기업 매출을 얼마나·언제·어느 확률로 바꾸는지는 입력에 숫자로 없다. 추정은 금지가 아니라 표시다(기존의 '추정 금지'는 사실 칸에만). 계산기는 산수와 형식만 본다.
    existing 은 지난 실행의 판단이지 사실이 아니다 — 오늘 근거로 다시 판단하고, bear 에 "아이디어 자체가 틀렸다"를 넣는다. 기업 자신의 근거가 없는 아이디어는 confidence high 불가.
    재료는 prices[primary] 의 close·currency·shares·fundamentals(TTM 매출·마진·P/S·P/E). fundamentals 가 없으면 원문(IR·실적 발표)에서 읽은 매출·이익을 가정에 근거 id 와 함께 적는다.
    close 가 없으면 valuation_skipped 에 이유. 검증기가 산수(내재 시총 → 주식수로 나눈 주가 → 확률 가중)를 다시 한다 — 너는 가정을 댄다.
    **가격·주식수가 있는 아이디어는 valuation 을 생략할 수 없다.** new·update·weaken 행은 이번에 다시 쓴다(리포트를 고쳐 썼으면 목표주가도 다시). keep 은 existing.valuation 이 있으면 생략 가능, 없으면 쓴다.
    검증기가 누락을 `valuation missing:` 으로 적고 exit 2 로 끝낸다 — 그 아이디어에 valuation 을 채워 5 를 다시 돌린다 (10/29 아침 실행이 새 리포트 4건을 목표주가 없이 쓴 뒤 추가된 규칙).
  - 숫자·날짜는 payload 에 있는 것만. 매수/매도 권유·시점 예측 금지. 주가 판단은 valuation 의 시나리오로만 — "목표가"·"매수" 같은 말은 쓰지 않는다 (모형 산출이지 권유가 아니다).

## 5. 검증
`.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s2 --hypotheses ../.ideas_run/s1/selected.json --from-llm-json ../.ideas_run/s2/raw.json --method session --model claude-opus-5-5 --out ../.ideas_run/s2/rows.json --emit-sql ../.ideas_run/s2/sql`
- 검증 명령에 `--hypotheses ../.ideas_run/s1/selected.json` 을 붙인다 (아이디어에 적은 hypothesis id 가 판단에 기록된다).
- `rejected:` 줄을 보고 raw.json 을 고쳐 다시 돌린다 (최대 2번). `valuation rejected:` 는 아이디어는 받되 가치평가만 거부된 것 — 사유(확률 합·가정 부족·verdict 길이·주식수 없음)대로 고친다.
- `verification:` 줄은 예측 채점이 ★·상태를 움직인 기록이다(적중 → ★ 상향, 반증 성립 → 종료, 빗나감 2건 → ★1) — 보고에 그대로 적는다.
- **exit 2 (`valuation missing`)**: 가격·주식수가 있는데 목표주가가 없는 아이디어 목록이다. raw.json 의 그 아이디어에 valuation 을 채우고 다시 돌린다. 끝까지 못 채우면 `--allow-missing-valuations` 로 넘기되 보고에 "목표주가 누락 N건: 사유"를 적는다.
- 6-1 에서 DB 가 `근거 없는 단계` 로 거부하면 0025 미적용이다 — 위 p24 규칙대로 추론 단계를 합쳐 다시 만든다.
  `valuation skipped:` 는 주가가 없어 평가를 안 쓴 아이디어 — 보고에 적는다.

## 6. 저장
### 6-1. 아이디어
- `s2/sql/` 의 파일을 이름순으로 Read 해서 그대로 execute_sql 로 실행한다: `01_…`(아이디어) → `zy_valuations.sql`(가치평가 — p23 이 false 면 건너뛴다; 결과의 rejected 가 있으면 raw.json 의 그 valuation 을 고쳐 5 부터 다시) → `zz_assessments.sql`(손대지 않은 아이디어의 점수·확인 일정 채점 갱신; p21 이 false 면 건너뛴다). SQL 을 손으로 고치지 않는다.
- zy_valuations.sql 을 실행한 뒤 **확인**: `select count(*) from ideas.valuations where as_of = current_date;` 가 rows.valuations.json 의 건수와 같아야 한다. 적으면 결과의 rejected 사유대로 raw.json 을 고쳐 5 부터 다시 — 목표주가 없이 리포트만 저장하고 끝내지 않는다.
- 그다음 `s1/sql/zx_issue_hypotheses.sql`(이슈별 영향 경로; p26 일 때)을 실행한다. 이슈 탭은 경로의 기업과 그 이슈를 근거로 쓴 리포트를 화면에서 잇는다. rejected 가 있으면(이슈 없음 등) 보고에만 적는다.

### 6-2. 심층 분석 메모 (p22 일 때만, 하루 최대 2건)
- 대상: 이번 실행에서 **새로 ★3 이 됐거나 기대 상승여력(valuation.expected_upside_pct)이 +50% 이상이면서 시총 $3B 이하인 아이디어**, 그리고 30일 넘게 메모가 없는 ★3 (`select idea_key, updated_at from public.v_idea_notes;` 로 확인). 기대 상승여력 높은 것부터 2건.
- `docs/agents/deep-dive.md` 를 끝까지 읽고 그 문단 구성·규칙대로 쓴다. 원문을 WebFetch 로 직접 열어 숫자를 확인하고, 회사·기관·표준·정부 출처를 섞는다.
- `select ideas.put_idea_notes($j$[…]$j$::jsonb);` 로 저장. 거부되면 사유대로 고쳐 한 번 더.

- DB 쓰기는 ideas.put_company_events · ideas.put_observations · ideas.put_ideas · ideas.put_valuations · ideas.put_assessments · ideas.put_idea_notes 여섯 함수뿐이다. 저장소는 수정·커밋하지 않는다. GitHub 에서는 issues 워크플로 실행만 한다.

## 7. 보고와 알림
7줄 이내: 수집 상태(가격·시총·재무 포함) · 가설 후보 N개 중 고른 N개(제목 한 줄씩, 미확인 표시) · 확인한 소식 N건 · 관측치 N개 · 아이디어 new/update/weaken/close/keep · **목표주가 저장 N/M (확인 쿼리 결과)**과 바뀐 아이디어(제목 · 현재 → 기대 주가 · 기대 상승여력 · 확신 · 시총; 점수는 적지 않는다) · 평가 못 쓴 아이디어(skipped·rejected 사유) · 선행 단서 중 경로 확인/미확인 · 채점 결과(적중·빗나감·반증)와 그로 바뀐 ★·종료 · 심층 메모 N건 · 버린 것.
알림은 다음일 때만: 0020 미적용, 수집 미완료로 아이디어를 못 썼을 때, DB 쓰기 실패, **기대 상승여력 +50% 이상이고 확신 mid 이상이며 시총 $3B 이하인 새 가치평가**(제목·현재 → 기대 주가·여력·확신·verdict 첫 문장), 기존 평가의 기대 상승여력이 ±30%p 넘게 바뀐 아이디어, ★3 아이디어의 확인 일정이 빗나갔을 때.
