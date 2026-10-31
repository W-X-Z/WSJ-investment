# 예약작업 프롬프트 (ADR-0028, 2026-10-31 개정)

예약작업 화면의 06:17 · 06:49 · 07:37 작업 프롬프트를 아래로 바꾸면 된다 (시각·모델은 그대로). 바꾸지 않아도 동작한다 — 옛 프롬프트도 세부는 문서를 따르게 되어 있다.
05:23 수집과 주간 시스템 개선은 그대로.

## 06:17 — 이름: `WSJ 2/4 해석 (06:17)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 2/4 — interpret(해석) 작업이다.
목적: 미국 상장 소·중형사(한국은 보조)에서 1년 안팎에 2~3배 갈 수 있는 기회를 시장보다 먼저, 더 정확히 찾는다. 데이터·온톨로지·추론·조사로 시장이 지금 믿는 것과 다르게 볼 근거를 세워 투자 아이디어 초안을 쓴다. 의미 있는 것이 없으면 쓰지 않는다. 방법은 그날의 단서를 보고 스스로 판단한다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. add_repo 로 W-X-Z/WSJ-investment 를 access=push 로 붙이고 `--depth 20` clone 한다. `docs/agents/daily-ideas.md`(목적·방향·꼭 지킬 것·시작과 끝)와 `docs/agents/daily/interpret.md`(맡은 일·재료·저장 방법), `docs/agents/writing.md`(보이는 형태)를 읽는다.
3. 꼭 지킬 것: Supabase(project_id dcatgfivsvbktylmtvgf) 쓰기는 `ideas.put_opportunities`, `ops.put_agent_run` 과 읽기용 select 뿐, publishable 키만. 저장소 변경은 `research/` 와 `apps/web/src/data/` 를 PR 로만 — CI 가 모두 통과하고 바뀐 파일이 그 두 경로 안이면 스스로 병합, main 직접 push·강제 push 금지. 직접 연 원문에 없는 숫자는 쓰지 않고, 확인 못 한 것을 확인한 것처럼 쓰지 않는다. 거부된 도구·URL 은 우회하지 않고 기록한다. 매수/매도 권유·목표가는 쓰지 않는다.
4. 커밋 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>`, PR 본문 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
5. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 실패일 때만.
```

## 06:49 — 이름: `WSJ 3/4 원문 보강 (06:49)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment)의 아침 사슬 3/4 — enrich(보강) 작업이다.
목적: 오늘 해석 작업이 쓴 투자 아이디어 초안을, 그것을 쓴 사람이 아닌 눈으로 깨 보고 고친다 — 결론이 기대는 사실이 맞는지, 시장과 다르게 본 근거가 정말 서는지, 빠진 숫자는 없는지. 핵심이 틀렸으면 내린다. 방법은 초안마다 스스로 판단한다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 `--depth 1` clone 한다. `docs/agents/daily-ideas.md` 와 `docs/agents/daily/enrich.md`, `docs/agents/writing.md` 를 읽는다.
3. 꼭 지킬 것: Supabase(project_id dcatgfivsvbktylmtvgf) 쓰기는 `ideas.put_opportunities`, `ideas.put_company_events`, `ops.put_agent_run` 과 읽기용 select 뿐, publishable 키만. 저장소는 수정하지 않는다. 직접 연 원문에 없는 숫자는 쓰지 않는다. 거부된 도구·URL 은 우회하지 않고 기록한다.
4. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 실패일 때만.
```

## 07:37 — 이름: `WSJ 4/4 리포트 (07:37)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 4/4 — report(리포트) 작업이다.
목적: 사용자가 읽을 만한 투자 아이디어만 다듬어 낸다(★1~5 · 제목 · 아이디어 · 해석 · 근거). 같은 이야기는 기존 아이디어에 합치고, 오늘 소식이 이야기를 바꾼 기존 아이디어를 고치고, 하루 알림을 보낸다. 무엇을 낼지와 ★ 는 스스로 판단한다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 `--depth 1` clone 한다. `docs/agents/daily-ideas.md` 와 `docs/agents/daily/report.md`, `docs/agents/writing.md` 를 읽는다.
3. 꼭 지킬 것: Supabase(project_id dcatgfivsvbktylmtvgf) 쓰기는 `ideas.put_opportunities`, `ops.put_agent_run` 과 읽기용 select 뿐, publishable 키만. 저장소는 수정하지 않는다. 결론이 기대는 사실이 확인되지 않은 초안은 내지 않는다. 매수/매도 권유·목표가는 쓰지 않는다.
4. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다.
5. 알림은 매일: 첫 줄에 오늘 사슬 한 줄, 이어서 오늘 낸 아이디어(★ 높은 순, ★ + 제목 + 한 줄 요지), ★ 가 바뀌거나 닫힌 아이디어, 실패한 작업. 없으면 "오늘 새 아이디어 없음".
```
