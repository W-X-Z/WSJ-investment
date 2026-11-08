# 저장 — 원천 · 산업 그래프 · 리서치 리포트 (ADR-0034)

지식 구조는 세 개뿐이다. 가격·상장사 목록·환율·금리는 지식이 아니라 **조회 도구**(`python -m wsj tools …`)가 맡는다. 실행 기록은 예약 작업 이력과 리포트로 충분하다.

## 쓰는 순서
**사실(원천) → 연결 제안(그래프) → 리포트 → 노션.** 중간에 끊겨도 앞에서 저장한 것은 다음 실행이 다시 쓴다.

## 1. 원천 — 바깥에서 들어온 것만
- 테이블: `ideas.clues`(+ 본문 `ideas.clue_texts`). 뉴스·업계지·공시·분기보고서·정책·논문, 그리고 **에이전트가 웹 검색으로 찾은 원문**까지 한 줄씩.
- 원문에서 뽑은 사실은 그 행의 `facts`(JSON 배열)에 둔다. 재무 공시 숫자도 그 공시 행의 사실이다.
- AI가 계산·추정한 숫자는 원천에 넣지 않는다 → 리포트로. (계산값이 공시 사실로 둔갑하는 것을 막는다.)

사실 하나의 모양:
```json
{"text": "연간 생산능력 5GW", "entity": "company:be", "value": 5, "unit": "GW/yr",
 "as_of": "2026-09-30", "loc": "10-Q p.32", "by": "fundamental:2026-11-09"}
```
`text` 만 필수. `entity` 는 그래프 노드 id(company:…, segment:…).

쓰는 함수:
- 새 원문: `select ideas.put_research_sources('[{"url": "...", "title": "...", "published_at": "2026-11-04", "source_name": "SEC", "summary": "...", "facts": [ ... ]}]'::jsonb);` — 같은 URL이 있으면 사실만 합친다. 돌려받은 `clue_id` 를 리포트 `cites` 에 쓴다.
- 이미 있는 단서에 사실 추가: `select ideas.put_clue_facts('[{"clue_id": 812345, "facts": [ ... ]}]'::jsonb);` — 같은 text 는 건너뛴다.
- 재사용 조회 예: `select clue_id, url, f from ideas.clues, jsonb_array_elements(facts) f where f->>'entity' = 'company:be' order by f->>'as_of' desc;`

## 2. 산업 그래프 — 연결
- 테이블: `core.graph_nodes`, `core.graph_edges`. 기업 노드가 곧 기업 기준표다(티커·거래소·이름 변형).
- 노드 유형에 **산업 구간**(`segment:…`, 예: `segment:uranium_enrichment`)이 있다. 관계 종류와 숫자 항목은 고정하지 않는다 — 전방·후방 투입, 참여(매출 비중·점유율), 공급, 경쟁, 소유(지분율), 대체, 규제 등 필요한 것을 쓴다. 숫자는 관계의 `attrs`, 출처는 `evidence`.
- 에이전트는 그래프를 직접 고치지 않는다. 추론으로 얻은 연결은 제안으로 넣는다:
  `select ideas.put_graph_proposal('[{"kind": "edge", "payload": {"from": "company:be", "relation": "participates_in", "to": "segment:sofc", "tier": "official_issuer", "attrs": {"segment_share": 0.95}, "evidence": [{"url": "...", "title": "...", "date": "2026-11-04"}]}}]'::jsonb);`
  공식 발표 등급은 반영되고, 추론 등급은 검증 뒤 반영된다.

## 3. 리서치 리포트 — AI가 계산·해석·판단한 모든 것
- 테이블: `research.reports`, 읽기 `public.v_reports`. 쓰기 `select research.put_reports('[ ... ]'::jsonb);` (report_id 로 덮어쓰기).
- 공통 칸: `report_id`, `kind`(screen | industry | company | idea | verification), `title`, `subjects`(노드 id 배열), `as_of`(기준일), `body`(객체), `cites`(원천 clue_id 배열), `notion_url`, `created_by`. `kind = idea` 는 `stars`(1~5)와 `verdict`(한 줄 판단)가 필수.
- 리포트의 숫자에는 출처 clue_id 를 붙이고, 직접 계산한 숫자는 `"label": "계산값"` 과 입력값의 출처를 단다.

`body` 모양 (칸 이름은 권장, 내용에 맞게 늘이거나 줄인다):
```json
// industry — report_id "industry:<segment>:<as_of>"
{"segment": "segment:uranium_enrichment",
 "sections": [{"h": "수요와 공급", "text": "…", "cites": [812345]}],
 "key_facts": [{"text": "서방 SWU 현물 $200 유지", "as_of": "2026-10-31", "clue_id": 812345}],
 "counter_evidence": [{"text": "…", "clue_id": 812346, "as_of": "2026-11-02"}]}

// company — report_id "company:<ticker>:<as_of>"
{"company": "company:leu",
 "sections": [{"h": "실적·재무", "as_of": "2026-11-04", "text": "…", "cites": [ ... ]}],
 "key_facts": [{"text": "순현금", "value": 1.09, "unit": "$B", "label": "계산값", "inputs": [812400, 812401]}],
 "exposure": [{"segment": "segment:uranium_enrichment", "level": "실제 공급", "share": null}],
 "counter_evidence": []}

// idea — report_id "idea:<slug>:<as_of>"
{"conclusion": {"stars": 3, "verdict": "…"},
 "sections": [{"h": "…", "text": "…", "cites": [ ... ]}],
 "scenarios_12m": {"bear": {"value": "…", "basis": "…"}, "base": { }, "bull": { }},
 "catalysts": [{"date": "2026-12-31", "event": "…"}],
 "candidates": [{"company": "company:leu", "role": "수혜", "why": "…"}],
 "reused": ["industry:uranium_enrichment:2026-11-08"]}

// verification — report_id "verification:<idea slug>:<as_of>"
{"target": "idea:<slug>", "challenges": [{"claim": "…", "counter": "…", "cites": [ ], "weight": "결론을 바꿈|약화|무관"}],
 "unknowns": [{"what": "…", "impact": "…"}], "checklist_used": [ "…" ]}

// screen — report_id "screen:YYYY-MM-DD" (screen.md)
```

## 신선도 (꺼내 쓸 때 확인)
| 꺼내는 것 | 그대로 쓰기 | 보완 | 새로 |
|---|---|---|---|
| 산업 리포트 | 7일 안 | 7~30일: 그 뒤 원천만 보완 | 30일 초과 |
| 기업 리포트 | 섹션별 90일 안 | 그 사이 분기 공시·8-K가 있으면 그 섹션만 | 90일 초과 |
| 원천 사실 | 기준일 30일 안(전제 사실), 반박 근거 90일 안 | — | 재확인 |
| 재무 숫자 | 항상 코드가 최신으로 | — | — |
| 피어·평가 가정 | 출발점으로만 | 숫자는 현재 가격으로 다시 계산 | — |

## 노션
노션은 리포트의 읽기용 사본이다. 규칙은 [notion.md](notion.md).
