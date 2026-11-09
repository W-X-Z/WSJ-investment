"""④ 빠른 점검 — 초기 아이디어의 후보 종목마다 티커 검증·시세·시총·최근 등락·52주 고점 대비·역DCF.

seeds 형식 (상상 단계 출력, docs/agents/v3/ideate.md):
{"as_of": "YYYY-MM-DD", "seeds": [{"id": "s1", "headline": "...", "archetype": "bottleneck|share_shift|pie|substitution|second_order|policy",
  "hypothesis": "...", "chain": "...", "why_now": "...", "must_be_true": ["..."], "evidence": [clue_id, ...],
  "companies": [{"name": "...", "ticker": "...", "market": "us|kr", "role": "beneficiary|loser", "why": "..."}],
  "status": "open|selected|requested|done|dropped"}]}
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("wsj.ideate")
ARCHETYPES = ("bottleneck", "share_shift", "pie", "substitution", "second_order", "policy")
STATUSES = ("open", "selected", "requested", "done", "dropped")


def validate(spec: dict[str, Any]) -> list[str]:
    errs = []
    if not spec.get("as_of"):
        errs.append("as_of 없음")
    seeds = spec.get("seeds") or []
    if not seeds:
        errs.append("seeds 비어 있음")
    ids = set()
    for i, s in enumerate(seeds):
        w = f"seeds[{i}]"
        for k in ("id", "headline", "hypothesis", "companies"):
            if not s.get(k):
                errs.append(f"{w}.{k} 없음")
        if s.get("id") in ids:
            errs.append(f"{w}.id 중복")
        ids.add(s.get("id"))
        if s.get("archetype") and s["archetype"] not in ARCHETYPES:
            errs.append(f"{w}.archetype 은 {ARCHETYPES}")
        if s.get("status") and s["status"] not in STATUSES:
            errs.append(f"{w}.status 는 {STATUSES}")
        for j, c in enumerate(s.get("companies") or []):
            if c.get("market") not in ("us", "kr"):
                errs.append(f"{w}.companies[{j}].market 은 us|kr")
    return errs


def _quick(ctx: Any, symbol: str) -> dict[str, Any]:
    from wsj.deep.valuation import implied
    from wsj.tools.quote import quote

    out: dict[str, Any] = {}
    try:
        q = quote(symbol, ctx=ctx)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:160]}
    ch = q.get("changes") or {}
    out["price"] = (q.get("live") or {}).get("last_sale") or (q.get("price") or {}).get("close")
    out["market_cap_usd"] = (q.get("market_cap") or {}).get("usd")
    out["change_pct"] = {k: (ch.get(k) or {}).get("pct") for k in ("1m", "3m", "6m", "1y")}
    out["from_52w_high_pct"] = (q.get("range_52w") or {}).get("pct_from_high")
    try:
        from wsj.deep.fin import fin

        f = fin(symbol, years=3, ctx=ctx)
        ttm = f.get("ttm") or {}
        if ttm:
            out["ttm"] = {k: ttm.get(k) for k in ("period_end", "revenue", "revenue_yoy_pct", "op_margin_pct", "net_income", "fcf")}
            mc = (q.get("market_cap") or {}).get("local")
            rd = implied(mc, ttm)
            if rd:
                out["reverse_dcf_cagr_pct"] = rd.get("implied_cagr_pct")
                if rd.get("note"):
                    out["reverse_dcf_note"] = rd["note"]
    except Exception as exc:  # noqa: BLE001
        out["fin_error"] = str(exc)[:120]
    return out


def check(spec: dict[str, Any], ctx: Any) -> dict[str, Any]:
    from wsj.monitor.candidates import resolve_symbol

    for s in spec.get("seeds") or []:
        s.setdefault("status", "open")
        for c in s.get("companies") or []:
            sym = resolve_symbol(ctx, {"name": c["name"], "ticker": c.get("ticker"), "market": c["market"]})
            if not sym:
                c["resolved"] = None
                c["note"] = "티커를 확인하지 못함 (미국·한국 상장 아님이거나 이름 불일치)"
                continue
            c["resolved"] = {k: sym.get(k) for k in ("symbol", "market", "name", "exchange")}
            c["quick"] = _quick(ctx, sym["symbol"])
    return spec


def report_row(spec: dict[str, Any], created_by: str = "ideate (subscription)") -> dict[str, Any]:
    seeds = spec["seeds"]
    subjects = sorted({f"ticker:{c['resolved']['market']}:{c['resolved']['symbol'].lower()}"
                       for s in seeds for c in s.get("companies") or [] if c.get("resolved")})[:40]
    n_sel = sum(1 for s in seeds if s.get("status") in ("selected", "requested"))
    return {"report_id": f"seeds:{spec['as_of']}", "kind": "screen", "as_of": spec["as_of"],
            "title": f"{spec['as_of']} 초기 아이디어 {len(seeds)} · 선택 {n_sel}",
            "subjects": subjects, "body": {"type": "idea_seeds", **spec}, "created_by": created_by}
