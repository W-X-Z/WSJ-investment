# discover (06:17, 월~토) — 이슈 경로 + 오늘의 약한 신호 + 작은 테제 (ADR-0027)

예약작업 "WSJ 2/5 발굴 (06:17)" 이 따른다 (작업명 `discover`, 옛 paths). 공통 규칙 `docs/agents/daily-ideas.md` §0 로 시작하고 끝낸다.
쓰는 함수: `ideas.put_issue_hypotheses`, `ideas.put_weak_signals`, `ideas.put_theses`, `ops.put_agent_run`. 저장소 쓰기는 §D 의 경로뿐.
p26 이 false 면 "0026 미적용" 을 보고·알림하고 `skipped` 로 끝낸다. p30(`select to_regprocedure('ideas.put_thesis_research(jsonb)') is not null as p30;`)이 false 면 **A 만** 하고 note 에 "0030 미적용 — 테제 발굴 건너뜀".

순서와 시간 상자 (전체 60분 안): **A 이슈 경로 (~20분) → B 약한 신호 (~15분) → C 작은 테제 ≤3 (~25분) → D 저장소 → E 기록**. 한 단계가 시간을 넘기면 남은 것은 다음 날로 넘기고 note 에 적는다.
이 작업의 핵심은 C 다 — **작은 규모(한 기업의 한 제품·한 고객·한 계약)에서 시장이 아직 반영하지 않은 변화를 소형·중형주에서 찾는 것.**

## A. 이슈 경로 (옛 paths — 그대로)
### A-1. 큐
`select issue_key, title, importance, ecosystem, published_at from public.v_q_issues_needing_paths;`
- 비어 있으면 A 는 건너뛰고 B 로 (보고 1줄).
- 오늘 수집이 아직 안 끝났으면(`select status from ops.collector_runs where collector='issues' and started_at > now() - interval '6 hours' order by started_at desc limit 1;` 가 succeeded 가 아님)
  B 를 먼저 하고 돌아온다. 그래도 안 끝났으면 쌓인 것으로 진행하고 note 에 "수집 미완료".

### A-2. 1단계 입력과 가설 후보 — 공통 §A
- 입력은 공통 §A 의 첫 명령에 **`--issues-from-queue`** 를 붙여 만든다:
  `.venv/bin/python -m wsj.ecosystems.ideas --from-public --snapshot-out ../.ideas_run/s1 --emit-prompt ../.ideas_run/s1/prompt.json --emit-research ../.ideas_run/s1/research.json --leads-out ../.ideas_run/s1/leads.json --emit-hypotheses ../.ideas_run/s1/hypo.json --issues-from-queue`
  → payload 에는 큐의 이슈 신호와 그 이슈에 닿는 후보·근거만 남는다. 출력 JSON 의 `queue` 가 큐 수, payload.queue.without_signal 이 신호가 없는 이슈다.
- `s1/hypo.system.md`·`s1/hypo.payload.json` 을 끝까지 읽는다. 이슈 신호(kind=issue)마다 그 신호의 evidence 첫 id 를 trigger 로 이슈마다 경로 ≤3 을 `s1/hypotheses.json` 에 쓴다.
  payload.queue.without_signal 의 이슈는 보고에 "신호 없음: issue_key" 로 남긴다.
- **경로를 쓸 때 2단계 아래를 본다** (ADR-0027): 뉴스가 이름을 부른 기업 대신, 그 기업의 공급사·장비사·소재사 중 미국·한국 소·중형사를 company 로 둔 경로를 이슈마다 하나는 넣는다 — 시장이 읽는 것은 헤드라인 기업이다.
- 경로마다 `thesis` 를 적는다 (ADR-0025): 경로가 활성 테제(`select thesis_key, scale, title from public.v_theses where status='active';`)를 지지(+)하거나 반박(−)하면 `{"key": "…", "direction": "+|-"}`, 아니면 null.
- 공통 §A 의 검사·선택 명령을 돌린다. `hypothesis rejected:` 가 절반 넘으면 사유대로 고쳐 한 번 더 (최대 2번).

### A-3. 저장
- `s1/sql/zx_issue_hypotheses*.sql` 을 이름순으로 Read 해서 그대로 execute_sql 로 실행한다. rejected 가 있으면 hypotheses.json 을 고쳐 A-2 의 검사부터 다시.

