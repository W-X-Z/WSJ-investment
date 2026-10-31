# 주간 개선 작업 — 시스템이 목적에 더 가까워지게 (ADR-0017, 2026-10-31 개정)

Claude 예약작업 "WSJ 시스템 개선 (주간)"이 매주 일요일 10:23 KST 에 이 문서를 따른다. 사용자는 자리에 없으니 질문하지 말고 진행한다.
목적·방향은 `docs/agents/daily-ideas.md` 와 같다 — 미국 소·중형의 1년 2~3배 기회를 시장보다 먼저, 더 정확히 찾는 것.

## 맡은 일
이번 주에 무엇을 고치면 시스템이 그 목적에 가장 가까워지는지 판단해서 고친다.
고를 때 묻는 것은 하나다: **이걸 고치면 기회를 더 많이 · 더 일찍 · 덜 틀리게 찾게 되나?** 문제가 사실이어도 목적과 무관하면 고치지 않고 `research/improvement_log.json` 에 '보류(목적과 무관)' 로 적는다.
무엇을 볼지도 판단한다. 아래 도구와 자료는 쓸 수 있는 것의 목록이지 순서가 아니다.

## 쓸 수 있는 도구와 자료
- 점검: `.venv/bin/python -m wsj.ecosystems.health --out ../.improve/health.json --md ../.improve/health.md`
- 그래프 공백·후보: `.venv/bin/python -m wsj.ecosystems.scan --from-public --out ../.improve/scan.json`
- 출처 도달: `gh api -X POST repos/W-X-Z/WSJ-investment/actions/workflows/source-probe.yml/dispatches -f ref=main` 후 그 실행의 job 로그
- 단서 출처 상태: `select started_at, watermark->'failed' as failed, watermark->>'kept' as kept, watermark->>'noise' as noise from ops.collector_runs where collector = 'clues' order by started_at desc limit 7;` · 출처 목록 `research/sources/registry.json`
- 지난주 아이디어: `select opportunity_key, title, stars, status, status_note, interpretation, nodes, updated_at from ideas.opportunities where updated_at > now() - interval '7 days' order by updated_at;`
- 사용자 지적 기록 `research/playbook/feedback.md`, 패턴 카드 `research/playbook/patterns/`, 지난 개선 `research/improvement_log.json`, 모니터 후보 `docs/adr/0018-monitor-registry.md`, 백로그 `docs/BACKLOG.md`

## 권한과 경계
- DB 쓰기: `ideas.put_observations`(병목 상태 관측치), `ideas.put_company_events`(원문 확인), `ideas.put_idea_notes`(심층 메모)만. 투자 아이디어는 쓰지 않는다 (매일 작업의 일).
- 저장소: 브랜치 `auto/improve-YYYYMMDD` 에 커밋하고 PR 을 연다. CI(pytest · typecheck-build · Vercel)가 모두 통과하고 바뀐 파일이 전부 `research/` · `apps/web/src/data/` · `pipeline/wsj/ecosystems/graph_patches/` 안이면 스스로 병합한다. 그 밖(파이프라인·웹 코드, 워크플로, 마이그레이션, docs/agents/)이 바뀌면 병합하지 않고 PR 링크를 알린다.
- 마이그레이션 SQL 은 만들 수 있지만 실행하지 않는다. 시크릿·서비스 키를 쓰지 않는다. 저장소 공개 설정·RLS 를 바꾸지 않는다.
- 근거는 직접 연 원문. 거부된 도구·URL 은 우회하지 않는다.

## 준비
- `date` 로 KST 날짜. add_repo(W-X-Z/WSJ-investment, access=push) 후 clone (`--depth 20`).
- `cd pipeline && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"`
- Supabase MCP 로 publishable 키를 받아 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` export.

## 그래프 패치를 쓸 때
- `pipeline/wsj/ecosystems/graph_patches/pYYYYMMDD_<주제>.py` (기존 패치를 본보기로, 기존 패치는 고치지 않는다) 또는 `research/ecosystems/patches/*.json` (`graph_patches/from_json.py` 형식).
- 간선마다 원문을 직접 열어 확인한다. excerpt 는 원문 문장 그대로, published_at 은 원문 날짜. 근거 등급: 회사 공시·IR = official_issuer, 업계 조사·언론 = third_party_report, 추론 = technical_inference.
- 새 상장사는 거래소·티커·규모를 정확히 (SEC 필러면 CIK 확인). 패턴 카드의 '관련 노드' 는 그래프에 있는 id 만 (`pytest tests/test_recall.py`).
- 검증: `ontology --check` · `export_web` · `python3 ../apps/web/scripts/sync_ecosystem_seed.py` · `pytest -q`

## 기록·PR·보고
- `research/improvement_log.json` 끝에 `{"date","kind":"data|ontology|judgment|ui|ops","by":"claude-weekly","title","detail"}` → `export_web`.
- 커밋 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 와 세션 링크. PR 은 `gh api repos/W-X-Z/WSJ-investment/pulls -f base=main -f head=… -f title=… -F body=@…`, 본문 끝 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- CI 를 기다리고(최대 20분) 조건이 맞으면 `gh api -X PUT repos/W-X-Z/WSJ-investment/pulls/<n>/merge -f merge_method=squash`. 실패하면 고쳐서 다시(2번까지), 그래도 안 되면 PR 을 열어 둔 채 알린다.
- 보고는 짧게: 무엇을 왜 골랐나, 고친 것, PR 과 병합 여부, 남은 큰 문제. 알림은 항상(주 1회) — 첫 문장에 병합 여부와 고친 것, 사람 승인이 필요한 PR 링크.
