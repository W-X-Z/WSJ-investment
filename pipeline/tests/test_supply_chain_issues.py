from datetime import UTC, datetime, timedelta

from wsj.ecosystems import issues
from wsj.ecosystems.ontology import load_graph

NOW = datetime(2026, 10, 27, tzinfo=UTC)


def item(title, days=1, pub="Reuters", st="news", url=None, snippet=""):
    return issues.Item(url or f"https://x.test/{abs(hash(title + pub))}", title, NOW - timedelta(days=days), pub, st, snippet)


def test_lexicon_tags_nodes_and_companies_with_word_boundaries():
    node_pats, comp_pats = issues.build_lexicon(load_graph())
    a = item("SK hynix delays hybrid bonding to HBM5; Camtek and Onto Innovation inspection demand extends")
    b = item("A classic physics review of powerful lasers")  # 'sic' ⊂ classic, 'power' ⊂ powerful 은 걸리면 안 된다
    c = item("Navitas and Infineon chase 800 VDC data center power")
    issues.tag([a, b, c], node_pats, comp_pats)
    assert "tech:hybrid_bond" in a.nodes and {"company:skhynix", "company:camt", "company:onto"} <= a.companies
    assert not b.nodes and not b.companies
    assert "company:nvts" in c.companies and "gen:800vdc" in c.nodes


def test_noise_filter_drops_stock_chatter_but_keeps_events():
    assert issues.NOISE.search("Kulicke and Soffa Industries Stock Forecast & Analyst Predictions")
    assert issues.NOISE.search("Adeia to Release Third Quarter 2026 Financial Results on November 2")
    assert issues.NOISE.search("AXT rebounds 10% after recent slide")
    assert not issues.NOISE.search("Infineon extends Wolfspeed wafer deal to 8-inch silicon carbide")
    assert not issues.NOISE.search("MaxLinear reports third quarter results, optical DSP revenue up 72%")


def test_dedupe_and_cluster_merge_same_story_but_not_different_companies():
    a = item("Infineon extends Wolfspeed wafer deal to 8-inch silicon carbide", pub="Reuters")
    b = item("Infineon extends Wolfspeed silicon carbide wafer supply deal to 8-inch", pub="EE Times")
    c = item("Navitas unveils 2300V full-bridge SiC module family for 800V", pub="Electronics Weekly")
    a.companies = {"company:wolf"}
    b.companies = {"company:wolf"}
    c.companies = {"company:nvts"}
    dup = item("Infineon extends Wolfspeed wafer deal to 8-inch silicon carbide", pub="Reuters", url=a.url)
    out = issues.dedupe([a, b, c, dup])
    assert len(out) == 3
    groups = issues.cluster(out)
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_score_rewards_primary_sources_coverage_and_small_caps():
    g = {n["id"]: n for n in load_graph()["nodes"]}
    news = [item("x", pub="A")]
    primary = [item("y", st="sec", pub="SEC"), item("y2", pub="B"), item("y3", pub="C")]
    primary[0].companies = {"company:aehr"}  # small cap
    primary[0].nodes = {"process:wafer_level_burn_in"}
    assert issues.score(primary, g, NOW)["rule_importance"] > issues.score(news, g, NOW)["rule_importance"]
    old = [item("z", days=12)]
    assert issues.score(old, g, NOW)["recency"] < 1


def test_ecosystem_vote_and_issue_key_stable():
    g = {n["id"]: n for n in load_graph()["nodes"]}
    assert issues.ecosystem_of(["tech:hybrid_bond"], ["company:camt"], None, g) == "hbm"
    assert issues.ecosystem_of(["tech:hybrid_bond"], ["company:nvts"], None, g) == "cross"
    assert issues.ecosystem_of([], [], "power", g) == "power"
    m = [item("a", url="https://a"), item("b", url="https://b")]
    assert issues.issue_key(m) == issues.issue_key(list(reversed(m)))


