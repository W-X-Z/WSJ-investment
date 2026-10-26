"""웹 번들용 정적 산출물. ADR-0012.

    python -m wsj.ecosystems.export_web          # 쓰기
    python -m wsj.ecosystems.export_web --check  # CI: 최신인지 확인

- apps/web/src/data/ecosystem-seed.json : seed_graph.json 그대로 (검증 통과 + confidence 채움)
- apps/web/src/data/impact-index.json   : 기업 아닌 모든 노드에 대해 "변화 시 영향 기업" 상위 8 (방향·신뢰도·경로)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wsj.ecosystems.impact import impact_report
from wsj.ecosystems.ontology import GRAPH_PATH, edge_confidence, load_graph, load_ontology, validate

WEB_DATA = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "data"
SEED_OUT = WEB_DATA / "ecosystem-seed.json"
IMPACT_OUT = WEB_DATA / "impact-index.json"


def build(graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    onto = load_ontology()
    for e in graph["edges"]:
        e["confidence"] = edge_confidence(e, onto)
    rep = validate(graph, onto)
    if rep.errors:
        raise SystemExit("seed_graph.json invalid: " + "; ".join(rep.errors[:5]))
    index: dict[str, Any] = {}
    for n in graph["nodes"]:
        if n["kind"] in ("company", "ecosystem"):
            continue
        r = impact_report(graph, n["id"], onto=onto)
        if not r["companies"] and not r["substitution_risks"]:
            continue
        index[n["id"]] = {
            "companies": [
                {
                    "company_id": c["company_id"],
                    "company": c["company"],
                    "direction": c["direction"],
                    "confidence": c["best_confidence"],
                    "band": c["band"],
                    "in_universe": c["in_universe"],
                    "size_band": c["size_band"],
                    "ticker": (c.get("listing") or {}).get("ticker"),
                    "role": c["best_path"]["role_on_path"],
                    "path": [p["label"] for p in c["best_path"]["path"]],
                    "weakest": c["best_path"]["weakest_edge"],
                    "upgrade_needed": c["upgrade_needed"],
                }
                for c in r["companies"][:8]
            ],
            "substitutions": [
                {
                    "technology": s["technology"],
                    "alternative": s["alternative"],
                    "relation": s["relation"],
                    "polarity": s["polarity"],
                    "note": s["note"],
                }
                for s in r["substitution_risks"][:6]
            ],
        }
    meta = {
        "generated_from": "research/ecosystems/seed_graph.json",
        "schema_version": graph["schema_version"],
        "as_of": graph["as_of"],
        "nodes_indexed": len(index),
        "caveat": r["caveat"] if index else "",
    }
    return graph, {"meta": meta, "nodes": index}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    graph, index = build(load_graph(GRAPH_PATH))
    seed_text = json.dumps(graph, ensure_ascii=False, indent=2) + "\n"
    index_text = json.dumps(index, ensure_ascii=False, indent=1) + "\n"
    if args.check:
        ok = (
            SEED_OUT.read_text(encoding="utf-8") == seed_text
            and IMPACT_OUT.read_text(encoding="utf-8") == index_text
        )
        print("OK: web data in sync" if ok else "ERROR: run python -m wsj.ecosystems.export_web")
        return 0 if ok else 1
    SEED_OUT.write_text(seed_text, encoding="utf-8")
    IMPACT_OUT.write_text(index_text, encoding="utf-8")
    print(
        f"wrote {SEED_OUT.name} ({len(graph['nodes'])} nodes / {len(graph['edges'])} edges) and {IMPACT_OUT.name} ({index['meta']['nodes_indexed']} nodes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
