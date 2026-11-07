"""동종 비교표: 시총, EV, 매출, 영업이익, 순이익, P/E, EV/Sales, EV/EBIT.

값의 출처 (없으면 null — 추정하지 않는다):
  시총       미국 Nasdaq summary / 한국 Naver integration (quote 도구와 같은 경로)
  재무(TTM)  raw.company_fundamentals (raw.company_facts.ticker → company_id, 최신 TTM 없으면 FY)
             → DB 에 없으면 라이브: 미국 SEC companyfacts 최근 4분기 합, 한국 Naver 분기 재무 최근 4분기 합
  순차입금   미국 SEC companyfacts 최근 분기말 (장단기 차입금 − 현금·단기투자). 한국은 출처가 없어 null → EV 도 null
EBIT 는 영업이익(OperatingIncomeLoss)으로 대신한다. 이익이 0 이하이면 배수는 null.
재무 통화가 시총 통화와 다르면 fx 로 환산한다 (환율을 못 얻으면 배수 null).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from wsj.tools.context import ToolContext, ToolError, ensure_context
from wsj.tools.fx import get_rate
from wsj.tools.lookup import sec_cik
from wsj.tools.prices import Symbol, parse_symbol
from wsj.tools.quote import kr_profile, us_profile


def latest_fundamental(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """v_company_fundamentals 와 같은 규칙: TTM 우선, 같은 종류 안에서는 최신 period_end."""
    cands = [r for r in rows if r.get("period") in ("ttm", "fy")]
    if not cands:
        return None
    return max(cands, key=lambda r: (r["period"] == "ttm", str(r["period_end"])))


def _f(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def db_fundamentals(ctx: ToolContext, sym: Symbol) -> dict[str, Any] | None:
    facts = ctx.db_select("raw.company_facts", ["company_id", "ticker"], {"ticker": sym.px_keys})
    if not facts:
        return None
    cid = facts[0]["company_id"]
    rows = ctx.db_select("raw.company_fundamentals",
                         ["company_id", "period", "period_end", "currency", "revenue", "operating_income", "net_income",
                          "source", "source_url"], {"company_id": cid})
    r = latest_fundamental(rows or [])
    if not r:
        return None
    return {"company_id": cid, "period": r["period"], "period_end": str(r["period_end"])[:10], "currency": r["currency"],
            "revenue": _f(r.get("revenue")), "operating_income": _f(r.get("operating_income")),
            "net_income": _f(r.get("net_income")), "source": f"db:raw.company_fundamentals ({r.get('source')})"}


def sec_derived(fin: dict[str, Any]) -> dict[str, Any]:
    """xbrl.build_financials 결과 → TTM 매출·영업이익·순이익과 순차입금 (4분기 모두 있어야 TTM)."""
    q = fin.get("quarters") or []
    last4 = q[-4:]

    def ttm(k: str) -> float | None:
        vs = [r.get(k) for r in last4]
        return float(sum(vs)) if len(vs) == 4 and all(v is not None for v in vs) else None

    d = fin.get("derived") or {}
    debt, liq = d.get("debt_total"), d.get("liquidity_cash_and_st_investments")
    return {"period": "ttm", "period_end": q[-1]["period_end"] if q else None, "currency": "USD",
            "revenue": ttm("revenue"), "operating_income": ttm("op_income"), "net_income": ttm("net_income"),
            "debt": debt, "cash": liq,
            "net_debt": (debt - liq) if debt is not None and liq is not None else None}


def sec_fundamentals(ctx: ToolContext, sym: Symbol) -> dict[str, Any] | None:
    key = f"sec_fin:{sym.code}"
    if key in ctx.memo:
        return ctx.memo[key]
    out = None
    cik = sec_cik(ctx, sym.code)
    if cik:
        try:
            cf = ctx.fetch.sec_companyfacts(cik)
            if cf:
                from wsj.briefs.xbrl import build_financials

                out = sec_derived(build_financials(cf, n_quarters=8)) | {"cik": cik, "source": "sec:companyfacts"}
        except Exception as exc:  # noqa: BLE001
            out = {"error": f"sec companyfacts: {str(exc)[:80]}"}
    else:
        out = {"error": "CIK not found (SEC ticker table unavailable or unknown ticker)"}
    ctx.memo[key] = out
    return out


def naver_fundamentals(ctx: ToolContext, sym: Symbol) -> dict[str, Any] | None:
    from wsj.ecosystems.fundamentals import parse_naver_quarters

    try:
        qs = parse_naver_quarters(ctx.fetch.naver_quarters(sym.code))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"naver quarters: {str(exc)[:80]}"}
    last4 = qs[-4:]
    if len(last4) < 4 or (date.fromisoformat(last4[-1]["period_end"]) - date.fromisoformat(last4[0]["period_end"])).days > 300:
        return {"error": "naver quarters: fewer than 4 consecutive reported quarters"}

    def tot(k: str) -> float | None:
        vs = [r.get(k) for r in last4]
        return float(sum(vs)) if all(v is not None for v in vs) else None

    return {"period": "ttm", "period_end": last4[-1]["period_end"], "currency": "KRW", "revenue": tot("revenue"),
            "operating_income": tot("operating_income"), "net_income": tot("net_income"),
            "source": "naver:finance/quarter (last 4 reported quarters, consensus excluded)"}


def ratios(mcap: float | None, net_debt: float | None, revenue: float | None, op_income: float | None,
           net_income: float | None) -> dict[str, Any]:
    """배수는 분모(매출·이익)가 양수일 때만. EV 는 시총과 순차입금이 둘 다 있을 때만."""
    ev = mcap + net_debt if mcap is not None and net_debt is not None else None

    def div(a: float | None, b: float | None) -> float | None:
        return round(a / b, 2) if a is not None and b is not None and b > 0 else None

    return {"enterprise_value": ev, "pe": div(mcap, net_income), "ev_sales": div(ev, revenue),
            "ev_ebit": div(ev, op_income), "price_sales": div(mcap, revenue)}


def peer_row(ctx: ToolContext, sym: Symbol, use_sec: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": sym.code, "market": sym.market, "currency": sym.currency, "sources": {}, "notes": []}
    if sym.market == "us":
        prof = us_profile(ctx, sym)
        info, summ = prof["info"] or {}, prof["summary"] or {}
        row["name"], row["price"], row["market_cap"] = info.get("name"), info.get("last_sale"), summ.get("market_cap")
        row["sources"]["market_cap"] = "nasdaq:summary" if row["market_cap"] else None
    else:
        prof = kr_profile(ctx, sym)
        basic, integ = prof["basic"] or {}, prof["integration"] or {}
        row["name"], row["price"], row["market_cap"] = basic.get("name"), basic.get("close"), integ.get("market_cap_krw")
        row["sources"]["market_cap"] = "naver:integration" if row["market_cap"] else None

    fund = db_fundamentals(ctx, sym)
    sec = sec_fundamentals(ctx, sym) if sym.market == "us" and use_sec else None
    if fund is None:
        live = sec if sym.market == "us" else naver_fundamentals(ctx, sym)
        if live and "error" not in live:
            fund = live
        elif live:
            row["notes"].append(live["error"])
    fx_mult = 1.0
    if fund:
        row["period"], row["period_end"], row["fundamentals_currency"] = fund.get("period"), fund.get("period_end"), fund.get("currency")
        row["sources"]["fundamentals"] = fund.get("source")
        if fund.get("currency") and fund["currency"] != sym.currency:
            try:
                fx_mult = get_rate(ctx, fund["currency"], sym.currency)["rate"]
                row["notes"].append(f"fundamentals converted {fund['currency']}→{sym.currency} at {fx_mult:.6g}")
            except ToolError as exc:
                fx_mult = None  # type: ignore[assignment]
                row["notes"].append(str(exc))
    conv = (lambda v: v * fx_mult if v is not None and fx_mult is not None else None)  # noqa: E731
    row["revenue"] = conv(fund.get("revenue")) if fund else None
    row["operating_income"] = conv(fund.get("operating_income")) if fund else None
    row["net_income"] = conv(fund.get("net_income")) if fund else None
    row["net_debt"] = None
    if sec and "error" not in sec:
        row["net_debt"] = sec.get("net_debt")
        if sec.get("net_debt") is not None:
            row["sources"]["net_debt"] = f"sec:companyfacts debt−cash ({sec.get('period_end')})"
        elif sec.get("debt") is None:
            row["notes"].append("SEC companyfacts has no debt tags (LongTermDebt*/DebtCurrent…) → net debt and EV null; "
                                "pass net debt to reverse-dcf yourself if the filing shows zero debt")
        else:
            row["notes"].append("SEC companyfacts has debt but no cash tag → net debt and EV null")
    elif sym.market == "kr":
        row["notes"].append("net debt not available for KR listings → EV null")
    elif sec and "error" in sec and sec["error"] not in row["notes"]:
        row["notes"].append(sec["error"])
    for k in ("revenue", "operating_income", "net_income"):
        if fund and row[k] is None:
            row["notes"].append(f"{k}: source has no 4 consecutive quarters (tag missing or gaps) → null")
    row |= ratios(row["market_cap"], row["net_debt"], row["revenue"], row["operating_income"], row["net_income"])
    row["sources"] = {k: v for k, v in row["sources"].items() if v}
    if not row["notes"]:
        row.pop("notes")
    return row


def peers(tickers: list[str], use_sec: bool = True, ctx: ToolContext | None = None) -> dict[str, Any]:
    if not tickers:
        raise ToolError("종목을 하나 이상 주세요")
    with ensure_context(ctx) as c:
        rows = []
        for t in tickers:
            try:
                rows.append(peer_row(c, parse_symbol(t), use_sec))
            except ToolError as exc:
                rows.append({"symbol": t, "error": str(exc)})
        return {"as_of": c.today.isoformat(), "metric_notes": {"ebit": "operating income", "ev": "market cap + net debt",
                                                               "pe": "market cap ÷ TTM net income (null if ≤ 0)"},
                "results": rows}
