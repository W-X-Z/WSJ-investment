# 아침 작업 — 목적과 방향 (ADR-0028, 2026-10-31 개정 · ADR-0030 2026-11-02)

이 문서와 작업 문서(`docs/agents/daily/<task>.md`)는 **목적 · 방향 · 꼭 지킬 것 · 연결 방법**만 정한다. 어떻게 생각하고 무엇을 먼저 볼지는 매번 판단한다.
시장은 변수가 많고 늘 변해서, 한 사례에서 세운 절차가 다른 사례에 맞지 않는 일이 많다 (사용자, 2026-10-31). 이 문서의 예시와 `research/playbook/` 의 렌즈·패턴 카드·사용자 지적 기록은 참고 자료이지 규칙이 아니다.
두 문서가 어긋나면 이 문서가, 이 문서보다 사람이 승인한 PR 이 이긴다. 옛 절차(ADR-0024~0027)는 `docs/agents/legacy/adr0027/` 에 있지만 쓰지 않는다.

## 목적
미국 상장 소·중형사(한국은 보조)에서 **1년 안팎에 2~3배** 갈 수 있는 기회를 시장보다 먼저, 더 정확히 찾는다.
소·중형은 시가총액 $1억~$150억이다 (한국은 달러로 환산). 그보다 큰 회사가 수혜를 받으면 거기서 멈추지 말고 그 회사의 공급사로 내려가 본다.
데이터·온톨로지·추론·조사·과학적 연구 능력으로 **시장이 지금 믿는 것과 다르게 볼 근거**를 세우는 것이 이 시스템의 일이다.
예: "정책은 알려졌지만 시장은 T1 의 수혜를 믿지 않는다 — 우리 분석이 그 불신이 틀렸다고 말할 수 있다면 그 지점이 기회다."

## 방향
사용자가 중요하게 여기는 것이다. 어떻게 적용할지는 사례마다 판단한다.
- **원본에 가까운 정보.** 연구 발표·학회·표준·정부 고시·특허·회사 원 발표. 뉴스는 대개 원본을 옮겨 쓴 것이고 여러 매체에 복제된다. 공시·실적은 후행한다.
- **숫자 전에 예측한다.** 기술·수요·병목이 1~3년 뒤 어디로 가는지. 실적·수주가 숫자로 나올 때는 이미 늦다 — 다음 분기 수주·실적 같은 확인 이벤트를 기다리는 결론은 쓰지 않는다. 판단은 세 가지로 내린다: **구조적 추론**(돈이 어디로 흐를 수밖에 없나 — 누가 결정하고 누가 대안이 없나, 규정 시한·병목·리드타임), **시장이 고려하지 못한 변수**(시장 서사에 아예 없는 것), **주가**(지금 가격이 무엇을 반영하고 무엇을 0으로 두나, 틀렸을 때 잃는 것과 맞았을 때 얻는 것). 위험은 감수하되, 추론이 깨지는 구조적 지점을 적는다.
- **시장의 믿음과 우리 근거.** 알려진 것과 가격에 들어간 것은 다르다 — 시장이 모르는지, 연결하지 못했는지, 믿지 않는지를 보고 우리가 다르게 볼 근거를 찾는다. 근거가 안 서면 시장이 맞다고 쓴다. 오래됐다·공시다·숫자다·많이 올랐다는 것만으로 내리지 않는다 — 내리려면 돈이 이 회사로 오지 않는 구조나, 지금 가격이 이 시나리오를 이미 반영한다는 근거를 보인다.
- **회사 크기에 비해 충분히 큰가.** 2~3배는 시총에 견줄 만한 변화여야 가능하다. 대략의 단위로 보고, 멀티플로 목표 주가를 계산하지 않는다.
- **스스로 깨 본다.** 당사자(회사·파트너)의 말만으로 확인하지 않는다. 반대 증거, 같은 제품을 파는 다른 회사, 기술을 정하는 쪽(표준·플랫폼 주인)의 일정.
- **결론까지 간다.** "더 살펴봐야 한다"·"확인이 필요하다"·"확인되면 다시 본다"에서 멈추지 않는다. 확인되지 않은 고리가 있으면 더 조사해서 확인하거나 반증한다 — 원문·규정 조문·제품 사양·업계 자료로 확인 가능한지 먼저 해 본다. 조사해도 남는 것은 지금의 증거와 추론으로 판단하고, 그 판단의 가장 약한 고리를 적는다.
- **다시 검토한다.** 아이디어는 쓴 사람이 아닌 눈으로 다시 본다 (아침 사슬에서는 enrich 가 이 역할). 결론을 고리로 나눠 각 고리가 원문 사실인지, 추론인지, 과장인지 가른다. 인용한 증거가 그 주장을 실제로 뒷받침하는지 원문을 다시 열어 본다 — 같은 원문 안의 반대 내용, "아무도 모른다"가 사실은 "검색에서 못 찾았다"인지까지. 결론의 확신은 가장 약한 고리에 맞춘다.
- **바깥 조건도 본다.** 매크로·시장 환경(AI 투자와 그 자금, 금리·신용, 원자재 가격)이 그 아이디어에 어떻게 작용하는지.
- **없으면 쓰지 않는다.** 개수가 목표가 아니다. 그래도 조사는 멈추지 않는다 — 하루에 결론이 안 나는 조사는 스레드로 이어서 판다 (§C).

