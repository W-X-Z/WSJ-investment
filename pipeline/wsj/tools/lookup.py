"""이름·티커 → 상장 정보.

  미국  SEC company_tickers_exchange.json (cik, name, ticker, exchange) — data/cache 에 7일 캐시. SEC 가 막히면 Nasdaq 자동완성.
  한국  6자리 코드는 Naver basic, 이름(한글 포함)은 Naver 자동완성 (미국 종목의 한글 이름도 나온다: '엔비디아' → NVDA).
출처가 하나 죽어도 나머지 결과는 돌려주고, 실패한 출처는 errors 에 남긴다.
"""

from __future__ import annotations

import re
from typing import Any

from wsj.tools import parse as P
from wsj.tools.context import ToolContext, ToolError, ensure_context
from wsj.tools.prices import KR_RE
from wsj.util import normalize_name

HANGUL = re.compile(r"[가-힣]")


def sec_table(ctx: ToolContext) -> tuple[list[dict[str, Any]], str]:
    if "sec_tickers" not in ctx.memo:
        payload, src = ctx.fetch.sec_tickers()
        ctx.memo["sec_tickers"] = (P.parse_sec_tickers_exchange(payload), src)
    return ctx.memo["sec_tickers"]


def sec_cik(ctx: ToolContext, ticker: str) -> int | None:
    try:
        rows, _ = sec_table(ctx)
    except Exception:  # noqa: BLE001
        return None
    t = ticker.upper()
    alt = {t, t.replace(".", "-"), t.replace("-", ".")}
    return next((r["cik"] for r in rows if r["ticker"] in alt), None)


def rank_sec(rows: list[dict[str, Any]], query: str, limit: int = 10) -> list[dict[str, Any]]:
    """정확한 티커 > 정규화 이름 일치 > 이름 앞부분 > 이름 포함 (같은 등급은 티커 길이·알파벳 순)."""
    q = query.strip()
    qt = q.upper()
    qn = normalize_name(q)
    scored = []
    for r in rows:
        name_n = normalize_name(r.get("name"))
        if r["ticker"] == qt or r["ticker"] == qt.replace(".", "-"):
            s = 0
        elif qn and name_n == qn:
            s = 1
        elif qn and name_n.startswith(qn):
            s = 2
        elif qn and len(qn) >= 3 and qn in name_n:
            s = 3
        else:
            continue
        scored.append((s, len(r["ticker"]), r["ticker"], r))
    scored.sort(key=lambda x: x[:3])
    return [dict(r, match=["ticker", "name_exact", "name_prefix", "name_contains"][s]) for s, _, _, r in scored[:limit]]


def lookup(query: str, market: str | None = None, limit: int = 10, ctx: ToolContext | None = None) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        raise ToolError("검색어가 비었습니다")
    with ensure_context(ctx) as c:
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        sources: list[str] = []
        m = KR_RE.match(q)
        if m:
            code = m.group(1)
            try:
                b = P.parse_naver_basic(c.fetch.naver_basic(code))
            except Exception as exc:  # noqa: BLE001
                b = None
                errors.append(f"naver basic: {str(exc)[:80]}")
            if b:
                results.append({"market": "kr", "ticker": b["code"], "name": b["name"], "exchange": b["exchange"],
                                "type": b["type"], "px_key": f"{'KOSDAQ' if b['exchange'] == 'KOSDAQ' else 'KRX'}:{b['code']}",
                                "source": "naver:basic", "match": "code"})
                sources.append("naver:basic")
            return {"query": q, "results": results, "sources": sources, "errors": errors}

        want_us = market in (None, "us")
        want_kr = market in (None, "kr")
        if want_us and not HANGUL.search(q):
            try:
                rows, src = sec_table(c)
                for r in rank_sec(rows, q, limit):
                    results.append({"market": "us", "ticker": r["ticker"], "name": r["name"], "exchange": r["exchange"],
                                    "cik": r["cik"], "px_key": r["ticker"], "source": "sec:company_tickers_exchange",
                                    "match": r["match"]})
                sources.append(src)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"sec tickers: {str(exc)[:80]}")
                try:
                    for r in P.parse_nasdaq_autocomplete(c.fetch.nasdaq_autocomplete(q))[:limit]:
                        results.append({"market": "us", "ticker": r["ticker"], "name": r["name"], "exchange": r["exchange"],
                                        "asset": r["asset"], "px_key": r["ticker"], "source": "nasdaq:autocomplete",
                                        "match": "autocomplete"})
                    sources.append("nasdaq:autocomplete")
                except Exception as exc2:  # noqa: BLE001
                    errors.append(f"nasdaq autocomplete: {str(exc2)[:80]}")
        if want_kr or HANGUL.search(q):
            try:
                for r in P.parse_naver_autocomplete(c.fetch.naver_autocomplete(q))[:limit]:
                    if market and r["market"] != market:
                        continue
                    row = {"market": r["market"], "ticker": r["ticker"], "name": r["name"], "exchange": r["exchange"],
                           "source": "naver:autocomplete", "match": "autocomplete"}
                    if r["market"] == "kr":
                        row["px_key"] = f"{'KOSDAQ' if r['exchange'] == 'KOSDAQ' else 'KRX'}:{r['ticker']}"
                    elif r["market"] == "us":
                        row["px_key"] = r["ticker"]
                    results.append(row)
                sources.append("naver:autocomplete")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"naver autocomplete: {str(exc)[:80]}")
        seen, uniq = set(), []
        for r in results:
            k = (r["market"], r["ticker"])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        return {"query": q, "results": uniq[: max(limit, 1) * 2], "sources": sources, "errors": errors}
