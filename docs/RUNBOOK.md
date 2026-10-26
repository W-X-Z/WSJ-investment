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

- 스케줄: 평일 10:17 UTC 일간 수집기 6개, 토요일 유니버스 재구축 (`.github/workflows/collect.yml`).
- 수동 실행: Actions → collect → Run workflow. `collectors` 에 이름을 공백으로 나눠 넣고, `since` 로 재수집 시작일 지정.
- 상태 확인: 조회 화면 `/` (수집기별 마지막 실행·에러) 또는 `select * from public.v_collector_overview`.

### 브리프 (ADR-0009)
- 스케줄: 월 12:23 UTC 후보 상위 5건 (`.github/workflows/briefs.yml`). 수동: Actions → briefs → `ciks` 또는 `top`, `model`(sonnet/opus/fable), `dry_run`.
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
