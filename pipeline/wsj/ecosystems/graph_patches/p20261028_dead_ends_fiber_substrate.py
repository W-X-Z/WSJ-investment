"""2026-10-28 그래프 보수 (ADR-0017): 상장사로 이어지지 않던 병목 11곳, 광섬유·게르마늄 사슬, 기판 공정장비, 현장 발전.

    python -m wsj.ecosystems.graph_patches.2026_10_28_dead_ends_fiber_substrate   (멱등: 이미 있는 노드·간선은 건너뛴다)

근거는 모두 원문을 열어 확인한 것이다. 기존 간선과 같은 출처를 다시 쓴 곳은 그 간선의 발췌를 그대로 옮겼다.
"""

from __future__ import annotations

from wsj.ecosystems.graph_patches import Edge, Node, apply

TF_FIBER = ("https://www.trendforce.com/presscenter/news/20261019-13275.html", "third_party_report", "2026-10-19",
            "global supply shortfall of 180 million fiber-kilometers in 2026; bend-insensitive fiber spot above 5x 2025 levels; utilization 92%")
INTROL = ("https://introl.com/blog/germanium-chokepoint-china-fiber-optic-supply-chain-2026", "third_party_report", "2026-02-27",
          "germanium dioxide is a dopant in every fiber's silica core; fiber optics consume roughly 30% of global germanium; China ~60% of production")
EVERTIQ_GE = ("https://evertiq.com/news/2025-11-10-china-suspends-ban-on-gallium-and-germanium-exports-to-the-us", "third_party_report", "2025-11-10",
              "China suspended its ban on gallium, germanium and antimony exports to the US until November 27, 2026; export licenses still required")
UDN_UMC = ("https://udn.com/news/story/7252/9840528", "third_party_report", "2026-10-27",
           "欣興董事會通過長交期設備預下訂單再增加約新台幣509億元，用於新建廠房並提升製程能力")
TF_EMIB = ("https://www.trendforce.com/news/2026/05/20/news-intel-says-emib-customers-back-substrate-prepayments-4-taiwan-and-2-japan-suppliers-reportedly-seek-commitments/",
           "third_party_report", "2026-05-20",
           "substrate supply remains extremely tight, with four suppliers from Taiwan and two from Japan requesting upfront commitments to secure capacity.")
OCP = ("https://www.opencompute.org/news/powering-the-next-era-of-ai-how-google-microsoft-and-nvidia-are-standardizing-and-accelerating-the-industry-transition-to-lvdc/",
       "official_issuer", None, None)
XENO = ("https://xenospectrum.com/en/china-memory-testing-hbm-equipment/", "third_party_report", None,
        "Advantest estimated the 2025 global memory tester market at $2.1 billion, with its own share at 61%")
ENKI = ("https://enkiai.com/data-centers/ai-data-center-energy-2026-the-grid-bypass-revolution", "third_party_report", None,
        "Oracle + Bloom Energy (Jul 2025): on-site solid oxide fuel cells at select data centers")
INNIO_ORDER = ("https://www.businesswire.com/news/home/20261022191376/en/Follow-on-Order-Brings-Orders-from-INNIO-Data-Center-Customer-to-1.72-GW-Further-Strengthening-INNIO%E2%80%99s-Data-Center-Backlog-and-Revenue-Visibility/",
               "official_issuer", "2026-10-22", "620 MW follow-on order of containerized Jenbacher J624 brings orders from a US data center customer to ~1.72 GW")

