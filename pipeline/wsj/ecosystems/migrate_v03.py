"""seed_graph.json v0.2 → v0.3 일회성 마이그레이션 + 2026-10-27 내용 추가. ADR-0012.

멱등: 이미 schema_version 0.3 이면 아무것도 하지 않는다.
    python -m wsj.ecosystems.migrate_v03 [--dry-run]

바뀌는 것
1. 제품(특정 회사 판매품)을 technology 에서 분리: tech:hawk → product:camt_hawk (implements process:microbump_metrology) 등 8개
2. 관계 어휘 통합: requires_component_or_material / uses_component_or_equipment → requires; stage → evidence_tier
3. 모든 노드에 ecosystem 부여, 기업 노드에 role / listing(cik) / in_universe / size_band
4. 수요 측(제품 세대·표준·고객)과 경쟁·대체·연기 관계 추가 — 각 관계에 2025~2026 출처
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any

from wsj.ecosystems.ontology import GRAPH_PATH, edge_confidence, load_ontology, validate

# ---------------------------------------------------------------------- 1. 제품 분리
# old tech id → (product id, label, implements target, [extra new generic node])
PRODUCT_SPLIT: dict[str, dict[str, Any]] = {
    "tech:hawk": {
        "product": "product:camt_hawk",
        "label": "Camtek Hawk 2D/3D 범프 검사·계측기",
        "implements": "process:microbump_metrology",
        "eco": "hbm",
    },
    "tech:onto_g3": {
        "product": "product:onto_dragonfly_g3",
        "label": "Onto Dragonfly G3 2D/3D 결함 검사기",
        "implements": "process:microbump_metrology",
        "eco": "hbm",
    },
    "tech:lite_eml": {
        "product": "product:lite_eml_200g",
        "label": "Lumentum 200G PAM4 EML",
        "implements": "component:eml",
        "eco": "optics",
    },
    "tech:cohr_1p6t": {
        "product": "product:cohr_1p6t_transceiver",
        "label": "Coherent 1.6T 광트랜시버",
        "implements": "tech:pluggable",
        "eco": "optics",
    },
    "tech:vertiv_800v": {
        "product": "product:vrt_800vdc_portfolio",
        "label": "Vertiv 800VDC 전력·냉각 인프라 제품군",
        "implements": "tech:sidecar",
        "eco": "power",
    },
    "tech:aehr_fox": {
        "product": "product:aehr_fox_xp",
        "label": "Aehr FOX-XP 웨이퍼 레벨 번인 시스템",
        "implements": "process:wafer_level_burn_in",
        "eco": "power",
        "new_generic": {
            "id": "process:wafer_level_burn_in",
            "kind": "process",
            "label": "SiC 웨이퍼 레벨 번인·신뢰성 검사",
            "measured_metrics": ["burn_in_hours", "early_failure_rate_ppm"],
        },
    },
    "tech:poet_interposer": {
        "product": "product:poet_optical_interposer",
        "label": "POET 광학 인터포저 광엔진",
        "implements": "tech:optical_interposer",
        "eco": "optics",
        "rename_generic": ("tech:optical_interposer", "광학 인터포저 기반 통합 광엔진"),
    },
    "tech:lessengers_dow": {
        "product": "product:lessengers_dow",
        "label": "Lessengers DOW 광배선 모듈",
        "implements": "tech:dow",
        "eco": "optics",
        "rename_generic": ("tech:dow", "Direct Optical Wiring (광섬유 직접 배선)"),
    },
}
RELATION_MAP = {"requires_component_or_material": "requires", "uses_component_or_equipment": "requires"}

COMPANY_META: dict[str, dict[str, Any]] = {
    "company:camt": {
        "role": "supplier",
        "ecosystem": "hbm",
        "listing": {"ticker": "CAMT", "exchange": "Nasdaq", "cik": 1109138, "filer_type": "20-F"},
        "size_band": "mid",
    },
    "company:onto": {
        "role": "supplier",
        "ecosystem": "hbm",
        "listing": {"ticker": "ONTO", "exchange": "NYSE", "cik": 704532, "filer_type": "10-K"},
        "size_band": "mid",
    },
    "company:poet": {
        "role": "supplier",
        "ecosystem": "optics",
        "listing": {"ticker": "POET", "exchange": "Nasdaq", "cik": 1437424, "filer_type": "40-F"},
        "size_band": "small",
    },
    "company:lessengers": {
        "role": "supplier",
        "ecosystem": "optics",
        "listing": {"ticker": None, "exchange": None, "cik": None, "filer_type": "private"},
        "size_band": "private",
    },
    "company:lite": {
        "role": "supplier",
        "ecosystem": "optics",
        "listing": {"ticker": "LITE", "exchange": "Nasdaq", "cik": 1633978, "filer_type": "10-K"},
        "size_band": "large",
    },
    "company:cohr": {
        "role": "supplier",
        "ecosystem": "optics",
        "listing": {"ticker": "COHR", "exchange": "NYSE", "cik": 820318, "filer_type": "10-K"},
        "size_band": "large",
    },
    "company:vrt": {
        "role": "supplier",
        "ecosystem": "power",
        "listing": {"ticker": "VRT", "exchange": "NYSE", "cik": 1674101, "filer_type": "10-K"},
        "size_band": "large",
    },
    "company:aehr": {
        "role": "supplier",
        "ecosystem": "power",
        "listing": {"ticker": "AEHR", "exchange": "Nasdaq", "cik": 1040470, "filer_type": "10-K"},
        "size_band": "small",
    },
}

# ---------------------------------------------------------------------- 4. 추가 내용 (출처 포함)
SRC = {
    "jedec_hbm4": {
        "url": "https://www.storagenewsletter.com/2025/04/17/jedec-and-industry-leaders-collaborate-to-release-jesd270-4-hbm4-standard/",
        "source_type": "standard_body_via_press",
        "published_at": "2025-04-17",
        "date_precision": "day",
        "note": "JEDEC JESD270-4 발행 보도자료 전재. 원문 jedec.org 는 등록 필요",
    },
    "skh_hbm4_mp": {
        "url": "https://www.koreatimes.co.kr/amp/business/tech-science/20250912/sk-hynix-completes-hbm4-development-mass-production-ready",
        "source_type": "third_party_report",
        "published_at": "2025-09-12",
        "date_precision": "day",
        "note": "SK hynix 발표(2,048 I/O, 10Gbps, Advanced MR-MUF, 1b nm) 보도",
    },
    "mu_hbm4": {
        "url": "https://micron.gcs-web.com/node/48886",
        "source_type": "official_issuer",
        "published_at": "2025-06-10",
        "date_precision": "day",
        "note": "Micron HBM4 36GB 12-high 샘플 출하, 2026 램프",
    },
    "hotchips_hb": {
        "url": "https://bits-chips.com/article/besi-faces-longer-wait-as-sk-hynix-pushes-hybrid-bonding-to-hbm5/",
        "source_type": "third_party_report",
        "published_at": "2026-08-26",
        "date_precision": "day",
        "note": "Hot Chips 2026 SK hynix VP 발언 보도: HBM4·HBM4E 는 microbump 유지, 하이브리드 본딩은 HBM5. JEDEC 적층 높이 720→775µm",
    },
    "amat_besi": {
        "url": "https://www.sec.gov/Archives/edgar/data/6951/000119312525080269/d939298dex991.htm",
        "source_type": "official_issuer",
        "published_at": "2025-04-14",
        "date_precision": "day",
        "note": "Applied Materials 8-K EX-99.1: BESI 지분 9% 취득, Cu-Cu 하이브리드 본딩 장비 공동개발",
    },
    "nv_cpo": {
        "url": "https://investor.nvidia.com/news/press-release-details/2025/NVIDIA-Announces-Spectrum-X-Photonics-Co-Packaged-Optics-Networking-Switches-to-Scale-AI-Factories-to-Millions-of-GPUs/default.aspx",
        "source_type": "official_issuer",
        "published_at": "2025-03-18",
        "date_precision": "day",
        "note": "NVIDIA CPO 스위치 발표. 파트너 TSMC·Coherent·Lumentum·Fabrinet·Corning 등; pluggable 은 보완재로 명시",
    },
    "ieee_dj": {
        "url": "https://standards.ieee.org/ieee/802.3dj/11115/",
        "source_type": "standard_body",
        "published_at": None,
        "date_precision": "unknown",
        "note": "P802.3dj 1.6T PAR 페이지",
    },
    "credo_aec": {
        "url": "https://credosemi.com/?p=21",
        "source_type": "vendor_claim",
        "published_at": None,
        "date_precision": "unknown",
        "note": "Credo HiWire AEC 제품 페이지: 단거리에서 광모듈 대체",
    },
    "nv_800v": {
        "url": "https://developer.nvidia.com/blog/nvidia-800-v-hvdc-architecture-will-power-the-next-Generation-of-ai-factories",
        "source_type": "customer_statement",
        "published_at": "2025-05-20",
        "date_precision": "day",
        "note": "NVIDIA 800VDC 아키텍처·1MW 랙(2027)·구리 45% 절감. 파트너: ADI, Infineon, Innoscience, MPS, Navitas, onsemi, Renesas, ROHM, ST, TI / Delta, Flex, Lead Wealth, LiteOn, Megmeet / Eaton, Schneider, Vertiv",
    },
    "nvts_800v": {
        "url": "https://ir.navitassemi.com/news-releases/news-release-details/nvidia-selects-navitas-collaborate-next-generation-800-v-hvdc",
        "source_type": "official_issuer",
        "published_at": "2025-05-21",
        "date_precision": "day",
        "note": "Navitas: GaN·SiC 가 NVIDIA 800V HVDC 지원에 선정 — 협업 단계, 수주·매출 언급 없음",
    },
    "ocp_lvdc": {
        "url": "https://www.opencompute.org/projects/data-center-facility/power-distribution/",
        "source_type": "standard_body",
        "published_at": "2026-09",
        "date_precision": "month",
        "note": "OCP LVDC White Paper v1.1.0",
    },
}


def _ev(key: str) -> dict[str, Any]:
    return dict(SRC[key])


def _company(
    id_: str,
    label: str,
    eco: str,
    role: str,
    ticker: str | None,
    exchange: str | None,
    cik: int | None,
    filer: str,
    band: str,
) -> dict[str, Any]:
    return {
        "id": id_,
        "kind": "company",
        "label": label,
        "ecosystem": eco,
        "role": role,
        "listing": {"ticker": ticker, "exchange": exchange, "cik": cik, "filer_type": filer},
        "in_universe": False,
        "size_band": band,
    }


NEW_NODES: list[dict[str, Any]] = [
    # --- 세대·표준 (HBM)
    {"id": "gen:hbm3e", "kind": "product_generation", "label": "HBM3E (1,024 I/O)", "ecosystem": "hbm"},
    {
        "id": "gen:hbm4",
        "kind": "product_generation",
        "label": "HBM4 (2,048 I/O, JESD270-4)",
        "ecosystem": "hbm",
        "measured_metrics": ["io_count", "gbps_per_pin", "stack_height_um"],
    },
    {
        "id": "gen:hbm4e",
        "kind": "product_generation",
        "label": "HBM4E (microbump 유지 전망)",
        "ecosystem": "hbm",
    },
    {
        "id": "gen:hbm5",
        "kind": "product_generation",
        "label": "HBM5 (하이브리드 본딩 후보 세대)",
        "ecosystem": "hbm",
    },
    {
        "id": "std:jesd270_4",
        "kind": "standard",
        "label": "JEDEC JESD270-4 HBM4 (2025-04)",
        "ecosystem": "hbm",
        "measured_metrics": ["gbps_per_pin", "io_count", "stack_height_um"],
    },
    {
        "id": "equipment:hybrid_bonder",
        "kind": "equipment",
        "label": "웨이퍼·다이 하이브리드 본더",
        "ecosystem": "hbm",
        "measured_metrics": ["overlay_nm", "uph"],
    },
    _company(
        "company:skhynix",
        "SK hynix (KRX 000660, 비SEC)",
        "hbm",
        "both",
        "000660",
        "KRX",
        None,
        "non_sec_listed",
        "mega",
    ),
    _company(
        "company:samsung",
        "Samsung Electronics (KRX 005930, 비SEC)",
        "hbm",
        "both",
        "005930",
        "KRX",
        None,
        "non_sec_listed",
        "mega",
    ),
    _company("company:mu", "Micron (MU)", "hbm", "both", "MU", "Nasdaq", 723125, "10-K", "mega"),
    {
        **_company(
            "company:nvda",
            "NVIDIA (NVDA) — HBM·광·전력 공통 수요처",
            "hbm",
            "customer",
            "NVDA",
            "Nasdaq",
            1045810,
            "10-K",
            "mega",
        ),
        "also_in": ["optics", "power"],
    },
    _company(
        "company:besi",
        "BE Semiconductor Industries (Euronext BESI, 비SEC)",
        "hbm",
        "supplier",
        "BESI",
        "Euronext",
        None,
        "non_sec_listed",
        "large",
    ),
    _company(
        "company:amat", "Applied Materials (AMAT)", "hbm", "supplier", "AMAT", "Nasdaq", 6951, "10-K", "mega"
    ),
    _company("company:klac", "KLA (KLAC)", "hbm", "supplier", "KLAC", "Nasdaq", 319201, "10-K", "mega"),
    # --- 세대·표준 (optics)
    {
        "id": "gen:800g",
        "kind": "product_generation",
        "label": "800G 광모듈 세대 (100G/lane)",
        "ecosystem": "optics",
    },
    {
        "id": "gen:1p6t",
        "kind": "product_generation",
        "label": "1.6T 광모듈 세대 (200G/lane)",
        "ecosystem": "optics",
    },
    {
        "id": "std:ieee_802_3dj",
        "kind": "standard",
        "label": "IEEE P802.3dj 1.6T (Draft, 2026-10 기준)",
        "ecosystem": "optics",
        "measured_metrics": ["lane_rate_gbps", "reach_m"],
    },
    {
        "id": "product:credo_aec",
        "kind": "product",
        "label": "Credo HiWire 능동 전기 케이블(AEC)",
        "ecosystem": "optics",
    },
    {
        "id": "component:aec",
        "kind": "component",
        "label": "능동 전기 케이블(AEC) — 단거리 구리 링크",
        "ecosystem": "optics",
        "measured_metrics": ["reach_m", "power_w_per_port"],
    },
    _company(
        "company:crdo", "Credo (CRDO)", "optics", "supplier", "CRDO", "Nasdaq", 1807794, "10-K", "large"
    ),
    _company("company:fn", "Fabrinet (FN)", "optics", "supplier", "FN", "NYSE", 1408710, "10-K", "large"),
    # --- 세대·표준 (power)
    {
        "id": "gen:54vdc",
        "kind": "product_generation",
        "label": "54VDC 랙 내 배전 (현행)",
        "ecosystem": "power",
    },
    {
        "id": "gen:800vdc",
        "kind": "product_generation",
        "label": "800VDC 배전 아키텍처 (NVIDIA 2027 1MW 랙 목표)",
        "ecosystem": "power",
        "measured_metrics": ["dc_bus_voltage_v", "rack_power_kw"],
    },
    {
        "id": "std:ocp_lvdc",
        "kind": "standard",
        "label": "OCP LVDC/800VDC White Paper v1.1 (2026-09)",
        "ecosystem": "power",
    },
    _company(
        "company:nvts",
        "Navitas Semiconductor (NVTS)",
        "power",
        "supplier",
        "NVTS",
        "Nasdaq",
        1821769,
        "10-K",
        "small",
    ),
    _company("company:on", "onsemi (ON)", "power", "supplier", "ON", "Nasdaq", 1097864, "10-K", "large"),
    _company(
        "company:mpwr",
        "Monolithic Power Systems (MPWR)",
        "power",
        "supplier",
        "MPWR",
        "Nasdaq",
        1280452,
        "10-K",
        "large",
    ),
    _company(
        "company:txn", "Texas Instruments (TXN)", "power", "supplier", "TXN", "Nasdaq", 97476, "10-K", "mega"
    ),
    _company("company:etn", "Eaton (ETN)", "power", "supplier", "ETN", "NYSE", 1551182, "10-K", "mega"),
]


ABOUT = {
    "n013": "gen:hbm4",
    "n014": "gen:hbm4",
    "n015": "gen:hbm4",
    "n035": "tech:cpo",
    "n036": "tech:cpo",
    "n037": "tech:cpo",
    "n054": "gen:800vdc",
    "n055": "gen:800vdc",
    "n056": "gen:800vdc",
    "n057": "gen:800vdc",
    "n058": "gen:800vdc",
    "n059": "gen:800vdc",
}  # 기업↔기업 관계가 어느 기술/세대에 관한 것인지 (전파 범위 제한)


def _e(
    id_: str, f: str, t: str, rel: str, tier: str, src: str, polarity: str = "positive", note: str = ""
) -> dict[str, Any]:
    e = {
        "id": id_,
        "from": f,
        "to": t,
        "relation": rel,
        "evidence_tier": tier,
        "polarity": polarity,
        "evidence": [_ev(src)],
        "note": note,
    }
    if id_ in ABOUT:
        e["about"] = ABOUT[id_]
    return e


NEW_EDGES: list[dict[str, Any]] = [
    # HBM 세대·표준·요구
    _e("n001", "gen:hbm3e", "gen:hbm4", "succeeds", "standard_body", "jedec_hbm4"),
    _e("n002", "gen:hbm4", "gen:hbm4e", "succeeds", "third_party_report", "hotchips_hb"),
    _e("n003", "gen:hbm4e", "gen:hbm5", "succeeds", "third_party_report", "hotchips_hb"),
    _e(
        "n004",
        "gen:hbm4",
        "std:jesd270_4",
        "specified_by",
        "standard_body",
        "jedec_hbm4",
        note="8Gb/s/pin, 2048-bit, 32채널, 4~16-high, 최대 64GB",
    ),
    _e("n005", "std:jesd270_4", "req:hbm_io", "drives_requirement", "standard_body", "jedec_hbm4"),
    _e(
        "n006",
        "gen:hbm4",
        "req:hbm_stack",
        "drives_requirement",
        "standard_body",
        "jedec_hbm4",
        note="16-high 까지 규격화",
    ),
    # 공급사·고객
    _e(
        "n010",
        "gen:hbm4",
        "company:skhynix",
        "offered_by",
        "third_party_report",
        "skh_hbm4_mp",
        note="2025-09 양산 준비 완료 발표",
    ),
    _e(
        "n011",
        "gen:hbm4",
        "company:mu",
        "offered_by",
        "official_issuer",
        "mu_hbm4",
        note="36GB 12-high 샘플 출하, 2026 램프",
    ),
    _e(
        "n012",
        "gen:hbm4",
        "company:samsung",
        "offered_by",
        "third_party_report",
        "skh_hbm4_mp",
        note="3사 모두 NVIDIA 인증 진행 보도",
    ),
    _e(
        "n013",
        "company:skhynix",
        "company:nvda",
        "qualifying_with",
        "third_party_report",
        "skh_hbm4_mp",
        note="Rubin 용 HBM4 인증 진행 (보도)",
    ),
    _e("n014", "company:mu", "company:nvda", "qualifying_with", "third_party_report", "skh_hbm4_mp"),
    _e("n015", "company:samsung", "company:nvda", "qualifying_with", "third_party_report", "skh_hbm4_mp"),
    # 채택·연기 — 하이브리드 본딩 타임라인 (핵심 부정 근거)
    _e(
        "n020",
        "company:skhynix",
        "tech:tcb",
        "adopts",
        "third_party_report",
        "skh_hbm4_mp",
        note="HBM4 는 Advanced MR-MUF + 기존 접합 유지",
    ),
    _e(
        "n021",
        "company:skhynix",
        "tech:hybrid_bond",
        "defers",
        "third_party_report",
        "hotchips_hb",
        polarity="negative",
        note="HBM4·HBM4E 는 microbump, 하이브리드 본딩은 HBM5 (Hot Chips 2026)",
    ),
    _e(
        "n022",
        "gen:hbm5",
        "tech:hybrid_bond",
        "adopts",
        "hypothesis",
        "hotchips_hb",
        polarity="conditional",
        note="세대 미도래. 16~20단 Cu-Cu 수율이 선결",
    ),
    _e(
        "n023",
        "tech:hybrid_bond",
        "component:microbump",
        "displaces",
        "technical_inference",
        "hotchips_hb",
        polarity="negative",
        note="채택 시 범프 검사 수요 구조 변화 — 시점은 HBM5 이후",
    ),
    _e("n024", "equipment:hybrid_bonder", "company:besi", "offered_by", "official_issuer", "amat_besi"),
    _e(
        "n025",
        "company:amat",
        "company:besi",
        "invests_in",
        "official_issuer",
        "amat_besi",
        note="9% 지분, 2020~ 공동개발",
    ),
    _e(
        "n026",
        "bottleneck:bond_void",
        "equipment:hybrid_bonder",
        "mitigated_by",
        "technical_inference",
        "amat_besi",
    ),
    _e(
        "n026b",
        "tech:hybrid_bond",
        "equipment:hybrid_bonder",
        "requires",
        "official_issuer",
        "amat_besi",
        note="Cu-Cu 접합 장비 (AMAT·BESI 공동개발)",
    ),
    _e(
        "n028",
        "company:camt",
        "company:onto",
        "competes_with",
        "technical_inference",
        "jedec_hbm4",
        note="2D/3D 범프 검사 동일 공정",
    ),
    _e("n029", "company:camt", "company:klac", "competes_with", "technical_inference", "jedec_hbm4"),
    # optics
    _e("n030", "gen:800g", "gen:1p6t", "succeeds", "standard_body", "ieee_dj"),
    _e("n031", "gen:1p6t", "std:ieee_802_3dj", "specified_by", "standard_body", "ieee_dj"),
    _e("n032", "gen:1p6t", "req:1p6t", "drives_requirement", "standard_body", "ieee_dj"),
    _e(
        "n033",
        "company:nvda",
        "tech:cpo",
        "adopts",
        "official_issuer",
        "nv_cpo",
        note="Quantum-X 2025, Spectrum-X 2026 출하 계획 — 당사 발표",
    ),
    _e(
        "n034",
        "tech:cpo",
        "tech:pluggable",
        "displaces",
        "vendor_claim",
        "nv_cpo",
        polarity="conditional",
        note="NVIDIA 는 pluggable 을 보완재로 명시. 스케일아웃 일부 대체 가능성",
    ),
    _e(
        "n035",
        "company:cohr",
        "company:nvda",
        "qualifying_with",
        "customer_statement",
        "nv_cpo",
        note="CPO 생태계 파트너 명단",
    ),
    _e("n036", "company:lite", "company:nvda", "qualifying_with", "customer_statement", "nv_cpo"),
    _e("n037", "company:fn", "company:nvda", "qualifying_with", "customer_statement", "nv_cpo"),
    _e("n038", "product:credo_aec", "component:aec", "implements", "vendor_claim", "credo_aec"),
    _e("n039", "product:credo_aec", "company:crdo", "offered_by", "vendor_claim", "credo_aec"),
    _e(
        "n040",
        "component:aec",
        "tech:pluggable",
        "substitutes_for",
        "vendor_claim",
        "credo_aec",
        polarity="conditional",
        note="단거리(랙 내·인접 랙)에서만",
    ),
    _e("n041", "company:cohr", "company:lite", "competes_with", "technical_inference", "nv_cpo"),
    # power
    _e("n050", "gen:54vdc", "gen:800vdc", "succeeds", "customer_statement", "nv_800v"),
    _e("n051", "gen:800vdc", "std:ocp_lvdc", "specified_by", "standard_body", "ocp_lvdc"),
    _e(
        "n052",
        "gen:800vdc",
        "req:800v",
        "drives_requirement",
        "customer_statement",
        "nv_800v",
        note="1MW 랙 2027, 구리 최대 45% 절감 (NVIDIA 주장)",
    ),
    _e("n053", "company:nvda", "gen:800vdc", "adopts", "customer_statement", "nv_800v"),
    _e(
        "n054",
        "company:nvts",
        "company:nvda",
        "qualifying_with",
        "official_issuer",
        "nvts_800v",
        note="협업 선정. 수주·매출 아님",
    ),
    _e("n055", "company:on", "company:nvda", "qualifying_with", "customer_statement", "nv_800v"),
    _e("n056", "company:mpwr", "company:nvda", "qualifying_with", "customer_statement", "nv_800v"),
    _e("n057", "company:txn", "company:nvda", "qualifying_with", "customer_statement", "nv_800v"),
    _e("n058", "company:etn", "company:nvda", "qualifying_with", "customer_statement", "nv_800v"),
    _e("n059", "company:vrt", "company:nvda", "qualifying_with", "customer_statement", "nv_800v"),
    _e(
        "n060",
        "tech:sic",
        "company:nvts",
        "offered_by",
        "official_issuer",
        "nvts_800v",
        note="GeneSiC 650V~6.5kV",
    ),
    _e("n061", "tech:sic", "company:on", "offered_by", "customer_statement", "nv_800v"),
    _e(
        "n062",
        "gen:800vdc",
        "component:dc_busbar",
        "displaces",
        "technical_inference",
        "nv_800v",
        polarity="negative",
        note="구리 사용량 감소 — 부스바 물량 역효과 가능",
    ),
    _e("n063", "company:nvts", "company:on", "competes_with", "technical_inference", "nv_800v"),
]

NEW_EVENTS: list[dict[str, Any]] = [
    {
        "id": "obs:jedec_hbm4_202504",
        "ecosystem": "eco:hbm",
        "target_id": "std:jesd270_4",
        "type": "standard_published",
        "source_id": "jedec",
        "published_at": "2025-04-17",
        "date_precision": "day",
        "source_url": SRC["jedec_hbm4"]["url"],
        "summary": "JEDEC JESD270-4 HBM4 발행: 8Gb/s/pin, 2048-bit, 16-high",
        "data": {"gbps_per_pin": 8, "io_count": 2048},
        "evidence_level": "standard_body",
        "interpretation": "요구사항 확정 — 공급사 채택 시점은 별도",
    },
    {
        "id": "obs:mu_hbm4_202506",
        "ecosystem": "eco:hbm",
        "target_id": "gen:hbm4",
        "type": "sample_shipment",
        "source_id": "issuer_micron",
        "published_at": "2025-06-10",
        "date_precision": "day",
        "source_url": SRC["mu_hbm4"]["url"],
        "summary": "Micron HBM4 36GB 12-high 샘플 출하, 2026 램프 계획",
        "data": {"capacity_gb": 36, "stack": 12},
        "evidence_level": "issuer_claim",
        "interpretation": "경쟁 3사 체제 유지",
    },
    {
        "id": "obs:skh_hbm4_202509",
        "ecosystem": "eco:hbm",
        "target_id": "gen:hbm4",
        "type": "mass_production_ready",
        "source_id": "issuer_skhynix_via_press",
        "published_at": "2025-09-12",
        "date_precision": "day",
        "source_url": SRC["skh_hbm4_mp"]["url"],
        "summary": "SK hynix HBM4 개발 완료·양산 체제, Advanced MR-MUF 유지",
        "data": {"io_count": 2048, "gbps_per_pin": 10},
        "evidence_level": "third_party_report",
        "interpretation": "하이브리드 본딩 없이 HBM4 — 기존 접합·검사 공급사 수요 지속",
    },
    {
        "id": "obs:hotchips_hb_202608",
        "ecosystem": "eco:hbm",
        "target_id": "tech:hybrid_bond",
        "type": "adoption_deferred",
        "source_id": "press_bits_chips",
        "published_at": "2026-08-26",
        "date_precision": "day",
        "source_url": SRC["hotchips_hb"]["url"],
        "summary": "SK hynix: HBM4E 까지 microbump, 하이브리드 본딩은 HBM5 (Hot Chips 2026)",
        "data": {"hybrid_bond_generation": "HBM5", "jedec_stack_height_um": 775},
        "evidence_level": "third_party_report",
        "interpretation": "하이브리드 본딩 장비(BESI·AMAT) 논제 약화, 범프 검사(CAMT·ONTO) 수명 연장",
    },
    {
        "id": "obs:nv_cpo_202503",
        "ecosystem": "eco:optics",
        "target_id": "tech:cpo",
        "type": "customer_adoption",
        "source_id": "issuer_nvidia",
        "published_at": "2025-03-18",
        "date_precision": "day",
        "source_url": SRC["nv_cpo"]["url"],
        "summary": "NVIDIA CPO 스위치 발표 (Quantum-X 2025, Spectrum-X 2026)",
        "data": {"power_efficiency_x": 3.5, "lasers_fewer_x": 4},
        "evidence_level": "issuer_claim",
        "interpretation": "pluggable 과 공존 선언 — 대체 비중은 미확정",
    },
    {
        "id": "obs:nv_800v_202505",
        "ecosystem": "eco:power",
        "target_id": "gen:800vdc",
        "type": "architecture_announcement",
        "source_id": "issuer_nvidia",
        "published_at": "2025-05-20",
        "date_precision": "day",
        "source_url": SRC["nv_800v"]["url"],
        "summary": "NVIDIA 800VDC 아키텍처·파트너 18사 공개, 1MW 랙 2027",
        "data": {"rack_power_kw": 1000, "copper_reduction_pct": 45},
        "evidence_level": "customer_statement",
        "interpretation": "수요처가 공급사 후보군을 명시 — 수주 아님",
    },
    {
        "id": "obs:nvts_202505",
        "ecosystem": "eco:power",
        "target_id": "company:nvts",
        "type": "partner_selection",
        "source_id": "issuer_navitas",
        "published_at": "2025-05-21",
        "date_precision": "day",
        "source_url": SRC["nvts_800v"]["url"],
        "summary": "Navitas GaN·SiC, NVIDIA 800V HVDC 협업 선정",
        "data": {},
        "evidence_level": "issuer_claim",
        "interpretation": "협업 ≠ 수주",
    },
]

NEW_WATCHES: list[dict[str, Any]] = [
    {
        "id": "watch:hbm_bonding_roadmap",
        "ecosystem": "eco:hbm",
        "target_id": "tech:hybrid_bond",
        "signal": "hybrid_bonding_adoption_generation",
        "condition": "SK hynix·Samsung·Micron 이 하이브리드 본딩 적용 세대(HBM4E/HBM5)를 앞당기거나 미루는 공식 발언·공시",
        "source_urls": [SRC["hotchips_hb"]["url"], "https://news.skhynix.com/"],
        "cadence": "monthly",
        "severity": "high",
        "confirmations_needed": "제조사 공식 발언 + 장비사 수주 공시",
        "failure_mode": "학회 발언을 로드맵 확정으로 오인",
    },
    {
        "id": "watch:nvda_hbm4_qual",
        "ecosystem": "eco:hbm",
        "target_id": "company:nvda",
        "signal": "hbm4_qualification_result",
        "condition": "NVIDIA Rubin 용 HBM4 공급사 인증 결과·점유율 보도",
        "source_urls": [SRC["skh_hbm4_mp"]["url"]],
        "cadence": "monthly",
        "severity": "review",
        "confirmations_needed": "공급사 공시 또는 복수 독립 보도",
        "failure_mode": "애널리스트 추정 점유율을 사실로 기록",
    },
    {
        "id": "watch:cpo_vs_pluggable",
        "ecosystem": "eco:optics",
        "target_id": "tech:cpo",
        "signal": "cpo_port_share",
        "condition": "하이퍼스케일러 스위치 세대에서 CPO 포트 비중·pluggable 주문 변화 공개",
        "source_urls": [SRC["nv_cpo"]["url"]],
        "cadence": "monthly",
        "severity": "high",
        "confirmations_needed": "고객 아키텍처 문서 + 광모듈사 매출 구성",
        "failure_mode": "공급사 전망치를 채택률로 오인",
    },
    {
        "id": "watch:800v_orders",
        "ecosystem": "eco:power",
        "target_id": "gen:800vdc",
        "signal": "first_800vdc_site_or_order",
        "condition": "800VDC 사이트 커미셔닝·부품 공급 계약 공시 (파트너 18사 중 누가 먼저 매출로 잇는가)",
        "source_urls": [SRC["nv_800v"]["url"]],
        "cadence": "weekly",
        "severity": "high",
        "confirmations_needed": "SEC 8-K 또는 고객 공식 발표",
        "failure_mode": "파트너 명단 포함을 수주로 오인",
    },
]


def _assign_ecosystems(graph: dict[str, Any]) -> None:
    nodes = {n["id"]: n for n in graph["nodes"]}
    adj: dict[str, set[str]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["from"], set()).add(e["to"])
        adj.setdefault(e["to"], set()).add(e["from"])
    for root in ("eco:hbm", "eco:optics", "eco:power"):
        eco = root.split(":")[1]
        q = deque([root])
        seen = {root}
        while q:
            cur = q.popleft()
            for nxt in adj.get(cur, ()):
                if nxt in seen:
                    continue
                seen.add(nxt)
                if nodes[nxt]["kind"] != "ecosystem":
                    nodes[nxt].setdefault("ecosystem", eco)
                    q.append(nxt)


def migrate(graph: dict[str, Any]) -> dict[str, Any]:
    if graph.get("schema_version") == "0.3":
        return graph
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = list(graph["edges"])
    new_nodes: list[dict[str, Any]] = []

    # 1. 제품 분리
    for old, spec in PRODUCT_SPLIT.items():
        node = nodes.pop(old)
        generic_id = spec["implements"]
        if "rename_generic" in spec:
            gid, glabel = spec["rename_generic"]
            nodes[gid] = {**node, "id": gid, "label": glabel, "ecosystem": spec["eco"]}
            nodes[gid].pop("disclosure_note", None)
        if "new_generic" in spec:
            g = spec["new_generic"]
            nodes[g["id"]] = {**g, "ecosystem": spec["eco"]}
        prod = {
            "id": spec["product"],
            "kind": "product",
            "label": spec["label"],
            "ecosystem": spec["eco"],
            "measured_metrics": node.get("measured_metrics", []),
        }
        new_nodes.append(prod)
        rewritten: list[dict[str, Any]] = []
        for e in edges:
            if e["from"] == old and e["relation"] == "offered_by":
                e = {**e, "from": spec["product"]}
            elif e["to"] == old and e["relation"] == "mitigated_by":
                # 병목 → 제품 : 병목 → 제품이 구현하는 일반 노드 (중복이면 버림)
                if any(
                    x["from"] == e["from"] and x["to"] == generic_id and x["relation"] == "mitigated_by"
                    for x in edges
                ):
                    continue
                e = {**e, "to": generic_id, "note": (e.get("note") or "") + f" [v0.3: {old} → {generic_id}]"}
            elif e["from"] == old and e["relation"] in RELATION_MAP:
                e = {**e, "from": spec["product"]}  # 제품 requires 부품
            elif e["to"] == old:
                continue  # process/component uses product, process mitigated_by product 등 → implements 로 대체
            rewritten.append(e)
        edges = rewritten
        edges.append(
            {
                "id": f"p_{spec['product'].split(':')[1]}",
                "from": spec["product"],
                "to": generic_id,
                "relation": "implements",
                "evidence_tier": "official_issuer",
                "polarity": "positive",
                "evidence": [
                    {
                        "url": next(
                            ev["url"]
                            for x in graph["edges"]
                            if x["from"] == old and x["relation"] == "offered_by"
                            for ev in x["evidence"]
                        ),
                        "source_type": "official_issuer",
                    }
                ],
                "note": "제품 ↔ 일반 기술 분리 (v0.3)",
            }
        )
    graph["nodes"] = list(nodes.values()) + new_nodes

    # 2. 관계·근거 어휘
    legacy = load_ontology()["legacy_stage_to_tier"]
    drop = {"e049", "e106"}  # 제품 implements 로 대체됨
    edges = [e for e in edges if e["id"] not in drop]
    for e in edges:
        e["relation"] = RELATION_MAP.get(e["relation"], e["relation"])
        if e["from"].startswith("bottleneck:") and e["relation"] == "requires":
            e["relation"] = "mitigated_by"
        if e["from"].startswith("req:") and e["to"].startswith("req:") and e["relation"] == "requires":
            e["relation"] = "drives_requirement"
        if "stage" in e:
            e["evidence_tier"] = legacy[e.pop("stage")]
        for ev in e.get("evidence", []):
            if "source_quality" in ev:
                ev["source_type"] = ev.pop("source_quality")
    graph["edges"] = edges

    # 3. 생태계·기업 메타
    _assign_ecosystems(graph)
    for n in graph["nodes"]:
        if n["id"] in COMPANY_META:
            n.update(COMPANY_META[n["id"]])
            n.setdefault("in_universe", False)
            n.pop("measured_metrics", None)
            n.pop("disclosure_note", None)

    # 3b. 이벤트·감시 대상 id 재매핑
    remap = {old: spec["product"] for old, spec in PRODUCT_SPLIT.items()}
    for row in graph["events"] + graph["watches"]:
        row["target_id"] = remap.get(row["target_id"], row["target_id"])

    # 4. 추가
    have = {n["id"] for n in graph["nodes"]}
    graph["nodes"] += [n for n in NEW_NODES if n["id"] not in have]
    graph["edges"] += NEW_EDGES
    graph["events"] += NEW_EVENTS
    graph["watches"] += NEW_WATCHES
    for n in graph["nodes"]:
        n.pop("disclosure_note", None)

    graph["schema_version"] = "0.3"
    graph["as_of"] = "2026-10-27"
    graph["ontology"] = "research/ecosystems/ontology.json"
    graph["notes"] = [
        "v0.3: 닫힌 어휘(ontology.json). 노드 kind / 관계 relation / 근거 evidence_tier 는 정의된 값만. 검증: python -m wsj.ecosystems.ontology --check",
        "product(특정 회사 제품)과 technology(일반 기술)를 분리. offered_by 는 판매 보유, supplied_to 는 확인된 거래, qualifying_with 는 인증·협업 단계",
        "수요 측(product_generation·standard·customer 기업)을 명시해 '세대 전환 → 요구 → 병목 → 기술 → 제품 → 공급사' 와 '고객 채택/연기' 를 같은 그래프에서 읽는다",
        "defers / displaces / substitutes_for 는 부정·조건부 극성. 영향 전파는 confidence(근거 등급) 와 polarity 를 곱한다",
        "in_universe 는 core.companies 기준 (현재 공급사 전부 false — 유니버스 SIC 버킷이 장비·부품사를 포함하지 않음, BACKLOG 참조)",
        "관계는 매출 증거가 아니다. 상장사 수혜는 supplied_to 이상 + 매출 노출 공시가 있을 때만",
    ]
    return graph


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, default=GRAPH_PATH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    out = migrate(graph)
    onto = load_ontology()
    for e in out["edges"]:
        e["confidence"] = edge_confidence(e, onto)
    rep = validate(out, onto)
    print(json.dumps(rep.stats, ensure_ascii=False, indent=1))
    for w in rep.warnings:
        print("WARN", w)
    for err in rep.errors:
        print("ERROR", err)
    if rep.errors:
        return 1
    if not args.dry_run:
        args.graph.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"written {args.graph}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
