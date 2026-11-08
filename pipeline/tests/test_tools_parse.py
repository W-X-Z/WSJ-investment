"""wsj.tools 파서 — 실제 응답을 줄인 픽스처 (tests/fixtures/tools, 2026-11-07 수집)."""

import json
from pathlib import Path

import pytest

from wsj.tools import parse as P
from wsj.tools.context import ToolError
from wsj.tools.prices import parse_symbol

FX = Path(__file__).parent / "fixtures" / "tools"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("raw,want", [("$19.48", 19.48), ("14,829,490", 14829490.0), ("+6.92%", 6.92), ("-1,010", -1010.0),
                                      ("−1.5", -1.5), ("N/A", None), ("", None), ("--", None), (None, None), (3, 3.0),
                                      ("1.77배", 1.77), ("-82원", -82.0)])
def test_num(raw, want):
    assert P.num(raw) == want


def test_nasdaq_history_dollar_comma_and_sorting():
    bars = P.parse_nasdaq_history(load("nasdaq_history_fps.json"))
    assert bars[0]["date"] < bars[-1]["date"]                      # 응답은 최신순 → 오름차순으로
    last = bars[-1]
    assert last == {"date": "2026-11-06", "open": 19.65, "high": 19.88, "low": 17.67, "close": 19.48, "volume": 14829490}


def test_nasdaq_history_etf_has_no_dollar_sign():
    bars = P.parse_nasdaq_history(load("nasdaq_history_spy_etf.json"))
    assert bars[-1]["close"] == 735.29 and bars[-1]["volume"] == 58978820


def test_nasdaq_null_payload():
    payload = load("nasdaq_history_null.json")
    assert not P.nasdaq_has_data(payload) and P.parse_nasdaq_history(payload) == []
    assert P.parse_nasdaq_info(payload) is None and P.parse_nasdaq_summary(payload) is None


def test_nasdaq_info_summary_autocomplete():
    info = P.parse_nasdaq_info(load("nasdaq_info_fps.json"))
    assert info["exchange"] == "NYSE" and info["last_sale"] == 19.47 and info["pct_change"] == 6.92
    assert info["trade_date"] == "2026-11-06"
    s = P.parse_nasdaq_summary(load("nasdaq_summary_fps.json"))
    assert s["market_cap"] == 5927230469.0 and s["exchange"] == "NYSE" and s["previous_close"] == 18.21
    ac = P.parse_nasdaq_autocomplete(load("nasdaq_autocomplete_forgent.json"))
    assert ac[0]["ticker"] == "FPS" and ac[0]["exchange"] == "NYSE"


def test_naver_chart_and_sise_agree():
    chart = P.parse_naver_chart(load("naver_chart_001440.json"))
    sise = P.parse_naver_sise((FX / "naver_sise_001440.txt").read_text(encoding="utf-8"))
    assert chart[-1]["date"] == "2026-11-06" and chart[-1]["close"] == 17040.0 and chart[-1]["volume"] == 2306140
    common = {b["date"]: b["close"] for b in sise}
    assert all(common[b["date"]] == b["close"] for b in chart if b["date"] in common)


def test_naver_basic_and_integration():
    b = P.parse_naver_basic(load("naver_basic_001440.json"))
    assert b == {**b, "code": "001440", "name": "대한전선", "exchange": "KOSPI", "close": 17040.0, "pct_change": -5.6,
                 "trade_date": "2026-11-06"}
    i = P.parse_naver_integration(load("naver_integration_001440.json"))
    assert i["market_cap_krw"] == 3_339_700_000_000 and i["market_cap_text"] == "3조 3,397억"


@pytest.mark.parametrize("raw,want", [("3조 3,397억", 3.3397e12), ("15조 312억", 15.0312e12), ("387억", 3.87e10),
                                      ("1조", 1e12), ("1,234만", 1.234e7), ("12,345", 12345.0), ("2,557억원", 2.557e11),
                                      ("N/A", None), ("", None), ("abc", None)])
def test_krw_amount(raw, want):
    got = P.parse_krw_amount(raw)
    assert (got is None and want is None) or abs(got - want) < 1e-3


def test_naver_autocomplete_markets():
    rows = P.parse_naver_autocomplete(load("naver_ac_hyosung.json"))
    assert rows[0] == {"market": "kr", "ticker": "004800", "name": "효성", "exchange": "KOSPI", "reuters_code": "004800"}
    us = P.parse_naver_autocomplete({"items": [{"code": "NVDA", "name": "엔비디아", "typeCode": "NASDAQ", "nationCode": "USA",
                                                "category": "stock", "reutersCode": "NVDA.O"}]})
    assert us[0]["market"] == "us" and us[0]["ticker"] == "NVDA"


def test_treasury_csv_tenors():
    rows = P.parse_treasury_csv((FX / "treasury_2026.csv").read_text())
    assert rows[-1]["date"] == "2026-11-06"
    c = rows[-1]["curve"]
    assert (c["3m"], c["2y"], c["10y"], c["30y"]) == (4.19, 4.51, 4.86, 5.26)
    assert c["1.5m"] == 4.07 and "1y" in c
    assert [P.tenor_key(x) for x in ("1 Mo", "1.5 Month", "4 Mo", "20 Yr")] == ["1m", "1.5m", "4m", "20y"]


def test_sec_tickers_exchange():
    rows = P.parse_sec_tickers_exchange({"fields": ["cik", "name", "ticker", "exchange"],
                                         "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"], [1067983, "BERKSHIRE HATHAWAY INC", "BRK-B", "NYSE"]]})
    assert rows[1] == {"cik": 1067983, "name": "BERKSHIRE HATHAWAY INC", "ticker": "BRK-B", "exchange": "NYSE"}


def test_fx_parsers():
    f = P.parse_frankfurter(load("frankfurter_usd_krw.json"))
    assert f == {"base": "USD", "date": "2026-11-06", "rates": {"KRW": 1358.73}}
    e = P.parse_er_api({"result": "success", "base_code": "USD", "time_last_update_utc": "Sat, 07 Nov 2026 00:02:31 +0000",
                        "rates": {"KRW": 1356.67}})
    assert e == {"base": "USD", "date": "2026-11-07", "rates": {"KRW": 1356.67}}
    assert P.parse_er_api({"result": "error"}) is None


@pytest.mark.parametrize("raw,market,code", [("FPS", "us", "FPS"), ("brk.b", "us", "BRK.B"), ("001440", "kr", "001440"),
                                             ("KRX:001440", "kr", "001440"), ("KOSDAQ:086390", "kr", "086390"),
                                             ("298040.KS", "kr", "298040"), ("US:etn", "us", "ETN")])
def test_parse_symbol(raw, market, code):
    s = parse_symbol(raw)
    assert (s.market, s.code) == (market, code)


def test_parse_symbol_rejects_garbage_and_keys():
    with pytest.raises(ToolError):
        parse_symbol("not a ticker!")
    assert parse_symbol("001440").px_keys == ["KRX:001440", "KOSDAQ:001440"]
    assert parse_symbol("FPS").px_keys == ["FPS"]
