"""환율: ref.fx_rates(있으면, 최신값만) → Frankfurter(ECB, 날짜 지정 가능) → open.er-api.com(최신값만).

ref 스키마는 PostgREST 에 노출되지 않을 수 있다(PGRST106, 0026 주석) — 그러면 바로 공개 출처로 간다.
rate 는 '기준통화 1 단위 = rate 상대통화' (USD/KRW 1358.73 = 1달러에 1,358.73원).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from wsj.tools import parse as P
from wsj.tools.context import ToolContext, ToolError, ensure_context, parse_day

_PAIR = re.compile(r"^([A-Za-z]{3})[/\-_ ]?([A-Za-z]{3})$")


def parse_pair(pair: str | None, base: str | None = None, quote: str | None = None) -> tuple[str, str]:
    if pair:
        m = _PAIR.match(pair.strip())
        if not m:
            raise ToolError(f"통화쌍을 읽을 수 없습니다: {pair!r} (예: USDKRW, USD/JPY)")
        return m.group(1).upper(), m.group(2).upper()
    return (base or "USD").upper(), (quote or "KRW").upper()


def rate_from_usd_per_unit(rows: list[dict[str, Any]], base: str, quote: str) -> tuple[float, str | None] | None:
    """ref.fx_rates 행(currency, usd_per_unit) → base/quote 교차환율."""
    usd = {"USD": (1.0, None)}
    for r in rows:
        v = P.num(r.get("usd_per_unit"))
        if r.get("currency") and v:
            usd[str(r["currency"]).upper()] = (v, str(r.get("as_of") or "")[:10] or None)
    if base not in usd or quote not in usd:
        return None
    (b, bd), (q, qd) = usd[base], usd[quote]
    as_of = min(d for d in (bd, qd) if d) if (bd or qd) else None
    return b / q, as_of


def get_rate(ctx: ToolContext, base: str, quote: str, day: date | None = None) -> dict[str, Any]:
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return {"pair": base + quote, "base": base, "quote": quote, "rate": 1.0, "as_of": None, "source": "identity"}
    key = f"fx:{base}{quote}:{day}"
    if key in ctx.memo:
        return ctx.memo[key]
    errors: list[str] = []
    res: dict[str, Any] | None = None
    if day is None:
        rows = ctx.db_select("ref.fx_rates", ["currency", "usd_per_unit", "as_of"], {"currency": sorted({base, quote} - {"USD"})})
        got = rate_from_usd_per_unit(rows or [], base, quote) if rows else None
        if got:
            res = {"rate": got[0], "as_of": got[1], "source": "db:ref.fx_rates"}
        elif rows is None and ctx.store is not None:
            errors.append("db:ref.fx_rates unavailable")
    if res is None:
        try:
            f = P.parse_frankfurter(ctx.fetch.fx_frankfurter(base, quote, day))
            if f and quote in f["rates"]:
                res = {"rate": f["rates"][quote], "as_of": f["date"], "source": "frankfurter (ECB reference)"}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"frankfurter: {str(exc)[:80]}")
    if res is None and day is None:
        try:
            e = P.parse_er_api(ctx.fetch.fx_er_api(base))
            if e and quote in e["rates"]:
                res = {"rate": e["rates"][quote], "as_of": e["date"], "source": "open.er-api.com"}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"er-api: {str(exc)[:80]}")
    if res is None:
        raise ToolError(f"{base}/{quote} 환율을 얻지 못했습니다: {'; '.join(errors) or '출처 없음'}")
    out = {"pair": base + quote, "base": base, "quote": quote, "rate": res["rate"], "inverse": 1 / res["rate"],
           "as_of": res["as_of"], "requested_date": day.isoformat() if day else None, "source": res["source"]}
    if errors:
        out["fallback_notes"] = errors
    ctx.memo[key] = out
    return out


def fx(pair: str | None = None, base: str | None = None, quote: str | None = None, day: str | date | None = None,
       ctx: ToolContext | None = None) -> dict[str, Any]:
    """환율 도구. fx('USDKRW') · fx(base='EUR', quote='USD', day='2026-11-04')."""
    b, q = parse_pair(pair, base, quote)
    with ensure_context(ctx) as c:
        return get_rate(c, b, q, parse_day(day))
