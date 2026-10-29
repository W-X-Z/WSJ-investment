"""2026-10-30 약한 신호 스캔의 잔차 (ADR-0026 1부 첫 실행): 온톨로지에 없던 것을 노드로, 수집기가 못 잡던 기존 노드엔 별칭을.

    python -m wsj.ecosystems.graph_patches.p20261030_weak_signals

research/weak_signals/20261029.md 의 §5. 출처 유형 둘 이상에서 만난 것만 노드로 올렸다 — HBF·NAND, CXL 풀 메모리·컨트롤러, PIM, 3D DRAM,
스케일업 패브릭 표준 셋(UEC·UALink·SUE-T/ESUN)과 그 요구, 계통 외란 사양과 그리드포밍 인버터, HTS 버스웨이, 멀티코어 파이버·TFLT, 영상 생성 수요 동인.
근거는 에이전트가 가져온 원문 URL(논문·표준·학회 프로그램·공시)이고 tier 는 그 종류대로 — 추론으로 이은 고리는 technical_inference.
벤더·고객 캐파 금융, 모델 랩의 칩 설계, API 용량 배급은 구조·데이터라 그래프가 아니라 weak_signals 에만 둔다.
"""

from __future__ import annotations

from wsj.ecosystems.graph_patches import Edge, Node, apply

A = "https://arxiv.org/abs/"
HBF_P = (A + "2609.25782", "paper", "2026-09-22", "HBF hot-cold KV tiering: 24x concurrent sessions per GPU, HBM confined to hot set cuts read power 7.6 kW per 8-GPU node")
HBF_NEG = (A + "2608.11668", "paper", "2026-08-12", "HBF as SSD-style KV offload: E2E latency 2-5.5x worse; KV traffic is write-heavy, stack hits thermal limit")
HBF_HC = ("https://hotchips.org/", "conference", "2026-08-23", "Hot Chips 2026 tutorial: HBF in AI Compute - A System Architect's view (Oxmiq Labs, PRAXMATI)")
HBF_SK = ("https://news.skhynix.com/en/q3-2026-business-results/", "official_issuer", "2026-10-28", "SK hynix 3Q26: NAND roadmap built on HBF (high-bandwidth flash); expects memory shortages through 2030")
CXL_P = (A + "2610.22716", "paper", "2026-10-15", "CMM-MP: CXL + Ethernet memory pool device, hundreds of TB logical memory, 2.7 us latency, 23 GB/s")
CXL_SPEC = ("https://computeexpresslink.org/wp-content/uploads/2025/11/CXL_4.0-Specification-Release_FINAL_Website-Copy.pdf", "standard", "2025-11-18", "CXL 4.0: 128 GT/s, bundled ports, up to 4 retimers, memory RAS")
CXL_SK = ("https://news.skhynix.com/en/ocp-global-summit-2026/", "conference", "2026-10-23", "SK hynix OCP 2026: KV-cache transfer/reuse over CXL pooled memory demo; CMM-DDR5 256 GB (CXL 3.x); CMM-Ax; 192 GB SOCAMM2; 128 GB MRDIMM")
CXL_MRVL = ("https://investor.marvell.com/news-events/press-releases/", "official_issuer", "2026-10-12", "Marvell Structera X 3406/3506 six-channel CXL 3.2 memory expanders for AI inference; memory shortage driving IT managers to use CXL to re-deploy used DDR4 DIMMs into DDR5 systems; sampling Q1 2027")
PIM_HC = ("https://hotchips.org/", "conference", "2026-08-25", "Hot Chips 2026: Samsung LPDDR5X-PIM, world's first LPDDR-based processing in memory, up to 8x effective bandwidth")
PNM_P = (A + "2610.26131", "paper", "2026-10-19", "DuoPD: PNM units in the HBM logic die run the entire decode phase sharing the HBM interface")
DRAM3D_P = (A + "2609.24343", "paper", "2026-09-21", "3D volumetric DRAM stacked above GPU with interleaved cooling cavities; stack height dominates peak temperature")
DRAM3D_IEDM = ("https://ieee-iedm.org/program/short-courses/", "conference", "2026-12-13", "IEDM 2026 short course: Kioxia OCTRAM (oxide-semiconductor channel transistor DRAM) for sub-10nm nodes and beyond")
DRAM3D_HC = ("https://hotchips.org/", "conference", "2026-08-23", "Hot Chips 2026: 3D DRAM based accelerator for generative inference (d-Matrix, Meta)")
UEC = ("https://ultraethernet.org/specification-history/", "standard", "2026-10-12", "Ultra Ethernet Specification 1.1: Unified Local Profile for scale-up (RODL, UFH header, CSIG, in-network collectives)")
SUET = ("https://www.opencompute.org/wp-content/uploads/2026/10/Scale-Up-Ethernet-Transport-SUE-T-Base-Specification-v1.0.0.pdf", "standard", "2026-10-08", "OCP SUE-T base spec v1.0.0: up to 16K XPUs, 1-hop < 2 us, 256 B transactions, lossless Ethernet (PFC/CBFC/LLR)")
ESUN = ("https://www.opencompute.org/documents/ocp-esun-network-operator-requirements-base-specification-rev-1-0-final-pdf/", "standard", "2026-02-09", "OCP ESUN network operator requirements v1.0: 4-byte ESUN header replaces IP, LLR/CBFC on switches, MACsec")
UAL = ("https://ualinkconsortium.org/wp-content/uploads/2026/04/UALink-2.0-Specification-PR_FINAL.pdf", "standard", "2026-04-07", "UALink 2.0 family ratified: common spec with in-network compute, 200G DL/PL 2.0, manageability 1.0, chiplet spec 1.0 (UCIe 3.0-compliant)")
MRVL_RT = ("https://investor.marvell.com/news-events/press-releases/", "official_issuer", "2026-10-13", "Marvell Alaska E 3.2T protocol-aware Ethernet/UALink/ESUN retimer (16x224G PAM4)")
GRID = ("https://www.opencompute.org/wp-content/uploads/2026/10/OCP-Base-Spec-Interface-Specification-Between-Hyperscalers-and-Utility-Grid-for-Disturbance-Performance.pdf", "standard", "2026-09-17",
        "OCP interface specification between hyperscalers and utility grid for disturbance performance v1.0.0; follow-on spec on ramp-rate/oscillation limits announced")