NODES = [
    Node("component:optical_fiber", "component", "광섬유·광케이블 (단일모드·굽힘 강화 BIF, 데이터센터 배선)", "optics"),
    Node("bottleneck:germanium_supply", "bottleneck", "게르마늄 공급 집중·중국 수출통제 (광섬유 코어 도펀트)", "optics"),
    Node("material:germanium", "material", "게르마늄·사염화게르마늄 (GeCl4, 광섬유 코어 도펀트)", "optics"),
    Node("equipment:substrate_process_equipment", "equipment", "기판·첨단패키징 공정장비 (진공 라미네이션·도포·건조·경화)", "hbm"),
    Node("equipment:memory_ate", "equipment", "메모리 테스터 (ATE, HBM·DRAM)", "hbm"),
    Node("material:inp_substrate_exchina", "material", "중국 밖 InP 기판 공급 (Sumitomo·JX)", "optics"),
    Node.company("company:yofc", "YOFC 长飞光纤 (SSE 601869, 비SEC)", "optics", "601869", "SSE", "large"),
    Node.company("company:taihan_fiberoptics", "Taihan Fiberoptics 대한광통신 (KOSDAQ 010170, 비SEC)", "optics", "010170", "KOSDAQ", "small"),
    Node.company("company:sterlite_tech", "Sterlite Technologies (NSE STLTECH, 비SEC)", "optics", "STLTECH", "NSE", "small"),
    Node.company("company:csun", "C Sun 志聖 (TWSE 2467, 비SEC)", "hbm", "2467", "TWSE", "mid"),
    Node.company("company:group_up", "Group Up 群翊 (TPEx 6664, 비SEC)", "hbm", "6664", "TPEx", "small"),
    Node.company("company:umicore", "Umicore (Euronext UMI, 비SEC)", "optics", "UMI", "Euronext", "mid"),
    Node.company("company:teck", "Teck Resources (TECK)", "optics", "TECK", "NYSE", "large", cik=886986, filer_type="40-F"),
]

