# 오케스트레이터 예약 작업 프롬프트 (v3)

> 설치는 사용자 확인 뒤. 설치하면 기존 아침 사슬(05:23 수집 · 06:17 해석 · 06:49 검토 · 07:37 리포트)은 끈다(수집은 GitHub Actions 가 계속한다).
> 권장 시각: monitor.yml(05:40 KST) 이 끝난 뒤 07:30 KST, 월~토.

```
개인 투자 리서치 WSJ-investment(저장소 W-X-Z/WSJ-investment)의 3단계 심층 리서치 작업이다 (설계 v3).
목적: 대기열의 (종목, 아이디어)를 그날 결론(★1~5와 판단)이 난 심층 리서치 리포트로 만든다.
대상은 미국·한국 상장사, 1년 내외 엑시트. 사용자는 자리에 없으니 묻지 말고 끝까지 진행한다.

1. `date` 로 KST 날짜를 확인한다.
2. W-X-Z/WSJ-investment 를 붙이고 --depth 20 으로 clone, `pip install -e "pipeline[chart]"`.
   docs/agents/v3/README.md 와 orchestrator.md 를 읽고 그대로 따른다. 하위 에이전트에는 해당 지침(fundamental.md,
   industry.md, valuation.md, verification.md)과 필요한 재료만 넘긴다. 리포트는 report-template.md, 노션은 notion.md.
3. Supabase 연결: SUPABASE_URL·SUPABASE_SECRET_KEY 가 환경에 있어야 한다. 없으면 Supabase 커넥터(project_id dcatgfivsvbktylmtvgf)로
   research.put_reports · ideas.put_research_sources 를 SQL 로 부르고, 나머지 계산은 `--no-db` 로 돌린다.
4. 하루 최대 2건. 건마다 결론까지 간다. 보류·관찰로 끝내지 않는다.
5. 경계: Supabase 쓰기는 위 두 함수와 `monitor mark` 뿐. 마이그레이션·스키마 변경 금지. 노션 DB 속성 변경 금지.
   직접 연 원문에 없는 숫자는 쓰지 않는다. 목표가·매수/매도 권유·시점 예측은 쓰지 않는다.
6. 알림: 첫 문장에 오늘 낸 결론 수와 ★ 가장 높은 아이디어. 이어서 건마다 ★·헤드라인·노션 링크 한 줄.
   대기열이 비었으면 "오늘 심층 대상 없음" 한 줄.
```
