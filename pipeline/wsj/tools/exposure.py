"""노출도: 종목들의 베타·상관 (묶음 대비, 벤치마크 대비) + 사용자가 준 구간 수익률.

  묶음      동일가중, 구성 종목 모두에 수익률이 있는 날만. 기본 AI 묶음 = NVDA, AVGO, VRT, GEV, PWR
  창        끝일 이하 마지막 N 거래일(기본 126 ≈ 6개월)의 일간 단순수익률
  구간      '2026-05-15:2026-10-06' 처럼 시작:끝. 묶음 구간 수익률 = 구성 종목 구간 수익률의 평균(동일가중 매수 보유)
한국·미국을 섞으면 같은 날짜끼리 맞추므로(시차) 상관이 낮게 나온다 — 한 시장끼리 쓰는 게 맞다.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wsj.tools import calc as C
from wsj.tools.context import ToolContext, ToolError, ensure_context, parse_day
from wsj.tools.prices import Symbol, default_benchmark, get_bars, parse_symbol

DEFAULT_BASKET = ("NVDA", "AVGO", "VRT", "GEV", "PWR")


def parse_period(p: str | tuple[Any, Any]) -> tuple[date, date]:
    if isinstance(p, (tuple, list)):
        a, b = p
    else:
        if ":" not in str(p):
            raise ToolError(f"구간은 시작:끝 형식입니다: {p!r}")
        a, b = str(p).split(":", 1)
    da, db = parse_day(a), parse_day(b)
    if da is None or db is None or da >= db:
        raise ToolError(f"구간이 잘못됐습니다: {p!r}")
    return da, db


def exposure_from_bars(series: dict[str, list[dict[str, Any]]], tickers: list[str], basket: list[str], benchmark: str,
                       window: int, end: date, periods: list[tuple[date, date]]) -> dict[str, Any]:
    """순수 계산부 (테스트용): series = {코드: 일봉}."""
    rets = {k: C.daily_returns(v) for k, v in series.items()}
    bask = C.basket_returns([rets.get(t, {}) for t in basket])
    bench = rets.get(benchmark, {})
    days = C.last_n_days(bask, window, end) if bask else C.last_n_days(bench, window, end)
    rows = []
    for t in tickers:
        r = rets.get(t)
        if r is None:
            rows.append({"ticker": t, "error": "no price history"})
            continue
        row: dict[str, Any] = {"ticker": t,
                               "vs_basket": C.beta_corr(r, bask, days) if bask else None,
                               "vs_benchmark": C.beta_corr(r, bench, days) if bench else None}
        if periods:
            row["periods"] = [C.period_return(series[t], a, b) for a, b in periods]
        rows.append(row)
    out: dict[str, Any] = {"window": {"trading_days": len(days), "requested": window, "start": days[0] if days else None,
                                      "end": days[-1] if days else None}, "results": rows}
    if periods:
        bp = []
        for a, b in periods:
            members = [C.period_return(series[t], a, b) for t in basket if t in series]
            vals = [m["return_pct"] for m in members if m["return_pct"] is not None]
            bp.append({"start": a.isoformat(), "end": b.isoformat(),
                       "basket_return_pct": round(sum(vals) / len(vals), 2) if vals and len(vals) == len(basket) else None,
                       "benchmark": C.period_return(series[benchmark], a, b) if benchmark in series else None})
        out["periods"] = bp
    return out


def exposure(tickers: list[str], basket: list[str] | None = None, benchmark: str | None = None, window: int = 126,
             end: str | date | None = None, periods: list[str] | None = None, ctx: ToolContext | None = None) -> dict[str, Any]:
    if not tickers:
        raise ToolError("종목을 하나 이상 주세요")
    with ensure_context(ctx) as c:
        syms = [parse_symbol(t) for t in tickers]
        bsyms = [parse_symbol(t) for t in (basket or DEFAULT_BASKET)]
        bench = parse_symbol(benchmark or default_benchmark(syms[0]))
        e = parse_day(end, c.today)
        per = [parse_period(p) for p in periods or []]
        start = min([e - timedelta(days=int(window * 1.6) + 20)] + [a - timedelta(days=10) for a, _ in per])
        last = max([e] + [b for _, b in per])
        series: dict[str, list[dict[str, Any]]] = {}
        sources: dict[str, str] = {}
        errors: dict[str, str] = {}
        uniq: dict[str, Symbol] = {s.code: s for s in [*syms, *bsyms, bench]}
        for code, s in uniq.items():
            try:
                series[code], sources[code] = get_bars(c, s, start, last)
            except ToolError as exc:
                errors[code] = str(exc)
        missing_basket = [s.code for s in bsyms if s.code not in series]
        if missing_basket:
            raise ToolError(f"묶음 종목 가격을 못 받았습니다: {', '.join(missing_basket)} ({'; '.join(errors.values())[:200]})")
        win_series = {k: [b for b in v if b["date"] <= e.isoformat()] for k, v in series.items()}
        res = exposure_from_bars(win_series, [s.code for s in syms], [s.code for s in bsyms], bench.code, window, e, [])
        if per:
            pres = exposure_from_bars(series, [s.code for s in syms], [s.code for s in bsyms], bench.code, window, e, per)
            by = {r["ticker"]: r.get("periods") for r in pres["results"]}
            for r in res["results"]:
                r["periods"] = by.get(r["ticker"])
            res["periods"] = pres["periods"]
        return {"basket": [s.code for s in bsyms], "basket_weighting": "equal", "benchmark": bench.code, "end": e.isoformat(),
                **res, "sources": sources, "errors": errors or None, "adjusted": False}
