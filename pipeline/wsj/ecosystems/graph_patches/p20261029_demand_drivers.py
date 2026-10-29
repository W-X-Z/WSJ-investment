"""2026-10-29 수요측 층 (ADR-0025): 워크로드 변화 → 메모리 요구 → 비트 공급 병목 → 메모리 공급사.

    python -m wsj.ecosystems.graph_patches.p20261029_demand_drivers

지금까지 그래프는 세대·표준(gen:hbm4)에서 시작했다 — "AI 가 에이전트로 쓰이면 메모리가 얼마나 더 필요한가" 를 그릴 노드가 없었다.
수요 동인(demand_driver) 세 개와 그것이 강제하는 요구·병목·부품을 더해 메모리 3사까지 잇는다. 근거는 TrendForce 2026-07-07 인사이트(원문 확인)와
SK hynix 3Q26 실적 보도(EE Times·DigiTimes 2026-10-28). 크기는 관측치(obs:*)로 잰다 — 질문당 출력 토큰, CPU:GPU 비, 랙당 컨텍스트 저장 용량.
"""

from __future__ import annotations

from wsj.ecosystems.graph_patches import Edge, Node, apply

TF = ("https://www.trendforce.com/insights/ai-inference-drives-memory-demand", "third_party_report", "2026-07-07",
      "average output tokens per question have grown more than 5x per year since 2H 2024, reaching roughly 30,000-40,000 tokens; "
      "Dynamo (March 2025) moves infrequently used KV cache to CPU RAM and SSD; CMX Context Memory Storage Platform (January 2026) ~9,600 TB per rack; "
      "CPU-to-GPU ratio for agentic AI expected to shift from 1:4 or 1:8 to about 1:1; Vera CPU supports up to 1.5 TB of LPDDR5X; "
      "Nvidia reportedly halving SOCAMM capacity on Vera Rubin due to insufficient LPDRAM allocation under suppliers' preliminary 2027 production plans")
EET = ("https://www.eetimes.com/sk-hynix-reports-record-q3-results-driven-by-ai-memory-surge/", "third_party_report", "2026-10-28",
       "SK hynix: customers want more than twice the HBM it can supply; DRAM and HBM sold out through 2029 (3Q26 results call)")
DT_NAND = ("https://www.digitimes.com/news/a20261028VL212/sk-hynix-flash-data-hbm-nand.html", "third_party_report", "2026-10-28",
           "SK hynix on AI inference lifting NAND/eSSD demand alongside HBM (3Q26)")

NODES = [
    Node("demand_driver:agentic_inference", "demand_driver", "에이전트 추론 워크로드 (다단계·장시간 세션, CPU:GPU 1:1 로)", "hbm"),
    Node("demand_driver:long_context", "demand_driver", "긴 컨텍스트·출력 토큰 폭증 (질문당 출력 토큰 연 5배↑, 3~4만 토큰)", "hbm"),
    Node("demand_driver:kv_cache_residency", "demand_driver", "KV 캐시 상주·오프로딩 (HBM → CPU DRAM → SSD 컨텍스트 계층)", "hbm"),
    Node("req:memory_per_accelerator", "requirement", "가속기당 메모리 용량·대역폭 요구 (KV 캐시 ∝ 시퀀스 길이 × 배치)", "hbm"),
    Node("req:cpu_memory_per_rack", "requirement", "랙당 CPU 메모리 요구 (Vera 1.5TB LPDDR5X, SOCAMM2)", "hbm"),
    Node("req:context_storage_tier", "requirement", "컨텍스트 저장 계층 요구 (KV 캐시용 SSD POD, 랙당 ~9,600TB)", "hbm"),
    Node("bottleneck:hbm_bit_supply", "bottleneck", "HBM 비트 공급 부족 (수요가 공급의 2배, 2029년까지 매진)", "hbm"),
    Node("bottleneck:dram_bit_supply", "bottleneck", "DRAM·LPDRAM 비트 공급 부족 (2027 할당 부족으로 SOCAMM 용량 반감)", "hbm"),
    Node("component:hbm_stack", "component", "HBM 스택 (세대 불문 BOM 부품 — HBM3E·HBM4)", "hbm"),
    Node("component:server_dram_lpdram", "component", "서버 DRAM·LPDRAM 모듈 (RDIMM·SOCAMM2)", "hbm"),
    Node("component:kv_cache_ssd", "component", "KV 캐시·컨텍스트 저장용 고용량 eSSD (QLC)", "hbm"),
]

