"""deep: 라벨 맞추기·주가 이슈·재무·밸류에이션·시나리오·저장 (네트워크 없음)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from wsj.deep import diff as D
from wsj.deep import fin as FN
from wsj.deep import scenario as S
from wsj.deep import store as ST
from wsj.deep import story as STY
from wsj.deep import valuation as V
from wsj.deep.cards import prior_labels
from wsj.tools.context import ToolError


def test_align_matches_similar_labels_across_years():
    new = {"empty": False, "items": [{"label": "수직 계열화", "value": None}, {"label": "원재료 가격 연동", "value": "일부"}]}
    old = {"empty": False, "items": [{"label": "수직계열화 제조", "value": None}, {"label": "원재료가격연동", "value": None},
                                     {"label": "PO 기반 구매", "value": None}]}
    d = D.slot_diff(new, old)
    assert "added" not in d
    assert [r["label"] for r in d["removed"]] == ["PO 기반 구매"]
    assert d["changed"] == [{"label": "원재료 가격 연동", "from": None, "to": "일부", "detail": None}]


def test_prior_labels_block():
    card = {"orders": {"items": [{"label": "백로그 공시"}, {"label": "선수금"}]}, "customers": {"items": []}}
    txt = prior_labels(card)
    assert txt.startswith("[이전 해 라벨]") and "- orders: 백로그 공시, 선수금" in txt and "customers" not in txt
    assert prior_labels(None) == ""


def _bars(n: int, jumps: dict[int, float], vol_spike: dict[int, float] | None = None) -> list[dict[str, Any]]:
    out, px, d = [], 100.0, date(2026, 1, 2)
    for i in range(n):
        px *= 1 + jumps.get(i, 0.001)
        out.append({"date": (d + timedelta(days=i)).isoformat(), "close": round(px, 4),
                    "volume": 1000 * (vol_spike or {}).get(i, 1.0)})
    return out


def test_pick_moves_ranks_excess_moves_and_merges_neighbors():
    bars = _bars(80, {30: 0.15, 31: 0.06, 60: -0.2, 45: 0.02}, {45: 4.0})
    bench = _bars(80, {})
    moves = STY.pick_moves(bars, bench, top=5)
    days = [m["date"] for m in moves]
    assert bars[30]["date"] in days and bars[31]["date"] not in days    # 이웃한 날은 하나로
    assert bars[60]["date"] in days and bars[45]["date"] in days         # 거래량 급증일도 들어간다
    assert [m["n"] for m in moves] == list(range(1, len(moves) + 1)) and days == sorted(days)
    STY.attach_filings(moves, [{"form": "8-K", "file_date": bars[60]["date"], "items": ["2.02"], "url": "u"}])
    assert next(m for m in moves if m["date"] == bars[60]["date"])["filings"][0]["form"] == "8-K"


def _cf() -> dict[str, Any]:
    def dur(vals: dict[str, float]):
        return [{"start": f"{int(y) - 1}-07-01", "end": f"{y}-06-30", "val": v, "filed": f"{y}-09-15", "form": "10-K"}
                for y, v in vals.items()]

    def inst(vals: dict[str, float]):
        return [{"end": f"{y}-06-30", "val": v, "filed": f"{y}-09-15", "form": "10-K"} for y, v in vals.items()]

    g = {
        "Revenues": {"units": {"USD": dur({"2024": 500, "2025": 750, "2026": 1420})}},
        "GrossProfit": {"units": {"USD": dur({"2024": 150, "2025": 230, "2026": 450})}},
        "OperatingIncomeLoss": {"units": {"USD": dur({"2024": 40, "2025": 72, "2026": 183})}},
        "NetIncomeLoss": {"units": {"USD": dur({"2024": 20, "2025": 40, "2026": 90})}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": dur({"2024": 30, "2025": 50, "2026": 120})}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": dur({"2024": 20, "2025": 60, "2026": 110})}},
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": inst({"2024": 50, "2025": 60, "2026": 100})}},
        "LongTermDebtNoncurrent": {"units": {"USD": inst({"2024": 400, "2025": 450, "2026": 580})}},
        "StockholdersEquity": {"units": {"USD": inst({"2024": 300, "2025": 350, "2026": 800})}},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": dur({"2024": 100, "2025": 100, "2026": 112})}},
    }
    return {"facts": {"us-gaap": g}}


def test_us_financials_annual_ttm_and_anomalies():
    f = FN.us_financials(_cf(), years=5)
    a = f["annual"]
    assert [r["period_end"] for r in a] == ["2024-06-30", "2025-06-30", "2026-06-30"]
    last = a[-1]
    assert last["revenue_yoy_pct"] == pytest.approx(89.3, abs=0.1)
    assert last["fcf"] == 10 and last["net_debt"] == 480 and last["op_margin_pct"] == pytest.approx(12.9, abs=0.1)
    assert last["roic_pct"] == pytest.approx(100 * 183 * 0.79 / (800 + 580), abs=0.1)
    assert last["diluted_shares_yoy_pct"] == 12.0
    assert f["ttm"]["basis"] == "fiscal_year" and f["ttm"]["revenue"] == 1420   # 분기 자료가 없으면 마지막 회계연도
    metrics = {(x["period"], x["metric"]) for x in f["anomalies"]}
    assert ("2026-06-30", "diluted_shares_yoy_pct") in metrics
    assert ("2026-06-30", "revenue_yoy_pct") in metrics   # 50% → 89%


def test_current_multiples_and_reverse_dcf_fallback():
    ttm = {"revenue": 1420e6, "op_income": 183e6, "net_income": 90e6, "fcf": -7e6, "net_debt": 480e6}
    m = V.current_multiples(6.8e9, ttm)
    assert m["price_sales"] == pytest.approx(4.79, abs=0.01) and m["ev_ebit"] == pytest.approx(39.78, abs=0.01)
    assert m["p_fcf"] is None
    r = V.implied(6.8e9, ttm)
    assert r["basis"] == "nopat_proxy" and r["implied_cagr_pct"] is not None
    assert "음수" in V.implied(1e9, {"fcf": -1, "op_income": -5})["note"]


def test_scenario_cases_and_required_earnings():
    spec = {"symbol": "FPS", "price": 25.0, "shares": 300e6, "net_debt": 500e6, "basis": "FY2028",
            "cases": {"bear": {"revenue": 3.0e9, "margin_pct": 20, "metric": "ebitda", "multiple": 10},
                      "base": {"revenue": 3.6e9, "margin_pct": 25, "metric": "ebitda", "multiple": 15},
                      "bull": {"eps": 2.6, "multiple": 30, "multiple_type": "pe"}}}
    out = S.run(spec)
    base = out["cases"]["base"]
    assert base["earnings"] == pytest.approx(900e6) and base["equity_value"] == pytest.approx(900e6 * 15 - 500e6)
    assert base["vs_price_x"] == round((900e6 * 15 - 500e6) / 300e6 / 25, 2)
    assert out["cases"]["bull"]["value_per_share"] == pytest.approx(78.0)
    need2 = out["to_reach_at_base_multiple"]["2x"]
    assert need2["earnings_needed"] == pytest.approx((50 * 300e6 + 500e6) / 15)
    assert need2["revenue_needed_at_base_margin"] == pytest.approx(need2["earnings_needed"] / 0.25)
    with pytest.raises(ToolError):
        S.run({"price": 1, "shares": 1, "cases": {"x": {"revenue": 1, "margin_pct": 1, "multiple": 1, "multiple_type": "zz"}}})


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def rpc(self, fn: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((fn, args))
        if fn == "ideas.put_research_sources":
            return {"ok": len(args["rows"]), "rejected": [], "ids": [{"i": i + 1, "clue_id": 900 + i} for i in range(len(args["rows"]))]}
        return {"ok": 1, "rejected": []}


def _spec() -> dict[str, Any]:
    return {"symbol": "FPS", "market": "us", "as_of": "2026-11-10", "title": "Forgent — 백로그 대비 수급 할인", "stars": 3,
            "verdict": "수급 할인이 과도하다", "sections": {"summary": "s", "conclusion": "c", "risks": "r", "extra_note": "x"},
            "sources": [{"url": "https://www.sec.gov/a.htm", "title": "10-K", "published_at": "2026-09-15"}]}


def test_store_saves_sources_then_idea_report():
    st = FakeStore()
    res = ST.save(st, _spec())
    assert [c[0] for c in st.calls] == ["ideas.put_research_sources", "research.put_reports"]
    row = st.calls[1][1]["rows"][0]
    assert row["report_id"] == "idea:us:fps:2026-11-10" and row["kind"] == "idea" and row["cites"] == [900]
    assert list(row["body"]["sections"]) == ["summary", "conclusion", "risks", "extra_note"]
    assert res["cites"] == [900]


def test_store_validate_rejects_missing_conclusion_and_bad_stars():
    bad = _spec() | {"stars": 7, "sections": {"summary": "s"}}
    errs = ST.validate(bad)
    assert any("stars" in e for e in errs) and any("conclusion" in e for e in errs)
    with pytest.raises(ST.ReportError):
        ST.save(FakeStore(), bad)
