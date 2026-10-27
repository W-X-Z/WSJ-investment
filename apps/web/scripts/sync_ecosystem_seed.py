#!/usr/bin/env python3
"""Keep the web's read-only seed in sync with the canonical ecosystem graph.

This is deliberate: the Vercel project Root Directory is apps/web, so an
import crossing into the repository's research/ folder is not deployment-safe.
Use --check in CI, default mode to write the frontend's bundled research seed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research" / "ecosystems" / "seed_graph.json"
TARGET = ROOT / "apps" / "web" / "src" / "data" / "ecosystem-seed.json"


def web_view(graph: dict) -> dict:
    """Same projection as pipeline wsj.ecosystems.export_web.web_seed: evidence excerpts are not
    shown in the UI, so they are dropped to keep the canvas bundle small (852-node graph)."""
    edges = [{**e, "evidence": [{k: v for k, v in ev.items() if k != "excerpt"} for ev in e.get("evidence", [])]} for e in graph["edges"]]
    return {**graph, "edges": edges}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if published UI seed differs")
    args = parser.parse_args()
    source = web_view(json.loads(SOURCE.read_text(encoding="utf-8")))
    current = json.loads(TARGET.read_text(encoding="utf-8"))
    if args.check:
        if current != source:
            print("ERROR: UI seed differs. Run: python apps/web/scripts/sync_ecosystem_seed.py")
            return 1
        print(f"OK: UI seed synced, {len(source['nodes'])} nodes, {len(source['edges'])} edges")
        return 0
    TARGET.write_text(json.dumps(source, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Synced {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
