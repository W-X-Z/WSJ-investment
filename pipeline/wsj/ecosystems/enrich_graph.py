"""Conservative enrichment of historical evidence into a reviewable technical graph index.

This DOES NOT create confirmed supply edges or validated claims. It maps source
metadata to pre-defined ontology nodes using curated lexical aliases, preserves
date precision and provenance, and produces a human-review queue for co-mentions
and quantitative abstract passages. All outputs deterministic, no LLM cost.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BACKFILL = ROOT / "research" / "backfill"
GRAPH = ROOT / "research" / "ecosystems" / "seed_graph.json"
ALIASES = ROOT / "research" / "ecosystems" / "node_aliases.json"
WEB_INDEX = ROOT / "apps" / "web" / "src" / "data" / "graph-evidence-index.json"
REPORT = ROOT / "research" / "enriched" / "summary.json"
CO_MENTIONS = ROOT / "research" / "enriched" / "relation-candidates.json"

# Patterns deliberately exclude bare Mbps shorthand without a unit and exclude
# speculative performance extrapolation. This is only a quote candidate.
METRIC = re.compile(
    r"(?<![a-zA-Z0-9.])"
    r"(?P<value>\d{1,4}(?:,\d{3})*(?:\.\d{1,4})?)"
    r"\s*(?P<unit>Tb/s|Gb/s|Gbps|Tbps|GHz|MHz|kHz|kW|MW|GW|mW|W|"
    r"VDC|V|µm|μm|um|nm|mm|dBm|dB|ppm|wph|%|mA|kA|A)"
    r"(?=$|[^a-zA-Z0-9])", re.IGNORECASE,
)
UNITS = {"μm":"um","µm":"um","Gbps":"Gb/s","Tbps":"Tb/s"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STOP_ALIASES = {
    "power", "memory", "laser", "semiconductor", "thermal", "packaging",
    "inspection", "fiber", "current", "data center", "wafer", "converter",
}

def normalize(text: str) -> str:
    """Spaces and hyphens match consistently; retain units/slashes for metrics."""
    return re.sub(r"\s+", " ", str(text).lower().replace("‐","-").replace("–","-")).strip()

def alias_pattern(alias: str) -> re.Pattern[str]:
    # Curated literal terms, with word boundaries to avoid "sic" in "basic".
    token = re.escape(normalize(alias)).replace(r"\ ",r"[\s\-]+")
    return re.compile(r"(?<![a-zA-Z0-9])"+token+r"(?![a-zA-Z0-9])",re.IGNORECASE)

def lexicon(graph: dict, index: dict) -> dict[str, list[tuple[str,re.Pattern[str]]]]:
    nodes={n["id"] for n in graph["nodes"]}
    output={}
    for node_id,terms in index.get("aliases",{}).items():
        if node_id not in nodes:
            raise ValueError("Alias points to non-existent graph node: "+node_id)
        curated=[]
        for term in terms:
            normalized=normalize(term)
            if normalized in STOP_ALIASES or len(normalized)<4:
                continue
            if normalized not in [x[0] for x in curated]:
                curated.append((normalized,alias_pattern(normalized)))
        if curated:
            output[node_id]=curated
    return output

def load_sources(folder:Path):
    for eco in ("hbm","optics","power"):
        path=folder/(eco+".jsonl")
        if not path.exists():
            raise FileNotFoundError("Required historical corpus absent: "+str(path))
        with path.open(encoding="utf-8") as reader:
            for line_no,line in enumerate(reader,1):
                if not line.strip():continue
                try:
                    row=json.loads(line)
                    if row.get("ecosystem")!=eco or not row.get("id"):
                        raise ValueError("unexpected historical ecosystem/id")
                    yield row
                except (ValueError,TypeError) as exc:
                    raise ValueError(f"Invalid historical source at {path}:{line_no}: {exc}") from exc

def quantitative_passages(text:str, matches:list[tuple[int,int]], max_count:int=5) -> list[dict]:
    """Attach numeric substrings to nearby matched technical phrases ONLY.

    Measurements extracted from bibliographic text are candidates, not audited
    results. Document may discuss a prior benchmark, simulation or aspiration.
    """
    output=[];known=set()
    for metric in METRIC.finditer(text):
        value=float(metric.group("value").replace(",",""))
        if value>10_000_000 or value<0:
            continue
        if not matches or min(min(abs(metric.start()-a),abs(metric.start()-b)) for a,b in matches)>145:
            continue
        unit=UNITS.get(metric.group("unit"),metric.group("unit"))
        key=(metric.start(),unit)
        if key in known:continue
        known.add(key)
        lo=max(0,metric.start()-85);hi=min(len(text),metric.end()+100)
        output.append({
            "value":value,"unit":unit,"literal":metric.group(0),
            "passage":re.sub(r"\s+"," ",text[lo:hi]),
            "passage_location":"indexed_abstract_or_title",
            "verification":"unverified_numeric_mention",
            "conditions_verified":False,
        })
        if len(output)>=max_count:break
    return output

def links(row:dict, lex:dict) -> list[dict]:
    title=normalize(row.get("title",""))[:300]
    abstract=normalize(row.get("excerpt",""))[:620]
    result=[]
    for node_id,aliases in lex.items():
        hits_title=[];hits_abstract=[]
        positions=[]
        for alias,pattern in aliases:
            a=pattern.search(title)
            b=pattern.search(abstract)
            if a:hits_title.append(alias)
            if b:
                hits_abstract.append(alias);positions.append(b.span())
        # Require title match for short aliases (or multiple distinct abstract
        # aliases), so generic body mention does not fan out to every node.
        if not hits_title and len(set(hits_abstract))<2:
            continue
        rank=min(30,6*len(set(hits_title))+2*len(set(hits_abstract)))
        if any(" " in x or "-" in x for x in hits_title):rank+=2
        if rank<4:continue
        metrics=quantitative_passages(abstract,positions)
        if not metrics:
            title_positions=[m.span() for _,pat in aliases for m in list(pat.finditer(title))[:1]]
            metrics=quantitative_passages(title,title_positions,max_count=3)
        result.append({
            "node_id":node_id,"rank":rank,"title_matches":sorted(set(hits_title)),
            "abstract_matches":sorted(set(hits_abstract)),
            "measurement_candidates":metrics,
            "match_reason":"lexical_title_or_multi_alias_abstract_only",
            "semantic_validation":"NOT_PERFORMED",
        })
    # Limit each source to a few *research leads*, not dense invented edges.
    return sorted(result,key=lambda x:(-x["rank"],x["node_id"]))[:7]

def as_of_ok(row:dict,as_of:str)->bool:
    day=row.get("published_at")
    return bool(isinstance(day,str) and DATE.fullmatch(day) and day<=as_of
                and row.get("historical_backfill") is True)

def slim_source(row:dict,match:dict)->dict:
    return {
        "id":row["id"],"canonical_id":row.get("canonical_id"),"title":row.get("title"),
        "published_at":row["published_at"],"published_precision":row.get("published_precision","unknown"),
        "first_seen_at":row.get("first_seen_at"),"source":row["source"],
        "source_group":row.get("source_group"),"url":row["url"],
        "excerpt":row.get("excerpt","")[:290],
        "rank":match["rank"],"matched_terms":sorted(set(match["title_matches"]+match["abstract_matches"])),
        "metric_candidates":match["measurement_candidates"][:4],
        "verification_status":"index_match_only", "source_independence_verified":False,
        "historical_investor_observation_unverified":True,
    }

def build(*,folder:Path,graph_path:Path,alias_path:Path,as_of:str,source_cap:int=16)->tuple[dict,dict,dict]:
    if not DATE.fullmatch(as_of):raise ValueError("as_of requires YYYY-MM-DD")
    graph=json.loads(graph_path.read_text(encoding="utf-8"))
    aliases=json.loads(alias_path.read_text(encoding="utf-8"))
    lx=lexicon(graph,aliases)
    node_data={n["id"]:{"node_id":n["id"],"name":n["label"],"kind":n["kind"],
                         "total_document_leads":0,
                         "year_counts":{},"source_counts":{},"sources":[],
                         "measurement_candidates":[]}
               for n in graph["nodes"]}
    buckets=defaultdict(list)
    pairs=defaultdict(lambda:{"count":0,"years":set(),"references":[]})
    total=0;rejected_future=0;linked=0;source_ids=set();seen_linked=set()
    for source in load_sources(folder):
        total+=1
        if not as_of_ok(source,as_of):
            rejected_future+=1;continue
        dedupe=(source["ecosystem"],source.get("canonical_id") or source["id"])
        if dedupe in source_ids:continue
        source_ids.add(dedupe)
        found=links(source,lx)
        if not found:continue
        linked+=1
        for match in found:
            n=node_data[match["node_id"]]
            key=(dedupe,match["node_id"])
            if key in seen_linked:continue
            seen_linked.add(key)
            n["total_document_leads"]+=1
            year=source["published_at"][:4]
            n["year_counts"][year]=n["year_counts"].get(year,0)+1
            group=source.get("source_group") or source["source"]
            n["source_counts"][group]=n["source_counts"].get(group,0)+1
            record=slim_source(source,match)
            buckets[match["node_id"]].append(record)
        # A co-mention is a review prompt, NEVER a proposed graph edge.
        ids=sorted(x["node_id"] for x in found)
        for i,a in enumerate(ids):
            for b in ids[i+1:]:
                if node_data[a]["kind"]==node_data[b]["kind"]:continue
                if node_data[a]["kind"]=="ecosystem" or node_data[b]["kind"]=="ecosystem":continue
                key=(a,b)
                p=pairs[key];p["count"]+=1;p["years"].add(source["published_at"][:4])
                if len(p["references"])<3:p["references"].append({
                    "source_id":source["id"],"url":source["url"],
                    "title":source["title"][:200],"published_at":source["published_at"]})
    for id,n in node_data.items():
        # Balanced per-year selection avoids hiding early inflection evidence.
        top=sorted(buckets[id],key=lambda x:(-x["rank"],x["published_at"]))[:source_cap]
        annual=[]
        for y in sorted(n["year_counts"]):
            choices=sorted((x for x in buckets[id] if x["published_at"].startswith(y)),
                key=lambda x:-x["rank"])
            annual.extend(choices[:2])
        unique={x["id"]:x for x in annual+top}
        n["sources"]=sorted(unique.values(),key=lambda x:(-x["rank"],x["published_at"]))[:source_cap+12]
        all_metrics=[]
        for row in n["sources"]:
            for m in row["metric_candidates"]:
                all_metrics.append({"source_id":row["id"],"published_at":row["published_at"],
                                    "source_url":row["url"],**m})
        n["measurement_candidates"]=all_metrics[:16]
    # Report only co-mentions that recur; do not mutate canonical graph.
    relation_candidates=[]
    for (a,b),p in pairs.items():
        if p["count"]<2:continue
        relation_candidates.append({
            "left_node_id":a,"right_node_id":b,"shared_source_count":p["count"],
            "years":sorted(p["years"]), "example_documents":p["references"],
            "status":"lexical_co_mention_not_supply_relation",
            "should_create_graph_edge":False,
            "review_prompt":"Does source text explicitly assert a causal relation? If not, keep separate from tech_edges.",
        })
    relation_candidates.sort(key=lambda x:(-x["shared_source_count"],x["left_node_id"],x["right_node_id"]))
    summary={
        "as_of":as_of,"total_historical_records_read":total,
        "unique_valid_sources":len(source_ids),"excluded_future_or_invalid":rejected_future,
        "documents_with_ontology_matches":linked,
        "ontology_nodes":len(node_data),
        "nodes_with_at_least_one_match":sum(bool(x["total_document_leads"]) for x in node_data.values()),
        "numeric_mentions_requiring_validation":sum(len(x["measurement_candidates"]) for x in node_data.values()),
        "co_mention_pairs_requiring_review":len(relation_candidates),
        "independent_factual_correlations_confirmed":0,"new_confirmed_supply_edges":0,
        "interpretation":"Lexical bibliographic evidence links and numeric quote candidates are NOT verified technological breakthroughs, customer adoption, or investment ideas.",
        "limitations":["Metadata/abstract only, no full-text scientific fact verification.",
                        "Historical publication dates do not establish historical collector access.",
                        "Count trends are bibliographic visibility, not commercialization or scientific efficacy.",
                        "Co-mentions never automatically create technology, supplier, or customer relations."],
    }
    payload={"schema_version":1,"summary":summary,"nodes":node_data}
    queue={"summary":{"relation_pairs":len(relation_candidates),"status":"review_only"},
           "candidates":relation_candidates[:150]}
    return payload,summary,queue

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--backfill-dir",type=Path,default=BACKFILL)
    parser.add_argument("--graph",type=Path,default=GRAPH)
    parser.add_argument("--aliases",type=Path,default=ALIASES)
    parser.add_argument("--web-index",type=Path,default=WEB_INDEX)
    parser.add_argument("--report",type=Path,default=REPORT)
    parser.add_argument("--relations",type=Path,default=CO_MENTIONS)
    parser.add_argument("--as-of",default=datetime.now(timezone.utc).date().isoformat())
    args=parser.parse_args()
    data,summary,relations=build(folder=args.backfill_dir,graph_path=args.graph,
         alias_path=args.aliases,as_of=args.as_of)
    for path,payload in ((args.web_index,data),(args.report,summary),(args.relations,relations)):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if not summary["unique_valid_sources"]:
        raise RuntimeError("No historical sources found; cannot publish empty graph index")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
