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
