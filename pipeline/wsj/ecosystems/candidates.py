"""후보 노드 통로 (ADR-0031, 백로그 G-7 · T-8) — 그래프가 못 잡는 것을 단서에서 찾아 그래프 제안으로 올린다.

    python -m wsj.ecosystems.candidates run [--days 14] [--dry-run]

수집(issues 워크플로)이 clues 다음에 돌린다. 판단은 하지 않는다 — 찾아서 `ideas.graph_proposals` 에 by='collect' 로 올리면
해석 작업이 원문을 열어 확인하고 패치에 합치거나 rejected 로 둔다 (`docs/agents/daily/interpret.md`).

1. 다시 잇기: 분류기가 적은 기업 중 그래프 id 가 비어 있던 것을 지금 어휘·거래소 묶음으로 다시 잇는다 (거래소 묶음이 늘면 지난 단서도 붙는다).
2. 그래프 밖 상장사 → 후보 기업 노드 제안 (kind='node', status='candidate', size_band='unknown'):
   최근 단서 2건 이상, 또는 원본·공시·뉴스룸 층 단서 1건. 같이 걸린 노드에서 생태계를 정한다 (걸린 노드가 없으면 올리지 않는다).
   그래프에 들어가면 기업 소식 수집·가격·재무 대상이 된다 — 수집 범위가 그래프 밖으로 넓어지는 길.
3. 사전 밖 식별자 → 용어 제안 (kind='term'): 기술 노드가 하나도 안 걸린 원본·뉴스룸 단서에서 표준 번호·규칙 번호·인터페이스 이름 꼴의
   말(JESD·802.3xx·NOGRR·CEI-·xxxZR·PCIe/CXL 세대·NERC 표준 …)을 뽑아 어휘에 없는 것만. 해석이 별칭·codes·후보 노드 중 하나로 정한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from wsj.ecosystems.ontology import load_graph

log = logging.getLogger("wsj.ecosystems.candidates")

STRONG_LAYERS = {"raw", "disclosure", "newsroom"}
COMPANY_CAP = 15
TERM_CAP = 15
TICKER_OK = {
    "US": r"[A-Z][A-Z.\-]{0,5}", "KR": r"\d{6}", "TW": r"\d{4,6}[A-Z]?", "JP": r"\d{3}[0-9A-Z]", "CN": r"\d{6}", "HK": r"\d{1,5}",
}
TERM_PATTERNS = [
    r"\bJESD\d{2,4}(?:-\d{1,2})?[A-Z]?\b", r"\bJEP\d{2,4}[A-Z]?\b",
    r"\bP?802\.3[a-z]{1,3}\b",
    r"\b(?:NOGRR|NPRR|PGRR|RRGRR|OBDRR|SCR|VCMRR)\s?\d{3,4}\b",
    r"\bOIF-[A-Za-z0-9.\-]{3,}\b", r"\bCEI-\d{2,3}G(?:-[A-Z]{2,4})?\b", r"\b\d{3,4}ZR\+?\b", r"\b\d{3,4}LR\d?\b",
    r"\b(?:PCIe|CXL|UCIe|UALink|NVLink)\s?\d(?:\.\d)?\b",
    r"\b(?:LPDDR|GDDR|DDR|HBM)\d[A-Z]?\b", r"\bSOCAMM\d?\b", r"\bLPCAMM\d?\b", r"\bMRDIMM\b",
    r"\b(?:EOP|TOP|CIP|PRC|TPL|MOD|FAC|BAL|VAR|PER|IRO)-\d{3}-\d{1,2}\b",
    r"\bORv\d\b", r"\b\d{1,2}\.\dT\b",
]
TERM_RE = re.compile("|".join(f"(?:{p})" for p in TERM_PATTERNS))
CLUE_COLS = ["url", "title", "summary", "published_at", "seen_at", "source_id", "source_name", "source_kind", "lang", "region",
             "companies", "nodes", "relevant", "note", "extra"]


def norm_ticker(grp: str, t: str) -> str:
    return (str(t or "").upper().split(":")[-1].strip().lstrip("0") or "0") if grp != "US" else str(t or "").upper().split(":")[-1].strip()


def slug(name: str) -> str:
    s = re.sub(r"\b(inc|corp|corporation|co|ltd|limited|plc|holdings?|group|technolog(?:y|ies)|ag|sa|nv|se)\b\.?", " ", name.lower())
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:40]


def relink(rows: list[dict[str, Any]], resolve: Any) -> list[dict[str, Any]]:
    """그래프 id 가 비어 있는 기업을 다시 잇는다. 바뀐 단서 행(url, companies)만 돌려준다."""
    out = []
    for r in rows:
        cos = r.get("companies") or []
        have = {c.get("company") for c in cos if c.get("company")}
        changed = False
        new = []
        for c in cos:
            if not c.get("company") and c.get("name"):
                cid = resolve(c.get("name"), c.get("ticker"), c.get("exchange"))
                if cid and cid in have:
                    changed = True
                    continue                      # 같은 회사가 이미 붙어 있다
                if cid:
                    c = {**c, "company": cid}
                    have.add(cid)
                    changed = True
            new.append(c)
        if changed:
            out.append({"url": r["url"], "companies": new})
    return out


def outside_companies(rows: list[dict[str, Any]], graph: dict[str, Any], skip_keys: set[tuple[str, str]], today: str) -> list[dict[str, Any]]:
    from wsj.ecosystems.clues import EXCHANGE_GROUP

    nodes = {n["id"]: n for n in graph["nodes"]}
    ids = set(nodes)
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    names_to_keys: dict[str, set[tuple[str, str]]] = {}
    for r in rows:
        layer = (r.get("extra") or {}).get("layer") or "press"
        tech = [n for n in r.get("nodes") or [] if n in ids and not n.startswith(("company:", "eco:"))]
        in_graph = [c["company"] for c in r.get("companies") or [] if c.get("company") in ids]
        for c in r.get("companies") or []:
            if c.get("company") or not c.get("ticker") or not c.get("name"):
                continue
            ex = str(c.get("exchange") or "").strip()
            grp = EXCHANGE_GROUP.get(ex.upper())
            if not grp:
                continue
            tk = str(c["ticker"]).upper().split(":")[-1].strip()
            if grp in TICKER_OK and not re.fullmatch(TICKER_OK[grp], tk):
                continue
            key = (grp, norm_ticker(grp, tk))
            if key in skip_keys:
                continue
            g = groups.setdefault(key, {"names": Counter(), "exchanges": Counter(), "tickers": Counter(), "urls": [], "layers": set(),
                                        "nodes": Counter(), "co_companies": Counter(), "first": None})
            g["names"][c["name"]] += 1
            g["exchanges"][ex] += 1
            g["tickers"][tk] += 1
            if r["url"] not in g["urls"]:
                g["urls"].append(r["url"])
            g["layers"].add(layer)
            g["nodes"].update(tech)
            g["co_companies"].update(in_graph)
            d = str(r.get("published_at") or "")[:10]
            if d and (g["first"] is None or d < g["first"]["date"]):
                g["first"] = {"date": d, "url": r["url"], "layer": layer_to_evidence(layer)}
            names_to_keys.setdefault(c["name"].strip().lower(), set()).add(key)
    out = []
    for g in groups.values():
        n = len(g["urls"])
        if n < 2 and not (g["layers"] & STRONG_LAYERS):
            continue
        ecos = Counter()
        for nid, k in g["nodes"].items():
            ecos[nodes[nid].get("ecosystem")] += k
        for cid, k in g["co_companies"].items():
            ecos[nodes[cid].get("ecosystem")] += k
        ecos.pop(None, None)
        if not ecos:
            continue
        name = g["names"].most_common(1)[0][0]
        ex = g["exchanges"].most_common(1)[0][0]
        tk = g["tickers"].most_common(1)[0][0]
        cid = f"company:{slug(name)}" if slug(name) and re.fullmatch(r"[A-Za-z0-9 .,&'\-()]+", name) else f"company:{ex.lower().replace(' ', '_')}_{tk.lower()}"
        if cid in ids:
            cid = f"{cid}_{tk.lower()}"
        conflict = any(len(names_to_keys.get(nm.strip().lower(), set())) > 1 for nm in g["names"])
        out.append({
            "n": n,
            "payload": {"id": cid, "kind": "company", "label": f"{name} ({ex} {tk})", "ecosystem": ecos.most_common(1)[0][0],
                        "ticker": tk, "exchange": ex, "size_band": "unknown", "status": "candidate", "first_seen": today,
                        "first_evidence": g["first"], "names": list(g["names"])},
            "reason": (f"그래프 밖 상장사 — 최근 단서 {n}건 (층: {', '.join(sorted(g['layers']))}). 같이 걸린 노드: "
                       f"{', '.join(k for k, _ in g['nodes'].most_common(4)) or '없음'}; 같이 나온 그래프 기업: "
                       f"{', '.join(k for k, _ in g['co_companies'].most_common(3)) or '없음'}. 단서: {' · '.join(g['urls'][:3])}. "
                       "티커·거래소(분류기가 적은 값)와 시가총액을 확인해 size_band 를 채우고, 공급 관계가 원문에 있으면 간선도 같이"
                       + (" — 같은 이름에 티커가 엇갈린다" if conflict else "")),
        })
    out.sort(key=lambda x: -x["n"])
    return out[:COMPANY_CAP]


def layer_to_evidence(layer: str) -> str:
    return {"raw": "standard", "disclosure": "filing", "newsroom": "press", "press": "press", "company": "press", "issue": "press"}.get(layer, "other")


def unmapped_terms(rows: list[dict[str, Any]], graph: dict[str, Any], skip_terms: set[str], bodies: dict[str, str] | None = None) -> list[dict[str, Any]]:
    from wsj.ecosystems.issues import build_lexicon

    node_pats, _ = build_lexicon(graph)
    found: dict[str, dict[str, Any]] = {}
    for r in rows:
        layer = (r.get("extra") or {}).get("layer") or "press"
        if layer not in ("raw", "newsroom"):
            continue
        if any(not n.startswith(("company:", "eco:")) for n in r.get("nodes") or []):
            continue
        text = f"{r.get('title') or ''} {r.get('summary') or ''} {(bodies or {}).get(r['url']) or ''}"[:8000]
        for m in TERM_RE.finditer(text):
            term = re.sub(r"\s+", " ", m.group(0).strip())
            k = term.lower()
            if k in skip_terms or any(p.search(term) for p, _ in node_pats):
                continue
            f = found.setdefault(k, {"term": term, "urls": [], "layers": set()})
            if r["url"] not in f["urls"]:
                f["urls"].append(r["url"])
            f["layers"].add(layer)
    out = [{"n": len(f["urls"]), "payload": {"term": f["term"], "count": len(f["urls"]), "urls": f["urls"][:3], "layers": sorted(f["layers"])},
            "reason": f"기술 노드가 안 걸린 원본·뉴스룸 단서 {len(f['urls'])}건에 나온 식별자. 기존 노드의 codes·별칭인지, 새 후보 노드인지, 버릴 말인지 정한다"}
           for f in found.values()]
    out.sort(key=lambda x: -x["n"])
    return out[:TERM_CAP]


def existing_keys(store: Any) -> tuple[set[tuple[str, str]], set[str]]:
    from wsj.ecosystems.clues import EXCHANGE_GROUP

    keys: set[tuple[str, str]] = set()
    terms: set[str] = set()
    try:
        for p in store.select("ideas.graph_proposals", ["kind", "payload"], {"kind": ["node", "term"]}):
            pl = p.get("payload") or {}
            if p["kind"] == "node" and pl.get("kind") == "company" and pl.get("ticker"):
                grp = EXCHANGE_GROUP.get(str(pl.get("exchange") or "").upper())
                if grp:
                    keys.add((grp, norm_ticker(grp, pl["ticker"])))
            elif p["kind"] == "term" and pl.get("term"):
                terms.add(str(pl["term"]).lower())
    except Exception as exc:  # noqa: BLE001 - 0035 전
        log.warning("ideas.graph_proposals 를 읽지 못함: %s", exc)
    return keys, terms


def graph_keys(graph: dict[str, Any]) -> set[tuple[str, str]]:
    from wsj.ecosystems.clues import EXCHANGE_GROUP

    out = set()
    for n in graph["nodes"]:
        lst = n.get("listing") or {}
        grp = EXCHANGE_GROUP.get(str(lst.get("exchange") or "").upper())
        if n.get("kind") == "company" and grp and lst.get("ticker"):
            out.add((grp, norm_ticker(grp, str(lst["ticker"]))))
    return out


def run(store: Any, graph: dict[str, Any], days: int = 14, dry_run: bool = False) -> dict[str, Any]:
    from wsj.ecosystems.clues import company_resolver

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    today = datetime.now(UTC).date().isoformat()
    rows = store.select("ideas.clues", CLUE_COLS, {"relevant": True, "seen_at": ("gte", since)})
    stats: dict[str, Any] = {"clues": len(rows)}
    fixed = relink(rows, company_resolver(graph))
    stats["relinked"] = len(fixed)
    by = {f["url"]: f["companies"] for f in fixed}
    for r in rows:
        if r["url"] in by:
            r["companies"] = by[r["url"]]
    if fixed and not dry_run:
        try:   # 행 전체를 다시 쓴다 (부분 행 upsert 는 NOT NULL 칸에 막힌다)
            store.upsert("ideas.clues", [r for r in rows if r["url"] in by], ["url"])
        except Exception as exc:  # noqa: BLE001
            log.warning("다시 잇기 저장 실패: %s", exc)
    skip_keys, skip_terms = existing_keys(store)
    comps = outside_companies(rows, graph, skip_keys | graph_keys(graph), today)
    bodies: dict[str, str] = {}
    try:
        raw_urls = [r["url"] for r in rows if ((r.get("extra") or {}).get("layer") in ("raw", "newsroom"))
                    and not any(not n.startswith(("company:", "eco:")) for n in r.get("nodes") or [])]
        if raw_urls:
            bodies = {b["url"]: b.get("body") or "" for b in store.select("ideas.clue_texts", ["url", "body"], {"url": raw_urls, "status": "ok"})}
    except Exception as exc:  # noqa: BLE001 - 0034 전
        log.warning("ideas.clue_texts 를 읽지 못함: %s", exc)
    terms = unmapped_terms(rows, graph, skip_terms, bodies)
    stats.update({"company_candidates": [c["payload"]["label"] for c in comps], "terms": [t["payload"]["term"] for t in terms]})
    props = [{"by": "collect", "kind": "node", "payload": c["payload"], "reason": c["reason"]} for c in comps] + \
            [{"by": "collect", "kind": "term", "payload": t["payload"], "reason": t["reason"]} for t in terms]
    if props and not dry_run:
        try:
            stats["proposed"] = store.insert("ideas.graph_proposals", props)
        except Exception as exc:  # noqa: BLE001 - 0036 전이면 term 이 막힌다 → 기업 후보만
            log.warning("제안을 한 번에 쓰지 못함 (0036 적용 전?): %s", exc)
            only = [p for p in props if p["kind"] != "term"]
            try:
                stats["proposed"] = store.insert("ideas.graph_proposals", only) if only else 0
            except Exception as exc2:  # noqa: BLE001
                log.warning("ideas.graph_proposals 에 쓰지 못함: %s", exc2)
                stats["proposed"] = 0
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--dry-run", action="store_true", help="DB 를 읽기만 하고 제안·다시 잇기를 쓰지 않는다")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    from wsj.config import load_settings
    from wsj.db import make_store

    store = make_store(load_settings())
    graph = load_graph()
    run_id = None
    try:
        if not args.dry_run:
            run_id = store.run_started("candidates", {"days": args.days})
        stats = run(store, graph, args.days, args.dry_run)
        if run_id is not None:
            store.run_finished(run_id, "succeeded", int(stats.get("proposed") or 0) + int(stats.get("relinked") or 0), stats, None)
        print(json.dumps(stats, ensure_ascii=False))
    except Exception as exc:
        if run_id is not None:
            store.run_finished(run_id, "failed", 0, {}, str(exc)[:500])
        raise
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
