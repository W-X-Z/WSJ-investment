"""리레이팅 가치평가 (ADR-0025 결정 6, T-2) — "지금 가격은 몇 %의 지속 마진을 가정하나" 를 역산하고, 체제별 가격을 낸다.

    python -m wsj.ecosystems.rerating company:skhynix company:mu          # 기본 밴드(memory)
    python -m wsj.ecosystems.rerating company:semco --band substrate --json

12개월 P/S 시나리오(리포트 가치평가)는 배수가 고정된 세계를 가정한다. 메모리·기판처럼 마진이 사이클로 크게 움직이는 업종의
리레이팅은 두 가지가 동시에 바뀌는 일이다 — (1) 지속 가능한 마진에 대한 시장의 믿음, (2) 그 이익에 주는 배수.
그래서 이 계산은 두 숫자를 낸다:
- **시장 내재 지속 마진** = 시총 / (배수 × 매출 × (1 − 세율)). 배수를 '정상' 값으로 두면, 지금 가격이 몇 %의 영업이익률이 영원히 간다고
  보는지가 나온다. TTM 마진보다 훨씬 낮으면 시장은 정점이라 보고 있는 것이다.
- **체제별 가격** = 매출 × 마진 × (1 − 세율) × 배수 / 주식수 — trough · mid(사이클 정상) · regime(구조적 고마진 유지) 세 밴드.
- **필요 매출 배수** = 그 밴드의 마진·배수로 지금 시총을 정당화하려면 매출이 TTM 의 몇 배여야 하나. 내재 마진이 100% 를 넘는
  종목(성장을 가격에 넣은 종목)은 이 숫자로 읽는다.
밴드의 마진·배수는 **가정**이다 (BANDS, 출처 없는 기본값). 테제 작업이 업종 근거로 덮어쓴다. 확률은 이 계산이 정하지 않는다.
영업이익 기준으로 계산한다 — 순이익은 일회성 영업외 손익이 커서(예: SK hynix TTM 순이익 > 영업이익) 정규화에 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

# 업종 밴드 — 가정. margin = 영업이익률, pe = 세후 영업이익 기준 배수.
BANDS: dict[str, dict[str, dict[str, float]]] = {
    "memory": {"trough": {"margin": 0.05, "pe": 15.0}, "mid": {"margin": 0.25, "pe": 11.0}, "regime": {"margin": 0.45, "pe": 14.0}},
    "substrate": {"trough": {"margin": 0.03, "pe": 20.0}, "mid": {"margin": 0.10, "pe": 16.0}, "regime": {"margin": 0.18, "pe": 22.0}},
    "equipment": {"trough": {"margin": 0.05, "pe": 20.0}, "mid": {"margin": 0.15, "pe": 18.0}, "regime": {"margin": 0.25, "pe": 25.0}},
}
TAX = 0.22
NORMAL_PE = (8.0, 12.0, 16.0)


def _f(x: Any) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def scenario_price(revenue: float, margin: float, pe: float, shares: float, tax: float = TAX) -> float:
    return revenue * margin * (1 - tax) * pe / shares


def implied_margin(market_cap: float, revenue: float, pe: float, tax: float = TAX) -> float:
    return market_cap / (pe * revenue * (1 - tax))


def evaluate(f: dict[str, Any], price: float | None, band: str = "memory", bands: dict[str, dict[str, float]] | None = None,
             revenue_growth: float = 0.0, tax: float = TAX) -> dict[str, Any]:
    """f = v_company_fundamentals 의 ttm 행. price = 현재가(현지 통화). revenue_growth = 시나리오 매출에 곱할 성장(0 이면 TTM 그대로)."""
    b = bands or BANDS[band]
    rev, op, shares = _f(f.get("revenue")), _f(f.get("operating_income")), _f(f.get("shares_outstanding"))
    out: dict[str, Any] = {"company": f.get("company_id"), "currency": f.get("currency"), "period_end": f.get("period_end"), "band": band,
                           "assumptions": {"tax": tax, "revenue_growth": revenue_growth, "bands": b, "basis": "세후 영업이익 × 배수 (순이익 아님)"}}
    if not (rev and shares):
        out["note"] = "매출·주식수 없음"
        return out
    out["ttm_op_margin_pct"] = round(100 * op / rev, 1) if op is not None else None
    if not price:
        out["note"] = "가격 없음 — 시나리오 가격만"
    else:
        mcap = price * shares
        out["price"] = price
        out["market_cap_local"] = mcap
        if op:
            out["pe_on_after_tax_op"] = round(mcap / (op * (1 - tax)), 1)
        out["implied_durable_margin_pct"] = {f"pe_{int(p)}": round(100 * implied_margin(mcap, rev, p, tax), 1) for p in NORMAL_PE}
    r = rev * (1 + revenue_growth)
    sc = {}
    for name, v in b.items():
        px = scenario_price(r, v["margin"], v["pe"], shares, tax)
        sc[name] = {"margin_pct": round(100 * v["margin"], 1), "pe": v["pe"], "price": round(px, 2)}
        if price:
            sc[name]["vs_price_pct"] = round(100 * (px / price - 1), 1)
            sc[name]["required_revenue_multiple"] = round(price * shares / (v["margin"] * (1 - tax) * v["pe"]) / rev, 2)
    out["scenarios"] = sc
    return out


def _public() -> tuple[Any, str, str]:
    from wsj.http import HttpClient

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "https://dcatgfivsvbktylmtvgf.supabase.co"
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_KEY")
    if not key:
        raise SystemExit("SUPABASE_PUBLISHABLE_KEY 가 필요하다 (공개 읽기 키)")
    return HttpClient("WSJ-investment rerating", timeout=30, max_retries=2), url, key


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("companies", nargs="+")
    ap.add_argument("--band", default="memory", choices=sorted(BANDS))
    ap.add_argument("--growth", type=float, default=0.0, help="시나리오 매출 = TTM × (1 + growth)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    from wsj.ecosystems.ideas import fetch_public_view
    from wsj.ecosystems.ontology import load_graph
    from wsj.ecosystems.quiet import listing_keys

    http, url, key = _public()
    try:
        ids = ",".join(f'"{c}"' for c in args.companies)
        fund = {r["company_id"]: r for r in fetch_public_view(http, url, key, "v_company_fundamentals", {"company_id": f"in.({ids})", "period": "eq.ttm"})}
        keys = listing_keys(load_graph())
        pxk = [keys[c] for c in args.companies if c in keys]
        px = {r["ticker"]: _f(r.get("close")) for r in fetch_public_view(http, url, key, "v_price_context", {"ticker": "in.(" + ",".join(f'"{k}"' for k in pxk) + ")"})} if pxk else {}
    finally:
        http.close()
    out = [evaluate(fund[c], px.get(keys.get(c, "")), args.band, revenue_growth=args.growth) if c in fund else {"company": c, "note": "재무 없음"} for c in args.companies]
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    for o in out:
        print(f"{o['company']} ({o.get('currency')}, TTM {o.get('period_end')}) 영업이익률 {o.get('ttm_op_margin_pct')}%  {o.get('note', '')}")
        if "implied_durable_margin_pct" in o:
            print(f"  가격 {o['price']:,.0f}  세후영업이익 배수 {o.get('pe_on_after_tax_op')}배  시장 내재 지속 마진 {o['implied_durable_margin_pct']}")
        for n, s in (o.get("scenarios") or {}).items():
            need = f"  필요 매출 ×{s['required_revenue_multiple']}" if "required_revenue_multiple" in s else ""
            print(f"  {n:<7} 마진 {s['margin_pct']:>5}% × {s['pe']:>4}배 → {s['price']:>14,.0f}  {s.get('vs_price_pct', '')}{need}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
