# 리포트 형식 (N22) — Forgent(FPS) 리포트 기준

모든 절은 두괄식: 굵은 한두 문장으로 결론, 그 아래 근거 글머리표·표. 과정·방법 서술("셋으로 가른다" 등)은 쓰지 않는다.

## 제목
`<회사명> — <아이디어 명사형 헤드라인>` (예: "Forgent Power Solutions — 스폰서 매각 수급 할인과 백로그 성장의 괴리")

## 요약 박스 (`sections.summary`)
`★N · 거래소 티커 · 시총 $X(기준 종가 $Y, 날짜)` 다음 줄에 3~4문장: 아이디어, 핵심 숫자 근거, 2배·3배 경로, 가장 큰 위험.

## 결론 (`sections.conclusion`)
- 투자 아이디어 — 무엇이 바뀌어 이 회사의 무엇이 늘어나는지
- 향후 밸류 요지 — 2배·3배가 되는 가격과 그 조건
- 위험 — 이 고리가 끊기면 ★가 어떻게 되는지
- 이 ★인 이유 — 한 단계 위가 아닌 이유

## 본문 절
1. `profile` 종목 프로필 — 무엇을 팔아 어디서 버는지(사업 부문·매출 구성), 구조 카드 7칸 요지, 연도별로 바뀐 것
2. `price_story` 주가 이슈 — 번호·날짜·이슈 한 줄씩(차트 PNG 번호와 같게). 결론은 따로 쓰지 않는다
3. `fundamentals` 펀더멘탈 — 연도별 표 + 숫자 변화의 원인
4. `industry_peers` 산업 및 피어 — 산업 구조·이 회사의 자리, 피어 비교표와 고른 이유
5. `valuation` 밸류에이션 — 현재 배수, 자기 과거·피어 대비, 지금 주가가 가정하는 것
6. `future_value` 향후 밸류 — Bear/Base/Bull 표(가정·이익·배수·주당가치·지금 대비 배수), 12개월 안의 계기
7. `risks` 리스크 — 확인하지 못한 부분도 여기서
8. `estimates` 추정(원문 아님) — 계산·외삽한 숫자와 그 근거를 따로 모은다

## 쓰지 않는 것
"시장은 이렇게 믿는다" 단언(대신 주가를 움직인 공시·뉴스·의견을 나열), '가장 약한 고리'·'확인 지점'·'다시 볼 트리거' 같은 고정 항목명, 확률·기댓값 숫자, 목표가·매수/매도 권유, 정보 없는 한 줄 요약.

## 저장 JSON (`python -m wsj deep save --file report.json`)
```json
{"symbol": "FPS", "market": "us", "as_of": "2026-11-10", "title": "…", "stars": 3, "verdict": "판단 한 문장",
 "candidate": {"report_id": "candidates:2026-11-10", "id": "e1p1-fps"},
 "sections": {"summary": "…", "conclusion": "…", "profile": "…", "price_story": "…", "fundamentals": "…",
              "industry_peers": "…", "valuation": "…", "future_value": "…", "risks": "…", "estimates": "…"},
 "data": {"scenario": {}, "peers": {}, "story_moves": []},
 "sources": [{"url": "https://…", "title": "…", "published_at": "2026-09-15"}],
 "created_by": "orchestrator-v3"}
```
