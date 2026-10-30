"""논문·특허 백필 (techdocs) — 분류로 고르고, 그래프 어휘로 노드를 붙이고, 노드별 흐름으로 묶는다."""

import gzip
import io
import json
import re
from datetime import date

from wsj.ecosystems import recall as R
from wsj.ecosystems import techdocs as T
from wsj.ecosystems.ontology import load_graph

GRAPH = load_graph()


def _lex():
    _, _, terms = T.load_conf()
    return T.build_lex(GRAPH, terms)


def test_config_files_point_at_real_nodes_and_domains():
    domains, topics, terms = T.load_conf()
    ids = {n["id"] for n in GRAPH["nodes"]}
    assert set(terms) <= ids
    assert all(len(w) >= 4 for ws in terms.values() for w in ws)
    assert set(topics.values()) <= set(domains)
    assert set(T.load_context()) <= ids                       # 문맥 규칙도 그래프에 있는 노드만
    assert re.match(T.cpc_regex(p for ps in domains.values() for p in ps), "H01L25/0657")
    assert not re.match(T.cpc_regex(domains["packaging"]), "A61K31/00")
    assert T.domain_of("H05K1/0366", domains) == "substrate" and T.domain_of("G11C11/4096", domains) == "memory"


def test_lexicon_tags_patent_language_and_prefilter_is_re2_safe():
    lex = _lex()
    got = lex.nodes("Semiconductor package having stacked memory dies connected by through silicon vias and micro bumps")
    assert {"component:tsv", "component:microbump", "component:hbm_stack"} <= got
    assert "component:tia" in lex.nodes("A transimpedance amplifier for an optical receiver")
    rx = T.term_regex(lex.phrases)
    assert "(?<" not in rx and "(?!" not in rx                 # BigQuery(RE2)는 앞뒤 살피기를 못 한다
    assert re.search(rx, "a method of forming a through-silicon via in a wafer")
    assert re.search(rx, "high bandwidth memory with 16 stacked core dies")
    assert lex.company("SK HYNIX INC") == "company:skhynix"


def _pat(num, fam, cc, pub, title, lang="en", assignee="SK HYNIX INC", cpc=("H01L25/0657",), prio=20220101):
    return {"publication_number": num, "family_id": fam, "country_code": cc, "kind_code": "A1", "publication_date": pub,
            "priority_date": prio, "filing_date": prio, "cpc": list(cpc), "assignees": [{"name": assignee, "country_code": "KR"}],
            "title": title, "title_lang": lang, "abstract": ""}


def test_patent_docs_group_families_and_prefer_english():
    domains, _, _ = T.load_conf()
    rows = [_pat("KR-20240001-A", "77", "KR", 20240105, "적층 메모리", lang="ko"),
            _pat("US-2024001-A1", "77", "US", 20240301, "Stacked memory with through silicon via"),
            _pat("JP-2024001-A", "77", "JP", 20240401, "積層メモリ", lang="ja"),
            _pat("US-2025002-A1", "-1", "US", 20250101, "Cooling plate", assignee="Tiny Cooling LLC", cpc=("H05K7/20254",))]
    docs = {d.doc_id: d for d in T.patent_docs(rows, _lex(), domains)}
    fam = docs["patent:KR-20240001-A"]                        # 대표는 가장 이른 공개
    assert fam.title == "Stacked memory with through silicon via" and fam.countries == {"KR", "US", "JP"}
    assert fam.published == date(2024, 1, 5) and "component:tsv" in fam.nodes and "packaging" in fam.domains
    assert fam.orgs[0]["company"] == "company:skhynix"
    assert fam.url == "https://patents.google.com/patent/KR20240001A"
    assert docs["patent:US-2025002-A1"].domains == {"cooling"}   # 패밀리 id 없는 공개도 한 건으로


def test_paper_docs_keep_company_affiliations_only():
    rows = [{"id": "W1", "title": "Hybrid bonding of HBM stacks", "publication_date": "2025-03-01", "topic": "T1",
             "institutions": [{"name": "SK Hynix (South Korea)", "type": "company", "country": "KR"},
                              {"name": "KAIST", "type": "education", "country": "KR"}], "cited_by": 4, "abstract": "", "doi": None},
            {"id": "W1", "title": "Hybrid bonding of HBM stacks", "publication_date": "2025-03-01", "topic": "T2", "institutions": [], "cited_by": 4}]
    (d,) = T.paper_docs(rows, _lex(), {"T1": "packaging"})
    assert [o["name"] for o in d.orgs] == ["SK Hynix (South Korea)"] and d.codes == {"T1", "T2"}
    assert "tech:hybrid_bond" in d.nodes and d.url == "https://openalex.org/W1"


