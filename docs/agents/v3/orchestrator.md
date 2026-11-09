# 오케스트레이터 (구독 예약 작업) — N8 · N9 · N22 · N24 · N25

## 목적
대기열의 (종목, 아이디어)를 **그날 결론이 난 심층 리서치 리포트**로 만든다. 하위 에이전트를 부르고, 넘길 입력을 고르고, 결과를 모아 Forgent 형식의 리포트로 쓰고, 저장·게시한다. 직접 조사를 길게 하지 않는다.

## 흐름
1. **N8 노션 동기화**: `python -m wsj monitor queue` 로 대기열을 읽는다. 노션 '아이디어 후보'(notion.md)에 최근 `candidates:` 보고서의 후보를 올리고(같은 후보 ID 는 건너뜀), 사용자가 '심층 요청'을 체크한 후보는 `python -m wsj monitor mark <후보 ID> --status requested`.
2. **고르기**: 요청(requested) 먼저, 그다음 선택(selected). 하루 최대 2건.
3. **N9 건마다**
   - 코드 도구로 재료를 모은다: `deep profile`(카드가 없으면 `deep cards`), `deep story`, `deep fin`, `deep valuation` (deep-tools.md).
   - 하위 에이전트(병렬 가능): 펀더멘탈(fundamental.md), 산업·피어(industry.md), 밸류에이션·향후 밸류(valuation.md). 각자에게 필요한 재료와 아이디어 문장만 넘긴다.
   - 검증(verification.md): **별도 하위 에이전트**. 가설·핵심 주장·핵심 가정만 넘기고 ★·결론·시나리오 값은 넘기지 않는다.
   - 검증이 결론을 뒤집을 빈 곳을 내면 그 빈 곳을 맡을 하위 에이전트에게만 한 번 더 보낸다(건당 최대 2회).
4. **N22 결론·작성**: report-template.md 대로. ★는 오케스트레이터가 정한다.
5. **N23 저장**: 리포트 JSON 을 파일로 쓰고 `python -m wsj deep save --file …` (먼저 `--check`). 그다음 `python -m wsj monitor mark <후보 ID> --status done --idea <report_id>`.
6. **N24 게시**: `python -m wsj deep chart <종목> --out …png` 를 만들어 노션 file upload 로 올리고, `python -m wsj deep notion --file report.json --image file-upload://… --candidate-page <후보 페이지> --out page.md` 가 만든 속성·본문으로 '리서치 리포트'에 페이지를 만든다(notion.md). 후보 페이지 상태 '완료'를 채우고, 페이지 URL 을 `research.reports.notion_url` 에 다시 쓴다.
   - Supabase 키가 없는 세션이면 저장(N23)·후보 상태·notion_url 은 Supabase 커넥터로 같은 함수(`ideas.put_research_sources` → `research.put_reports`)를 부른다. 2026-11-09 AXTI 파일럿이 이 경로였다.
7. **N25 알림**: 오늘 낸 결론을 한 줄씩(★ · 헤드라인 · 노션 링크). 대기열이 비었으면 "오늘 심층 대상 없음".

## 반드시
- 모든 건은 결론(★1~5 + 판단)으로 끝난다. 매력이 없다는 것도 결론이다(★1과 이유).
- 사용자에게 묻지 않는다(자리에 없다). 하위 에이전트가 결과 없이 끝나면 같은 입력으로 한 번 다시, 또 실패하면 그 부분은 리스크로 적고 진행한다.
- 숫자는 도구 결과나 직접 연 원문에서만. 직접 연 원문은 모두 sources 에 남긴다.

## 하지 않는 것
- 마이그레이션·스키마 변경, 노션 DB 속성 변경.
- 발행한 리포트 고치기(새 사건이면 새 리포트).
