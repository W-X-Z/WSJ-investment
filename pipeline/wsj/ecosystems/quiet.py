"""조용함 검사 (ADR-0026 결정 7) — 테제의 수혜 기업이 '이미 움직였나' 를 가격으로 잰다.

    python -m wsj.ecosystems.quiet                      # 활성 테제 전부, JSON
    python -m wsj.ecosystems.quiet --sql                # put_theses 갱신문 한 줄 (quiet_check 만 갈아 끼움)
    python -m wsj.ecosystems.quiet --companies company:skhynix,company:mu

읽기는 공개 뷰(v_theses·v_price_context, publishable 키)뿐이다. 기업 → 가격 키는 그래프의 listing 으로 (prices.px_key).
판정은 기계적이다 — 해석(되돌림이 기회인가)은 테제 작업이 stage_reason 에 쓴다.

기업 판정 (위에서부터 처음 맞는 것):
- unmeasured  : 가격 없음 (비상장·미수집)
- moved_reset : 12개월 +50% 이상인데 고점 대비 −35% 이하 — 시장이 한 번 반영했다가 크게 되돌림
- moved       : 12개월 +100% 이상, 또는 +50% 이상이면서 고점 대비 −20% 안
- sold_off    : 고점 대비 −50% 이하 — 12개월 안에 크게 오른 적이 있고 절반 넘게 잃었다. 시장이 '안 본' 것이 아니라 '보고 버린' 것
- quiet       : 12개월 +30% 미만이고 3개월 +20% 미만, 고점 대비 −50% 안
- mixed       : 그 밖
같은 숫자를 우주 중앙값(v_price_context, 200일 이상)과 나란히 낸다 — 2026-10 처럼 전체가 고점 대비 −40% 인 때는 절대 판정만으로 읽으면 안 된다.
테제 판정은 primary 수혜 기업(없으면 전체)의 측정된 판정으로: moved 계열이 절반 이상 → moved (moved_reset 이 더 많으면 moved_reset),
quiet 가 절반 이상이고 moved 가 없음 → quiet, 측정된 것이 없음 → unmeasured, 그 밖 → mixed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

from wsj.ecosystems.ontology import load_graph
from wsj.ecosystems.prices import px_key

MOVED_12M, MOVED_NEAR_HIGH, RESET_FROM_HIGH, BIG_12M, SOLD_FROM_HIGH = 50.0, -20.0, -35.0, 100.0, -50.0
QUIET_12M, QUIET_3M = 30.0, 20.0


def _f(x: Any) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def company_verdict(px: dict[str, Any] | None) -> str:
    if not px:
        return "unmeasured"
    r12, r3, fh = _f(px.get("r12m")), _f(px.get("r3m")), _f(px.get("from_high"))
    if r12 is None:
        return "unmeasured"
    if r12 >= MOVED_12M and fh is not None and fh <= RESET_FROM_HIGH:
        return "moved_reset"
    if r12 >= BIG_12M or (r12 >= MOVED_12M and (fh is None or fh >= MOVED_NEAR_HIGH)):
        return "moved"
    if fh is not None and fh <= SOLD_FROM_HIGH:
        return "sold_off"
    if r12 < QUIET_12M and (r3 is None or r3 < QUIET_3M):
        return "quiet"
    return "mixed"


def thesis_verdict(rows: list[dict[str, Any]]) -> str:
    prim = [r for r in rows if r.get("role") == "primary"] or rows
    measured = [r["verdict"] for r in prim if r["verdict"] != "unmeasured"]
    if not measured:
        return "unmeasured"
    n = len(measured)
    moved, reset, quiet, sold = measured.count("moved"), measured.count("moved_reset"), measured.count("quiet"), measured.count("sold_off")
    if moved + reset >= n / 2:
        return "moved_reset" if reset > moved else "moved"
    if sold >= n / 2:
        return "sold_off"
    if quiet >= n / 2 and moved == 0:
        return "quiet"
    return "mixed"


def listing_keys(graph: dict[str, Any]) -> dict[str, str]:
    out = {}
    for n in graph["nodes"]:
        if n.get("kind") == "company":
            lst = n.get("listing") or {}
            k = px_key(lst.get("exchange"), lst.get("ticker"))
            if k:
                out[n["id"]] = k
    return out


def quiet_check(companies: list[dict[str, Any]], keys: dict[str, str], px: dict[str, dict[str, Any]], as_of: str,
                universe: dict[str, Any] | None = None) -> dict[str, Any]:
    """companies = [{company, role?}] (테제의 beneficiaries 모양)."""
    rows = []
    for b in companies:
        cid = b.get("company")
        if not isinstance(cid, str) or not cid.startswith("company:"):
            continue
        k = keys.get(cid)
        p = px.get(k) if k else None
        row: dict[str, Any] = {"company": cid, "role": b.get("role"), "px_key": k}
        if p:
            row.update({"px_as_of": p.get("as_of"), "px_1m_pct": _f(p.get("r1m")), "px_3m_pct": _f(p.get("r3m")),
                        "px_12m_pct": _f(p.get("r12m")), "from_high_pct": _f(p.get("from_high"))})
        else:
            row["note"] = "비상장" if not k else "가격 미수집"
        row["verdict"] = company_verdict(p)
        rows.append(row)
    v = thesis_verdict(rows)
    counts = {s: sum(1 for r in rows if r["verdict"] == s) for s in ("quiet", "mixed", "moved", "moved_reset", "sold_off", "unmeasured")}
    out = {"as_of": as_of, "method": "wsj.ecosystems.quiet v2", "verdict": v, "counts": counts, "companies": rows}
    if universe:
        out["universe"] = universe
    return out


def universe_stats(px: dict[str, dict[str, Any]], min_points: int = 200) -> dict[str, Any]:
    """가격 우주의 중앙값 — 절대 판정을 읽는 기준선."""
    rows = [r for r in px.values() if (r.get("points") or 0) >= min_points]

    def med(k: str) -> float | None:
        xs = sorted(v for v in (_f(r.get(k)) for r in rows) if v is not None)
        if not xs:
            return None
        m = len(xs) // 2
        return round(xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2, 1)

    fh = [_f(r.get("from_high")) for r in rows]
    return {"n": len(rows), "median_1m_pct": med("r1m"), "median_3m_pct": med("r3m"), "median_12m_pct": med("r12m"),
            "median_from_high_pct": med("from_high"), "share_from_high_le_40": round(sum(1 for x in fh if x is not None and x <= -40) / max(1, len(rows)), 2)}


def _public() -> tuple[Any, str, str]:
    from wsj.http import HttpClient

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "https://dcatgfivsvbktylmtvgf.supabase.co"
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_KEY")
    if not key:
        raise SystemExit("SUPABASE_PUBLISHABLE_KEY 가 필요하다 (공개 읽기 키 — Supabase MCP get_publishable_keys 로 얻는다)")
    return HttpClient("WSJ-investment quiet", timeout=30, max_retries=2), url, key


def update_sql(checks: dict[str, dict[str, Any]]) -> str:
    """quiet_check 만 바꾸는 put_theses 문 — 나머지 항목은 서버가 지금 행에서 읽는다 (쓰기 경로는 put_theses 하나)."""
    payload = json.dumps(checks, ensure_ascii=False, separators=(",", ":"))
    return ("select ideas.put_theses(jsonb_agg(to_jsonb(t) - 'created_at' - 'updated_at' || jsonb_build_object('quiet_check', q.v -> t.thesis_key))) "
            f"from ideas.theses t, (select $q${payload}$q$::jsonb v) q where q.v ? t.thesis_key;")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thesis", help="thesis_key (없으면 활성 테제 전부)")
    ap.add_argument("--companies", help="쉼표로 구분한 company id — 테제 없이 기업만 잴 때")
    ap.add_argument("--sql", action="store_true", help="quiet_check 만 바꾼 put_theses 갱신문을 출력")
    args = ap.parse_args(argv)
    from wsj.ecosystems.ideas import fetch_public_view

    http, url, key = _public()
    try:
        px = {r["ticker"]: r for r in fetch_public_view(http, url, key, "v_price_context")}
        theses = [] if args.companies else fetch_public_view(http, url, key, "v_theses", {"status": "eq.active"})
    finally:
        http.close()
    keys = listing_keys(load_graph())
    as_of = max((r.get("as_of") or "" for r in px.values()), default="") or datetime.now(UTC).date().isoformat()
    uni = universe_stats(px)
    if args.companies:
        print(json.dumps(quiet_check([{"company": c.strip()} for c in args.companies.split(",") if c.strip()], keys, px, as_of, uni), ensure_ascii=False, indent=1))
        return 0
    if args.thesis:
        theses = [t for t in theses if t["thesis_key"] == args.thesis]
        if not theses:
            print(f"테제 없음: {args.thesis}", file=sys.stderr)
            return 1
    out = [{"thesis_key": t["thesis_key"], "kind": t.get("kind"), "quiet_check": quiet_check(t.get("beneficiaries") or [], keys, px, as_of, uni)}
           for t in theses]
    print(update_sql({o["thesis_key"]: o["quiet_check"] for o in out}) if args.sql else json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
