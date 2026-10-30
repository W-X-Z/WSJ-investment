"""꺼내 쓰기 (ADR-0028 3단계) — 그래프 자리·패턴·지난 사례·지난 단서를 한 장으로."""

import re

from wsj.ecosystems import recall as R

G = {"nodes": [
    {"id": "product:tpu", "kind": "product", "label": "TPU 시스템"},
    {"id": "component:mlb", "kind": "component", "label": "고다층 기판"},
    {"id": "material:ccl", "kind": "material", "label": "동박적층판"},
    {"id": "company:isu", "kind": "company", "label": "ISU Petasys", "size_band": "mid", "listing": {"ticker": "007660", "exchange": "KRX"}},
    {"id": "company:gce", "kind": "company", "label": "Gold Circuit", "size_band": "large", "listing": {"ticker": "2368", "exchange": "TWSE"}},
    {"id": "company:ccl_kr", "kind": "company", "label": "CCL Korea", "size_band": "small", "listing": {"ticker": "000001", "exchange": "KOSDAQ"}},
], "edges": [
    {"from": "product:tpu", "relation": "implements", "to": "component:mlb"},
    {"from": "component:mlb", "relation": "offered_by", "to": "company:isu"},
    {"from": "component:mlb", "relation": "offered_by", "to": "company:gce"},
    {"from": "component:mlb", "relation": "requires", "to": "material:ccl"},
    {"from": "material:ccl", "relation": "offered_by", "to": "company:ccl_kr"},
]}


def test_graph_walks_up_and_down():
    g = R.Graph(G)
    assert g.offers("company:isu") == ["component:mlb"]
    assert ("product:tpu", "implements", "component:mlb") in g.demanders("component:mlb")
    assert g.suppliers("component:mlb") == ["company:isu", "company:gce"]
    down = dict((c, p) for p, c in g.downstream_suppliers("product:tpu"))
    assert down["company:ccl_kr"] == ["product:tpu", "component:mlb", "material:ccl"]   # 두 단계 아래 소형 공급사


def test_recall_pack_has_place_cases_and_clues(monkeypatch):
    monkeypatch.setattr(R, "load_patterns", lambda d=None: [{"file": "x.md", "title": "세컨드 소스", "nodes": {"component:mlb"}, "text": "# 세컨드 소스 vs 함량"}])
    opps = [{"title": "TPU 고다층화에 따른 기판 매출 확대", "stars": 3, "status": "active", "nodes": ["component:mlb"], "companies": [], "updated_at": "2026-10-30"},
            {"title": "다른 이야기", "stars": 2, "status": "active", "nodes": ["component:x"], "companies": [], "updated_at": "2026-10-30"}]
    clues = [{"title": "金像電 TPU v8 진입", "nodes": ["component:mlb"], "companies": [], "published_at": "2026-10-23", "source_name": "經濟日報", "url": "https://u"}]
    out = R.recall(G, ["company:isu"], [], [], "", opps, clues, None)
    assert "같이 파는 회사: Gold Circuit" in out and "# 세컨드 소스 vs 함량" in out
    assert "TPU 고다층화에 따른 기판 매출 확대" in out and "다른 이야기" not in out
    assert "金像電 TPU v8 진입" in out


def test_pattern_cards_point_at_real_nodes():
    from wsj.ecosystems.ontology import load_graph

    ids = {n["id"] for n in load_graph()["nodes"]}
    pats = R.load_patterns()
    assert len(pats) >= 5
    for p in pats:
        assert p["nodes"], p["file"]
        assert p["nodes"] <= ids, (p["file"], p["nodes"] - ids)
        assert re.search(r"^- 반대 신호", p["text"], re.M), p["file"]
