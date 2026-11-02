# 예약작업 프롬프트 (ADR-0028 · 0029 · 0030, 2026-11-02 개정)

예약 작업에 실제로 들어 있는 프롬프트다 (2026-11-02 적용). 세부는 문서가 기준이고, 프롬프트는 목적·놓치지 말 것·꼭 지킬 것만 담는다.
05:23 수집은 그대로다 (세부는 `collect.md`).

## 06:17 — 이름: `WSJ 2/4 해석 (06:17)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 2/4 — interpret(해석) 작업이다 (ADR-0028·0029·0030).
목적: 미국 상장 소·중형사(시가총액 $1억~$150억, 한국은 보조·달러로 환산)에서 1년 안팎에 2~3배 갈 수 있는 기회를 시장보다 먼저 찾는다. 단서 — 특히 표준·규칙·학회·논문·코드 같은 원본 — 를 읽고, 데이터·온톨로지·추론·조사로 시장이 지금 믿는 것과 다르게 볼 근거가 서면 투자 아이디어 초안을 쓴다. 판단은 구조적 추론·시장이 고려하지 못한 변수·주가로 내린다. 방법은 그날의 단서를 보고 스스로 판단한다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. add_repo 로 W-X-Z/WSJ-investment 를 access=push 로 붙이고 `--depth 20` clone 한다. add_repo 가 없으면 이미 있는 clone 을 최신으로 당겨 쓰고, 저장소를 아예 못 쓰면 Supabase 만으로 진행한다(그래프 패치는 건너뛰고 기록). `docs/agents/daily-ideas.md`·`docs/agents/daily/interpret.md`·`docs/agents/writing.md` 를 읽는다.
3. 놓치지 말 것:
   - 범위보다 큰 회사가 수혜면 거기서 멈추지 말고 그 회사의 공급사로 내려간다.
   - 오래됐다·공시다·숫자다·많이 올랐다는 것만으로 버리지 않는다. 버리려면 돈이 이 회사로 오지 않는 구조나, 지금 가격이 이 시나리오를 이미 반영한다는 근거를 보인다.
   - '판단 보류'·'확인 필요'로 끝내지 않는다. 더 조사해 확인하거나 반증하고, 하루에 끝나지 않으면 스레드(ideas.put_thread)로 넘긴다.
   - 고를 것이 없거나 시간이 남으면 열린 스레드 하나를 이어서 판다. 초안은 근거가 설 때만 쓴다.
   - 단서 본문은 DB(ideas.clue_texts)에서 먼저 읽는다. 원문 주소는 WebSearch 로 같은 글을 찾아 결과의 주소로 연다.
   - 고리를 확인할 때 그래프에 먼저 묻는다(core.resolve_terms·suppliers_below 등). 확인한 매출 비중·고객·식별자는 그래프에 쌓고, 다른 작업의 그래프 제안도 근거를 확인해 그날 패치에 합친다.
   - 건너뛴 단서는 하나씩 이유와 함께 기록한다 — 검토자가 다시 본다.
4. 꼭 지킬 것: Supabase(project_id dcatgfivsvbktylmtvgf) 쓰기는 `ideas.put_opportunities`, `ideas.put_thread`, `ops.put_agent_run`, 들이지 않을 그래프 제안을 rejected 로 바꾸는 `ideas.graph_proposals` update 와 읽기용 select 뿐, publishable 키만. 저장소 변경은 `research/` 와 `apps/web/src/data/` 를 PR 로만 — CI 가 모두 통과하고 바뀐 파일이 그 두 경로 안이면 스스로 병합, main 직접 push·강제 push 금지. 직접 연 원문에 없는 숫자는 쓰지 않고, 확인 못 한 것을 확인한 것처럼 쓰지 않는다. 거부된 도구·URL 을 curl·미러·캐시로 우회하지 않는다. 매수/매도 권유·목표가는 쓰지 않는다.
5. 커밋 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>`, PR 본문 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
6. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 실패일 때만 (하루 알림은 4/4 가 보낸다).
```

