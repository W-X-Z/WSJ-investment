"""그래프 패치 — 근거 있는 노드·간선 추가를 코드로 남긴다 (ADR-0017).

사람이든 Claude 개선 예약작업이든 그래프를 고칠 때는 seed_graph.json 을 손으로 고치지 않고 이 폴더에 패치 모듈을 하나 더한다.
패치는 멱등이다 (같은 from·relation·to 간선, 같은 id 노드는 건너뛴다). 적용 후 온톨로지 검증이 실패하면 파일을 쓰지 않는다.

    python -m wsj.ecosystems.graph_patches.p20261028_dead_ends_fiber_substrate
    python -m wsj.ecosystems.graph_patches --all        # 모든 패치를 이름순으로 (CI 가 '이미 적용됨'을 확인)
"""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wsj.ecosystems.ontology import GRAPH_PATH, edge_confidence, load_ontology, validate

ALIASES_PATH = GRAPH_PATH.parent / "node_aliases.json"
NATIVE_PATH = GRAPH_PATH.parent / "native_names.json"

# 근거 = (url, source_type, published_at|None, excerpt|None)
Evidence = tuple[str, str, str | None, str | None]


@dataclass
class Node:
    id: str
    kind: str
    label: str
    ecosystem: str
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def company(cls, cid: str, label: str, eco: str, ticker: str | None, exchange: str | None, size_band: str,
                cik: int | None = None, filer_type: str | None = None, role: str = "supplier") -> Node:
        ft = filer_type or ("private" if not exchange else "10-K" if cik else "non_sec_listed")
        return cls(cid, "company", label, eco, {"role": role, "listing": {"ticker": ticker, "exchange": exchange, "cik": cik, "filer_type": ft},
                                                 "size_band": size_band, "in_universe": False})

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "label": self.label, "ecosystem": self.ecosystem, **self.extra}


@dataclass
class Edge:
    frm: str
    relation: str
    to: str
    evidence: Evidence | list[Evidence]
    tier: str
    polarity: str = "positive"
    note: str = ""

    def evidence_rows(self) -> list[dict[str, Any]]:
        evs = self.evidence if isinstance(self.evidence, list) else [self.evidence]
        out = []
        for url, st, pub, ex in evs:
            row: dict[str, Any] = {"url": url, "source_type": st}
            if pub:
                row["published_at"] = pub
            if ex:
                row["excerpt"] = ex
            out.append(row)
        return out


def _dump(path: Path, data: Any, indent: int) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def apply(nodes: list[Node], edges: list[Edge], prefix: str, native: dict[str, str] | None = None,
          aliases: dict[str, list[str]] | None = None, node_terms: dict[str, list[str]] | None = None, dry_run: bool = False) -> int:
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    onto = load_ontology()
    ids = {n["id"] for n in graph["nodes"]}
    added_n = 0
    for n in nodes:
        if n.id not in ids:
            graph["nodes"].append(n.as_dict())
            ids.add(n.id)
            added_n += 1
    have = {(e["from"], e["relation"], e["to"]) for e in graph["edges"]}
    used = {e["id"] for e in graph["edges"]}
    seq = 1 + max([int(i.rsplit("-", 1)[1]) for i in used if i.startswith(prefix + "-") and i.rsplit("-", 1)[1].isdigit()] or [0])
    added_e = 0
    for e in edges:
        if (e.frm, e.relation, e.to) in have:
            continue
        row: dict[str, Any] = {"id": f"{prefix}-{seq:03d}", "from": e.frm, "to": e.to, "relation": e.relation, "evidence_tier": e.tier,
                               "polarity": e.polarity, "evidence": e.evidence_rows()}
        if e.note:
            row["note"] = e.note
        row["confidence"] = edge_confidence(row, onto)
        graph["edges"].append(row)
        have.add((e.frm, e.relation, e.to))
        seq += 1
        added_e += 1
    rep = validate(graph, onto)
    for err in rep.errors:
        print("ERROR", err, file=sys.stderr)
    if not rep.ok:
        print(f"FAIL: 패치 적용 후 검증 오류 {len(rep.errors)}개 — 파일을 쓰지 않는다", file=sys.stderr)
        return 1
    if dry_run:
        print(json.dumps({"nodes_added": added_n, "edges_added": added_e, "dry_run": True}))
        return 0
    if added_n or added_e:
        _dump(GRAPH_PATH, graph, 2)
    if aliases:
        a = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
        for nid, words in aliases.items():
            cur = a["aliases"].setdefault(nid, [])
            cur += [w for w in words if w not in cur]
        _dump(ALIASES_PATH, a, 2)
    if native or node_terms:
        nn = json.loads(NATIVE_PATH.read_text(encoding="utf-8"))
        for cid, name in (native or {}).items():
            nn["names"].setdefault(cid, name)
        for nid, words in (node_terms or {}).items():
            cur = nn["node_terms"].setdefault(nid, [])
            cur += [w for w in words if w not in cur]
        _dump(NATIVE_PATH, nn, 2)
    print(json.dumps({"nodes_added": added_n, "edges_added": added_e, "nodes": len(graph["nodes"]), "edges": len(graph["edges"])}))
    return 0


def all_patches() -> list[str]:
    return sorted(m.name for m in pkgutil.iter_modules(__path__) if m.name.startswith("p"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="모든 패치를 이름순으로 적용")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    if args.list or not args.all:
        print("\n".join(all_patches()))
        return 0
    rc = 0
    for name in all_patches():
        mod = importlib.import_module(f"{__name__}.{name}")
        rc |= mod.main()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