def _doc(i, year, org, company=None, node="component:tsv", src="patent", countries=("US",)):
    return T.Doc(f"{src}:{i}", src, f"t{i}", "", date(year, 5, 1), orgs=[{"name": org, "company": company}],
                 countries=set(countries), nodes={node})


def test_aggregate_series_orgs_and_doc_priority():
    docs = [_doc(1, 2020, "Old Co"), _doc(2, 2024, "Old Co"), _doc(3, 2024, "New Co"), _doc(4, 2025, "New Co"),
            _doc(5, 2025, "SK hynix", "company:skhynix"), _doc(6, 2025, "Old Co", countries=("US", "KR", "JP")), _doc(7, 2025, "Old Co")]
    series, orgs, rows = T.aggregate(docs, cap_docs=3, docs_since=date(2023, 1, 1))
    assert {(r["period"], r["n"]) for r in series} == {("2020-04-01", 1), ("2024-04-01", 2), ("2025-04-01", 4)}
    assert next(r for r in series if r["period"] == "2025-04-01")["n_company"] == 1
    new = next(o for o in orgs if o["org"] == "New Co" and o["span"] == "2024~")
    assert new["n"] == 2 and new["first_year"] == 2024
    assert next(o for o in orgs if o["org"] == "Old Co" and o["span"] == "~2021")["first_year"] == 2020
    picked = [r["doc_id"] for r in rows]
    assert picked[0] == "patent:5"                            # 그래프 기업 → 새 기관 → 여러 나라 특허 순
    assert set(picked[1:]) == {"patent:3", "patent:4"}


def test_domain_series_and_rising():
    rows = T.domain_series_rows([{"domain": "packaging", "country_code": "US", "year": 2024, "families": 10},
                                 {"domain": "packaging", "country_code": "KR", "year": 2024, "families": 5}],
                                [{"topic": "T1", "scope": "all", "year": 2024, "n": 90}, {"topic": "T1", "scope": "company", "year": 2024, "n": 9}],
                                [{"id": "T1", "domain": "packaging"}])
    assert {"node": "cpc:packaging", "source": "patent", "period": "2024-01-01", "n": 15, "n_company": None} in rows
    assert {"node": "topic:T1", "source": "paper", "period": "2024-01-01", "n": 90, "n_company": 9} in rows
    series = [{"node": "component:tsv", "source": "patent", "period": f"{y}-01-01", "n": n} for y, n in ((2022, 3), (2023, 3), (2024, 9), (2025, 9))]
    series += [{"node": "cpc:packaging", "source": "patent", "period": "2025-01-01", "n": 999}]
    (r,) = T.rising(series, today=date(2026, 3, 1), min_recent=5)
    assert (r["node"], r["prior"], r["recent"], r["ratio"]) == ("component:tsv", 6, 18, 3.0)


class FakeStore:
    def __init__(self):
        self.calls = []

    def delete(self, table, filters):
        self.calls.append(("delete", table, filters))

    def upsert(self, table, rows, conflict):
        self.calls.append(("upsert", table, len(rows), tuple(conflict)))
        return len(rows)


def test_upload_replaces_by_source(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "OUT", tmp_path)
    with gzip.open(tmp_path / "tech_docs.jsonl.gz", "wt") as f:
        for i in range(3):
            f.write(json.dumps({"doc_id": f"patent:{i}", "source": "patent"}) + "\n")
    store = FakeStore()
    T.main  # noqa: B018 - CLI 가 있다
    T.run_upload(type("A", (), {"replace": True, "batch": 2})(), store)
    assert ("delete", "ideas.tech_docs", {"source": "patent"}) in store.calls
    assert [c[2] for c in store.calls if c[0] == "upsert"] == [2, 1]


