"""Nasdaq historical API (비공식) 로 일봉을 받아 raw.px_daily 에 캐시하고, 브리프용 가격 지표를 만든다.

검증 (2026-10-26): https://api.nasdaq.com/api/quote/RAPP/historical?assetclass=stocks&fromdate=...&todate=...&limit=9999
브라우저 User-Agent 가 필요하고, 응답은 data.tradesTable.rows = [{date:'10/24/2026', close:'$12.34', volume:'1,234,567', open, high, low}].
NYSE 종목도 같은 엔드포인트로 나온다. 알 수 없는 티커는 data=null. 수정주가 아님 — 분할이 있으면 수익률이 깨진다 (payload 에 플래그 없음).
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any

from wsj.db.base import Store
from wsj.http import HttpClient
from wsj.util import parse_date, to_num

log = logging.getLogger("wsj.marketdata")

URL = "https://api.nasdaq.com/api/quote/{ticker}/historical"
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def _clean(v: str | None) -> float | None:
    if v is None:
        return None
    s = str(v).replace("$", "").replace(",", "").strip()
    if s in ("", "N/A", "--"):
        return None
    return to_num(s)


def fetch_daily(http: HttpClient, ticker: str, start: date, end: date) -> list[dict[str, Any]]:
    params = {
        "assetclass": "stocks",
        "fromdate": start.isoformat(),
        "todate": end.isoformat(),
        "limit": 9999,
    }
    data = http.get_json(URL.format(ticker=ticker.upper()), params=params, headers=BROWSER_HEADERS)
    table = (data or {}).get("data") or {}
    rows = (table.get("tradesTable") or {}).get("rows") or []
    out: list[dict[str, Any]] = []
    for r in rows:
        d = parse_date(r.get("date"))
        close = _clean(r.get("close"))
        if d is None or close is None:
            continue
        vol = _clean(r.get("volume"))
        out.append(
            {
                "ticker": ticker.upper(),
                "trade_date": d.isoformat(),
                "open": _clean(r.get("open")),
                "high": _clean(r.get("high")),
                "low": _clean(r.get("low")),
                "close": close,
                "volume": int(vol) if vol is not None else None,
                "source": "nasdaq",
            }
        )
    out.sort(key=lambda x: x["trade_date"])
    return out


def get_daily(
    store: Store, http: HttpClient, ticker: str, as_of: date, days: int = 400, max_stale_days: int = 3
) -> list[dict[str, Any]]:
    """캐시 우선. 마지막 캐시일이 as_of 보다 max_stale_days 넘게 오래되면 그 뒤만 받아 채운다."""
    start = as_of - timedelta(days=days)
    cached = store.select(
        "raw.px_daily",
        None,
        {"ticker": ticker.upper(), "trade_date": ("gte", start.isoformat())},
        order="trade_date",
    )
    last = parse_date(cached[-1]["trade_date"]) if cached else None
    need_from = start if last is None else last + timedelta(days=1)
    # 주말·휴일 고려: 마지막 캐시일이 영업일 기준 충분히 최신이면 재요청하지 않는다
    if last is None or (as_of - last).days > max_stale_days:
        try:
            fresh = fetch_daily(http, ticker, need_from, as_of)
        except Exception as exc:  # noqa: BLE001 - 시세 실패는 브리프를 막지 않는다
            log.warning("price fetch failed %s: %s", ticker, exc)
            fresh = []
        if fresh:
            store.upsert("raw.px_daily", fresh, ["ticker", "trade_date"])
            have = {r["trade_date"] for r in cached}
            cached = cached + [r for r in fresh if r["trade_date"] not in have]
            cached.sort(key=lambda x: x["trade_date"])
    for r in cached:
        for k in ("open", "high", "low", "close"):
            if r.get(k) is not None:
                r[k] = float(r[k])
    return cached


def _ret(closes: list[float], n: int) -> float | None:
    if len(closes) <= n or closes[-1 - n] in (0, None):
        return None
    return closes[-1] / closes[-1 - n] - 1


def price_metrics(rows: list[dict[str, Any]], shares_outstanding: float | None = None) -> dict[str, Any]:
    if not rows:
        return {"available": False}
    closes = [float(r["close"]) for r in rows]
    vols = [int(r["volume"]) if r.get("volume") is not None else 0 for r in rows]
    dates = [r["trade_date"] for r in rows]
    last = closes[-1]
    hi_idx = max(range(len(closes)), key=lambda i: closes[i])
    lo_idx = min(range(len(closes)), key=lambda i: closes[i])
    # 최대 낙폭 (1년)
    peak = closes[0]
    mdd = 0.0
    for c in closes:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    adv20 = sum(c * v for c, v in zip(closes[-20:], vols[-20:], strict=False)) / max(1, min(20, len(closes)))
    vol20 = _realized_vol(closes[-21:])
    out: dict[str, Any] = {
        "available": True,
        "as_of": dates[-1],
        "last_close": last,
        "first_date": dates[0],
        "trading_days": len(closes),
        "ret_1m": _ret(closes, 21),
        "ret_3m": _ret(closes, 63),
        "ret_6m": _ret(closes, 126),
        "ret_12m": _ret(closes, 252)
        if len(closes) > 252
        else (closes[-1] / closes[0] - 1 if len(closes) > 200 else None),
        "high_52w": closes[hi_idx],
        "high_52w_date": dates[hi_idx],
        "pct_from_52w_high": last / closes[hi_idx] - 1,
        "low_52w": closes[lo_idx],
        "low_52w_date": dates[lo_idx],
        "pct_from_52w_low": last / closes[lo_idx] - 1 if closes[lo_idx] else None,
        "max_drawdown_1y": mdd,
        "adv20_usd": adv20,
        "realized_vol_20d_annualized": vol20,
        "market_cap": last * shares_outstanding if shares_outstanding else None,
    }
    # 월별 종가 (추세 서술용, 13개 점)
    monthly: list[tuple[str, float]] = []
    seen_month = None
    for d, c in zip(dates, closes, strict=False):
        m = d[:7]
        if m != seen_month:
            monthly.append((d, c))
            seen_month = m
        else:
            monthly[-1] = (d, c)
    out["monthly_closes"] = [{"date": d, "close": c} for d, c in monthly[-13:]]
    return out


def _realized_vol(closes: list[float]) -> float | None:
    if len(closes) < 10:
        return None
    rets = [math.log(b / a) for a, b in zip(closes[:-1], closes[1:], strict=False) if a > 0 and b > 0]
    if len(rets) < 5:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def event_window_returns(
    rows: list[dict[str, Any]], event_date: str, before: int = 5, after: int = 20
) -> dict[str, Any] | None:
    """신호일 전후 수익률: 시장이 이미 반응했는지 본다. event_date 이후 첫 거래일을 T 로 둔다."""
    if not rows:
        return None
    dates = [r["trade_date"] for r in rows]
    closes = [float(r["close"]) for r in rows]
    t = next((i for i, d in enumerate(dates) if d >= event_date), None)
    if t is None or t == 0:
        return None
    out = {"event_date": event_date, "t_date": dates[t], "close_t": closes[t]}
    if t - before >= 0:
        out[f"ret_pre_{before}d"] = closes[t] / closes[t - before] - 1
    for n in (5, after):
        if t + n < len(closes):
            out[f"ret_post_{n}d"] = closes[t + n] / closes[t] - 1
    out["ret_since_event"] = closes[-1] / closes[t] - 1
    return out
