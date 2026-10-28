# 매일 아침 작업 — 수집 실행 · 원문 확인 · 병목 관측치 · 투자 아이디어 작성 · 가치평가 · 판단 갱신

Claude 예약작업 "WSJ 수집 실행 + 투자 아이디어 작성 (06:41)"이 월~토 06:41 KST 에 이 문서를 그대로 따른다 (ADR-0016 개정 2, ADR-0017, ADR-0019).
사람이 보는 결과는 **가치평가**(이슈 → 영향 경로 → 기업 숫자 → 시나리오별 내재 주가와 기댓값)다. 근거·선행 점수는 계산기로만 쓰고 화면에 올리지 않는다.
**이 시스템의 일은 좋은 가설을 세우는 것이다** (ADR-0020): 변화가 어떤 경로로 어느 기업의 숫자를 언제 얼마나 바꾸는지 — 시장이 아직 반영하지 않은 것을 — 추론으로 세우고,
날짜 있는 예측(watch)으로 검증하고, 가치평가로 기댓값을 낸다. 근거는 가설을 막는 문이 아니라 시험하는 도구다. ★ 는 확신이 아니라 검증 단계(★1 가설 · ★2 부분 확인 · ★3 확인).
사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다. 이 문서를 바꾸려면 사람이 승인한 PR 이어야 한다 (개선 예약작업은 고치지 않는다).

## 0. 날짜와 전제
- `date` 로 KST(UTC+9) 오늘 날짜를 구한다. 일요일이면 "일요일" 한 줄로 끝낸다.
- Supabase MCP execute_sql (project_id: dcatgfivsvbktylmtvgf):
  `select to_regprocedure('ideas.put_ideas(jsonb)') is not null as p20, to_regprocedure('ideas.put_assessments(jsonb)') is not null as p21, to_regprocedure('ideas.put_idea_notes(jsonb)') is not null as p22, to_regprocedure('ideas.put_valuations(jsonb)') is not null as p23, position('추론' in pg_get_functiondef('ideas.put_ideas(jsonb)'::regprocedure)) > 0 as p24;`
  - p20 이 false 면 "0020 미적용"으로 알리고 끝낸다.
  - p21 이 false 면 "0021 미적용"을 보고에 적고, 아래의 관측치(3-2)·판단 갱신(zz_assessments.sql) 단계는 건너뛴다.
  - p22 가 false 면 "0022 미적용"을 보고에 적고, 심층 분석(6-2)은 건너뛴다.
  - p23 이 false 면 "0024 미적용"을 보고에 적고, 가치평가(4 의 valuation, 6-1 의 zy_valuations.sql)는 건너뛴다.
  - p24 가 false 면 "0025 미적용"을 보고에 적는다 — DB 가 추론 단계를 거부하므로 raw.json 의 추론 단계(근거 없는 "(추론)")를 바로 앞 사실 단계의 claim 끝에 합쳐 넣는다 (추론 자체는 버리지 않는다).
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
`.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s1 --emit-prompt ../.ideas_run/s1/prompt.json --emit-research ../.ideas_run/s1/research.json --leads-out ../.ideas_run/s1/leads.json`

## 3. 원문 확인
### 3-1. 기업 소식 (최대 12건)
- research.json(미확인 ★2+ 소식)에서 ★3, 기존 아이디어의 기업, leads.json 의 company_leads 기업을 먼저 고른다.
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

## 4. 2차 입력과 아이디어 작성
- `.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s2 --emit-prompt ../.ideas_run/s2/prompt.json`
- `s2/prompt.system.md` 를 끝까지 읽는다 — 작성 규칙(근거 세 층, ★, 노출 순도, 날짜 있는 확인 일정, 채점, 선행 추론, **가치평가**, states·leads·prices 사용법).
- `s2/prompt.payload.json` 을 Read 로 2,000줄씩 끝까지 읽는다.
- `s2/raw.json` 에 `{"model": "claude-opus-5-5", "ideas": [...], "grades": [...]}` 를 쓴다.
  - 제목은 30자 안팎의 짧은 한 문장 — 기업명·티커·숫자·괄호·줄표(—) 없이 무엇이 어디로 움직이는지만 (예 "전력망 연결을 못 기다리는 데이터센터는 현장 가스엔진으로"). 피드 카드는 제목·관련 기업·생성일·관련 이슈만 보여 준다.
  - 아이디어 = 가설. 좋은 가설의 조건: 구체적(경로·기업·숫자·시점) · 대담(시장이 아직 반영하지 않은 것) · 반증 가능(틀리면 어느 날짜에 어떤 숫자로 드러나는지) · 설명력.
    chain 의 추론 단계는 근거 없이 "(추론)" 으로 쓴다 (사실 단계 1개 이상). watch 는 가설에서 도출한 예측 2~3개 + 반증 조건 1개(direction=weaken).
    anticipation.effect 는 근거가 없어도 basis 에 논리를 적어 추정한다. ★1 은 결함이 아니다 — 모든 좋은 가설은 ★1 에서 시작한다.
  - 기존 아이디어는 빠짐없이 update / weaken / keep / close 중 하나.
  - 주 기업 자신의 새 사실이 없으면 '강화'하지 않는다.
  - 노출 순도(exposure)는 부문 매출을 근거로 계산할 수 있을 때만, 근거 id 와 함께.
  - watch 는 날짜(due)·기준(metric·threshold)·방향(direction)이 있는 확인 일정 2~3개.
  - existing 의 watch 중 기한이 지났거나 결과가 나온 항목을 grades 로 채점한다 (hit·miss 는 근거 id 필수).
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
    keep 인 기존 아이디어도 valuation 을 쓴다 — existing.valuation 이 없으면 반드시(첫날은 전부), 있으면 그 뒤 주가가 ±15% 넘게 움직였거나 새 근거가 매출·마진 가정을 바꿀 때.
  - 숫자·날짜는 payload 에 있는 것만. 매수/매도 권유·시점 예측 금지. 주가 판단은 valuation 의 시나리오로만 — "목표가"·"매수" 같은 말은 쓰지 않는다 (모형 산출이지 권유가 아니다).

