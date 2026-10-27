"""방향·근거 가중 영향 전파 (v0.3). ADR-0012.

"노드 X 에 변화가 생기면 어느 기업이, 어느 경로로, 얼마나 확실하게 영향받는가" 를 답한다.

- 방향: ontology.json 의 술어별 direction 을 따른다. demand_to_supply 는 from→to, supply_to_demand 는 to→from
  (implements / supplied_to / qualifying_with 를 거꾸로 타고 올라가 고객·제품에 닿는다), none 은 전파하지 않는다
  (competes_with / succeeds 는 경로가 아니라 맥락).
- 가중: 경로 신뢰도 = Π edge.confidence (근거 등급 사전확률 × 극성 보정). 부정 극성(displaces/defers)을 지나면 부호가 뒤집힌다.
- 결과는 "노출 후보" 다. supplied_to 이상 + 매출 노출 공시가 없으면 수혜를 확정하지 않는다 (경고 문구 유지).

    python -m wsj.ecosystems.impact --node tech:hybrid_bond
    python -m wsj.ecosystems.impact --as-of 2026-10-26   # 이벤트 리플레이
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

from wsj.ecosystems.ontology import ONTOLOGY_PATH, edge_confidence, load_ontology, validate

DEFAULT_GRAPH = Path(__file__).resolve().parents[3] / "research" / "ecosystems" / "seed_graph.json"
NON_PATH_RELATIONS = {"competes_with", "succeeds", "invests_in", "substitutes_for"}
TIER_BAND = {  # 경로 신뢰도 → 사람이 읽는 라벨
    0.6: "documented",
    0.35: "claimed",
    0.0: "inferred",
}


def _public_by(event: dict[str, Any], as_of: str) -> bool:
    """보수적 날짜: YYYY-MM 은 월말, 미상은 checked_as_of."""
    published = event.get("published_at")
    if not published:
        checked = event.get("checked_as_of")
        return bool(checked and date.fromisoformat(checked) <= date.fromisoformat(as_of))
    precision = event.get("date_precision")
    if precision == "month":
        year, month = map(int, published.split("-"))
        event_date = date(year, month, calendar.monthrange(year, month)[1])
    elif precision == "day":
        event_date = date.fromisoformat(published)
    else:
        return False
    return event_date <= date.fromisoformat(as_of)


def validate_graph(graph: dict[str, Any], onto: dict[str, Any] | None = None) -> None:
    rep = validate(graph, onto or load_ontology(ONTOLOGY_PATH))
    if rep.errors:
        raise ValueError("; ".join(rep.errors[:5]))
    for event in graph.get("events", []):
        if event.get("date_precision") not in {"day", "month", "unknown"}:
            raise ValueError(f"Unknown date precision: {event['id']}")


def event_fingerprint(event: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "url": event["source_url"],
            "published": event.get("published_at"),
            "source_id": event["source_id"],
            "target": event["target_id"],
            "event_type": event["type"],
            "data": event.get("data", {}),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _band(conf: float) -> str:
    for threshold, label in sorted(TIER_BAND.items(), reverse=True):
        if conf >= threshold:
            return label
    return "inferred"


def _adjacency(
    graph: dict[str, Any], onto: dict[str, Any]
) -> dict[str, list[tuple[str, dict[str, Any], str]]]:
    """node → [(next_node, edge, hop_kind)]. hop_kind: 'forward' | 'reverse'."""
    preds = onto["predicates"]
    adj: dict[str, list[tuple[str, dict[str, Any], str]]] = defaultdict(list)
    for e in graph["edges"]:
        rel = e["relation"]
        if rel in NON_PATH_RELATIONS:
            continue
        direction = preds.get(rel, {}).get("direction", "none")
        if direction == "demand_to_supply":
            adj[e["from"]].append((e["to"], e, "forward"))
            if rel in ("adopts", "defers"):  # 기술 → 채택 고객 (역방향으로 고객에 닿음)
                adj[e["to"]].append((e["from"], e, "reverse"))
        elif direction == "supply_to_demand":
            adj[e["to"]].append((e["from"], e, "reverse"))
    return adj


def influence_paths(
    graph: dict[str, Any],
    start: str,
    max_depth: int = 6,
    onto: dict[str, Any] | None = None,
    min_confidence: float = 0.02,
) -> list[dict[str, Any]]:
    """start 에서 방향을 따라 기업 노드까지의 경로. 기업에 닿으면 멈춘다 (기업을 통과하지 않는다)."""
    onto = onto or load_ontology(ONTOLOGY_PATH)
    nodes = {n["id"]: n for n in graph["nodes"]}
    if start not in nodes:
        raise KeyError(start)
    adj = _adjacency(graph, onto)
    for e in graph["edges"]:
        e.setdefault("confidence", edge_confidence(e, onto))
    start_node = nodes[start]
    start_eco = start.removeprefix("eco:") if start_node["kind"] == "ecosystem" else start_node.get("ecosystem")

    def same_program(company_id: str) -> bool:
        """about 이 없는 기업↔기업 관계는 시작 노드와 같은 생태계의 기업으로만 탄다 (전력 공급사가 CPO 경로로 새지 않게)."""
        c = nodes[company_id]
        return not start_eco or start_eco in {c.get("ecosystem"), *(c.get("also_in") or [])}

    queue = deque([(start, [start], [], 1.0, 1)])
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    while queue:
        cur, visited, edges, conf, sign = queue.popleft()
        if nodes[cur]["kind"] == "company" and edges:
            key = tuple(visited)
            if key in seen:
                continue
            seen.add(key)
            # 고객 기업에서는 확인된 거래·인증 관계를 거꾸로 타고 공급사까지 한 번 더 간다
            for nxt, edge, hop in adj.get(cur, ()):
                chained = edges[-1]["relation"] in ("supplied_to", "qualifying_with")
                scoped = (
                    edge.get("about") in visited if edge.get("about") else (not chained and same_program(nxt))
                )  # 다른 프로그램의 공급사로 새지 않게 (about 없는 관계는 같은 생태계·한 번만)
                if (
                    hop == "reverse"
                    and scoped
                    and edge["relation"] in ("supplied_to", "qualifying_with")
                    and nxt not in visited
                    and len(edges) < max_depth
                ):
                    nconf = conf * edge["confidence"]
                    if nconf >= min_confidence:
                        queue.append((nxt, visited + [nxt], edges + [edge], nconf, sign))
            last = edges[-1]
            if last["relation"] in ("adopts", "defers"):
                role = "adopter"
            elif last["relation"] in ("supplied_to", "qualifying_with"):
                role = "customer" if last["to"] == cur else "supplier_via_customer"
            else:
                role = "supplier"
            weakest = min(edges, key=lambda e: e["confidence"])
            found.append(
                {
                    "company": nodes[cur]["label"],
                    "company_id": cur,
                    "role_on_path": role,
                    "listing": nodes[cur].get("listing"),
                    "in_universe": nodes[cur].get("in_universe", False),
                    "size_band": nodes[cur].get("size_band"),
                    "path": [
                        {"node_id": n, "label": nodes[n]["label"], "kind": nodes[n]["kind"]} for n in visited
                    ],
                    "edge_ids": [e["id"] for e in edges],
                    "relations": [e["relation"] for e in edges],
                    "confidence": round(conf, 3),
                    "band": _band(conf),
                    "sign": sign,
                    "weakest_edge": {
                        "id": weakest["id"],
                        "relation": weakest["relation"],
                        "tier": weakest.get("evidence_tier"),
                        "confidence": weakest["confidence"],
                    },
                    "warning": "Possible ecosystem exposure, NOT proven customer revenue or investable alpha.",
                }
            )
            continue
        if len(edges) >= max_depth:
            continue
        for nxt, edge, _hop in adj.get(cur, ()):
            if nxt in visited:
                continue
            nconf = conf * edge["confidence"]
            if nconf < min_confidence:
                continue
            nsign = -sign if edge.get("polarity") == "negative" else sign
            queue.append((nxt, visited + [nxt], edges + [edge], nconf, nsign))
    found.sort(key=lambda p: -p["confidence"])
    return found


def impact_report(
    graph: dict[str, Any], node_id: str, max_depth: int = 6, onto: dict[str, Any] | None = None
) -> dict[str, Any]:
    """기업별로 집계: 가장 확실한 경로, 부호, 가장 약한 고리, 상장 정보. 대체 기술 시나리오 동봉."""
    onto = onto or load_ontology(ONTOLOGY_PATH)
    nodes = {n["id"]: n for n in graph["nodes"]}
    paths = influence_paths(graph, node_id, max_depth, onto)
    by_company: dict[str, dict[str, Any]] = {}
    for p in paths:
        c = by_company.setdefault(
            p["company_id"],
            {
                "company": p["company"],
                "company_id": p["company_id"],
                "listing": p["listing"],
                "in_universe": p["in_universe"],
                "size_band": p["size_band"],
                "best_confidence": 0.0,
                "band": "inferred",
                "net_sign": 0,
                "paths": [],
            },
        )
        c["paths"].append(p)
        c["net_sign"] += p["sign"] * p["confidence"]
        if p["confidence"] > c["best_confidence"]:
            c["best_confidence"], c["band"], c["best_path"] = p["confidence"], p["band"], p
    for c in by_company.values():
        c["net_sign"] = round(c["net_sign"], 3)
        c["direction"] = (
            "positive" if c["net_sign"] > 0.01 else ("negative" if c["net_sign"] < -0.01 else "mixed")
        )
        c["paths"] = c["paths"][:3]
        c["upgrade_needed"] = (
            "supplied_to(official_issuer 이상) + 매출 노출 공시"
            if c["band"] != "documented"
            else "매출 노출·수량·마진 공시"
        )
    ranked = sorted(by_company.values(), key=lambda c: -c["best_confidence"])
    return {
        "node": {"id": node_id, "label": nodes[node_id]["label"], "kind": nodes[node_id]["kind"]},
        "companies": ranked,
        "substitution_risks": displacement_scenarios(graph, node_id, onto=onto),
        "caveat": "경로 신뢰도는 근거 등급의 곱이다. 'documented' 라도 기술 보유·협업까지이며 매출 증거가 아니다.",
    }


def displacement_scenarios(
    graph: dict[str, Any], start: str, max_depth: int = 5, onto: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """start 에서 닿는 기술·부품의 대체/잠식 관계. 수치 영향은 매기지 않는다."""
    onto = onto or load_ontology(ONTOLOGY_PATH)
    nodes = {n["id"]: n for n in graph["nodes"]}
    adj = _adjacency(graph, onto)
    alternatives: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in graph["edges"]:
        if e["relation"] in ("substitutes_for", "displaces"):
            alternatives[e["from"]].append(e)
            if e["relation"] == "substitutes_for":
                alternatives[e["to"]].append({**e, "from": e["to"], "to": e["from"]})
    queue = deque([(start, [start])])
    found, seen = [], set()
    while queue:
        node, path = queue.popleft()
        for edge in alternatives.get(node, []):
            key = (node, edge["to"], edge["relation"])
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "technology": nodes[node]["label"],
                    "alternative": nodes[edge["to"]]["label"],
                    "relation": edge["relation"],
                    "polarity": edge.get("polarity"),
                    "tier": edge.get("evidence_tier"),
                    "note": edge.get("note", ""),
                    "path": path + [edge["to"]],
                    "status": "competing_technology_scenario_only",
                    "warning": "Replacement is NOT established; architectures may coexist, and customer adoption must be verified.",
                }
            )
        if len(path) > max_depth:
            continue
        for nxt, _e, _h in adj.get(node, ()):
            if nxt not in path and nodes[nxt]["kind"] != "company":
                queue.append((nxt, path + [nxt]))
    return found


def possible_watch_matches(event: dict[str, Any], graph: dict[str, Any]) -> list[dict]:
    """감시 룰의 대상 노드가 이벤트 대상과 같으면 후보로 올린다 (룰 조건·독립 확인은 사람 몫)."""
    return [
        {
            "watch": w["id"],
            "status": "candidate_requires_rule_and_source_review",
            "reason": "The event targets a watched subject; baseline/delta and independent confirmation have not been checked.",
            "missing_confirmation": w["confirmations_needed"],
        }
        for w in graph["watches"]
        if w["target_id"] == event["target_id"]
    ]


def replay(graph: dict[str, Any], as_of: str) -> dict[str, Any]:
    onto = load_ontology(ONTOLOGY_PATH)
    validate_graph(graph, onto)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in graph["events"]:
        if not _public_by(event, as_of):
            continue
        fingerprint = event_fingerprint(event)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        report = impact_report(graph, event["target_id"], onto=onto)
        results.append(
            {
                "event_id": event["id"],
                "published_at": event.get("published_at"),
                "published_precision": event["date_precision"],
                "source_url": event["source_url"],
                "event_fingerprint": fingerprint,
                "summary": event["summary"],
                "possible_company_paths": [c["best_path"] for c in report["companies"]],
                "company_impacts": [
                    {
                        k: c[k]
                        for k in (
                            "company_id",
                            "company",
                            "best_confidence",
                            "band",
                            "direction",
                            "in_universe",
                        )
                    }
                    for c in report["companies"]
                ],
                "possible_substitution_risks": report["substitution_risks"],
                "watch_candidates": possible_watch_matches(event, graph),
                "source_independence": "NOT ESTABLISHED: multiple press reproductions count as one source group",
                "asof_integrity": "Contemporary evidence must be re-validated. Graph is a 2026 ontology, not a historic snapshot.",
            }
        )
    return {
        "as_of": as_of,
        "research_only": True,
        "seed_graph_version": graph["schema_version"],
        "warnings": [
            "The graph is curated retrospectively. NO point-in-time alpha backtest or return calculation.",
            "An implication path is a research candidate and must not be called a validated supplier relationship.",
            "Watch rules are evaluated by the 6-hourly monitor as candidates; promotion requires human review.",
        ],
        "events": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Supply-chain graph impact explorer")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--node", help="영향 전파 시작 노드 id (예: tech:hybrid_bond)")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    result = impact_report(graph, args.node) if args.node else replay(graph, args.as_of)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
