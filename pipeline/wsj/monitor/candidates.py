"""N5 후보 종목: 경로의 회사 → 미국·한국 상장 티커 확정 + 시총(USD).

  티커가 있으면 그 티커로 시세를 확인하고, 없거나 틀리면 이름으로 찾는다(tools.lookup — 미국 SEC 티커표, 한국 Naver).
  시세를 못 얻는 회사(비상장·다른 거래소)는 버린다.
후보 = (사건, 경로, 종목) 한 줄. 같은 사건 안에서 같은 종목은 한 번만(먼저 나온 경로).
"""

from __future__ import annotations

import logging
from typing import Any

from wsj.tools.context import ToolContext, ToolError

log = logging.getLogger("wsj.monitor")


def resolve_symbol(ctx: ToolContext, company: dict[str, Any]) -> dict[str, Any] | None:
    from wsj.tools.lookup import lookup
    from wsj.tools.quote import quote

    key = f"resolve:{company['market']}:{company.get('ticker') or company['name']}"
    if key in ctx.memo:
        return ctx.memo[key]
    tried = []
    if company.get("ticker"):
        tried.append(company["ticker"])
    else:
        try:
            res = lookup(company["name"], market=company["market"], limit=3, ctx=ctx)
            tried += [r["ticker"] for r in res.get("results", []) if r.get("market") == company["market"]][:1]
        except ToolError:
            pass
    out = None
    for t in tried:
        try:
            q = quote(t, ctx=ctx)
        except ToolError:
            continue
        if q.get("market") != company["market"]:
            continue
        mc = q.get("market_cap") or {}
        out = {"symbol": q["symbol"], "market": q["market"], "name": q.get("name") or company["name"],
               "exchange": q.get("exchange"), "market_cap_usd": mc.get("usd"),
               "close": (q.get("price") or {}).get("close"), "changes": q.get("changes")}
        break
    ctx.memo[key] = out
    return out


def resolve(ctx: ToolContext, event_id: str, event: dict[str, Any], explored: dict[str, Any]) -> list[dict[str, Any]]:
    rows, seen = [], set()
    for pi, p in enumerate(explored.get("paths") or []):
        for c in p["companies"]:
            sym = resolve_symbol(ctx, c)
            if not sym or sym["symbol"] in seen:
                continue
            seen.add(sym["symbol"])
            rows.append({"id": f"{event_id}p{pi + 1}-{sym['symbol'].lower()}", "event_id": event_id,
                         "event_title": event.get("title"), "event_date": event.get("date"),
                         "headline": explored.get("headline"), "axis": p["axis"], "path": p["path"],
                         "mechanism": p["mechanism"], "size": p["size"], "role": c["role"], "why": c["why"],
                         **sym, "status": "open"})
    return rows
