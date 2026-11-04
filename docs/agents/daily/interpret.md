# interpret (05:17, 월~토) — 단서를 읽고 해석해 투자 아이디어 초안을 쓴다 (ADR-0028)

예약작업 "WSJ 2/4 해석 (05:17)" 이 따른다 (작업명 `interpret`). `docs/agents/daily-ideas.md` 의 목적·방향·꼭 지킬 것을 먼저 읽고, §0·§B 로 시작하고 끝낸다 (앞 작업 collect 를 기다린다).
쓰는 함수: `ideas.put_opportunities`, `ideas.put_thread`, `ops.put_agent_run`. 저장소는 아래 '그래프와 참고 자료'의 경로만. 끝나는 기준은 시간이 아니라 판단이다.

## 맡은 일
시장보다 먼저 볼 수 있는 단서를 골라, 그것이 어느 회사의 무엇을 얼마나 바꾸는지 해석하고, 시장의 믿음과 다르게 볼 근거가 서는 것만 초안으로 쓴다.
무엇을 읽고, 몇 개를 고르고, 어떤 순서로 생각하고, 어디까지 조사할지는 그날의 단서를 보고 판단한다. 초안은 근거가 설 때만 쓴다.
- 고른 단서는 판단까지 간다 — '확인 필요'나 '오늘은 고리를 세우지 못했다'로 끝내지 않는다. 조사해도 남는 것은 지금의 증거와 추론으로 판단하고 가장 약한 고리를 적는다. 그 판단과 근거는 스레드에 남겨 다음 세션이 이어받는다 (`daily-ideas.md` §C).
- 열린 스레드도 본다 — 검토자가 질문을 고친 것, 오늘 단서가 약한 고리에 닿는 것부터. 이어서 판단을 고치고, 초안이 되면 초안을 쓴다.
- 건너뛴 단서는 하나씩 이유를 `skipped` 에 남긴다 — 검토자가 다시 본다. 내릴 때의 기준은 `daily-ideas.md` 방향의 '시장의 믿음과 우리 근거'.

## 쓸 수 있는 재료
필요한 것을 골라 쓴다. 여기 없는 원본(federalregister.gov, JEDEC·OCP·OIF, arXiv, 회사 IR, 고객·경쟁사 발표)을 직접 찾아도 된다.
- 단서와 본문: `select c.url, c.title, c.source_name, c.extra->>'layer' as layer, c.extra->>'scope' as scope, c.note, c.companies, c.nodes, c.published_at, left(t.body, 3000) as body from ideas.clues c left join ideas.clue_texts t on t.url = c.url where c.relevant and c.seen_at > now() - interval '30 hours' order by (c.extra->>'layer' = 'raw') desc, c.seen_at desc;`
  층(layer): raw(표준·규칙·학회·논문·정책·릴리스 노트 — 원본) · press(업계지) · newsroom · company(기업 이름으로 모은 소식) · disclosure · issue.
  범위(scope): core(AI 데이터센터 공급망과 그것에 닿는 수요) · frontier(그래프 밖 산업 — 로봇·피지컬 AI·우주·전력기기 등). frontier 도 같은 기준으로 판단한다 — 그래프에 자리가 없다는 것은 내릴 이유가 아니다 (`daily-ideas.md` 방향 '산업을 정하지 않는다').
  원본 페이지(표준 위원회 문서 목록·규칙 개정·회의 자료·사양 페이지)는 바뀐 것만 들어온다 — 새 문서·새 항목은 그 링크가, 본문 변화는 '… 페이지 변경' 단서(주소 끝 `#changed-…`, 본문 = 새로 생긴 줄)가 된다.
