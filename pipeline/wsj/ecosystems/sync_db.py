"""온톨로지·기업 마스터 동기화 — git research/ecosystems/seed_graph.json(원본) → core.entities / core.ontology_nodes / core.ontology_edges. ADR-0015.

    python -m wsj.ecosystems.sync_db [--dry-run]

단방향: DB 를 손으로 고치지 않는다. 그래프에서 빠진 노드·관계는 지우지 않고 active=false (과거 이슈·카드의 참조 보존).
그래프 밖 기업(대만 월매출 지표의 공급사 등)은 indicators.TW_ENTITIES 에서 source='indicator' 로 등록한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from wsj.ecosystems.ontology import load_graph

log = logging.getLogger("wsj.ecosystems.sync_db")
NODE_CORE = {"id", "kind", "label", "ecosystem"}


def clean_name(label: str) -> str:
    """'NVIDIA (NVDA) — HBM·광·전력 공통 수요처' → 'NVIDIA', 'Samsung Electronics (KRX 005930, 비SEC)' → 'Samsung Electronics'."""
    s = re.split(r"\s+[—–-]\s+", label, maxsplit=1)[0]
    return re.sub(r"\s*\(.*\)\s*$", "", s).strip() or label


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def build_rows(graph: dict[str, Any], extra_entities: dict[str, dict[str, Any]], known_ciks: set[int] | None) -> dict[str, list[dict[str, Any]]]:
    now = datetime.now(UTC).isoformat()
    as_of = str(graph.get("as_of") or "")
    entities: dict[str, dict[str, Any]] = {}
    for n in graph["nodes"]:
        if n["kind"] != "company":
            continue
        lst = n.get("listing") or {}
        cik = lst.get("cik")
        if cik is not None and known_ciks is not None and int(cik) not in known_ciks:
            log.warning("cik %s of %s not in core.companies — stored without cik", cik, n["id"])
            cik = None
        code = str(lst.get("ticker") or "")
        entities[n["id"]] = {
            "entity_id": n["id"], "name": clean_name(n["label"]), "cik": int(cik) if cik else None,
            "ticker": code if code and not code.isdigit() else None,          # 005930 같은 숫자 코드는 local_code 로
            "exchange": lst.get("exchange"), "local_code": code if code.isdigit() else None,
            "listing": lst.get("filer_type"), "size_band": n.get("size_band"),
            "ecosystems": sorted({x for x in [n.get("ecosystem"), *_as_list(n.get("also_in"))] if x}),
            "role": n.get("role"), "in_graph": True, "in_universe": bool(n.get("in_universe")), "source": "ontology",
            "attrs": {k: v for k, v in n.items() if k not in NODE_CORE | {"listing", "size_band", "role", "in_universe", "also_in"}},
            "updated_at": now,
        }
    for eid, e in extra_entities.items():
        if eid in entities:  # 그래프로 승격된 기업은 그래프가 원본
            continue
        entities[eid] = {"entity_id": eid, "name": e["name"], "cik": None, "ticker": e.get("ticker"), "exchange": e.get("exchange"),
                         "local_code": e.get("local_code"), "listing": e.get("listing"), "size_band": e.get("size_band"),
                         "ecosystems": e.get("ecosystems") or [], "role": e.get("role"), "in_graph": False, "in_universe": False,
                         "source": "indicator", "attrs": e.get("attrs") or {}, "updated_at": now}
    nodes = [{
        "node_id": n["id"], "kind": n["kind"], "label": n["label"], "ecosystem": n.get("ecosystem"),
        "entity_id": n["id"] if n["kind"] == "company" else None,
        "attrs": {k: v for k, v in n.items() if k not in NODE_CORE}, "graph_as_of": as_of, "active": True, "updated_at": now,
    } for n in graph["nodes"]]
    edges = [{
        "edge_id": e["id"], "src": e["from"], "dst": e["to"], "predicate": e["relation"], "evidence_tier": e.get("evidence_tier"),
        "confidence": e.get("confidence"), "polarity": e.get("polarity"), "about": _as_list(e.get("about")),
        "evidence": e.get("evidence") or [], "note": e.get("note") or None, "graph_as_of": as_of, "active": True, "updated_at": now,
    } for e in graph["edges"]]
    return {"entities": list(entities.values()), "nodes": nodes, "edges": edges}


def sync(store, dry_run: bool = False) -> dict[str, int]:
    from wsj.ecosystems.indicators import TW_ENTITIES

    graph = load_graph()
    ciks = None
    if store is not None:
        want = [int(n["listing"]["cik"]) for n in graph["nodes"] if n["kind"] == "company" and (n.get("listing") or {}).get("cik")]
        ciks = {int(r["cik"]) for r in store.select("core.companies", ["cik"], {"cik": want})} if want else set()
    rows = build_rows(graph, TW_ENTITIES, ciks)
    stats = {k: len(v) for k, v in rows.items()}
    if dry_run or store is None:
        return stats
    store.upsert("core.entities", rows["entities"], ["entity_id"])
    store.upsert("core.ontology_nodes", rows["nodes"], ["node_id"])
    store.upsert("core.ontology_edges", rows["edges"], ["edge_id"])
    # 그래프에서 빠진 것은 비활성 (지우지 않는다)
    keep_nodes = {r["node_id"] for r in rows["nodes"]}
    keep_edges = {r["edge_id"] for r in rows["edges"]}
    stale_e = [r for r in store.select("core.ontology_edges", ["*"], {"active": True}) if r["edge_id"] not in keep_edges]
    stale_n = [r for r in store.select("core.ontology_nodes", ["*"], {"active": True}) if r["node_id"] not in keep_nodes]
    now = datetime.now(UTC).isoformat()
    if stale_e:
        store.upsert("core.ontology_edges", [{**r, "active": False, "updated_at": now} for r in stale_e], ["edge_id"])
    if stale_n:
        store.upsert("core.ontology_nodes", [{**r, "active": False, "updated_at": now} for r in stale_n], ["node_id"])
    stats.update(deactivated_nodes=len(stale_n), deactivated_edges=len(stale_e))
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.dry_run:
        print(json.dumps(sync(None, dry_run=True)))
        return 0
    from wsj.config import load_settings
    from wsj.db import make_store
    from wsj.runlog import logged_run

    store = make_store(load_settings())
    try:
        with logged_run(store, "ontology_sync") as run:
            stats = sync(store)
            run["rows"] = stats["entities"] + stats["nodes"] + stats["edges"]
            run["notes"] = json.dumps(stats)
    finally:
        store.close()
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