EDGES = [
    Edge("demand_driver:long_context", "drives_requirement", "req:memory_per_accelerator", TF, "third_party_report",
         note="KV 캐시 = 2 × layers × KV heads × head dim × sequence length × batch × bytes — 출력 토큰이 늘면 가속기당 메모리가 는다"),
    Edge("demand_driver:agentic_inference", "drives_requirement", "req:cpu_memory_per_rack", TF, "third_party_report",
         note="에이전트 AI 에서 CPU:GPU 1:4~1:8 → 1:1, Vera 1.5TB LPDDR5X"),
    Edge("demand_driver:kv_cache_residency", "drives_requirement", "req:context_storage_tier", TF, "third_party_report",
         note="Dynamo(2025-03) KV 캐시 오프로딩, CMX(2026-01) 랙당 ~9,600TB 컨텍스트 계층"),
    Edge("demand_driver:agentic_inference", "drives_requirement", "req:memory_per_accelerator", TF, "technical_inference",
         note="장시간 세션은 KV 캐시를 더 오래 상주시킨다 (추론)"),
    Edge("req:memory_per_accelerator", "drives_requirement", "req:hbm_stack", TF, "technical_inference",
         note="가속기당 메모리 요구가 HBM 적층 수·용량 요구로 (추론)"),
    Edge("req:memory_per_accelerator", "creates_bottleneck", "bottleneck:hbm_bit_supply", EET, "third_party_report",
         note="SK hynix 3Q26: HBM 요청 물량이 공급의 2배, 2029년까지 매진"),
    Edge("req:cpu_memory_per_rack", "creates_bottleneck", "bottleneck:dram_bit_supply", TF, "third_party_report",
         note="2027 LPDRAM 할당 부족으로 Vera Rubin SOCAMM 용량 반감 보도"),
    Edge("bottleneck:hbm_bit_supply", "mitigated_by", "component:hbm_stack", EET, "technical_inference", note="공급 확대 = HBM 스택 증산"),
    Edge("bottleneck:dram_bit_supply", "mitigated_by", "component:server_dram_lpdram", TF, "technical_inference", note="공급 확대 = 서버 DRAM·LPDRAM 증산"),
    Edge("req:context_storage_tier", "requires", "component:kv_cache_ssd", TF, "third_party_report", note="SSD POD 컨텍스트 계층"),
    Edge("component:hbm_stack", "offered_by", "company:skhynix", EET, "third_party_report"),
    Edge("component:hbm_stack", "offered_by", "company:samsung", EET, "third_party_report"),
    Edge("component:hbm_stack", "offered_by", "company:mu", TF, "third_party_report"),
    Edge("component:server_dram_lpdram", "offered_by", "company:skhynix", TF, "third_party_report", note="SOCAMM2 샘플"),
    Edge("component:server_dram_lpdram", "offered_by", "company:samsung", TF, "technical_inference"),
    Edge("component:server_dram_lpdram", "offered_by", "company:mu", TF, "technical_inference"),
    Edge("component:kv_cache_ssd", "offered_by", "company:skhynix", DT_NAND, "third_party_report"),
    Edge("component:kv_cache_ssd", "offered_by", "company:samsung", DT_NAND, "technical_inference"),
    Edge("component:kv_cache_ssd", "offered_by", "company:mu", DT_NAND, "technical_inference"),
]

ALIASES = {
    "demand_driver:agentic_inference": ["agentic inference", "AI agents workload", "에이전트 추론"],
    "demand_driver:long_context": ["long context", "output tokens", "reasoning tokens", "긴 컨텍스트"],
    "demand_driver:kv_cache_residency": ["KV cache", "KV 캐시", "context memory", "Dynamo", "CMX"],
    "bottleneck:hbm_bit_supply": ["HBM shortage", "HBM sold out", "HBM 공급 부족"],
    "bottleneck:dram_bit_supply": ["DRAM shortage", "LPDRAM allocation", "SOCAMM", "DRAM 공급 부족"],
    "component:kv_cache_ssd": ["SSD POD", "QLC eSSD", "context storage"],
}

if __name__ == "__main__":
    raise SystemExit(apply(NODES, EDGES, "d1029", aliases=ALIASES))
