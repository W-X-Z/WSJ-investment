"""역DCF / DCF — 순수 함수 (네트워크 없음).

모형 (연말 할인, 단순):
  FCF_t = FCF_0 × Π(1 + g_i)                 t = 1..N
  EV    = Σ FCF_t / (1+r)^t  +  TV / (1+r)^N,   TV = FCF_N × (1 + g_term) / (r − g_term)
  지분가치 = EV − 순차입금
역DCF: 지분가치 = 시가총액 이 되는 일정한 FCF 연평균 성장률(CAGR) g 를 이분법으로 푼다 (FCF_0 > 0 일 때 g 에 대해 단조 증가).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wsj.tools.context import ToolError

G_LO, G_HI = -0.95, 5.0  # 역DCF 탐색 범위 (−95% ~ +500%/년)


def _check(discount_rate: float, terminal_growth: float, years: int) -> None:
    if discount_rate <= terminal_growth:
        raise ToolError(f"할인율({discount_rate}) 은 영구성장률({terminal_growth}) 보다 커야 합니다")
    if discount_rate <= -1 or years < 1:
        raise ToolError("할인율 > −100%, 기간 ≥ 1년 이어야 합니다")


def growth_path(growth: float | Sequence[float], years: int | None) -> list[float]:
    if isinstance(growth, (int, float)):
        if not years:
            raise ToolError("단일 성장률에는 years 가 필요합니다")
        return [float(growth)] * int(years)
    path = [float(g) for g in growth]
    if not path:
        raise ToolError("성장 경로가 비었습니다")
    if years and years != len(path):
        if years < len(path):
            raise ToolError(f"성장 경로 길이 {len(path)} 가 years={years} 보다 깁니다")
        path = path + [path[-1]] * (years - len(path))  # 모자라면 마지막 값을 이어 쓴다
    return path


def dcf_value(base_fcf: float, discount_rate: float, terminal_growth: float, growth: float | Sequence[float],
              years: int | None = 10, net_debt: float = 0.0, shares: float | None = None) -> dict[str, Any]:
    """정방향: 성장 경로 → EV·지분가치(·주당가치)."""
    path = growth_path(growth, years)
    n = len(path)
    _check(discount_rate, terminal_growth, n)
    fcf, pv_sum, flows = float(base_fcf), 0.0, []
    for t, g in enumerate(path, start=1):
        fcf *= 1 + g
        df = (1 + discount_rate) ** -t
        pv_sum += fcf * df
        flows.append({"year": t, "growth": g, "fcf": fcf, "pv": fcf * df})
    tv = fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_tv = tv * (1 + discount_rate) ** -n
    ev = pv_sum + pv_tv
    equity = ev - net_debt
    out = {"enterprise_value": ev, "equity_value": equity, "pv_explicit": pv_sum, "pv_terminal": pv_tv,
           "terminal_value": tv, "terminal_share_of_ev": pv_tv / ev if ev else None, "fcf_final_year": fcf,
           "exit_multiple_tv_over_fcf_next": tv / (fcf * (1 + terminal_growth)) if fcf else None,
           "cagr": (fcf / base_fcf) ** (1 / n) - 1 if base_fcf > 0 and fcf > 0 else None,
           "years": n, "flows": flows}
    if shares:
        out["value_per_share"] = equity / shares
    return out


def implied_cagr(target_equity: float, base_fcf: float, discount_rate: float, terminal_growth: float, years: int = 10,
                 net_debt: float = 0.0, tol: float = 1e-10, max_iter: int = 300) -> float | None:
    """지분가치(g) = target 인 g. 범위 밖이면 None."""
    _check(discount_rate, terminal_growth, years)
    if base_fcf <= 0:
        raise ToolError("역DCF 는 기준 FCF 가 양수일 때만 풀 수 있습니다 (음수면 성장할수록 가치가 줄어든다)")

    def f(g: float) -> float:
        return dcf_value(base_fcf, discount_rate, terminal_growth, g, years, net_debt)["equity_value"] - target_equity

    lo, hi = G_LO, G_HI
    flo, fhi = f(lo), f(hi)
    if flo > 0 or fhi < 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(hi - lo) < tol:
            break
        if fm < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def reverse_dcf(base_fcf: float, discount_rate: float, terminal_growth: float, years: int = 10,
                market_cap: float | None = None, price: float | None = None, shares: float | None = None,
                net_debt: float = 0.0) -> dict[str, Any]:
    """시가총액(또는 주가 × 희석주식수)이 요구하는 FCF CAGR."""
    if market_cap is None:
        if price is None or shares is None:
            raise ToolError("market_cap 또는 (price, shares) 가 필요합니다")
        market_cap = price * shares
    g = implied_cagr(market_cap, base_fcf, discount_rate, terminal_growth, years, net_debt)
    out: dict[str, Any] = {
        "inputs": {"market_cap": market_cap, "price": price, "shares": shares, "net_debt": net_debt, "base_fcf": base_fcf,
                   "discount_rate": discount_rate, "terminal_growth": terminal_growth, "years": years},
        "enterprise_value_at_price": market_cap + net_debt,
        "ev_over_base_fcf": (market_cap + net_debt) / base_fcf,
        "fcf_yield_on_ev": base_fcf / (market_cap + net_debt) if market_cap + net_debt else None,
        "implied_fcf_cagr": g,
        "implied_fcf_cagr_pct": round(g * 100, 3) if g is not None else None,
    }
    if g is None:
        lo = dcf_value(base_fcf, discount_rate, terminal_growth, G_LO, years, net_debt)["equity_value"]
        out["note"] = (f"탐색 범위({G_LO:.0%}~{G_HI:.0%}/년) 밖 — 시총이 {'너무 낮아' if market_cap < lo else '너무 높아'} "
                       "일정 성장률로 맞출 수 없습니다")
        return out
    fwd = dcf_value(base_fcf, discount_rate, terminal_growth, g, years, net_debt, shares)
    out.update({"fcf_final_year": fwd["fcf_final_year"], "fcf_multiple_of_base": fwd["fcf_final_year"] / base_fcf,
                "pv_explicit": fwd["pv_explicit"], "pv_terminal": fwd["pv_terminal"],
                "terminal_share_of_ev": fwd["terminal_share_of_ev"],
                "check_equity_value": fwd["equity_value"]})
    return out
