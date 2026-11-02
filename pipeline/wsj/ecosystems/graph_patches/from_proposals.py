"""그래프 제안 → 그래프 패치 JSON (ADR-0031, 백로그 G-4).

    python -m wsj.ecosystems.graph_patches.from_proposals proposals.json --prefix p1103 --out ../research/ecosystems/patches/20261103_proposals.json

proposals.json 은 `select proposal_id, kind, payload from ideas.graph_proposals where status = 'pending' order by proposal_id;` 의 결과(JSON 배열).
해석 작업이 근거를 다시 확인한 제안만 남겨 이 명령으로 패치를 만들고, from_json 으로 적용해 PR 을 올린다.
병합 뒤 graph-sync 가 그래프에 들어간 제안을 applied 로 바꾼다. 들이지 않을 제안은
`update ideas.graph_proposals set status = 'rejected', note = '…' where proposal_id = …;` (해석 작업만).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def to_patch(rows: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    doc: dict[str, Any] = {"prefix": prefix, "nodes": [], "edges": [], "node_updates": [], "aliases": {}, "proposal_ids": []}
    for r in rows:
        p = r.get("payload") or {}
        k = r.get("kind")
        if k == "edge":
            doc["edges"].append(p)
        elif k == "node":
            doc["nodes"].append(p)
        elif k == "node_update":
            doc["node_updates"].append(p)
        elif k == "alias":
            cur = doc["aliases"].setdefault(p["id"], [])
            cur += [w for w in p.get("aliases") or [] if w not in cur]
        else:
            continue
        doc["proposal_ids"].append(r.get("proposal_id"))
    return {k: v for k, v in doc.items() if v or k == "prefix"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("proposals", type=Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    rows = json.loads(args.proposals.read_text(encoding="utf-8"))
    doc = to_patch(rows, args.prefix)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"edges": len(doc.get("edges", [])), "nodes": len(doc.get("nodes", [])), "node_updates": len(doc.get("node_updates", [])),
                      "aliases": len(doc.get("aliases", {})), "out": str(args.out)}), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
