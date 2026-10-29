# research (06:49, 월~토) — 작은 테제의 가장 약한 고리를 반박 우선으로, 그다음 리포트 후보 경로를 원문으로 조사한다

예약작업 "WSJ 3/5 조사 (06:49)" 이 따른다. 큐 두 개 (ADR-0027):
`public.v_q_theses_needing_research`(조사 결과가 없는 활성 micro 테제, 새것 먼저)와 `public.v_q_paths_needing_research`(최근 7일 경로 중 selected 이고 기업이 있는데 조사 결과가 없는 경로, 점수 순).
쓰는 함수: `ideas.put_company_events`, `ideas.put_observations`, `ideas.put_thesis_research`, `ideas.put_path_research`, `ops.put_agent_run`. 공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다 (앞 작업 discover 를 기다리는 규칙 포함).
p30 이 false 면 테제 큐는 건너뛰고 경로만 (note 에 "0030 미적용").

조사의 목적은 **가설의 가장 약한 고리를 원문으로 깨 보는 것**이다. 확인하려 들지 말고 반박하려 든다 — 반박을 찾지 못한 것만 다음 단계로 간다.
지난 실행에서 가장 값졌던 것도 반박이었다 (MACOM CW 레이저 양산 2027 말 이후, Coherent InP 외판 없음 → 메모를 뒤집었다).

## 1. 큐 (한 실행에 합쳐 최대 8개)
- 테제: `select thesis_key, scale, parent_key, title, weakest_link, beneficiaries, stage, created_at from public.v_q_theses_needing_research;` — **최대 3개를 먼저** (새것 순). 큰 테제(macro)는 토요일 verify 가 본다.
- 경로: `select issue_key, issue_title, as_of, path_id, company, company_label, claim, research, falsifier, flags, score from public.v_q_paths_needing_research;` — 남은 칸(8 − 테제 수)을 점수 순으로.
- 둘 다 비어 있으면 `skipped` 로 기록하고 끝낸다 (보고 1줄). 나머지는 다음 날.

## 2. 테제마다 — 가장 약한 고리
- `weakest_link` 한 문장이 원문에서 사실인지 본다: 기업 IR·사업보고서·공시(공급계약·단일판매), 고객의 협력사 명단·발표, 업계지, 채용 공고, 전시회 후기. 대개 "이 회사가 그 고객에게 그 부품을 공급하는가 / 그 제품의 매출 비중이 얼마인가" 다.
- **반박부터 찾는다**: 경쟁사가 그 자리를 가져갔다는 보도, 고객의 다른 공급사 발표, 제품 매출 비중이 작다는 공시, 양산 시점이 늦다는 원문, 이미 주가에 반영됐다는 근거(빠르게 오른 가격 + 그 이유가 같은 논리인 기사).
- 판정(verdict) — 경로와 같은 다섯 가지:
  - `confirmed` — 고리와 크기(비중·금액·수량)가 원문에서 확인 (sources 1개 이상, 가능하면 event_ids).
  - `partial` — 고리는 확인, 크기·시점은 못 찾음.
  - `unconfirmed` — 찾아봤지만 확인할 원문이 없다 (무엇을 어디서 찾았는지 summary 에).
  - `no_data` — 그 기업이 공시·IR 을 내지 않아 확인할 길이 없다.
  - `refuted` — 원문이 고리를 부정한다. sources 필수. **stage 0 micro 테제는 이 판정으로 그날 닫힌다** (함수가 status=closed, 근거 −, weight 3). macro 는 근거만 남는다.
- 단편 단서는 kind=rumor 로 밝히고 쓴다. rumor 뿐이면 판정은 `partial` 까지 (confirmed 는 official·customer·trade_press 가 하나는 있어야 한다).
- 확인한 사실은 그 기업의 소식으로 저장하고(공통 §B) event_id 를 받아 둔다 — 리포트가 근거 id 로 쓴다. 병목 숫자는 관측치로(공통 §C).
- 저장:
  `select ideas.put_thesis_research($j$[{"thesis_key":"…","verdict":"partial","summary":"한국어 1~3문장, 숫자·날짜","sources":[{"title":"…","url":"https://…","date":"YYYY-MM-DD","kind":"official|customer|trade_press|news|rumor"}],"event_ids":["…"],"model":"claude-…"}]$j$::jsonb);`
  결과의 `closed` 가 반박으로 닫힌 수다. rejected(테제 없음·summary 짧음·sources 없음)가 있으면 고쳐 한 번 더.

## 3. 경로마다 — 마지막 고리 (공통 §B 의 출처 규칙)
- `research` 목록(확인할 것)을 순서대로 원문에서 확인한다: 회사 IR·실적 발표·공시·제품 페이지, 고객의 증설·수주 발표, 업계지. WebFetch 로 열고, 안 열리면 WebSearch 로 같은 사건의 다른 기사 (거부된 것은 우회하지 않는다 — 공통 §0).
- 이 기업이 정말 그 부품·장비·소재를 그 고객에게 공급하는지, 매출 비중이 얼마인지, 변화가 이미 숫자(수주·가이던스·증설)로 나타났는지. 판정은 2 와 같은 다섯 가지 (refuted 경로는 리포트 대상에서 빠진다).
- 저장: `select ideas.put_path_research($j$[{"issue_key":"…","path_id":"H1","as_of":"YYYY-MM-DD","verdict":"confirmed","summary":"…","sources":[{"title":"…","url":"https://…","date":"YYYY-MM-DD","kind":"official"}],"event_ids":["c…"],"model":"claude-…"}, …]$j$::jsonb);`
  as_of 는 큐 행의 as_of 그대로. rejected 가 있으면 고쳐 한 번 더.
- 경로가 활성 **micro** 테제의 weakest_link 를 반박하면(예: 그 primary 가 그 부품을 공급하지 않는다) 그 테제에도 `put_thesis_research` 로 refuted 를 적는다 — 이미 조사됐어도 덮어쓴다. macro 에 대한 반박은 경로의 thesis 태그(−)로 verify 가 근거에 남긴다.

## 4. 완료 조건과 기록
- `select verdict, count(*) from ideas.path_research where created_at > now() - interval '3 hours' group by 1;`
- `select research->>'verdict' as verdict, count(*) from ideas.theses where researched_at > now() - interval '3 hours' group by 1;`
- `select (select count(*) from public.v_q_theses_needing_research where scale='micro') as left_micro, (select count(*) from public.v_q_paths_needing_research) as left_paths;`
- 처리한 수가 min(두 큐 합, 8) 이어야 한다.
- `select ops.put_agent_run('{"task":"research","status":"succeeded","rows":<처리 수>,"counts":{"theses":…,"paths":…,"confirmed":…,"partial":…,"unconfirmed":…,"no_data":…,"refuted":…,"theses_closed":…,"events":…,"observations":…,"left_micro":…,"left_paths":…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`

## 5. 보고와 알림
- 보고 7줄 이내: 테제 N(판정별 · **반박으로 닫힌 테제와 이유**) · 경로 N(판정별 · 반박된 경로) · 저장한 소식 N·관측치 N · 남은 큐(micro N · 경로 N).
- 알림은 실패했을 때만: 큐가 있는데 하나도 저장하지 못했을 때, DB 쓰기 실패.