- 열린 스레드: `daily-ideas.md` §C
- 그래프 조회(글 → 노드, 이웃, 아래로 내려가며 공급사, 노드 한 장): `daily-ideas.md` §D. 0035 전이면 아래 recall 을 쓴다.
- 기업 소식·이슈: `public.v_company_events`, `public.v_supply_chain_issues` (`v_weak_signals` 는 옛 작업이 쓰던 것으로 10-29 뒤 갱신이 없다 — 사전 밖 용어는 그래프 제안 term 으로 들어온다)
- 논문·특허 흐름: `public.v_tech_rising`, `public.v_tech_orgs`, `public.v_tech_docs`
- 가격: `select * from public.v_price_context where ticker = '…';` (미국 `RMBS`, 한국 `KRX:007660`·`KOSDAQ:…`)
- 입구는 둘이다 — (a) 단서 우선: 오늘 원본 단서 → 메커니즘 → 회사. (b) 가격 우선: 낙폭·병목·노출도에서 출발해 "시장이 틀렸나"를 묻는다. 주는 (a)이고, (b)는 최근 주가 이슈와 우리 근거를 견주는 데 쓴다. 초안·스레드에 어느 입구인지 적는다 (11-03 대화: (b)만으로는 목적의 '시장보다 먼저'가 되지 않았다).
  (b) 의 재료 한 줄: `select n.id, n.ecosystem, round(cf.market_cap_usd/1e6) mcap, p.r3m, p.r12m, p.from_high, (select string_agg(distinct e.src, ', ') from core.graph_edges e where e.dst = n.id and e.relation = 'offered_by') sells from core.graph_nodes n join public.v_company_facts cf on cf.company_id = n.id left join public.v_price_context p on p.ticker = n.ticker where n.kind = 'company' and n.exchange in ('NYSE','Nasdaq','NYSE American') and cf.market_cap_usd between 1e8 and 1.5e10 order by p.from_high asc nulls last limit 40;` — 여기에 `ideas.exposure_facts` 의 매출 구성을 겹친다.
- 지금 아이디어와 내린 아이디어: `select opportunity_key, title, stars, companies, nodes, status, status_note, updated_at from ideas.opportunities order by updated_at desc limit 50;`
- 그래프 한 장 보기: `cd pipeline && .venv/bin/python -m wsj.ecosystems.recall --company company:… --node <id> --name "<기업명>" --text "<단서 제목>"` — 그래프 자리, 같이 파는 회사, 관련 패턴 카드, 지난 단서·아이디어, 가격, 논문·특허가 나온다. 그래프 파일은 `research/ecosystems/seed_graph.json`·`node_aliases.json`.
- 참고 자료: `research/playbook/` (렌즈·패턴 카드·사용자 지적 기록). 규칙이 아니라 기억이다.
- 시장 배경: `research/macro/` 의 가장 최근 장 (주간 개선이 매주 쓴다 — 소형주 환경·금리·반도체 사이클·전력). '시장이 이미 가격에 넣었나'를 볼 때의 배경일 뿐, 아이디어의 근거는 회사 원문이다.

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
 "history": [{"date": "YYYY-MM-DD", "title": "일어난 일 한 줄", "body": "자세히 (선택)", "url": "https://… (선택)"}],   // writing.md 히스토리 — 차트의 점
 "nodes": ["product:google_tpu_system", "component:mlb_pcb"],
 "clue_refs": [{"title": "…", "url": "https://…", "date": "YYYY-MM-DD"}],
 "status": "draft", "model": "claude-…"}
