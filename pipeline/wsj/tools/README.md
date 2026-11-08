# wsj.tools — 리서치 계산 도구

리서치 에이전트(Claude 세션)가 숫자를 글로 계산하지 않고 **코드로 재현 가능하게** 얻기 위한 도구 모음.
모든 명령은 JSON 한 덩어리를 stdout 으로 낸다 (로그는 stderr, `-v` 일 때만). API 키는 필요 없다.

```bash
cd pipeline
python -m wsj tools <명령> --help      # 또는 python -m wsj.tools <명령>
```

| 명령 | 하는 일 | 출처 |
|---|---|---|
| `quote` | 마지막 종가, 시총(USD·KRW), 1m/3m/6m/1y/YTD 등락, 52주 고저 | raw.px_daily → Nasdaq / Naver |
| `history` | 기간 일봉 종가(·거래량, `--ohlc`) | raw.px_daily → Nasdaq / Naver |
| `lookup` | 이름·티커 → 거래소, CIK, 가격 키(`px_key`) | SEC 티커표(7일 캐시) · Naver 자동완성 · Nasdaq 자동완성 |
| `fx` | 환율 (기본 USDKRW, `--date` 과거) | ref.fx_rates → Frankfurter(ECB) → open.er-api.com |
| `rates` | 미 국채 수익률 곡선 3m·2y·10y·30y + 전체 + 스프레드 | home.treasury.gov CSV |
| `event` | 지정일 전후 수익률·거래량, 벤치마크 대비 초과·비정상 수익률 | 위 가격 경로 |
| `exposure` | 묶음(기본 NVDA,AVGO,VRT,GEV,PWR)·벤치마크 대비 베타·상관, 구간 수익률 | 위 가격 경로 |
| `reverse-dcf` | 시총이 요구하는 FCF CAGR / `--forward` 성장 경로 → 가치 | 순수 계산 |
| `peers` | 시총·EV·매출·영업이익·순이익·P/E·EV/Sales·EV/EBIT | raw.company_fundamentals → SEC companyfacts / Naver 분기 |
| `incremental` | 시나리오 → 부품별 Δ$ → 회사별 Δ매출·Δ순이익·÷시총, 민감도 | 입력 JSON 만 |

## 예시

```bash
python -m wsj tools quote FPS 001440                 # 여러 종목이면 {"results": [...]}
python -m wsj tools quote VRT --as-of 2026-11-05
python -m wsj tools history FPS --start 2026-10-01 --end 2026-11-06
python -m wsj tools lookup forgent                   # → FPS (NYSE, CIK)
python -m wsj tools lookup 효성                       # → 004800, 298040(효성중공업) ...
python -m wsj tools lookup 엔비디아                    # Naver 자동완성은 미국 종목 한글명도 찾는다
python -m wsj tools fx                               # USDKRW
python -m wsj tools fx EURUSD --date 2026-11-04
python -m wsj tools rates 2026-11-06
python -m wsj tools event FPS 2026-11-04             # 벤치마크 기본 SPY, 한국 종목이면 069500
python -m wsj tools event 001440 2026-11-05
python -m wsj tools exposure FPS POWL ETN --period 2026-05-15:2026-10-06 --period 2026-10-06:2026-11-06
python -m wsj tools exposure 001440 298040 --basket 005930,000660 --benchmark 069500
python -m wsj tools reverse-dcf --market-cap 5.93e9 --net-debt 0.48e9 --fcf 0.15e9 --discount 0.10 --terminal 0.03
python -m wsj tools reverse-dcf --forward --growth 0.30,0.25,0.20,0.15,0.12 --years 10 \
    --fcf 0.15e9 --discount 0.10 --terminal 0.03 --market-cap 5.93e9
python -m wsj tools peers FPS POWL ETN 001440
python -m wsj tools incremental tests/fixtures/tools/incremental_8gw.json --top 15
```

공통 옵션: `--no-db`(DB 안 봄) · `--live`(가격 캐시 건너뜀) · `--today YYYY-MM-DD` · `--compact` · `-v`.

## Python 에서

```python
from wsj.tools import open_context, quote, event, exposure, reverse_dcf, incremental_run

with open_context() as ctx:                 # 연결·환율·티커표를 재사용
    q = quote("FPS", ctx=ctx)
    e = event("FPS", "2026-11-04", ctx=ctx)
r = reverse_dcf(base_fcf=0.15e9, discount_rate=0.10, terminal_growth=0.03, years=10, market_cap=5.93e9, net_debt=0.48e9)
```

`ctx` 없이 불러도 된다 (그때그때 열고 닫는다). 실패는 `ToolError` (CLI 는 `{"error": ...}` + 종료코드 1).

## 정의 (숫자가 바뀌지 않게 고정한 규칙)

