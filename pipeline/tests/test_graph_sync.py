"""그래프 조회본 (ADR-0031) — 행 만들기·어휘·제안 정리, v0.5 칸 검증, 제안 → 패치."""

from wsj.ecosystems import graph_sync as G
from wsj.ecosystems.ontology import load_graph, load_ontology, validate


def test_rows_cover_graph_and_carry_direction():
    g, o = load_graph(), load_ontology()
    nodes, edges = G.node_rows(g, "abc"), G.edge_rows(g, o, "abc")
    assert len(nodes) == len(g["nodes"]) and len(edges) == len(g["edges"])
    off = next(e for e in edges if e["relation"] == "offered_by")
    assert off["direction"] == "demand_to_supply" and off["src"] and off["dst"]
    mu = next(n for n in nodes if n["id"] == "company:mu")
    assert mu["ticker"] == "MU" and mu["name"] == "Micron" and mu["status"] == "active"


def test_terms_mark_short_names_case_sensitive():
    terms = {(t["term"], t["node_id"]): t for t in G.term_rows(load_graph())}
    on = terms.get(("on", "company:on"))
    assert on and on["case_sensitive"] and on["raw"] == "ON"          # 'on' 은 영어 낱말 — 대문자 티커일 때만
    assert any(t["node_id"] == "tech:hybrid_bond" and not t["case_sensitive"] for t in terms.values())


class _Store:
    def __init__(self, pend):
        self.pend, self.up = pend, []

    def select(self, table, cols=None, filters=None, limit=None, order=None):
        return self.pend

    def upsert(self, table, rows, key):
        self.up += rows
        return len(rows)


def test_reconcile_marks_proposals_already_in_graph():
    g = load_graph()
    e = next(x for x in g["edges"] if x["relation"] == "offered_by")
    pend = [{"proposal_id": 1, "kind": "edge", "payload": {"from": e["from"], "relation": "offered_by", "to": e["to"]}},
            {"proposal_id": 2, "kind": "edge", "payload": {"from": e["from"], "relation": "offered_by", "to": e["to"], "exposure_pct": 99}},
            {"proposal_id": 3, "kind": "node", "payload": {"id": "component:not_there"}}]
    st = _Store(pend)
    assert G.reconcile_proposals(st, g) == 1 and st.up[0]["proposal_id"] == 1     # 숫자가 아직 안 들어간 제안은 대기


def test_v05_fields_are_checked():
    g, o = load_graph(), load_ontology()
    g = {**g, "nodes": [dict(n) for n in g["nodes"]], "edges": [dict(e) for e in g["edges"]]}
    n = next(x for x in g["nodes"] if x["id"] == "tech:hybrid_bond")
    n.update({"codes": {"cpc": ["H01L24/80"]}, "status": "active", "first_evidence": {"date": "2019-06-01", "url": "https://x.test", "layer": "conference"}})
    e = next(x for x in g["edges"] if x["relation"] == "offered_by")
    e.update({"exposure_pct": 45, "exposure_year": 2025, "exposure_source": "https://ir.test"})
    assert validate(g, o).ok
    n["codes"] = {"isbn": ["x"]}
    e["exposure_pct"] = 145
    errs = validate(g, o).errors
    assert any("codes 키" in x for x in errs) and any("exposure_pct" in x for x in errs)


def test_rule_nodes_and_mandates():
    g, o = load_graph(), load_ontology()
    g = {**g, "nodes": list(g["nodes"]), "edges": list(g["edges"])}
    req = next(x for x in g["nodes"] if x["kind"] == "requirement")
    g["nodes"] += [{"id": "rule:ercot_nogrr282", "kind": "rule", "label": "ERCOT NOGRR282", "ecosystem": "power"},
                   {"id": "authority:ercot", "kind": "authority", "label": "ERCOT", "ecosystem": "power"}]
    ev = [{"url": "https://www.ercot.com/mktrules/issues/NOGRR282", "source_type": "standard_body"}]
    g["edges"] += [{"id": "t-1", "from": "rule:ercot_nogrr282", "to": req["id"], "relation": "mandates", "evidence_tier": "standard_body",
                    "polarity": "positive", "evidence": ev, "effective_date": "2026-12-01"},
                   {"id": "t-2", "from": "rule:ercot_nogrr282", "to": "authority:ercot", "relation": "issued_by", "evidence_tier": "standard_body",
                    "polarity": "positive", "evidence": ev}]
    assert validate(g, o).ok


def test_proposals_to_patch():
    from wsj.ecosystems.graph_patches.from_json import parse, parse_node_updates
    from wsj.ecosystems.graph_patches.from_proposals import to_patch

    doc = to_patch([
        {"proposal_id": 7, "kind": "edge", "payload": {"from": "component:mlb_pcb", "relation": "offered_by", "to": "company:isu_petasys",
                                                      "tier": "official_issuer", "exposure_pct": 45, "exposure_year": 2025,
                                                      "evidence": [{"url": "https://ir.test", "source_type": "official_issuer"}]}},
        {"proposal_id": 8, "kind": "node_update", "payload": {"id": "tech:hybrid_bond", "codes": {"cpc": ["H01L24/80"]}}},
        {"proposal_id": 9, "kind": "alias", "payload": {"id": "tech:hybrid_bond", "aliases": ["하이브리드본딩"]}}], "p1103")
    nodes, edges, prefix, aliases, _ = parse(doc)
    assert edges[0].attrs["exposure_pct"] == 45 and prefix == "p1103" and aliases["tech:hybrid_bond"] == ["하이브리드본딩"]
    assert parse_node_updates(doc)[0]["codes"] == {"cpc": ["H01L24/80"]} and doc["proposal_ids"] == [7, 8, 9]


def test_node_updates_merge_codes_and_keep_maturity_history():
    from wsj.ecosystems.graph_patches import update_nodes

    g = {"nodes": [{"id": "tech:x", "kind": "technology", "label": "X", "ecosystem": "hbm", "codes": {"cpc": ["A"]},
                    "maturity": {"stage": "early", "as_of": "2025-01-01", "evidence_url": "https://a.test", "evidence_tier": "standard_body"},
                    "first_evidence": {"date": "2024-05-01", "url": "https://old.test", "layer": "paper"}}], "edges": []}
    n = update_nodes(g, [{"id": "tech:x", "codes": {"cpc": ["A", "B"], "jesd": ["JESD1"]},
                          "maturity": {"stage": "near", "as_of": "2026-06-01", "evidence_url": "https://b.test", "evidence_tier": "standard_body"},
                          "first_evidence": {"date": "2025-01-01", "url": "https://late.test", "layer": "press"}},
                         {"id": "tech:missing", "status": "active"}])
    x = g["nodes"][0]
    assert n == 1 and x["codes"] == {"cpc": ["A", "B"], "jesd": ["JESD1"]}
    assert x["maturity"]["stage"] == "near" and x["maturity_history"][0]["stage"] == "early"
    assert x["first_evidence"]["url"] == "https://old.test"          # 더 이른 날짜만 바꾼다