## 5. 검증
`.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s2 --from-llm-json ../.ideas_run/s2/raw.json --method session --model claude-opus-5-5 --out ../.ideas_run/s2/rows.json --emit-sql ../.ideas_run/s2/sql`
- `rejected:` 줄을 보고 raw.json 을 고쳐 다시 돌린다 (최대 2번). `valuation rejected:` 는 아이디어는 받되 가치평가만 거부된 것 — 사유(확률 합·가정 부족·verdict 길이·주식수 없음)대로 고친다.
- 6-1 에서 DB 가 `근거 없는 단계` 로 거부하면 0025 미적용이다 — 위 p24 규칙대로 추론 단계를 합쳐 다시 만든다.
  `valuation skipped:` 는 주가가 없어 평가를 안 쓴 아이디어 — 보고에 적는다.

## 6. 저장
### 6-1. 아이디어
- `s2/sql/` 의 파일을 이름순으로 Read 해서 그대로 execute_sql 로 실행한다: `01_…`(아이디어) → `zy_valuations.sql`(가치평가 — p23 이 false 면 건너뛴다; 결과의 rejected 가 있으면 raw.json 의 그 valuation 을 고쳐 5 부터 다시) → `zz_assessments.sql`(손대지 않은 아이디어의 점수·확인 일정 채점 갱신; p21 이 false 면 건너뛴다). SQL 을 손으로 고치지 않는다.

### 6-2. 심층 분석 메모 (p22 일 때만, 하루 최대 2건)
- 대상: 이번 실행에서 **새로 ★3 이 됐거나 기대 상승여력(valuation.expected_upside_pct)이 +50% 이상이면서 시총 $3B 이하인 아이디어**, 그리고 30일 넘게 메모가 없는 ★3 (`select idea_key, updated_at from public.v_idea_notes;` 로 확인). 기대 상승여력 높은 것부터 2건.
- `docs/agents/deep-dive.md` 를 끝까지 읽고 그 문단 구성·규칙대로 쓴다. 원문을 WebFetch 로 직접 열어 숫자를 확인하고, 회사·기관·표준·정부 출처를 섞는다.
- `select ideas.put_idea_notes($j$[…]$j$::jsonb);` 로 저장. 거부되면 사유대로 고쳐 한 번 더.

- DB 쓰기는 ideas.put_company_events · ideas.put_observations · ideas.put_ideas · ideas.put_valuations · ideas.put_assessments · ideas.put_idea_notes 여섯 함수뿐이다. 저장소는 수정·커밋하지 않는다. GitHub 에서는 issues 워크플로 실행만 한다.

## 7. 보고와 알림
7줄 이내: 수집 상태(가격·시총·재무 포함) · 확인한 소식 N건 · 관측치 N개 · 아이디어 new/update/weaken/close/keep · **가치평가 N건**과 바뀐 아이디어(제목 · 현재 → 기대 주가 · 기대 상승여력 · 확신 · 시총; 점수는 적지 않는다) · 평가 못 쓴 아이디어(skipped·rejected 사유) · 선행 단서 중 경로 확인/미확인 · 채점 결과(적중·빗나감) · 심층 메모 N건 · 버린 것.
알림은 다음일 때만: 0020 미적용, 수집 미완료로 아이디어를 못 썼을 때, DB 쓰기 실패, **기대 상승여력 +50% 이상이고 확신 mid 이상이며 시총 $3B 이하인 새 가치평가**(제목·현재 → 기대 주가·여력·확신·verdict 첫 문장), 기존 평가의 기대 상승여력이 ±30%p 넘게 바뀐 아이디어, ★3 아이디어의 확인 일정이 빗나갔을 때.
