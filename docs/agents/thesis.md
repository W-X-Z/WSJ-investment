# thesis (토요일 09:17) — 구조 가설을 세우고, 드라이버를 재고, 단계를 옮긴다

예약작업 "WSJ 구조 가설 (토 09:17)" 이 따른다 (ADR-0025). 리포트가 "이 기업 + 이 이슈" 라면 테제는 "사용 방식의 변화 → 자원 요구 → 공급 병목 → 누가 리레이팅되나" 를 여러 달에 걸쳐 쌓는 단위다. 대형주도 받는다.
공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다 (작업명 `thesis`). 쓰는 함수: `ideas.put_theses`, `ideas.put_thesis_evidence`, `ideas.put_observations`, `ideas.put_company_events`, `ops.put_agent_run`.
p28 확인: `select to_regprocedure('ideas.put_theses(jsonb)') is not null as p28;` — false 면 "0028 미적용" 보고·알림 후 끝.

## 1. 읽기
- 활성 테제: `select thesis_key, title, stage, stage_reason, drivers, falsifiers, n_support, n_against, last_evidence_at from public.v_theses where status='active';`
- 지난 7일 근거: `select thesis_key, as_of, direction, what, ref from public.v_thesis_evidence where as_of > current_date - 7 order by as_of;`
- 벤치마크: `research/benchmarks/regime_cases.json` — 테제마다 닮은 사례의 '가장 이른 신호·시차·필요했던 데이터' 를 다시 읽는다.
- 수요측 그래프: `research/ecosystems/seed_graph.json` 의 `demand_driver:*` 노드와 그 하류.

## 2. 테제마다 드라이버 갱신 — 출처는 수요가 만들어지는 곳
각 driver 의 최신값을 원문에서 찾는다: 모델 릴리스 노트(컨텍스트 길이·출력 토큰·가격), 추론 플랫폼 발표(메모리 계층·오프로딩), 하이퍼스케일러 capex 가이던스·컨콜, Nvidia·AMD 키노트 수치, TrendForce·SemiAnalysis 류 데이터, 메모리 3사 컨콜(수급비·계약가), 추론 인프라 채용 공고.
- 찾은 값은 관측치로도 저장한다 (공통 §C, nodes 에 demand_driver·bottleneck 노드 id).
- 근거를 기록한다: `select ideas.put_thesis_evidence($j$[{"thesis_key":"…","direction":"+|-|0","what":"한 줄 (숫자·날짜)","ref":{"url":"https://…","indicator_id":"obs:…"},"weight":1}]$j$::jsonb);`
- falsifier 의 due 가 지났으면 결과를 적고(direction -, weight 3) 성립이면 status=closed.

## 3. 단계 판정
- stage 0 가설 → 1: 드라이버 중 둘 이상이 임계 방향으로 움직임 (수치 근거).
- 1 → 2: 공급 반응이 보임 — 증설·할당·가격(계약가·리드타임) 중 둘 이상이 원문으로 확인.
- 2 → 3: 시장이 반영 — 수혜 기업의 배수가 사이클 밴드를 벗어남(리레이팅이 일어남). 3 은 '맞았다' 지 '사라' 가 아니다. 이때 하류(2차 파동)의 새 테제 후보를 적는다.
- 내려가는 쪽도 같은 규칙: 드라이버가 되돌아가면 stage 를 내리고 이유를 stage_reason 에.

