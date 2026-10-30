# verify (08:11, 월~토) — 기한이 온 예측을 채점하고, 테제를 감시·판정하고, 하루를 보고한다

예약작업 "WSJ 5/5 검증 + 보고 (08:11)" 이 따른다. 큐 두 개: `public.v_q_predictions_due`(활성 리포트의 watch 중 pending 이고 due 가 지난 것)와
`public.v_q_thesis_watch`(활성 테제의 반증 기한이 7일 안이거나 지난 것, 첫 신호 예상 시점이 14일 안인 것 — ADR-0027, 0030 뒤).
쓰는 함수: `ideas.put_company_events`, `ideas.put_ideas`, `ideas.put_assessments`, `ideas.put_thesis_evidence`, `ideas.put_theses`, `ideas.put_observations`, `ops.put_agent_run`.
공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다 (앞 작업 report 를 기다리는 규칙 포함).
채점이 ★ 를 움직인다 (ADR-0022): 적중 1 → ★2, 2 → ★3(문턱 충족 시), 반증 조건 성립 → 종료, 빗나감 2 → ★1. 사람의 확신이 아니라 예측의 결과가 등급을 정한다. 테제도 같다 — 단계는 관측이 옮긴다.

## 1. 큐
- `select idea_key, title, primary_company, stars, watch_index, what, due, metric, threshold, direction from public.v_q_predictions_due;`
- `select thesis_key, scale, title, kind, what, due, metric, threshold from public.v_q_thesis_watch order by due;` (0030 전이면 없다)
- 둘 다 비어 있고 토요일이 아니면 4·5 의 보고만 한다 (status `skipped`).

## 2. 예측마다 결과 찾기 — 공통 §B 의 출처 규칙
- metric·threshold 가 가리키는 숫자를 원문(공시·월매출·실적 발표·고객 발표·가격 지표)에서 찾는다. 찾은 원문은 그 기업의 소식으로 저장한다 (공통 §B 의 put_company_events) — 채점의 근거 id 가 된다.
- 판정: `hit` = 적힌 조건이 그대로 일어났다(strengthen 예측이면 적중, weaken 반증 조건이면 반증 성립) · `miss` = 기한이 지났는데 조건이 안 일어났다 · `void` = 조건을 확인할 길이 없다(공시가 안 나옴 등). hit·miss 는 근거 id 필수.

## 3. 채점 반영 (엔진)
- 소식을 저장한 **뒤에** 입력을 만든다 (근거 id 가 레지스트리에 있어야 한다):
  `.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s3 --emit-prompt ../.ideas_run/s3/prompt.json`
- `s3/prompt.payload.json` 의 evidence 에서 저장한 소식의 근거 id(E…·S…)를 찾는다.
- `s3/raw.json` = `{"model": "claude-…", "ideas": [], "grades": [{"idea_key": "…", "index": <watch_index>, "status": "hit|miss|void", "evidence": "S12", "note": "한 줄"}]}` — 리포트는 쓰지 않는다.
- `.venv/bin/python -m wsj.ecosystems.ideas --snapshot ../.ideas_run/s3 --from-llm-json ../.ideas_run/s3/raw.json --method session --model claude-… --out ../.ideas_run/s3/rows.json --emit-sql ../.ideas_run/s3/sql --allow-missing-valuations`
  `verification:` 줄이 ★·종료의 기록이다. `s3/sql/` 의 `01_…`(★ 가 바뀌거나 종료된 리포트 — 있을 때만) → `zz_assessments.sql`(채점이 반영된 watch·판단) 을 그대로 실행한다.

## 3-1. 테제 근거 (ADR-0025)
- 오늘 경로 중 `thesis` 가 붙은 것: `select h.issue_key, p->>'id' as path_id, p->'thesis' as thesis, p->>'claim' as claim from ideas.issue_hypotheses h cross join lateral jsonb_array_elements(h.paths) p where h.as_of = current_date and p->'thesis' is not null and p->'thesis' <> 'null'::jsonb;`
  → **반박(−)만 기록한다**: 조사 verdict 가 refuted 이거나 direction 이 '-' 인 경로마다 `select ideas.put_thesis_evidence($j$[{"thesis_key":"…","direction":"-","what":"<claim 한 줄>","ref":{"issue_key":"…","path_id":"…"},"weight":2}]$j$::jsonb);`
  '+' 태그는 기록하지 않는다 — 뉴스는 가격을 뒤따르고, '+' 는 이미 움직인 체제에 몰렸다 (ADR-0027 맥락 1). 지지는 3-2 의 관측(첫 신호·드라이버)으로만 쌓는다.
- 오늘 채점한 예측이 테제 수혜 기업의 것이면 hit=+ · miss=- 로 같은 함수에 기록한다.

