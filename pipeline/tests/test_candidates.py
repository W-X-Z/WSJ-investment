"""후보 노드 통로 — 기업 예시는 그래프에 들어올 일이 없는 가상의 회사(티커 99xx)로 쓴다 (실제 회사는 해석이 그래프에 넣으면 테스트가 깨진다).

후보 노드 통로 (ADR-0031 G-6·G-7·T-8) — 식별자 태깅, 본문 태깅, 다시 잇기, 그래프 밖 상장사·사전 밖 식별자 제안."""

import pytest

from wsj.ecosystems import candidates as K
from wsj.ecosystems import clues as C
from wsj.ecosystems import graph_sync as G
from wsj.ecosystems.graph_patches.from_json import parse
from wsj.ecosystems.issues import build_lexicon
from wsj.ecosystems.ontology import load_graph


def _hits(text):
    node_pats, _ = build_lexicon(load_graph())
    return {nid for p, nid in node_pats if p.search(text)}


def test_codes_tag_raw_titles():
    assert "rule:ercot_nogrr282" in _hits("ERCOT TAC approves NOGRR 282 language")
    assert "std:jesd328" in _hits("JEDEC publishes JESD328 v1.00")
    assert "std:ieee_802_3dj" in _hits("IEEE P802.3dj D3.1 comment resolution")
    assert "tech:coherent_dci" in _hits("OIF releases 1600ZR implementation agreement")
    assert "tech:sidecar" in _hits("OCP Mt. Diablo Disaggregated Power Rack v1.0")


def test_tag_bodies_only_for_untagged_raw_and_newsroom():
    g = load_graph()
    raw = C.Clue("https://jedec.org/a", "Meeting materials", "", None, "jedec_jc45", "JEDEC", "standards", layer="raw")
    press = C.Clue("https://press/a", "Weekly roundup", "", None, "p", "P", "trade_press", layer="press")
    tagged = C.Clue("https://jedec.org/b", "HBM4 update", "", None, "jedec_jc45", "JEDEC", "standards", layer="raw", nodes={"gen:hbm4"})
    body = "Agenda: SOCAMM2 module ballot (JESD328 rev), LPDDR6 errata"
    got = C.tag_bodies([raw, press, tagged], {raw.url: body, press.url: body, tagged.url: body}, g)
    assert got == [raw] and {"std:jesd328", "component:server_dram_lpdram"} <= raw.nodes
    assert raw.extra["nodes_from_body"] and not press.nodes and tagged.nodes == {"gen:hbm4"}
    # 페이지 변화 단서는 층과 상관없이 (layers=None)
    assert C.tag_bodies([press], {press.url: body}, g, layers=None) == [press]


def test_resolver_covers_more_exchanges_and_other_listings():
    r = C.company_resolver(load_graph())
    assert r("剑桥科技", "603083", "SSE") == "company:cig"
    assert r("Infineon", "IFX", "XETRA") == "company:infineon"
    assert r("台積電", "2330", "TWSE") == "company:tsmc"      # 그래프는 TSM(NYSE) — 현지어 이름·별칭으로
    assert r("Nobody Corp", "ZZZZ", "Nasdaq") is None


def test_relink_fixes_old_unresolved_companies():
    rows = [{"url": "u1", "companies": [{"company": None, "name": "烽火通信", "ticker": "600498", "exchange": "SSE"},
                                        {"company": "company:fiberhome", "name": "FiberHome"}]},
            {"url": "u2", "companies": [{"company": None, "name": "Nobody", "ticker": "ZZZZ", "exchange": "Nasdaq"}]}]
    fixed = K.relink(rows, C.company_resolver(load_graph()))
    assert [f["url"] for f in fixed] == ["u1"]
    assert fixed[0]["companies"] == [{"company": "company:fiberhome", "name": "FiberHome"}]   # 같은 회사 중복은 뺀다


def _row(url, layer, companies, nodes=(), date="2026-11-01"):
    return {"url": url, "published_at": date, "extra": {"layer": layer}, "companies": companies, "nodes": list(nodes), "title": "", "summary": ""}


def test_outside_companies_threshold_ecosystem_and_skip():
    g = load_graph()
    co = {"company": None, "name": "Zyxtron Semiconductor", "ticker": "9998", "exchange": "TWSE"}
    one_press = [_row("a", "press", [co], ["component:optical_dsp"])]
    assert K.outside_companies(one_press, g, set(), "2026-11-02") == []                      # 업계지 1건은 아직
    two = one_press + [_row("b", "press", [co], ["component:optical_dsp"], "2026-10-30")]
    got = K.outside_companies(two, g, set(), "2026-11-02")
    p = got[0]["payload"]
    assert p["status"] == "candidate" and p["size_band"] == "unknown" and p["ecosystem"] == "optics"
    assert p["id"] == "company:zyxtron_semiconductor" and p["first_evidence"]["date"] == "2026-10-30" and got[0]["n"] == 2
    raw_one = [_row("c", "disclosure", [co], ["component:optical_dsp"])]
    assert K.outside_companies(raw_one, g, set(), "2026-11-02")                               # 공시·원본 층은 1건으로
    assert K.outside_companies(two, g, {("TW", "9998")}, "2026-11-02") == []                  # 이미 제안됨
    no_anchor = [_row("d", "disclosure", [co])]
    assert K.outside_companies(no_anchor, g, set(), "2026-11-02") == []                       # 걸린 노드·그래프 기업이 없으면 올리지 않는다
    bad = [_row("e", "disclosure", [{**co, "ticker": "Holtek"}], ["component:optical_dsp"])]
    assert K.outside_companies(bad, g, set(), "2026-11-02") == []                             # 대만 티커 꼴이 아니면


