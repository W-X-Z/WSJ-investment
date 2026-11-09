"""N19 밸류에이션(현재): 지금 주가 기준 배수, 자기 과거 배수, 역DCF 가 가정하는 성장률.

  현재     시총(tools.quote) ÷ TTM 손익(deep.fin): P/S · P/E · EV/EBIT · EV/Sales · FCF 수익률
  과거     회계연도 말 종가 × 그때 발행주식수 → P/S · P/E (주식 수 태그가 Class A 만일 수 있다 → notes)
  역DCF    기준 FCF(TTM, 양수일 때) 또는 세후 영업이익(FCF 가 음수면 대용)으로, 지금 EV 가 요구하는 10년 CAGR
피어 대비는 deep.peers_table. 해석(왜 싸거나 비싼지)은 3단계 에이전트가 한다.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wsj.tools import calc as C
from wsj.tools.context import ToolContext, ToolError, ensure_context
from wsj.tools.prices import get_bars, parse_symbol

DISCOUNT = 0.10
TERMINAL = 0.025
TAX = 0.21


def _div(a: float | None, b: float | None) -> float | None:
    return round(a / b, 2) if a is not None and b is not None and b > 0 else None


def current_multiples(mcap: float | None, ttm: dict[str, Any] | None) -> dict[str, Any]:
    t = ttm or {}
    nd = t.get("net_debt")
    ev = mcap + nd if mcap is not None and nd is not None else None
    return {"market_cap": mcap, "net_debt": nd, "enterprise_value": ev,
            "price_sales": _div(mcap, t.get("revenue")), "pe": _div(mcap, t.get("net_income")),
            "ev_sales": _div(ev, t.get("revenue")), "ev_ebit": _div(ev, t.get("op_income")),
            "p_fcf": _div(mcap, t.get("fcf")),
            "fcf_yield_pct": round(100 * t["fcf"] / mcap, 2) if mcap and t.get("fcf") is not None else None}


def history_multiples(bars: list[dict[str, Any]], annual: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in annual:
        b = C.close_on_or_before(bars, r["period_end"])
        sh = r.get("shares_out") or r.get("diluted_shares")
        if not b or not sh:
            continue
        mcap = b["close"] * sh
        out.append({"period_end": r["period_end"], "close": b["close"], "close_date": b["date"], "shares": sh,
                    "market_cap": mcap, "price_sales": _div(mcap, r.get("revenue")), "pe": _div(mcap, r.get("net_income")),
                    "ev_ebit": _div(mcap + r["net_debt"], r.get("op_income")) if r.get("net_debt") is not None else None})
    return out


def implied(mcap: float | None, ttm: dict[str, Any] | None, discount: float = DISCOUNT,
            terminal: float = TERMINAL) -> dict[str, Any] | None:
    from wsj.tools.dcf import reverse_dcf

    t = ttm or {}
    if not mcap:
        return None
    base, basis = t.get("fcf"), "ttm_fcf"
    if base is None or base <= 0:
        op = t.get("op_income")
        if op is None or op <= 0:
            return {"note": "FCF·영업이익이 모두 음수 — 역DCF 를 풀 수 없다 (매출 배수로 본다)"}
        base, basis = op * (1 - TAX), "nopat_proxy"
    try:
        res = reverse_dcf(base, discount, terminal, 10, market_cap=mcap, net_debt=t.get("net_debt") or 0.0)
    except ToolError as exc:
        return {"note": str(exc)}
    return {"basis": basis, "base": base, "discount_rate": discount, "terminal_growth": terminal,
            "implied_cagr_pct": res.get("implied_fcf_cagr_pct"), "ev_over_base": res.get("ev_over_base_fcf"),
            "terminal_share_of_ev": res.get("terminal_share_of_ev"), "note": res.get("note")}


def valuation(symbol: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    from wsj.deep.fin import fin
    from wsj.tools.quote import quote

    with ensure_context(ctx) as c:
        sym = parse_symbol(symbol)
        q = quote(sym.code, ctx=c)
        mc = (q.get("market_cap") or {})
        mcap = mc.get("local") or mc.get("value") or mc.get("market_cap")
        f = fin(sym.code, years=5, ctx=c)
        out: dict[str, Any] = {"symbol": sym.code, "market": sym.market, "price": q.get("price"),
                               "market_cap_block": mc, "notes": []}
        if "error" in f:
            out["notes"].append(f["error"])
            return out
        ttm = f.get("ttm")
        out["current"] = current_multiples(mcap, ttm)
        out["ttm_basis"] = {k: (ttm or {}).get(k) for k in ("period_end", "basis", "revenue", "op_income", "net_income",
                                                           "fcf", "net_debt")}
        if f.get("annual"):
            start = date.fromisoformat(f["annual"][0]["period_end"]) - timedelta(days=10)
            try:
                bars, _ = get_bars(c, sym, start, c.today)
                out["history"] = history_multiples(bars, f["annual"])
            except ToolError as exc:
                out["notes"].append(f"history: {exc}")
        out["reverse_dcf"] = implied(mcap, ttm)
        if sym.market == "us":
            out["notes"].append("과거 시총 = 회계연도 말 종가 × 표지 발행주식수(dei) — 복수 주식 종류(Up-C 등)면 과소")
        return out
