"""JSON 그래프 패치 (ADR-0027) — 매일 발굴 작업이 소형 공급사를 그래프에 넣는 길."""

import pytest

from wsj.ecosystems.graph_patches import from_json


def _doc(**over):
    doc = {
        "prefix": "dtest",
        "nodes": [{"id": "company:zz_test_small", "kind": "company", "label": "ZZ Test (KOSDAQ 999999)", "ecosystem": "hbm",
                   "ticker": "999999", "exchange": "KOSDAQ", "size_band": "small"}],
        "edges": [{"from": "component:mlb_pcb", "relation": "offered_by", "to": "company:zz_test_small", "tier": "third_party_report",
                   "evidence": [{"url": "https://example.com/a", "source_type": "third_party_report", "published_at": "2026-10-30", "excerpt": "x"}]}],
        "aliases": {"company:zz_test_small": ["지지테스트"]},
    }
    doc.update(over)
    return doc


def test_parse_valid_patch():
    nodes, edges, prefix, aliases, native = from_json.parse(_doc())
    assert prefix == "dtest" and len(nodes) == 1 and len(edges) == 1
    assert nodes[0].extra["listing"]["exchange"] == "KOSDAQ" and nodes[0].extra["size_band"] == "small"
    assert aliases["company:zz_test_small"] == ["지지테스트"] and native == {}


@pytest.mark.parametrize("bad", [
    {"prefix": "1bad"},
    {"edges": [{"from": "component:mlb_pcb", "relation": "offered_by", "to": "company:zz_test_small", "tier": "third_party_report", "evidence": []}]},
    {"edges": [{"from": "component:mlb_pcb", "relation": "offered_by", "to": "company:zz_test_small", "tier": "third_party_report",
                "evidence": [{"url": "http://insecure", "source_type": "third_party_report"}]}]},
    {"nodes": [{"id": "company:zz_unlisted", "kind": "company", "label": "Private", "ecosystem": "hbm", "size_band": "small"}]},
    {"nodes": [{"id": "company:zz_band", "kind": "company", "label": "X", "ecosystem": "hbm", "ticker": "1", "exchange": "KRX", "size_band": "tiny"}]},
])
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        from_json.parse(_doc(**bad))


def test_dry_run_validates_against_graph(tmp_path, capsys):
    import json

    p = tmp_path / "x.json"
    p.write_text(json.dumps(_doc()), encoding="utf-8")
    assert from_json.apply_file(p, dry_run=True) == 0
    assert '"nodes_added": 1' in capsys.readouterr().out
    bad = _doc(edges=[{"from": "component:does_not_exist", "relation": "offered_by", "to": "company:zz_test_small", "tier": "third_party_report",
                       "evidence": [{"url": "https://example.com/a", "source_type": "third_party_report"}]}])
    p.write_text(json.dumps(bad), encoding="utf-8")
    assert from_json.apply_file(p, dry_run=True) == 1


def _annotate(attrs, rel="offered_by", frm="component:mlb_pcb", to="company:isu_petasys"):
    return {"prefix": "dtest", "nodes": [], "edges": [dict(frm_to(frm, rel, to), tier="third_party_report", **attrs,
            evidence=[{"url": "https://example.com/exposure", "source_type": "third_party_report", "published_at": "2026-10-30"}])]}


def frm_to(frm, rel, to):
    return {"from": frm, "relation": rel, "to": to}


def test_annotates_existing_supplier_edge(tmp_path, capsys):
    import json

    p = tmp_path / "a.json"
    p.write_text(json.dumps(_annotate({"exposure": "core", "position": "leader"})), encoding="utf-8")
    assert from_json.apply_file(p, dry_run=True) == 0
    out = capsys.readouterr().out
    assert '"edges_added": 0' in out and '"edges_annotated": 1' in out       # 새 간선이 아니라 기존 간선에 덧붙인다
    p.write_text(json.dumps(_annotate({"exposure": "huge"})), encoding="utf-8")
    assert from_json.apply_file(p, dry_run=True) == 1                       # 값은 정해진 것만
    p.write_text(json.dumps(_annotate({"position": "leader"}, rel="requires", frm="product:google_tpu_system", to="component:mlb_pcb")), encoding="utf-8")
    assert from_json.apply_file(p, dry_run=True) == 1                       # 자리는 공급 간선에만