EDGES = [
    # 광섬유 — 부족이 가격·장기계약으로
    Edge("bottleneck:fiber_supply", "mitigated_by", "component:optical_fiber", TF_FIBER, "third_party_report"),
    Edge("component:optical_fiber", "offered_by", "company:glw",
         ("https://www.sec.gov/Archives/edgar/data/0000024741/000002474126000273/glw-20261027xex99xq32026.htm", "official_issuer", "2026-10-27",
          "Optical Communications net sales $2,379M, up 44% YoY; Enterprise Networks +84%; four long-term multibillion-dollar agreements in Q3"),
         "official_issuer"),
    Edge("component:optical_fiber", "offered_by", "company:yofc",
         ("https://www.jiemian.com/article/14763704.html", "third_party_report", "2026-07-14",
          "长飞光纤 2026 上半年归母净利润预计 24~30 亿元 (+711%~914%); G.652.D 光纤从不到 20 元/芯公里涨到约 100 元"), "third_party_report"),
    Edge("material:fiber_preform", "offered_by", "company:yofc",
         ("https://govt.chinadaily.com.cn/s/202209/02/WS6357b1e2498ea274927a68de/yofc-enjoys-largest-global-market-share-for-6-years.html",
          "third_party_report", "2022-09-02", "YOFC enjoys largest global market share for 6 years (preform·fiber·cable)"), "third_party_report"),
    Edge("component:optical_fiber", "offered_by", "company:fujikura",
         ("https://www.datacenterdynamics.com/en/news/fujikura-to-triple-optical-fiber-production-as-part-of-2bn-investment/", "third_party_report", "2026-03-19",
          "a maximum of 300 billion yen ($1.9bn) to increase production capacity up to approximately three times the current level"), "third_party_report"),
    Edge("component:optical_fiber", "offered_by", "company:furukawa_electric",
         ("https://finance.technews.tw/2026/08/05/furukawa-electric-to-expand-fiber-optic-output-in-japan-us-brazil-india/", "third_party_report", "2026-08-05",
          "古河電氣工業擬在日本、美國、巴西、印度投資 1,000 億日圓，倍增光纖產能"), "third_party_report"),
    Edge("component:optical_fiber", "offered_by", "company:taihan_fiberoptics",
         ("https://www.job-post.co.kr/news/articleView.html?idxno=234998", "third_party_report", "2026-10-28",
          "대한광통신은 광섬유와 광케이블을 통신망·데이터 전송 인프라에 공급"), "third_party_report"),
    Edge("component:optical_fiber", "offered_by", "company:sterlite_tech",
         ("https://www.investywise.com/?p=122260", "third_party_report", "2026-10-23",
          "STL Q2 FY'27 revenue ₹2,529 crore, up ~145% YoY, on hyperscaler data center demand"), "third_party_report"),
    # 광섬유의 원료 — 게르마늄
    Edge("bottleneck:germanium_supply", "creates_bottleneck", "bottleneck:fiber_supply", INTROL, "third_party_report"),
    Edge("bottleneck:germanium_supply", "mitigated_by", "material:germanium", EVERTIQ_GE, "third_party_report", note="중국 밖 공급원이 수혜 — 유예 만료 2026-11-27"),
    Edge("material:germanium", "offered_by", "company:umicore",
         (INTROL[0], "third_party_report", INTROL[2], "Umicore's Olen recycling facilities supply 30% of U.S. germanium metal imports and 47% of germanium dioxide imports"),
         "third_party_report"),
    Edge("material:germanium", "offered_by", "company:teck",
         (INTROL[0], "third_party_report", INTROL[2], "Teck refines germanium at its Trail smelter, supplying 46% of U.S. germanium dioxide imports"), "third_party_report"),
    # 기판 생산능력 — 기판사와 증설 장비
    Edge("bottleneck:substrate_capacity", "mitigated_by", "component:package_substrate", TF_EMIB, "third_party_report"),
    Edge("bottleneck:substrate_capacity", "mitigated_by", "equipment:substrate_process_equipment", UDN_UMC, "third_party_report"),
    Edge("equipment:substrate_process_equipment", "offered_by", "company:group_up",
         ("https://wantrich.chinatimes.com/news/20261021900219-420101", "third_party_report", "2026-10-21",
          "群翊 塗佈·壓合·烘烤設備; 在手訂單約60億元, 交期排到2027年底; FOPLP·TGV玻璃基板製程設備"), "third_party_report"),
    Edge("equipment:substrate_process_equipment", "offered_by", "company:csun",
         ("https://news.cnyes.com/news/id/6629490", "third_party_report", "2026-10-13",
          "志聖 1-9月營收 80.23億元 (+84.2%), 深化先進封裝與先進PCB布局, 台積電供應鏈"), "third_party_report"),
    # 상장사로 이어지지 않던 병목 — 라벨이 이미 말하던 공급사로 잇는다 (같은 출처의 발췌)
    Edge("bottleneck:abf_single_source", "mitigated_by", "material:abf",
         ("https://www.trendforce.com/news/2026/05/08/news-ajinomoto-ramps-chip-packaging-push-with-%c2%a51-2b-land-buy-for-new-plant-in-2032-abf-margins-top-50-on-ai-boom/",
          "third_party_report", "2026-05-08", "the company is said to hold more than 95% of the global ABF market share"), "third_party_report"),
    Edge("bottleneck:msb_supply", "mitigated_by", "material:micro_solder_ball",
         ("https://m.stock.naver.com/research/company/94604", "third_party_report", "2026-07-28",
          "마이크로솔더볼은 일본의 Senju Metal과 과점 구조 ... 공급이 수요 대비 부족한 상황"), "third_party_report"),
    Edge("bottleneck:tcb_supplier_concentration", "mitigated_by", "equipment:tc_bonder",
         ("https://www.techinvestments.io/p/hbmdie-bonding-semicap-outlook", "third_party_report", None,
          "SK Hynix: historically Hanmi, ASMPT took large share; Micron: Hanmi dominant; Samsung relies on in-house SEMES"), "third_party_report"),
    Edge("bottleneck:muf_single_source", "mitigated_by", "material:muf_lmc",
         ("https://dealsite.co.kr/articles/119413", "third_party_report", "2024-03-15",
          "일본 나믹스가 SK하이닉스 MR-MUF 소재를 독점 공급; 독점 계약으로 신규 진입 쉽지 않다는 분석"), "third_party_report"),
    Edge("bottleneck:hbm_probe_card_supply", "mitigated_by", "component:dram_probe_card",
         ("https://www.fool.com/earnings/call-transcripts/2026/04/29/formfactor-form-q1-2026-earnings-transcript/", "official_issuer", "2026-04-29",
          "we expect to be a leading supplier to all 3 DRAM manufacturers for these at speed DRAM test"), "official_issuer"),
    Edge("bottleneck:memory_ate_concentration", "mitigated_by", "equipment:memory_ate", XENO, "third_party_report"),
    Edge("equipment:memory_ate", "offered_by", "company:advantest", XENO, "third_party_report"),
    Edge("equipment:memory_ate", "offered_by", "company:ter",
         ("https://www.nasdaq.com/articles/ters-memory-test-sales-hit-128m-growth-thesis-strengthening", "third_party_report", "2026-01-22",
          "Teradyne memory test sales hit $128M (article title)"), "third_party_report"),
    Edge("bottleneck:cpo_engine_yield", "mitigated_by", "equipment:photonics_wafer_prober",
         ("https://www.trendforce.com/insights/cpo-testing-market-opportunities", "third_party_report", "2026-07-20",
          "OE-level test: full-flow calibration, DC, high-speed, optical loop-back and S-parameter tests confirm Known Good Optical Engines (KGOE)"),
         "third_party_report"),
    Edge("bottleneck:cpo_engine_yield", "mitigated_by", "equipment:laser_burn_in",
         ("https://www.aehr.com/2026/03/aehr-receives-follow-on-order-for-fully-automated-wafer-level-burn-in-systems-powering-ai-optical-i-o-and-data-center-interconnects/",
          "official_issuer", "2026-03-03", "ultra-high-power FOX-XP wafer-level test and burn-in for SiPh ICs for data center optical interconnects and optical I/O"),
         "official_issuer"),
    Edge("bottleneck:mlcc_supply", "mitigated_by", "component:mlcc_ai",
         ("https://www.trendforce.com/presscenter/news/20260706-13136.html", "third_party_report", "2026-07-06",
          "AI server upgrades and custom accelerators boost demand for high-capacitance MLCCs; Q4 2026 critical period for shortage"), "third_party_report"),
    Edge("bottleneck:copper", "mitigated_by", "component:dc_busbar", OCP, "technical_inference", note="낮은 전압의 대전류 → 버스바 수요 (추론)"),
    Edge("bottleneck:copper", "mitigated_by", "tech:sidecar", OCP, "technical_inference", note="전압을 올리면 같은 전력에 구리가 준다 (추론)"),
    Edge("bottleneck:china_inp_export_control", "mitigated_by", "material:inp_substrate_exchina",
         ("https://www.sec.gov/Archives/edgar/data/1051627/000121390026002690/ea027235801ex99-1_axtinc.htm", "official_issuer", "2026-01-08",
          "Q4 2025 revenue cut: fewer indium phosphide export control permits issued by China's Ministry of Commerce"), "technical_inference",
         note="중국 허가가 줄면 중국 밖 기판 공급사로 수요가 옮겨간다 (추론). AXT 는 중국 생산이라 피해 쪽"),
    Edge("material:inp_substrate_exchina", "offered_by", "company:sumitomo_electric",
         ("https://www.trendforce.com/news/2026/06/16/news-jx-advanced-metals-to-invest-jpy-120b-through-fy2030-expand-inp-capacity-up-to-10x-as-cpo-demand-accelerates/",
          "third_party_report", "2026-06-16", "AXT and Sumitomo together account for nearly 80% of global InP substrate production"), "third_party_report"),
    Edge("material:inp_substrate_exchina", "offered_by", "company:jx_metals",
         ("https://wwwcdn.furuchi.co.jp/english/newsrelease/fy2026/20260616_02.html", "official_issuer", "2026-06-16",
          "JX to invest up to JPY120bn to increase InP substrate production capacity ~7 to 10 times"), "official_issuer"),
    # 계통연계 대기열 — 현장 발전
    Edge("bottleneck:interconnection_queue", "mitigated_by", "component:recip_gas_engine", INNIO_ORDER, "official_issuer"),
    Edge("bottleneck:interconnection_queue", "mitigated_by", "component:fuel_cell", ENKI, "third_party_report"),
]

