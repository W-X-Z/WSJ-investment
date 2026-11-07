"""수익률·베타·이벤트 반응 — 순수 계산. 입력은 parse.Bar 목록(날짜 오름차순), 출력은 숫자와 그 숫자를 만든 날짜.

규칙 (재현성을 위해 고정):
  - 기간 수익률 a→b = (b 이하 마지막 종가) ÷ (a 이하 마지막 종가) − 1. 휴장일이면 그 전 거래일 종가.
  - 1m/3m/6m = 마지막 거래일에서 달력 기준 1·3·6개월 전 날짜(말일 보정) 이하 마지막 종가 대비.
  - YTD = 전년도 마지막 거래일 종가 대비.
  - 일간 수익률 = 연속한 두 거래일 종가 비율 − 1 (그 시리즈 자신의 거래일 기준), 날짜로 맞춰 비교.
  - 베타 = cov(y, x) ÷ var(x), 상관 = cov ÷ (sd_x · sd_y), 표본(n−1) 기준.
  - 이벤트일 d = 지정일 당일 또는 그 뒤 첫 거래일.
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from typing import Any

Bar = dict[str, Any]


def _d(x: str | date) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def pct(x: float | None, nd: int = 2) -> float | None:
    return None if x is None else round(x * 100, nd)


def close_on_or_before(bars: Sequence[Bar], day: str | date) -> Bar | None:
    key = _d(day).isoformat()
    best = None
    for b in bars:
        if b["date"] <= key:
            best = b
        else:
            break
    return best


def period_return(bars: Sequence[Bar], start: str | date, end: str | date) -> dict[str, Any]:
    a, b = close_on_or_before(bars, start), close_on_or_before(bars, end)
    r = b["close"] / a["close"] - 1 if a and b and a["close"] else None
    return {"start": _d(start).isoformat(), "end": _d(end).isoformat(),
            "start_date": a["date"] if a else None, "start_close": a["close"] if a else None,
            "end_date": b["date"] if b else None, "end_close": b["close"] if b else None,
            "return_pct": pct(r)}


def trailing_changes(bars: Sequence[Bar]) -> dict[str, Any]:
    if not bars:
        return {}
    last = bars[-1]
    ld = _d(last["date"])
    out: dict[str, Any] = {}
    for label, months in (("1m", 1), ("3m", 3), ("6m", 6), ("1y", 12)):
        ref = close_on_or_before(bars, add_months(ld, -months))
        out[label] = _change(last, ref)
    ref = close_on_or_before(bars, date(ld.year - 1, 12, 31))
    out["ytd"] = _change(last, ref)
    return out


def _change(last: Bar, ref: Bar | None) -> dict[str, Any] | None:
    if not ref or not ref["close"] or ref["date"] == last["date"]:
        return None
    return {"pct": pct(last["close"] / ref["close"] - 1), "from_date": ref["date"], "from_close": ref["close"]}


def high_low(bars: Sequence[Bar], days: int = 365) -> dict[str, Any] | None:
    if not bars:
        return None
    cut = (_d(bars[-1]["date"]) - timedelta(days=days)).isoformat()
    xs = [b for b in bars if b["date"] > cut]
    hi = max(xs, key=lambda b: b["close"])
    lo = min(xs, key=lambda b: b["close"])
    last = bars[-1]["close"]
    return {"high": hi["close"], "high_date": hi["date"], "low": lo["close"], "low_date": lo["date"],
            "pct_from_high": pct(last / hi["close"] - 1), "pct_from_low": pct(last / lo["close"] - 1)}


def daily_returns(bars: Sequence[Bar]) -> dict[str, float]:
    out: dict[str, float] = {}
    for a, b in zip(bars, bars[1:], strict=False):
        if a["close"] and b["close"]:
            out[b["date"]] = b["close"] / a["close"] - 1
    return out


def basket_returns(members: Iterable[dict[str, float]]) -> dict[str, float]:
    """동일가중 묶음의 일간 수익률 — 구성 종목 모두에 수익률이 있는 날만 (구성이 날마다 바뀌지 않게)."""
    ms = [m for m in members if m]
    if not ms:
        return {}
    days = set(ms[0])
    for m in ms[1:]:
        days &= set(m)
    return {d: sum(m[d] for m in ms) / len(ms) for d in sorted(days)}


def beta_corr(y: dict[str, float], x: dict[str, float], days: Iterable[str] | None = None,
              min_obs: int = 20) -> dict[str, Any]:
    """y 를 x 에 회귀한 베타와 상관. days 를 주면 그 날짜만 쓴다."""
    common = sorted(set(y) & set(x) & (set(days) if days is not None else set(y)))
    n = len(common)
    out: dict[str, Any] = {"n": n, "start": common[0] if common else None, "end": common[-1] if common else None,
                           "beta": None, "corr": None}
    if n < max(min_obs, 3):
        return out
    xs = [x[d] for d in common]
    ys = [y[d] for d in common]
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=False)) / (n - 1)
    vx = sum((a - mx) ** 2 for a in xs) / (n - 1)
    vy = sum((b - my) ** 2 for b in ys) / (n - 1)
    if vx > 0:
        out["beta"] = round(cov / vx, 4)
    if vx > 0 and vy > 0:
        out["corr"] = round(cov / math.sqrt(vx * vy), 4)
    out["vol_ann_pct"] = pct(math.sqrt(vy) * math.sqrt(252)) if vy > 0 else None
    return out


def last_n_days(returns: dict[str, float], n: int, end: str | date | None = None) -> list[str]:
    keys = sorted(returns)
    if end is not None:
        e = _d(end).isoformat()
        keys = [k for k in keys if k <= e]
    return keys[-n:]


# ---------------------------------------------------------------- 이벤트 반응
def _idx_on_or_after(bars: Sequence[Bar], day: str | date) -> int | None:
    key = _d(day).isoformat()
    return next((i for i, b in enumerate(bars) if b["date"] >= key), None)


def _r(bars: Sequence[Bar], i: int, j: int) -> float | None:
    if i < 0 or j < 0 or i >= len(bars) or j >= len(bars) or not bars[i]["close"]:
        return None
    return bars[j]["close"] / bars[i]["close"] - 1


def _r_dates(bars: Sequence[Bar], d0: str | None, d1: str | None) -> float | None:
    """벤치마크는 인덱스가 아니라 종목의 날짜로 맞춘다 (휴장일이 다를 수 있다)."""
    if not d0 or not d1:
        return None
    a, b = close_on_or_before(bars, d0), close_on_or_before(bars, d1)
    return b["close"] / a["close"] - 1 if a and b and a["close"] else None


WINDOWS = {"d-1_to_d": (-1, 0), "d_to_d+1": (0, 1), "d-1_to_d+1": (-1, 1), "d-5_to_d+5": (-5, 5)}


def event_window(bars: Sequence[Bar], day: str | date, bench: Sequence[Bar] | None = None,
                 vol_lookback: int = 20, beta_window: int = 120, beta_gap: int = 5) -> dict[str, Any]:
    t = _idx_on_or_after(bars, day)
    if t is None:
        return {"error": f"{_d(day).isoformat()} 이후 거래일 데이터가 없습니다"}
    date_at = lambda i: bars[i]["date"] if 0 <= i < len(bars) else None  # noqa: E731
    out: dict[str, Any] = {"requested_date": _d(day).isoformat(), "event_date": bars[t]["date"],
                           "close_d-1": bars[t - 1]["close"] if t >= 1 else None, "close_d": bars[t]["close"]}

    # 시장 모형 베타: d−(gap+window) .. d−gap−1 의 일간 수익률
    beta = None
    if bench:
        sr, br = daily_returns(bars[: max(0, t - beta_gap)]), daily_returns(bench)
        days = last_n_days(sr, beta_window)
        bc = beta_corr(sr, br, days, min_obs=60)
        beta = bc["beta"]
        out["beta_pre_event"] = {"beta": beta, "n": bc["n"], "start": bc["start"], "end": bc["end"]}

    rets: dict[str, Any] = {}
    for name, (a, b) in WINDOWS.items():
        r = _r(bars, t + a, t + b)
        row: dict[str, Any] = {"from": date_at(t + a), "to": date_at(t + b), "return_pct": pct(r)}
        if bench:
            br_ = _r_dates(bench, date_at(t + a), date_at(t + b))
            row["benchmark_pct"] = pct(br_)
            row["excess_pct"] = pct(r - br_) if r is not None and br_ is not None else None
            row["abnormal_pct"] = pct(r - beta * br_) if r is not None and br_ is not None and beta is not None else None
        rets[name] = row
    out["returns"] = rets

    def vol_ratio(i: int) -> dict[str, Any] | None:
        if i >= len(bars) or bars[i].get("volume") is None:
            return None
        prior = [b["volume"] for b in bars[max(0, t - vol_lookback): t] if b.get("volume") is not None]
        if len(prior) < max(5, vol_lookback // 2):
            return None
        avg = sum(prior) / len(prior)
        return {"date": bars[i]["date"], "volume": bars[i]["volume"], "avg_prior": round(avg),
                "n_prior": len(prior), "ratio": round(bars[i]["volume"] / avg, 2) if avg else None}

    out["volume"] = {"d": vol_ratio(t), "d+1": vol_ratio(t + 1), "lookback_days": vol_lookback}
    return out
