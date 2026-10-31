# interpret (06:17, 월~토) — 단서를 읽고 해석해 투자 아이디어 초안을 쓴다 (ADR-0028)

예약작업 "WSJ 2/4 해석 (06:17)" 이 따른다 (작업명 `interpret`). `docs/agents/daily-ideas.md` 의 목적·방향·꼭 지킬 것을 먼저 읽고, §0·§B 로 시작하고 끝낸다 (앞 작업 collect 를 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ops.put_agent_run`. 저장소는 아래 '그래프와 참고 자료'의 경로만. 시간은 60분 안팎.

## 맡은 일
시장보다 먼저 볼 수 있는 단서를 골라, 그것이 어느 회사의 무엇을 얼마나 바꾸는지 해석하고, 시장의 믿음과 다르게 볼 근거가 서는 것만 초안으로 쓴다.
무엇을 읽고, 몇 개를 고르고, 어떤 순서로 생각하고, 어디까지 조사할지는 그날의 단서를 보고 판단한다. 의미 있는 것이 없으면 아무것도 쓰지 않는다.

## 쓸 수 있는 재료
필요한 것을 골라 쓴다. 여기 없는 원본(federalregister.gov, JEDEC·OCP·OIF, arXiv, 회사 IR, 고객·경쟁사 발표)을 직접 찾아도 된다.
- 단서: `select * from public.v_clues where seen_at > now() - interval '30 hours' order by seen_at desc;` (`source_kind` 로 연구·표준·정책·업계지·기업 소식·공시를 구분)
- 기업 소식·이슈: `public.v_company_events`, `public.v_supply_chain_issues`, 약한 신호 `public.v_weak_signals`
- 논문·특허 흐름: `public.v_tech_rising`, `public.v_tech_orgs`, `public.v_tech_docs`
- 가격: `select * from public.v_price_context where ticker = '…';` (미국 `RMBS`, 한국 `KRX:007660`·`KOSDAQ:…`)
- 지금 아이디어와 내린 아이디어: `select opportunity_key, title, stars, companies, nodes, status, status_note, updated_at from ideas.opportunities order by updated_at desc limit 50;`
- 그래프 한 장 보기: `cd pipeline && .venv/bin/python -m wsj.ecosystems.recall --company company:… --node <id> --name "<기업명>" --text "<단서 제목>"` — 그래프 자리, 같이 파는 회사, 관련 패턴 카드, 지난 단서·아이디어, 가격, 논문·특허가 나온다. 그래프 파일은 `research/ecosystems/seed_graph.json`·`node_aliases.json`.
- 참고 자료: `research/playbook/` (렌즈·패턴 카드·사용자 지적 기록). 규칙이 아니라 기억이다.

## 초안 쓰기
`select ideas.put_opportunities($j$[{…}]$j$::jsonb);`
```json
{"opportunity_key": "isu_petasys_tpu_v8_mlb",           // 영문 소문자·숫자·_ (회사_이야기)
 "title": "구글 TPU v8 고다층화에 따른 이수페타시스 기판 매출 확대", // writing.md
 "stars": 3,                                              // 잠정 — report 가 다시 본다
 "idea": "writing.md 의 아이디어",
 "interpretation": "결론 문장 몇 개",
 "companies": [{"company": "company:isu_petasys", "name": "이수페타시스", "ticker": "007660", "exchange": "KRX", "role": "primary"}],
 "evidence": [{"title": "…", "url": "https://…", "date": "YYYY-MM-DD", "publisher": "…"}],
 "nodes": ["product:google_tpu_system", "component:mlb_pcb"],
 "clue_refs": [{"title": "…", "url": "https://…", "date": "YYYY-MM-DD"}],
 "status": "draft", "model": "claude-…"}
```
- 같은 회사·같은 이야기의 아이디어가 이미 있으면 그 key 로 다시 보낸다. 이미 active 면 status 를 보내지 않는다.
- 그래프 밖 회사는 `company` 를 `null` 로 두고 name·ticker·exchange 를 쓴다.

## 그래프와 참고 자료에 쌓기 (알게 된 것이 있을 때)
해석이 매번 같은 것을 다시 찾지 않도록, 확인한 사실은 그래프에 남긴다.
- `research/ecosystems/patches/YYYYMMDD_interpret.json` (형식은 `pipeline/wsj/ecosystems/graph_patches/from_json.py` 맨 위). 기업은 상장사만(ticker·exchange·size_band), 간선마다 https 근거 1개 이상, 추론뿐인 고리는 tier `hypothesis`.
  공급사의 매출 비중·자리를 확인했으면 `offered_by` 간선에 `exposure`(core·major·minor)·`position`(leader·second_source·entrant·captive), 누가 누구에게 납품하는지 확인했으면 `supplied_to` + `about`.
- 패턴 카드(`research/playbook/patterns/`, 형식은 그 폴더 README)는 반복해서 보인 메커니즘을 적는 기억이다. 오늘 아이디어 하나가 근거의 전부인 새 카드는 맨 위에 `상태: 가설` 을 적는다.
- `cd pipeline && .venv/bin/python -m wsj.ecosystems.graph_patches.from_json ../research/ecosystems/patches/YYYYMMDD_interpret.json && .venv/bin/python -m wsj.ecosystems.export_web && .venv/bin/python -m wsj.ecosystems.ontology --check`
- 브랜치 `auto/interpret-YYYYMMDD` → 커밋(끝에 `Co-Authored-By: Claude <noreply@anthropic.com>`) → PR(`gh api repos/W-X-Z/WSJ-investment/pulls -f base=main -f head=… -f title=… -F body=@…`, 본문 끝 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`).
  CI 를 최대 15분 기다리고(`gh api repos/W-X-Z/WSJ-investment/commits/<sha>/check-runs`), 모두 통과하고 바뀐 파일이 전부 `research/`·`apps/web/src/data/` 안이면 `gh api -X PUT repos/W-X-Z/WSJ-investment/pulls/<n>/merge -f merge_method=squash`. 그 밖이 바뀌었거나 CI 가 실패하면 병합하지 않고 note 에 PR 링크.

## 기록과 보고
- `select ops.put_agent_run('{"task":"interpret","status":"succeeded|skipped","rows":<새 초안 + 갱신>,"counts":{"clues_read":…,"picked":…,"drafts_new":…,"drafts_updated":…,"graph_nodes":…,"graph_edges":…,"pr":"…","skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`
- 보고는 짧게: 무엇을 골랐고 왜, 새 초안·갱신(제목 · ★), 그래프에 더한 것, PR. 알림은 실패했을 때만.