def test_recall_shows_exposure_tags():
    from wsj.ecosystems import recall as R
    from wsj.ecosystems.ontology import load_graph

    g = load_graph()
    for e in g["edges"]:
        if e["relation"] == "offered_by" and e["from"] == "component:mlb_pcb" and e["to"] == "company:isu_petasys":
            e.update({"exposure": "core", "position": "leader"})
    out = R.recall(g, ["company:isu_petasys"], [], [])
    assert "매출 핵심·선두" in out

def test_annotation_recomputes_confidence(tmp_path, monkeypatch):
    """근거를 더하면 신뢰도도 다시 센다 — 아니면 seed_graph 와 export_web 번들이 어긋나 CI 두 검사가 갈린다 (2026-11-04)."""
    import json
    import shutil

    from wsj.ecosystems import graph_patches
    from wsj.ecosystems.ontology import GRAPH_PATH, edge_confidence, load_ontology

    g = tmp_path / "graph.json"
    shutil.copy(GRAPH_PATH, g)
    monkeypatch.setattr(graph_patches, "GRAPH_PATH", g)
    p = tmp_path / "a.json"
    p.write_text(json.dumps(_annotate({"exposure": "core", "position": "leader"})), encoding="utf-8")
    assert from_json.apply_file(p) == 0
    row = next(e for e in json.loads(g.read_text(encoding="utf-8"))["edges"]
               if (e["from"], e["relation"], e["to"]) == ("component:mlb_pcb", "offered_by", "company:isu_petasys"))
    assert any(ev["url"] == "https://example.com/exposure" for ev in row["evidence"])
    assert row["confidence"] == edge_confidence(row, load_ontology())


def test_private_company_node():
    nodes, *_ = from_json.parse(_doc(nodes=[{"id": "company:zz_private", "kind": "company", "label": "Private Co (비상장)", "ecosystem": "power",
                                              "private": True, "role": "customer"}]))
    n = nodes[0]
    assert n.extra["listing"] == {"ticker": None, "exchange": None, "cik": None, "filer_type": "private"}
    assert n.extra["size_band"] == "private" and n.extra["role"] == "customer"
    with pytest.raises(ValueError):
        from_json.parse(_doc(nodes=[{"id": "company:zz_p2", "kind": "company", "label": "X", "ecosystem": "power", "private": True, "ticker": "1", "exchange": "KRX"}]))


# ------------------------------------------------------------------ v0.6: 산업 구간(segment)·최종 수요(end_demand)
def _seg_doc(**over):
    doc = {
        "prefix": "dseg",
        "nodes": [{"id": "segment:zz_test_segment", "kind": "segment", "label": "ZZ 시험 구간", "ecosystem": "power"},
                  {"id": "end_demand:zz_test_demand", "kind": "end_demand", "label": "ZZ 시험 수요(GW)", "ecosystem": "power", "unit": "GW"}],
        "edges": [
            {"from": "component:lpt", "relation": "part_of", "to": "segment:zz_test_segment", "tier": "third_party_report",
             "evidence": [{"url": "https://example.com/seg", "source_type": "third_party_report"}]},
            {"from": "company:gev", "relation": "participates_in", "to": "segment:zz_test_segment", "tier": "official_issuer",
             "evidence": [{"url": "https://example.com/seg", "source_type": "official_issuer"}]},
            {"from": "segment:zz_test_segment", "relation": "feeds", "to": "end_demand:zz_test_demand", "tier": "third_party_report",
             "coef": 25000, "coef_unit": "USD/MW", "coef_source": "https://example.com/coef",
             "evidence": [{"url": "https://example.com/seg", "source_type": "third_party_report"}]},
        ],
    }
    doc.update(over)
    return doc


def _dry(tmp_path, doc):
    import json

    p = tmp_path / "seg.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return from_json.apply_file(p, dry_run=True)


def test_segment_kinds_and_relations_validate(tmp_path, capsys):
    nodes, edges, *_ = from_json.parse(_seg_doc())
    assert {n.kind for n in nodes} == {"segment", "end_demand"}
    feeds = next(e for e in edges if e.relation == "feeds")
    assert feeds.attrs == {"coef": 25000, "coef_unit": "USD/MW", "coef_source": "https://example.com/coef"}
    assert _dry(tmp_path, _seg_doc()) == 0
    assert '"nodes_added": 2' in capsys.readouterr().out


