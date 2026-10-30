# 주간 개선 작업 — 점검 → 고칠 일 고르기 → 근거 찾기 → 패치 PR → CI → 병합

Claude 예약작업 "WSJ 시스템 개선 (주간)"이 매주 일요일 10:23 KST 에 이 문서를 따른다 (ADR-0017).
목표는 시스템이 **더 많은 출처에서 작은 단서를 보고, 끊긴 곳 없이 해석하고, 해석의 암묵지(패턴)가 쌓이게** 만드는 것이다 (ADR-0028). 사용자는 자리에 없으니 질문하지 말고 진행한다.

## 권한과 경계
- DB 쓰기: `ideas.put_observations`(병목 상태 관측치), `ideas.put_company_events`(원문 확인), `ideas.put_idea_notes`(심층 메모)만. 아이디어는 쓰지 않는다 (매일 작업의 일).
- 저장소: 브랜치 `auto/improve-YYYYMMDD` 에 커밋하고 PR 을 연다.
- **스스로 병합해도 되는 PR** — CI(pytest · typecheck-build · Vercel)가 모두 통과하고, 바뀐 파일이 전부 아래 경로 안일 때:
  `research/` · `apps/web/src/data/` · `pipeline/wsj/ecosystems/graph_patches/`
- 그 밖의 경로(파이프라인·웹 코드, 워크플로, 마이그레이션, 이 문서와 docs/agents/)가 바뀌면 병합하지 않고 PR 링크를 알린다 — 사람이 본다.
- 마이그레이션 SQL 은 만들 수 있지만 실행하지 않는다 (사용자가 SQL 에디터에서 실행).
- 시크릿·서비스 키를 쓰지 않는다. 저장소 공개 설정·RLS 를 바꾸지 않는다.