def test_openalex_pages_follow_cursor_and_cap():
    pages = [{"results": [{"id": 1}, {"id": 2}], "meta": {"next_cursor": "c2"}}, {"results": [{"id": 3}], "meta": {"next_cursor": None}}]
    seen = []

    def opener(req, timeout=None):
        seen.append(req.full_url)
        return io.BytesIO(json.dumps(pages[len(seen) - 1]).encode())

    oa = T.OpenAlex("k", opener=opener)
    assert [w["id"] for w in oa.pages("/works", {"filter": "x"}, cap=10)] == [1, 2, 3]
    assert "api_key=k" in seen[0] and "cursor=c2" in seen[1]
    seen.clear()
    assert len(list(oa.pages("/works", {}, cap=1))) == 1


def test_recall_shows_tech_section():
    tech = {"series": [{"node": "component:tsv", "source": "patent", "period": "2024-01-01", "n": 3},
                       {"node": "component:tsv", "source": "patent", "period": "2024-04-01", "n": 4}],
            "orgs": [{"node": "component:tsv", "source": "patent", "span": "2024~", "rank": 1, "org": "SK HYNIX INC", "company": "company:skhynix", "n": 5, "first_year": 2019},
                     {"node": "component:tsv", "source": "patent", "span": "2024~", "rank": 2, "org": "Tiny Via Corp", "company": None, "n": 3, "first_year": 2024}],
            "docs": [{"source": "patent", "nodes": ["component:tsv"], "published_on": "2025-02-01", "orgs": [{"name": "Tiny Via Corp"}], "title": "Via fill", "url": "https://p/1"}]}
    out = R.recall(GRAPH, [], ["component:tsv"], [], tech_fetch=lambda nodes: tech)
    assert "특허 연도별: 2024 7" in out and "새로 나타난 곳: Tiny Via Corp 3" in out and "Via fill https://p/1" in out
    assert "논문·특허" in R.recall(GRAPH, [], ["component:tsv"], [], tech_fetch=lambda nodes: {})


def test_sql_uses_parameters():
    domains, _, _ = T.load_conf()
    sql = T.patents_sql(domains)
    assert all(p in sql for p in ("@since", "@countries", "@cpc_re", "@term_re"))
    assert "STRUCT('packaging' AS domain" in T.domain_series_sql(domains)


def test_context_keeps_data_center_meaning_only():
    lex = _lex()
    ev = lex.nodes("Liquid cooling plate for a battery module of an electric vehicle")
    dc = lex.nodes("Liquid cooling cold plate for a GPU in a server rack of a data center")
    assert not ev & {"bottleneck:liquidcool", "component:coldplate"}
    assert {"bottleneck:liquidcool", "component:coldplate"} & dc
    assert "tech:glass_core_substrate" not in lex.nodes("Glass core substrate for a vacuum insulated window")
    assert "tech:glass_core_substrate" in lex.nodes("Glass core substrate with through glass vias for a semiconductor package")
    assert "component:photodiode" not in lex.nodes("Image sensor pixel with a photodiode and transfer gate")
    assert "component:photodiode" in lex.nodes("Germanium photodiode integrated with a silicon photonic waveguide receiver")
    assert "component:hbm_stack" in lex.nodes("High bandwidth memory stack")      # 문맥 규칙이 없는 노드는 그대로


def test_org_names_group_variants():
    assert T.org_key("TOYOTA MOTOR CO LTD") == T.org_key("TOYOTA MOTOR CORP") == "TOYOTA MOTOR"
    assert T.org_key("Intel (United States)") == T.org_key("INTEL CORP") == "INTEL"
    assert T.org_key("SK INNOVATION CO LTD") != T.org_key("SK ON CO LTD")
    docs = [_doc(1, 2019, "NANJING THIRD GEN CENTER"), _doc(2, 2025, "NANJING THIRD GEN CENTER CO LTD"), _doc(3, 2025, "NANJING THIRD GEN CENTER CO LTD")]
    _, orgs, _ = T.aggregate(docs)
    (o,) = [o for o in orgs if o["span"] == "2024~"]
    assert o["first_year"] == 2019 and o["n"] == 2 and o["org"] == "NANJING THIRD GEN CENTER CO LTD"   # 새 기관이 아니다


