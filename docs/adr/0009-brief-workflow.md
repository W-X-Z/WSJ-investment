# ADR-0009: 브리프 생성 워크플로 — 데이터팩 → 리서치 → 종합 → 비평, 날짜 박힌 예측

- 상태: accepted
- 날짜: 2026-10-26
- 관련: [ADR-0008](0008-product-is-the-brief.md) (제품 = 브리프), [ADR-0007](0007-alpha-hypothesis-and-validation-order.md) (알파 가설·청산 원칙)

## 맥락

사용자 요구 (2026-10-26): *"브리프에서 중요한 것은 미래에 대한 분석과 전망을 논리적으로 작성하는 것. 기업의 히스토리와 현재 상황 요약, 매크로·섹터·테마 시장 분석, 경쟁기업·매출 및 사업구조의 변화, 주가 히스토리와 최근 동향을 고려한 향후 전망 시나리오."*

즉 브리프는 "신호 나열"이 아니라 **논증**이어야 한다. 논증에는 (a) 회사 자신이 쓴 1차 자료(10-K·8-K·XBRL), (b) 회사 밖의 맥락(섹터·매크로·경쟁사 — 우리 DB에 없다), (c) 시장이 이미 무엇을 반영했는지(주가·거래량·공매도), (d) 결론을 틀리게 만들 조건(반증)이 필요하다. 이 네 가지가 서로 다른 성격의 입력이므로 한 번의 LLM 호출로 뭉개지 않고 단계를 나눈다.

제약: 유료 데이터 없음(ADR-0008), 비용은 후보 수에 비례, 프롬프트와 산출물은 사람이 리뷰·개선할 수 있어야 한다.

## 결정

### 1. 4단계 파이프라인 (`wsj briefs build`)

| 단계 | 담당 | 입력 | 출력 | LLM |
|---|---|---|---|---|
| ① 데이터팩 | Data Desk (코드) | DB + SEC + Nasdaq | `datapack` JSON + 마크다운 렌더 | 없음 |
| ② 리서치 | Analyst (웹 검색) | 데이터팩 요약 + 리서치 질문 | `research` JSON: 매크로·섹터·테마, 경쟁사, 최근 뉴스, 각 항목 출처 URL | Sonnet + `web_search` (max_uses 8) |
| ③ 종합 | Analyst (추론) | 데이터팩 전문 + 리서치 | `brief` JSON (§3 스키마) | Sonnet (기본) / Opus (`--model`) |
| ④ 비평 | Risk (추론) | 브리프 + 데이터팩 요약 | `critique` JSON: 근거 없는 주장, 빠진 리스크, 시나리오 확률 조정, 사전부검(pre-mortem), 최종 확신도 | Sonnet |

- ①은 결정론적이며 LLM 없이 `--dry-run` 으로 파일에 떨어뜨려 사람이 검토할 수 있다. 프롬프트 개선은 이 파일을 보면서 한다.
- ②를 ③과 분리하는 이유: 검색 도구가 켜진 호출은 긴 문맥(10-K 수만 토큰)을 들고 다니면 검색마다 비용이 커지고, 검색 결과가 1차 자료보다 앞서는 경향이 있다. 리서치는 짧은 요약만 들고 나가고, 종합은 검색 없이 전체 문맥을 읽는다.
- ④를 두는 이유: 같은 모델이 자기 글을 채점하면 후하다. 별도 시스템 프롬프트(반대 입장)로 돌리고 결과를 브리프 옆에 그대로 저장한다 — 비평이 브리프를 덮어쓰지 않는다 (Risk 는 거부권이 아님, ADR-0008 §2).

### 2. 데이터팩의 내용 (무엇을 읽히는가)

사용자가 요구한 다섯 축을 각각 어떤 하드데이터로 뒷받침하는지:

| 축 | 데이터 | 출처 | 비고 |
|---|---|---|---|
| 히스토리·현재 상황 | 10-K Item 1(사업) · Item 1A(리스크 요인) · Item 7(MD&A), 최근 8-K 본문 ≤3건 | EDGAR Archives (TOC 앵커로 섹션 추출, `raw.sec_documents` 캐시) | 1A 는 회사가 스스로 쓴 반증 목록 — 리스크 섹션의 1차 재료 |
| 매출·사업구조 변화 | XBRL 분기 시계열 12분기: Revenues, R&D, SG&A, OperatingIncome, NetIncome, OCF, Cash, Debt, SharesOutstanding → TTM·YoY·현금소진·런웨이·희석률 | `companyfacts` (`data.sec.gov`) | 태그 별칭 사전으로 회사마다 다른 태그 흡수. 없는 값은 "없음"으로 명시 |
| 주가 히스토리·최근 동향 | 1년 일봉 → 1/3/6/12개월 수익률, 52주 고저 대비, 최대낙폭, 20일 평균 거래대금, 시총(주식수×종가) | Nasdaq historical API (비공식, 캐시 `raw.px_daily`) | 신호 발생일 전후 수익률을 같이 줘 "이미 반영됐는가"를 묻는다 |
| 수급·내부자 | 90일 신호·리스크, Form 4 거래 상세(임원·금액·가격), FINRA 공매도 잔고 추이 | `core.signals`, `raw.sec_form4_*`, `raw.finra_short_interest` | 내부자 매수가 vs 현재가 를 명시 |
| 섹터·경쟁·매크로 | SIC 동일 유니버스 피어(시총·수익률), 리서치 단계 웹 검색 | `core.companies` + web_search | 피어 목록은 검색 질의의 앵커 |

