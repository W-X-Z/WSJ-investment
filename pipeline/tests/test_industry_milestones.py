"""The curated milestone stream must stay tied to public, date-valid original sources."""
import json
from pathlib import Path
from datetime import date

ROOT=Path(__file__).resolve().parents[2]
def _sources():
    graph=json.loads((ROOT/"research/ecosystems/seed_graph.json").read_text())
    moments=json.loads((ROOT/"apps/web/src/data/industry-milestones.json").read_text())
    return graph,moments

def test_all_curated_milestones_have_graph_nodes_and_source():
    graph,moments=_sources()
    valid={n["id"] for n in graph["nodes"]}
    ids=set()
    for row in moments["milestones"]:
        assert row["id"] not in ids
        ids.add(row["id"])
        assert set(row["node_ids"]).issubset(valid)
        assert row["source_url"].startswith("https://")
        assert row["fact_type"] in ("issuer_technical_claim","official_process_record","official_standards_workgroup_record")
        assert row["published_at"] <= moments["as_of"]
        assert len(row["next_trigger"])>=12
        assert row["date_precision"] in ("day","month","year")
    assert len(ids)>=5

def test_ballot_approval_does_not_claim_final_standard_publication():
    _,moments=_sources()
    ieee=[x for x in moments["milestones"] if x["id"].startswith("ieee-8023dj")]
    assert len(ieee)==3
    assert [x["values"][0]["value"] for x in sorted(ieee,key=lambda x:x["published_at"])]==[77,86,97]
    assert "아직" in max(ieee,key=lambda x:x["published_at"])["fact"]
