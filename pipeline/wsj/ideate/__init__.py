"""상상 단계 — 원천 다이제스트 → (구독 모델이 상상한) 초기 아이디어 → 빠른 점검 → 선택.

    python -m wsj ideate digest [--days 3] [--out d.md]     원천(ideas.clues)을 상상 단계 입력으로 압축
    python -m wsj ideate check --file seeds.json             후보 종목 시세·시총·최근 등락·역DCF 를 붙인다
    python -m wsj ideate save  --file seeds.json             research.reports 'seeds:YYYY-MM-DD' (kind=screen)
    python -m wsj ideate queue                               선택·요청된 초기 아이디어(3단계 대기열)

상상 자체는 코드가 하지 않는다. 지침은 docs/agents/v3/ideate.md.
"""
