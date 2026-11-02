# 출처 목록 (ADR-0028 2단계)

`registry.json` 은 단서 수집기(`python -m wsj.ecosystems.clues run`)가 매일 훑는 출처다. **키워드 검색이 아니라 출처가 입력이다** — 키워드로는 모르는 것을 찾을 수 없다.
수집기는 출처마다 지난 이틀의 새 글을 모두 받아, 시세·특징주·지분 변동 기사와 주제 밖 글만 버리고 `ideas.clues` 에 쌓는다. 해석 작업(06:17)이 `v_clues` 를 읽는다.

## 항목
```json
{"id": "thelec_kr", "name": "디일렉", "type": "rss", "url": "<피드 주소>", "home": "<사이트>", "lang": "ko", "region": "KR",
 "kinds": ["trade_press"], "ecosystems": ["semis"], "broad": false, "enabled": true, "why": "이 출처가 먼저 싣는 작은 단서", "paywall": false,
 "verified": {"ok": true, "checked": "2026-10-30", "latest_item_date": "2026-10-29"}}
```
- `type`: `rss`·`atom` 은 피드로, `html_diff` 는 페이지 변화 감지로 수집한다 (`wsj.ecosystems.pages` — 새 링크는 하나씩, 본문 변화는 페이지마다 하나의 단서). `html_list` 는 옛 표기(같은 방식으로 바꾸는 중), `json_api` 는 기록만.
- 이 파일이 수집기가 읽는 유일한 출처 목록이다. 노션 '출처원 목록'(122개, 2026-11-02 조사)은 후보와 근거를 보는 곳이고, 수집을 시작한 출처만 여기로 옮긴다.
- `broad`: 종합 매체(주제 밖 글이 많은 곳). LLM 분류가 없을 때는 그래프 어휘에 걸린 글만 남긴다.
- `kinds`: trade_press · company_newsroom · disclosure · standards · conference · research · release_notes · market_data · policy · regulation · code.
- 층(layer, ADR-0030): 첫 `kinds` 로 정한다 — standards·conference·research·policy·release_notes·regulation·code 는 `raw`(원본), company_newsroom 은 `newsroom`, disclosure 는 `disclosure`, 나머지는 `press`. 다르게 보려면 `"layer": "press"` 처럼 적는다 (리서치 회사 보도자료 등).
- 원본 층이면서 `broad` 가 아닌 출처는 출처 자체를 골라 둔 것이라 분류기가 '주제 밖'이라 해도 버리지 않는다 (한 번 실행에 120건까지). 분야 전체를 내는 원본(arXiv 분야 피드 등)은 `broad: true` 로 두어 분류기를 거치게 한다.
- 남긴 단서는 원문 본문을 받아 `ideas.clue_texts` 에 둔다 (공개하지 않는 테이블). 구글 뉴스 중계 주소·PDF·공시 사이트는 받지 않는다.
- 스커틀벗(피셔): 한 회사의 단서는 그 **고객·공급사·경쟁사 쪽** 출처에서 먼저 나온다 — 한국 기업이라도 대만·일본·미국 공급망 매체를 함께 둔다.

## 고치는 법
- 더하기·빼기는 이 파일만 고치면 된다 (`research/` 안이라 주간 개선 작업이 스스로 병합할 수 있다).
- 점검: `cd pipeline && .venv/bin/python -m wsj.ecosystems.clues sources` (형식·중복), 페이지형은 `python -m wsj.ecosystems.pages probe [--id …]`, 수집 결과는 `ops.collector_runs` 의 `clues` 행(watermark.failed·kept·noise).
- 3번 넘게 실패한 출처는 `"enabled": false`. 시세 기사만 내는 출처는 뺀다.