## B. 오늘의 약한 신호 (요일별 출처)
선행 시간이 긴 출처에서 **온톨로지에 없거나 새로 빨라지는 것** 을 관찰로 남긴다. 출처별 주소·방법·네 질문·온톨로지 대조는 `docs/agents/thesis.md` 1부(1-1 ~ 1-4)가 기준이다.
| 요일 | 오늘 훑는 출처 (source_type) |
|---|---|
| 월 | 논문 `paper` — arXiv cs.AR·cs.DC·cs.ET 최근 1주 |
| 화 | 표준·컨소시엄 `standard` — OCP·OIF·UEC·UALink·JEDEC·CXL·PCI-SIG·IEEE 802.3 |
| 수 | 학회 프로그램·IR 자료 `conference`·`filing` — 이번 달 학회 하이라이트, 메모리·패키징·광·전력사 IR 발표 자료 |
| 목 | 플랫폼 릴리스·모델 API `platform_release`·`model_release` — vLLM·SGLang·Dynamo·TRT-LLM·LMCache 릴리스, 컨텍스트·캐시 가격·출력 한도 변경 |
| 금 | 채용 `hiring` + **소형주 공시** `filing` — 하이퍼스케일러·모델사 인프라 채용 공고, 한국 단일판매·공급계약 체결 보도·미국 8-K item 1.01 중 AI 공급망 소형주 |
| 토 | 전 유형을 가볍게 + 계수표 갱신(thesis.md 1-1′) |
- 수집기 잔차도 매일 본다: `select term, kind_guess, n_seen, last_seen, context from public.v_unmapped_terms where status='open' order by n_seen desc limit 20;`
- 저장: `ideas.put_weak_signals` (thesis.md 1-4 의 형식). 하루 3~10개. 지난번에 본 것을 다시 봤으면 다시 넣는다 (재등장이 신호다).
- 승격·폐기 표시는 sources 없이 `{"signal_key":"…","status":"promoted","promoted_to":"<thesis_key>"}` 만 보낸다 (횟수가 늘지 않는다).
- 1부 결과는 `research/weak_signals/YYYYMMDD.md` 에 짧게 (본 출처, 새 신호, 승격 후보).

## C. 작은 테제 (micro, 하루 최대 3개)
### C-0. 상한 확인
`select count(*) filter (where scale='micro' and status='active') as active_micro, count(*) filter (where scale='micro' and created_at::date = current_date) as today from ideas.theses;`
— 활성 micro 가 40 이상이면 C 는 건너뛰고 note 에 "micro 상한". 오늘 이미 쓴 것이 있으면(다시 돌린 경우) 3 에서 뺀다.

### C-1. 후보 (우선순위 순으로, 후보 6~9개를 적어 놓고 3개를 고른다)
1. **큰 테제 쪼개기** — `select thesis_key, kind, scale, title, chain, beneficiaries, n_children from public.v_theses where status='active' and scale='macro' order by n_children, updated_at;`
   자식이 적은 것부터. chain 의 부품·병목 노드에서 그래프(`research/ecosystems/seed_graph.json`) 하류(`requires`·`offered_by`·`mitigated_by`)를 **두 단계 더** 내려가 미국·한국 상장 소·중형사를 찾는다.
   묻는 것: "이 큰 변화가 **매출 비중으로 가장 크게** 닿는 작은 회사의 한 제품 라인은?" (예: TPU 외부 판매 → 고다층 MLB → 이수페타시스; 메모리 리레이팅 → FC-BGA → 삼성전기 — 재현에서 놓친 고리).
   regime(이미 움직인 체제)도 부모가 될 수 있다 — 그때는 "2차 파동" 의 작은 고리.
2. **승격 가능한 약한 신호** — `select signal_key, term, mechanism, consumes_more, source_types, n_seen from public.v_weak_signals where status='watch' and promotable;` → consumes_more 를 파는 소·중형사.
3. **이슈 경로의 2단계 이상 고리** — 최근 3일 경로 중 company 가 소·중형이고 이슈 제목에 이름이 없는 것:
   `select h.issue_key, i.title, p->>'company' as company, p->>'claim' as claim from ideas.issue_hypotheses h join ideas.supply_chain_issues i using (issue_key) cross join lateral jsonb_array_elements(h.paths) p where h.as_of >= current_date - 3 and p->>'company' is not null;`
