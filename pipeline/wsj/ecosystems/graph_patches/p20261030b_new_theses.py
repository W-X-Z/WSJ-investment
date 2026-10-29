"""2026-10-30 새 테제 3개(ADR-0026 2부, 사람이 세션에서 돌림)가 필요로 한 노드·간선.

    python -m wsj.ecosystems.graph_patches.p20261030b_new_theses

- 메모리 인터페이스 칩(RCD·MRCD/MDB·PMIC) — 비트가 아니라 모듈 수·모듈당 채널로 팔리는 부품이 그래프에 없었다.
- Google TPU 시스템(외부 판매) · 고다층 MLB · 이수페타시스 — TPU 공급망의 설계사 밖 고리.
- 효성중공업의 STATCOM·e-STATCOM·SST 근거.
근거는 이 세션에서 원문을 직접 연 것만 (tier 는 종류대로).
"""

from __future__ import annotations

from wsj.ecosystems.graph_patches import Edge, Node, apply

SKH_OCP = ("https://news.skhynix.com/en/ocp-global-summit-2026/", "official_issuer", "2026-10-16",
           "SK hynix OCP 2026: 128GB DDR5 MRDIMM; 256GB 3DS RDIMM 'the industry's largest capacity for AI workloads'; KV cache over CXL pooled memory demo")
RMBS_Q3 = ("https://pro.edgex.exchange/en-US/news/article/rambus-record-q3-2026-revenue-ai-server-demand", "third_party_report", "2026-10-27",
           "Rambus Q3 2026: record product revenue $114.3M (+22% YoY, +15% QoQ), led by DDR5 registered clock drivers for AI servers; PMIC for LPDDR6 SOCAMM2")
MRVL_SX = ("https://investor.marvell.com/news-events/press-releases/detail/1037/marvell-unveils-second-generation-structera-x-industry-first-six-channel-cxl-3-2-memory-expanders-for-ai-inference",
           "official_issuer", "2026-10-12", "today's memory shortage and subsequent high prices are driving IT managers to use CXL to re-deploy used DDR4 DIMMs into DDR5 systems; KV-cache capacity directly determines TTFT")
DCD_TPU = ("https://www.datacenterdynamics.com/en/news/google-grows-tpu-stash-by-7bn-in-last-year/", "third_party_report", "2026-07-30",
           "Q2 FY2026 call: TPU system sales are reflected in the $514bn cloud backlog; 'the vast majority of the revenue from that agreement come through in 2027'; 10-Q inventory primarily hardware related to TPU systems for sale to enterprise customers")
TNW_TPU = ("https://thenextweb.com/news/google-inference-chips-nvidia-challenge-supply-chain", "third_party_report", "2026-04-20",
           "Broadcom long-term supply agreement through 2031 (TPU v8 'Sunfish', 2nm, late 2027); MediaTek cost-optimised inference variant 'Zebrafish'; ~4.3M TPU shipments projected 2026, >35M 2028; Anthropic ~3.5 GW next-gen TPU from 2027")
MS_TPU = ("https://www.kucoin.com/news/flash/morgan-stanley-defends-broadcom-s-role-in-google-s-tpu-supply-chain-forecasts-5m-shipments-by-2027", "third_party_report", "2026-07-15",
          "Morgan Stanley: TPU shipments 3.2M (2026), 5M (2027); Broadcom retains majority role in high-performance variants")
ISU = ("https://dealsite.co.kr/articles/150410", "third_party_report", "2025-10-31", "이수페타시스는 구글 TPU 에 들어가는 MLB 를 공급하는 핵심 협력사로 분석; 800G MLB 수율 80% 중반")
HYO_KPI = ("https://www.kpinews.kr/newsView/1065577251239974", "third_party_report", "2026-04-30",
           "효성중공업 IEEE PES T&D 2026: 데이터센터·신재생 전력 안정성을 강화하는 STATCOM, 차세대 데이터센터 핵심 전력 솔루션 SST(22.9kV 서브모듈)")