def test_orgs_group_by_graph_company_across_old_names():
    lex = _lex()
    assert lex.company("INVENSAS BONDING TECHNOLOGIES INC") == lex.company("ADEIA SEMICONDUCTOR BONDING TECHNOLOGIES INC") == "company:adea"
    docs = [_doc(1, 2020, "INVENSAS BONDING TECHNOLOGIES INC", "company:adea"), _doc(2, 2025, "ADEIA SEMICONDUCTOR BONDING TECHNOLOGIES INC", "company:adea")]
    _, orgs, _ = T.aggregate(docs)
    (o,) = [o for o in orgs if o["span"] == "2024~"]
    assert o["company"] == "company:adea" and o["first_year"] == 2020     # 이름이 바뀌었을 뿐 새 기관이 아니다


def test_signals_pick_new_or_accelerating_us_kr_small_players():
    g = {"nodes": [{"id": "component:tsv", "kind": "component", "label": "TSV (실리콘 관통 전극)"},
                   {"id": "company:tiny", "kind": "company", "label": "Tiny Corp (Nasdaq TINY)", "size_band": "small", "listing": {"ticker": "TINY", "exchange": "Nasdaq"}},
                   {"id": "company:big", "kind": "company", "label": "Big Corp", "size_band": "mega", "listing": {"ticker": "BIG", "exchange": "Nasdaq"}}],
         "edges": []}
    series = [{"node": "component:tsv", "source": "patent", "period": f"{y}-01-01", "n": n} for y, n in ((2022, 5), (2023, 5), (2024, 20), (2025, 20))]
    orgs = [{"node": "component:tsv", "source": "patent", "span": "2024~", "org": "TINY CORP", "company": "company:tiny", "n": 6, "first_year": 2024},
            {"node": "component:tsv", "source": "patent", "span": "2024~", "org": "BIG CORP", "company": "company:big", "n": 30, "first_year": 2024},
            {"node": "component:tsv", "source": "patent", "span": "2024~", "org": "SEOUL NATIONAL UNIVERSITY", "company": None, "n": 9, "first_year": 2024},
            {"node": "component:tsv", "source": "patent", "span": "2024~", "org": "KIM CHUL SOO", "company": None, "n": 4, "first_year": 2025},
            {"node": "component:tsv", "source": "patent", "span": "2024~", "org": "VIA KOREA CO LTD", "company": None, "n": 8, "first_year": 2019},
            {"node": "component:tsv", "source": "patent", "span": "2022-2023", "org": "VIA KOREA CO LTD", "company": None, "n": 2, "first_year": 2019},
            {"node": "component:tsv", "source": "patent", "span": "2024~", "org": "STEADY CO LTD", "company": None, "n": 6, "first_year": 2019},
            {"node": "component:tsv", "source": "patent", "span": "2022-2023", "org": "STEADY CO LTD", "company": None, "n": 5, "first_year": 2019}]
    docs = [{"source": "patent", "title": "Via fill", "published_on": "2025-05-01", "url": "https://p/1", "nodes": ["component:tsv"],
             "orgs": [{"name": "VIA KOREA CO LTD", "country": "KR"}]},
            {"source": "patent", "title": "Steady", "published_on": "2025-05-01", "url": "https://p/2", "nodes": ["component:tsv"],
             "orgs": [{"name": "STEADY CO LTD", "country": "KR"}]}]
    got = T.signals(series, orgs, docs, g, today=date(2026, 3, 1))
    assert [(s["org"], s["new"]) for s in got] == [("TINY CORP", True), ("VIA KOREA CO LTD", False)]   # 대형·대학·개인·완만한 곳은 뺀다
    assert got[1]["url"] == "https://p/1" and got[1]["country"] == "KR"
    title, summary = T.signal_text(got[0])
    assert title.startswith("[특허 흐름] TSV: TINY CORP 2024년 이후 6건 — 새로 들어옴") and "×4.0" in title


def test_tech_signal_clues_are_weekly_and_capped():
    from datetime import UTC, datetime

    from wsj.ecosystems import clues as C

    assert C.tech_signals_due(datetime(2026, 11, 1, 16, 0, tzinfo=UTC))        # 일요일 16시 UTC = 월요일 01시 KST
    assert not C.tech_signals_due(datetime(2026, 11, 2, 16, 0, tzinfo=UTC))

    class Store:
        def select(self, table, columns=None, filters=None, limit=None, order=None):
            raise RuntimeError("relation does not exist")

    assert C.tech_signal_clues(Store(), GRAPH) == []                           # 0033·백필 전에도 수집은 돈다