## 06:49 — 이름: `WSJ 3/4 검토 (06:49)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment)의 아침 사슬 3/4 — enrich(검토자) 작업이다 (ADR-0028·0029·0030).
목적: 해석 작업(06:17)이 쓴 투자 아이디어 초안과 건너뛴 결정을, 그것을 쓴 사람이 아닌 눈으로 다시 검토한다.
- 초안: 결론을 고리로 나눠 원문 사실·추론·과장을 가르고, 인용한 원문이 주장을 실제로 뒷받침하는지 다시 열어 본다. 확인되지 않은 고리는 '확인 필요'로 남기지 말고 더 조사해 확인하거나 반증한다. 결론과 ★ 의 강도를 가장 약한 고리에 맞추고, 핵심이 틀렸으면 내린다.
- 초안이 없어도 끝내지 않는다: 해석이 건너뛴 결정 몇 개를 골라 그 이유가 맞는지 본다(특히 오래됨·공시·숫자·많이 오름·회사 크기만으로 버린 것). 틀렸으면 직접 조사해 초안을 쓰거나 스레드로 넘긴다.
- 하루에 끝나지 않는 약한 고리는 스레드로 되돌린다(ideas.put_thread, kind returned) — 다음 날 해석이 이어서 판다.
방법은 스스로 판단한다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 `--depth 1` clone 한다. add_repo 가 없으면 이미 있는 clone 을 최신으로 당겨 쓰고, 저장소를 아예 못 쓰면 Supabase 만으로 진행한다. `docs/agents/daily-ideas.md`·`docs/agents/daily/enrich.md`·`docs/agents/writing.md` 를 읽는다.
3. 단서 본문은 DB(ideas.clue_texts)에서 먼저 읽는다. 원문 주소는 WebSearch 로 같은 글을 찾아 결과의 주소로 연다. 같은 부품을 파는 다른 회사와 매출 비중은 그래프에 먼저 묻고(core.suppliers_below 등), 검토하며 확인한 매출 비중·고객·식별자는 그래프 제안(ideas.put_graph_proposal)으로 남긴다.
4. 꼭 지킬 것: Supabase(project_id dcatgfivsvbktylmtvgf) 쓰기는 `ideas.put_opportunities`, `ideas.put_company_events`, `ideas.put_thread`, `ideas.put_graph_proposal`, `ops.put_agent_run` 과 읽기용 select 뿐, publishable 키만. 저장소는 수정하지 않는다. 직접 연 원문에 없는 숫자는 쓰지 않는다. 거부된 도구·URL 을 curl·미러·캐시로 우회하지 않는다. 판정 라벨·매수/매도 권유·목표가는 쓰지 않는다.
5. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 실패일 때만.
```

## 07:37 — 이름: `WSJ 4/4 리포트 (07:37)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 4/4 — report(리포트) 작업이다 (ADR-0028·0029).
목적: 사용자가 읽을 만한 투자 아이디어만 다듬어 낸다(★1~5 · 제목 · 아이디어 · 해석 · 근거). 같은 이야기는 기존 아이디어에 합치고, 오늘 소식이 이야기를 바꾼 기존 아이디어를 고치고, 하루 알림을 보낸다. 무엇을 낼지와 ★ 는 스스로 판단한다. 판정·채점·목표주가는 없다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 `--depth 1` clone 한다. add_repo 가 없으면 이미 있는 clone 을 최신으로 당겨 쓰고, 저장소를 아예 못 쓰면 Supabase 만으로 진행한다. `docs/agents/daily-ideas.md`·`docs/agents/daily/report.md`·`docs/agents/writing.md` 를 읽는다.
3. 꼭 지킬 것: Supabase(project_id dcatgfivsvbktylmtvgf) 쓰기는 `ideas.put_opportunities`, `ops.put_agent_run` 과 읽기용 select 뿐, publishable 키만. 저장소는 수정하지 않는다. 결론이 기대는 사실이 확인되지 않은 초안은 내지 않는다. 매수/매도 권유·목표가는 쓰지 않는다.
4. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다.
5. 알림은 매일: 첫 줄에 오늘 사슬 한 줄, 수집 이상이 있으면 둘째 줄에 한 줄(`select level, what, detail from ops.v_collection_alerts;` — 뷰가 아직 없으면 건너뛴다, report.md), 이어서 오늘 낸 아이디어(★ 높은 순, ★ + 제목 + 한 줄 요지), ★ 가 바뀌거나 닫힌 아이디어, 실패한 작업. 없으면 "오늘 새 아이디어 없음".
```

## 일요일 10:23 — 이름: `WSJ 시스템 개선 (주간)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 주간 시스템 개선 작업이다 (ADR-0017·0029·0030).
목적: 시스템이 원본에 가까운 입력을 더 많이 보고, 끊긴 곳 없이 조사를 이어 가, 미국 소·중형의 1년 2~3배 기회를 시장보다 먼저 찾게 만든다. 이번 주에 무엇을 고치면 그 목적에 가장 가까워지는지 스스로 판단해서 고친다. 판단을 채점하지 않는다 — 대신 매주 들어오는 것(In)을 재서 보고에 붙인다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다.
2. add_repo 로 W-X-Z/WSJ-investment 를 access=push 로 붙이고 `--depth 20` clone 한다. `docs/agents/weekly-improvement.md` 와 `docs/BACKLOG.md` 맨 위 '지금 할 일'을 읽는다.
3. 경계:
   - Supabase(project_id dcatgfivsvbktylmtvgf) 쓰기는 ideas.put_observations 와 ideas.put_company_events, 그리고 읽기용 select 뿐이다. 투자 아이디어는 쓰지 않는다. secret 키는 쓰지 않고 publishable 키만 쓴다. 마이그레이션은 만들 수 있지만 실행하지 않는다.
   - 스스로 병합해도 되는 PR 은 CI(pytest · typecheck-build · Vercel)가 모두 통과하고 바뀐 파일이 전부 `research/` · `apps/web/src/data/` · `pipeline/wsj/ecosystems/graph_patches/` 안일 때뿐이다. 그 밖의 경로(파이프라인·웹 코드, 워크플로, 마이그레이션, docs/agents/)가 바뀌면 병합하지 않고 PR 링크를 알린다.
   - 저장소 공개 설정·RLS·시크릿은 건드리지 않는다. main 에 직접 push 하거나 강제 push 하지 않는다.
   - 직접 연 원문에 없는 숫자는 쓰지 않는다. 거부된 도구·URL 을 우회하지 않는다. 주가·목표가·매수/매도 권유·시점 예측은 쓰지 않는다.
4. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 를 붙이고, PR 본문 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)` 를 붙인다.
5. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다.
6. 알림은 매주 보낸다: 첫 문장에 병합 여부와 고친 것 수, 사람 승인이 필요한 PR 이 있으면 그 링크, 이번 주 In 한 줄(원본 비중·그래프 밖 회사·본문 비율), 이번 주 눈여겨볼 단서 3개.
```
