# 에이전트 지침 v3 (2026-11-09) — 이슈 모니터링 → 선별 → 심층 리서치

설계: 노션 '투자 리서치 서비스 설계 v3'. v2(`docs/agents/v2/`)를 대체한다. v2 의 선별(screen)은 그대로 N3 로 쓴다.

| 단계 | 노드 | 어디서 | 지침 |
|---|---|---|---|
| 1 | N1 수집 · N2 분류 · N3 선별 | GitHub Actions (`monitor.yml`) | `v2/screen.md` |
| 1 | N4 영향 경로 · N5 후보 종목 | 〃 `python -m wsj monitor run` | `monitor.md` |
| 2 | N6 주가 반응 · N7 선택 | 〃 | `monitor.md` |
| 3 | N10~N13 대상·공시·구조 카드·프로필 (카드는 Actions 가 미리) | `python -m wsj deep …` | `deep-tools.md` |
| 3 | N8 노션 후보·요청, N9 오케스트레이터, N22 결론, N24 게시, N25 알림 | 구독 예약 작업 | `orchestrator.md`, `notion.md` |
| 3 | N14 주가 이슈 · N16 펀더멘탈 · N17 산업 · N18 피어 · N19·N20 밸류 | 하위 에이전트 | `fundamental.md`, `industry.md`, `valuation.md` |
| 3 | N21 검증 (별도 맥락) | 하위 에이전트 | `verification.md` |
| 3 | 리포트 형식 | — | `report-template.md` |

## 공통 원칙
- 목표: 1년 내외 엑시트로 2~3배가 가능한 미국·한국 상장사. 확률·기댓값 숫자는 쓰지 않는다. ★는 "이 아이디어를 얼마나 강하게 권하고 싶은지"의 주관.
- 숫자는 코드가 계산하고, 해석·추정·판단은 에이전트가 한다. 추정은 원문 사실과 구분해 표시한다.
- 지침은 목적과 방향만 정한다. 방법은 그때그때 판단한다.
- 모든 심층 리서치는 결론(★1~5 + 판단)으로 끝난다. 보류·관찰·"다음 실적을 보고"로 끝내지 않는다. 확인 못 한 것은 리스크에 넣고 ★에 반영한다.
- 발행한 아이디어는 추적하지 않는다. 다시 볼 일은 새 사건으로 들어와 새 리포트가 된다.
- 가격이 무엇을 반영했는지 말하기 전에 그 사실이 나온 날 전후 주가·거래량과 그날 이유를 먼저 확인한다. "시장은 이렇게 믿는다"고 단정하지 않는다.
- 애널리스트 커버리지가 있다는 이유로 아이디어를 깎지 않는다. "알려졌으니 반영됐다"는 효율 시장식 판단을 하지 않는다.
- 목표가·매수/매도 권유·시점 예측은 쓰지 않는다(시나리오 가치는 판단 재료).

## 저장 (새 테이블 없음)
| 무엇 | 어디 | id |
|---|---|---|
| 선별 사건 | `research.reports` kind=screen | `screen:YYYY-MM-DD` |
| 후보·선택·대기 상태 | `research.reports` kind=screen | `candidates:YYYY-MM-DD` (후보 status: open·selected·requested·done·dropped) |
| 구조 카드 | `research.reports` kind=company | `card:<시장>:<코드>:<fy연도 또는 문서>` |
| 심층 리서치 | `research.reports` kind=idea (★·판단 필수) | `idea:<시장>:<코드>:<YYYY-MM-DD>` |
| 직접 연 출처 | `ideas.clues` (`ideas.put_research_sources`) | clue_id → 리포트 cites |