4. **금요일 소형주 공시** (B 에서 본 것) — 계약 상대가 AI 인프라 고객인 소형주의 공급계약·증설.
5. **토요일 새 macro** — 승격된 약한 신호가 여러 기업·여러 해에 걸친 구조 변화를 가리키면 3개 중 하나를 macro(scale 생략, `docs/agents/thesis.md` 2-4 그대로)로 쓸 수 있다. 주 1개까지.
- 빼는 것: 그 primary 에 활성 micro 가 이미 있음(`select thesis_key from ideas.theses t, jsonb_array_elements(t.beneficiaries) b where t.status='active' and t.scale='micro' and b->>'company' = '…';`), primary 가 미국·한국 밖, 대형·메가만 있음.

### C-2. 후보마다 빠르게 재기 (각 5~10분)
- **시총과 크기**: 가격 DB 에 있으면 `select * from public.v_price_context where ticker = '…';`(미국 `RMBS`, 한국 `KRX:007660`·`KOSDAQ:…`; 없으면 WebSearch 로 시총 기사). size_band: micro <$0.3B · small <$2B · mid <$10B · large · mega. **primary 는 micro·small·mid 중 하나가 있어야 한다.**
- **노출 비중**: 그 제품 라인의 매출 비중(사업보고서·IR·기사). 모르면 모른다고 쓰고, 그 비중을 weakest_link 로 삼는다.
- **조용함**: 그래프에 있고 가격이 있으면 `cd pipeline && .venv/bin/python -m wsj.ecosystems.quiet --companies company:x` (판정 규칙은 thesis.md 2-4). 그래프·가격이 없으면 `unmeasured` — verify 가 다음 날 다시 잰다.
  `moved`(12개월 +100%↑ 또는 +50%↑·고점 −20% 안)면 쓰지 않는다 — 이미 읽혔다.
- **리레이팅**: 가격이 있으면 `.venv/bin/python -m wsj.ecosystems.rerating company:x --band memory|substrate|equipment` 의 내재 지속 마진·필요 매출 배수를 beneficiaries[].rerating 에. 없으면 기사·IR 의 PER·영업이익률로 한 줄.
- 셋 중 **what_market_misses 가 가장 구체적인 것** 을 고른다 (커버리지 없음 · 헤드라인 기업만 반영 · 고객이 공개되지 않음 · 비중이 알려지지 않음).

### C-3. 형식 (`research/theses/*.json` 과 같고, 아래가 더 붙는다)
```json
{"thesis_key": "tpu_mlb_isu_2027", "scale": "micro", "kind": "thesis", "parent_key": "tpu_merchant_volume_2027", "origin": "decompose",
 "title": "TPU 외부 판매가 고다층 기판 한 곳으로 몰린다",
 "statement": "80자 이상 — 무엇이 바뀌어 이 회사의 어느 제품 매출이 언제 얼마나 바뀌는가",
 "weakest_link": "이수페타시스가 2027년 TPU v8 보드 MLB 의 주 공급사로 남는다 (경쟁사 진입 없음)",
 "chain": [{"node": "product:google_tpu_system", "claim": "…", "evidence": [{"url": "https://…", "title": "…", "date": "YYYY-MM-DD", "kind": "official|customer|trade_press|news|rumor"}]}, {"node": "component:mlb_pcb", "claim": "…"}, {"node": "company:isu_petasys", "claim": "…"}],
 "drivers": [{"id": "tpu_shipments", "metric": "TPU 출하 전망", "latest": "2027 5M (MS, 2026-07)", "threshold": "≥ 5M", "source": "https://…"}],
 "beneficiaries": [{"company": "company:isu_petasys", "role": "primary", "size_band": "mid", "basis": "TPU·스위치 MLB, 매출 비중 …%", "rerating": {"from": "…", "to": "…", "why": "…"}}],
 "losers": [], "falsifiers": [{"what": "4Q26 매출 YoY < +20%", "metric": "분기 실적", "threshold": "< +20%", "due": "2027-02-28"}],
 "first_signal": {"metric": "…", "where": "…", "expected_by": "2026-12"},
 "novelty": "new_structure", "novelty_reason": "…", "what_market_misses": "…", "lag_months": 6, "stage": 0, "stage_reason": "발굴 — weakest_link 미확인",
 "quiet_check": {…quiet 출력 또는 {"verdict":"unmeasured","note":"그래프·가격 없음 — 다음 날 verify"}}, "model": "claude-…", "method": "daily"}
```
- `origin` 은 C-1 의 출발점: `decompose`(큰 테제 쪼개기) · `weak_signal` · `issue_path`(2단계 고리) · `filing`(소형주 공시) · `residual`(수집기 잔차). 성적표가 출발점별 정밀도를 센다.
- **반증 기한 하나 이상은 190일 안**, first_signal 은 3개월 안이 좋다 — 작은 테제는 빨리 판정한다.
- weakest_link 는 **조사가 원문으로 확인하거나 부정할 수 있는 사실 주장** 한 문장이다 ("수혜가 클 것이다" 는 안 된다).
- chain 의 노드는 그래프 id. 없는 기업·부품은 §D 의 JSON 패치로 더한다 (DB 는 노드를 검사하지 않으므로 테제는 먼저 저장해도 된다).
- 근거는 WebFetch 로 직접 연 원문. 단편 단서는 kind=rumor 로 밝히고 쓴다 (공통 §B).

