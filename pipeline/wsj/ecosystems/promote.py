"""발굴 결과(discovery.json) 중 사람이 고른 회사를 그래프 기업 노드로 승격한다. ADR-0013.

    python -m wsj.ecosystems.promote [--dry-run]

승격 규칙
- CURATED 에 있는 티커만. 발굴은 자동이지만 승격은 사람이 한다 (10-K 에 구문이 나온다 ≠ 공급사).
- 관계는 `<node> --offered_by--> company`, 근거 등급 technical_inference, 출처는 해당 10-K 색인 URL.
  해자 카드(moat)·원문 검토가 끝나면 등급을 official_issuer 로 올린다.
- 기업 노드에는 discovery 의 공개유동·SIC 를 붙이고 size_band 를 계산한다. 멱등.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wsj.ecosystems.discover import OUT_DEFAULT as DISCOVERY_PATH
from wsj.ecosystems.discover import size_band
from wsj.ecosystems.ontology import GRAPH_PATH, edge_confidence, load_graph, load_ontology, validate

# ticker → (생태계, 매칭 노드, 메모). 2026-10-27 발굴 실행 결과에서 사람이 판단.
CURATED: dict[str, dict[str, Any]] = {
    # HBM / 첨단 패키징
    "ADEA": {
        "eco": "hbm",
        "nodes": ["tech:hybrid_bond"],
        "note": "하이브리드 본딩(DBI) 특허 라이선스 — 장비가 아니라 IP 로 병목에 노출",
    },
    "KLIC": {
        "eco": "hbm",
        "nodes": ["tech:tcb", "tech:hybrid_bond"],
        "note": "TCB 본더 공급사, 하이브리드 본딩 장비 개발 중",
    },
    "FORM": {
        "eco": "hbm",
        "nodes": ["process:kgd_test", "component:tsv"],
        "note": "프로브 카드 — HBM 적층 전 KGD 테스트",
    },
    "COHU": {"eco": "hbm", "nodes": ["process:kgd_test"], "note": "테스트 핸들러·인터페이스"},
    "NVMI": {
        "eco": "hbm",
        "nodes": ["process:microbump_metrology", "process:cmp"],
        "note": "계측 (Camtek·Onto 경쟁)",
    },
    "VECO": {"eco": "hbm", "nodes": ["process:surface_activation"], "note": "웨트 프로세싱·레이저 어닐 장비"},
    "ICHR": {"eco": "hbm", "nodes": ["process:cmp"], "note": "유체 전달 서브시스템 (장비사 공급망)"},
    # 광통신
    "LWLG": {
        "eco": "optics",
        "nodes": ["component:modulator"],
        "note": "전기광학 폴리머 변조기 — 200G+/lane 후보, 매출 전 단계",
    },
    "ALMU": {
        "eco": "optics",
        "nodes": ["material:inp", "component:optical_laser"],
        "note": "InP-on-Si 광소자 플랫폼, 마이크로캡",
    },
    "AXTI": {"eco": "optics", "nodes": ["material:inp"], "note": "InP·GaAs 기판 — 레이저 소재 공급"},
    "MXL": {"eco": "optics", "nodes": ["component:optical_dsp"], "note": "PAM4 광 DSP (Keystone)"},
    "AAOI": {"eco": "optics", "nodes": ["tech:pluggable"], "note": "800G/1.6T 트랜시버 조립"},
    "BELFA": {
        "eco": "optics",
        "nodes": ["component:fiber_connector"],
        "note": "커넥터·전원 — 광 커넥터 일부",
    },
    # 전력 / 냉각
    "AOSL": {
        "eco": "power",
        "nodes": ["component:gate_driver", "component:sic_mosfet"],
        "note": "전력 디스크리트·모듈, 800V 언급",
    },
    "IPWR": {
        "eco": "power",
        "nodes": ["component:dc_breaker", "component:power_converter"],
        "note": "B-TRAN 양방향 스위치 — 고체 차단기 후보",
    },
    "ASYS": {
        "eco": "power",
        "nodes": ["material:sic_wafer", "process:cmp"],
        "note": "SiC 웨이퍼 가공·CMP 소모품",
    },
    "WOLF": {
        "eco": "power",
        "nodes": ["material:sic_wafer", "component:sic_mosfet"],
        "note": "SiC 웨이퍼·소자 (구조조정 후 소형)",
    },
    "CVV": {"eco": "power", "nodes": ["material:sic_wafer"], "note": "SiC CVD 장비, 마이크로캡"},
    "INTT": {"eco": "power", "nodes": ["process:wafer_level_burn_in"], "note": "열 시험·테스트 장비"},
}


NEW_PROCESS_NODES = [
    {
        "id": "process:kgd_test",
        "kind": "process",
        "label": "적층 전 KGD 웨이퍼 테스트 (프로브·핸들러)",
        "ecosystem": "hbm",
        "measured_metrics": ["test_time_s", "contact_yield_percent"],
        "mitigates": "bottleneck:hbm_kged",
        "evidence_url": "https://www.storagenewsletter.com/2025/04/17/jedec-and-industry-leaders-collaborate-to-release-jesd270-4-hbm4-standard/",
    },
]


def promote(graph: dict[str, Any], discovery: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    by_ticker = {r["ticker"]: r for r in discovery["companies"] if r.get("ticker")}
    nodes = {n["id"]: n for n in graph["nodes"]}
    for spec in NEW_PROCESS_NODES:
        if spec["id"] not in nodes:
            node = {k: v for k, v in spec.items() if k not in ("mitigates", "evidence_url")}
            graph["nodes"].append(node)
            nodes[spec["id"]] = node
            graph["edges"].append(
                {
                    "id": f"p_{spec['id'].split(':')[1]}",
                    "from": spec["mitigates"],
                    "to": spec["id"],
                    "relation": "mitigated_by",
                    "evidence_tier": "technical_inference",
                    "polarity": "positive",
                    "evidence": [{"url": spec["evidence_url"], "source_type": "standard_body_via_press"}],
                    "note": "16-high 적층은 KGD 테스트 비용을 키운다",
                }
            )
    edge_keys = {(e["from"], e["to"], e["relation"]) for e in graph["edges"]}
    added: list[str] = []
    seq = 1 + max(
        (int(e["id"][1:]) for e in graph["edges"] if e["id"].startswith("d") and e["id"][1:].isdigit()),
        default=0,
    )
    for ticker, spec in CURATED.items():
        r = by_ticker.get(ticker)
        if not r:
            continue
        cid = f"company:{ticker.lower()}"
        pf = r.get("public_float")
        if cid not in nodes:
            nodes[cid] = {
                "id": cid,
                "kind": "company",
                "label": f"{r['name'].title()} ({ticker})",
                "ecosystem": spec["eco"],
                "role": "supplier",
                "listing": {
                    "ticker": ticker,
                    "exchange": r.get("exchange"),
                    "cik": r["cik"],
                    "filer_type": "10-K",
                },
                "in_universe": True,
                "size_band": size_band(pf),
                "public_float": pf,
                "sic": r.get("sic"),
                "discovery": {"as_of": discovery["as_of"], "score": r["score"], "note": spec["note"]},
            }
            graph["nodes"].append(nodes[cid])
            added.append(cid)
        else:
            nodes[cid].update({"in_universe": True, "size_band": size_band(pf), "public_float": pf})
        form, fdate, adsh = r["filings"][0]
        url = f"https://www.sec.gov/Archives/edgar/data/{r['cik']}/{adsh.replace('-', '')}/{adsh}-index.htm"
        for node_id in spec["nodes"]:
            if node_id not in nodes:
                raise KeyError(f"{ticker}: node {node_id} not in graph")
            key = (node_id, cid, "offered_by")
            if key in edge_keys:
                continue
            graph["edges"].append(
                {
                    "id": f"d{seq:03d}",
                    "from": node_id,
                    "to": cid,
                    "relation": "offered_by",
                    "evidence_tier": "technical_inference",
                    "polarity": "positive",
                    "evidence": [
                        {
                            "url": url,
                            "source_type": "official_issuer_filing_mention",
                            "published_at": fdate,
                            "date_precision": "day",
                            "note": f"{form} 본문에 노드 구문 등장 (발굴 {discovery['as_of']}). 공급 여부는 해자 카드에서 검증",
                        }
                    ],
                    "note": spec["note"],
                }
            )
            edge_keys.add(key)
            seq += 1
    # 기존 그래프의 소형 SEC 필러(AEHR·NVTS·POET·CAMT 등)도 유니버스에 넣는다
    for n in graph["nodes"]:
        if (
            n["kind"] == "company"
            and n.get("size_band") in ("micro", "small")
            and (n.get("listing") or {}).get("cik")
        ):
            n["in_universe"] = True
    return graph, added


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discovery", type=Path, default=DISCOVERY_PATH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    graph = load_graph()
    discovery = json.loads(args.discovery.read_text(encoding="utf-8"))
    graph, added = promote(graph, discovery)
    onto = load_ontology()
    for e in graph["edges"]:
        e["confidence"] = edge_confidence(e, onto)
    rep = validate(graph, onto)
    for err in rep.errors:
        print("ERROR", err)
    print(f"added companies: {added}")
    print(
        f"companies in graph: {rep.stats['node_kinds'].get('company')} · edges: {rep.stats['edges']} · warnings {len(rep.warnings)}"
    )
    if rep.errors:
        return 1
    if not args.dry_run:
        GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
