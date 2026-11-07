"""미 재무부 국채 par yield curve (home.treasury.gov 연도별 CSV, 키 없음).

지정일이 휴일·주말이면 그 전 마지막 공시일 값을 쓰고 as_of 에 남긴다. 연초라 그 해 값이 없으면 전년도 CSV 를 본다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from wsj.tools import parse as P
from wsj.tools.context import ToolContext, ToolError, ensure_context, parse_day
from wsj.tools.fetch import TREASURY_URL

HEADLINE = ("3m", "2y", "10y", "30y")


def pick_curve(rows: list[dict[str, Any]], day: date) -> dict[str, Any] | None:
    best = None
    for r in rows:
        if r["date"] <= day.isoformat():
            best = r
    return best


def curve_summary(row: dict[str, Any], requested: date, source_url: str) -> dict[str, Any]:
    c = row["curve"]

    def spread(a: str, b: str) -> float | None:
        return round((c[a] - c[b]) * 100, 1) if c.get(a) is not None and c.get(b) is not None else None

    return {"requested_date": requested.isoformat(), "as_of": row["date"], "units": "percent (par yield, bond-equivalent)",
            "yields": {k: c.get(k) for k in HEADLINE}, "curve": c,
            "spreads_bp": {"10y_2y": spread("10y", "2y"), "10y_3m": spread("10y", "3m"), "30y_10y": spread("30y", "10y")},
            "source": "home.treasury.gov daily_treasury_yield_curve", "source_url": source_url}


def rates(day: str | date | None = None, ctx: ToolContext | None = None) -> dict[str, Any]:
    with ensure_context(ctx) as c:
        d = parse_day(day, c.today)
        for year in (d.year, d.year - 1):
            try:
                rows = P.parse_treasury_csv(c.fetch.treasury_csv(year))
            except Exception as exc:  # noqa: BLE001
                raise ToolError(f"재무부 CSV {year} 실패: {str(exc)[:120]}") from exc
            row = pick_curve(rows, d)
            if row:
                return curve_summary(row, d, TREASURY_URL.format(year=year))
        raise ToolError(f"{d} 이전의 수익률 곡선이 없습니다")