### C-4. 저장
- `select ideas.put_theses($j$[{…}]$j$::jsonb);` — 거부되면 사유대로 고쳐 한 번 더. 출발점이 약한 신호면 그 신호를 `status=promoted, promoted_to=<thesis_key>` 로.
- 같은 내용을 `research/theses/<thesis_key>.json` 에 쓴다.

## D. 저장소 (바뀐 것이 있을 때만)
- 새 기업·간선: `research/ecosystems/patches/YYYYMMDD_discover.json` (형식은 `pipeline/wsj/ecosystems/graph_patches/from_json.py` 맨 위) →
  `cd pipeline && .venv/bin/python -m wsj.ecosystems.graph_patches.from_json ../research/ecosystems/patches/YYYYMMDD_discover.json && .venv/bin/python -m wsj.ecosystems.export_web && .venv/bin/python -m wsj.ecosystems.ontology --check`
  기업은 상장사만(ticker·exchange·size_band), 간선마다 https 원문 근거. 검증이 실패하면 그 노드·간선을 빼고 다시.
- 브랜치 `auto/discover-YYYYMMDD` 에 커밋(메시지 끝 `Co-Authored-By: Claude <noreply@anthropic.com>`) → PR (`gh api repos/W-X-Z/WSJ-investment/pulls -f base=main -f head=… -f title=… -F body=@…`, 본문 끝 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`).
- CI 를 최대 15분 기다린다 (`gh api repos/W-X-Z/WSJ-investment/commits/<sha>/check-runs`). 모두 통과하고 **바뀐 파일이 전부 `research/` 와 `apps/web/src/data/` 안이면** `gh api -X PUT repos/W-X-Z/WSJ-investment/pulls/<n>/merge -f merge_method=squash`.
  그 밖의 경로가 바뀌었거나 CI 가 실패하면 병합하지 않고 PR 링크를 note 에 — 테제는 이미 DB 에 있으므로 사슬은 계속된다. 충돌이 나면 main 을 다시 받아 패치만 다시 적용한다 (강제 push 금지).

## E. 완료 조건과 기록
- `select count(*) as left_in_queue from public.v_q_issues_needing_paths;` — 0 (신호 없음으로 남긴 이슈는 note 에).
- `select count(*) as paths_today, sum((select count(*) from jsonb_array_elements(paths) p where (p->>'selected')::boolean)) as selected from ideas.issue_hypotheses where as_of = current_date;`
- `select count(*) filter (where last_seen = current_date) as signals_today from ideas.weak_signals;` 와 `select thesis_key, title from ideas.theses where scale='micro' and created_at::date = current_date;`
- `select ops.put_agent_run('{"task":"discover","status":"succeeded","rows":<경로 이슈 수 + 새 테제 수>,"counts":{"issues":…,"paths":…,"selected":…,"left_in_queue":…,"signals":…,"micro_new":…,"graph_nodes":…,"pr":"…","skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`

## F. 보고와 알림
- 보고 6줄 이내: 이슈 경로(큐 N → 이슈 N·경로 N·후보 N) · 오늘 출처와 약한 신호 N(새 것·승격) · **새 작은 테제 (제목 · primary · 크기 · weakest_link)** · 그래프에 더한 기업 · PR 병합 여부 · 남은 큐.
- 알림은 실패했을 때만 (공통 §G). 새 테제는 verify 의 하루 알림에 들어간다.
