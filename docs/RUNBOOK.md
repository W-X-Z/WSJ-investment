# 운영 절차 (RUNBOOK)

## 1. 최초 설정

### Supabase
- 프로젝트 `wsj-investment` (ref `dcatgfivsvbktylmtvgf`, ap-northeast-2). 마이그레이션은 `supabase/migrations/` 순서대로 이미 적용됨.
- **서비스 롤(secret) 키**: Supabase 대시보드 → Project Settings → API Keys → `service_role` (또는 `sb_secret_...`). 파이프라인 전용. 레포·프론트에 절대 넣지 않는다.
- 새 마이그레이션은 파일을 먼저 레포에 추가하고(번호 순), Supabase MCP `apply_migration` 또는 SQL Editor 로 같은 내용을 적용한다. 레포 파일이 단일 진실.

### GitHub Secrets (Settings → Secrets and variables → Actions)
| 이름 | 값 |
|---|---|
| `SUPABASE_URL` | `https://dcatgfivsvbktylmtvgf.supabase.co` |
| `SUPABASE_SECRET_KEY` | 서비스 롤 키 |
| `OPENFDA_API_KEY` | (선택) https://open.fda.gov/apis/authentication/ 에서 발급. 없으면 1,000/일 |
| `ANTHROPIC_API_KEY` | 브리프 생성용 (`briefs` 워크플로). https://console.anthropic.com 에서 발급. 건당 ≈ $0.3~0.7 (Sonnet) |

### 로컬
```bash
cd pipeline && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
cp .env.example .env   # 키 입력
python -m wsj list
```

## 2. 일상 운영

- 스케줄: 토 11:41 UTC 주 1회 — 유니버스 재구축 + 일간 수집기(`.github/workflows/collect.yml`). 수집기는 워터마크로 지난 실행 이후분을 이어 받는다.
- 수동 실행: Actions → collect → Run workflow. `collectors` 에 이름을 공백으로 나눠 넣고, `since` 로 재수집 시작일 지정.
- 상태 확인: 조회 화면 `/` (수집기별 마지막 실행·에러) 또는 `select * from public.v_collector_overview`.

### 브리프 (ADR-0009)
- 정기 실행 없음 (2026-10-27부터, 아카이브 기능). 수동: Actions → briefs → `ciks` 또는 `top`, `model`(sonnet/opus/fable), `dry_run`.
- 로컬:
  ```bash
  python -m wsj briefs build --cik 2012593 --dry-run        # LLM 없이 data/briefs/<티커>_<날짜>/ 에 데이터팩·프롬프트
  python -m wsj briefs build --top 3                         # ANTHROPIC_API_KEY 필요, ideas.briefs 저장
  python -m wsj briefs build --cik 2012593 --model opus --force
  ```
- 프롬프트를 고치면 `wsj/briefs/prompts.py` 의 `PROMPT_VERSION` 을 올린다. 먼저 `--dry-run` 으로 입력을 확인하고, 한 종목에 `--force` 로 돌려 비평의 '근거 없는 주장' 수가 줄었는지 본다.
- 채점: 분기마다 `select * from public.v_predictions where outcome='pending' and due_date <= current_date` 를 보고 `ideas.predictions.outcome` 을 hit/miss/unclear 로 갱신 (S-5 에서 화면화).

## 3. 처음 돌릴 때 순서

```bash
python -m wsj run sec_universe              # 5~8분 (후보 ~2,500 종목 submissions)
python -m wsj run sec_form4 --since 2026-10-01
python -m wsj run sec_filings --since 2026-10-01
python -m wsj run finra --since 2026-10-01
python -m wsj run clinicaltrials
python -m wsj run openfda --since 2026-09-01
python -m wsj run usaspending --since 2026-08-01
python -m wsj entities resolve
```

## 4. 장애 대응

| 증상 | 원인·조치 |
|---|---|
| `ops.collector_runs.status='failed'`, error 에 403 (sec.gov) | User-Agent 누락 또는 과속. `SEC_USER_AGENT` 에 이름·이메일 확인. 10 rps 초과 시 10분 차단 |
| FINRA 400 "Sorting is allowed only if all partitions keys…" | 파티션 키 EQUAL 필터 누락. `finra.py` 의 `_query` 만 써야 함 |
| openFDA 429 | 키 없이 1,000/일 초과. `OPENFDA_API_KEY` 설정 |
| ClinicalTrials 403 | 클라우드 IP 봇 차단 가능성. 재시도 간격 늘리거나 로컬에서 실행 |
| 유니버스가 0 | `sec_universe` 가 EntityPublicFloat 프레임을 못 받음(404 연속) → `_frames_to_try` 의 분기 범위 확인 |
| 수집기 하나가 계속 실패 | 모듈의 `schedule = "paused"` 로 바꾸면 러너가 건너뜀. DATA_SOURCES 에 사유 기록 |

## 5. 워터마크 되감기

```bash
python -m wsj run sec_form4 --since 2026-09-01     # 그 날부터 다시 (멱등)
```
`--limit` 를 주면 워터마크를 갱신하지 않으므로 스모크 테스트에 안전하다.

## 6. 로컬 검증 (Supabase 없이)

```bash
WSJ_STORE=sqlite python -m wsj run sec_form4 --since 2026-10-20 --limit 20
sqlite3 data/wsj.sqlite 'select count(*) from raw__sec_form4_transactions'
```
SQLite 테이블은 `schema__table` 이름으로 자동 생성된다 (운영 스키마와 타입은 다름).

## 7. 로컬 결과를 Supabase 로 옮기기 (비상용)