TORQ = (A + "2610.22572", "paper", "2026-10-15", "DC-TORQ: closed-form transfer functions from data-center power perturbation to generator shaft torque; frequency-dependent limits on allowed oscillation")
SWSMOOTH = (A + "2610.36441", "paper", "2026-10-27", "Phase-coordinated job launch: -74.39% mean-square fluctuation in 0.2-2 Hz band without smoothing hardware")
ANTH_NPI = ("https://job-boards.greenhouse.io/anthropic/jobs/5409569008", "hiring", "2026-08-19", "Anthropic NPI sourcing manager, data center power & cooling: BESS, grid-forming and grid-following inverters, solid-state transformers, E-STATCOM, MV switchgear")
OCP_SCHED = ("https://2026ocpglobal.fnvirtual.app/a/schedule/", "conference", "2026-10-14", "OCP Global Summit 2026 schedule: HTS workshop (Tokamak Energy 3.8 MW 800VDC-HTS busway, VEIR 250 MW, LS Cable, Nexans SFCL, Vision Electric); Google hardware mitigations with supercapacitor and battery; Panasonic BBU/CBU")
OCP_EMEA = ("https://www.opencompute.org/events/future-tech-symposium/ocp-future-technologies-symposium/", "conference", "2026-04-29", "OCP EMEA 2026 FTS best paper: Rittal + Vision Electric, superconducting distribution for multi-MW data halls")
MGX = ("https://www.opencompute.org/wp-content/uploads/2026/10/MGX-Accelerated-Computing-Rack-and-Trays-Specification-1.2.0-Final.pdf", "standard", "2026-10-06", "MGX rack & trays 1.2.0: liquid-cooled 48 V busbar rated 5,000 A, 250 kW/350 LPM racks")
MCF_P = (A + "2609.20686", "paper", "2026-09-17", "Volumetric evanescent edge coupling to multicore fiber: 88% (-0.56 dB) coupling, 86 nm 1-dB bandwidth")
MCF_OCP = ("https://2026ocpglobal.fnvirtual.app/a/schedule/", "conference", "2026-10-14", "LightXcelerate: micro-VCSEL arrays + 19-core multicore fiber, 608 Gb/s per fiber, > 6 Tb/s/mm2 beachfront")
TFLT_P = (A + "2610.26674", "paper", "2026-10-19", "Thin-film lithium tantalate 8-wavelength monolithic transmitter, 1.6 Tb/s aggregate, two-fiber interface")
TFLT_ECOC = ("https://www.ecoc2026.org/ECOC2026/programme/invited-speakers", "conference", "2026-09-21", "ECOC 2026 invited (Kippenberg): thin-film lithium tantalate PICs for high-speed comms and lasers")
VIDEO_G = ("https://ai.google.dev/gemini-api/docs/changelog", "official_issuer", "2026-08-27", "Gemini Omni Flash GA: video generation and editing 360p-4K, video extension, first/last-frame interpolation")
VIDEO_V = ("https://blog.vllm.ai/blog/2026-08-17-distributed-layerwise-offload", "official_issuer", "2026-08-17", "vLLM-Omni distributed layerwise offload: 8xB300 MiniMax-H3 183.78 videos/h, 43.97 Wh per video; video models exceed single-GPU HBM")

