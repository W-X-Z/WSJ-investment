"""N14 주가 이슈: 지난 1년 주가에서 크게 움직인 날을 고르고, 그날 전후 공시를 붙인다.

  고르는 기준  벤치마크 대비 초과 수익률(일간)의 절댓값이 큰 날 + 거래량이 20일 평균의 2.5배 이상인 날.
               이웃한 날(3거래일 안)은 하나로 묶고 더 큰 날을 남긴다. 상위 N개(기본 8)를 날짜순으로 번호를 붙인다.
  공시        같은 날 ±1일에 접수된 공시(8-K 항목·10-Q·10-K 등)를 붙인다 — 이유는 3단계 에이전트가 웹 검색으로 채운다.
번호는 리포트의 시계열 글머리표와 주가 차트(chart.py)의 표시 번호로 그대로 쓴다.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wsj.tools import calc as C
from wsj.tools.context import ToolContext, ensure_context
from wsj.tools.prices import default_benchmark, get_bars, parse_symbol


def pick_moves(bars: list[dict[str, Any]], bench: list[dict[str, Any]] | None, top: int = 8, gap: int = 3,
               vol_mult: float = 2.5, min_abs_pct: float = 4.0) -> list[dict[str, Any]]:
    r = C.daily_returns(bars)
    rb = C.daily_returns(bench) if bench else {}
    vols = [b.get("volume") for b in bars]
    idx = {b["date"]: i for i, b in enumerate(bars)}
    cands = []
    for d, ret in r.items():
        i = idx[d]
        ex = ret - rb.get(d, 0.0)
        window = [v for v in vols[max(0, i - 20):i] if v]
        vr = (vols[i] / (sum(window) / len(window))) if window and vols[i] else None
        score = abs(ex) * 100
        if abs(ex) * 100 < min_abs_pct and not (vr and vr >= vol_mult):
            continue
        if vr and vr >= vol_mult:
            score += min(vr, 10)
        cands.append({"date": d, "i": i, "return_pct": C.pct(ret), "excess_pct": C.pct(ex),
                      "volume_ratio": round(vr, 2) if vr else None, "close": bars[i]["close"], "_s": score})
    cands.sort(key=lambda x: -x["_s"])
    kept: list[dict[str, Any]] = []
    for c in cands:
        if any(abs(c["i"] - k["i"]) <= gap for k in kept):
            continue
        kept.append(c)
        if len(kept) >= top:
            break
    kept.sort(key=lambda x: x["date"])
    for n, k in enumerate(kept, 1):
        k["n"] = n
        k.pop("_s")
        k.pop("i")
    return kept


def attach_filings(moves: list[dict[str, Any]], filings: list[dict[str, Any]], days: int = 1) -> None:
    for m in moves:
        d = date.fromisoformat(m["date"])
        near = []
        for f in filings or []:
            fd = date.fromisoformat(f["file_date"])
            if abs((fd - d).days) <= days:
                near.append({k: f.get(k) for k in ("form", "file_date", "items", "url")})
        if near:
            m["filings"] = near


def story(symbol: str, days: int = 365, top: int = 8, filings: list[dict[str, Any]] | None = None,
          ctx: ToolContext | None = None) -> dict[str, Any]:
    with ensure_context(ctx) as c:
        sym = parse_symbol(symbol)
        end = c.today
        start = end - timedelta(days=days)
        bars, src = get_bars(c, sym, start, end)
        bsym = parse_symbol(default_benchmark(sym))
        try:
            bench, bsrc = get_bars(c, bsym, start, end)
        except Exception as exc:  # noqa: BLE001
            bench, bsrc = [], f"error: {str(exc)[:80]}"
        moves = pick_moves(bars, bench, top=top)
        if filings:
            attach_filings(moves, filings)
        hl = C.high_low(bars, days) or {}
        return {"symbol": sym.code, "market": sym.market, "start": start.isoformat(), "end": end.isoformat(),
                "benchmark": bsym.code, "sources": {"symbol": src, "benchmark": bsrc}, "range": hl,
                "changes": C.trailing_changes(bars), "moves": moves,
                "series": [{"date": b["date"], "close": b["close"]} for b in bars]}