```bash
python scripts/sqlite_to_sql.py data/wsj.sqlite out/ --batch 500 --exclude-cols payload
# out/*.sql 을 Supabase SQL Editor 에 순서대로 붙여넣기 (companies → form4_filings → transactions)
```
정식 경로는 Actions. 이 스크립트는 키 없이 수집한 결과를 한 번 옮길 때만 쓴다.

## 8. 조회 화면

```bash
cd apps/web && cp .env.local.example .env.local && npm install && npm run dev
```
`NEXT_PUBLIC_SUPABASE_KEY` 는 **publishable** 키 (`sb_publishable_...`). 읽기 전용 RLS 로만 접근한다.

## 9. 사용량 한도 (2026-10-27)

- 10/26 까지 레포가 **private** 이라 GitHub Actions 무료 분(월 2,000분, Linux)을 차감했다. 10/26~27 이틀에 479회·약 1,560분(벽시계), 그중 69% 가 PR 마다 7개씩 돌던 중복·이전 기능 워크플로였다 → 그 달 할당량 초과.
- 지금은 **public** → 표준 GitHub 호스팅 러너(ubuntu-latest) 사용은 무료이고 할당량과 무관하게 돈다. 다시 private 로 바꾸면 아래 정기 실행이 월 약 1,000분을 쓴다.
- Vercel Hobby 는 배포 일일 한도가 있다 → `apps/web/vercel.json` `ignoreCommand` 로 `apps/web` 변경이 없는 커밋은 빌드 생략.
- 정리 (2026-10-27):
  - 삭제: `technology-intelligence-monitor`(issues.yml 이 대체, ADR-0014), `canvas-web-build`(web-quality 와 중복), `canvas-visual-preview`·`ecosystem-impact-preview`(개발용 미리보기).
  - 수동 실행만: `briefs`(아카이브 기능), `technology-evidence-graph-enrichment`·`technology-historical-backfill`(일회성 데이터 생성).
  - PR 워크플로(`web-quality`·`pipeline-tests`)는 경로가 바뀔 때만, 같은 브랜치의 이전 실행은 취소.
  - `issues` 는 코드 병합(push)으로 돌지 않는다 — 병합마다 LLM 비용이 나가지 않게. 바로 확인하려면 Actions → issues → Run workflow.
- 정기 실행:

  | 워크플로 | 주기 | LLM |
  |---|---|---|
  | 투자 아이디어 (Claude 예약작업, `docs/agents/daily-ideas.md`) — issues 실행 → 원문 확인·병목 관측치 → 아이디어·판단 | 월~토 06:41 KST | 요금제 안 (API 비용 없음) |
  | 시스템 개선 (Claude 예약작업, `docs/agents/weekly-improvement.md`, ADR-0017) — 점검 → 그래프 패치·관측치 → PR → CI → 데이터 PR 은 스스로 병합 | 일 10:23 KST | 요금제 안 |
  | issues (이슈 선별 + 기업 소식 + 가격, 위 예약작업이 실행) | 월~토 아침 | Sonnet 1회 ≈ $0.1 |
  | issues (기업 소식·가격 수집·저장만) | 매일 18:47 KST | 없음 |
  | source-probe (Actions 러너에서 출처 도달 점검, 저장 없음) | 수동·관련 PR | 없음 |
  | collect (유니버스 + 공시·내부자·공매도·정부 수주) | 토 20:41 KST | 없음 |
  | moat (해자 카드, 같은 기준일 카드는 건너뜀) | 화 22:41 KST | Sonnet, 새 카드만 |

## 10. 스스로 판단·개선하는 시스템 (ADR-0017, 2026-10-28)
- 화면: `/bottlenecks`(병목 보드) · `/system`(시스템 점검 — 고칠 것, 수집 상태, 커버리지, 판단 성적, 스스로 고친 기록).
- 점검·스캔을 손으로 돌리기: `cd pipeline && SUPABASE_URL=… SUPABASE_PUBLISHABLE_KEY=… python -m wsj.ecosystems.health` / `python -m wsj.ecosystems.scan --from-public`.
- 가격: `python -m wsj.ecosystems.prices run --budget-min 10` (서비스 키 필요, Actions 에서만). 도달 점검: `python -m wsj.ecosystems.prices probe`.
- 그래프 고치기: `seed_graph.json` 을 손으로 고치지 않고 `pipeline/wsj/ecosystems/graph_patches/pYYYYMMDD_*.py` 패치를 더한다. 병목은 2단계 안에 상장사가 있어야 검증을 통과한다.
- 0021 적용 전: 점수·가격 맥락·관측치·수집 기록 화면이 비어 보일 뿐 나머지는 돈다.
- 시가총액(ADR-0017 개정 1, 0022): `python -m wsj.ecosystems.facts run` (Actions 에서 매일, 미국은 하루 40곳). 도달 점검 `facts probe`. 0022 적용 전에는 카드에 "주가·시총 수집 전"으로 보인다.
  텐배거 출발 조건(시총 $3B 이하 · 저점 대비 3배 미만)은 `assess.TENBAGGER_*` 와 `apps/web/src/lib/ideas.ts` 두 곳에 같은 값 — 바꿀 때 함께.
- 심층 분석 메모: 매일 작업 6-2 (`docs/agents/deep-dive.md`), `ideas.put_idea_notes`. 상세 화면 '심층 분석' 절.
- 선행 추론(ADR-0017 개정 2): 근거 점수(확신)와 별개의 선행 점수(기대값) — `assess.anticipation`. 단서는 `scan --from-public` 의 `second_order`. 0023 은 고점·저점 대비의 이력 120일 보호.
- 개선 예약작업이 연 PR 중 코드·워크플로·마이그레이션이 바뀐 것은 사람이 병합한다. 데이터(`research/`, `apps/web/src/data/`, `graph_patches/`)만 바뀐 PR 은 CI 통과 시 스스로 병합한다.