NODES = [
    Node("demand_driver:video_generation", "demand_driver", "영상 생성 워크로드 (영상 토큰 ≫ 텍스트 — 영상당 Wh·GPU 시간)", "hbm"),
    Node("tech:hbf", "technology", "고대역폭 플래시 (HBF: XPU 옆 TSV 적층 NAND, HBM 아래 용량 계층)", "hbm"),
    Node("component:nand_3d", "component", "3D NAND (TLC/QLC 셀 — eSSD·HBF 의 저장 매체)", "hbm"),
    Node("tech:cxl_memory_pool", "technology", "CXL 풀 메모리·메모리 패브릭 (노드 간 KV 캐시 공유 계층)", "hbm"),
    Node("component:cxl_controller", "component", "CXL 컨트롤러·스위치·메모리 확장 장치 (CMM·Structera·Leo)", "hbm"),
    Node("tech:pim", "technology", "프로세싱 인 메모리 (PIM/PNM: LPDDR-PIM·CMM-Ax·베이스 다이 PNM)", "hbm"),
    Node("tech:3d_dram", "technology", "3D DRAM·산화물 채널 DRAM (OCTRAM/IGZO, 연산 위 DRAM 적층 — 6F² 벽의 출구)", "hbm"),
    Node("standard:uec", "standard", "Ultra Ethernet 1.1 (스케일아웃 + ULP 스케일업 프로파일)", "optics"),
    Node("standard:ualink", "standard", "UALink 2.0 (스케일업, 인네트워크 컴퓨트, UCIe 칩렛 1.0)", "optics"),
    Node("standard:scaleup_ethernet", "standard", "스케일업 이더넷 SUE-T 1.0 · ESUN 1.0 (OCP)", "optics"),
    Node("req:open_scaleup_fabric", "requirement", "개방형 스케일업 패브릭 요구 (2군 XPU 의 표준 링크 — 16K XPU·1홉 <2µs)", "optics"),
    Node("standard:ocp_grid_interface", "standard", "OCP 하이퍼스케일러↔유틸리티 외란 성능 인터페이스 v1.0 (램프레이트 후속 예고)", "power"),
    Node("req:grid_disturbance_ridethrough", "requirement", "계통 외란 라이드스루·램프레이트 요구 (sag 에 트립 금지 → 홀드업·평활을 랙·MV-UPS 로)", "power"),
    Node("component:grid_forming_inverter", "component", "그리드포밍 인버터·E-STATCOM (데이터센터 측 계통 안정화 설비)", "power"),
    Node("bottleneck:rack_busbar_losses", "bottleneck", "랙당 >1MW 에서 구리 버스웨이의 I²R 손실·중량", "power"),
    Node("tech:hts_busway", "technology", "초전도(HTS) 버스웨이·케이블 (REBCO 테이프, 극저온 루프)", "power"),
    Node("material:multicore_fiber", "material", "멀티코어 파이버 (MCF, 19코어·공간분할다중화)", "optics"),
    Node("material:tflt", "material", "박막 리튬탄탈레이트 (TFLT — TFLN 대안 변조기·콤 플랫폼)", "optics"),
    Node.company("company:ls_cable", "LS Cable & System (비상장, LS 006260 자회사)", "power", None, None, "large", role="supplier"),
]

