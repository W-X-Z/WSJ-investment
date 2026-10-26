"""Evidence-aware ecosystem impact explorer and historical event replay.

This is a research proof of concept: it DOES NOT infer a confirmed revenue
beneficiary, evaluate security prices, or send notifications.
Run from pipeline/: python -m wsj.ecosystems.impact
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_GRAPH = Path(__file__).resolve().parents[3] / "research" / "ecosystems" / "seed_graph.json"
PATH_RELATIONS = {"drives_requirement", "creates_bottleneck", "mitigated_by", "offered_by"}
WARNING_STAGES = {
    "technical_inference", "technology_option", "vendor_claim",
    "unverified_hypothesis", "scenario", "standard_draft", "standardization_in_progress",
}


def _public_by(event: dict[str, Any], as_of: str) -> bool:
    """Conservative dates: YYYY-MM means end-of-month; unknown uses checked_as_of."""
    published = event.get("published_at")
    if not published:
        checked = event.get("checked_as_of")
        return bool(checked and date.fromisoformat(checked) <= date.fromisoformat(as_of))
    precision = event.get("date_precision")
    if precision == "month":
        year, month = map(int, published.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        event_date = date(year, month, last_day)
    elif precision == "day":
        event_date = date.fromisoformat(published)
    else:
        return False
    return event_date <= date.fromisoformat(as_of)


def validate_graph(graph: dict[str, Any]) -> None:
    nodes = {n["id"] for n in graph["nodes"]}
    if len(nodes) != len(graph["nodes"]):
        raise ValueError("Duplicate node IDs")
    for edge in graph["edges"]:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            raise ValueError(f"Dangling edge: {edge['id']}")
        if edge["relation"] not in PATH_RELATIONS | {"substitutes_for"}:
            raise ValueError(f"Unknown edge semantics: {edge['id']}")
        if not edge.get("evidence") or not all(
            item.get("url", "").startswith("https://") for item in edge["evidence"]
        ):
            raise ValueError(f"Graph edge without HTTPS provenance: {edge['id']}")
    for event in graph["events"]:
        if event["target_id"] not in nodes:
            raise ValueError(f"Dangling event target: {event['id']}")
        if not event.get("source_url", "").startswith("https://"):
            raise ValueError(f"Event without source: {event['id']}")
        if event.get("date_precision") not in {"day", "month", "unknown"}:
            raise ValueError(f"Unknown date precision: {event['id']}")
    if len({w["id"] for w in graph["watches"]}) != len(graph["watches"]):
        raise ValueError("Duplicate watch IDs")
    for watch in graph["watches"]:
        if watch["target_id"] not in nodes:
            raise ValueError(f"Dangling watch: {watch['id']}")


def event_fingerprint(event: dict[str, Any]) -> str:
    """Stable source/content identity, independent of when the monitor ingested it."""
    canonical = json.dumps(
        {"url": event["source_url"], "published": event.get("published_at"),
         "source_id": event["source_id"], "target": event["target_id"],
         "event_type": event["type"], "data": event.get("data", {})},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def influence_paths(graph: dict[str, Any], start: str, max_depth: int = 6) -> list[dict[str, Any]]:
    """Explore documented and hypothesized paths, never assert confirmed customers."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph["edges"]:
        if edge["relation"] in PATH_RELATIONS and edge["polarity"] != "negative":
            outgoing[edge["from"]].append(edge)
    queue = deque([(start, [start], [], False)])
    found: list[dict[str, Any]] = []
    seen_paths: set[tuple[str, ...]] = set()
    while queue:
        current, visited, edges, speculative = queue.popleft()
        if nodes[current]["kind"] == "company" and edges:
            key = tuple(visited)
            if key not in seen_paths:
                seen_paths.add(key)
                found.append({
                    "company": nodes[current]["label"], "company_id": current,
                    "path": [{"node_id": n, "label": nodes[n]["label"]} for n in visited],
                    "edge_ids": [e["id"] for e in edges],
                    "confidence": "requires_validation" if speculative else "documented_capability_only",
                    "warning": "Possible ecosystem exposure, NOT proven customer revenue or investable alpha.",
                })
            continue
        if len(edges) >= max_depth:
            continue
        for edge in outgoing.get(current, []):
            if edge["to"] in visited:
                continue
            is_hypothesis = speculative or edge["stage"] in WARNING_STAGES or edge["polarity"] == "conditional"
            queue.append((edge["to"], visited + [edge["to"]], edges + [edge], is_hypothesis))
    return found


WATCH_EVENT_TYPES = {
    "watch:hbm_orders": {"commercial_order", "repeat_order"},
    "watch:optic_standard": {"standard_status"},
    "watch:power_standard": {"standard_revision"},
}


def possible_watch_matches(event: dict[str, Any], graph: dict[str, Any]) -> list[dict]:
    matches = []
    for watch in graph["watches"]:
        if watch["target_id"] != event["target_id"]:
            continue
        if event["type"] in WATCH_EVENT_TYPES.get(watch["id"], set()):
            matches.append({
                "watch": watch["id"], "status": "candidate_requires_rule_and_source_review",
                "reason": "The event type aligns with a tracked subject; baseline/delta and independent confirmation have not been checked.",
                "missing_confirmation": watch["confirmations_needed"],
            })
    return matches


def replay(graph: dict[str, Any], as_of: str) -> dict[str, Any]:
    validate_graph(graph)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in graph["events"]:
        if not _public_by(event, as_of):
            continue
        fingerprint = event_fingerprint(event)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        paths = influence_paths(graph, event["target_id"])
        results.append({
            "event_id": event["id"], "published_at": event.get("published_at"),
            "published_precision": event["date_precision"], "source_url": event["source_url"],
            "event_fingerprint": fingerprint,
            "summary": event["summary"],
            "possible_company_paths": paths,
            "watch_candidates": possible_watch_matches(event, graph),
            "source_independence": "NOT ESTABLISHED: multiple press reproductions count as one source group",
            "asof_integrity": "Contemporary evidence must be re-validated. Graph is 2026 ontology, not historic graph snapshot.",
        })
    return {
        "as_of": as_of, "research_only": True, "seed_graph_version": graph["schema_version"],
        "warnings": [
            "The graph is curated retrospectively. NO point-in-time alpha backtest or return calculation.",
            "An implication path is a research candidate and must not be called a validated supplier relationship.",
            "Monitors are definitions only. No background polling or active notifications are set up.",
        ],
        "events": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Supply-chain graph impact research replay")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--as-of", default="2026-10-26")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    output = json.dumps(replay(graph, args.as_of), ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
