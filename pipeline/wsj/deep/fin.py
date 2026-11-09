"""N15 펀더멘탈 계산: 최근 5개 회계연도 + 최근 4분기(TTM) 표준 지표와 크게 튄 값.

미국: SEC companyfacts(XBRL) — briefs.xbrl 의 개념·태그 별칭을 그대로 쓴다.
  연간  매출·매출총이익·영업이익·순이익·영업현금흐름·capex·FCF·SBC·현금(+단기투자)·차입(장+단)·자본·선수금·희석주식수·EPS
  파생  성장률, 매출총이익률·영업이익률·FCF 마진, ROIC(영업이익×(1−21%) ÷ (자본+차입) — 순현금 회사가 튀지 않게 현금을 빼지 않는다), 순차입, 희석주식 증가율
  이상치 성장률·이익률 변화가 크게 튄 값(성장률 |Δ| ≥ 30%p, 이익률 |Δ| ≥ 5%p, 희석 ≥ 5%) — 원인은 3단계 에이전트가 카드·8-K 에서 찾는다.
한국: 공급망 지도 재무(매출·영업이익·순이익·자산) 또는 Naver 분기(TTM) — 깊이는 미국보다 얕다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from wsj.briefs.xbrl import CONCEPTS, _facts, annual_series, instant_series, quarterly_series
from wsj.tools.context import ToolContext, ensure_context
from wsj.tools.prices import parse_symbol

TAX = 0.21
FLOWS = ("revenue", "gross_profit", "op_income", "net_income", "ocf", "capex", "sbc", "rnd", "sga", "diluted_shares",
         "eps_diluted")
STOCKS = ("cash", "st_investments", "debt_lt", "debt_st", "equity", "total_assets", "deferred_revenue", "shares_out")


def _r(x: float | None, nd: int = 1) -> float | None:
    return None if x is None else round(x, nd)


def _ratio(a: float | None, b: float | None) -> float | None:
    return a / b if a is not None and b not in (None, 0) else None


def _near(series: dict[date, float], end: date, tol: int = 20) -> float | None:
    best = None
    for d, v in series.items():
        g = abs((d - end).days)
        if g <= tol and (best is None or g < best[0]):
            best = (g, v)
    return best[1] if best else None


def series(cf: dict[str, Any]) -> dict[str, dict[str, dict[date, float]]]:
    out: dict[str, dict[str, dict[date, float]]] = {"annual": {}, "quarter": {}, "instant": {}}
    for k, (tags, unit, kind) in CONCEPTS.items():
        fs = _facts(cf, tags, unit)
        if kind == "duration":
            out["annual"][k] = annual_series(fs)
            out["quarter"][k] = quarterly_series(fs, additive=k not in ("eps_diluted", "diluted_shares"))
        else:
            out["instant"][k] = instant_series(fs)
    return out


def _row(get_flow, get_stock) -> dict[str, Any]:
    r = {k: get_flow(k) for k in FLOWS} | {k: get_stock(k) for k in STOCKS}
    if r["capex"] is not None:
        r["capex"] = abs(r["capex"])
    r["fcf"] = r["ocf"] - r["capex"] if r["ocf"] is not None and r["capex"] is not None else None
    cash = (r["cash"] or 0) + (r["st_investments"] or 0) if r["cash"] is not None else None
    debt = (r["debt_lt"] or 0) + (r["debt_st"] or 0) if (r["debt_lt"] is not None or r["debt_st"] is not None) else None
    r["cash_total"], r["debt_total"] = cash, debt
    r["net_debt"] = debt - cash if debt is not None and cash is not None else None
    r["gross_margin_pct"] = _r(_ratio(r["gross_profit"], r["revenue"]) and 100 * _ratio(r["gross_profit"], r["revenue"]))
    r["op_margin_pct"] = _r(_ratio(r["op_income"], r["revenue"]) and 100 * _ratio(r["op_income"], r["revenue"]))
    r["fcf_margin_pct"] = _r(_ratio(r["fcf"], r["revenue"]) and 100 * _ratio(r["fcf"], r["revenue"]))
    invested = (r["equity"] or 0) + (debt or 0) if r["equity"] is not None else None
    r["roic_pct"] = _r(100 * r["op_income"] * (1 - TAX) / invested) if r["op_income"] is not None and invested and invested > 0 else None
    return r


def us_financials(cf: dict[str, Any], years: int = 5) -> dict[str, Any]:
    s = series(cf)
    rev = s["annual"].get("revenue") or {}
    ends = sorted(rev)[-years:]
    if not ends:  # 매출 태그가 없으면 순이익 기준으로 연도를 잡는다
        ends = sorted(s["annual"].get("net_income") or {})[-years:]
    annual = []
    for e in ends:
        row = _row(lambda k, e=e: _near(s["annual"].get(k) or {}, e),
                   lambda k, e=e: _near(s["instant"].get(k) or {}, e, tol=50 if k == "shares_out" else 20))
        annual.append({"period_end": e.isoformat(), **row})
    for i in range(1, len(annual)):
        a, b = annual[i], annual[i - 1]
        for k in ("revenue", "op_income", "net_income", "fcf"):
            a[f"{k}_yoy_pct"] = _r(100 * (a[k] / b[k] - 1)) if a.get(k) is not None and b.get(k) not in (None, 0) and b[k] > 0 else None
        a["diluted_shares_yoy_pct"] = _r(100 * (a["diluted_shares"] / b["diluted_shares"] - 1)) \
            if a.get("diluted_shares") and b.get("diluted_shares") else None
    q_rev = s["quarter"].get("revenue") or {}
    q_ends = sorted(q_rev)[-8:]
    ttm = None
    if len(q_ends) >= 4:
        last4 = q_ends[-4:]

        def flow(k: str, qs=last4) -> float | None:
            ser = s["quarter"].get(k) or {}
            vals = [_near(ser, q) for q in qs]
            if k in ("diluted_shares", "eps_diluted"):
                return vals[-1] if k == "diluted_shares" else (sum(vals) if all(v is not None for v in vals) else None)
            return sum(vals) if all(v is not None for v in vals) else None

        ttm = {"period_end": last4[-1].isoformat(), "quarters": [q.isoformat() for q in last4],
               **_row(flow, lambda k: _near(s["instant"].get(k) or {}, last4[-1], tol=50 if k == "shares_out" else 20))}
        if len(q_ends) >= 8:
            prev = q_ends[-8:-4]
            prev_rev = [_near(q_rev, q) for q in prev]
            if all(v is not None for v in prev_rev) and sum(prev_rev) > 0 and ttm["revenue"] is not None:
                ttm["revenue_yoy_pct"] = _r(100 * (ttm["revenue"] / sum(prev_rev) - 1))
    if annual and (ttm is None or abs((date.fromisoformat(ttm["period_end"]) -
                                         date.fromisoformat(annual[-1]["period_end"])).days) <= 20):
        # 최근 4분기 = 마지막 회계연도 → 분기 차분보다 연간 보고값이 정확하다
        ttm = dict(annual[-1], quarters=ttm["quarters"] if ttm else [], basis="fiscal_year")
    quarters = [{"period_end": q.isoformat(), "revenue": _near(q_rev, q),
                 "op_income": _near(s["quarter"].get("op_income") or {}, q),
                 "net_income": _near(s["quarter"].get("net_income") or {}, q)} for q in q_ends]
    return {"annual": annual, "ttm": ttm, "quarters": quarters, "anomalies": anomalies(annual, ttm)}


def anomalies(annual: list[dict[str, Any]], ttm: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    out = []
    rows = annual + ([dict(ttm, period_end=f"TTM {ttm['period_end']}")] if ttm else [])
    for i in range(1, len(rows)):
        a, b = rows[i], rows[i - 1]
        for k in ("revenue_yoy_pct", "op_income_yoy_pct"):
            if a.get(k) is not None and b.get(k) is not None and abs(a[k] - b[k]) >= 30:
                out.append({"period": a["period_end"], "metric": k, "from": b[k], "to": a[k]})
        for k in ("gross_margin_pct", "op_margin_pct", "fcf_margin_pct"):
            if a.get(k) is not None and b.get(k) is not None and abs(a[k] - b[k]) >= 5:
                out.append({"period": a["period_end"], "metric": k, "from": b[k], "to": a[k]})
        if (a.get("diluted_shares_yoy_pct") or 0) >= 5:
            out.append({"period": a["period_end"], "metric": "diluted_shares_yoy_pct", "to": a["diluted_shares_yoy_pct"]})
    return out


def fin(symbol: str, years: int = 5, ctx: ToolContext | None = None) -> dict[str, Any]:
    with ensure_context(ctx) as c:
        sym = parse_symbol(symbol)
        if sym.market == "us":
            from wsj.tools.lookup import sec_cik

            cik = sec_cik(c, sym.code)
            if cik is None:
                return {"symbol": sym.code, "error": "CIK 없음"}
            key = f"companyfacts:{cik}"
            if key not in c.memo:
                c.memo[key] = c.fetch.sec_companyfacts(cik)
            cf = c.memo[key]
            if not cf:
                return {"symbol": sym.code, "error": "companyfacts 없음(XBRL 미제출)"}
            return {"symbol": sym.code, "market": "us", "currency": "USD", "source": "sec:companyfacts", "cik": cik,
                    **us_financials(cf, years)}
        from wsj.tools.peers import naver_fundamentals

        nf = naver_fundamentals(c, sym) or {}
        return {"symbol": sym.code, "market": "kr", "currency": "KRW", "source": nf.get("source") or "naver",
                "ttm": {k: nf.get(k) for k in ("period", "period_end", "revenue", "operating_income", "net_income")},
                "annual": [], "anomalies": [], "notes": ["한국은 TTM 손익만 — 연도별은 공급망 지도 financials(deep profile)를 본다"]}