비용 상한: 10-K 섹션은 Item 1 ≤ 25k자, 1A ≤ 15k자, 7 ≤ 25k자, 8-K ≤ 6k자/건. 브리프 1건 ≈ 60~90k 입력 토큰 → 약 $0.3~0.7 (Sonnet, 검색 8회 포함).

### 3. 브리프 스키마 (구조화 JSON, 한국어 서술)

```
header        회사·티커·섹터·기준일·현재가·시총·점수
history       창업/전환점/현재 사업 (3~6 문장, 10-K 근거)
current_state 재무 상태·런웨이·최근 공시 요약 (수치 인용)
market        macro / sector / theme 각각 "무엇이 변하고 있고 이 회사에 어떤 의미" + 출처
business_change 매출 구성·고객·사업구조 변화, 경쟁사 비교 (표)
price_context  주가 추세, 신호 대비 반응, 밸류에이션 맥락 (시총 대비 매출·현금)
why_now       신호 교차 해석 — 왜 지금 이 종목인가, 시장이 아직 반영 못한 것
scenarios     bull / base / bear: 확률(합 1.0) · 12~36개월 경로 · 핵심 드라이버 · 트리거 이벤트 · 가격 함의
tenbagger_path 10배가 되려면 무엇이 맞아야 하는가 (시총 목표 역산: 매출×배수 또는 비교기업)
thesis        한 문단 투자 논제
risks         [{risk, evidence_url, severity, mitigant}]
falsifiers    [{statement, check_by(date), metric, threshold}] — 이게 깨지면 논제 철회
predictions   [{claim, due_date, measurable}] — 포워드 채점용 (ideas.predictions)
scores        conviction 1~5, asymmetry 1~5, data_quality 1~5, time_horizon_months
hard_data     인용한 원문 링크 목록 (accession·URL)
```

- 모든 수치 주장에는 데이터팩 안의 값 또는 리서치 출처 URL 이 붙어야 한다 (프롬프트에 명시, 비평 단계가 점검).
- 시나리오 확률은 "모른다"를 허용하되 합이 1 이 되게 하고, 각 시나리오에 **먼저 관측될 트리거**를 쓰게 한다 — 분기 채점 때 어느 시나리오로 가고 있는지 판정할 수 있어야 한다.

### 4. 저장과 채점

- `ideas.briefs`: 버전 누적 (같은 CIK 라도 새 실행은 새 행). `brief` / `research` / `critique` / `datapack_summary` jsonb, 모델·토큰·비용 기록.
- `ideas.predictions`: 브리프에서 뽑은 예측 행. `outcome` (pending/hit/miss/unclear) 은 사람이 분기마다 채운다 (ADR-0008 §결과). 나중에 Audit 에이전트가 가격·공시로 자동 채점.
- `core.candidates.status` 는 브리프 생성 시 `briefed` 로 바꾼다.
- 캐시: `raw.sec_documents` (10-K/8-K 추출 텍스트), `raw.px_daily` (일봉). 재실행 시 재다운로드 없음.

### 5. 프롬프트 원칙 (`wsj/briefs/prompts.py`)

1. **근거 위계**: 10-K/8-K/XBRL(회사 1차) > 규제기관 DB > 거래 데이터 > 웹 기사 > 모델 사전지식. 사전지식만으로 사실을 쓰지 말고, 모르면 "데이터 없음".
2. **시간 고정**: 기준일 명시, 사전지식의 최신 사건은 날짜를 모르면 쓰지 않는다. 웹 리서치가 날짜를 붙인다.
3. **반대 가설 먼저**: why_now 를 쓰기 전에 "이 신호가 아무 의미 없을 가능성"을 한 문단 쓰게 한다 (루틴 매수, 자금조달 직전 연출 등).
4. **숫자로 끝내기**: 시나리오마다 시총·매출·현금 중 최소 한 가지 수치 경로.
5. **한국어 서술, 고유명사·티커·재무 용어는 원문**.

## 대안과 기각 이유

- 단일 호출(전체 자료 + 검색 + 작성): 검색 턴마다 10-K 문맥 재과금, 검색 결과가 1차 자료를 압도, 프롬프트 디버깅 불가 → 기각.
- 외부 리서치 API (Perplexity 등): 추가 키·비용, 출처 포맷 상이. Claude 서버 도구 `web_search` 가 인용(`web_search_result_location`)을 같이 주므로 그대로 사용.
- 전문 10-K 전체 투입(1M 문맥): 가능하지만 건당 $1 이상, 품질 향상 근거 없음. 섹션 추출 + 캡으로 시작, 필요 시 `--full-10k` 옵션.
- 가격 데이터 유료(Polygon 등): ADR-0008. Nasdaq 비공식 API 는 UA 만 있으면 동작하며 1년 일봉으로 충분. 막히면 Yahoo chart 폴백.

## 결과

- 신규: `wsj/briefs/{datapack,prompts,llm,build}.py`, `wsj/parsers/sec_html.py`, `wsj/marketdata/nasdaq.py`, 마이그레이션 0010, 화면 `/briefs`, 워크플로 `briefs.yml` (수동 + 주 1회).
- 시크릿: `ANTHROPIC_API_KEY` (GitHub Actions). 로컬은 `pipeline/.env`.
- 프롬프트 변경은 코드 리뷰 대상이다 — 버전 문자열을 브리프 행에 남긴다 (`prompt_version`).
- 열린 문제: 분기 채점 UI, 피어 비교의 자동화(현재는 SIC 동일 + 검색), 10-K 가 없는 신규 상장사(S-1 폴백) — BACKLOG S-4~S-6.