- **종목 표기**: 6자리 숫자 = 한국(`001440`, `KRX:001440`, `298040.KS` 도 됨), 그 밖 = 미국 티커(`BRK.B` 그대로).
- **가격은 수정주가가 아니다** (Nasdaq·Naver 모두 조정 플래그 없음). 분할이 낀 구간은 수익률이 깨질 수 있다 — 결과에 `"adjusted": false`.
- **기간 수익률 a→b** = b 이하 마지막 종가 ÷ a 이하 마지막 종가 − 1. 실제 쓴 날짜·종가를 함께 낸다.
- **1m/3m/6m/1y** = 마지막 거래일에서 달력 기준 N개월 전(말일 보정) 이하 마지막 종가 대비. **YTD** = 전년 마지막 거래일 종가 대비. 이력이 짧으면(신규 상장) null.
- **일간 등락**은 종가 대 종가. 네이버 화면의 등락률은 기준가 기준이라 다를 수 있다 (예: 대한전선 11/6 화면 −5.60%, 종가 대비 −6.17%).
- **베타·상관**: 일간 단순수익률, 표본(n−1) 공분산. 묶음은 동일가중, 모든 구성 종목에 수익률이 있는 날만. 한국·미국을 섞으면 시차 때문에 상관이 낮게 나온다.
- **이벤트일 d** = 지정일 당일(거래일이면) 또는 다음 거래일. 창: d-1→d, d→d+1, d-1→d+1, d-5→d+5. 거래량 = d·d+1 ÷ 직전 20거래일 평균. 비정상 수익률 = 종목 − β × 벤치마크, β 는 d-5 이전 120거래일(60개 미만이면 null).
- **시총**: 미국 = Nasdaq summary MarketCap (다중 클래스 회사는 상장 클래스만일 수 있음 → DB 에 발행주식수가 있으면 `db_shares_x_close` 도 표시). 한국 = Naver `marketValue`. 과거 `--as-of` 는 (현재 시총 ÷ 현재가) × 그날 종가.
- **역DCF**: 연말 할인, FCF_t = FCF_0 (1+g)^t, TV = FCF_N (1+g_term)/(r − g_term), 지분가치 = EV − 순차입금. 기준 FCF ≤ 0 이면 풀지 않는다. 탐색 범위 −95% ~ +500%/년.
- **peers**: TTM = 최근 4개 분기 합(빠진 분기가 있으면 null). EBIT = 영업이익. 순차입금 = SEC 장단기 차입금 − 현금·단기투자 (태그가 없으면 null, 한국은 출처 없음 → EV null). 이익 ≤ 0 이면 배수 null.

## incremental 입력 형식

```jsonc
{
  "units": "USD bn; unit costs per GW",                 // 표시용
  "scenarios": {"base": {"TX": 11}, "event": {"DEST": 8, "NEW_TERMS": 4}},
  "mixes": {                                            // 가중 묶음 (다른 mix 를 품을 수 있음, 순환 금지)
    "TX":   {"bldg": 1, "cool_evap": 0.30, "pwr_grid": 0.45, "pwr_turb": 0.35},
    "DEST": {"OK": 0.25, "LA": 0.15, "MW": 0.275}
  },
  "unit_costs": {"turbine": {"pwr_turb": 1.60}, "mv_swgr": {"bldg": 0.60}},   // 부품 → {기초 드라이버: 단위당 금액}
  "suppliers": {"mv_swgr": {"ETN": 0.25, "FPS": 0.08}},                       // 부품 → {회사: 점유율}
  "companies": {"ETN": {"margin": 0.25, "mcap": 129.9}},                      // 증분 영업이익률, 시총(같은 금액 단위)
  "tax": 0.22,
  "sensitivities": {"low_reloc": {"scenarios.event.DEST": 5}}                // 점 경로 → 그 노드를 통째로 교체
}
```

계산: Δ[부품] = Σ q_event × 단가 − Σ q_base × 단가 → Δ매출[회사] = Σ Δ[부품] × 점유율 → Δ순이익 = Δ매출 × margin × (1 − tax) → ÷ 시총.
`companies` 에 없는 공급사는 Δ순이익 null + 경고. 예제 `tests/fixtures/tools/incremental_8gw.json` 은 연구 스크래치 `deep4/model.py`
(텍사스 11GW vs 이전 8GW + 소실 3GW + 신규 조건 4GW)를 그대로 옮긴 것이고, 테스트가 원래 스크립트 결과와 숫자가 같은지 확인한다.

## 출처별 주의

- `api.nasdaq.com`: 브라우저 UA + Origin/Referer 필요. ETF 는 `assetclass=etf` (자동으로 주식 → ETF 순서로 시도). 없는 티커는 `data: null`.
- `*.naver.com`: Origin 헤더를 붙이면 `Invalid CORS request` 로 거절된다 — UA·Accept 만 보낸다.
- `www.sec.gov`: 연락처가 든 `SEC_USER_AGENT` 필요. 막히면 묵은 캐시 → Nasdaq 자동완성으로 대체 (`errors` 에 기록).
- DB: `SUPABASE_URL`·`SUPABASE_SECRET_KEY` 가 있을 때만, select 만 쓴다. `ref` 스키마가 PostgREST 에 노출되지 않으면 fx 는 바로 공개 출처로 간다.