def _edge(frm, rel, to, **kw):
    return dict({"from": frm, "relation": rel, "to": to, "tier": "third_party_report",
                 "evidence": [{"url": "https://example.com/seg", "source_type": "third_party_report"}]}, **kw)


@pytest.mark.parametrize("edges", [
    [_edge("company:gev", "part_of", "segment:zz_test_segment")],                         # part_of 는 부품·소재·장비·제품만
    [_edge("component:lpt", "participates_in", "segment:zz_test_segment")],               # participates_in 은 기업만
    [_edge("segment:zz_test_segment", "feeds", "component:lpt")],                         # feeds 는 구간·최종 수요로만
    [_edge("end_demand:zz_test_demand", "feeds", "segment:zz_test_segment")],             # 최종 수요는 끝 칸
    [_edge("segment:zz_test_segment", "feeds", "end_demand:zz_test_demand", coef=-1)],    # 계수는 0 이상
    [_edge("segment:zz_test_segment", "feeds", "end_demand:zz_test_demand", coef_unit=5)],     # 단위는 문자열
    [_edge("component:lpt", "requires", "material:goes", coef=3)],                        # coef 는 feeds 에만
])
def test_segment_relations_reject_wrong_domain_or_attrs(tmp_path, edges):
    assert _dry(tmp_path, _seg_doc(edges=edges)) == 1


def test_segment_ids_and_unit_checked(tmp_path):
    with pytest.raises(ValueError):
        from_json.parse(_seg_doc(nodes=[{"id": "component:zz_wrong", "kind": "segment", "label": "x", "ecosystem": "power"}]))
    bad_unit = _seg_doc(nodes=[{"id": "segment:zz_test_segment", "kind": "segment", "label": "x", "ecosystem": "power"},
                               {"id": "end_demand:zz_test_demand", "kind": "end_demand", "label": "y", "ecosystem": "power", "unit": ""}])
    assert _dry(tmp_path, bad_unit) == 1


def test_segment_seed_patch_is_applied_and_reuses_existing_evidence():
    """20261108 구간 패치: 모든 간선이 그래프에 있던 간선의 근거 URL 만 쓴다 (새 사실 없음), participates_in 은 offered_by 공급사와 같다."""
    import json

    from wsj.ecosystems.ontology import load_graph

    g = load_graph()
    doc = json.loads((from_json.PATCH_DIR / "20261108_segments.json").read_text(encoding="utf-8"))
    have_edges = {(e["from"], e["relation"], e["to"]) for e in g["edges"]}
    ids = {n["id"] for n in g["nodes"]}
    assert all(n["id"] in ids for n in doc["nodes"]) and all((e["from"], e["relation"], e["to"]) in have_edges for e in doc["edges"])
    old_urls = {ev["url"] for e in g["edges"] if not e["id"].startswith("seg1108-") for ev in e["evidence"]}
    assert all(ev["url"] in old_urls for e in doc["edges"] for ev in e["evidence"])
    members = {e["from"]: e["to"] for e in doc["edges"] if e["relation"] == "part_of"}
    suppliers = {(e["to"], members[e["from"]]) for e in g["edges"] if e["relation"] == "offered_by" and e["from"] in members}
    assert {(e["from"], e["to"]) for e in doc["edges"] if e["relation"] == "participates_in"} == suppliers


def test_impact_reaches_segment_participants_from_end_demand():
    """최종 수요의 변화는 feeds 를 거꾸로 타고 구간 → 참여 기업에 닿는다 (기존 노드의 영향 경로는 바뀌지 않는다)."""
    from wsj.ecosystems.impact import influence_paths
    from wsj.ecosystems.ontology import load_graph

    g = load_graph()
    paths = influence_paths(g, "end_demand:ai_dc_power")
    reached = {p["company_id"] for p in paths}
    assert {"company:clf", "company:cat", "company:be", "company:hitachi"} <= reached
    goes = next(p for p in paths if p["company_id"] == "company:clf")
    assert [x["node_id"] for x in goes["path"]][:3] == ["end_demand:ai_dc_power", "segment:large_power_transformer", "segment:goes"]