NATIVE = {"company:yofc": "长飞光纤", "company:taihan_fiberoptics": "대한광통신", "company:csun": "志聖", "company:group_up": "群翊"}
ALIASES = {
    "bottleneck:fiber_supply": ["fiber spot prices", "optical fiber prices", "fiber prices", "fibre shortage", "fiber-kilometers"],
    "component:optical_fiber": ["optical fiber", "optical fibre", "single-mode fiber", "bend-insensitive fiber", "fiber optic cable"],
    "material:germanium": ["germanium", "germanium tetrachloride", "gecl4"],
    "bottleneck:germanium_supply": ["germanium export", "germanium ban"],
    "equipment:substrate_process_equipment": ["substrate equipment", "lamination equipment", "long-lead equipment"],
    "bottleneck:substrate_capacity": ["abf substrate", "ic substrate shortage", "substrate shortage"],
    "equipment:memory_ate": ["memory tester", "memory test"],
}
NODE_TERMS = {
    "component:optical_fiber": ["光纤", "光纖", "광섬유", "光ファイバ"],
    "material:germanium": ["锗", "鍺", "게르마늄", "ゲルマニウム"],
    "equipment:substrate_process_equipment": ["載板設備", "壓膜", "长交期设备", "長交期設備"],
}


def main() -> int:
    return apply(NODES, EDGES, "x-si", native=NATIVE, aliases=ALIASES, node_terms=NODE_TERMS)


if __name__ == "__main__":
    raise SystemExit(main())
