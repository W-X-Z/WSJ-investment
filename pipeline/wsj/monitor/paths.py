"""N4 영향 경로 탐색: 진행(proceed) 사건 하나 → 돈이 움직이는 경로 최대 3개와 수혜·피해 상장사.

입력  선별 사건(title·summary·hypothesis_seed·entities) + 그래프 이웃(core.graph_nodes·edges, 있으면)
도구  웹 검색(서버 도구) 사건당 최대 MAX_SEARCHES 회 — 공급망 위치·점유·고객을 가볍게 확인하는 용도
출력  {"headline": 명사형 아이디어 한 줄, "paths": [{"axis", "path", "mechanism", "size", "companies": [{name, ticker, market, role, why}]}]}
미국·한국 상장사만 후보로 쓴다(그 밖 거래소는 이름만 남기지 않는다). 투자 권유·목표가는 쓰지 않는다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("wsj.monitor")

PATH_MODEL = "claude-sonnet-5-5"
MAX_SEARCHES = 3
AXES = ("bottleneck", "substitution", "market_growth", "bargaining", "other")

SYSTEM = """너는 개인 투자 리서치의 1단계 연구원이다. 방금 확인된 '변화 사건' 하나를 받아, 이 변화가 1년 안에 어느 상장사의 이익을 바꾸는지
돈이 움직이는 경로를 최대 3개 찾는다. 깊은 조사는 다음 단계가 하니, 여기서는 공급망 위치와 수혜·피해 기업을 빠르게 짚는다.

보는 축(axis)
- bottleneck: 새 병목이 생기거나 풀린다 — 공급이 수요를 못 따라가는 부품·소재·공정·설비, 그 공급자
- substitution: 기존 기술·제품을 대체한다 — 이기는 쪽과 자리를 잃는 쪽
- market_growth: 시장 파이 자체가 커지거나 줄어든다 — 물량이 늘어나는 층
- bargaining: 가격 협상력이 바뀐다 — 공급자가 판가를 올릴 수 있는지(대안이 없는지, 증설이 어려운지)
- other: 그 밖 (규제 비용, 보조금, 수입 제한 등)

원칙
1. 사건에 직접 이름이 나온 회사뿐 아니라 전·후방(부품·소재·장비·고객)에서 더 크게 영향받는 작은 회사를 찾는다. 시총 대비 영향이 큰 쪽을 앞에 둔다.
2. 후보는 미국(NYSE·Nasdaq 등) 또는 한국(KOSPI·KOSDAQ) 상장사만. 티커를 아는 만큼 쓴다(미국 'VRT', 한국 6자리 '001440'). 모르면 null.
3. 웹 검색은 공급망 위치·점유·고객 확인에만 쓴다(최대 3번). 단서에 없고 확인 못 한 숫자는 쓰지 않는다.
4. size: 그 회사 1년 이익에 미칠 크기 — large(이익을 크게 바꾼다) | medium | small. 근거는 why 에 한 문장.
5. headline: 투자 아이디어를 읽기 쉬운 명사형 한 줄로(예: "HBM 고집적화에 따른 유리 인터포저 수요 확대").
6. 매수·매도·목표가를 쓰지 않는다.

출력은 JSON 객체 하나(설명·코드블록 없이):
{"headline": "…", "paths": [{"axis": "bottleneck", "path": "변화 → 무엇이 → 누구에게(한 줄)", "mechanism": "한두 문장",
  "size": "large", "companies": [{"name": "…", "ticker": "…", "market": "us", "role": "beneficiary", "why": "한 문장"}]}]}
role 은 beneficiary | loser. 경로가 없으면 {"headline": null, "paths": []}."""

REPAIR = "직전 응답이 JSON 형식이 아니다({error}). 같은 내용을 형식에 맞는 JSON 객체 하나로만 다시 써라."


def graph_context(store: Any | None, entities: list[str], limit: int = 40) -> dict[str, Any]:
    """사건 주인공 노드와 이웃 — 이름·티커·관계. DB 가 없으면 빈 값."""
    if store is None or not entities:
        return {}
    try:
        edges = store.select("core.graph_edges", ["src", "dst", "relation", "exposure_pct", "note"], {"src": entities}, limit=limit)
        edges += store.select("core.graph_edges", ["src", "dst", "relation", "exposure_pct", "note"], {"dst": entities}, limit=limit)
        ids = sorted({e["src"] for e in edges} | {e["dst"] for e in edges} | set(entities))
        nodes = store.select("core.graph_nodes", ["id", "kind", "name", "ticker", "exchange"], {"id": ids[:150]})
    except Exception as exc:  # noqa: BLE001
        log.warning("graph context failed: %s", str(exc)[:120])
        return {}
    names = {n["id"]: n for n in nodes}
    return {"nodes": [{k: v for k, v in n.items() if v} for n in nodes if n["id"] in entities or n.get("ticker")][:60],
            "edges": [f"{names.get(e['src'], {}).get('name') or e['src']} —{e['relation']}→ "
                      f"{names.get(e['dst'], {}).get('name') or e['dst']}"
                      + (f" ({e['exposure_pct']}%)" if e.get("exposure_pct") else "") for e in edges[:limit]]}


def build_user(event: dict[str, Any], graph: dict[str, Any]) -> str:
    ev = {k: event.get(k) for k in ("title", "summary", "hypothesis_seed", "reason", "entities", "novelty")}
    return json.dumps({"event": ev, "graph": graph or None}, ensure_ascii=False)


def clean(raw: dict[str, Any]) -> dict[str, Any]:
    paths = []
    for p in (raw.get("paths") or [])[:3]:
        if not isinstance(p, dict):
            continue
        comps = []
        for c in p.get("companies") or []:
            if not isinstance(c, dict) or not c.get("name"):
                continue
            mk = str(c.get("market") or "").lower()
            if mk not in ("us", "kr"):
                continue
            comps.append({"name": str(c["name"])[:120], "ticker": (str(c["ticker"]).strip().upper() or None) if c.get("ticker") else None,
                          "market": mk, "role": c.get("role") if c.get("role") in ("beneficiary", "loser") else "beneficiary",
                          "why": str(c.get("why") or "")[:300]})
        if not comps:
            continue
        axis = p.get("axis") if p.get("axis") in AXES else "other"
        paths.append({"axis": axis, "path": str(p.get("path") or "")[:200], "mechanism": str(p.get("mechanism") or "")[:500],
                      "size": p.get("size") if p.get("size") in ("large", "medium", "small") else "medium",
                      "companies": comps[:5]})
    return {"headline": (str(raw.get("headline")).strip()[:120] or None) if raw.get("headline") else None, "paths": paths}


def explore(llm: Any, event: dict[str, Any], graph: dict[str, Any] | None = None, model: str = PATH_MODEL,
            max_searches: int = MAX_SEARCHES) -> dict[str, Any]:
    raw, comps = llm.complete_json(SYSTEM, build_user(event, graph or {}), model, REPAIR, max_tokens=6000,
                                   web_search_max_uses=max_searches or None, effort="medium")
    from wsj.briefs.llm import sum_usage

    out = clean(raw)
    out["usage"] = sum_usage(comps)
    out["citations"] = [c for comp in comps for c in comp.citations][:12]
    return out