HYO_E = ("https://www.smarttoday.co.kr/ko-kr/articles/101702", "third_party_report", "2026-01-20",
         "효성중공업 스태콤 + 스켈레톤 슈퍼커패시터 결합 e-STATCOM 을 2027년까지 공동개발")

NODES = [
    Node("component:memory_interface_chip", "component", "메모리 인터페이스 칩 (DDR5 RCD · MRDIMM MRCD/MDB · PMIC · SPD hub — 모듈마다 붙는 칩)", "hbm"),
    Node("product:google_tpu_system", "product", "Google TPU 시스템 (자사 + 외부 판매·임대)", "hbm"),
    Node("component:mlb_pcb", "component", "고다층 MLB 기판 (가속기 보드·스위치 — 다층·Sequential 적층)", "hbm"),
    Node.company("company:isu_petasys", "ISU Petasys (KRX 007660, 비SEC)", "hbm", "007660", "KRX", "mid"),
]

EDGES = [
    Edge("component:server_dram_lpdram", "requires", "component:memory_interface_chip", [RMBS_Q3, SKH_OCP], "third_party_report",
         note="RDIMM 마다 RCD, MRDIMM 마다 MRCD + MDB — 비트가 아니라 모듈·채널 수에 비례"),
    Edge("component:memory_interface_chip", "offered_by", "company:rmbs", RMBS_Q3, "third_party_report", note="DDR5 RCD 가 Q3 2026 기록적 제품 매출을 이끎"),
    Edge("component:memory_interface_chip", "offered_by", "company:montage", RMBS_Q3, "technical_inference", note="RCD·MRCD 경쟁사 (SSE 상장 — 투자 범위 밖)"),
    Edge("bottleneck:dram_bit_supply", "mitigated_by", "component:memory_interface_chip", [MRVL_SX, SKH_OCP], "technical_inference",
         note="부족이 모듈당 고용량화(3DS 256GB)·MRDIMM·CXL 재배치를 부른다 — 칩 수요가 비트와 갈라진다 (추론)"),
    Edge("product:google_tpu_system", "offered_by", "company:googl", DCD_TPU, "third_party_report", note="외부 판매 매출 대부분 2027"),
    Edge("product:google_tpu_system", "implements", "component:hbm_stack", TNW_TPU, "technical_inference"),
    Edge("product:google_tpu_system", "implements", "component:mlb_pcb", ISU, "third_party_report"),
    Edge("company:avgo", "develops", "product:google_tpu_system", [TNW_TPU, MS_TPU], "third_party_report", note="고성능 변종 설계, 2031년까지 장기 공급 계약"),
    Edge("component:mlb_pcb", "offered_by", "company:isu_petasys", ISU, "third_party_report", note="TPU·스위치 MLB"),
    Edge("company:hyosung_hi", "develops", "component:sst", HYO_KPI, "third_party_report", note="22.9kV SST 서브모듈"),
    Edge("company:hyosung_hi", "develops", "component:grid_forming_inverter", [HYO_KPI, HYO_E], "third_party_report", note="데이터센터용 STATCOM, e-STATCOM(+스켈레톤 슈퍼커패시터) 2027년까지"),
    Edge("component:supercapacitor", "offered_by", "company:skeleton", HYO_E, "third_party_report", note="e-STATCOM 의 저장 소자"),
]

ALIASES = {
    "component:memory_interface_chip": ["RCD", "registered clock driver", "MRCD", "MDB", "MRDIMM", "PMIC", "SPD hub", "메모리 인터페이스 칩"],
    "product:google_tpu_system": ["TPU", "Ironwood", "TPU v8", "Sunfish", "Zebrafish", "구글 TPU"],
    "component:mlb_pcb": ["MLB", "multilayer board", "high layer count PCB", "고다층 기판"],
    "company:isu_petasys": ["ISU Petasys", "이수페타시스"],
}


def main() -> int:
    return apply(NODES, EDGES, "t1030", aliases=ALIASES)


if __name__ == "__main__":
    raise SystemExit(main())
