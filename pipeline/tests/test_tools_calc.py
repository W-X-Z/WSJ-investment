"""wsj.tools 순수 계산 — 수익률·베타·이벤트 창·역DCF."""

import math
from datetime import date, timedelta

import pytest

from wsj.tools import calc as C
from wsj.tools import dcf as D
from wsj.tools.context import ToolError
from wsj.tools.exposure import exposure_from_bars, parse_period


def bars_from(closes, start="2026-01-02", vols=None, skip_weekends=True):
    out, d, i = [], date.fromisoformat(start), 0
    while i < len(closes):
        if not skip_weekends or d.weekday() < 5:
            out.append({"date": d.isoformat(), "close": float(closes[i]), "volume": (vols[i] if vols else 1000)})
            i += 1
        d += timedelta(days=1)
    return out


def test_add_months_clamps_month_end():
    assert C.add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)
    assert C.add_months(date(2026, 1, 15), -3) == date(2025, 10, 15)
    assert C.add_months(date(2024, 3, 30), -1) == date(2024, 2, 29)


def test_period_return_uses_last_close_on_or_before():
    bars = [{"date": "2026-05-14", "close": 10.0}, {"date": "2026-05-18", "close": 11.0}, {"date": "2026-10-06", "close": 15.0}]
    r = C.period_return(bars, "2026-05-16", "2026-10-07")  # 5/16 토요일 → 5/14 종가, 10/7 → 10/6 종가
    assert r["start_date"] == "2026-05-14" and r["end_date"] == "2026-10-06" and r["return_pct"] == 50.0
    assert C.period_return(bars, "2026-01-01", "2026-10-06")["return_pct"] is None


def test_trailing_changes_calendar_months_and_ytd():
    bars = [{"date": "2025-12-30", "close": 80.0}, {"date": "2026-05-06", "close": 50.0}, {"date": "2026-08-06", "close": 200.0},
            {"date": "2026-10-06", "close": 125.0}, {"date": "2026-11-06", "close": 100.0}]
    ch = C.trailing_changes(bars)
    assert ch["1m"] == {"pct": -20.0, "from_date": "2026-10-06", "from_close": 125.0}
    assert ch["3m"]["pct"] == -50.0 and ch["6m"]["pct"] == 100.0
    assert ch["ytd"] == {"pct": 25.0, "from_date": "2025-12-30", "from_close": 80.0}
    assert ch["1y"] is None                                         # 1년 전 이력 없음 → null (추정 안 함)


def test_daily_and_basket_returns_intersection():
    a = {"d1": 0.01, "d2": 0.02, "d3": -0.01}
    b = {"d2": 0.04, "d3": 0.01}
    assert C.basket_returns([a, b]) == {"d2": pytest.approx(0.03), "d3": pytest.approx(0.0)}
    r = C.daily_returns([{"date": "x1", "close": 100.0}, {"date": "x2", "close": 110.0}, {"date": "x3", "close": 99.0}])
    assert r == {"x2": pytest.approx(0.1), "x3": pytest.approx(-0.1)}


def test_beta_corr_exact():
    x = {f"d{i:03d}": math.sin(i) / 50 for i in range(60)}
    y = {k: 2 * v + 0.001 for k, v in x.items()}
    bc = C.beta_corr(y, x)
    assert bc["beta"] == 2.0 and bc["corr"] == 1.0 and bc["n"] == 60
    neg = C.beta_corr({k: -v for k, v in x.items()}, x)
    assert neg["beta"] == -1.0 and neg["corr"] == -1.0
    assert C.beta_corr(y, x, days=list(x)[:10])["beta"] is None     # 표본 부족 → null


