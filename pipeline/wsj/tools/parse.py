"""응답 파서 — 네트워크 없이 테스트하는 순수 함수만 둔다.

출처별 형식 (2026-11-08 컨테이너에서 확인):
  Nasdaq historical  data.tradesTable.rows = [{date:'11/06/2026', close:'$19.48', volume:'14,829,490', open, high, low}]
                     주식은 '$' 가 붙고 ETF 는 안 붙는다. 없는 티커·자산군이 틀리면 data=null (rCode 400).
  Nasdaq info        data.primaryData = {lastSalePrice:'$19.47', percentageChange:'+6.92%', lastTradeTimestamp:'Nov 6, 2026'}
  Nasdaq summary     data.summaryData.MarketCap.value = '5,927,230,469' (다중 클래스 회사는 상장 클래스만일 수 있다)
  Naver chart        [{localDate:'20261020', closePrice:22050.0, openPrice, highPrice, lowPrice, accumulatedTradingVolume}]
  Naver basic        {closePrice:'17,040', fluctuationsRatio:'-5.60', localTradedAt, stockExchangeType:{code:'KS'|'KQ'}}
  Naver integration  totalInfos=[{code:'marketValue', value:'3조 3,397억'}, ...]
  Treasury CSV       Date,"1 Mo","1.5 Month","2 Mo","3 Mo",...,"30 Yr"  /  11/06/2026,4.02,...
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from typing import Any

Bar = dict[str, Any]  # {date:'YYYY-MM-DD', open, high, low, close, volume}

_MISSING = {"", "N/A", "NA", "--", "-", "n/a", "null", "None"}


def num(v: Any) -> float | None:
    """'$1,234.50' · '+6.92%' · '14,829,490' · '−1.2' → float. 비었거나 'N/A' 면 None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("−", "-").replace("$", "").replace(",", "").replace("%", "").replace("+", "")
    s = s.replace("배", "").replace("원", "").strip()
    if s in _MISSING:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _bar(d: date | None, o: Any, h: Any, lo: Any, c: Any, v: Any) -> Bar | None:
    close = num(c)
    if d is None or close is None or close <= 0:
        return None
    vol = num(v)
    return {"date": d.isoformat(), "open": num(o), "high": num(h), "low": num(lo), "close": close,
            "volume": int(vol) if vol is not None else None}


def sort_bars(bars: list[Bar]) -> list[Bar]:
    by = {b["date"]: b for b in bars}
    return [by[k] for k in sorted(by)]


# ---------------------------------------------------------------- Nasdaq
def nasdaq_has_data(payload: dict[str, Any] | None) -> bool:
    return bool((payload or {}).get("data"))


def parse_nasdaq_history(payload: dict[str, Any] | None) -> list[Bar]:
    rows = ((((payload or {}).get("data") or {}).get("tradesTable") or {}).get("rows")) or []
    out = []
    for r in rows:
        try:
            d = datetime.strptime(str(r.get("date")), "%m/%d/%Y").date()
        except ValueError:
            continue
        b = _bar(d, r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("volume"))
        if b:
            out.append(b)
    return sort_bars(out)


def _nasdaq_day(ts: str | None) -> str | None:
    m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", ts or "")
    if not m:
        return None
    return datetime.strptime(" ".join(m.groups()), "%b %d %Y").date().isoformat()


