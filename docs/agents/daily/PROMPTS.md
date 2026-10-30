# 예약작업 프롬프트 (ADR-0028 — 2026-10-31 부터)

예약작업 화면에서:
- **바꾸기 (3개)**: 06:17 · 06:49 · 07:37 작업의 이름과 프롬프트를 아래로 통째로 바꾼다 (시각·모델은 그대로).
- **끄기 (2개)**: 08:11 "WSJ 5/5 검증 + 보고" 와 06:41 "WSJ (전환기) 아침 한 세션 작업".
- 그대로: 05:23 수집, 주간 시스템 개선.

## 06:17 — 이름: `WSJ 2/4 해석 (06:17)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 2/4 — **interpret(해석)** 작업이다 (ADR-0028). 공시·실적보다 먼저 나오는 작은 단서(제품 출시·협약·샘플·인증·초도 수주·전시회·채용·특허·소문)를 읽고, 온톨로지와 해석 지침으로 그것이 어느 미국·한국 상장사(소·중형 먼저)의 무엇을 얼마나 바꾸는지 해석해 투자 아이디어 초안(★1~5 · 제목 · 아이디어 · 해석 · 근거)을 쓴다. 의미 있는 단서가 없으면 아무것도 쓰지 않는다. 그래프에 없던 고리·기업은 그래프에 더한다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ideas.put_opportunities(jsonb)') is not null as p31;` — false 면 "0031 미적용" 한 줄로 끝낸다 (알림 없음).
3. add_repo 로 W-X-Z/WSJ-investment 를 access=push 로 붙이고 안내된 clone 명령으로 `--depth 20` clone 한다. `docs/agents/daily/interpret.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다. 공통 규칙은 `docs/agents/daily-ideas.md`, 작성 규칙은 `docs/agents/writing.md`, 해석 지침은 `research/playbook/`. 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계:
   - Supabase 쓰기는 `ideas.put_opportunities`, `ops.put_agent_run` 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다.
   - 저장소 변경은 `research/`(ecosystems/patches 와 패치가 바꾸는 그래프 파일, playbook)와 생성 파일 `apps/web/src/data/` 뿐이다. 브랜치 `auto/interpret-YYYYMMDD` 로 PR 을 올리고, CI(pytest · typecheck-build · Vercel)가 모두 통과하고 바뀐 파일이 전부 그 두 경로 안이면 스스로 병합한다. 그 밖의 경로가 바뀌면 병합하지 않는다. main 직접 push·강제 push 금지.
   - 근거는 WebFetch 로 직접 연 원문. 거부된 도구·URL 은 다른 수단(curl·미러·캐시)으로 우회하지 않고 건너뛰어 기록한다. 시세·특징주 기사는 쓰지 않는다. 매수/매도 권유·목표가·시점 예측은 쓰지 않는다.
5. 커밋 메시지 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>` 를, PR 본문 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)` 를 붙인다.
6. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 실패일 때만 (하루 알림은 4/4 가 보낸다).
```

## 06:49 — 이름: `WSJ 3/4 원문 보강 (06:49)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment)의 아침 사슬 3/4 — **enrich(원문 보강)** 작업이다 (ADR-0028). 오늘 해석 작업이 쓴 투자 아이디어 초안마다, 아이디어가 기대는 핵심 사실을 원문으로 먼저 깨 보고(반대 증거부터), 빠진 숫자(제품 매출 비중·고객·계약 규모·시총·주가 흐름)를 채운다. 핵심이 틀렸으면 초안을 내린다(dropped). 판정 라벨은 붙이지 않는다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ideas.put_opportunities(jsonb)') is not null as p31;` — false 면 "0031 미적용" 한 줄로 끝낸다 (알림 없음).
3. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 안내된 clone 명령으로 `--depth 1` clone 한다. `docs/agents/daily/enrich.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다. 공통 규칙은 `docs/agents/daily-ideas.md`, 작성 규칙은 `docs/agents/writing.md`. 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계: Supabase 쓰기는 `ideas.put_opportunities`, `ideas.put_company_events`, `ops.put_agent_run` 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 저장소는 수정·커밋하지 않는다. 근거는 WebFetch 로 직접 연 원문 — 단편 단서(소문·채용 공고·전시회 후기)는 성격을 밝히고 쓰되 시세 기사·자동 생성 요약·날짜 없는 글·출처 없는 숫자는 쓰지 않는다. 거부된 도구·URL 은 우회하지 않고 기록한다.
5. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 그 밖의 알림은 실패일 때만.
```

## 07:37 — 이름: `WSJ 4/4 리포트 (07:37)`
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 아침 사슬 4/4 — **report(리포트)** 작업이다 (ADR-0028). 보강이 끝난 투자 아이디어 초안을 작성 규칙대로 다듬어(명사형 제목 '[원인]에 따른 [대상] [변화]', 읽기 쉬운 한국어, 내부 용어 없이) ★1~5 를 다시 매겨 낸다(active). 같은 회사·같은 이야기는 기존 아이디어에 합친다. 오늘 들어온 공시·실적이 이야기를 바꾼 기존 아이디어를 고친다. 그리고 하루 알림을 보낸다. 판정·채점·목표주가는 하지 않는다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다. 일요일이면 "일요일" 한 줄로 끝낸다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ideas.put_opportunities(jsonb)') is not null as p31;` — false 면 "0031 미적용" 한 줄로 끝낸다 (알림 없음).
3. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 안내된 clone 명령으로 `--depth 1` clone 한다. `docs/agents/daily/report.md` 와 `docs/agents/writing.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다. 공통 규칙은 `docs/agents/daily-ideas.md`. 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계: Supabase 쓰기는 `ideas.put_opportunities`, `ops.put_agent_run` 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 저장소는 수정·커밋하지 않는다. 매수/매도 권유·목표가·시점 예측은 쓰지 않는다.
5. 문서를 읽을 수 없으면(클론 실패 등) 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다.
6. 알림은 **매일** 보낸다: 첫 줄에 오늘 사슬 한 줄, 이어서 오늘 낸 아이디어를 ★ 높은 순으로 '★ 개수 + 제목 + 한 줄 요지', 그다음 ★ 가 바뀌거나 닫힌 아이디어, 실패한 작업. 새로 낸 것도 바뀐 것도 없으면 "오늘 새 아이디어 없음" 한 줄.
```
