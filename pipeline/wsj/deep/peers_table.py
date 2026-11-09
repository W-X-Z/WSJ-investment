"""N18 피어 비교표 (가벼운 모드): 고른 피어마다 시총·TTM 손익·배수 + 성장·이익률을 같은 기준으로.

피어는 3단계 에이전트가 고르고 이유를 적는다. 이 도구는 숫자만 맞춘다.
  배수   tools.peers (시총·순차입·EV, price_sales·pe·ev_ebit·ev_sales) — 통화는 각 종목 상장 통화
  성장   deep.fin 의 TTM 매출 성장률·영업이익률·FCF 마진 (미국만; 한국은 null)
  중앙값 대상 종목을 뺀 피어의 중앙값
"""

from __future__ import annotations

from statistics import median
from typing import Any

from wsj.tools.context import ToolContext, ToolError, ensure_context
from wsj.tools.prices import parse_symbol

METRICS = ("price_sales", "pe", "ev_ebit", "ev_sales", "revenue_yoy_pct", "op_margin_pct", "fcf_margin_pct", "roic_pct")


def _num(v: Any) -> float | None:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def light_row(ctx: ToolContext, symbol: str) -> dict[str, Any]:
    from wsj.deep.fin import fin
    from wsj.tools.peers import peer_row

    sym = parse_symbol(symbol)
    row = peer_row(ctx, sym)
    if sym.market == "us":
        f = fin(sym.code, years=3, ctx=ctx)
        t = f.get("ttm") or {}
        row.update(revenue_yoy_pct=t.get("revenue_yoy_pct"), op_margin_pct=t.get("op_margin_pct"),
                   fcf_margin_pct=t.get("fcf_margin_pct"), roic_pct=t.get("roic_pct"))
        if row.get("revenue_yoy_pct") is None and len(f.get("annual") or []) >= 1:
            row["revenue_yoy_pct"] = f["annual"][-1].get("revenue_yoy_pct")
    return row


def peers_table(target: str, peers: list[str], ctx: ToolContext | None = None) -> dict[str, Any]:
    if not peers:
        raise ToolError("피어를 하나 이상 주세요")
    with ensure_context(ctx) as c:
        rows = []
        for s in [target, *peers]:
            try:
                r = light_row(c, s)
            except Exception as exc:  # noqa: BLE001
                r = {"symbol": s, "error": str(exc)[:160]}
            r["is_target"] = s == target
            rows.append(r)
        med = {}
        for m in METRICS:
            vals = [_num(r.get(m)) for r in rows if not r["is_target"]]
            vals = [v for v in vals if v is not None]
            med[m] = round(median(vals), 2) if vals else None
        tgt = rows[0]
        vs = {m: (round(tgt[m] / med[m], 2) if _num(tgt.get(m)) is not None and med[m] not in (None, 0) else None)
              for m in ("price_sales", "pe", "ev_ebit", "ev_sales")}
        return {"as_of": c.today.isoformat(), "target": target, "rows": rows, "peer_median": med,
                "target_vs_median": vs}
