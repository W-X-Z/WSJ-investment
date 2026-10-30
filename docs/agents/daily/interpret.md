# interpret (06:17, 월~토) — 새 단서를 읽고 해석해 투자 아이디어 초안을 쓴다 (ADR-0028)

예약작업 "WSJ 2/4 해석 (06:17)" 이 따른다 (작업명 `interpret`). 공통 규칙 `docs/agents/daily-ideas.md` §0·§B 로 시작하고 끝낸다 (앞 작업 collect 를 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ops.put_agent_run`. 저장소는 §5 의 경로만.
시간 상자: 전체 60분. 단서 읽기 15분 · 해석과 초안 35분 · 그래프 패치·기록 10분.

**이 작업이 시스템의 중심이다.** 시장이 아직 읽지 않은 작은 단서를 찾아, 그것이 어느 회사의 무엇을 얼마나 바꾸는지 해석한다.
의미 있는 단서가 없으면 아무것도 쓰지 않는다 — 개수가 목표가 아니다.

## 1. 읽을 것
- **해석 지침**을 먼저 끝까지 읽는다: `research/playbook/README.md`·`lenses.md`, 그리고 `research/playbook/patterns/` 의 패턴 카드 전부. 작성 규칙 `docs/agents/writing.md`.
- **새 단서** (지난 실행 이후):
  - 단서 저장소가 있으면 (`select to_regclass('public.v_clues') is not null;`): `select * from public.v_clues where seen_at > now() - interval '30 hours' order by seen_at desc;`
  - 없으면(2단계 전): 기업 소식 `select event_id, company_id, kind, published_at, title, url, publisher, text from public.v_company_events where published_at > now() - interval '2 days' order by published_at desc;`
    와 새 이슈 `select issue_key, title, summary, nodes, companies, sources, latest_published_at from public.v_supply_chain_issues where first_seen > now() - interval '2 days';`
  - 최근 약한 신호: `select signal_key, term, mechanism, consumes_more, mapped_node, sources, last_seen from public.v_weak_signals where last_seen > current_date - 7;`
  - 시세·특징주·자동 요약은 읽지 않고 버린다.
- **지금 아이디어**: `select opportunity_key, title, stars, companies, nodes, status, updated_at from ideas.opportunities where status in ('draft','active') order by updated_at desc;` — 같은 회사·같은 이야기면 새로 만들지 않고 그것을 고친다.
- **그래프**: `research/ecosystems/seed_graph.json` 과 `node_aliases.json`. 그래프에서 기업·노드 이웃을 찾을 때는 Python 으로 읽는다 (예: `json.load` 후 간선을 from/to 로 거른다).

## 2. 고르기
- **작은 단서를 먼저 본다** (공통 §B): 제품 출시·시연, 협약·공동개발, 샘플·인증, 초도 수주, 협력사 명단, 전시회, 채용, 특허·논문, 소형사 증설, 업계 소문.
  **공시·실적은 후행 데이터다 — 맨 나중에 본다** (사용자, 2026-10-30). `source_kind` 가 `disclosure` 인 단서는 작은 단서를 다 읽고 시간이 남을 때만,
  그것도 이미 있는 아이디어를 고치는 데만 쓴다 (예: 공급계약 공시가 나오면 그 회사의 아이디어를 갱신). 공시에서 새 아이디어를 시작하지 않는다.
- 큰 회사 뉴스는 그 자체보다 **두 단계 아래** — 그 회사의 공급사·장비사·소재사 중 미국·한국 소·중형사에게 무엇을 뜻하나로 읽는다. 시장이 읽는 것은 헤드라인 기업이다.
- 고르는 기준은 하나: "이 단서가 어느 회사의 매출·이익을 시장이 아직 모르게 바꾸는가." 그렇다고 볼 이유가 없으면 넘긴다.

## 3. 해석 (단서마다)
1. **원문을 연다** (WebFetch). 필요하면 키워드 검색으로 따라간다 — 같은 사건의 다른 보도, 그 회사의 고객·공급사·경쟁사 쪽 보도(스커틀벗). 키워드 검색은 단서를 따라가는 도구다.
2. **이미 아는 것을 꺼낸다**: `cd pipeline && .venv/bin/python -m wsj.ecosystems.recall --company company:… --name "<기업명>" --text "<단서 제목>"`
   — 그래프 자리(이 회사가 파는 것 → 누가 왜 쓰나 위로 두 단계 → 같이 파는 회사, 노드면 아래로 두 단계의 미국·한국 공급사), 관련 패턴 카드, 지난 아이디어, 같은 기업·노드의 지난 단서, 가격, 그리고 논문·특허(노드별 연도 흐름 · 최근 많이 낸 곳과 새로 나타난 곳 · 대표 문서)가 한 장으로 나온다.
   논문·특허는 기술이 매출보다 몇 년 먼저 움직이는 곳을 보여 준다 — 새로 나타난 출원인, 갑자기 늘어난 노드는 그 자체로 단서다. 건수는 판단 기준이 아니라 재료다.
   내린 사례도 본다: `select title, status_note, updated_at from ideas.opportunities where status = 'dropped' and (nodes && array['<노드>'] or companies @> '[{"company":"<id>"}]') order by updated_at desc limit 10;`
   **지난 단서와 이어지는 이야기인가**를 본다 — 횟수가 아니라 같은 변화가 다른 출처(고객·공급사·경쟁사 쪽)에서도 보이는지.
   **없는 고리는 §5 에서 그래프에 더한다** (누적). 원문이 있으면 그 근거로, 추론뿐이면 `hypothesis` 등급으로. 세대 전환이 부품의 대당 함량(층수·면적·개수·등급)을 늘리면 `raises_content` 관계로.
3. **렌즈** (`lenses.md`)에서 그 단서에 맞는 것만 골라 생각한다: 매출 분해 · 병목과 이익 이동 · 대체 · 파이 · 단서의 다른 설명 · 부족기 증폭 · 시장 기대 · 누가 지키나. 관련 패턴 카드가 있으면 그 사례와 **반대 신호**를 먼저 대 본다.
4. **누구인가**: 이 변화가 **매출에서 가장 큰 비중**을 차지하는 미국·한국 상장사를 primary 로 (소·중형 먼저). 그래프 밖 회사여도 된다(§5 에서 더한다). 관련 회사는 role=related.
5. **가격**: 있으면 `select * from public.v_price_context where ticker = '…';`(미국 `RMBS`, 한국 `KRX:007660`·`KOSDAQ:…`), 없으면 기사. 같은 이야기로 이미 크게 오른 회사는 ★ 를 낮게 매기거나 쓰지 않는다.

## 4. 초안 쓰기
`select ideas.put_opportunities($j$[{…}]$j$::jsonb);`
```json
{"opportunity_key": "isu_petasys_tpu_v8_mlb",           // 영문 소문자·숫자·_ (회사_이야기)
 "title": "구글 TPU v8 고다층화에 따른 이수페타시스 기판 매출 확대", // writing.md 제목 규칙
 "stars": 3,                                              // 잠정 — report 가 다시 본다
 "idea": "3~5문장 (writing.md)",
 "interpretation": "결론 문장 2~5개 (렌즈 이름 없이)",
 "companies": [{"company": "company:isu_petasys", "name": "이수페타시스", "ticker": "007660", "exchange": "KRX", "role": "primary"}],
 "evidence": [{"title": "…", "url": "https://…", "date": "YYYY-MM-DD", "publisher": "…"}],
 "nodes": ["product:google_tpu_system", "component:mlb_pcb"],   // 지나는 그래프 노드 (화면 묶음용)
 "clue_refs": [{"title": "…", "url": "https://…", "date": "YYYY-MM-DD"}],  // 출발 단서
 "status": "draft", "model": "claude-…"}
```
- 같은 회사·같은 이야기의 기존 아이디어가 있으면 그 key 로 다시 보낸다(근거를 더하고 ★ 를 다시 매긴다). 이미 active 면 status 를 보내지 않는다(그대로 유지).
- 그래프 밖 회사는 `company` 를 `null` 로 두고 name·ticker·exchange 를 쓴다 — §5 에서 그래프에 더하면 다음 날부터 id 로.

## 5. 그래프와 패턴에 더하기 (바뀐 것이 있을 때만)
- **패턴 카드**: 오늘 해석이 기존 패턴에 들어맞으면 그 카드의 '사례' 줄에 아이디어 key·날짜를 더한다. 새 메커니즘이면 `research/playbook/patterns/<영문_이름>.md` 초안을 쓴다(형식은 `research/playbook/README.md`). 같은 PR 에 넣는다.
- 오늘 해석에서 그래프에 없던 고리·기업을 `research/ecosystems/patches/YYYYMMDD_interpret.json` 에 적는다 (형식은 `pipeline/wsj/ecosystems/graph_patches/from_json.py` 맨 위).
  기업은 상장사만(ticker·exchange·size_band micro|small|mid|large|mega), 간선마다 https 근거 1개 이상. 추론뿐인 고리는 tier `hypothesis`.
- `cd pipeline && .venv/bin/python -m wsj.ecosystems.graph_patches.from_json ../research/ecosystems/patches/YYYYMMDD_interpret.json && .venv/bin/python -m wsj.ecosystems.export_web && .venv/bin/python -m wsj.ecosystems.ontology --check`
- 브랜치 `auto/interpret-YYYYMMDD` → 커밋(끝에 `Co-Authored-By: Claude <noreply@anthropic.com>`) → PR(`gh api repos/W-X-Z/WSJ-investment/pulls -f base=main -f head=… -f title=… -F body=@…`, 본문 끝 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`).
  CI 를 최대 15분 기다리고(`gh api repos/W-X-Z/WSJ-investment/commits/<sha>/check-runs`), 모두 통과하고 바뀐 파일이 전부 `research/`·`apps/web/src/data/` 안이면 `gh api -X PUT repos/W-X-Z/WSJ-investment/pulls/<n>/merge -f merge_method=squash`.
  그 밖이 바뀌었거나 CI 가 실패하면 병합하지 않고 note 에 PR 링크. 강제 push 금지.

## 6. 기록과 보고
- `select ops.put_agent_run('{"task":"interpret","status":"succeeded|skipped","rows":<새 초안 + 갱신>,"counts":{"clues_read":…,"picked":…,"drafts_new":…,"drafts_updated":…,"graph_nodes":…,"graph_edges":…,"pr":"…","skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`
- 보고 5줄 이내: 읽은 단서 수 · 고른 단서와 이유 한 줄씩 · 새 초안 / 갱신한 아이디어(제목 · ★) · 그래프에 더한 것 · PR.
- 알림은 실패했을 때만 (하루 알림은 report 가 보낸다).