def parse_nasdaq_info(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    d = (payload or {}).get("data")
    if not d:
        return None
    p = d.get("primaryData") or {}
    return {
        "symbol": d.get("symbol"),
        "name": d.get("companyName"),
        "exchange": d.get("exchange"),
        "stock_type": d.get("stockType"),
        "asset_class": d.get("assetClass"),
        "last_sale": num(p.get("lastSalePrice")),
        "net_change": num(p.get("netChange")),
        "pct_change": num(p.get("percentageChange")),
        "last_trade_timestamp": p.get("lastTradeTimestamp"),
        "trade_date": _nasdaq_day(p.get("lastTradeTimestamp")),
        "market_status": d.get("marketStatus"),
    }


def parse_nasdaq_summary(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    d = (payload or {}).get("data")
    if not d:
        return None
    s = d.get("summaryData") or {}

    def val(k: str) -> Any:
        return (s.get(k) or {}).get("value")

    return {
        "exchange": val("Exchange"),
        "sector": val("Sector"),
        "industry": val("Industry"),
        "market_cap": num(val("MarketCap")),
        "previous_close": num(val("PreviousClose")),
        "average_volume": num(val("AverageVolume")),
        "fifty_two_week": val("FiftTwoWeekHighLow"),
        "one_year_target": num(val("OneYrTarget")),
    }


def parse_nasdaq_autocomplete(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for r in (payload or {}).get("data") or []:
        if not r.get("symbol"):
            continue
        out.append({"ticker": r["symbol"], "name": r.get("name"), "exchange": r.get("exchange") or None,
                    "asset": (r.get("asset") or "").lower() or None})
    return out


# ---------------------------------------------------------------- Naver (한국)
def parse_naver_chart(rows: list[dict[str, Any]] | None) -> list[Bar]:
    out = []
    for r in rows or []:
        try:
            d = datetime.strptime(str(r.get("localDate")), "%Y%m%d").date()
        except ValueError:
            continue
        b = _bar(d, r.get("openPrice"), r.get("highPrice"), r.get("lowPrice"), r.get("closePrice"),
                 r.get("accumulatedTradingVolume"))
        if b:
            out.append(b)
    return sort_bars(out)


def parse_naver_sise(text: str) -> list[Bar]:
    """api.finance.naver.com siseJson (대체 경로) — wsj.ecosystems.prices.parse_naver 를 쓰고 형식만 맞춘다."""
    from wsj.ecosystems.prices import parse_naver

    out = []
    for r in parse_naver(text or "", "x"):
        out.append({"date": r["trade_date"], "open": r["open"], "high": r["high"], "low": r["low"],
                    "close": r["close"], "volume": r["volume"]})
    return sort_bars(out)


KR_EXCHANGE = {"KS": "KOSPI", "KQ": "KOSDAQ", "KN": "KONEX"}


def parse_naver_basic(d: dict[str, Any] | None) -> dict[str, Any] | None:
    if not d or not d.get("itemCode"):
        return None
    ex = d.get("stockExchangeType") or {}
    traded = d.get("localTradedAt")
    return {
        "code": d.get("itemCode"),
        "name": d.get("stockName"),
        "exchange": KR_EXCHANGE.get(ex.get("code"), d.get("stockExchangeName") or ex.get("name")),
        "type": d.get("stockEndType"),  # stock | etf | ...
        "close": num(d.get("closePrice")),
        "change": num(d.get("compareToPreviousClosePrice")),
        "pct_change": num(d.get("fluctuationsRatio")),
        "traded_at": traded,
        "trade_date": str(traded)[:10] if traded else None,
        "market_status": d.get("marketStatus"),
    }


def parse_krw_amount(s: Any) -> float | None:
    """'3조 3,397억' · '15조 312억' · '387억' · '1,234만' · '12,345' → 원."""
    if s is None:
        return None
    t = str(s).replace(",", "").replace(" ", "").replace("원", "")
    if not t or t in _MISSING:
        return None
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)조)?(?:(\d+(?:\.\d+)?)억)?(?:(\d+(?:\.\d+)?)만)?(\d+(?:\.\d+)?)?", t)
    if not m or not any(m.groups()):
        return None
    jo, eok, man, rest = (float(g) if g else 0.0 for g in m.groups())
    return jo * 1e12 + eok * 1e8 + man * 1e4 + rest


def parse_naver_integration(d: dict[str, Any] | None) -> dict[str, Any] | None:
    if not d:
        return None
    info = {i.get("code"): i.get("value") for i in d.get("totalInfos") or [] if i.get("code")}
    return {
        "code": d.get("itemCode"),
        "name": d.get("stockName"),
        "type": d.get("stockEndType"),
        "market_cap_krw": parse_krw_amount(info.get("marketValue")),
        "market_cap_text": info.get("marketValue"),
        "per": num(info.get("per")),
        "pbr": num(info.get("pbr")),
        "eps": num(info.get("eps")),
        "high_52w": num(info.get("highPriceOf52Weeks")),
        "low_52w": num(info.get("lowPriceOf52Weeks")),
    }


def parse_naver_autocomplete(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for r in (payload or {}).get("items") or []:
        if r.get("category") not in (None, "stock") or not r.get("code"):
            continue
        nation = r.get("nationCode")
        out.append({"market": "kr" if nation == "KOR" else ("us" if nation == "USA" else (nation or "").lower() or None),
                    "ticker": r["code"], "name": r.get("name"), "exchange": r.get("typeCode"),
                    "reuters_code": r.get("reutersCode")})
    return out


# ---------------------------------------------------------------- SEC
def parse_sec_tickers_exchange(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """company_tickers_exchange.json = {fields:[cik,name,ticker,exchange], data:[[...], ...]}."""
    fields = (payload or {}).get("fields") or []
    out = []
    for row in (payload or {}).get("data") or []:
        r = dict(zip(fields, row, strict=False))
        if r.get("ticker"):
            out.append({"cik": int(r["cik"]) if r.get("cik") is not None else None, "name": r.get("name"),
                        "ticker": str(r["ticker"]).upper(), "exchange": r.get("exchange")})
    return out


# ---------------------------------------------------------------- 미 재무부 수익률 곡선
_TENOR = re.compile(r"([\d.]+)\s*(Mo|Month|Months|Yr|Year|Years)", re.I)


def tenor_key(label: str) -> str | None:
    m = _TENOR.search(label or "")
    if not m:
        return None
    n = m.group(1).rstrip("0").rstrip(".") if "." in m.group(1) else m.group(1)
    return f"{n}{'m' if m.group(2).lower().startswith('mo') else 'y'}"


def parse_treasury_csv(text: str) -> list[dict[str, Any]]:
    """→ [{date:'YYYY-MM-DD', curve:{'1m':4.02, '3m':4.19, ..., '30y':5.26}}] (최신 순 정렬 아님 — 날짜 오름차순)."""
    reader = csv.reader(io.StringIO(text or ""))
    header = next(reader, None)
    if not header:
        return []
    keys = [tenor_key(h) for h in header]
    out = []
    for row in reader:
        if not row:
            continue
        try:
            d = datetime.strptime(row[0].strip(), "%m/%d/%Y").date()
        except ValueError:
            continue
        curve = {k: num(v) for k, v in zip(keys[1:], row[1:], strict=False) if k and num(v) is not None}
        out.append({"date": d.isoformat(), "curve": curve})
    out.sort(key=lambda r: r["date"])
    return out


# ---------------------------------------------------------------- 환율
def parse_frankfurter(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload or not payload.get("rates"):
        return None
    return {"base": payload.get("base"), "date": payload.get("date"),
            "rates": {k: float(v) for k, v in payload["rates"].items()}}


def parse_er_api(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload or payload.get("result") != "success":
        return None
    day = None
    try:
        day = datetime.strptime(payload.get("time_last_update_utc", "")[:16], "%a, %d %b %Y").date().isoformat()
    except ValueError:
        pass
    return {"base": payload.get("base_code"), "date": day, "rates": {k: float(v) for k, v in (payload.get("rates") or {}).items()}}
