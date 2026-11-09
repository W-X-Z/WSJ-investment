"""N20 향후 밸류: 에이전트가 쓴 가정(Bear/Base/Bull) → 이익 → 배수 → 12개월 뒤 주가·지금 대비 배수.

가정은 3단계 에이전트(valuation.md)가 정하고, 계산은 이 코드가 한다. 입력 JSON:
{
  "symbol": "FPS", "price": 22.44, "shares": 304400000, "net_debt": 500000000, "currency": "USD",
  "basis": "FY2028",                                    # 12개월 뒤 시장이 볼 이익의 해
  "cases": {
    "bear": {"revenue": 3.0e9, "margin_pct": 20, "metric": "ebitda", "multiple": 11, "multiple_type": "ev", "why": "…"},
    "base": {"revenue": 3.6e9, "margin_pct": 25, "metric": "ebitda", "multiple": 16, "multiple_type": "ev", "why": "…"},
    "bull": {"eps": 2.6, "multiple": 30, "multiple_type": "pe", "why": "…"}
  }
}
  metric        net(순이익) | ebit | ebitda | fcf | sales — margin_pct 와 revenue 로 이익을 만든다 (sales 면 매출 그대로)
  multiple_type ev  → EV = 이익 × 배수, 지분 = EV − 순차입
                pe  → 지분 = 이익 × 배수 (metric 기본 net). eps 를 주면 주당 × 배수
                p   → 지분 = 이익 × 배수 (P/S·P/FCF 처럼 시총 기준 배수)
  shares        희석 주식 수(전 종류 합). 케이스별 shares 를 주면 그 값(희석·자사주 반영)
출력: 케이스별 이익·지분가치·주당가치·지금 대비 배수, 그리고 Base 배수에서 2배·3배가 되려면 필요한 이익(매출).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wsj.tools.context import ToolError

METRICS = ("net", "ebit", "ebitda", "fcf", "sales")
TYPES = ("ev", "pe", "p")


def _f(v: Any, name: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ToolError(f"{name} 는 숫자여야 한다: {v!r}") from None


def case_value(c: dict[str, Any], shares: float, net_debt: float) -> dict[str, Any]:
    mt = c.get("multiple_type", "ev")
    if mt not in TYPES:
        raise ToolError(f"multiple_type 은 {TYPES}: {mt!r}")
    mult = _f(c.get("multiple"), "multiple")
    sh = _f(c.get("shares", shares), "shares")
    if "eps" in c:
        eps = _f(c["eps"], "eps")
        earnings = eps * sh
        metric = "net"
    else:
        metric = c.get("metric") or ("net" if mt == "pe" else "ebitda")
        if metric not in METRICS:
            raise ToolError(f"metric 은 {METRICS}: {metric!r}")
        if "earnings" in c:
            earnings = _f(c["earnings"], "earnings")
        else:
            rev = _f(c.get("revenue"), "revenue")
            earnings = rev if metric == "sales" else rev * _f(c.get("margin_pct"), "margin_pct") / 100
        eps = earnings / sh if metric == "net" else None
    if mt == "ev":
        ev = earnings * mult
        equity = ev - net_debt
    else:
        equity = earnings * mult
        ev = equity + net_debt
    return {"metric": metric, "earnings": earnings, "eps": eps, "multiple": mult, "multiple_type": mt,
            "enterprise_value": ev, "equity_value": equity, "shares": sh, "value_per_share": equity / sh,
            "revenue": c.get("revenue"), "margin_pct": c.get("margin_pct"), "why": c.get("why")}


def run(spec: dict[str, Any]) -> dict[str, Any]:
    price = _f(spec.get("price"), "price")
    shares = _f(spec.get("shares"), "shares")
    nd = _f(spec.get("net_debt", 0.0), "net_debt")
    cases = spec.get("cases") or {}
    if not cases:
        raise ToolError("cases 가 비었다 (bear·base·bull)")
    out: dict[str, Any] = {"symbol": spec.get("symbol"), "price": price, "shares": shares, "net_debt": nd,
                           "currency": spec.get("currency"), "basis": spec.get("basis"),
                           "market_cap": price * shares, "cases": {}}
    for name, c in cases.items():
        v = case_value(c, shares, nd)
        v["vs_price_x"] = round(v["value_per_share"] / price, 2)
        v["upside_pct"] = round((v["value_per_share"] / price - 1) * 100, 1)
        out["cases"][name] = v
    base = out["cases"].get("base") or next(iter(out["cases"].values()))
    need = {}
    for x in (2, 3):
        equity = price * x * shares
        earnings = (equity + nd) / base["multiple"] if base["multiple_type"] == "ev" else equity / base["multiple"]
        row = {"price": price * x, "earnings_needed": earnings}
        if base.get("margin_pct") and base["metric"] != "sales":
            row["revenue_needed_at_base_margin"] = earnings / (float(base["margin_pct"]) / 100)
        elif base["metric"] == "sales":
            row["revenue_needed_at_base_margin"] = earnings
        if base["metric"] == "net":
            row["eps_needed"] = earnings / base["shares"]
        need[f"{x}x"] = row
    out["to_reach_at_base_multiple"] = need
    return out


def load_spec(path_or_json: str) -> dict[str, Any]:
    s = path_or_json.strip()
    if s.startswith("{"):
        return json.loads(s)
    return json.loads(Path(s).read_text())
