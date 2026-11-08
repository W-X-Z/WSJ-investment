"""시세 요약: 마지막 종가, 시가총액(USD·KRW), 1m/3m/6m/1y/YTD 등락, 52주 고저.

  미국  종가·이력 = raw.px_daily 또는 Nasdaq historical / 시총 = Nasdaq summary MarketCap
        (다중 클래스 회사는 상장 클래스만 셀 수 있다 → DB 에 발행주식수가 있으면 '주식수 × 종가'도 같이 보여 준다)
  한국  종가·이력 = raw.px_daily 또는 Naver chart / 시총 = Naver integration marketValue ('3조 3,397억')
환산 환율은 fx 도구와 같은 경로(ref.fx_rates → Frankfurter → er-api).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wsj.tools import calc as C
from wsj.tools import parse as P
from wsj.tools.context import ToolContext, ToolError, ensure_context, parse_day
from wsj.tools.fx import get_rate
from wsj.tools.prices import Symbol, get_bars, parse_symbol

HISTORY_DAYS = 400


def _try(fn, *a) -> Any:
    try:
        return fn(*a)
    except Exception:  # noqa: BLE001 - 시세 보조 정보 실패는 null 로
        return None


def us_profile(ctx: ToolContext, sym: Symbol) -> dict[str, Any]:
    """Nasdaq info + summary (자산군은 이력 조회 때 맞춘 것을 쓴다)."""
    key = f"us_profile:{sym.code}"
    if key in ctx.memo:
        return ctx.memo[key]
    acs = [ctx.memo[f"assetclass:{sym.code}"]] if ctx.memo.get(f"assetclass:{sym.code}") else ["stocks", "etf"]
    info = summ = None
    for ac in acs:
        info = P.parse_nasdaq_info(_try(ctx.fetch.nasdaq_info, sym.code, ac))
        if info:
            summ = P.parse_nasdaq_summary(_try(ctx.fetch.nasdaq_summary, sym.code, ac))
            ctx.memo[f"assetclass:{sym.code}"] = ac
            break
    out = {"info": info, "summary": summ}
    ctx.memo[key] = out
    return out


def kr_profile(ctx: ToolContext, sym: Symbol) -> dict[str, Any]:
    key = f"kr_profile:{sym.code}"
    if key in ctx.memo:
        return ctx.memo[key]
    out = {"basic": P.parse_naver_basic(_try(ctx.fetch.naver_basic, sym.code)),
           "integration": P.parse_naver_integration(_try(ctx.fetch.naver_integration, sym.code))}
    ctx.memo[key] = out
    return out


def db_shares(ctx: ToolContext, sym: Symbol) -> dict[str, Any] | None:
    rows = ctx.db_select("raw.company_facts", ["company_id", "ticker", "currency", "shares_outstanding", "shares_as_of", "source"],
                         {"ticker": sym.px_keys})
    return rows[0] if rows else None


def market_cap_block(ctx: ToolContext, sym: Symbol, close: float | None, close_date: str | None,
                     latest: bool) -> dict[str, Any]:
    """시가총액 USD·KRW (+출처). 과거 기준일이면 '현재 시총 ÷ 현재가 = 주식수' 로 그 날 종가에 곱한다."""
    out: dict[str, Any] = {"local": None, "usd": None, "krw": None, "currency": sym.currency, "source": None}
    shares_live = None
    if sym.market == "us":
        prof = us_profile(ctx, sym)
        summ, info = prof["summary"] or {}, prof["info"] or {}
        mcap_now = summ.get("market_cap")
        ref_px = info.get("last_sale")
        if mcap_now:
            out["source"] = "nasdaq:summary.MarketCap (listed class only for multi-class issuers)"
            shares_live = mcap_now / ref_px if ref_px else None
            out["local"] = mcap_now if latest or not (shares_live and close) else shares_live * close
    else:
        prof = kr_profile(ctx, sym)
        integ, basic = prof["integration"] or {}, prof["basic"] or {}
        mcap_now = integ.get("market_cap_krw")
        ref_px = basic.get("close")
        if mcap_now:
            out["source"] = "naver:integration.marketValue"
            shares_live = mcap_now / ref_px if ref_px else None
            out["local"] = mcap_now if latest or not (shares_live and close) else shares_live * close
    if out["local"] is not None and not latest:
        out["source"] += f" × close on {close_date} ÷ live price"
    if shares_live:
        out["shares_implied"] = round(shares_live)
    facts = db_shares(ctx, sym)
    if facts and close:
        out["db_shares_x_close"] = {"shares": float(facts["shares_outstanding"]), "shares_as_of": facts.get("shares_as_of"),
                                    "market_cap_local": float(facts["shares_outstanding"]) * close, "source": "db:raw.company_facts"}
        if out["local"] is None:
            out["local"] = out["db_shares_x_close"]["market_cap_local"]
            out["source"] = "db:raw.company_facts shares × close"
    if out["local"] is not None:
        try:
            fx = get_rate(ctx, "USD", "KRW")
            out["fx"] = {"usdkrw": fx["rate"], "as_of": fx["as_of"], "source": fx["source"]}
            if sym.market == "us":
                out["usd"], out["krw"] = out["local"], out["local"] * fx["rate"]
            else:
                out["krw"], out["usd"] = out["local"], out["local"] / fx["rate"]
        except ToolError as exc:
            out["fx_error"] = str(exc)
            out["usd" if sym.market == "us" else "krw"] = out["local"]
    return out


def quote(symbol: str, as_of: str | date | None = None, ctx: ToolContext | None = None) -> dict[str, Any]:
    with ensure_context(ctx) as c:
        sym = parse_symbol(symbol)
        end = parse_day(as_of, c.today)
        bars, src = get_bars(c, sym, end - timedelta(days=HISTORY_DAYS), end)
        if not bars:
            raise ToolError(f"{sym.code}: {end} 이전 가격이 없습니다")
        last = bars[-1]
        latest = as_of is None or end >= c.today
        out: dict[str, Any] = {"symbol": sym.code, "market": sym.market, "currency": sym.currency}
        if sym.market == "us":
            prof = us_profile(c, sym)
            info, summ = prof["info"] or {}, prof["summary"] or {}
            out.update(name=info.get("name"), exchange=info.get("exchange") or summ.get("exchange"),
                       sector=summ.get("sector"), industry=summ.get("industry"))
            live = {"last_sale": info.get("last_sale"), "pct_change": info.get("pct_change"),
                    "trade_date": info.get("trade_date"), "source": "nasdaq:info"} if info else None
        else:
            prof = kr_profile(c, sym)
            basic = prof["basic"] or {}
            out.update(name=basic.get("name"), exchange=basic.get("exchange"), type=basic.get("type"))
            live = {"last_sale": basic.get("close"), "pct_change": basic.get("pct_change"),
                    "trade_date": basic.get("trade_date"), "source": "naver:basic"} if basic else None
        prev = bars[-2] if len(bars) >= 2 else None
        out["price"] = {"close": last["close"], "date": last["date"],
                        "prev_close": prev["close"] if prev else None,
                        "day_change_pct": C.pct(last["close"] / prev["close"] - 1) if prev else None,
                        "volume": last.get("volume"), "source": src, "adjusted": False}
        if latest and live:
            out["live"] = live
            if live.get("trade_date") and live["trade_date"] > last["date"]:
                out.setdefault("notes", []).append(
                    f"live quote is newer ({live['trade_date']}) than the last daily bar ({last['date']})")
        out["market_cap"] = market_cap_block(c, sym, last["close"], last["date"], latest)
        out["changes"] = C.trailing_changes(bars)
        out["history_from"] = bars[0]["date"]  # 이력이 이보다 짧으면(신규 상장) 1y·YTD 는 null
        out["range_52w"] = C.high_low(bars, 365)
        out["as_of"] = last["date"]
        return out
