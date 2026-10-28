# 매일 아침 작업 — 수집 실행 · 원문 확인 · 병목 관측치 · 투자 아이디어 작성 · 판단 갱신

Claude 예약작업 "WSJ 수집 실행 + 투자 아이디어 작성 (06:41)"이 월~토 06:41 KST 에 이 문서를 그대로 따른다 (ADR-0016 개정 2, ADR-0017).
사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다. 이 문서를 바꾸려면 사람이 승인한 PR 이어야 한다 (개선 예약작업은 고치지 않는다).

## 0. 날짜와 전제
- `date` 로 KST(UTC+9) 오늘 날짜를 구한다. 일요일이면 "일요일" 한 줄로 끝낸다.
- Supabase MCP execute_sql (project_id: dcatgfivsvbktylmtvgf):
  `select to_regprocedure('ideas.put_ideas(jsonb)') is not null as p20, to_regprocedure('ideas.put_assessments(jsonb)') is not null as p21;`
  - p20 이 false 면 "0020 미적용"으로 알리고 끝낸다.
  - p21 이 false 면 "0021 미적용"을 보고에 적고, 아래의 관측치(3-2)·판단 갱신(zz_assessments.sql) 단계는 건너뛴다.
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
- `s2/prompt.system.md` 를 끝까지 읽는다 — 작성 규칙(근거 세 층, ★ 와 10점 근거 점수, 노출 순도, 날짜 있는 확인 일정, 채점, states·leads·prices 사용법).
- `s2/prompt.payload.json` 을 Read 로 2,000줄씩 끝까지 읽는다.
- `s2/raw.json` 에 `{"model": "claude-opus-5-5", "ideas": [...], "grades": [...]}` 를 쓴다.
  - 기존 아이디어는 빠짐없이 update / weaken / keep / close 중 하나.
  - 주 기업 자신의 새 사실이 없으면 '강화'하지 않는다.
  - 노출 순도(exposure)는 부문 매출을 근거로 계산할 수 있을 때만, 근거 id 와 함께.
  - watch 는 날짜(due)·기준(metric·threshold)·방향(direction)이 있는 확인 일정 2~3개.
  - existing 의 watch 중 기한이 지났거나 결과가 나온 항목을 grades 로 채점한다 (hit·miss 는 근거 id 필수).
  - leads 의 company_leads·uncovered 공급사는 원문 확인(3-1)으로 근거가 생겼을 때만 새 아이디어로.
  - 숫자·날짜는 payload 에 있는 것만. 주가·목표가·매수/매도 권유·시점 예측 금지.

## 5. 검증
`.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s2 --from-llm-json ../.ideas_run/s2/raw.json --method session --model claude-opus-5-5 --out ../.ideas_run/s2/rows.json --emit-sql ../.ideas_run/s2/sql`
- `rejected:` 줄을 보고 raw.json 을 고쳐 다시 돌린다 (최대 2번).

## 6. 저장
- `s2/sql/` 의 파일을 이름순으로 Read 해서 그대로 execute_sql 로 실행한다 (마지막 zz_assessments.sql 은 손대지 않은 아이디어의 점수·확인 일정 채점 갱신; p21 이 false 면 건너뛴다). SQL 을 손으로 고치지 않는다.
- DB 쓰기는 ideas.put_company_events · ideas.put_observations · ideas.put_ideas · ideas.put_assessments 네 함수뿐이다. 저장소는 수정·커밋하지 않는다. GitHub 에서는 issues 워크플로 실행만 한다.

## 7. 보고와 알림
6줄 이내: 수집 상태(가격 포함) · 확인한 소식 N건 · 관측치 N개 · 아이디어 new/update/weaken/close/keep 와 바뀐 아이디어(★, 근거 점수) · 채점 결과(적중·빗나감) · 버린 것.
알림은 다음일 때만: 0020 미적용, 수집 미완료로 아이디어를 못 썼을 때, DB 쓰기 실패, 새 ★3 또는 ★3 으로 오른 아이디어(제목·근거 점수·thesis 한 줄), ★3 아이디어의 확인 일정이 빗나갔을 때.