def test_beta_corr_matches_manual_formula():
    xs = [0.01, -0.02, 0.015, 0.003, -0.007, 0.02, -0.011, 0.004] * 4
    ys = [0.012, -0.03, 0.01, 0.006, -0.002, 0.025, -0.02, 0.001] * 4
    x = {f"d{i:02d}": v for i, v in enumerate(xs)}
    y = {f"d{i:02d}": v for i, v in enumerate(ys)}
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True)) / (n - 1)
    vx = sum((a - mx) ** 2 for a in xs) / (n - 1)
    vy = sum((b - my) ** 2 for b in ys) / (n - 1)
    bc = C.beta_corr(y, x)
    assert bc["beta"] == round(cov / vx, 4) and bc["corr"] == round(cov / math.sqrt(vx * vy), 4)


def test_event_window_returns_volume_and_benchmark():
    closes = [100.0] * 30 + [110.0, 99.0, 99.0, 99.0, 99.0, 108.9]
    vols = [1000] * 30 + [3000, 2000, 1000, 1000, 1000, 1000]
    s = bars_from(closes, vols=vols)
    bench = bars_from([50.0] * 30 + [51.0, 51.0, 51.0, 51.0, 51.0, 51.0])
    d = s[30]["date"]
    ev = C.event_window(s, d, bench)
    r = ev["returns"]
    assert ev["event_date"] == d
    assert r["d-1_to_d"]["return_pct"] == 10.0 and r["d-1_to_d"]["benchmark_pct"] == 2.0 and r["d-1_to_d"]["excess_pct"] == 8.0
    assert r["d_to_d+1"]["return_pct"] == -10.0
    assert r["d-5_to_d+5"]["return_pct"] == pytest.approx(8.9) and r["d-5_to_d+5"]["to"] == s[35]["date"]
    assert ev["volume"]["d"]["ratio"] == 3.0 and ev["volume"]["d+1"]["ratio"] == 2.0
    assert ev["beta_pre_event"]["beta"] is None                      # 평평한 벤치마크 / 표본 부족 → null, abnormal 도 null
    assert r["d-1_to_d"]["abnormal_pct"] is None


def test_event_window_weekend_date_rolls_forward_and_missing_after():
    s = bars_from([10, 11, 12, 13, 14, 15, 16, 17], start="2026-11-02")  # 월~수 다음 주
    ev = C.event_window(s, "2026-11-07")                               # 토요일 → 다음 월요일
    assert ev["event_date"] == "2026-11-09"
    assert ev["returns"]["d-5_to_d+5"]["return_pct"] is None
    assert "error" in C.event_window(s, "2027-01-01")


def test_event_window_abnormal_uses_pre_event_beta():
    import random

    rnd = random.Random(7)
    bench_c, stock_c = [100.0], [100.0]
    for _ in range(200):
        br = rnd.gauss(0, 0.01)
        bench_c.append(bench_c[-1] * (1 + br))
        stock_c.append(stock_c[-1] * (1 + 1.5 * br))
    s, b = bars_from(stock_c), bars_from(bench_c)
    ev = C.event_window(s, s[180]["date"], b)
    assert ev["beta_pre_event"]["beta"] == pytest.approx(1.5, abs=1e-3) and ev["beta_pre_event"]["n"] == 120
    w = ev["returns"]["d-1_to_d"]
    assert w["abnormal_pct"] == pytest.approx(0.0, abs=0.01)


def test_exposure_from_bars_and_periods():
    import random

    rnd = random.Random(1)
    base = [100.0]
    for _ in range(150):
        base.append(base[-1] * (1 + rnd.gauss(0, 0.01)))
    a = bars_from(base)
    double = [100.0]
    for x0, x1 in zip(base, base[1:], strict=False):
        double.append(double[-1] * (1 + 2 * (x1 / x0 - 1)))
    series = {"A": a, "B": bars_from(base), "T": bars_from(double), "SPY": bars_from(base)}
    end = date.fromisoformat(a[-1]["date"])
    p = (date.fromisoformat(a[10]["date"]), date.fromisoformat(a[20]["date"]))
    out = exposure_from_bars(series, ["T"], ["A", "B"], "SPY", 60, end, [p])
    t = out["results"][0]
    assert t["vs_basket"]["beta"] == 2.0 and t["vs_basket"]["corr"] == 1.0 and t["vs_basket"]["n"] == 60
    assert out["window"]["trading_days"] == 60
    assert t["periods"][0]["return_pct"] == C.period_return(series["T"], *p)["return_pct"]
    assert out["periods"][0]["basket_return_pct"] == C.period_return(a, *p)["return_pct"]
    assert parse_period("2026-05-15:2026-10-06") == (date(2026, 5, 15), date(2026, 10, 6))
    with pytest.raises(ToolError):
        parse_period("2026-10-06:2026-05-15")


