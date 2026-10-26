"""온톨로지 기반 공급사 발굴 — 병목·공정·소재·부품 노드의 별칭을 10-K/20-F 본문에서 전문검색해 후보 상장사를 찾는다. ADR-0013.

    python -m wsj.ecosystems.discover [--months 15] [--max-float 5e9] [--out research/ecosystems/discovery.json]

- 질의: 노드별 영어 별칭(구문 검색). 일반어(laser, power 등)는 제외하고 특정성이 있는 구문만 쓴다.
- 특정성: 질의 전체 hit 수가 적을수록 한 회사가 그 주제를 '사업으로' 쓴다는 신호가 강하다. 점수 = Σ 1/log2(2+hits_q) (매칭 노드마다).
- 크기: core.companies.public_float (dei:EntityPublicFloat) 로 micro(<$300M) / small(<$2B) / mid(<$10B) / large.
- 결과는 '발굴 후보' 다. 10-K 에 단어가 나온다 ≠ 그 병목의 공급사. 사람이 노드와 연결해 offered_by(technical_inference) 로 승격한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from wsj.config import load_settings
from wsj.db import make_store
from wsj.ecosystems.ontology import GRAPH_PATH, load_graph
from wsj.http import HttpClient

log = logging.getLogger("wsj.ecosystems.discover")
EFTS = "https://efts.sec.gov/LATEST/search-index"
OUT_DEFAULT = GRAPH_PATH.parent / "discovery.json"

# 노드 → 특정성 있는 검색 구문. 범용어는 넣지 않는다 (laser, power, cooling, memory ...).
QUERIES: dict[str, list[str]] = {
    # HBM / 첨단 패키징
    "tech:hybrid_bond": ['"hybrid bonding"', '"direct bond interconnect"'],
    "tech:tcb": ['"thermocompression bonding"', '"thermo-compression bonding"'],
    "equipment:hybrid_bonder": ['"hybrid bonder"', '"die-to-wafer bonding"'],
    "process:microbump_metrology": ['"bump inspection"', '"bump metrology"', '"overlay metrology"'],
    "bottleneck:hbm_kged": ['"known good die"', '"known-good die"'],
    "component:tsv": ['"through-silicon via"', '"through silicon via"'],
    "process:tsv_plating": ['"TSV" "copper plating"', '"via fill"'],
    "material:abf": ['"build-up film"', '"ABF substrate"'],
    "component:package_substrate": ['"advanced packaging substrate"', '"IC substrate"'],
    "process:cmp": ['"chemical mechanical planarization"', '"CMP slurry"', '"CMP pad"'],
    "material:underfill": ['"underfill"', '"molding compound" "semiconductor"'],
    "bottleneck:hbm_wafer_warpage": ['"wafer warpage"'],
    "gen:hbm4": ['"HBM4"', '"high bandwidth memory"'],
    "process:wafer_level_burn_in": ['"wafer-level burn-in"', '"wafer level burn-in"'],
    # 광통신
    "tech:cpo": ['"co-packaged optics"'],
    "tech:pluggable": ['"1.6T" transceiver', '"800G" transceiver'],
    "component:eml": ['"electro-absorption modulated laser"', '"EML" "200G"'],
    "component:vcsel": ['"VCSEL"'],
    "component:pic": ['"photonic integrated circuit"', '"silicon photonics"'],
    "component:optical_dsp": ['"PAM4 DSP"', '"optical DSP"'],
    "component:fiber_ferrule": ['"fiber array"', '"MT ferrule"'],
    "component:fiber_connector": ['"expanded beam" connector', '"MPO connector"'],
    "material:inp": ['"indium phosphide"'],
    "component:aec": ['"active electrical cable"'],
    "component:modulator": ['"thin-film lithium niobate"', '"lithium niobate" modulator'],
    "process:optical_test": ['"optical transceiver" test', '"wafer-level" "photonic" test'],
    "tech:optical_interposer": ['"optical interposer"'],
    "component:optical_laser": ['"DFB laser"', '"CW laser" "silicon photonics"'],
    # 전력 / 냉각
    "gen:800vdc": ['"800 VDC"', '"800V DC"', '"800-volt"'],
    "tech:sic": ['"silicon carbide" "power"'],
    "material:sic_wafer": ['"silicon carbide" wafer', '"SiC substrate"'],
    "component:sic_mosfet": ['"SiC MOSFET"'],
    "component:gate_driver": ['"gate driver"'],
    "component:dc_busbar": ['"busbar"'],
    "component:dc_breaker": ['"solid-state circuit breaker"', '"DC circuit breaker"'],
    "component:dc_contactor": ['"DC contactor"'],
    "component:power_converter": ['"DC-DC converter" "data center"', '"power module" "data center"'],
    "component:planar_transformer": ['"planar transformer"', '"solid-state transformer"'],
    "component:dc_capacitor": ['"DC link capacitor"', '"film capacitor"'],
    "material:hv_insulation": ['"high-voltage" insulation "cable"'],
    "bottleneck:liquidcool": ['"direct liquid cooling"', '"direct-to-chip"'],
    "component:coldplate": ['"cold plate"'],
    "tech:cdu": ['"coolant distribution unit"'],
    "process:cdu_pump": ['"coolant" pump "data center"'],
    "tech:sidecar": ['"power sidecar"', '"sidecar" "800"'],
    "bottleneck:sic_reliability": ['"burn-in" "silicon carbide"'],
}
FORMS = "10-K,20-F,40-F"


def efts(
    http: HttpClient, q: str, start: date, end: date, max_pages: int = 3
) -> tuple[int, list[dict[str, Any]]]:
    hits: list[dict[str, Any]] = []
    total = 0
    for page in range(1, max_pages + 1):
        params = {
            "q": q,
            "forms": FORMS,
            "dateRange": "custom",
            "startdt": start.isoformat(),
            "enddt": end.isoformat(),
            "from": (page - 1) * 100,
            "page": page,
        }
        data = http.get_json(EFTS, params=params)
        total = int((data.get("hits", {}).get("total") or {}).get("value") or 0)
        batch = data.get("hits", {}).get("hits", [])
        hits += [h["_source"] for h in batch]
        if len(batch) < 100:
            break
    return total, hits


def size_band(pf: float | None) -> str:
    if pf is None:
        return "unknown"
    if pf < 300e6:
        return "micro"
    if pf < 2e9:
        return "small"
    if pf < 10e9:
        return "mid"
    return "large"


def run(
    store, http: HttpClient, graph: dict[str, Any], months: int, max_float: float | None
) -> dict[str, Any]:
    end = date.today()
    start = end - timedelta(days=30 * months)
    nodes = {n["id"]: n for n in graph["nodes"]}
    known = {
        int(n["listing"]["cik"])
        for n in graph["nodes"]
        if n["kind"] == "company" and (n.get("listing") or {}).get("cik")
    }
    per_company: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"nodes": {}, "score": 0.0, "filings": set()}
    )
    query_log: list[dict[str, Any]] = []
    for node_id, queries in QUERIES.items():
        if node_id not in nodes:
            log.warning("query node not in graph: %s", node_id)
            continue
        for q in queries:
            try:
                total, hits = efts(http, q, start, end)
            except Exception as exc:  # noqa: BLE001
                log.warning("efts failed %r: %s", q, exc)
                query_log.append({"node": node_id, "q": q, "error": str(exc)[:120]})
                continue
            specificity = 1.0 / math.log2(2 + total)
            seen_ciks: set[int] = set()
            for h in hits:
                for cik_s, name in zip(h.get("ciks", []), h.get("display_names", []), strict=False):
                    cik = int(cik_s)
                    if cik in seen_ciks:
                        continue
                    seen_ciks.add(cik)
                    c = per_company[cik]
                    c["name"] = name.split("  (")[0].strip()
                    c.setdefault("sic", (h.get("sics") or [None])[0])
                    c["filings"].add((h["form"], h["file_date"], h["adsh"]))
                    entry = c["nodes"].setdefault(node_id, {"queries": [], "specificity": 0.0})
                    entry["queries"].append(q)
                    entry["specificity"] = max(entry["specificity"], specificity)
            query_log.append({"node": node_id, "q": q, "total_hits": total, "companies": len(seen_ciks)})
            log.info("%-32s %-45s hits=%4d companies=%d", node_id, q, total, len(seen_ciks))
    # 점수 = 매칭 노드별 최대 특정성 합
    for c in per_company.values():
        c["score"] = round(sum(v["specificity"] for v in c["nodes"].values()), 3)
    # 크기·섹터
    ciks = list(per_company)
    meta: dict[int, dict[str, Any]] = {}
    for i in range(0, len(ciks), 150):
        for r in store.select(
            "core.companies",
            [
                "cik",
                "ticker",
                "name",
                "public_float",
                "public_float_asof",
                "sic",
                "sic_description",
                "exchange",
                "in_universe",
            ],
            {"cik": ciks[i : i + 150]},
        ):
            meta[int(r["cik"])] = r
    rows: list[dict[str, Any]] = []
    for cik, c in per_company.items():
        m = meta.get(cik, {})
        pf = float(m["public_float"]) if m.get("public_float") is not None else None
        band = size_band(pf)
        if max_float is not None and pf is not None and pf > max_float:
            continue
        rows.append(
            {
                "cik": cik,
                "ticker": m.get("ticker"),
                "name": m.get("name") or c.get("name"),
                "sic": m.get("sic") or c.get("sic"),
                "sic_description": m.get("sic_description"),
                "exchange": m.get("exchange"),
                "public_float": pf,
                "size_band": band,
                "in_graph": cik in known,
                "in_universe": bool(m.get("in_universe")),
                "score": c["score"],
                "matched_nodes": {
                    k: v["queries"]
                    for k, v in sorted(c["nodes"].items(), key=lambda kv: -kv[1]["specificity"])
                },
                "node_count": len(c["nodes"]),
                "filings": sorted(c["filings"], key=lambda x: x[1], reverse=True)[:3],
            }
        )
    rows.sort(key=lambda r: (-r["score"], r["public_float"] or 1e12))
    by_band = defaultdict(int)
    for r in rows:
        by_band[r["size_band"]] += 1
    # 노드별: 소형사가 있는 병목 / 없는 병목
    node_view: dict[str, Any] = {}
    for node_id in QUERIES:
        hits_small = [
            r for r in rows if node_id in r["matched_nodes"] and r["size_band"] in ("micro", "small")
        ]
        hits_all = [r for r in rows if node_id in r["matched_nodes"]]
        node_view[node_id] = {
            "label": nodes.get(node_id, {}).get("label"),
            "companies_total": len(hits_all),
            "companies_small": len(hits_small),
            "small": [
                {
                    "cik": r["cik"],
                    "ticker": r["ticker"],
                    "name": r["name"],
                    "public_float": r["public_float"],
                    "score": r["score"],
                }
                for r in hits_small[:8]
            ],
        }
    return {
        "as_of": end.isoformat(),
        "window_start": start.isoformat(),
        "forms": FORMS,
        "max_float": max_float,
        "summary": {
            "queries": len(query_log),
            "companies": len(rows),
            "by_size_band": dict(by_band),
            "nodes_with_small_cap": sum(1 for v in node_view.values() if v["companies_small"]),
            "nodes_queried": len(node_view),
        },
        "caveat": "10-K/20-F 본문에 구문이 등장한 회사다. 공급 관계·매출 노출은 별도 검증. 점수는 특정성 합(희귀 구문일수록 큼).",
        "nodes": node_view,
        "companies": rows,
        "query_log": query_log,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=15)
    ap.add_argument(
        "--max-float", type=float, default=None, help="공개유동 상한 (기본 없음 — 대형사도 기록, 밴드로 구분)"
    )
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--store", choices=["postgrest", "sqlite"])
    args = ap.parse_args(argv)
    settings = load_settings()
    if args.store:
        settings.wsj_store = args.store
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    store = make_store(settings)
    http = HttpClient(user_agent=settings.sec_user_agent)
    try:
        result = run(store, http, load_graph(), args.months, args.max_float)
    finally:
        http.close()
        store.close()
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
