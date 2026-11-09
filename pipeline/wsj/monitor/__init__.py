"""1·2단계 (설계 v3): 선별 보고서의 진행 사건 → 영향 경로 → 후보 종목 → 주가 반응 → 하루 최대 2건 선택.

  N1·N2  수집기·관련성 분류 (그대로)
  N3     선별 에이전트 wsj.agents.screen → research.reports 'screen:YYYY-MM-DD' (그대로 쓴다)
  N4     paths.explore      사건마다 최대 3개 경로(병목·대체·파이 확대·협상력)와 수혜·피해 상장사 — 중형 모델 + 웹 검색 몇 번
  N5     candidates.resolve 미국·한국 상장 티커 확정, 시총
  N6     pick.reaction      사건일 전후 초과 수익률·거래량 (tools.event)
  N7     pick.choose        후보 전체를 한 번에 보고 하루 최대 2건 선택 — 중형 모델
저장: research.reports kind='screen', report_id 'candidates:YYYY-MM-DD' — 후보마다 status(open·selected·requested·done).
3단계 대기열 = 이 보고서들의 selected·requested 후보 (queue.py). 새 테이블은 없다.
"""
