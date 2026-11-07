"""이벤트 반응: 지정일 전후 수익률·거래량, 벤치마크 대비 초과·비정상 수익률.

  d          = 지정일 당일(거래일이면) 또는 그 뒤 첫 거래일
  창          d-1→d, d→d+1, d-1→d+1, d-5→d+5 (거래일 기준, 종목의 거래일로 벤치마크 날짜를 맞춤)
  거래량      d·d+1 거래량 ÷ d 직전 20거래일 평균
  초과        종목 − 벤치마크 / 비정상 = 종목 − β × 벤치마크 (β: d-5 이전 120거래일 일간수익률, 60개 미만이면 null)
벤치마크 기본값: 미국 SPY, 한국 KODEX200(069500).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from wsj.tools import calc as C
from wsj.tools.context import ToolContext, ToolError, ensure_context, parse_day
from wsj.tools.prices import default_benchmark, get_bars, parse_symbol

PRE_DAYS = 220   # 베타 120거래일 + 거래량 20일 + 여유 (달력일)
POST_DAYS = 14   # d+5 거래일 + 휴일 여유


def event(symbol: str, day: str | date, benchmark: str | None = None, vol_lookback: int = 20, beta_window: int = 120,
          ctx: ToolContext | None = None) -> dict[str, Any]:
    with ensure_context(ctx) as c:
        sym = parse_symbol(symbol)
        d = parse_day(day)
        if d is None:
            raise ToolError("이벤트 날짜가 필요합니다")
        start, end = d - timedelta(days=PRE_DAYS), min(d + timedelta(days=POST_DAYS), c.today)
        bars, src = get_bars(c, sym, start, end)
        bsym = parse_symbol(benchmark or default_benchmark(sym))
        try:
            bbars, bsrc = get_bars(c, bsym, start, end)
        except ToolError as exc:
            bbars, bsrc = [], f"error: {exc}"
        res = C.event_window(bars, d, bbars or None, vol_lookback=vol_lookback, beta_window=beta_window)
        if "error" in res:
            raise ToolError(f"{sym.code}: {res['error']}")
        missing = [k for k, v in res["returns"].items() if v["return_pct"] is None]
        out = {"symbol": sym.code, "market": sym.market, "benchmark": bsym.code, **res,
               "sources": {"symbol": src, "benchmark": bsrc}, "adjusted": False}
        if missing:
            out["notes"] = [f"windows without enough trading days yet: {', '.join(missing)}"]
        return out