## 4. 새 테제 (주 최대 1개)
- 후보는 지난 7일 이슈·관측치·demand_driver 하류에서 "사용 방식이 바뀌고 있다" 는 신호가 있는 것. 뉴스 제목이 아니라 **누가 무엇을 다르게 쓰기 시작했나** 에서 출발한다.
- 형식은 `research/theses/memory_inference_rerating_2026.json` 과 같다: statement 80자 이상, chain 3단계 이상(수요 동인 → 요구 → 병목 → 부품 → 기업, 노드 id), drivers 1개 이상(수치·출처·임계치), beneficiaries(리레이팅 근거 from→to), losers, falsifiers(due 날짜), benchmark(닮은 사례 id).
- `select ideas.put_theses($j$[{…}]$j$::jsonb);` 거부되면 사유대로 고쳐 한 번 더. 저장한 테제는 `research/theses/<key>.json` 에 같은 내용으로 남기고 PR 로 올린다 (주간 개선 작업과 같은 경계: research/ 안만 스스로 병합).

## 5. 완료 조건과 기록
- `select thesis_key, stage, n_support, n_against from public.v_theses where status='active';` 와 이번 주 근거 수.
- `select ops.put_agent_run('{"task":"thesis","status":"succeeded","rows":<근거 수>,"counts":{"theses":…,"evidence":…,"stage_changes":…,"new":…},"note":"…"}'::jsonb);`

## 6. 보고와 알림
- 보고 7줄 이내: 테제마다 (stage · 드라이버 최신값 · 이번 주 근거 ± · 바뀐 것) · 새 테제 · 닫은 테제.
- 알림은 매주: 첫 문장에 stage 가 바뀐 테제, 이어서 드라이버가 임계를 넘은 것, 반증이 성립한 것.

## 부록 — 예약작업 프롬프트 (등록용, 토 09:17 KST)
```
개인 투자 연구 웹 WSJ-investment(저장소 W-X-Z/WSJ-investment, https://wsj-investment.vercel.app)의 주간 thesis(구조 가설) 작업이다 (ADR-0025). 리포트가 "이 기업 + 이 이슈" 라면 테제는 "사용 방식의 변화 → 자원 요구 → 공급 병목 → 누가 리레이팅되나" 를 여러 달에 걸쳐 쌓는 단위다. 뉴스 제목이 아니라 누가 무엇을 다르게 쓰기 시작했나에서 출발하고, 대형주도 받는다. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST(UTC+9) 오늘 날짜를 확인한다.
2. Supabase MCP execute_sql (project_id dcatgfivsvbktylmtvgf): `select to_regprocedure('ideas.put_theses(jsonb)') is not null as p28;` — false 면 "0028 미적용" 한 줄로 끝낸다 (알림 없음).
3. add_repo 로 W-X-Z/WSJ-investment 를 push 권한으로 붙이고 안내된 clone 명령으로 `--depth 20` clone 한다. `docs/agents/thesis.md` 를 처음부터 끝까지 읽고 그 절차를 그대로 따른다. 공통 규칙은 `docs/agents/daily-ideas.md` §0·§B·§C. 세부 규칙은 이 프롬프트가 아니라 문서가 기준이다.
4. 경계: Supabase 쓰기는 ideas.put_theses, ideas.put_thesis_evidence, ideas.put_observations, ideas.put_company_events, ops.put_agent_run 과 읽기용 select 뿐이다. secret 키는 쓰지 않고 publishable 키만 쓴다. 저장소 변경은 research/theses/ 안의 테제 JSON 뿐이며 브랜치 auto/thesis-YYYYMMDD 로 PR 을 올리고 CI 통과 + 바뀐 파일이 전부 research/ 안이면 스스로 병합한다. 그 밖의 경로는 바꾸지 않는다. main 직접 push·강제 push 금지. 근거는 WebFetch 로 직접 연 원문만. 매수/매도 권유·시점 예측은 쓰지 않는다.
5. 커밋 메시지 끝에 `Co-Authored-By: Claude <noreply@anthropic.com>` 를, PR 본문 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)` 를 붙인다.
6. 문서를 읽을 수 없으면 무엇이 실패했는지 보고하고 알림을 보낸 뒤 끝낸다. 알림은 매주: 첫 문장에 stage 가 바뀐 테제, 이어서 드라이버가 임계를 넘은 것·반증이 성립한 것·새 테제.
```