EDGES = [
    # 영상 생성 → 가속기당 메모리
    Edge("demand_driver:video_generation", "drives_requirement", "req:memory_per_accelerator", [VIDEO_V, VIDEO_G], "official_issuer",
         note="영상 모델은 GPU 하나의 HBM 을 넘어 레이어 분산 오프로드가 필요; 영상당 43.97Wh"),
    # HBF
    Edge("bottleneck:hbm_bit_supply", "mitigated_by", "tech:hbf", [HBF_P, HBF_HC, HBF_SK], "third_party_report",
         note="hot KV 는 HBM, cold 세션·가중치는 HBF — GPU 당 세션 24×; 반증 논문: write-heavy KV 는 2~5.5× 느림"),
    Edge("req:context_storage_tier", "requires", "component:nand_3d", HBF_SK, "technical_inference", note="컨텍스트 저장 계층(eSSD)의 매체"),
    Edge("tech:hbf", "requires", "component:nand_3d", HBF_HC, "technical_inference", note="TSV 적층 NAND"),
    Edge("tech:hbf", "requires", "component:hbm_base_die", PNM_P, "technical_inference", note="HBM 베이스 다이를 경유하는 GPU↔HBF 경로 (2608.14333)"),
    Edge("tech:hbf", "displaces", "component:server_dram_lpdram", HBF_NEG, "technical_inference", polarity="negative",
         note="KV 용 호스트 DRAM 일부를 대체할 수 있음 — 단 write-heavy 에선 반대 (반증 논문)"),
    Edge("tech:hbf", "offered_by", "company:skhynix", HBF_SK, "official_issuer", note="3Q26: NAND 로드맵을 HBF 위에"),
    Edge("component:nand_3d", "offered_by", "company:skhynix", HBF_SK, "official_issuer"),
    Edge("component:nand_3d", "offered_by", "company:samsung", HBF_SK, "technical_inference"),
    Edge("component:nand_3d", "offered_by", "company:mu", HBF_SK, "technical_inference"),
    # CXL
    Edge("bottleneck:dram_bit_supply", "mitigated_by", "tech:cxl_memory_pool", [CXL_MRVL, CXL_SK, CXL_P], "official_issuer",
         note="메모리 부족이 중고 DDR4 를 CXL 로 재배치하게 한다 (Marvell); KV-over-CXL 데모 (SK hynix)"),
    Edge("req:context_storage_tier", "requires", "component:cxl_controller", CXL_SK, "technical_inference", note="풀 메모리 계층의 컨트롤러·스위치"),
    Edge("tech:cxl_memory_pool", "requires", "component:cxl_controller", CXL_SPEC, "standard_body"),
    Edge("tech:cxl_memory_pool", "requires", "component:server_dram_lpdram", CXL_P, "technical_inference", note="풀 DRAM"),
    Edge("component:cxl_controller", "offered_by", "company:mrvl", CXL_MRVL, "official_issuer", note="Structera X, 2027-1Q 샘플"),
    Edge("component:cxl_controller", "offered_by", "company:alab", CXL_SPEC, "technical_inference", note="Leo CXL 컨트롤러"),
    Edge("component:cxl_controller", "offered_by", "company:montage", CXL_SPEC, "technical_inference"),
    Edge("component:cxl_controller", "offered_by", "company:skhynix", CXL_SK, "official_issuer", note="CMM-DDR5·CMM-Ax"),
    Edge("component:cxl_controller", "offered_by", "company:samsung", CXL_SK, "technical_inference", note="CMM-D"),
    # PIM · 3D DRAM
    Edge("bottleneck:hbm_bit_supply", "mitigated_by", "tech:pim", [PIM_HC, PNM_P], "third_party_report", note="뱅크 안 연산으로 유효 대역폭 8× — HBM 대신 LPDDR 로 추론"),
    Edge("tech:pim", "offered_by", "company:samsung", PIM_HC, "vendor_claim", note="LPDDR5X-PIM"),
    Edge("tech:pim", "offered_by", "company:skhynix", CXL_SK, "vendor_claim", note="CMM-Ax"),
    Edge("bottleneck:dram_bit_supply", "mitigated_by", "tech:3d_dram", [DRAM3D_IEDM, DRAM3D_HC, DRAM3D_P], "third_party_report",
         note="평면 커패시터 스케일링 한계(6F² 벽)의 출구 — 36~60개월"),
    Edge("tech:3d_dram", "requires", "equipment:hybrid_bonder", DRAM3D_P, "technical_inference", note="웨이퍼 본딩"),
    Edge("tech:3d_dram", "offered_by", "company:samsung", OCP_SCHED, "vendor_claim", note="OCP FTS 키노트: 메모리 포드·3D DRAM"),
    Edge("tech:3d_dram", "offered_by", "company:skhynix", DRAM3D_IEDM, "vendor_claim", note="IEDM 기조: 2D→3D 메모리·웨이퍼 본딩"),
    # 스케일업 패브릭 개방
    Edge("standard:uec", "drives_requirement", "req:open_scaleup_fabric", UEC, "standard_body"),
    Edge("standard:ualink", "drives_requirement", "req:open_scaleup_fabric", UAL, "standard_body"),
    Edge("standard:scaleup_ethernet", "drives_requirement", "req:open_scaleup_fabric", [SUET, ESUN], "standard_body"),
    Edge("req:open_scaleup_fabric", "drives_requirement", "req:scaleup_optical", UAL, "technical_inference", note="도메인이 1,152 XPU 로 가면 구리 밖"),
    Edge("req:open_scaleup_fabric", "requires", "component:retimer", MRVL_RT, "official_issuer", note="멀티프로토콜 3.2T 리타이머"),
    Edge("component:retimer", "offered_by", "company:mrvl", MRVL_RT, "official_issuer"),
    # 계통 외란 사양
    Edge("standard:ocp_grid_interface", "drives_requirement", "req:grid_disturbance_ridethrough", GRID, "standard_body"),
    Edge("req:grid_disturbance_ridethrough", "requires", "component:supercapacitor", [GRID, OCP_SCHED], "standard_body", note="홀드업·평활을 랙으로"),
    Edge("req:grid_disturbance_ridethrough", "requires", "component:bbu", GRID, "standard_body"),
    Edge("req:grid_disturbance_ridethrough", "requires", "component:facility_bess", [GRID, ANTH_NPI], "technical_inference", note="MV-UPS·BESS"),
    Edge("req:grid_disturbance_ridethrough", "requires", "component:grid_forming_inverter", [ANTH_NPI, TORQ], "technical_inference",
         note="모델 랩의 소싱 공고에 그리드포밍 인버터·E-STATCOM; 발전기 비틀림 진동 한계"),
    Edge("component:grid_forming_inverter", "offered_by", "company:abb", ANTH_NPI, "technical_inference"),
    Edge("component:grid_forming_inverter", "offered_by", "company:schneider", ANTH_NPI, "technical_inference"),
    Edge("component:grid_forming_inverter", "offered_by", "company:hyosung_hi", ANTH_NPI, "technical_inference", note="STATCOM"),
    Edge("component:grid_forming_inverter", "offered_by", "company:ls_electric", ANTH_NPI, "technical_inference"),
    Edge("tech:gpu_power_smoothing", "displaces", "component:supercapacitor", SWSMOOTH, "technical_inference", polarity="negative",
         note="잡 위상 조정으로 0.2~2Hz 변동 −74% — 평활 하드웨어 용량 일부 대체"),
    # HTS 버스웨이
    Edge("req:800v", "creates_bottleneck", "bottleneck:rack_busbar_losses", MGX, "technical_inference", note="5,000A 수냉 버스바가 이미 필요"),
    Edge("bottleneck:rack_busbar_losses", "mitigated_by", "component:liquid_cooled_busbar", MGX, "standard_body"),
    Edge("bottleneck:rack_busbar_losses", "mitigated_by", "tech:hts_busway", [OCP_SCHED, OCP_EMEA], "third_party_report",
         note="Tokamak Energy 3.8MW 800VDC-HTS: 저압 손실 −98%·도체 중량 −94%"),
    Edge("tech:hts_busway", "offered_by", "company:ls_cable", OCP_SCHED, "third_party_report", note="OCP HTS 워크숍 발표사"),
    # 광 소재
    Edge("tech:microled_link", "requires", "material:multicore_fiber", [MCF_OCP, MCF_P], "technical_inference", note="slow-and-wide: µVCSEL/µLED 어레이 ↔ 멀티코어 파이버"),
    Edge("bottleneck:modulator_bw_400g", "mitigated_by", "material:tflt", [TFLT_P, TFLT_ECOC], "third_party_report", note="TFLT 8λ 1.6T 송신기"),
]

