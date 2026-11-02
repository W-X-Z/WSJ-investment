"""그래프 조회본 (ADR-0031, 백로그 G-2) — Git 의 그래프를 Supabase `core.graph_*` 로 옮긴다.

    python -m wsj.ecosystems.graph_sync run [--dry-run]

원본은 Git(`research/ecosystems/seed_graph.json` + 패치 + CI 검증)이다. DB 는 조회본이라 직접 고치지 않는다 — 고칠 것은
`ideas.put_graph_proposal` 로 제안하고, 해석 작업이 그날 패치에 합친다. 병합될 때마다 graph-sync 워크플로가 이 모듈을 돌린다.
조회 함수(core.resolve_terms · graph_neighbors · suppliers_below · node_signals, 0035)가 이 테이블을 읽는다.

- core.graph_nodes: 노드 (v0.5 칸 status·first_seen·first_evidence·codes·maturity_history 포함)
- core.graph_edges: 간선 (방향 direction 은 온톨로지 술어에서, 노출도 숫자 칸 포함)
- core.graph_terms: 글 → 노드 잇기용 어휘 — 단서 태깅 어휘(issues.lexicon_terms) + 라벨 + 현지어 이름 + 노드 용어 + codes + 티커
동기화는 이번 실행 시각으로 전부 덮어쓰고(upsert), 그보다 오래된 행(그래프에서 빠진 것)을 지운다.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from wsj.ecosystems.ontology import GRAPH_PATH, clean_name, load_graph, load_ontology

log = logging.getLogger("wsj.ecosystems.graph_sync")
NATIVE_PATH = GRAPH_PATH.parent / "native_names.json"
NODE_COLS = {"id", "kind", "label", "ecosystem", "also_in", "status", "maturity", "maturity_history", "first_seen", "first_evidence", "codes",
             "listing", "size_band", "role", "in_universe"}
EDGE_COLS = {"id", "from", "to", "relation", "evidence_tier", "polarity", "confidence", "exposure", "exposure_pct", "exposure_year",
             "exposure_source", "position", "about", "effective_date", "content_usd_per_system", "lead_time_weeks", "note", "evidence"}


def norm_term(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def node_rows(graph: dict[str, Any], sha: str | None) -> list[dict[str, Any]]:
    out = []
    for n in graph["nodes"]:
        lst = n.get("listing") or {}
        out.append({
            "id": n["id"], "kind": n["kind"], "label": n["label"], "name": clean_name(n["label"]),
            "ecosystem": n.get("ecosystem"), "also_in": list(n.get("also_in") or []), "status": n.get("status") or "active",
            "maturity": n.get("maturity"), "maturity_stage": (n.get("maturity") or {}).get("stage"),
            "maturity_history": n.get("maturity_history") or [], "first_seen": n.get("first_seen"), "first_evidence": n.get("first_evidence"),
            "codes": n.get("codes") or {}, "ticker": lst.get("ticker"), "exchange": lst.get("exchange"), "cik": lst.get("cik"),
            "size_band": n.get("size_band"), "role": n.get("role"),
            "attrs": {k: v for k, v in n.items() if k not in NODE_COLS}, "graph_sha": sha,
        })
    return out


def edge_rows(graph: dict[str, Any], onto: dict[str, Any], sha: str | None) -> list[dict[str, Any]]:
    preds = onto["predicates"]
    out = []
    for e in graph["edges"]:
        dates = sorted(str(v.get("published_at"))[:10] for v in e.get("evidence") or [] if v.get("published_at"))
        out.append({
            "id": e["id"], "src": e["from"], "dst": e["to"], "relation": e["relation"],
            "direction": (preds.get(e["relation"]) or {}).get("direction"),
            "evidence_tier": e.get("evidence_tier"), "polarity": e.get("polarity"), "confidence": e.get("confidence"),
            "exposure": e.get("exposure"), "exposure_pct": e.get("exposure_pct"), "exposure_year": e.get("exposure_year"),
            "exposure_source": e.get("exposure_source"), "position": e.get("position"), "about": e.get("about"),
            "effective_date": e.get("effective_date"), "content_usd_per_system": e.get("content_usd_per_system"),
            "lead_time_weeks": e.get("lead_time_weeks"), "note": e.get("note") or None,
            "first_evidence_date": dates[0] if dates and re.match(r"^\d{4}-\d{2}-\d{2}$", dates[0]) else None,
            "evidence": e.get("evidence") or [], "attrs": {k: v for k, v in e.items() if k not in EDGE_COLS}, "graph_sha": sha,
        })
    return out


def term_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """(term, node_id, source). term 은 소문자·공백 하나로. 짧은 영문 티커·약어는 매칭 때 단어 경계를 본다(함수 쪽)."""
    from wsj.ecosystems.issues import lexicon_terms

    ids = {n["id"] for n in graph["nodes"]}
    seen: dict[tuple[str, str], tuple[str, str, bool]] = {}

    def add(term: str | None, nid: str, source: str) -> None:
        raw = re.sub(r"\s+", " ", (term or "").strip())
        t = raw.lower()
        if len(t) < 2 or nid not in ids or (t, nid) in seen:
            return
        # 대소문자를 가리는 짧은 이름·티커 ('KLA', 'ON', 'MU') — 단서 태깅(issues.build_lexicon)과 같은 규칙
        cs = source == "ticker" or (source == "company_name" and (raw.isupper() or len(raw) <= 4))
        seen[(t, nid)] = (source, raw, cs)

    phrases, company_names = lexicon_terms(graph)
    for t, nid in phrases.items():
        add(t, nid, "alias")
    for cid, names in company_names.items():
        for nm in names:
            add(nm, cid, "company_name")
    from wsj.ecosystems.clues import known_company_names

    for nm, cid in known_company_names(graph).items():     # 현지어 이름·기업 별칭 (TSMC ↔ 台積電 ↔ TSM) — 소문자라 대소문자 무시
        add(nm, cid, "native")
    for n in graph["nodes"]:
        if n["kind"] not in ("ecosystem",):
            name = clean_name(n["label"])
            if len(name) >= 3:
                add(name, n["id"], "label")
        for words in (n.get("codes") or {}).values():
            for w in words:
                add(w, n["id"], "code")
        tk = ((n.get("listing") or {}).get("ticker") or "")
        if n["kind"] == "company" and len(tk) >= 2 and not tk.isdigit():
            add(tk, n["id"], "ticker")
    try:
        nat = json.loads(NATIVE_PATH.read_text(encoding="utf-8"))
        for cid, name in (nat.get("names") or {}).items():
            add(name, cid, "native")
        for nid, words in (nat.get("node_terms") or {}).items():
            for w in words:
                add(w, nid, "native")
    except (OSError, ValueError) as exc:
        log.warning("native_names 를 읽지 못함: %s", exc)
    return [{"term": t, "node_id": nid, "source": src, "raw": raw, "case_sensitive": cs} for (t, nid), (src, raw, cs) in seen.items()]


def graph_sha() -> str | None:
    import subprocess

    try:
        return subprocess.run(["git", "log", "-1", "--format=%h", "--", str(GRAPH_PATH)], capture_output=True, text=True,
                              cwd=GRAPH_PATH.parent, timeout=10).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def sync(store: Any, graph: dict[str, Any], onto: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    sha = graph_sha()
    nodes, edges, terms = node_rows(graph, sha), edge_rows(graph, onto, sha), term_rows(graph)
    stats = {}
    for table, rows, key in (("core.graph_nodes", nodes, ["id"]), ("core.graph_edges", edges, ["id"]), ("core.graph_terms", terms, ["term", "node_id"])):
        for r in rows:
            r["synced_at"] = now
        stats[table] = store.upsert(table, rows, key)
        store.delete(table, {"synced_at": ("lt", now)})       # 그래프에서 빠진 행
    stats["proposals_applied"] = reconcile_proposals(store, graph)
    stats["graph_sha"] = sha
    return stats


def reconcile_proposals(store: Any, graph: dict[str, Any]) -> int:
    """대기 중인 제안 중 그래프에 이미 들어간 것(간선 from·relation·to, 노드 id)을 applied 로."""
    try:
        pend = store.select("ideas.graph_proposals", ["proposal_id", "kind", "payload"], {"status": "pending"})
    except Exception as exc:  # noqa: BLE001 - 0035 전
        log.warning("ideas.graph_proposals 를 읽지 못함: %s", exc)
        return 0
    have_e = {(e["from"], e["relation"], e["to"]) for e in graph["edges"]}
    by_e = {(e["from"], e["relation"], e["to"]): e for e in graph["edges"]}
    have_n = {n["id"] for n in graph["nodes"]}
    done = []
    for p in pend:
        pl = p.get("payload") or {}
        if p["kind"] == "edge":
            key = (pl.get("from"), pl.get("relation"), pl.get("to"))
            attrs = {k: v for k, v in pl.items() if k in ("exposure", "exposure_pct", "position", "about", "effective_date")}
            if key in have_e and all(by_e[key].get(k) == v for k, v in attrs.items()):
                done.append(p["proposal_id"])
        elif p["kind"] == "node" and pl.get("id") in have_n:
            done.append(p["proposal_id"])
    if done:
        store.upsert("ideas.graph_proposals", [{"proposal_id": i, "status": "applied", "applied_at": datetime.now(UTC).isoformat()} for i in done],
                     ["proposal_id"])
    return len(done)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--dry-run", action="store_true", help="행만 만들어 수를 보인다 (DB 에 쓰지 않는다)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    graph, onto = load_graph(), load_ontology()
    if args.dry_run:
        sha = graph_sha()
        print(json.dumps({"nodes": len(node_rows(graph, sha)), "edges": len(edge_rows(graph, onto, sha)), "terms": len(term_rows(graph)), "graph_sha": sha}))
        return 0
    from wsj.config import load_settings
    from wsj.db import make_store
    from wsj.runlog import logged_run

    store = make_store(load_settings())
    try:
        with logged_run(store, "graph_sync", {}) as lr:
            stats = sync(store, graph, onto)
            lr["rows"] = int(stats.get("core.graph_edges") or 0)
            lr["notes"] = json.dumps(stats, ensure_ascii=False)
        print(json.dumps(stats, ensure_ascii=False))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
