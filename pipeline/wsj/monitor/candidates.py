"""N5 후보 종목: 경로의 회사 → 미국·한국 상장 티커 확정 + 시총(USD).

  티커가 있으면 그 티커로 시세를 확인하고, 없거나 틀리면 이름으로 찾는다(tools.lookup — 미국 SEC 티커표, 한국 Naver).
  시세를 못 얻는 회사(비상장·다른 거래소)는 버린다.
후보 = (사건, 경로, 종목) 한 줄. 같은 사건 안에서 같은 종목은 한 번만(먼저 나온 경로).
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

from wsj.tools.context import ToolContext, ToolError

log = logging.getLogger("wsj.monitor")


def _norm(name: str | None) -> str:
    n = re.sub(r"\b(inc|corp|corporation|co|ltd|plc|holdings?|group|company|the|class [a-z]|common stock|ordinary shares)\b\.?",
               "", (name or "").lower())
    return re.sub(r"[^0-9a-z가-힣]+", "", n)


def same_company(a: str | None, b: str | None) -> bool:
    """이름이 같은 회사로 보이는지 — 한쪽이 다른 쪽을 포함하거나 충분히 비슷하면. 한글·영문이 섞이면 판단하지 않는다(True)."""
    x, y = _norm(a), _norm(b)
    if not x or not y:
        return True
    if bool(re.search(r"[가-힣]", x)) != bool(re.search(r"[가-힣]", y)):
        return True
    return x in y or y in x or SequenceMatcher(None, x, y).ratio() >= 0.6


def _quote_row(ctx: ToolContext, ticker: str, market: str) -> dict[str, Any] | None:
    from wsj.deep.target import clean_name
    from wsj.tools.quote import quote

    try:
        q = quote(ticker, ctx=ctx)
    except ToolError:
        return None
    if q.get("market") != market:
        return None
    mc = q.get("market_cap") or {}
    return {"symbol": q["symbol"], "market": q["market"], "name": clean_name(q.get("name")), "exchange": q.get("exchange"),
            "market_cap_usd": mc.get("usd"), "close": (q.get("price") or {}).get("close"), "changes": q.get("changes")}


def _by_name(ctx: ToolContext, company: dict[str, Any]) -> str | None:
    from wsj.tools.lookup import lookup

    try:
        res = lookup(company["name"], market=company["market"], limit=3, ctx=ctx)
    except ToolError:
        return None
    hits = [r for r in res.get("results", []) if r.get("market") == company["market"]]
    good = [r for r in hits if same_company(company["name"], r.get("name"))]
    return (good or hits[:1] or [{}])[0].get("ticker")


def resolve_symbol(ctx: ToolContext, company: dict[str, Any]) -> dict[str, Any] | None:
    """모델이 준 티커 → 시세. 티커가 없거나, 시세의 회사 이름이 모델이 말한 이름과 다르면 이름으로 다시 찾는다."""
    key = f"resolve:{company['market']}:{company.get('ticker') or company['name']}:{company['name']}"
    if key in ctx.memo:
        return ctx.memo[key]
    out = _quote_row(ctx, company["ticker"], company["market"]) if company.get("ticker") else None
    if out and not same_company(company["name"], out["name"]):
        log.info("ticker %s is %r, not %r — looking up by name", company["ticker"], out["name"], company["name"])
        alt = _by_name(ctx, company)
        alt_row = _quote_row(ctx, alt, company["market"]) if alt and alt != out["symbol"] else None
        out = alt_row if alt_row and same_company(company["name"], alt_row["name"]) else None
    elif out and company["market"] == "kr" and re.search(r"[가-힣]", company["name"]) \
            and _norm(company["name"]) != _norm(out["name"]):
        # 한국 종목은 모델이 코드를 틀리는 일이 잦다 → 한글 이름으로 찾은 종목의 이름이 정확히 같으면 그쪽을 쓴다
        alt = _by_name(ctx, company)
        alt_row = _quote_row(ctx, alt, "kr") if alt and alt != out["symbol"] else None
        if alt_row and _norm(alt_row["name"]) == _norm(company["name"]):
            out = alt_row
        elif not same_company(company["name"], out["name"]) or alt is None:
            log.info("kr %s: code %s is %r and the name finds nothing — dropped", company["name"], out["symbol"], out["name"])
            out = None
    if out is None and not company.get("ticker"):
        t = _by_name(ctx, company)
        out = _quote_row(ctx, t, company["market"]) if t else None
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
