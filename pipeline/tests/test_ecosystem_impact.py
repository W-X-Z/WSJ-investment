import json
from copy import deepcopy

import pytest

from wsj.ecosystems.impact import (
    DEFAULT_GRAPH,
    _public_by,
    event_fingerprint,
    influence_paths,
    displacement_scenarios,
    possible_watch_matches,
    replay,
    validate_graph,
)


def graph():
    return json.loads(DEFAULT_GRAPH.read_text(encoding="utf-8"))


def test_seed_has_three_ecosystems_and_nine_watches():
    g = graph()
    validate_graph(g)
    assert sum(x["kind"] == "ecosystem" for x in g["nodes"]) == 3
    assert len(g["watches"]) == 9
    assert len(g["edges"]) >= 30


def test_hbm_requirement_reaches_camtek_but_only_as_hypothesis():
    paths = influence_paths(graph(), "req:hbm_io")
    camt = [p for p in paths if p["company_id"] == "company:camt"]
    assert camt and all(p["confidence"] == "requires_validation" for p in camt)
    assert all("NOT proven" in p["warning"] for p in camt)


def test_optics_reaches_poet_not_unrelated_camtek():
    paths = influence_paths(graph(), "req:1p6t")
    assert any(p["company_id"] == "company:poet" for p in paths)
    assert all(p["company_id"] != "company:camt" for p in paths)


def test_800v_does_not_claim_confirmed_sic_beneficiary():
    paths = influence_paths(graph(), "req:800v")
    aehr = [p for p in paths if p["company_id"] == "company:aehr"]
    assert aehr
    assert all(p["confidence"] == "requires_validation" for p in aehr)
    assert all("revenue" in p["warning"] for p in aehr)


def test_unknown_and_month_precision_are_conservative():
    events = {x["id"]: x for x in graph()["events"]}
    assert not _public_by(events["obs:ocp_202609"], "2026-09-01")
    assert _public_by(events["obs:ocp_202609"], "2026-09-30")
    assert not _public_by(events["obs:ieee_202610"], "2026-10-25")
    assert _public_by(events["obs:ieee_202610"], "2026-10-26")


def test_replay_cannot_include_events_after_cutoff():
    result = replay(graph(), "2024-12-31")
    assert [x["event_id"] for x in result["events"]] == ["obs:camt_202411"]
    assert result["research_only"]
    assert "NO point-in-time alpha" in result["warnings"][0]


def test_replay_source_fingerprint_is_stable_and_deduplicated():
    g = graph()
    e = g["events"][0]
    assert event_fingerprint(e) == event_fingerprint(deepcopy(e))
    g["events"].append(deepcopy(e))
    result = replay(g, "2026-10-26")
    assert len(result["events"]) == len(graph()["events"])


def test_candidate_watch_does_not_trigger_investment_alert():
    g = graph()
    matches = possible_watch_matches(g["events"][0], g)
    assert [x["watch"] for x in matches] == ["watch:hbm_orders"]
    assert matches[0]["status"] == "candidate_requires_rule_and_source_review"


def test_rejects_unsourced_edge():
    g = graph()
    g["edges"][0]["evidence"] = []
    with pytest.raises(ValueError, match="without HTTPS provenance"):
        validate_graph(g)


def test_rejects_unknown_relation_and_dangling_node():
    g = graph()
    g["edges"][0]["relation"] = "guarantees_10x"
    with pytest.raises(ValueError, match="Unknown edge"):
        validate_graph(g)
    g = graph()
    g["edges"][0]["to"] = "company:does_not_exist"
    with pytest.raises(ValueError, match="Dangling edge"):
        validate_graph(g)


def test_substitutes_are_scenarios_not_assumed_negative_sales():
    g = graph()
    scenarios = displacement_scenarios(g, "req:800v")
    assert any(s["technology"].startswith("중전압 AC") for s in scenarios)
    assert all(s["status"] == "competing_technology_scenario_only" for s in scenarios)
    assert all("NOT established" in s["warning"] for s in scenarios)
