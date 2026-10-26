"""온톨로지 기업 → core.companies 유니버스 동기화. ADR-0013.

    python -m wsj.ecosystems.universe sync [--dry-run]

그래프에서 in_universe=true 인 SEC 필러를 core.companies 에 in_universe=true, universe_reason='ontology:<eco>:<nodes>',
sector_bucket='supply_chain' 으로 올린다. sec_universe 주간 재구축은 universe_reason 이 'ontology' 로 시작하면 건드리지 않는다.
그래프에서 빠진 회사는 다시 SIC 규칙으로 돌아간다 (universe_reason 을 지움).
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

from wsj.config import load_settings
from wsj.db import make_store
from wsj.ecosystems.ontology import load_graph

log = logging.getLogger("wsj.ecosystems.universe")


def sync(store, graph: dict, dry_run: bool = False) -> dict:
    wanted: dict[int, str] = {}
    for n in graph["nodes"]:
        if n["kind"] != "company" or not n.get("in_universe"):
            continue
        cik = (n.get("listing") or {}).get("cik")
        if not cik:
            continue
        nodes = sorted(
            e["from"] for e in graph["edges"] if e["to"] == n["id"] and e["relation"] == "offered_by"
        )
        wanted[int(cik)] = f"ontology:{n.get('ecosystem')}:{','.join(nodes)[:200]}"
    existing = {
        int(r["cik"]): r
        for r in store.select(
            "core.companies",
            ["cik", "in_universe", "universe_reason", "sector_bucket"],
            {"cik": list(wanted)},
        )
    }
    prior = store.select(
        "core.companies", ["cik", "universe_reason"], {"universe_reason": ("like", "ontology%")}
    )
    now = datetime.utcnow().isoformat()
    ups, downs = [], []
    for cik, reason in wanted.items():
        if cik not in existing:
            log.warning("CIK %s not in core.companies — run sec_universe first", cik)
            continue
        r = existing[cik]
        if r.get("universe_reason") != reason or not r.get("in_universe"):
            ups.append(
                {
                    "cik": cik,
                    "in_universe": True,
                    "universe_reason": reason,
                    "sector_bucket": "supply_chain",
                    "updated_at": now,
                }
            )
    for r in prior:
        if int(r["cik"]) not in wanted:
            downs.append(
                {"cik": int(r["cik"]), "in_universe": False, "universe_reason": None, "updated_at": now}
            )
    if not dry_run:
        if ups:
            store.upsert("core.companies", ups, ["cik"])
        if downs:
            store.upsert("core.companies", downs, ["cik"])
    return {
        "wanted": len(wanted),
        "promoted": len(ups),
        "demoted": len(downs),
        "missing": len(wanted) - len(existing),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sync"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--store", choices=["postgrest", "sqlite"])
    args = ap.parse_args(argv)
    settings = load_settings()
    if args.store:
        settings.wsj_store = args.store
    logging.basicConfig(level=logging.INFO)
    store = make_store(settings)
    try:
        print(sync(store, load_graph(), args.dry_run))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