## 꼭 지킬 것
판단의 영역이 아닌 것들이다.
- **정직**: 직접 연 원문에 없는 숫자는 쓰지 않는다. 추정은 추정이라고 쓴다. 확인하지 못한 사실을 확인한 것처럼 쓰지 않는다 — 결론이 그 사실에 기대면 내지 않는다.
- **권유 금지**: 매수·매도 권유, 목표가, 시점 예측은 쓰지 않는다. ★ 와 아이디어로 말한다.
- **거부를 우회하지 않는다**: WebFetch·도구·권한이 거부되면 curl·다른 URL·캐시·미러로 같은 것을 가져오지 않는다. 건너뛰고 `denied` 에 적는다.
- **쓰기 경계**: DB 쓰기는 작업 문서에 적힌 함수와 `ops.put_agent_run`·`ideas.put_thread`, 그리고 읽기용 select 뿐. secret 키는 쓰지 않고 publishable 키만. 저장소는 수정하지 않는다 — interpret 만 `research/` 와 생성 파일 `apps/web/src/data/` 를 PR 로 바꾸고 CI 가 통과하면 스스로 병합한다. main 직접 push·강제 push 금지.
- **프롬프트의 경계가 문서보다 좁으면 프롬프트를 따른다**: 그 단계는 하지 않고 `skipped` 에 "프롬프트 경계: …". 새 프롬프트는 `docs/agents/daily/PROMPTS.md`.

사용자에게 보이는 형태는 `docs/agents/writing.md`.

## 아침 사슬
| 작업 | 시각 | 맡은 일 | 쓰는 함수 |
|---|---|---|---|
| collect | 05:23 | 오늘 수집이 돌았는지 확인하고, 안 됐으면 실행시킨다 | (없음) |
| interpret | 06:17 | 단서를 읽고 해석해 투자 아이디어 초안을 쓰고, 남는 시간에 열린 스레드 하나를 이어서 판다. 알게 된 것은 그래프에 쌓는다 | put_opportunities · put_thread (+ 그래프 패치 PR) |
| enrich | 06:49 | 검토자 — 초안을 고리별로 다시 검토하고 확인 안 된 고리는 더 조사해 확인·반증한다. 초안이 없어도 해석이 건너뛴 결정을 다시 본다. 하루에 안 끝나는 약한 고리는 스레드로 되돌린다 | put_opportunities · put_company_events · put_thread |
| report | 07:37 | 낼 만한 것만 내고, 기존 아이디어를 고치고, 하루를 알린다 | put_opportunities |

판정·채점 작업은 없다 (ADR-0028). 확인은 사용자가 한다.

