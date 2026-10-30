"""JSON 그래프 패치 — 매일 발굴 작업(ADR-0027)이 작은 테제의 소형 공급사를 그래프에 넣는 길.

예약작업은 파이프라인 코드를 바꾸지 않는다. 대신 `research/ecosystems/patches/YYYYMMDD_<task>.json` 에 노드·간선을 데이터로 적고 이 모듈로 적용한다.
적용은 파이썬 패치와 같은 apply() — 멱등이고, 온톨로지 검증이 실패하면 파일을 쓰지 않는다.
이미 있는 간선(from·relation·to 같음)에 exposure·position·about 을 주면 그 간선에 덧붙이고 근거를 더한다 (새로 만들지 않는다). 그 뒤 `python -m wsj.ecosystems.export_web` 로 웹 데이터를 맞춘다.

    python -m wsj.ecosystems.graph_patches.from_json ../research/ecosystems/patches/20261031_discover.json [--dry-run]
    python -m wsj.ecosystems.graph_patches.from_json --all      # 폴더의 패치 전부 (이미 적용된 것은 건너뛴다)

형식:
    {"prefix": "d1031",
     "nodes": [{"id": "company:isu_petasys", "kind": "company", "label": "ISU Petasys (KRX 007660, 비SEC)", "ecosystem": "hbm",
                "ticker": "007660", "exchange": "KRX", "size_band": "mid"},
               {"id": "component:mlb_pcb", "kind": "component", "label": "고다층 MLB 기판", "ecosystem": "hbm"}],
     "edges": [{"from": "component:mlb_pcb", "relation": "offered_by", "to": "company:isu_petasys", "tier": "third_party_report", "note": "…",
                "exposure": "core", "position": "leader",          # 선택: 매출 비중(core·major·minor·unknown)·자리(leader·second_source·entrant·captive)
                "evidence": [{"url": "https://…", "source_type": "third_party_report", "published_at": "2025-10-31", "excerpt": "원문 한 줄"}]}],
     "aliases": {"company:isu_petasys": ["이수페타시스"]}, "native": {"company:isu_petasys": "이수페타시스"}}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from wsj.ecosystems.graph_patches import Edge, Node, apply
from wsj.ecosystems.ontology import GRAPH_PATH

PATCH_DIR = GRAPH_PATH.parent / "patches"
SIZE_BANDS = {"micro", "small", "mid", "large", "mega"}  # 온톨로지 company_fields.size_band (상장사만 — private 제외)


def parse(doc: dict[str, Any]) -> tuple[list[Node], list[Edge], str, dict[str, list[str]], dict[str, str]]:
    """JSON 패치 → (노드, 간선, 접두사, 별칭, 현지어 이름). 형식이 틀리면 ValueError (어느 행이 왜)."""
    prefix = str(doc.get("prefix") or "")
    if not re.fullmatch(r"[a-z][a-z0-9]{2,11}", prefix):
        raise ValueError("prefix 는 영문 소문자로 시작하는 3~12자 (간선 id 접두사)")
    nodes: list[Node] = []
    for i, n in enumerate(doc.get("nodes") or []):
        nid, kind, label, eco = n.get("id"), n.get("kind"), n.get("label"), n.get("ecosystem")
        if not (isinstance(nid, str) and ":" in nid and kind and label and eco):
            raise ValueError(f"nodes[{i}]: id(kind:slug)·kind·label·ecosystem 필수")
        if kind == "company":
            if not nid.startswith("company:"):
                raise ValueError(f"nodes[{i}]: 기업 id 는 company: 로 시작")
            band = n.get("size_band")
            if band not in SIZE_BANDS:
                raise ValueError(f"nodes[{i}]: size_band 는 {sorted(SIZE_BANDS)}")
            if not (n.get("ticker") and n.get("exchange")):
                raise ValueError(f"nodes[{i}]: 상장 기업만 — ticker·exchange 필수")
            nodes.append(Node.company(nid, label, eco, str(n["ticker"]), str(n["exchange"]), band, cik=n.get("cik"), role=n.get("role") or "supplier"))
        else:
            nodes.append(Node(nid, kind, label, eco, {k: v for k, v in n.items() if k not in {"id", "kind", "label", "ecosystem"}}))
    edges: list[Edge] = []
    for i, e in enumerate(doc.get("edges") or []):
        evs = e.get("evidence") or []
        if not (e.get("from") and e.get("relation") and e.get("to") and e.get("tier")):
            raise ValueError(f"edges[{i}]: from·relation·to·tier 필수")
        if not evs or any(not str(v.get("url") or "").startswith("https://") or not v.get("source_type") for v in evs):
            raise ValueError(f"edges[{i}]: evidence 1개 이상, 각각 https url·source_type")
        attrs = {k: e[k] for k in ("exposure", "position", "about") if e.get(k)}
        edges.append(Edge(e["from"], e["relation"], e["to"],
                          [(v["url"], v["source_type"], v.get("published_at"), v.get("excerpt")) for v in evs],
                          e["tier"], e.get("polarity") or "positive", e.get("note") or "", attrs or None))
    aliases = {k: [str(w) for w in v] for k, v in (doc.get("aliases") or {}).items()}
    native = {k: str(v) for k, v in (doc.get("native") or {}).items()}
    return nodes, edges, prefix, aliases, native


def apply_file(path: Path, dry_run: bool = False) -> int:
    try:
        nodes, edges, prefix, aliases, native = parse(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {path.name}: {exc}", file=sys.stderr)
        return 1
    return apply(nodes, edges, prefix, native=native or None, aliases=aliases or None, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true", help=f"{PATCH_DIR} 의 패치 전부 이름순")
    ap.add_argument("--dry-run", action="store_true", help="검증만 (파일을 쓰지 않는다)")
    args = ap.parse_args(argv)
    files = sorted(PATCH_DIR.glob("*.json")) if args.all else args.files
    if not files:
        ap.error("패치 파일을 주거나 --all")
    rc = 0
    for f in files:
        rc |= apply_file(f, args.dry_run)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
