# research (06:49, 월~토) — 리포트 후보로 뽑힌 경로를 원문으로 조사한다

예약작업 "WSJ 3/5 조사 (06:49)" 이 따른다. 큐 = `public.v_q_paths_needing_research` (최근 7일 경로 묶음 중 selected 이고 기업이 있는데 조사 결과가 없는 경로, 점수 순).
쓰는 함수: `ideas.put_company_events`, `ideas.put_observations`, `ideas.put_path_research`, `ops.put_agent_run`. 공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다.
조사의 목적은 **경로의 마지막 고리를 확인하는 것**이다 — 이 기업이 정말 그 부품·장비·소재를 그 고객에게 공급하는지, 매출 비중이 얼마인지, 변화가 이미 숫자(수주·가이던스·증설)로 나타났는지.

## 1. 큐
`select issue_key, issue_title, as_of, path_id, company, company_label, claim, research, falsifier, flags, score from public.v_q_paths_needing_research;`
- 비어 있으면 `skipped` 로 기록하고 끝낸다 (보고 1줄). 한 실행에 **최대 8개**(점수 순) — 나머지는 다음 날.

## 2. 경로마다 조사 — 공통 §B 의 출처 규칙
- `research` 목록(확인할 것)을 순서대로 원문에서 확인한다: 회사 IR·실적 발표·공시·제품 페이지, 고객의 증설·수주 발표, 업계지. WebFetch 로 열고, 안 열리면 WebSearch 로 같은 사건의 다른 기사.
- **단편적인 단서도 쓴다.** 조사가 디테일해질수록(이 기업이 그 고객의 2차 공급사인가, 그 장비의 비중이 얼마인가) 공식 자료에는 없고 업계 소문·전시회 후기·채용 공고·구인 사이트·고객사 협력사 명단·특허·논문·커뮤니티 글에만 있는 경우가 많다.
  그런 것도 **출처의 종류를 밝히고** 쓴다 — sources[].kind: `official`(기업 자신) · `customer`(고객·파트너 발표) · `trade_press`(업계지·데이터) · `news`(일반 언론) · `rumor`(소문·커뮤니티·단편 단서).
  빼는 것은 문제 있는 데이터뿐: 자동 생성 시세 요약, 날짜 없는 글, 출처가 없는 숫자, 서로 모순되는데 확인할 길이 없는 것. 단서가 rumor 뿐이면 판정은 `partial` 까지만(confirmed 는 official·customer·trade_press 가 하나는 있어야 한다).
- 확인한 사실은 그 기업의 소식으로 저장한다 (공통 §B 의 put_company_events, 1~3문장·숫자·날짜·상대방). 저장 뒤 event_id 를 받아 둔다.
- 경로가 지나는 병목의 상태 숫자를 읽었으면 관측치로 기록한다 (공통 §C, 실행당 최대 8개).
- 판정(verdict):
  - `confirmed` — 마지막 고리와 변화의 숫자가 원문에서 확인됐다 (sources 1개 이상, event_ids 있음).
  - `partial` — 고리는 확인됐지만 크기·시점은 못 찾았다 (sources 1개 이상).
  - `unconfirmed` — 찾아봤지만 고리를 확인할 원문이 없다 (무엇을 어디서 찾았는지 summary 에).
  - `no_data` — 그 기업이 공시·IR 을 내지 않아 확인할 길이 없다.
  - `refuted` — 원문이 경로를 부정한다 (예: 그 계약이 다른 제품이었다). sources 필수. 리포트 대상에서 빠진다.
- summary 는 한국어 1~3문장(10자 이상, 1,200자 이내): 무엇을 확인했고 못 했는지, 숫자·날짜와 함께.

## 3. 저장
`select ideas.put_path_research($j$[{"issue_key":"…","path_id":"H1","as_of":"YYYY-MM-DD","verdict":"confirmed","summary":"…","sources":[{"title":"…","url":"https://…","date":"YYYY-MM-DD","kind":"official"}],"event_ids":["c…"],"model":"claude-opus-5-5"}, …]$j$::jsonb);`
- as_of 는 큐 행의 as_of 그대로(경로 묶음의 날짜). rejected(경로 없음·summary 짧음·sources 없음)가 있으면 고쳐 한 번 더.

## 4. 완료 조건과 기록
- `select verdict, count(*) from ideas.path_research where created_at > now() - interval '3 hours' group by 1;` 와 `select count(*) as left_in_queue from public.v_q_paths_needing_research;`
- 처리한 경로 수가 min(큐, 8) 이어야 한다.
- `select ops.put_agent_run('{"task":"research","status":"succeeded","rows":<처리 경로 수>,"counts":{"queue":…,"confirmed":…,"partial":…,"unconfirmed":…,"no_data":…,"refuted":…,"events":…,"observations":…,"left_in_queue":…},"note":"…"}'::jsonb);`

## 5. 보고와 알림
- 보고 6줄 이내: 큐 N 중 조사 N · 판정별 수 · 저장한 소식 N·관측치 N · 반박된 경로(기업·이유) · 남은 큐 N.
- 알림은 실패했을 때만: 큐가 있는데 하나도 저장하지 못했을 때, DB 쓰기 실패.
