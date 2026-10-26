import json

from wsj.briefs.moat import ontology_context, render_context
from wsj.ecosystems import discover, promote
from wsj.ecosystems.impact import DEFAULT_GRAPH
from wsj.ecosystems.ontology import load_ontology, validate


def graph():
    return json.loads(DEFAULT_GRAPH.read_text(encoding="utf-8"))


def test_size_bands():
    assert discover.size_band(None) == "unknown"
    assert discover.size_band(50e6) == "micro" and discover.size_band(1.9e9) == "small"
    assert discover.size_band(5e9) == "mid" and discover.size_band(5e10) == "large"


def test_discovery_queries_reference_graph_nodes():
    ids = {n["id"] for n in graph()["nodes"]}
    missing = [k for k in discover.QUERIES if k not in ids]
    assert missing == []


def test_promote_is_idempotent_and_valid():
    g = graph()
    before = (len(g["nodes"]), len(g["edges"]))
    disc = {
        "as_of": "2026-10-27",
        "companies": [
            {
                "ticker": "LWLG",
                "cik": 1325964,
                "name": "LIGHTWAVE LOGIC, INC.",
                "public_float": 155e6,
                "exchange": "Nasdaq",
                "sic": 3080,
                "score": 2.0,
                "filings": [["10-K", "2026-03-01", "0000000000-26-000001"]],
            },
        ],
    }
    g2, added = promote.promote(g, disc)
    assert added == [] and (len(g2["nodes"]), len(g2["edges"])) == before  # 이미 승격됨
    assert validate(g2, load_ontology()).ok
    lwlg = next(n for n in g2["nodes"] if n["id"] == "company:lwlg")
    assert lwlg["in_universe"] and lwlg["listing"]["cik"] == 1325964 and lwlg["size_band"] == "micro"


def test_promoted_edges_are_inference_tier_with_filing_source():
    g = graph()
    edges = [e for e in g["edges"] if e["to"] == "company:adea"]
    assert edges and all(
        e["evidence_tier"] == "technical_inference" and "sec.gov/Archives" in e["evidence"][0]["url"]
        for e in edges
    )


def test_moat_context_lists_position_peers_threats_and_timing():
    g = graph()
    ctx = ontology_context(g, 1325964)  # LWLG
    assert ctx and ctx["positions"][0]["node_id"] == "component:modulator"
    assert any("1.6T" in u or "1.6 Tb" in u for u in ctx["positions"][0]["upstream_demand"])
    ctx2 = ontology_context(g, 1040470)  # AEHR → product 노드 경유
    assert ctx2 and ctx2["positions"] and ctx2["ecosystem_events"]
    md = render_context(ctx2)
    assert "위치:" in md and "생태계 이벤트" in md
    assert ontology_context(g, 999999999) is None
