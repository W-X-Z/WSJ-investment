# ADR-0019: 결과는 가치평가, 점수는 계산기

상태: accepted (2026-10-28). 사용자: "로직 기반 점수를 표면으로 올리지 말고, 예약 실행 시 LLM 이 이슈들과 영향을 파악해서 기업 가치평가(주가)를 해서 그 결과만 보여주면 좋겠어. 로직 계산기가 필요하면 알아서 쓰고."

## 문제
ADR-0017 은 판단을 두 축의 점수(근거 점수 = 확신, 선행 점수 = 기대값)로 표면에 올렸다. 점수는 규칙의 산물이라 설명하기는 쉽지만 투자자가 묻는 질문 —
"이 변화가 이 회사를 얼마짜리로 만드나, 지금 주가와 얼마나 다른가" — 에 답하지 않는다. 사용자가 원하는 것은 그 답이다.

## 결정
1. **사람이 보는 결과는 가치평가 하나다.** 매일 아침 예약작업의 LLM 이 아이디어마다 쓴다: 이슈(변화) → 영향 경로 → 이 기업의 숫자(매출·마진) → 시나리오별 내재 시총·주가 → 확률 가중 기댓값.
   - 시나리오 bear·base·bull, 확률 합 1. 각각 12개월 뒤 매출(현지 통화)·마진·배수(P/S 또는 P/E) → 내재 시총. 가정 2개 이상(근거 id), 깨지는 조건, confidence(low|mid|high), verdict 한 단락.
   - **산수는 검증기가 한다** (`ideas.parse_valuation`): 내재 시총 = 매출 × 배수(ps) 또는 매출 × 마진 × 배수(pe) 로 다시 계산해 LLM 숫자가 15% 넘게 다르면 고치고, 발행주식수로 나눠 주가를 내고, 확률 가중으로 expected_price 를 낸다. `ideas.put_valuations` 가 한 번 더 검증한다.
   - 저장: `ideas.valuations (idea_key, as_of)` — 평가일마다 한 행. 이력이 남아 주간 '적중 점검'의 재료가 된다. 뷰 `v_valuations`(최신)·`v_valuation_history`.
   - 화면: 카드 한 줄 `+86%  NT$42.5 → NT$78.0 · 12개월 기대 · 확신 중간 / 약세 −20% · 기본 +60% · 강세 +180%`. 상세는 verdict → 시나리오 표 → 영향 경로 → 가정(각주) → 깨지는 조건 → 이력.
     상승여력은 오늘 종가로 다시 계산한다 (기대 주가는 평가일의 것, 여력만 움직인다). 피드 순서는 기대 상승여력 순.
2. **점수는 계산기로 남는다.** 근거 점수·선행 점수(`assess.assess`)는 계속 계산해 `assessment` 에 저장하지만 카드·상세에 그리지 않는다. 쓰임: ★ 규칙(★3 ≥ 7점, ≤2점 → ★1), 알림 조건, 시스템 화면, 그리고 `valuations.calculator` 에 참고값으로 기록. LLM 입력(existing.score)에도 그대로 들어간다 — "필요하면 알아서 쓰라"는 뜻 그대로.
   텐배거 꼬리표("룸 큼"·"이미 간 종목")도 표면에서 뺀다. 시총·저점 대비 같은 사실은 상세의 '이미 움직인 폭' 줄에 남는다.
3. **분모(재무)를 수집한다.** `raw.company_fundamentals` — 미국 SEC companyfacts(TTM·FY), 대만 월매출 12개월 합 + TWSE/TPEx YTD 손익 비율, 한국 네이버 분기 표(억원). `v_company_fundamentals` 가 시총과 붙여 P/S·P/E·성장률을 낸다. 일본·중국은 아직 없다 — LLM 이 근거에서 읽은 숫자를 가정으로 쓴다.
4. 매수·매도 권유가 아니다. "목표가"·"매수" 같은 말을 쓰지 않고, 화면에 "모형 산출이지 권유가 아님"을 적는다.

## 가치평가가 아닌 것
- 주가 예측이 아니다 — 가정(변화의 규모·배수)이 맞을 때의 내재가치와 그 확률 분포다. 틀리는 쪽은 가정이고, 가정은 근거 id 로 추적된다.
- 매일 전부 다시 쓰지 않는다. keep 인 아이디어는 주가가 ±15% 넘게 움직였거나 새 근거가 가정을 바꿀 때만 다시 평가한다.

## 주간 점검 (weekly-improvement 8단계)
4주 넘은 평가의 기대 상승여력 vs 실제 주가 변화. confidence=high 가 방향을 반복해 틀리면 프롬프트의 배수·bear 규칙을 고친다.

## 바뀐 것
- 0024: `raw.company_fundamentals`, `ideas.valuations`, `ideas.put_valuations`, `v_company_fundamentals`, `v_valuations`, `v_valuation_history`.
- `wsj.ecosystems.fundamentals` (수집기, issues 워크플로에 단계 추가), `ideas.py` (프롬프트 '가치평가' 절, `money_context`, `parse_valuation`, `zy_valuations.sql`), 웹(`ValueLine`, 상세 `Value` 섹션; `ScoreText`·`Anticipate` 제거).
- `docs/agents/daily-ideas.md`: p23 검사, 4단계 valuation 규칙, 6-1 zy_valuations.sql, 보고·알림 기준(기대 상승여력 +50%·확신 mid+·시총 $3B 이하).
