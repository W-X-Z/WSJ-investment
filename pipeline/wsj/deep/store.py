"""N23 저장: 심층 리서치 결과 JSON → 원천(직접 연 출처) → 리포트.

입력(오케스트레이터가 쓴다):
{
  "symbol": "FPS", "market": "us", "as_of": "2026-11-10",
  "title": "Forgent Power Solutions — 스폰서 매각 수급 할인과 백로그 성장의 괴리",
  "stars": 3, "verdict": "한 문장 판단",
  "candidate": {"report_id": "screen:2026-11-10", "id": "c3"},      # 어디서 왔는지 (선택)
  "sections": {"summary": "…", "conclusion": "…", "profile": "…", "price_story": "…", "fundamentals": "…",
               "industry_peers": "…", "valuation": "…", "future_value": "…", "risks": "…", "estimates": "…"},
  "data": {"scenario": {…}, "peers": {…}, "story_moves": […]},      # 계산 결과 원본 (선택)
  "sources": [{"url": "https://…", "title": "…", "published_at": "2026-09-15", "summary": "…", "facts": []}],
  "notion_url": "https://…", "created_by": "orchestrator-v3"
}
  1) sources → ideas.put_research_sources (같은 url 은 합쳐진다) → clue_id
  2) research.put_reports kind='idea', report_id 'idea:<시장>:<티커>:<날짜>', cites=clue_id
"""

from __future__ import annotations

import re
from typing import Any

SECTION_ORDER = ("summary", "conclusion", "profile", "price_story", "fundamentals", "industry_peers", "valuation",
                 "future_value", "risks", "estimates")


class ReportError(ValueError):
    pass


def report_id(market: str, symbol: str, as_of: str) -> str:
    return f"idea:{market}:{re.sub(r'[^a-z0-9.-]+', '-', symbol.lower())}:{as_of}"[:80]


def validate(spec: dict[str, Any]) -> list[str]:
    errs = []
    for k in ("symbol", "market", "as_of", "title", "stars", "verdict", "sections"):
        if spec.get(k) in (None, "", {}):
            errs.append(f"{k} 필수")
    if spec.get("stars") is not None and spec["stars"] not in (1, 2, 3, 4, 5):
        errs.append("stars 는 1~5 정수")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(spec.get("as_of") or "")):
        errs.append("as_of 는 YYYY-MM-DD")
    secs = spec.get("sections") or {}
    if isinstance(secs, dict):
        missing = [s for s in ("summary", "conclusion") if not secs.get(s)]
        if missing:
            errs.append(f"sections 에 {', '.join(missing)} 필수 (요약 박스·결론)")
    for i, s in enumerate(spec.get("sources") or []):
        if not str(s.get("url", "")).startswith(("http://", "https://")) or not s.get("title"):
            errs.append(f"sources[{i}] 는 url·title 필수")
    return errs


def save(store: Any, spec: dict[str, Any]) -> dict[str, Any]:
    errs = validate(spec)
    if errs:
        raise ReportError("; ".join(errs))
    if not hasattr(store, "rpc"):
        raise ReportError(f"{type(store).__name__} 는 rpc 를 못 부른다 — WSJ_STORE=postgrest")
    cites: list[int] = []
    src_res = None
    sources = [{k: v for k, v in s.items() if k in ("url", "title", "published_at", "summary", "facts", "source_name")}
               | {"source_kind": s.get("source_kind") or "agent_research"} for s in spec.get("sources") or []]
    if sources:
        src_res = store.rpc("ideas.put_research_sources", {"rows": sources}) or {}
        cites = [x["clue_id"] for x in src_res.get("ids") or [] if x.get("clue_id")]
    rid = report_id(spec["market"], spec["symbol"], spec["as_of"])
    body = {"type": "deep_research", "symbol": spec["symbol"], "market": spec["market"],
            "sections": {k: spec["sections"][k] for k in SECTION_ORDER if spec["sections"].get(k)}
            | {k: v for k, v in spec["sections"].items() if k not in SECTION_ORDER},
            "data": spec.get("data") or {}, "candidate": spec.get("candidate"),
            "sources": [{"url": s["url"], "title": s["title"], "published_at": s.get("published_at")} for s in sources]}
    row = {"report_id": rid, "kind": "idea", "title": spec["title"][:200], "as_of": spec["as_of"],
           "subjects": [f"ticker:{spec['market']}:{spec['symbol'].lower()}"] + list(spec.get("subjects") or []),
           "stars": int(spec["stars"]), "verdict": spec["verdict"][:400], "body": body, "cites": cites,
           "created_by": (spec.get("created_by") or "orchestrator-v3")[:80]}
    if spec.get("notion_url"):
        row["notion_url"] = spec["notion_url"]
    res = store.rpc("research.put_reports", {"rows": [row]}) or {}
    if res.get("rejected"):
        raise ReportError(f"research.put_reports 거부: {res['rejected']}")
    return {"report_id": rid, "cites": cites, "sources": src_res, "report": res}