```
- 같은 회사·같은 이야기의 아이디어가 이미 있으면 그 key 로 다시 보낸다. 이미 active 면 status 를 보내지 않는다.
- 그래프 밖 회사는 `company` 를 `null` 로 두고 name·ticker·exchange 를 쓴다.

## 그래프와 참고 자료에 쌓기 (알게 된 것이 있을 때)
해석이 매번 같은 것을 다시 찾지 않도록, 확인한 사실은 그래프에 남긴다.
- `research/ecosystems/patches/YYYYMMDD_interpret.json` (형식은 `pipeline/wsj/ecosystems/graph_patches/from_json.py` 맨 위). 기업은 상장사만(ticker·exchange·size_band), 간선마다 https 근거 1개 이상, 추론뿐인 고리는 tier `hypothesis`.
  미국 공시 기업의 매출 구성 숫자(차원별 매출 pct·고객 집중도·'매출의 N%' 문장)는 이미 `ideas.exposure_facts` 에 있다 — 조사하는 회사면 먼저 본다 (`select kind, label, pct, period_end, url from ideas.exposure_facts where company_id = '<id>' and kind <> 'none' order by kind, pct desc nulls last;`).
  공급사의 매출 비중·자리를 확인했으면 `offered_by` 간선에 `exposure_pct`·`exposure_year`·`exposure_source`(원문 숫자가 있을 때) 또는 `exposure`(core·major·minor)와 `position`(leader·second_source·entrant·captive), 누가 누구에게 납품하는지 확인했으면 `supplied_to` + `about`.
  이미 있는 노드에 표준 번호·특허 분류·규칙 번호(`codes`), 근거상 처음 나온 날(`first_evidence`), 단계 전환(`maturity`)을 더하려면 `node_updates`. 규칙과 그것을 정한 곳은 `rule`·`authority` 노드와 `mandates`(시행일 `effective_date`)·`issued_by` 간선 (온톨로지 v0.5, ADR-0031).
- 다른 작업이 남긴 그래프 제안(pending)도 오늘 패치에 합친다 — 근거를 다시 열어 맞는 것만: `select proposal_id, kind, payload, reason, by from ideas.graph_proposals where status = 'pending' order by proposal_id;` 결과를 파일로 두고 `.venv/bin/python -m wsj.ecosystems.graph_patches.from_proposals <파일> --prefix p<MMDD> --out ../research/ecosystems/patches/YYYYMMDD_proposals.json`. 들이지 않을 제안은 `update ideas.graph_proposals set status = 'rejected', note = '…' where proposal_id = …;`. 병합되면 graph-sync 가 applied 로 바꾸고 DB 조회본을 맞춘다.
  수집기가 올린 제안(`by = 'collect'`)은 판단 없이 찾기만 한 것이다 — 합치기 전에 확인한다:
  · 그래프 밖 상장사 후보(kind `node`, status `candidate`): 분류기가 적은 티커·거래소가 맞는지, 그래프에 다른 시장 상장으로 이미 있는지(`select * from core.resolve_terms('<이름>', 5);`) 보고, `size_band` 를 채운다 — 기억으로 정하지 말고 `select market_cap_usd, price_as_of from public.v_company_facts where company_id = '<id>';` (그래프에 들어간 다음 수집부터 생긴다. 아직 없으면 unknown). 구간: micro < $3억 · small < $20억 · mid < $100억 · large < $2,000억 · mega. DB 조회본(`core.graph_nodes.size_band`)은 graph-sync 가 매일 시가총액으로 다시 매기므로 그래프 파일 값이 낡아도 조회는 맞다. 공급망과 무관하거나 이미 있으면 rejected. 들이면 기업 소식·가격·재무 수집 대상이 된다.
  · 사전 밖 식별자(kind `term`): 기존 노드의 `codes`(node_updates)나 별칭(aliases)이면 그쪽으로 옮겨 적고, 새 개념이면 근거 1개로 후보 노드(`status: candidate`)를 만들고, 의미 없는 말이면 rejected. term 제안 자체는 패치가 되지 않으니 처리한 뒤 `status = 'applied'`(또는 rejected)와 note 를 직접 적는다.
  시간이 모자라면 남겨 둔다 — 주간 개선이 묵은 것을 정리한다.
- 패턴 카드(`research/playbook/patterns/`, 형식은 그 폴더 README)는 반복해서 보인 메커니즘을 적는 기억이다. 오늘 아이디어 하나가 근거의 전부인 새 카드는 맨 위에 `상태: 가설` 을 적는다.
- `cd pipeline && .venv/bin/python -m wsj.ecosystems.graph_patches.from_json ../research/ecosystems/patches/YYYYMMDD_interpret.json && .venv/bin/python -m wsj.ecosystems.export_web && .venv/bin/python -m wsj.ecosystems.ontology --check`
- 브랜치 `auto/interpret-YYYYMMDD` → 커밋(끝에 `Co-Authored-By: Claude <noreply@anthropic.com>`) → PR(`gh api repos/W-X-Z/WSJ-investment/pulls -f base=main -f head=… -f title=… -F body=@…`, 본문 끝 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`).
  CI 를 최대 15분 기다리고(`gh api repos/W-X-Z/WSJ-investment/commits/<sha>/check-runs`), 모두 통과하고 바뀐 파일이 전부 `research/`·`apps/web/src/data/` 안이면 `gh api -X PUT repos/W-X-Z/WSJ-investment/pulls/<n>/merge -f merge_method=squash`. 그 밖이 바뀌었거나 CI 가 실패하면 병합하지 않고 note 에 PR 링크.

## 기록과 보고
- `select ops.put_agent_run('{"task":"interpret","status":"succeeded|skipped","rows":<새 초안 + 갱신>,"counts":{"clues_read":…,"picked":…,"drafts_new":…,"drafts_updated":…,"threads_opened":…,"threads_continued":…,"threads_closed":…,"graph_nodes":…,"graph_edges":…,"pr":"…","skipped":[…],"denied":[…],"unverified":[…]},"note":"…"}'::jsonb);`
- 보고는 짧게: 무엇을 골랐고 왜, 새 초안·갱신(제목 · ★), 이어 판 스레드와 결론, 그래프에 더한 것, PR. 알림은 실패했을 때만.
