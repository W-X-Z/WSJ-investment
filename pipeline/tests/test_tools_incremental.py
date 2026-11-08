"""증분 수요 엔진 — 손계산 예제 + 8GW 예제(연구 스크래치 deep4/model.py 결과와 숫자 일치)."""

import json
from pathlib import Path

import pytest

from wsj.tools import incremental as I
from wsj.tools.context import ToolError

FIXTURE = Path(__file__).parent / "fixtures" / "tools" / "incremental_8gw.json"

TOY = {
    "scenarios": {"base": {"A": 10}, "event": {"B": 10}},
    "mixes": {"B": {"A": 1, "boost": 0.5}},
    "unit_costs": {"xfmr": {"A": 2.0, "boost": 4.0}, "cable": {"A": 1.0}},
    "suppliers": {"xfmr": {"X": 0.5, "Y": 0.25}, "cable": {"Y": 0.5}},
    "companies": {"X": {"margin": 0.2, "mcap": 10.0}, "Y": {"margin": 0.1, "mcap": 5.0}},
    "tax": 0.25,
}


def test_toy_by_hand():
    r = I.evaluate(TOY)
    comp = {c["component"]: c for c in r["components"]}
    # event: A=10, boost=5 → xfmr 10*2 + 5*4 = 40 (base 20) ; cable 10 → 10 (base 10)
    assert comp["xfmr"]["delta"] == 20.0 and comp["cable"]["delta"] == 0.0
    assert r["totals"] == {"base": 30.0, "event": 50.0, "delta": 20.0}
    co = {c["company"]: c for c in r["companies"]}
    assert co["X"]["d_revenue"] == 10.0 and co["X"]["d_net_income"] == pytest.approx(10 * 0.2 * 0.75)
    assert co["X"]["d_ni_over_mcap_pct"] == pytest.approx(15.0)
    assert co["Y"]["d_revenue"] == 5.0 and co["Y"]["d_ni_over_mcap_pct"] == pytest.approx(7.5)
    assert [c["company"] for c in r["companies"]] == ["X", "Y"]          # Δ/시총 내림차순


def test_overrides_replace_node_and_do_not_mutate():
    s = I.apply_overrides(TOY, {"scenarios.event.B": 20, "companies.Z": {"margin": 0.1, "mcap": 1}})
    assert s["scenarios"]["event"]["B"] == 20 and TOY["scenarios"]["event"]["B"] == 10
    assert "Z" in s["companies"] and "Z" not in TOY["companies"]


def test_mix_cycle_and_missing_inputs():
    bad = dict(TOY, mixes={"B": {"C": 1}, "C": {"B": 1}})
    with pytest.raises(ToolError):
        I.evaluate(bad)
    with pytest.raises(ToolError):
        I.evaluate({k: v for k, v in TOY.items() if k != "suppliers"})
    with pytest.raises(ToolError):
        I.evaluate(dict(TOY, scenarios={"base": {"A": 1}}))


def test_unknown_company_gives_null_not_number():
    spec = I.apply_overrides(TOY, {"suppliers.cable": {"Y": 0.5, "Q": 0.2}})
    r = I.evaluate(spec)
    q = next(c for c in r["companies"] if c["company"] == "Q")
    assert q["d_net_income"] is None and q["d_ni_over_mcap_pct"] is None
    assert any("'Q'" in w for w in r["warnings"])
    assert r["companies"][-1]["company"] == "Q"                            # null 은 맨 뒤


def test_run_sensitivity_table_and_case_filter():
    spec = dict(TOY, sensitivities={"double": {"scenarios.event.B": 20}})
    out = I.run(spec)
    assert list(out["cases"]) == ["central", "double"]
    row = next(r for r in out["sensitivity_table"]["rows"] if r["company"] == "X")
    assert row["central"] == pytest.approx(15.0) and row["double"] == pytest.approx(45.0)  # (20*2+10*4 − 20)=60 → 30 rev
    only = I.run(spec, cases=["double"])
    assert list(only["cases"]) == ["double"]
    with pytest.raises(ToolError):
        I.run(spec, cases=["nope"])


# ---------------------------------------------------------------- 8GW 예제 = model.py
# 기대값: deep4/model.py (2026-11-06 연구 스크래치) 를 그대로 돌린 결과. Δ순이익 ÷ 시총, %.
MODEL_PY = {
    "central": (-51.1291, {"FPS": -0.9108291891891891, "ETN": -0.37711258660508085, "BE": -0.3012689938398357,
                           "INIO": -0.25801941176470594, "MYRG": 0.039278139534883696}),
    "tx_btm_heavy": (-56.4036, {"FPS": -0.9711210810810812, "ETN": -0.38784584295612007, "BE": -0.3012689938398357,
                                "INIO": -0.8750223529411763, "MYRG": 0.09514790697674422}),
    "dest_grid": (-49.8948, {"FPS": -0.8654416216216216, "ETN": -0.355597286374134, "BE": -0.41082135523613955,
                             "INIO": -0.3814200000000001, "MYRG": 0.05620837209302322}),
    "dest_selfsupply": (-45.73539999999999, {"FPS": -0.8385000000000001, "ETN": -0.3508010969976905,
                                             "BE": -0.15519917864476385, "INIO": -0.11218235294117647,
                                             "MYRG": 0.021670697674418538}),
    "low_reloc": (-95.7011875, {"FPS": -1.721046283783784, "ETN": -0.7178404662240184, "BE": -0.37658624229979465,
                                "INIO": -0.6240143382352944, "MYRG": -0.019893023255813998}),
}


def test_8gw_fixture_reproduces_model_py():
    spec = json.loads(FIXTURE.read_text())
    out = I.run(spec)
    assert list(out["cases"]) == list(MODEL_PY)
    for case, (total, pcts) in MODEL_PY.items():
        r = out["cases"][case]
        assert r["totals"]["delta"] == pytest.approx(total, abs=1e-9), case
        assert len(r["companies"]) == 46 and r["warnings"] == []
        got = {c["company"]: c["d_ni_over_mcap_pct"] for c in r["companies"]}
        for co, want in pcts.items():
            assert got[co] == pytest.approx(want, abs=1e-12), (case, co)
    comp = {c["component"]: c["delta"] for c in out["cases"]["central"]["components"]}
    assert comp["turbine"] == pytest.approx(-2.88) and comp["net_upgrade"] == pytest.approx(0.348)
    assert comp["towers"] == pytest.approx(-0.70)


def test_8gw_cli_top(capsys):
    from wsj.runner import main

    assert main(["tools", "incremental", str(FIXTURE), "--case", "central", "--top", "3", "--compact"]) == 0
    out = json.loads(capsys.readouterr().out)
    rows = out["cases"]["central"]["companies"]
    assert [r["company"] for r in rows] == ["MYRG", "TAIHAN", "PWR"] and len(out["sensitivity_table"]["rows"]) == 3
