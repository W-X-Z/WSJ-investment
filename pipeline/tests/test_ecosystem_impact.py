import json
from copy import deepcopy

import pytest

from wsj.ecosystems import migrate_v03
from wsj.ecosystems.impact import (
    DEFAULT_GRAPH,
    _public_by,
    displacement_scenarios,
    event_fingerprint,
    impact_report,
    influence_paths,
    possible_watch_matches,
    replay,
    validate_graph,
)
from wsj.ecosystems.ontology import edge_confidence, load_ontology, validate


def graph():
    return json.loads(DEFAULT_GRAPH.read_text(encoding="utf-8"))


def by_company(paths, cid):
    return [p for p in paths if p["company_id"] == cid]


# ---------------------------------------------------------------- 온톨로지 검증
def test_seed_conforms_to_closed_vocabulary():
    g = graph()
    rep = validate(g, load_ontology())
    assert rep.ok, rep.errors
    assert g["schema_version"] == "0.3"
    assert sum(x["kind"] == "ecosystem" for x in g["nodes"]) == 3
    assert {x["kind"] for x in g["nodes"]} >= {
        "product_generation",
        "standard",
        "product",
        "company",
        "equipment",
    }
    assert all(n.get("ecosystem") for n in g["nodes"] if n["kind"] != "ecosystem")
    assert all(n.get("role") and n.get("listing") for n in g["nodes"] if n["kind"] == "company")


def test_products_are_separated_from_generic_technologies():
    g = graph()
    ids = {n["id"] for n in g["nodes"]}
    assert "tech:hawk" not in ids and "product:camt_hawk" in ids and "tech:optical_interposer" in ids
    rels = {(e["from"], e["relation"], e["to"]) for e in g["edges"]}
    assert ("product:camt_hawk", "implements", "process:microbump_metrology") in rels
    assert ("product:camt_hawk", "offered_by", "company:camt") in rels


def test_migration_is_idempotent():
    g = graph()
    assert migrate_v03.migrate(deepcopy(g)) == g


def test_validator_rejects_domain_range_and_tier_violations():
    onto = load_ontology()
    g = graph()
    g["edges"][0]["relation"] = "supplied_to"  # ecosystem → requirement 는 supplied_to 정의역 밖
    assert any("domain/range" in e for e in validate(g, onto).errors)
    g = graph()
    e = next(x for x in g["edges"] if x["relation"] == "qualifying_with")
    e["relation"], e["evidence_tier"] = "supplied_to", "hypothesis"
    assert any("needs tier" in err for err in validate(g, onto).errors)
    g = graph()
    g["edges"][0]["evidence"] = []
    with pytest.raises(ValueError, match="no evidence"):
        validate_graph(g)
    g = graph()
    g["edges"][0]["to"] = "company:does_not_exist"
    with pytest.raises(ValueError, match="dangling"):
        validate_graph(g)


def test_confidence_follows_evidence_tier_and_polarity():
    onto = load_ontology()
    base = {
        "evidence_tier": "official_issuer",
        "polarity": "positive",
        "evidence": [{"url": "https://a.test/x"}],
    }
    assert edge_confidence(base, onto) == 0.8
    assert edge_confidence({**base, "polarity": "conditional"}, onto) == 0.64
    two = {**base, "evidence": [{"url": "https://a.test/x"}, {"url": "https://b.test/y"}]}
    assert edge_confidence(two, onto) == 0.825
    assert edge_confidence({**base, "evidence_tier": "hypothesis"}, onto) == 0.25


# ---------------------------------------------------------------- 영향 전파
def test_hbm4_reaches_inspection_vendors_only_as_inferred_and_memory_makers_as_documented():
    paths = influence_paths(graph(), "gen:hbm4")
    camt = by_company(paths, "company:camt")
    assert camt and all(p["band"] == "inferred" and p["sign"] == 1 for p in camt)
    assert all("NOT proven" in p["warning"] for p in camt)
    mu = by_company(paths, "company:mu")
    assert mu and mu[0]["band"] == "documented" and mu[0]["relations"] == ["offered_by"]
    assert all(
        p["company_id"] not in ("company:poet", "company:nvts") for p in paths
    )  # 다른 생태계로 새지 않음


def test_negative_polarity_flips_sign_and_customer_deferral_is_visible():
    report = impact_report(graph(), "tech:hybrid_bond")
    companies = {c["company_id"]: c for c in report["companies"]}
    assert companies["company:skhynix"]["direction"] == "negative"  # defers
    assert companies["company:skhynix"]["best_path"]["role_on_path"] == "adopter"
    assert companies["company:besi"]["direction"] == "positive"
    assert any(s["relation"] == "displaces" for s in report["substitution_risks"])


def test_customer_to_supplier_hop_is_scoped_by_program():
    cpo = {c["company_id"] for c in impact_report(graph(), "tech:cpo")["companies"]}
    assert {"company:nvda", "company:cohr", "company:lite", "company:fn"} <= cpo
    assert "company:nvts" not in cpo  # 800VDC 파트너는 CPO 경로로 닿지 않는다
    power = {c["company_id"] for c in impact_report(graph(), "gen:800vdc")["companies"]}
    # Coherent 는 SiC 기판 공급사로 800VDC 에도 닿는다 (2026-10-27 확장). 광 전용 기업은 닿지 않는다.
    assert {"company:nvts", "company:vrt", "company:etn", "company:cohr"} <= power and "company:lite" not in power


def test_paths_report_weakest_link_and_listing():
    paths = influence_paths(graph(), "req:800v")
    aehr = by_company(paths, "company:aehr")
    assert aehr and aehr[0]["band"] == "inferred" and aehr[0]["listing"]["cik"] == 1040470
    assert aehr[0]["weakest_edge"]["confidence"] <= min(0.55, aehr[0]["confidence"] + 0.5)
    assert aehr[0]["in_universe"] is True  # promote 로 유니버스 편입


def test_optics_reaches_poet_not_unrelated_camtek():
    paths = influence_paths(graph(), "req:1p6t")
    assert any(p["company_id"] == "company:poet" for p in paths)
    assert all(p["company_id"] != "company:camt" for p in paths)


# ---------------------------------------------------------------- 이벤트·리플레이
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
    later = replay(graph(), "2026-08-31")
    hb = next(x for x in later["events"] if x["event_id"] == "obs:hotchips_hb_202608")
    assert any(
        c["company_id"] == "company:skhynix" and c["direction"] == "negative" for c in hb["company_impacts"]
    )


def test_replay_source_fingerprint_is_stable_and_deduplicated():
    g = graph()
    e = g["events"][0]
    assert event_fingerprint(e) == event_fingerprint(deepcopy(e))
    g["events"].append(deepcopy(e))
    assert len(replay(g, "2026-10-26")["events"]) == len(graph()["events"])


def test_candidate_watch_does_not_trigger_investment_alert():
    g = graph()
    hb = next(x for x in g["events"] if x["id"] == "obs:hotchips_hb_202608")
    matches = possible_watch_matches(hb, g)
    assert {x["watch"] for x in matches} == {"watch:hbm_displacement", "watch:hbm_bonding_roadmap"}
    assert all(m["status"] == "candidate_requires_rule_and_source_review" for m in matches)


def test_substitutes_are_scenarios_not_assumed_negative_sales():
    scenarios = displacement_scenarios(graph(), "req:800v")
    assert any(
        s["technology"].startswith("중전압 AC") or s["alternative"].startswith("중전압 AC") for s in scenarios
    )
    assert all(s["status"] == "competing_technology_scenario_only" for s in scenarios)
    assert all("NOT established" in s["warning"] for s in scenarios)
