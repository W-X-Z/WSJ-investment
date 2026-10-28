"""기회 스캔 — 엔진이 매일 '어디를 더 봐야 하나'를 찾는다 (ADR-0017). 결과는 아이디어 작성(leads)과 개선 예약작업이 쓴다.

  company_leads   최근 14일 기업 자신의 소식(★2+ 또는 원문 확인)이 있는데 활성 아이디어가 없는 기업
  bottlenecks     병목별 활동(최근 30일 이슈·상태 관측치)과 상장 공급사, 그중 아이디어가 없는 공급사
  price_leads     설명 안 된 가격 급변: 1개월 ±30% 이상 또는 거래량 3배인데 최근 14일 기업 소식이 없는 그래프 상장사
  untagged_issues 노드가 없는 활성 이슈 (그래프에 노드·별칭이 필요할 수 있다)
  second_order    선행 단서 (ADR-0017 개정 2): 최근 14일 중요 이슈(★2+)의 노드에서 그래프를 2단계 이상 타고 닿는 상장사 중
                  아직 자기 소식이 없고 주가가 조용한 곳 — "변화는 일어났는데 시장이 아직 안 본 다음 고리"

    python -m wsj.ecosystems.scan --from-public --out scan.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from wsj.ecosystems.assess import Structure, price_context
from wsj.ecosystems.scope import in_scope


def _get(e: Any, k: str) -> Any:
    return e.get(k) if isinstance(e, dict) else getattr(e, k, None)


def _date(v: Any) -> str:
    return (v.isoformat() if hasattr(v, "isoformat") else str(v or ""))[:10]


def states(indicators: list[dict[str, Any]], st: Structure) -> list[dict[str, Any]]:
    """병목 상태 관측치(category=observation)의 최신값 — 아이디어 작성 입력용."""
    out = []
    for i in indicators:
        if i.get("category") != "observation":
            continue
        out.append({"indicator_id": i["indicator_id"], "label": i.get("label"), "value": i.get("value"), "unit": i.get("unit"), "as_of": _date(i.get("as_of")),
                    "value_1m": i.get("value_1m"), "nodes": [st.label(n) for n in i.get("nodes") or []], "source": i.get("source"), "url": i.get("source_url")})
    return sorted(out, key=lambda x: x["as_of"], reverse=True)[:30]


def leads(graph: dict[str, Any], issues: list[dict[str, Any]], indicators: list[dict[str, Any]], events: list[Any],
          existing: list[dict[str, Any]], prices: dict[str, dict[str, Any]], now: datetime) -> dict[str, Any]:
    st = Structure(graph)
    nodes = st.nodes
    covered = {c.get("id") for x in existing for c in x.get("companies") or []} | {x.get("primary_company") for x in existing}
    cut14 = (now - timedelta(days=14)).date().isoformat()
    cut30 = (now - timedelta(days=30)).date().isoformat()

    # 1) 기업 소식은 있는데 아이디어가 없는 기업
    by_co: dict[str, list[Any]] = defaultdict(list)
    for e in events:
        cid = _get(e, "company_id")
        verified = bool((_get(e, "extra") or {}).get("verified_by")) or bool(_get(e, "verified"))
        if _date(_get(e, "published_at")) >= cut14 and (int(_get(e, "importance") or 1) >= 2 or verified) and cid in nodes:
            by_co[cid].append(e)
    company_leads = []
    for cid, evs in by_co.items():
        if cid in covered:
            continue
        n = nodes[cid]
        if n.get("size_band") in ("private",) or not (n.get("listing") or {}).get("ticker") or not in_scope(n):
            continue
        evs.sort(key=lambda e: (_date(_get(e, "published_at")), int(_get(e, "importance") or 1)), reverse=True)
        top = evs[0]
        company_leads.append({"company_id": cid, "company": st.label(cid), "size_band": n.get("size_band"), "events": len(evs),
                              "latest": _date(_get(top, "published_at")), "title": _get(top, "title"), "text": (_get(top, "text") or "")[:200] or None,
                              "url": _get(top, "url"), "bottlenecks": [st.label(b) for b in st.bottlenecks(cid)[:2]],
                              "price": price_context(prices, n)})
    size_rank = {"micro": 0, "small": 1, "mid": 2, "large": 3, "mega": 4}
    company_leads.sort(key=lambda x: (-(len(x["bottlenecks"]) > 0), -x["events"], size_rank.get(x["size_band"] or "", 3)))

    # 2) 병목 보드
    mit: dict[str, set[str]] = defaultdict(set)
    for e in graph["edges"]:
        if e.get("relation") == "mitigated_by" and nodes.get(e["from"], {}).get("kind") == "bottleneck":
            mit[e["from"]].add(e["to"])
    board = []
    for b in (n["id"] for n in graph["nodes"] if n.get("kind") == "bottleneck"):
        watch = {b} | mit[b]
        recent = [i for i in issues if _date(i.get("latest_published_at") or i.get("last_seen")) >= cut30 and set(i.get("nodes") or []) & watch]
        obs = [i for i in indicators if i.get("category") == "observation" and set(i.get("nodes") or []) & watch]
        sups = sorted({c for x in mit[b] for c in st.suppliers.get(x, ())})
        if not recent and not obs:
            continue
        activity = sum(int(i.get("importance") or 1) for i in recent) + 3 * len(obs)
        board.append({"bottleneck": b, "label": st.label(b), "ecosystem": nodes[b].get("ecosystem"), "activity": activity,
                      "issues": [{"title": i.get("title"), "date": _date(i.get("latest_published_at")), "importance": i.get("importance")}
                                 for i in sorted(recent, key=lambda i: -int(i.get("importance") or 1))[:3]],
                      "states": [{"label": o.get("label"), "value": o.get("value"), "unit": o.get("unit"), "as_of": _date(o.get("as_of"))} for o in obs[:3]],
                      "suppliers": [st.label(c) for c in sups][:10],
                      "uncovered": [{"company_id": c, "company": st.label(c), "size_band": nodes[c].get("size_band")}
                                    for c in sups if c not in covered and nodes[c].get("size_band") not in ("mega",) and in_scope(nodes[c])][:8]})
    board.sort(key=lambda x: -x["activity"])

    # 3) 설명 안 된 가격 급변
    recent_co = {_get(e, "company_id") for e in events if _date(_get(e, "published_at")) >= cut14}
    price_leads = []
    for n in graph["nodes"]:
        if n.get("kind") != "company" or not in_scope(n):
            continue
        pc = price_context(prices, n)
        if not pc:
            continue
        big = (pc.get("r1m") is not None and abs(pc["r1m"]) >= 30) or (pc.get("vol_ratio") is not None and pc["vol_ratio"] >= 3)
        if big and n["id"] not in recent_co:
            price_leads.append({"company_id": n["id"], "company": st.label(n["id"]), "size_band": n.get("size_band"), "price": pc,
                                "bottlenecks": [st.label(b) for b in st.bottlenecks(n["id"])[:2]]})
    price_leads.sort(key=lambda x: -abs(x["price"].get("r1m") or 0))

    untagged = [{"issue_key": i.get("issue_key"), "title": i.get("title"), "date": _date(i.get("latest_published_at"))}
                for i in issues if not (i.get("nodes") or [])]
    second = second_order(graph, st, issues, recent_co, covered, prices, cut14)
    return {"as_of": now.isoformat(timespec="seconds"), "company_leads": company_leads[:12], "bottlenecks": board[:12],
            "price_leads": price_leads[:10], "untagged_issues": untagged, "second_order": second[:15]}


def second_order(graph: dict[str, Any], st: Structure, issues: list[dict[str, Any]], recent_co: set[str], covered: set[str],
                 prices: dict[str, dict[str, Any]], cut14: str, min_hops: int = 2, max_depth: int = 5) -> list[dict[str, Any]]:
    """최근 중요 이슈의 노드 → 영향 경로 → 상장사. 이슈에 이름이 나온 기업(1차)과 최근 소식이 있는 기업은 빼고, 2단계 이상 떨어진
    소형·중형 상장사를 경로 확신도 × 이슈 중요도 순으로. 주가가 이미 움직였으면(1개월 +30%) 뒤로 보낸다."""
    from wsj.ecosystems.impact import influence_paths
    from wsj.ecosystems.ontology import load_ontology

    try:
        onto = load_ontology()
    except Exception:  # noqa: BLE001
        return []
    acc: dict[str, dict[str, Any]] = {}
    cache: dict[str, list[dict[str, Any]]] = {}
    for i in issues:
        if _date(i.get("latest_published_at") or i.get("last_seen")) < cut14 or int(i.get("importance") or 0) < 5:
            continue
        named = {c.get("id") if isinstance(c, dict) else c for c in i.get("companies") or []}
        for nid in i.get("nodes") or []:
            if nid not in st.nodes:
                continue
            if nid not in cache:
                try:
                    cache[nid] = influence_paths(graph, nid, max_depth=max_depth, onto=onto)
                except KeyError:
                    cache[nid] = []
            for p in cache[nid]:
                cid = p["company_id"]
                n = st.nodes.get(cid) or {}
                if cid in named or cid in recent_co or cid in covered or not (n.get("listing") or {}).get("ticker") or not in_scope(n):
                    continue
                if n.get("size_band") not in ("micro", "small", "mid"):
                    continue
                hops = len(p["path"]) - 1
                if hops < min_hops:
                    continue
                w = float(p["confidence"]) * (1 + 0.1 * int(i.get("importance") or 0))
                cur = acc.get(cid)
                if cur is None or w > cur["w"]:
                    acc[cid] = {"w": w, "company_id": cid, "company": st.label(cid), "size_band": n.get("size_band"), "hops": hops,
                                "path": [x["node_id"] for x in p["path"]], "path_labels": [st.label(x["node_id"]) for x in p["path"]],
                                "confidence": round(float(p["confidence"]), 3), "trigger": i.get("title"), "trigger_key": i.get("issue_key"),
                                "trigger_date": _date(i.get("latest_published_at"))}
    out = []
    for c in acc.values():
        pc = price_context(prices, st.nodes.get(c["company_id"])) or {}
        quiet = not ((pc.get("r1m") or 0) >= 30 or (pc.get("vol_ratio") or 0) >= 3)
        c["price"] = {k: pc.get(k) for k in ("r1m", "r12m", "from_low", "market_cap_usd")} if pc else None
        c["quiet"] = quiet
        c["rank"] = c["w"] * (1.0 if quiet else 0.4)
        out.append(c)
    out.sort(key=lambda x: -x["rank"])
    return out


def compact(ld: dict[str, Any]) -> dict[str, Any]:
    """아이디어 작성 입력용으로 줄인 단서."""
    return {
        "company_leads": [{k: x[k] for k in ("company_id", "company", "latest", "title", "text", "bottlenecks") if x.get(k)} for x in ld["company_leads"][:8]],
        "bottlenecks": [{"label": b["label"], "activity": b["activity"], "states": b["states"], "uncovered": [u["company_id"] for u in b["uncovered"][:5]]}
                        for b in ld["bottlenecks"][:6]],
        "price_leads": [{"company_id": p["company_id"], "r1m": p["price"].get("r1m"), "vol_ratio": p["price"].get("vol_ratio")} for p in ld["price_leads"][:6]],
        "second_order": [{k: x[k] for k in ("company_id", "company", "size_band", "hops", "path", "confidence", "trigger", "quiet", "price") if x.get(k) is not None}
                         for x in ld.get("second_order", [])[:10]],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-public", action="store_true")
    ap.add_argument("--snapshot", type=Path, help="ideas --snapshot-out 폴더")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    from wsj.ecosystems.ontology import load_graph

    graph = load_graph()
    if args.snapshot:
        rd = lambda n: json.loads((args.snapshot / f"{n}.json").read_text(encoding="utf-8")) if (args.snapshot / f"{n}.json").exists() else []  # noqa: E731
        inputs = {k: rd(k) for k in ("issues", "indicators", "existing", "events", "prices")}
    else:
        from wsj.ecosystems.ideas import load_public_inputs, public_credentials

        inputs = load_public_inputs(*public_credentials())
    prices = {p["ticker"]: p for p in inputs.get("prices") or []}
    res = leads(graph, inputs["issues"], inputs["indicators"], inputs["events"], inputs["existing"], prices, datetime.now(UTC))
    text = json.dumps(res, ensure_ascii=False, indent=1, default=str)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps({k: len(v) for k, v in res.items() if isinstance(v, list)}))
    for b in res["bottlenecks"][:5]:
        print(f"  [{b['activity']:>3}] {b['label']} — 미커버 {', '.join(u['company'] for u in b['uncovered'][:4])}")
    for c in res["company_leads"][:5]:
        title = re.sub(r"\s+", " ", c["title"] or "")[:70]
        print(f"  · {c['company']} {c['latest']} {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
