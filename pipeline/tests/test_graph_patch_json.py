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
