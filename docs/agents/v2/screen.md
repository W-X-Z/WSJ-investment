# 선별 (API 에이전트)

## 목적
하루치 단서를 읽고 **"무엇이 전과 달라졌나"를 변화 사건으로 묶어**, 아이디어로 만들 만한 것만 진행 표시를 한다. 판단은 얕고 양이 많아서 API로 돌린다.

## 실행
- `python -m wsj screen` (GitHub Actions, 수동 실행으로 시작 → 비용을 잰 뒤 매일 예약). 키: `ANTHROPIC_API_KEY`.
- 1단계 관련성 분류는 수집 단계에 이미 있다(소형 모델, `clues.py`). 선별은 2단계다: 관련 단서 + 본문 → 변화 사건.
- 모델: 중형(Sonnet). 지시문·기존 아이디어 목록은 캐시한다. 하루 입력 토큰 상한을 넘으면 멈추고 그때까지의 결과만 저장한다.

## 입력
- 지난 실행 이후 `relevant` 단서(제목·요약·출처 층)와 받아 둔 본문(`clue_texts`).
- 동조화·급등락 감지 단서(`source_kind = market_move`), 정책 테마(`extra.themes`).
- 노션 '조사 요청'(새 아이디어 / 추가 조사 / 사실 정정) — 오케스트레이터가 함께 읽어도 된다.
- 기존 리포트 목록: 최근 아이디어와 기각한 아이디어(결론·이유), 산업 구간 목록. 겹치는지 판단하는 데 쓴다.

## 출력 — `research.put_reports`, kind `screen`, report_id `screen:YYYY-MM-DD`
```json
{"window": {"from": "2026-11-08T21:00:00Z", "to": "2026-11-09T21:00:00Z"},
 "events": [{"event_id": "e1", "title": "무엇이 달라졌나 (한 줄)", "summary": "2~3문장, 날짜·숫자",
             "clue_ids": [812345, 812346], "entities": ["company:leu", "segment:uranium_enrichment"],
             "novelty": "new|update|dup", "overlaps": ["idea:russian_enrichment_ban:2026-11-09"],
             "proceed": true, "reason": "진행/보류 이유 한 문장", "hypothesis_seed": "가설 한 줄"}],
 "usage": {"model": "claude-sonnet-5-5", "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0}}
```
- 같은 보도자료를 인용한 기사 여러 건은 한 사건으로 묶는다.
- 기존 아이디어와 겹치면 `overlaps` 에 적고, 새 사건이 그 아이디어의 결론·기각 이유를 바꾸는 경우에만 `proceed: true`.

## 오케스트레이터가 쓰는 방식
가장 최근 `screen` 리포트에서 `proceed = true` 인 사건을 우선순위대로 읽어 예산 안에서 고른다(orchestrator.md).

## 하지 않는 것
- 투자 판단·★를 내지 않는다. 숫자를 추정하지 않는다(단서에 있는 숫자만).
- 단서 전부에서 사실을 뽑지 않는다 — 사실 기록은 조사하는 에이전트의 몫이다.
