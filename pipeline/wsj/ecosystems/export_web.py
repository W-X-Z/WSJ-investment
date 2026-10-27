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
DISCOVERY_IN = GRAPH_PATH.parent / "discovery.json"
DISCOVERY_OUT = WEB_DATA / "discovery.json"


def trim_discovery(d: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    """웹용: 쿼리 로그·필링 제거, 기업별 매칭 노드와 승격 여부만."""
    promoted = {int(n["listing"]["cik"]) for n in graph["nodes"] if n["kind"] == "company" and (n.get("listing") or {}).get("cik")}
    labels = {n["id"]: n["label"] for n in graph["nodes"]}
    companies = [
        {
            "cik": r["cik"], "ticker": r["ticker"], "name": r["name"], "size_band": r["size_band"], "public_float": r["public_float"],
            "sic": r["sic"], "score": r["score"], "node_count": r["node_count"], "promoted": r["cik"] in promoted,
            "nodes": [{"id": k, "label": labels.get(k, k), "queries": v} for k, v in r["matched_nodes"].items()],
            "filing": {"form": r["filings"][0][0], "date": r["filings"][0][1]} if r.get("filings") else None,
        }
        for r in d["companies"] if r["size_band"] in ("micro", "small", "mid", "unknown")
    ]
    return {"as_of": d["as_of"], "window_start": d["window_start"], "summary": d["summary"], "nodes": {k: {**v, "label": labels.get(k, v.get("label"))} for k, v in d["nodes"].items()}, "companies": companies}


def web_seed(graph: dict[str, Any]) -> dict[str, Any]:
    """브라우저 번들용: 근거 발췌문(excerpt)은 빼고(화면에서 쓰지 않음) 공백 없이 — 그래프가 커져도 캔버스 청크를 작게."""
    edges = [{**e, "evidence": [{k: v for k, v in ev.items() if k != "excerpt"} for ev in e.get("evidence", [])]} for e in graph["edges"]]
    return {**graph, "edges": edges}


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
    seed_text = json.dumps(web_seed(graph), ensure_ascii=False, separators=(",", ":")) + "\n"
    index_text = json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n"
    disc_text = json.dumps(trim_discovery(json.loads(DISCOVERY_IN.read_text(encoding="utf-8")), graph), ensure_ascii=False, indent=1) + "\n" if DISCOVERY_IN.exists() else None
    if args.check:
        ok = (
            SEED_OUT.read_text(encoding="utf-8") == seed_text
            and IMPACT_OUT.read_text(encoding="utf-8") == index_text
            and (disc_text is None or (DISCOVERY_OUT.exists() and DISCOVERY_OUT.read_text(encoding="utf-8") == disc_text))
        )
        print("OK: web data in sync" if ok else "ERROR: run python -m wsj.ecosystems.export_web")
        return 0 if ok else 1
    SEED_OUT.write_text(seed_text, encoding="utf-8")
    IMPACT_OUT.write_text(index_text, encoding="utf-8")
    if disc_text:
        DISCOVERY_OUT.write_text(disc_text, encoding="utf-8")
    print(
        f"wrote {SEED_OUT.name} ({len(graph['nodes'])} nodes / {len(graph['edges'])} edges) and {IMPACT_OUT.name} ({index['meta']['nodes_indexed']} nodes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
