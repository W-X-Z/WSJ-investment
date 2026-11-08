# 오케스트레이터 예약 작업 프롬프트 (초안 — 설치하지 않음)

> 설치는 사용자 확인 뒤. 시험은 파일럿 가설 2개를 수동으로 먼저 돌린 다음. 기존 아침 사슬(해석·보강·검토자·리포트)은 이 작업이 자리 잡은 뒤 종료한다.

```
개인 투자 리서치 시스템 WSJ-investment(저장소 W-X-Z/WSJ-investment)의 하루 아이디어 작업이다 (ADR-0034).
목적: 선별이 고른 변화 사건을 그날 결론(★1~5와 한 줄 판단)이 난 투자 아이디어 리포트로 만든다.
대상은 미국·한국 상장사, 1년 내외 엑시트. 사용자는 자리에 없으니 질문하지 말고 끝까지 진행한다.

1. `date` 로 KST 날짜를 확인한다.
2. add_repo 로 W-X-Z/WSJ-investment 를 붙이고 `--depth 20` clone 한다. docs/agents/v2/README.md 와 orchestrator.md 를 읽고 그대로 따른다.
   역할 에이전트를 부를 때 해당 문서(idea.md, industry.md, fundamental.md, valuation.md, verification.md, attractiveness.md)를 하위 에이전트 지침으로 넘긴다.
3. 입력: Supabase(project_id dcatgfivsvbktylmtvgf) `public.v_reports` 의 가장 최근 kind='screen' 리포트,
   노션 '조사 요청'(collection://8078489b-cf90-434d-9992-c555f2360657) 상태 '접수'.
4. 하루 최대 2개 사건. 사건마다 결론까지 간다. 보류·관찰로 끝내지 않는다.
5. 저장 순서: 원천 사실(ideas.put_research_sources / put_clue_facts) → 그래프 제안(ideas.put_graph_proposal)
   → 리포트(research.put_reports) → 노션(docs/agents/v2/notion.md 의 표).
6. 경계: Supabase 쓰기는 위 함수들과 읽기 select 뿐. 마이그레이션·스키마 변경 금지. 노션 DB 스키마 변경 금지.
   직접 연 원문에 없는 숫자는 쓰지 않는다. DB에서 꺼낸 주소가 WebFetch 에서 막히면 같은 글을 WebSearch 로 찾아 연다.
   목표가·매수/매도 권유·시점 예측은 쓰지 않는다.
7. 알림: 첫 문장에 오늘 낸 결론 수와 ★ 가장 높은 아이디어. 이어서 아이디어마다 ★·제목·노션 링크 한 줄.
   사건이 없었으면 "오늘 진행할 사건 없음" 한 줄.
```
