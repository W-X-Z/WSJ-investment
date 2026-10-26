# WSJ-investment

개인 미국 소형주 투자 시스템. 실제 운용사처럼 **부서(에이전트)와 데이터 공간을 분리**하고, 공개 하드데이터(SEC·FINRA·FDA·ClinicalTrials·정부조달 등)를 수집해 텐배거 후보를 발굴·심사·집행하는 것을 목표로 한다.

현재 단계: **Phase 2 — 연결 레이어(신호·후보) + 브리프(Analyst/Risk).** 제품은 "텐배거 후보 브리프" ([ADR-0008](docs/adr/0008-product-is-the-brief.md), [ADR-0009](docs/adr/0009-brief-workflow.md)). 매매는 사용자가 직접.

```
WSJ-investment/
├── docs/                 설계 문서·의사결정 기록(ADR)·데이터 소스 카탈로그·백로그
├── supabase/migrations/  DB 스키마 (부서별 schema 분리)
├── pipeline/             Python 수집 파이프라인 (wsj 패키지)
├── apps/web/             Next.js 개발용 조회 콘솔
└── .github/workflows/    수집 스케줄 (GitHub Actions)
```

## 빠른 시작

```bash
# 1) 파이프라인
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # SUPABASE_URL / SUPABASE_SECRET_KEY 입력
python -m wsj list              # 수집기 목록
python -m wsj run sec_universe  # 유니버스 생성 (최초 1회)
python -m wsj run sec_form4 --since 2026-10-01
python -m wsj run --all         # 전체 증분 수집
python -m wsj entities resolve  # 소스별 이름 → CIK 매칭
python -m wsj signals build     # 신호·후보 재계산
python -m wsj briefs build --cik 2012593 --dry-run   # 데이터팩·프롬프트만 (LLM 없음)
python -m wsj briefs build --top 3                    # ANTHROPIC_API_KEY 필요

# 공급망 온톨로지 (ADR-0012·0013)
python -m wsj.ecosystems.ontology --check             # 닫힌 어휘 검증
python -m wsj.ecosystems.impact --node tech:hybrid_bond   # 이 노드가 바뀌면 누가 영향
python -m wsj.ecosystems.discover                     # 병목별 소형 공급사 발굴 (EDGAR 전문검색)
python -m wsj.ecosystems.promote && python -m wsj.ecosystems.export_web   # 승격 → 웹 데이터
python -m wsj moat build --ticker LWLG --dry-run      # 해자 카드 입력 확인 / 키 있으면 실제 생성

# 로컬 검증용 (Supabase 없이 SQLite)
WSJ_STORE=sqlite python -m wsj run sec_form4 --since 2026-10-20 --limit 50

# 2) 조회 화면
cd apps/web
cp .env.example .env.local      # NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_KEY
npm install && npm run dev
```

## 문서 지도

| 문서 | 내용 |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 전체 구조, 부서(에이전트) 분리, 데이터 흐름 |
| [docs/adr/](docs/adr/) | 설계 판단 기록. 번호 순으로 읽으면 왜 이렇게 만들었는지 따라갈 수 있다 |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | 2026-10 검증 기준 데이터 소스 카탈로그 (API·시차·조인키·함정) |
| [docs/BACKLOG.md](docs/BACKLOG.md) | 수집기·기능 백로그와 우선순위 |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | 운영 절차, 장애 대응, 키 발급 |
| [docs/log/](docs/log/) | 작업 일지 (날짜별) |

## 원칙

1. **에이전트는 자기 스키마에만 쓴다.** 다음 단계 스키마는 읽기 전용. Risk 승인 없이는 아무것도 체결되지 않는다.
2. **원천 데이터는 가공 없이 `raw`에 보존**하고, 해석은 `core` 이상에서 한다. 재처리가 가능해야 한다.
3. **수집기는 멱등(idempotent)·증분(watermark)·독립 모듈.** 하나가 죽어도 나머지는 돈다.
4. **판단은 문서로 남긴다.** 되돌리기 어려운 결정은 ADR, 작업 흐름은 log.
