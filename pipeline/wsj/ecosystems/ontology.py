"""온톨로지(닫힌 어휘) 로더·검증·린트. ADR-0012.

    python -m wsj.ecosystems.ontology --check            # 스키마 위반이면 exit 1
    python -m wsj.ecosystems.ontology --report           # 통계·린트 경고

seed_graph.json 의 모든 노드 kind / 관계 relation / 근거 evidence_tier 는 research/ecosystems/ontology.json
에 정의된 값만 쓸 수 있고, 관계는 정의역(domain)→치역(range) 제약을 지킨다. 린트는 "틀린 건 아니지만 약한" 것
(단일 URL 이 떠받치는 관계 수, 추론만으로 이어진 기업, 고객 없는 생태계)을 경고한다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESEARCH_DIR = Path(__file__).resolve().parents[3] / "research" / "ecosystems"
ONTOLOGY_PATH = RESEARCH_DIR / "ontology.json"
GRAPH_PATH = RESEARCH_DIR / "seed_graph.json"


def clean_name(label: str) -> str:
    """'NVIDIA (NVDA) — HBM·광·전력 공통 수요처' → 'NVIDIA', 'Samsung Electronics (KRX 005930, 비SEC)' → 'Samsung Electronics'."""
    import re

    s = re.split(r"\s+[—–-]\s+", label, maxsplit=1)[0]
    return re.sub(r"\s*\(.*\)\s*$", "", s).strip() or label


def load_ontology(path: Path = ONTOLOGY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_graph(path: Path = GRAPH_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def edge_confidence(edge: dict[str, Any], onto: dict[str, Any]) -> float:
    """근거 등급의 사전 확률 × 극성 보정. 여러 근거가 있으면 가장 높은 등급 + 독립 출처 보너스(최대 +0.05)."""
    tiers = onto["evidence_tiers"]
    best = tiers.get(edge.get("evidence_tier", ""), {}).get("confidence", 0.25)
    hosts = {_host(ev.get("url", "")) for ev in edge.get("evidence", [])}
    bonus = min(0.05, 0.025 * max(0, len(hosts) - 1))
    conf = min(0.99, best + bonus)
    if edge.get("polarity") == "conditional":
        conf *= 0.8
    return round(conf, 3)


def _host(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0].lower().removeprefix("www.")


def validate(graph: dict[str, Any], onto: dict[str, Any]) -> Report:
    rep = Report()
    kinds = onto["node_kinds"]
    preds = onto["predicates"]
    tiers = onto["evidence_tiers"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    if len(nodes) != len(graph["nodes"]):
        rep.errors.append("duplicate node ids")
    for n in graph["nodes"]:
        if n.get("kind") not in kinds:
            rep.errors.append(f"node {n['id']}: unknown kind {n.get('kind')!r}")
        if not n.get("label"):
            rep.errors.append(f"node {n['id']}: missing label")
        if n.get("kind") not in ("ecosystem",) and not n.get("ecosystem"):
            rep.warnings.append(f"node {n['id']}: no ecosystem membership")
        mat = n.get("maturity")
        if mat is not None:
            mf = onto.get("maturity_field", {})
            if n.get("kind") not in mf.get("applies_to", []):
                rep.errors.append(f"node {n['id']}: maturity not allowed on kind {n.get('kind')}")
            elif mat.get("stage") not in onto.get("maturity_stages", {}):
                rep.errors.append(f"node {n['id']}: unknown maturity stage {mat.get('stage')!r}")
            elif not str(mat.get("evidence_url", "")).startswith("https://") or not mat.get("as_of"):
                rep.errors.append(f"node {n['id']}: maturity needs as_of and https evidence_url")
        if n.get("kind") == "company":
            if n.get("role") not in onto["company_fields"]["role"]:
                rep.errors.append(f"company {n['id']}: role must be one of {onto['company_fields']['role']}")
            listing = n.get("listing")
            if not isinstance(listing, dict) or "filer_type" not in listing:
                rep.errors.append(f"company {n['id']}: listing{{ticker,exchange,cik,filer_type}} required")

    edge_ids: Counter[str] = Counter(e["id"] for e in graph["edges"])
    for eid, c in edge_ids.items():
        if c > 1:
            rep.errors.append(f"duplicate edge id {eid}")
    url_edges: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]:
        for f in onto["edge_required_fields"]:
            if f not in e:
                rep.errors.append(f"edge {e.get('id')}: missing {f}")
        if e.get("from") not in nodes or e.get("to") not in nodes:
            rep.errors.append(f"edge {e.get('id')}: dangling endpoint")
            continue
        p = preds.get(e.get("relation"))
        if p is None:
            rep.errors.append(f"edge {e['id']}: unknown relation {e.get('relation')!r}")
            continue
        fk, tk = nodes[e["from"]]["kind"], nodes[e["to"]]["kind"]
        if fk not in p["domain"] or tk not in p["range"]:
            rep.errors.append(f"edge {e['id']}: {fk} -{e['relation']}-> {tk} violates domain/range")
        tier = e.get("evidence_tier")
        if tier not in tiers:
            rep.errors.append(f"edge {e['id']}: unknown evidence_tier {tier!r}")
        elif "min_tier" in p and tiers[tier]["confidence"] < tiers[p["min_tier"]]["confidence"]:
            rep.errors.append(f"edge {e['id']}: {e['relation']} needs tier >= {p['min_tier']}, got {tier}")
        if e.get("polarity") not in onto["polarity"]:
            rep.errors.append(f"edge {e['id']}: bad polarity {e.get('polarity')!r}")
        evs = e.get("evidence") or []
        if not evs:
            rep.errors.append(f"edge {e['id']}: no evidence")
        for ev in evs:
            for f in onto["evidence_required_fields"]:
                if f not in ev:
                    rep.errors.append(f"edge {e['id']}: evidence missing {f}")
            if not str(ev.get("url", "")).startswith("https://"):
                rep.errors.append(f"edge {e['id']}: evidence url must be https")
            url_edges[ev.get("url", "")].append(e["id"])

    for row in graph.get("events", []) + graph.get("watches", []):
        if row.get("target_id") not in nodes:
            rep.errors.append(f"{row.get('id')}: target_id {row.get('target_id')!r} not in graph")

    # 린트
    lint = onto["lint_rules"]
    for url, ids in url_edges.items():
        if len(ids) > lint["max_edges_per_source_url"]:
            rep.warnings.append(f"single source carries {len(ids)} edges: {url}")
    by_eco_customer: Counter[str] = Counter()
    for n in graph["nodes"]:
        if n.get("kind") == "company" and n.get("role") in ("customer", "both"):
            for eco in [n.get("ecosystem", "")] + list(n.get("also_in", [])):
                by_eco_customer[eco] += 1
    for n in graph["nodes"]:
        if n["kind"] == "ecosystem":
            eco = n["id"].split(":", 1)[1]
            if lint["every_ecosystem_needs_customer"] and by_eco_customer.get(eco, 0) == 0:
                rep.warnings.append(f"ecosystem {eco}: no customer-role company node")
    if lint["product_must_have_implements_and_offered_by"]:
        rel_from: dict[str, set[str]] = defaultdict(set)
        for e in graph["edges"]:
            rel_from[e["from"]].add(e["relation"])
        for n in graph["nodes"]:
            if n["kind"] == "product" and not {"implements", "offered_by"} <= rel_from[n["id"]]:
                rep.warnings.append(f"product {n['id']}: needs both implements and offered_by edges")
    # 기업에 닿는 경로가 추론/가설뿐인 경우
    weak_only = []
    for n in graph["nodes"]:
        if n["kind"] != "company":
            continue
        inc = [e for e in graph["edges"] if e["to"] == n["id"] or e["from"] == n["id"]]
        if inc and all(
            tiers[e["evidence_tier"]]["confidence"] < 0.6 for e in inc if e.get("evidence_tier") in tiers
        ):
            weak_only.append(n["id"])
    if weak_only:
        rep.warnings.append(f"companies connected only by inference/hypothesis edges: {weak_only}")

    rep.stats = {
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "node_kinds": dict(Counter(n["kind"] for n in graph["nodes"])),
        "relations": dict(Counter(e["relation"] for e in graph["edges"])),
        "evidence_tiers": dict(Counter(e.get("evidence_tier") for e in graph["edges"])),
        "polarity": dict(Counter(e.get("polarity") for e in graph["edges"])),
        "distinct_source_urls": len(url_edges),
        "events": len(graph.get("events", [])),
        "watches": len(graph.get("watches", [])),
        "companies": {
            n["id"]: {
                "role": n.get("role"),
                "in_universe": n.get("in_universe"),
                "size_band": n.get("size_band"),
            }
            for n in graph["nodes"]
            if n["kind"] == "company"
        },
    }
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, default=GRAPH_PATH)
    ap.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    rep = validate(load_graph(args.graph), load_ontology(args.ontology))
    if args.report or not args.check:
        print(json.dumps(rep.stats, ensure_ascii=False, indent=1))
        for w in rep.warnings:
            print("WARN", w)
    for e in rep.errors:
        print("ERROR", e)
    print(f"{'OK' if rep.ok else 'FAIL'}: {len(rep.errors)} errors, {len(rep.warnings)} warnings")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