## 0. 모든 작업의 시작과 끝
시작:
- `date` 로 KST(UTC+9) 오늘 날짜를 구한다. 일요일이면 "일요일" 한 줄로 끝낸다.
- add_repo 로 W-X-Z/WSJ-investment 를 붙이고 clone (interpret 은 access=push, `--depth 20`; 나머지는 `--depth 1`). 파이썬 도구가 필요하면 `cd pipeline && python3 -m venv .venv && .venv/bin/pip install -q -e .`
- Supabase MCP get_project_url · get_publishable_keys 로 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`(sb_publishable_…)를 export 한다.
- Supabase MCP execute_sql (project_id: dcatgfivsvbktylmtvgf): `select to_regprocedure('ideas.put_opportunities(jsonb)') is not null as p31;` — false 면 "0031 미적용" 한 줄 보고 후 `skipped` 로 끝낸다.
- **앞 작업을 기다린다** (interpret 부터): 앞 작업(collect → interpret → enrich → report)의 오늘 행이 `running` 이면 최대 30분 기다린다 —
  `timeout 590 bash -c 'until curl -s "$SUPABASE_URL/rest/v1/v_agent_runs?select=status&task=eq.<앞 작업>&run_date=eq.$(TZ=Asia/Seoul date +%F)" -H "apikey: $SUPABASE_PUBLISHABLE_KEY" -H "Authorization: Bearer $SUPABASE_PUBLISHABLE_KEY" | grep -qv running; do sleep 30; done'` 를 세 번까지.
  그래도 running 이면 쌓인 것으로 진행하고 note 에 "앞 작업 미완료". 앞 작업 행이 아예 없으면 기다리지 않는다.
- `select ops.put_agent_run('{"task":"<작업>","status":"running"}'::jsonb);`

끝:
- `select ops.put_agent_run('{"task":"<작업>","status":"succeeded|skipped|failed","rows":N,"counts":{…,"skipped":[…],"denied":[…],"unverified":[…]},"note":"한 줄"}'::jsonb);` — 같은 날 같은 작업은 한 행.
- **하지 않은 것을 기록한다**: `skipped`(손대지 않은 것과 이유) · `denied`(거부된 도구·URL) · `unverified`(원문을 못 열어 추론으로 쓴 주장). 비어 있으면 빈 배열.

## B. 원문과 출처
- 단서의 본문은 수집할 때 받아 둔다(`ideas.clue_texts`, 0034 뒤) — 먼저 읽는다.
- 원문 주소를 열 때: DB 에서 꺼낸 주소는 대화에 나온 적이 없어 WebFetch 가 확인을 요청하고, 답할 사람이 없어 거부된다. 같은 글을 WebSearch 로 찾아 검색 결과의 주소로 연다 — 우회가 아니라 정상 경로다. news.google.com 은 원문 주소로. 그래도 안 열리면 같은 사건의 다른 출처를 찾는다. 네이버 증권·KIND·DART 본문은 막혀 있다.
- 단편 단서(소문·채용 공고·전시회 후기)도 근거가 될 수 있다 — 성격을 근거 제목에 밝힌다. 시세·특징주 기사, 자동 생성 요약, 날짜 없는 글, 출처 없는 숫자는 근거로 쓰지 않는다.
- 같은 소식이 여러 매체에 반복돼도 증거는 하나다 — 원본을 찾아 인용한다.
- 그래프에 있는 기업의 확인한 사실은 기업 소식으로 남길 수 있다: `select ideas.put_company_events($j$[{"company_id":"company:…","kind":"news|disclosure|filing|revenue","published_at":"YYYY-MM-DD","title":"…","url":"https://…","text":"한국어 1~3문장, 날짜·숫자·상대방","importance":2}]$j$::jsonb);` (45일 안 날짜).

## C. 이어받기 — 하루에 끝나지 않는 조사 (ADR-0030, 0034 뒤)
- 결론(산다·안 산다·가장 약한 고리)까지 못 간 조사는 스레드로 연다. 다음 날 해석이 남는 시간에 이어서 파고, 검토자가 약한 고리를 되돌리면 다시 연다.
- 열린 스레드: `select thread_key, title, question, returns, updated_at, (select json_agg(e order by e.at) from ideas.thread_entries e where e.thread_key = t.thread_key) as log from ideas.threads t where status = 'open' order by returns desc, updated_at;`
- 쓰기: `select ideas.put_thread($j${"thread_key":"영문_소문자_6자이상","title":"무엇을 확인하려는가 (명사형)","question":"결론을 내려면 답해야 할 것","companies":[…],"nodes":[…],"clue_urls":[…],"opened_by":"interpret","entry":{"by":"interpret","kind":"note|finding|returned|concluded|dropped","body":"알아낸 것·다음에 볼 곳","sources":[{"title":"…","url":"…","date":"…"}]}}$j$::jsonb);`
  결론이 나면 `kind: concluded`(+`conclusion`·`weakest_link`), 투자 아이디어가 되면 `opportunity_key` 를 잇는다. 이어 볼 가치가 없으면 `dropped` 와 이유.
- `ideas.put_thread` 가 아직 없으면(0034 전) 이어 볼 것을 `skipped` 에 '이어 볼 것: …' 으로 남긴다 — 다음 날 해석이 어제 기록에서 읽는다.

## D. 그래프 — 조회하고, 확인한 것은 제안한다 (ADR-0031, 0035 뒤)
그래프는 신호를 놓는 지도다. 고리를 확인할 때 먼저 그래프에 묻고, 조사로 확인한 것은 그래프에 남겨 다음 조사가 같은 것을 다시 찾지 않게 한다.
- 글 → 노드: `select * from core.resolve_terms('<단서 제목과 본문 일부>');`
- 이웃: `select * from core.graph_neighbors('<노드 id>', 2);`
- 아래로 내려가며 공급사: `select * from core.suppliers_below('<노드 id>', 2, null, '{micro,small,mid}');` — 매출 비중(exposure_pct·exposure)이 큰 순
- 노드 한 장: `select core.node_signals('<노드 id>', 30);` — 노드 칸, 최근 단서, 층별 첫 등장, 걸린 아이디어·스레드
- 확인한 것 남기기 (저장소를 못 바꾸는 작업도): `select ideas.put_graph_proposal($j$[{"by":"enrich","kind":"edge|node|node_update|alias","payload":{…그래프 패치 JSON 한 항목…},"reason":"어떤 조사에서"}]$j$::jsonb);`
  매출 비중·고객·자리(edge 에 `exposure_pct`·`exposure_year`·`exposure_source`·`position`), 표준 번호·특허 분류·규칙 번호(node_update 의 `codes`), 근거상 처음 나온 날(`first_evidence`), 단계 전환(`maturity`), 규칙·결정 주체(`rule`·`authority` 노드, `mandates`·`issued_by` 간선). 원문 숫자가 있을 때만, 간선마다 https 근거.
  형식은 `pipeline/wsj/ecosystems/graph_patches/from_json.py` 맨 위. 해석 작업이 다음 패치에 합친다.