# ---------------------------------------------------------------- DCF
def test_dcf_value_matches_closed_form():
    f0, r, g, gt, n = 100.0, 0.10, 0.05, 0.02, 5
    q = (1 + g) / (1 + r)
    pv = f0 * q * (1 - q**n) / (1 - q)
    fn = f0 * (1 + g) ** n
    tv = fn * (1 + gt) / (r - gt)
    want = pv + tv / (1 + r) ** n
    out = D.dcf_value(f0, r, gt, g, n, net_debt=50.0, shares=10.0)
    assert out["enterprise_value"] == pytest.approx(want, rel=1e-12)
    assert out["equity_value"] == pytest.approx(want - 50.0, rel=1e-12)
    assert out["value_per_share"] == pytest.approx((want - 50.0) / 10.0)
    assert out["cagr"] == pytest.approx(g) and out["exit_multiple_tv_over_fcf_next"] == pytest.approx(1 / (r - gt))


def test_reverse_dcf_round_trip_and_price_shares():
    target = D.dcf_value(150.0, 0.09, 0.03, 0.18, 10, net_debt=400.0)["equity_value"]
    rev = D.reverse_dcf(150.0, 0.09, 0.03, 10, market_cap=target, net_debt=400.0)
    assert rev["implied_fcf_cagr"] == pytest.approx(0.18, abs=1e-8)
    assert rev["check_equity_value"] == pytest.approx(target, rel=1e-8)
    rev2 = D.reverse_dcf(150.0, 0.09, 0.03, 10, price=target / 1000, shares=1000, net_debt=400.0)
    assert rev2["implied_fcf_cagr"] == pytest.approx(0.18, abs=1e-8)
    # 성장 0 일 때의 가치보다 시총이 낮으면 음의 CAGR
    low = D.dcf_value(150.0, 0.09, 0.03, 0.0, 10)["equity_value"] * 0.8
    assert D.reverse_dcf(150.0, 0.09, 0.03, 10, market_cap=low)["implied_fcf_cagr"] < 0


def test_reverse_dcf_errors_and_out_of_range():
    with pytest.raises(ToolError):
        D.reverse_dcf(100.0, 0.03, 0.03, 10, market_cap=1000.0)           # r ≤ g
    with pytest.raises(ToolError):
        D.reverse_dcf(-5.0, 0.10, 0.03, 10, market_cap=1000.0)            # 음수 FCF
    with pytest.raises(ToolError):
        D.reverse_dcf(10.0, 0.10, 0.03, 10)                                # 시총 없음
    r = D.reverse_dcf(1.0, 0.10, 0.03, 10, market_cap=1e15)
    assert r["implied_fcf_cagr"] is None and "범위" in r["note"]


def test_growth_path_list_and_padding():
    out = D.dcf_value(100.0, 0.10, 0.02, [0.3, 0.2], years=4)
    assert [f["growth"] for f in out["flows"]] == [0.3, 0.2, 0.2, 0.2]
    assert out["fcf_final_year"] == pytest.approx(100 * 1.3 * 1.2**3)
    with pytest.raises(ToolError):
        D.dcf_value(100.0, 0.10, 0.02, [0.1, 0.1, 0.1], years=2)