ALIASES = {
    "tech:hbf": ["HBF", "high-bandwidth flash", "high bandwidth flash", "고대역폭 플래시"],
    "component:nand_3d": ["3D NAND", "NAND", "QLC", "TLC", "낸드"],
    "tech:cxl_memory_pool": ["CXL memory pool", "CXL pooled memory", "memory fabric", "CMS", "CXL 풀 메모리"],
    "component:cxl_controller": ["CXL controller", "CXL switch", "CXL memory expander", "CMM-DDR5", "Structera", "CXL 컨트롤러"],
    "tech:pim": ["PIM", "PNM", "processing in memory", "processing-in-memory", "near-memory processing", "LPDDR-PIM", "CMM-Ax"],
    "tech:3d_dram": ["3D DRAM", "vertical DRAM", "OCTRAM", "IGZO DRAM", "oxide semiconductor DRAM", "DRAM-on-compute"],
    "standard:uec": ["Ultra Ethernet", "UEC", "UET"],
    "standard:ualink": ["UALink", "Ultra Accelerator Link"],
    "standard:scaleup_ethernet": ["SUE-T", "ESUN", "scale-up Ethernet", "Scale-Up Ethernet Transport"],
    "req:open_scaleup_fabric": ["open scale-up fabric", "scale-up fabric"],
    "standard:ocp_grid_interface": ["grid disturbance performance", "hyperscaler utility interface"],
    "req:grid_disturbance_ridethrough": ["ride-through", "ride through", "ramp-rate limit", "fault ride through"],
    "component:grid_forming_inverter": ["grid-forming inverter", "grid forming", "E-STATCOM", "STATCOM", "그리드포밍"],
    "tech:hts_busway": ["HTS", "superconducting busway", "superconducting cable", "high-temperature superconducting", "REBCO", "초전도"],
    "material:multicore_fiber": ["multicore fiber", "multi-core fiber", "MCF", "멀티코어 광섬유"],
    "material:tflt": ["lithium tantalate", "TFLT", "LiTaO3", "리튬탄탈레이트"],
    "demand_driver:video_generation": ["video generation", "text-to-video", "영상 생성"],
    # 있었지만 수집기가 못 잡던 노드
    "tech:npo": ["NPO", "near-package optics", "near package optics", "CPX", "OpenCPX", "XPO"],
    "tech:custom_hbm": ["cHBM", "custom HBM", "custom base die", "NVHBM", "SPHBM4", "SPHBM"],
    "component:hbm_base_die": ["HBM base die", "base die", "logic base die"],
    "tech:panel_organic_interposer": ["panel interposer", "panel-level interposer", "organic interposer"],
    "req:400g_lane": ["400G/lane", "400G per lane", "448G", "802.3dv"],
    "tech:microled_link": ["microLED", "micro-LED", "µLED", "slow-and-wide", "slow and wide", "wide-and-slow"],
    "component:sst": ["SST", "solid-state transformer", "solid state transformer", "고체 변압기"],
    "component:facility_bess": ["BESS", "battery energy storage", "에너지저장장치"],
    "req:rack_energy_storage": ["CBU", "capacitor backup unit", "in-rack power filtering"],
    "component:hs_copper_cable": ["co-packaged copper", "CPC", "flyover cable"],
    "tech:heat_reuse": ["heat reuse", "waste heat", "폐열"],
    "tech:immersion_two_phase": ["two-phase immersion", "immersion cooling", "침지냉각"],
}


def main() -> int:
    return apply(NODES, EDGES, "w1030", aliases=ALIASES)


if __name__ == "__main__":
    raise SystemExit(main())
