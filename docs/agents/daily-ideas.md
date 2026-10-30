# 공통 규칙 — 아침 작업 네 개 (ADR-0028)

아침 일은 네 예약작업이 나눠 한다. 절차는 `docs/agents/daily/<task>.md`, 이 문서는 넷이 공유하는 전제·시작과 끝·출처 규칙이다.
두 곳이 어긋나면 작업 문서보다 이 문서가, 이 문서보다 사람이 승인한 PR 이 이긴다. 옛 절차(ADR-0024~0027: 경로 점수·목표주가·예측 채점·테제 사슬)는 `docs/agents/legacy/adr0027/` 에 남아 있지만 쓰지 않는다.

| 작업 | 시각 | 문서 | 하는 일 | 쓰는 함수 |
|---|---|---|---|---|
| collect | 05:23 | daily/collect.md | 수집 워크플로가 오늘 돌았는지 확인·실행 | (없음) |
| interpret | 06:17 | daily/interpret.md | 새 단서를 읽고 해석 → 투자 아이디어 초안(draft), 빠진 그래프 고리 추가 | put_opportunities (+ 그래프 패치 PR) |
| enrich | 06:49 | daily/enrich.md | 초안의 사실을 원문으로 채우고 고친다 — 핵심 사실이 틀리면 dropped | put_opportunities · put_company_events |
| report | 07:37 | daily/report.md | 초안을 다듬어 낸다(active), 기존 아이디어 갱신, 하루 알림 | put_opportunities |

08:11 검증 작업과 06:41 전환기 작업은 없다 (ADR-0028 — 판정·채점을 하지 않는다. 확인은 사용자가 한다).

**이 시스템의 일**: 공시·실적보다 먼저 나오는 **작은 단서**를 읽고, 온톨로지와 해석 지침(`research/playbook/`)으로 그 의미를 해석해,
**★1~5 · 제목 · 투자 아이디어 · 해석 · 근거** 로 사용자에게 알린다. 작성 규칙은 `docs/agents/writing.md`. 주 기업은 **미국 상장사 먼저, 한국은 보조** (ADR-0021, 사용자 2026-10-30), 소·중형을 먼저 본다. 목표는 **1년 안팎에 2~3배** — 텐배거가 아니어도 된다.
**숫자(실적·수주)가 나올 때는 이미 늦다** (사용자, 2026-10-30): 기술·수요·병목이 1~3년 뒤 어디로 가는지를 예측하고, 채택의 첫 신호에서 아이디어를 쓴다. 위험은 감수한다 — 대신 틀렸다고 볼 신호와 그 확인 시점을 적는다.
규칙·점수로 판단을 대신하지 않는다 — 판단은 해석이 하고, 해석이 남긴 기록을 사용자가 본다.

## 0. 모든 작업의 시작과 끝
시작:
- `date` 로 KST(UTC+9) 오늘 날짜를 구한다. 일요일이면 "일요일" 한 줄로 끝낸다.
- add_repo 로 W-X-Z/WSJ-investment 를 붙이고 clone (interpret 은 access=push, `--depth 20`; 나머지는 `--depth 1`). `cd pipeline && python3 -m venv .venv && .venv/bin/pip install -q -e .`
- Supabase MCP get_project_url · get_publishable_keys 로 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`(sb_publishable_…)를 export 한다. secret 키는 쓰지 않는다.
- Supabase MCP execute_sql (project_id: dcatgfivsvbktylmtvgf): `select to_regprocedure('ideas.put_opportunities(jsonb)') is not null as p31;`
  false 면 "0031 미적용" 한 줄 보고·알림 후 `skipped` 로 끝낸다.
- **앞 작업을 기다린다** (interpret 부터): 앞 작업(collect → interpret → enrich → report)의 오늘 행이 `running` 이면 최대 30분 기다린다 —
  `timeout 590 bash -c 'until curl -s "$SUPABASE_URL/rest/v1/v_agent_runs?select=status&task=eq.<앞 작업>&run_date=eq.$(TZ=Asia/Seoul date +%F)" -H "apikey: $SUPABASE_PUBLISHABLE_KEY" -H "Authorization: Bearer $SUPABASE_PUBLISHABLE_KEY" | grep -qv running; do sleep 30; done'` 를 세 번까지.
  그래도 running 이면 쌓인 것으로 진행하고 note 에 "앞 작업 미완료". 앞 작업 행이 아예 없으면 기다리지 않는다.
- `select ops.put_agent_run('{"task":"<작업>","status":"running"}'::jsonb);`

끝:
- `select ops.put_agent_run('{"task":"<작업>","status":"succeeded|skipped|failed","rows":N,"counts":{…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"한 줄"}'::jsonb);` — 같은 날 같은 작업은 한 행.
- **하지 않은 것을 기록한다**: `skipped`(손대지 않은 것과 이유) · `denied`(거부된 도구·URL) · `unverified`(원문을 못 열어 추론으로 쓴 주장). 비어 있으면 빈 배열.
- **프롬프트의 경계가 문서보다 좁으면 프롬프트를 따른다**: 프롬프트가 허용하지 않는 함수·저장소 쓰기가 문서에 있으면 그 단계는 하지 않고 `skipped` 에 "프롬프트 경계: …". 새 프롬프트는 `docs/agents/daily/PROMPTS.md`.
- **거부를 우회하지 않는다**: WebFetch·도구·권한이 거부되면 curl·다른 URL·캐시·미러로 같은 것을 가져오지 않는다. 건너뛰고 `denied` 에 적는다.
- 공통 경계: DB 쓰기는 작업 문서에 적힌 함수와 `ops.put_agent_run`, 읽기용 select 뿐이다. 저장소는 수정하지 않는다 — **interpret 만 예외**로 `research/` 와 생성 파일 `apps/web/src/data/` 를 PR 로 바꾸고, CI 가 통과하면 스스로 병합한다 (interpret.md §5).
  매수·매도 권유, 목표가, 시점 예측은 쓰지 않는다 — ★ 와 아이디어로 말한다.

## B. 원문과 출처
- WebFetch 로 원문을 연다(news.google.com 은 원문 주소로). 안 열리면 WebSearch 로 같은 사건의 다른 기사를 찾는다. 네이버 증권·KIND·DART 본문은 막혀 있다 — 같은 내용을 옮긴 기사를 찾는다.
- **작은 단서가 먼저다**: 제품 출시·시연, 업무협약·공동개발, 샘플·고객 인증, 초도·소량 수주, 고객사 협력사 명단, 전시회 후기, 새 직무 채용, 특허·논문, 소형사 라인 증설, 업계 소문. 공시·실적은 후행 데이터라 맨 나중에, 이미 진행 중인 아이디어를 고치거나 확인하는 데만 쓴다.
- 단편 단서도 근거가 된다 — 성격(소문·채용 공고·전시회 후기)을 근거 제목에 밝힌다. 빼는 것은 문제 있는 데이터뿐: **시세·특징주 기사**, 자동 생성 요약, 날짜 없는 글, 출처 없는 숫자.
- 기업의 확인한 사실을 남길 때: `select ideas.put_company_events($j$[{"company_id":"company:…","kind":"news|disclosure|filing|revenue","published_at":"YYYY-MM-DD","title":"…","url":"https://…","text":"한국어 1~3문장, 날짜·숫자·상대방","importance":2}]$j$::jsonb);` (그래프에 있는 기업만, 45일 안 날짜).
