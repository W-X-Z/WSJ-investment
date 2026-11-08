"""wsj.tools 도구 함수 — 가짜 페처(픽스처)와 가짜 DB 로, 네트워크 없이."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from wsj.tools import calc as C
from wsj.tools.context import ReadOnlyStore, ToolContext, ToolError
from wsj.tools.event import event
from wsj.tools.fx import fx, rate_from_usd_per_unit
from wsj.tools.lookup import lookup, rank_sec
from wsj.tools.peers import latest_fundamental, peers, ratios, sec_derived
from wsj.tools.prices import history
from wsj.tools.quote import quote
from wsj.tools.rates import rates

FX = Path(__file__).parent / "fixtures" / "tools"
TODAY = date(2026, 11, 8)


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def synth_nasdaq(closes_by_date, dollar=True):
    rows = [{"date": f"{d[5:7]}/{d[8:10]}/{d[:4]}", "close": f"${c:,.2f}" if dollar else f"{c:.2f}", "volume": "1,000",
             "open": "N/A", "high": "N/A", "low": "N/A"} for d, c in sorted(closes_by_date.items(), reverse=True)]
    return {"data": {"symbol": "X", "tradesTable": {"rows": rows}}}


def weekdays(start, n):
    out, d = [], date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


class FakeFetch:
    """Fetchers 와 같은 메서드 이름. calls 에 호출 기록."""

    def __init__(self, sec_ok=True):
        self.calls = []
        self.sec_ok = sec_ok
        self.us_hist = {"FPS": load("nasdaq_history_fps.json")}
        self.etf_hist = {"SPY": load("nasdaq_history_spy_etf.json")}

    def nasdaq_history(self, ticker, start, end, assetclass="stocks"):
        self.calls.append(("nasdaq_history", ticker, assetclass))
        src = self.us_hist if assetclass == "stocks" else self.etf_hist
        return src.get(ticker) or load("nasdaq_history_null.json")

    def nasdaq_info(self, ticker, assetclass="stocks"):
        self.calls.append(("nasdaq_info", ticker, assetclass))
        return load("nasdaq_info_fps.json") if ticker == "FPS" and assetclass == "stocks" else load("nasdaq_history_null.json")

    def nasdaq_summary(self, ticker, assetclass="stocks"):
        return load("nasdaq_summary_fps.json") if ticker == "FPS" else load("nasdaq_history_null.json")

    def nasdaq_autocomplete(self, q):
        self.calls.append(("nasdaq_autocomplete", q))
        return load("nasdaq_autocomplete_forgent.json")

    def naver_basic(self, code):
        return load("naver_basic_001440.json")

    def naver_integration(self, code):
        return load("naver_integration_001440.json")

    def naver_chart(self, code, start, end):
        self.calls.append(("naver_chart", code))
        return load("naver_chart_001440.json")

    def naver_sise(self, code, start, end):
        return (FX / "naver_sise_001440.txt").read_text(encoding="utf-8")

    def naver_autocomplete(self, q):
        return load("naver_ac_hyosung.json")

    def naver_quarters(self, code):
        return load("naver_quarters_001440.json")

    def sec_tickers(self):
        if not self.sec_ok:
            raise RuntimeError("HTTP 403 (rate threshold)")
        return {"fields": ["cik", "name", "ticker", "exchange"],
                "data": [[1, "Forgent Power Solutions, Inc.", "FPS", "NYSE"], [2, "Powell Industries Inc", "POWL", "Nasdaq"],
                         [3, "Forge Global Holdings", "FRGE", "NYSE"]]}, "fixture"

    def sec_companyfacts(self, cik):
        self.calls.append(("sec_companyfacts", cik))
        return companyfacts()

    def treasury_csv(self, year):
        self.calls.append(("treasury_csv", year))
        if year == 2026:
            return (FX / "treasury_2026.csv").read_text()
        return 'Date,"3 Mo","2 Yr","10 Yr","30 Yr"\n12/31/2025,4.30,4.20,4.50,4.80\n12/30/2025,4.31,4.21,4.51,4.81\n'

    def fx_frankfurter(self, base, quote, day=None):
        self.calls.append(("frankfurter", base, quote, day))
        usd_krw = load("frankfurter_usd_krw.json")["rates"]["KRW"]
        table = {("USD", "KRW"): usd_krw, ("KRW", "USD"): 1 / usd_krw}
        return {"amount": 1.0, "base": base, "date": "2026-11-06", "rates": {quote: table[(base, quote)]}}

    def fx_er_api(self, base):
        return {"result": "success", "base_code": base, "time_last_update_utc": "Sat, 07 Nov 2026 00:02:31 +0000",
                "rates": {"KRW": 1356.0}}


def companyfacts():
    """xbrl.build_financials 가 읽는 최소 구조: 4개 분기 매출·영업이익·순이익, 분기말 현금·차입금."""
    def q(vals, unit="USD"):
        ends = ["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"]
        starts = ["2025-10-01", "2026-01-01", "2026-04-01", "2026-07-01"]
        return {"units": {unit: [{"start": s, "end": e, "val": v, "filed": "2026-11-01", "form": "10-Q", "fy": 2026, "fp": "Q"}
                                 for s, e, v in zip(starts, ends, vals, strict=True)]}}

    def inst(v):
        return {"units": {"USD": [{"end": "2026-09-30", "val": v, "filed": "2026-11-01", "form": "10-Q", "fy": 2026, "fp": "Q3"}]}}

    return {"facts": {"us-gaap": {"Revenues": q([100, 110, 120, 130]), "OperatingIncomeLoss": q([10, 11, 12, 13]),
                                  "NetIncomeLoss": q([5, 6, 7, 8]), "CashAndCashEquivalentsAtCarryingValue": inst(40),
                                  "LongTermDebtNoncurrent": inst(90), "LongTermDebtCurrent": inst(10)}}}


class FakeDB:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def select(self, table, columns=None, filters=None, limit=None, order=None):
        self.calls.append((table, filters))
        if table not in self.tables:
            raise RuntimeError(f"PGRST106 {table}")
        rows = list(self.tables[table])
        for col, val in (filters or {}).items():
            if isinstance(val, list):
                rows = [r for r in rows if r.get(col) in val]
            elif isinstance(val, tuple):
                op, v = val
                rows = [r for r in rows if (str(r.get(col)) >= str(v) if op == "gte" else str(r.get(col)) <= str(v))]
            else:
                rows = [r for r in rows if r.get(col) == val]
        return rows


def ctx(fetch=None, db=None, live=False):
    return ToolContext(fetch=fetch or FakeFetch(), store=ReadOnlyStore(db) if db else None, today=TODAY, use_px_cache=not live)


# ---------------------------------------------------------------- history / quote
def test_history_live_us_and_etf_fallback():
    c = ctx()
    h = history("SPY", "2026-10-20", "2026-11-07", ctx=c)
    assert h["source"] == "nasdaq:etf" and h["rows"][-1] == {"date": "2026-11-06", "close": 735.29, "volume": 58978820}
    assert ("nasdaq_history", "SPY", "stocks") in c.fetch.calls and ("nasdaq_history", "SPY", "etf") in c.fetch.calls
    with pytest.raises(ToolError):
        history("ZZZZ", "2026-10-20", "2026-11-07", ctx=c)


def test_history_prefers_fresh_cache_and_skips_stale_cache():
    days = weekdays("2026-10-01", 27)                                           # ~ 11/06 까지
    rows = [{"ticker": "KRX:001440", "trade_date": d, "open": None, "high": None, "low": None, "close": 100 + i, "volume": 5}
            for i, d in enumerate(days)]
    c = ctx(db=FakeDB({"raw.px_daily": rows}))
    h = history("001440", "2026-10-01", "2026-11-07", ctx=c)
    assert h["source"] == "db:raw.px_daily" and h["n"] == 27 and not any(x[0] == "naver_chart" for x in c.fetch.calls)
    stale = ctx(db=FakeDB({"raw.px_daily": rows[:10]}))                         # 10/14 에서 끊김 → 라이브
    assert history("001440", "2026-10-01", "2026-11-07", ctx=stale)["source"] == "naver:chart"
    live = ctx(db=FakeDB({"raw.px_daily": rows}), live=True)                    # --live
    assert history("001440", "2026-10-01", "2026-11-07", ctx=live)["source"] == "naver:chart"


def test_quote_us_fixture():
    q = quote("FPS", ctx=ctx())
    assert q["exchange"] == "NYSE" and q["price"]["close"] == 19.48 and q["price"]["date"] == "2026-11-06"
    assert q["price"]["prev_close"] == 18.21 and q["price"]["day_change_pct"] == pytest.approx(6.97)
    mc = q["market_cap"]
    assert mc["usd"] == 5927230469.0 and mc["krw"] == pytest.approx(5927230469.0 * 1358.73)
    assert mc["fx"]["source"].startswith("frankfurter")
    assert q["live"]["last_sale"] == 19.47
    assert q["changes"]["1m"] is None and q["history_from"] == "2026-10-20"     # 픽스처 이력이 짧다 → null


def test_quote_kr_fixture_and_db_shares():
    db = FakeDB({"raw.company_facts": [{"company_id": "company:taihan", "ticker": "KRX:001440", "currency": "KRW",
                                        "shares_outstanding": 196_000_000, "shares_as_of": "2026-11-01", "source": "naver_mobile"}]})
    q = quote("001440", ctx=ctx(db=db))
    assert q["name"] == "대한전선" and q["exchange"] == "KOSPI" and q["price"]["source"] == "naver:chart"
    mc = q["market_cap"]
    assert mc["krw"] == 3_339_700_000_000 and mc["usd"] == pytest.approx(3_339_700_000_000 / 1358.73)
    assert mc["db_shares_x_close"]["market_cap_local"] == 196_000_000 * 17040.0


def test_quote_past_as_of_scales_market_cap():
    q = quote("FPS", as_of="2026-11-04", ctx=ctx())
    assert q["price"]["date"] == "2026-11-04" and "live" not in q
    implied = 5927230469.0 / 19.47
    assert q["market_cap"]["usd"] == pytest.approx(implied * q["price"]["close"])


# ---------------------------------------------------------------- event (도구 경로)
def test_event_tool_with_synthetic_series():
    days = weekdays("2026-04-01", 160)
    stock = {d: 100.0 for d in days}
    bench = {d: 50.0 for d in days}
    ev_day = days[150]
    for d in days[150:]:
        stock[d] = 90.0
    f = FakeFetch()
    f.us_hist = {"ABC": synth_nasdaq(stock)}
    f.etf_hist = {"SPY": synth_nasdaq(bench, dollar=False)}
    out = event("ABC", ev_day, ctx=ctx(f))
    assert out["benchmark"] == "SPY" and out["event_date"] == ev_day
    assert out["returns"]["d-1_to_d"]["return_pct"] == -10.0 and out["returns"]["d-1_to_d"]["excess_pct"] == -10.0
    assert out["returns"]["d-5_to_d+5"]["return_pct"] == -10.0
    assert out["sources"] == {"symbol": "nasdaq:stocks", "benchmark": "nasdaq:etf"}


# ---------------------------------------------------------------- fx / rates
def test_fx_db_then_public_fallback():
    db = FakeDB({"ref.fx_rates": [{"currency": "KRW", "usd_per_unit": 1 / 1400, "as_of": "2026-11-05"}]})
    r = fx("USDKRW", ctx=ctx(db=db))
    assert r["rate"] == pytest.approx(1400.0) and r["source"] == "db:ref.fx_rates"
    r2 = fx("USD/KRW", ctx=ctx(db=FakeDB({})))                                  # ref 스키마 비노출(PGRST106) → Frankfurter
    assert r2["rate"] == 1358.73 and r2["source"].startswith("frankfurter") and r2["fallback_notes"]
    assert fx("KRWKRW", ctx=ctx())["rate"] == 1.0
    with pytest.raises(ToolError):
        fx("dollars", ctx=ctx())


def test_rate_from_usd_per_unit_cross():
    rows = [{"currency": "KRW", "usd_per_unit": 0.0007, "as_of": "2026-11-05"}, {"currency": "JPY", "usd_per_unit": 0.0063, "as_of": "2026-11-04"}]
    rate, as_of = rate_from_usd_per_unit(rows, "JPY", "KRW")
    assert rate == pytest.approx(9.0) and as_of == "2026-11-04"
    assert rate_from_usd_per_unit(rows, "EUR", "KRW") is None


def test_rates_exact_weekend_and_new_year():
    c = ctx()
    assert rates("2026-11-06", ctx=c)["yields"] == {"3m": 4.19, "2y": 4.51, "10y": 4.86, "30y": 5.26}
    sat = rates("2026-11-07", ctx=c)
    assert sat["as_of"] == "2026-11-06" and sat["spreads_bp"]["10y_2y"] == 35.0
    ny = rates("2026-01-01", ctx=c)                                            # 2026 CSV 에 1/1 이전 값 없음 → 2025
    assert ny["as_of"] == "2025-12-31" and ny["yields"]["10y"] == 4.50 and ("treasury_csv", 2025) in c.fetch.calls


# ---------------------------------------------------------------- lookup
def test_lookup_sec_ranking_and_korean():
    c = ctx()
    r = lookup("forg", ctx=c)
    assert [x["ticker"] for x in r["results"] if x["market"] == "us"] == ["FPS", "FRGE"]
    assert lookup("FPS", market="us", ctx=c)["results"][0]["match"] == "ticker"
    kr = lookup("효성", ctx=c)
    assert kr["results"][0] == {"market": "kr", "ticker": "004800", "name": "효성", "exchange": "KOSPI",
                                "source": "naver:autocomplete", "match": "autocomplete", "px_key": "KRX:004800"}
    code = lookup("001440", ctx=c)["results"][0]
    assert code["name"] == "대한전선" and code["px_key"] == "KRX:001440"


def test_lookup_falls_back_when_sec_blocked():
    c = ctx(FakeFetch(sec_ok=False))
    r = lookup("forgent", market="us", ctx=c)
    assert r["results"][0]["source"] == "nasdaq:autocomplete" and r["results"][0]["ticker"] == "FPS"
    assert any("sec tickers" in e for e in r["errors"])


def test_rank_sec_exact_name():
    rows = [{"cik": 1, "name": "Eaton Corp plc", "ticker": "ETN", "exchange": "NYSE"},
            {"cik": 2, "name": "Eaton Vance Fund", "ticker": "EVX", "exchange": "NYSE"}]
    ranked = rank_sec(rows, "Eaton Corp")                                      # 'CORP' 는 정규화에서 빠진다 → 'EATON'
    assert [(r["ticker"], r["match"]) for r in ranked] == [("ETN", "name_exact"), ("EVX", "name_prefix")]
    assert rank_sec(rows, "evx")[0]["match"] == "ticker"


# ---------------------------------------------------------------- peers
def test_peers_live_sec_and_kr():
    out = peers(["FPS", "001440"], ctx=ctx())
    fps, kr = out["results"]
    assert fps["revenue"] == 460 and fps["operating_income"] == 46 and fps["net_income"] == 26
    assert fps["net_debt"] == 60 and fps["enterprise_value"] == 5927230469.0 + 60
    assert fps["pe"] == round(5927230469.0 / 26, 2) and fps["sources"]["fundamentals"] == "sec:companyfacts"
    assert kr["currency"] == "KRW" and kr["net_debt"] is None and kr["enterprise_value"] is None and kr["ev_sales"] is None
    assert kr["sources"]["fundamentals"].startswith("naver:finance/quarter")
    assert kr["revenue"] == pytest.approx(41463e8)


def test_peers_prefers_db_fundamentals_and_converts_currency():
    db = FakeDB({"raw.company_facts": [{"company_id": "company:fps", "ticker": "FPS"}],
                 "raw.company_fundamentals": [
                     {"company_id": "company:fps", "period": "fy", "period_end": "2025-12-31", "currency": "USD", "revenue": 1,
                      "operating_income": 1, "net_income": 1, "source": "sec_companyfacts"},
                     {"company_id": "company:fps", "period": "ttm", "period_end": "2026-06-30", "currency": "KRW", "revenue": 1358730,
                      "operating_income": 135873, "net_income": -5, "source": "x"}]})
    row = peers(["FPS"], ctx=ctx(db=db))["results"][0]
    assert row["period"] == "ttm" and row["fundamentals_currency"] == "KRW"
    assert row["revenue"] == pytest.approx(1000.0) and row["operating_income"] == pytest.approx(100.0)  # KRW → USD
    assert row["pe"] is None                                                   # 적자 → null
    assert row["sources"]["fundamentals"].startswith("db:raw.company_fundamentals")


def test_peer_helpers():
    assert latest_fundamental([{"period": "fy", "period_end": "2026-03-31"}, {"period": "ttm", "period_end": "2025-12-31"}])["period"] == "ttm"
    assert ratios(100.0, None, 50.0, 10.0, 5.0) == {"enterprise_value": None, "pe": 20.0, "ev_sales": None, "ev_ebit": None,
                                                    "price_sales": 2.0}
    assert ratios(100.0, -20.0, 40.0, -1.0, 0.0)["ev_ebit"] is None
    from wsj.briefs.xbrl import build_financials

    d = sec_derived(build_financials(companyfacts()))
    assert (d["revenue"], d["operating_income"], d["net_income"], d["net_debt"]) == (460.0, 46.0, 26.0, 60.0)


# ---------------------------------------------------------------- CLI (네트워크 없는 도구)
def test_cli_reverse_dcf_and_error(capsys):
    from wsj.runner import main

    assert main(["tools", "reverse-dcf", "--market-cap", "1000", "--fcf", "40", "--discount", "0.09", "--terminal", "0.03",
                 "--compact"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["tool"] == "reverse-dcf" and out["implied_fcf_cagr_pct"] is not None
    assert main(["tools", "reverse-dcf", "--forward", "--growth", "0.1", "--fcf", "40", "--discount", "0.09", "--terminal",
                 "0.03", "--market-cap", "1000", "--compact"]) == 0
    fwd = json.loads(capsys.readouterr().out)
    assert "upside_vs_market_cap_pct" in fwd
    assert main(["tools", "reverse-dcf", "--market-cap", "1000", "--fcf", "40", "--discount", "0.03", "--terminal", "0.03"]) == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_trailing_changes_on_real_fixture():
    from wsj.tools import parse as P

    bars = P.parse_nasdaq_history(load("nasdaq_history_fps.json"))
    r = C.period_return(bars, "2026-11-03", "2026-11-05")
    assert r["start_close"] == 27.14 and r["end_close"] == 18.21 and r["return_pct"] == pytest.approx(-32.9)