def test_sec_headline_and_boilerplate():
    poet = ("EX-99.1 2 exh_991.htm PRESS RELEASE EdgarFiling EXHIBIT 99.1 POET Technologies to Report Third Quarter 2026 Financial Results "
            "on November 16 TORONTO, Oct. 16, 2026 (GLOBE NEWSWIRE) -- POET will report. About POET Technologies Inc. POET's platform is the POET Optical Interposer.")
    head, boiler = issues.sec_headline(poet, '"optical interposer"', "POET TECHNOLOGIES INC.")
    assert head.startswith("POET Technologies to Report Third Quarter") and boiler
    assert issues.NOISE.search(head)
    mxl = ("EX-99.1 3 a.htm EX-99.1 Document Exhibit 99.1 FOR IMMEDIATE RELEASE MaxLinear, Inc. Announces Third Quarter 2026 Financial Results "
           "• Q3 net revenue up 72% Carlsbad, Calif. – October 22, 2026 – volume ramp of our Keystone PAM4 DSP platform. About MaxLinear ...")
    head, boiler = issues.sec_headline(mxl, '"PAM4 DSP"', "MAXLINEAR, INC")
    assert head == "MaxLinear, Inc. Announces Third Quarter 2026 Financial Results" and not boiler


def test_collect_unmapped_drops_known_vocabulary_and_merges_terms():
    """잔차(ADR-0026): 어휘 사전에 걸리는 용어(hybrid bonding·Navitas)는 잔차가 아니고, 같은 용어는 이슈 키를 합친다."""
    node_pats, comp_pats = issues.build_lexicon(load_graph())
    rows = [
        {"issue_key": "i1", "ecosystem": "hbm", "_unmapped": [{"term": "HBF", "kind_guess": "technology", "context": "NAND 적층 계층"},
                                                             {"term": "hybrid bonding", "kind_guess": "technology"}, {"term": "x", "kind_guess": "other"}]},
        {"issue_key": "i2", "ecosystem": "power", "_unmapped": [{"term": "hbf", "kind_guess": "nonsense"}, {"term": "Navitas"}, {"term": "Kyber liquid-cooled busway", "kind_guess": "component"}]},
        {"issue_key": "i3", "ecosystem": "optics"},
    ]
    out = issues.collect_unmapped(rows, node_pats, comp_pats)
    assert all("_unmapped" not in r for r in rows)
    keys = {r["term_key"]: r for r in out}
    assert set(keys) == {"hbf", "kyber_liquid_cooled_busway"}
    assert keys["hbf"]["issue_keys"] == ["i1", "i2"] and keys["hbf"]["kind_guess"] == "technology" and keys["hbf"]["context"] == "NAND 적층 계층"
    assert out[0]["term_key"] == "hbf"  # 더 많은 이슈에 나온 것이 앞


def test_save_unmapped_accumulates_n_seen_and_issue_keys():
    class Store:
        def __init__(self):
            self.rows = {"hbf": {"term_key": "hbf", "issue_keys": ["i0"], "first_seen": "2026-10-20", "n_seen": 2, "status": "open", "kind_guess": None, "context": None}}
            self.upserted = []

        def select(self, table, columns=None, filters=None, limit=None, order=None):
            return [r for k, r in self.rows.items() if k in filters["term_key"]]

        def upsert(self, table, rows, conflict):
            self.upserted = rows
            return len(rows)

    st = Store()
    n = issues.save_unmapped(st, [{"term_key": "hbf", "term": "HBF", "kind_guess": "technology", "ecosystem": "hbm", "context": "c", "issue_keys": ["i0", "i1"]},
                                  {"term_key": "new_one", "term": "New One", "kind_guess": None, "ecosystem": None, "context": None, "issue_keys": ["i1"]}], NOW)
    assert n == 2
    by = {r["term_key"]: r for r in st.upserted}
    assert by["hbf"]["n_seen"] == 3 and by["hbf"]["issue_keys"] == ["i0", "i1"] and by["hbf"]["first_seen"] == "2026-10-20" and by["hbf"]["kind_guess"] == "technology"
    assert by["new_one"]["n_seen"] == 1 and by["new_one"]["first_seen"] == "2026-10-27" and by["new_one"]["status"] == "open"