## 0. 준비
- `date` 로 KST 날짜. add_repo(W-X-Z/WSJ-investment, access=push) 후 clone (전체 이력 불필요: `--depth 20`).
- `cd pipeline && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"`
- Supabase MCP 로 publishable 키를 받아 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` export.

## 1. 점검과 스캔
- `.venv/bin/python -m wsj.ecosystems.health --out ../.improve/health.json --md ../.improve/health.md`
- `.venv/bin/python -m wsj.ecosystems.scan --from-public --out ../.improve/scan.json`
- 출처 도달: `gh api -X POST repos/W-X-Z/WSJ-investment/actions/workflows/source-probe.yml/dispatches -f ref=main`, 끝나면 그 실행의 job 로그에서 시장별 가격·지표 결과를 읽는다.
- 지난주 개선 PR 들의 결과(병합 여부, 그 뒤 수집기 실패가 늘었는지)를 `research/improvement_log.json` 과 `ops` 기록으로 확인한다.

## 2. 고칠 일 고르기 (최대 5개, 위에서부터)
**먼저 묻는다** (사용자, 2026-10-30): 이것을 고치면 시장보다 먼저 미국·한국 상장사(소·중형 먼저)의 기회를 **더 많이 · 더 일찍 · 덜 틀리게** 찾게 되나?
답할 수 없으면 고치지 않는다 — 문제가 사실이어도 목표와 무관하면 `research/improvement_log.json` 에 '보류(목표와 무관)' 로만 적는다. 아래 목록은 이 질문을 통과한 것 중에서의 순서다.
1. 심각도 3 문제 (매일 수집기 실패, 끊긴 병목).
2. 노드가 없는 활성 이슈 → 맞는 노드가 있으면 별칭·현지어 용어 추가, 없으면 노드·간선 추가.
3. scan 의 company_leads·bottlenecks.uncovered 중 그래프 밖이거나 관계가 빈약한 기업 → 원문으로 공급 관계를 확인해 노드·간선 추가.
4. 활동 많은 병목 중 상태 관측치가 없거나 60일 넘은 곳 → 숫자(가격 배수·리드타임·가동률·재고·수주잔고·평균단가·증설 완공 시점)를 찾아 put_observations.
5. 데이터 공백 (가격·시가총액 출처가 없는 거래소, 값 없는 지표, 막힌 출처) → 무료·공식 대체 출처를 찾아 수집기 코드를 고친다 (사람 승인 PR).
6. **주간 반성 (ADR-0028)** — 지난 7일의 투자 아이디어를 읽는다:
   `select opportunity_key, title, stars, status, status_note, interpretation, nodes, updated_at from ideas.opportunities where updated_at > now() - interval '7 days' order by updated_at;`
   그리고 `research/playbook/patterns/` 를 고친다: 같은 메커니즘이 두 번 이상 나왔으면 새 카드, 겹치는 카드는 합치기, 사례 줄 더하기,
   내린(dropped) 아이디어의 이유는 해당 카드의 '반대 신호' 에. `research/playbook/feedback.md` 에 사용자 지적이 있으면 그것부터 반영하고 반영했다고 그 줄 끝에 적는다.
   카드의 '관련 노드' 는 그래프에 있는 id 만 (`pytest tests/test_recall.py` 가 확인한다).
7. **출처 목록 점검** — `select started_at, watermark->'failed' as failed, watermark->>'kept' as kept, watermark->>'noise' as noise from ops.collector_runs where collector = 'clues' order by started_at desc limit 7;`
   3번 넘게 실패한 출처는 `research/sources/registry.json` 에서 `"enabled": false`, 시세 기사만 내는 출처는 빼고, 지난주 아이디어 근거에 자주 나온 매체가 목록에 없으면 피드 주소를 찾아 더한다.
8. 모니터 1개 붙이기 — `docs/adr/0018-monitor-registry.md` 우선순위 순 (법설회 IR → 8-K 숫자 추출 → 품목 가격). 출처 도달을 `source-probe` 로 먼저 확인하고, 수집기 코드는 사람 승인 PR.

## 3. 그래프 패치 쓰는 법
- `pipeline/wsj/ecosystems/graph_patches/pYYYYMMDD_<주제>.py` 를 새로 만든다 (기존 패치 p20261028_… 를 본보기로). 기존 패치는 고치지 않는다.
- 간선마다 근거를 WebFetch 로 직접 열어 확인한다. excerpt 는 원문 문장을 그대로 (번역 금지), published_at 은 원문 날짜. 열어 보지 못한 출처는 쓰지 않는다.
- 근거 등급: 회사 공시·IR = official_issuer, 업계 조사·언론 = third_party_report, 추론 = technical_inference(그 경우 note 에 "(추론)").
- 새 상장사는 `Node.company(...)` 로 거래소·티커·규모를 정확히 (SEC 필러면 CIK 를 sec.gov company_tickers.json 에서 확인).
- 실행·검증:
  ```
  .venv/bin/python -m wsj.ecosystems.graph_patches.pYYYYMMDD_<주제>
  .venv/bin/python -m wsj.ecosystems.ontology --check
  .venv/bin/python -m wsj.ecosystems.export_web
  python3 ../apps/web/scripts/sync_ecosystem_seed.py
  .venv/bin/pytest -q
  ```

## 4. 기록과 PR
- `research/improvement_log.json` 맨 끝에 항목을 더한다: `{"date","kind":"data|ontology|judgment|ui|ops","by":"claude-weekly","title","detail"}` → `export_web` 다시 실행.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 와 이 세션 링크(`Claude-Session: …`)를 붙인다.
- PR 은 REST 로 연다 (`gh api repos/W-X-Z/WSJ-investment/pulls -f base=main -f head=… -f title=… -F body=@…`). 본문: 고친 문제, 추가한 노드·간선 수와 근거 출처, 남은 문제, 점검 요약. 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- CI 를 기다린다 (`gh api repos/W-X-Z/WSJ-investment/commits/<sha>/check-runs`, 최대 20분). 모두 통과하고 경로가 허용 범위면 `gh api -X PUT repos/W-X-Z/WSJ-investment/pulls/<n>/merge -f merge_method=squash`.
- 실패하면 고쳐서 다시 올린다 (2번까지). 그래도 안 되면 PR 을 열어 둔 채 알린다.

## 5. 보고와 알림
보고 6줄 이내: 점검의 문제 수(심각도별) · 고친 것 · 추가한 노드/간선/관측치 · PR 번호와 병합 여부 · 남은 상위 문제 · 이번 주 눈여겨볼 단서 3개(scan 의 company_leads·병목).
알림은 항상 보낸다 (주 1회): 첫 문장에 병합 여부와 고친 것 수, 사람 승인이 필요한 PR 이 있으면 그 링크.