def test_cjk_name_gets_exchange_ticker_id():
    g = load_graph()
    co = {"company": None, "name": "測試電機", "ticker": "9999", "exchange": "TWSE"}
    got = K.outside_companies([_row("a", "disclosure", [co], ["component:mv_switchgear"])], g, set(), "2026-11-02")
    assert got[0]["payload"]["id"] == "company:twse_9999" and got[0]["payload"]["ecosystem"] == "power"


def test_unmapped_terms_from_untagged_raw_clues():
    g = load_graph()
    rows = [_row("a", "raw", []) | {"title": "TF meeting: P802.3dk objectives; NOGRR 282 cleanup"},
            _row("b", "raw", []) | {"title": "P802.3dk baseline"},
            _row("c", "raw", [], ["gen:hbm4"]) | {"title": "JESD999-1 draft"},          # 이미 기술 노드가 걸렸다
            _row("d", "press", []) | {"title": "JESD888 rumor"}]                       # 업계지는 보지 않는다
    got = K.unmapped_terms(rows, g, set(), {"b": "also see CXL 4.0 fabric"})
    terms = {t["payload"]["term"]: t for t in got}
    assert "P802.3dk" in terms and terms["P802.3dk"]["payload"]["count"] == 2
    assert "CXL 4.0" in terms and "NOGRR 282" not in terms                         # 사전에 있는 말은 뺀다
    assert not any(k.startswith("JESD") for k in terms)
    assert K.unmapped_terms(rows, g, {"p802.3dk", "cxl 4.0"}, {"b": "also see CXL 4.0 fabric"}) == []


def test_candidate_company_patch_allows_unknown_band_and_keeps_v05_fields():
    doc = {"prefix": "t1102", "nodes": [{"id": "company:twse_9999", "kind": "company", "label": "測試電機 (TWSE 9999)", "ecosystem": "power",
                                         "ticker": "9999", "exchange": "TWSE", "size_band": "unknown", "status": "candidate", "first_seen": "2026-11-02"}]}
    nodes, *_ = parse(doc)
    assert nodes[0].extra["status"] == "candidate" and nodes[0].extra["size_band"] == "unknown" and nodes[0].extra["first_seen"] == "2026-11-02"
    doc["nodes"][0]["status"] = "active"
    with pytest.raises(ValueError):
        parse(doc)


def test_graph_terms_include_company_aliases():
    terms = {(t["term"], t["node_id"]) for t in G.term_rows(load_graph())}
    assert ("台積電", "company:tsmc") in terms and ("nogrr282", "rule:ercot_nogrr282") in terms


class _Store:
    def __init__(self, rows):
        self.rows, self.inserted, self.upserted = rows, [], []

    def select(self, table, cols=None, filters=None, limit=None, order=None):
        if table == "ideas.clues":
            return self.rows
        if table == "ideas.graph_proposals":
            return [{"kind": "term", "payload": {"term": "P802.3dk"}}]
        return []

    def insert(self, table, rows):
        self.inserted += rows
        return len(rows)

    def upsert(self, table, rows, key):
        self.upserted += rows
        return len(rows)


def test_run_writes_relinks_and_proposals_skipping_known():
    co = {"company": None, "name": "測試電機", "ticker": "9999", "exchange": "TWSE"}
    rows = [_row("a", "disclosure", [co], ["component:mv_switchgear"]) | {"seen_at": "x", "relevant": True},
            _row("b", "raw", []) | {"title": "P802.3dk and PCIe 8.0"},
            _row("c", "press", [{"company": None, "name": "烽火通信", "ticker": "600498", "exchange": "SSE"}])]
    st = _Store(rows)
    stats = K.run(st, load_graph(), days=14)
    assert stats["relinked"] == 1 and st.upserted[0]["url"] == "c" and st.upserted[0]["companies"][0]["company"] == "company:fiberhome"
    kinds = [(p["kind"], p["payload"].get("term") or p["payload"].get("id")) for p in st.inserted]
    assert ("node", "company:twse_9999") in kinds and ("term", "PCIe 8.0") in kinds and ("term", "P802.3dk") not in kinds
    assert all(p["by"] == "collect" and p["reason"] for p in st.inserted)
