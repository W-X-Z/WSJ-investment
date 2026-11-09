"""N6 주가 반응 + N7 선별.

N6  후보마다 사건일 전후 반응(tools.event: d-1→d+1 초과 수익률, 거래량 배수)과 1개월 등락. 이미 크게 움직였으면 그 이유부터 본다.
N7  후보 전체를 한 번에 중형 모델에 보여 주고 하루 최대 MAX_PICK 건을 고른다. 기준:
      1년 안에 그 기업의 이익이나 멀티플을 바꿀 크기 · 시총 대비 영향 · 주가 반응(이미 반영됐는지 스스로 묻는다)
    애널리스트 커버리지가 있다는 이유로 깎지 않는다. 고르지 않은 후보도 노션에 남고 사용자가 심층 요청할 수 있다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from wsj.tools.context import ToolContext, ToolError

log = logging.getLogger("wsj.monitor")

PICK_MODEL = "claude-sonnet-5-5"
MAX_PICK = 2


def reaction(ctx: ToolContext, symbol: str, day: str | None) -> dict[str, Any] | None:
    if not day:
        return None
    from wsj.tools.event import event

    try:
        r = event(symbol, day[:10], ctx=ctx)
    except ToolError as exc:
        return {"error": str(exc)[:120]}
    w = r.get("returns") or {}
    win = next((w[k] for k in ("d-1_to_d+1",) if k in w), None) or next(iter(w.values()), {})
    wide = next((w[k] for k in ("d-5_to_d+5",) if k in w), None) or {}
    vol = (r.get("volume") or {}).get("d") or {}
    return {"date": r.get("event_date") or day[:10], "return_pct": win.get("return_pct"), "excess_pct": win.get("excess_pct"),
            "abnormal_pct": win.get("abnormal_pct"), "wide_return_pct": wide.get("return_pct"),
            "volume_ratio": vol.get("ratio")}


SYSTEM = """너는 개인 투자 리서치의 선별 담당이다. 오늘의 후보(사건 → 경로 → 종목) 목록을 보고, 깊이 조사할 종목·아이디어를 최대 {n}건 고른다.
투자 기간은 1년 내외, 목표는 1년 안팎 2~3배가 가능한 기회다. 미국·한국 상장사만.

기준
1. 크기: 이 변화가 1년 안에 그 회사의 이익이나 멀티플을 바꿀 만큼 큰가. 시총이 작을수록 같은 변화의 영향이 크다(market_cap_usd).
2. 구조: 병목·대체·시장 확대·협상력 중 무엇으로 돈을 버는지가 분명한가. 사건이 주인공 회사보다 전·후방의 작은 회사에 더 큰 경우를 찾는다.
3. 반응: 사건 전후 주가가 이미 크게 움직였는지(reaction) 스스로 묻는다. 움직였다면 그 크기가 변화의 크기에 비해 충분한지 본다 —
   움직였다는 이유만으로 빼지 않는다. 애널리스트가 다룬다는 이유로 빼지 않는다.
4. 같은 사건에서 둘을 고르지 말고, 서로 다른 사건을 고른다(가능하면).

출력은 JSON 객체 하나: {{"picks": [{{"id": "후보 id", "why": "한국어 한두 문장"}}], "skipped_note": "고르지 않은 주요 후보를 뺀 이유 한 문장"}}"""

REPAIR = "직전 응답이 JSON 형식이 아니다({error}). 형식에 맞는 JSON 객체 하나로만 다시 써라."


def brief_row(c: dict[str, Any]) -> dict[str, Any]:
    return {k: c.get(k) for k in ("id", "event_title", "headline", "axis", "path", "mechanism", "size", "role", "why",
                                  "symbol", "market", "name", "market_cap_usd", "reaction")}


def choose(llm: Any, candidates: list[dict[str, Any]], n: int = MAX_PICK, model: str = PICK_MODEL) -> dict[str, Any]:
    pool = [c for c in candidates if c.get("role") == "beneficiary"] or candidates
    if not pool:
        return {"picks": [], "usage": None}
    raw, comps = llm.complete_json(SYSTEM.format(n=n), json.dumps([brief_row(c) for c in pool], ensure_ascii=False),
                                   model, REPAIR, max_tokens=3000, effort="medium")
    ids = {c["id"] for c in pool}
    picks, seen = [], set()
    for p in raw.get("picks") or []:
        if isinstance(p, dict) and p.get("id") in ids and p["id"] not in seen:
            picks.append({"id": p["id"], "why": str(p.get("why") or "")[:400]})
            seen.add(p["id"])
        if len(picks) >= n:
            break
    from wsj.briefs.llm import sum_usage

    return {"picks": picks, "skipped_note": raw.get("skipped_note"), "usage": sum_usage(comps)}


def apply_picks(candidates: list[dict[str, Any]], picks: list[dict[str, Any]]) -> None:
    why = {p["id"]: p["why"] for p in picks}
    for c in candidates:
        if c["id"] in why:
            c["status"] = "selected"
            c["pick_reason"] = why[c["id"]]