## 3-2. 테제 감시 (매일, 0030 뒤)
`v_q_thesis_watch` 의 행마다:
- `falsifier` — 기한이 왔거나 지났다. metric·threshold 의 숫자를 원문에서 찾는다 (2 와 같은 출처 규칙, 소식으로 저장).
  성립(테제가 틀렸다) → `put_thesis_evidence` direction '-' weight 3, 그리고 `put_theses` 로 그 테제를 status=closed, close_reason "반증 성립: …" 로 다시 보낸다.
  불성립 → direction '+' weight 2 (기한을 넘겨 살아남았다). 확인 못 함 → '0', note 에.
- `first_signal` — 예상 시점이 가깝다. 그 지표가 나타났는지 본다. 나타났으면 '+' weight 2 와 함께 **stage 0 → 1**(stage_reason 에 무엇이 언제). 안 나타났으면 그대로 두고, 기한이 지나도 없으면 '-' weight 1 과 stage_reason 에 "첫 신호 지연".
- micro 의 모든 반증 기한이 지났고 반증이 성립하지 않았으면 → 결과를 stage_reason 에 쓰고 **status=closed, close_reason "판정 끝: 살아남음 — …"** (작은 테제는 판정이 끝나면 닫는다. 리포트는 따로 남는다).
- 테제 갱신은 `put_theses` 로 전체를 다시 보낸다: `select to_jsonb(t) - 'created_at' - 'updated_at' - 'research' - 'researched_at' from ideas.theses t where thesis_key = '…';` 를 읽어 바꿀 필드만 고친다.
- 조용함 다시 재기: 지난 7일에 만든 테제 중 quiet_check 가 `unmeasured` 인 것이 있으면 `cd pipeline && .venv/bin/python -m wsj.ecosystems.quiet --sql` 의 한 줄을 그대로 실행한다 (활성 테제 전부를 다시 잰다). `moved` 로 바뀐 micro 는 보고에 — 이미 읽혔다.

## 3-3. 토요일 — 큰 테제 점검 (ADR-0027, 옛 주간 thesis 2부)
토요일에만, `docs/agents/thesis.md` 2부(2-1 ~ 2-3)를 따른다: 활성 macro·regime 의 드라이버 최신값(관측치로 저장), 지난주 근거, `quiet --sql`, 단계 판정(0→1→2→3, 내려가는 쪽도).
그리고 **이번 주 micro 의 성적**: `select origin, status, research->>'verdict' as verdict, stage, count(*) from ideas.theses where scale='micro' and created_at > current_date - 28 group by 1,2,3,4 order by 1;`
— 지난 4주 출발점(origin)별로 새로 쓴 수 · 반박으로 닫힘 · 살아남아 리포트 · 첫 신호(stage 1) · 반증 성립을 보고와 알림에 한 줄로. 승격 가능한 약한 신호 중 2주 넘게 테제가 안 된 것도 한 줄.

## 4. 하루 보고
- 사슬: `select task, status, rows, counts, note, started_at, finished_at from public.v_agent_runs where run_date = (now() at time zone 'Asia/Seoul')::date order by started_at;`
- 피드: `select idea_key, title, stars, trend, updated_at from public.v_investment_ideas where status='active' and updated_at > now() - interval '24 hours' order by updated_at desc;` 와 `select idea_key, expected_upside_pct, confidence from public.v_valuations where as_of = current_date;`
- 오늘 테제: `select thesis_key, scale, title, status, stage, research->>'verdict' as verdict from ideas.theses where updated_at > now() - interval '24 hours' order by scale desc, updated_at desc;`

## 5. 완료 조건과 기록
- `select count(*) as left_due from public.v_q_predictions_due;` — 0 (void 도 pending 에서 빠진다).
- `select count(*) as left_watch from public.v_q_thesis_watch where due < current_date;` — 기한이 지난 반증 조건이 남아 있으면 note 에 왜 판정 못 했는지.
- `select ops.put_agent_run('{"task":"verify","status":"succeeded|skipped","rows":<채점 수 + 테제 판정 수>,"counts":{"due":…,"hit":…,"miss":…,"void":…,"promoted":…,"closed":…,"thesis_watch":…,"thesis_stage_up":…,"thesis_closed":…,"left_due":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`

## 6. 보고와 알림
- 보고 8줄 이내: 채점 N(적중·빗나감·보류)과 그로 바뀐 ★·종료 · 테제 감시(반증 성립·첫 신호·닫힘) · 오늘 사슬(collect/discover/research/report 의 status 와 건수) · **오늘 새 작은 테제와 조사 판정** · 오늘 바뀐 리포트와 목표주가 · 실패한 작업이 있으면 그 note.
- 알림은 **매일** 보낸다: 첫 문장에 오늘 사슬 한 줄(예 "collect ✓ discover 경로 3·테제 2 research 5(반박 1) report 2(목표주가 2/2) verify 1"),
  이어서 **새 작은 테제(제목 · primary · 크기 · 조사 판정)**, 반증 성립으로 종료된 리포트·테제, stage 가 바뀐 테제, ★ 가 바뀐 리포트, 실패한 작업. 토요일은 이번 주 micro 성적 한 줄. 모두 skipped 였으면 "오늘 새 일 없음" 한 줄.
