"""Safety-focused regression tests for graph evidence enrichment."""
import json
from pathlib import Path
from wsj.ecosystems.enrich_graph import (
    METRIC, alias_pattern, as_of_ok, build, links, quantitative_passages
)


def tiny_fixture(tmp_path:Path):
    root=tmp_path/"historical";root.mkdir()
    graph=tmp_path/"graph.json"
    graph.write_text(json.dumps({"nodes":[
        {"id":"eco:hbm","kind":"ecosystem","label":"HBM"},
        {"id":"process:hybrid_bond","kind":"process","label":"Hybrid bonding"},
        {"id":"material:cu_cu","kind":"material","label":"Cu-Cu bonding"},
    ],"edges":[]}))
    alias=tmp_path/"aliases.json"
    alias.write_text(json.dumps({"aliases":{
        "process:hybrid_bond":["hybrid bonding","wafer bonding"],
        "material:cu_cu":["copper-copper bonding","Cu-Cu bonding"],
    }}))
    docs=[
        {"id":"a","canonical_id":"doi:10.1000/a","historical_backfill":True,
         "title":"Hybrid bonding process at 50 nm overlay","excerpt":"Wafer bonding achieved 50 nm accuracy in one simulation; not an independently validated measurement.",
         "source":"openalex","source_group":"scholarly_bibliography","ecosystem":"hbm",
         "published_at":"2021-02-10","published_precision":"day",
         "first_seen_at":"2026-10-26T10:00:00Z","url":"https://api.openalex.org/works/W1"},
        {"id":"b","canonical_id":"doi:10.1000/a","historical_backfill":True,
         "title":"Hybrid bonding process at 50 nm overlay","excerpt":"",
         "source":"crossref","source_group":"scholarly_bibliography","ecosystem":"hbm",
         "published_at":"2021-02-10","first_seen_at":"2026-10-26T10:00:00Z","url":"https://api.crossref.org/works/10.1000/a"},
        {"id":"future","canonical_id":"doi:10.1000/future","historical_backfill":True,
         "title":"Hybrid bonding in 2027","excerpt":"",
         "source":"openalex","source_group":"scholarly_bibliography","ecosystem":"hbm",
         "published_at":"2027-11-12","first_seen_at":"2026-10-26T10:00:00Z","url":"https://api.openalex.org/works/W2"},
        {"id":"not_relevant","canonical_id":"doi:10.1000/no","historical_backfill":True,
         "title":"Biological technique","excerpt":"This is about sea water only.",
         "source":"openalex","source_group":"scholarly_bibliography","ecosystem":"hbm",
         "published_at":"2020-06-10","first_seen_at":"2026-10-26T10:00:00Z","url":"https://api.openalex.org/works/W3"},
    ]
    for eco in ("hbm","optics","power"):
        (root/(eco+".jsonl")).write_text("\n".join(json.dumps(d) for d in docs if d["ecosystem"]==eco)+"\n")
    return root,graph,alias


def test_regex_alias_word_boundaries_and_metrics():
    assert alias_pattern("SiC").search("SiC MOSFET")
    assert not alias_pattern("SiC").search("basic silicon")
    assert METRIC.search("50 nm overlay")
    assert METRIC.search("200 Gb/s lane")


def test_quantitative_passage_requires_alias_proximity_and_no_physics_certainty():
    text="Hybrid bonding achieved 50 nm pitch. Test conditions not described. "
    extracted=quantitative_passages(text,[(0,14)])
    assert len(extracted)==1
    assert extracted[0]["value"]==50
    assert extracted[0]["unit"]=="nm"
    assert extracted[0]["verification"]=="unverified_numeric_mention"
    assert not extracted[0]["conditions_verified"]
    assert not quantitative_passages("150 nm isolated statement",[])


def test_future_date_not_backfilled_as_historical():
    assert not as_of_ok({"published_at":"2026-12-28","historical_backfill":True},"2026-10-26")
    assert as_of_ok({"published_at":"2020-01-01","historical_backfill":True},"2026-10-26")
    assert not as_of_ok({"published_at":"2020-01-01","historical_backfill":False},"2026-10-26")


def test_crossref_duplicate_is_not_independent_validation(tmp_path):
    folder,graph,aliases=tiny_fixture(tmp_path)
    result,summary,relations=build(folder=folder,graph_path=graph,alias_path=aliases,as_of="2026-10-26")
    assert summary["total_historical_records_read"]==4
    assert summary["excluded_future_or_invalid"]==1
    assert summary["unique_valid_sources"]==2
    assert summary["documents_with_ontology_matches"]==1
    assert result["nodes"]["process:hybrid_bond"]["total_document_leads"]==1
    assert result["nodes"]["material:cu_cu"]["total_document_leads"]==0
    assert summary["new_confirmed_supply_edges"]==0
    assert relations["candidates"]==[]
    source=result["nodes"]["process:hybrid_bond"]["sources"][0]
    assert source["verification_status"]=="index_match_only"
    assert not source["source_independence_verified"]
    assert source["first_seen_at"]=="2026-10-26T10:00:00Z"


def test_lexical_co_mentions_do_not_create_supplier_edges(tmp_path):
    root,graph,alias=tiny_fixture(tmp_path)
    docs=[
        {"id":str(i),"canonical_id":"doi:10.9/"+str(i),
        "historical_backfill":True,"title":"Hybrid bonding versus Cu-Cu bonding process",
        "excerpt":"Hybrid bonding and Cu-Cu bonding discussed side by side, not a supply contract.",
        "source":"openalex","source_group":"scholarly_bibliography","ecosystem":"hbm",
        "published_at":f"202{i+1}-02-01","published_precision":"day",
        "first_seen_at":"2026-10-26T10:00:00Z","url":"https://api.openalex.org/works/W"+str(i)}
        for i in range(2)
    ]
    (root/"hbm.jsonl").write_text("\n".join(json.dumps(x) for x in docs)+"\n")
    out,summary,pairs=build(folder=root,graph_path=graph,alias_path=alias,as_of="2026-10-26")
    assert summary["co_mention_pairs_requiring_review"]==1
    assert pairs["candidates"][0]["should_create_graph_edge"] is False
    assert pairs["candidates"][0]["status"]=="lexical_co_mention_not_supply_relation"
