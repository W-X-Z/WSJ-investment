# JUDGE: memory_inference_2025 blind replay (as of 2025-09-30)

**Inputs used:** only the three raw files below. No web search was run and no other repository file was opened.

| Notation | Source file |
|---|---|
| A1–A45 | Row # in `raw/A_papers.md`. Appendix papers are cited by arXiv id. |
| P01–P22, M01–M19, U01–U09 | `raw/B_platform_model_hiring.md` |
| C-M*, C-O*, C-P*, C-X* | `raw/C_standards_conf_filings.md` |

**Date rule.** Every row cited here is dated on or before 2025-09-30. Material that the files themselves mark as post-cutoff was not used:
- the "Excluded after fetch" items;
- the later title of A5;
- the Oct-22 update to U09;
- arXiv IDs from 2510 onward.

Some rows have pages that were edited after the cutoff: P06, P18, P19 and U07 (marked †), and C-P2. For these, only content from the original date was used. None of them is the only support for any chain step.

**How rows were assigned to source types (used for promotion):**

| Source type | Rows |
|---|---|
| paper | File A |
| platform_release | P rows, plus C-P2 (NVIDIA architecture blog) |
| model_release | M rows |
| usage disclosure | U rows |
| standard | C-M1, C-M2, C-M6 (spec MoU), C-O2, C-O3, C-O5, C-O6, C-O7, C-P4 |
| conference | C-M3, C-M4, C-M5, C-M9, C-M16, C-O1, C-O4, C-O8, C-O10, C-O11, C-O12, C-P1, C-P5, C-P6, C-X1, C-X2 |
| filing (including primary company releases) | C-M7, C-M8, C-M10, C-M11, C-O9, C-O13–C-O15, C-P3, C-P7, C-P9–C-P12, C-X3–C-X7 |
| price/market report | C-M12–C-M15, C-P8 |

---

## 1. Weak signals

**Promotion rule:** a signal is promoted if it appears in 2 or more source types, or in 3 or more rows.

**"New"** means the signal was first seen within about 12 months of the cutoff (2024-10 or later).

| ID | Signal | Source types → rows | Earliest dated row | New (≤12m)? | Promoted? |
|---|---|---|---|---|---|
| S01 | Inference stacks build in **KV-cache tiers below HBM**: host DRAM/LPDDR, then local NVMe, then networked or object store | platform: P01, P02, P03, P06, P08, P09, P13, P14, P15, P16, P18, P19, P20, P21 · paper: A1, A2, A5, A6, A13 (A17 is a counter-signal) · model: M06 · usage: U04 · conference: C-M4 · filing: C-M7 | P01, 2025-03-18 | Partly. The mechanism dates from 2023 (A1 note). Being the default in NVIDIA and open-source reference stacks is new (Mar–Sep 2025). | **Yes** (6 types, 25+ rows) |
| S02 | **Retained KV is sold as a product**: cached-input discounts of 75–90%, implicit caching on by default, TTL up to 1 h, tiered long-context pricing | model: M02, M05, M06, M15, M17 · platform: P11, P16, P19 | M02, 2025-04-14 | Partly. 50% discounts existed before (M02: "from 50%"). The 75–90% discounts, implicit default and 1 h TTL are new. | **Yes** |
| S03 | **Long-horizon and coding agents** (multi-turn, hours-long sessions, prefix-cache hit above 90%) are the fastest-growing workload | model: M03, M06, M07, M10, M11, M15, M16, M19 · usage: U05, U06 · platform: P08, P16, P18 · paper: A10, A11, A13 | M03, 2025-04-16 | Yes | **Yes** |
| S04 | **Context of 1M–10M tokens and reasoning outputs of 32K–128K tokens** per request | model: M01, M02, M04, M07, M11, M13, M17 · platform: P04, P12, P15 · paper: A7, A12, A14, A15 | M01 / P04, 2025-04-05 | Yes | **Yes** |
| S05 (counter) | **Techniques that shrink KV**: FP8 or 2-bit KV, pruning of chain-of-thought KV, hybrid-linear and sparse attention, sliding windows, FP4 weights | paper: A5, A9, A14, A15 · platform: P04, P12, P17, P21, P22 · model: M12, M18 | P04, 2025-04-05 | Partly. KV quantization dates from 2024. Hybrid-linear attention in production models is new. | **Yes** |
| S06 | **Inference token volume grows faster than per-token cost falls**; buyers are capacity-constrained | usage: U01, U02, U03, U04, U05, U06 · model: M08, M14, M18 · platform: P05 · filing: C-M7, C-X6 | U01, 2025-04-30 | Yes | **Yes** |
| S07 | **Non-HBM DRAM is tight**: HBM crowds out conventional DRAM, contract prices turn up, and CSPs are "flexible on price" | filing: C-M10, C-M11, C-M7 · price report: C-M13, C-M14 | C-M10, 2025-03-20 | Yes | **Yes** |
| S08 | **LPDDR moves into servers**: SOCAMM modules, and Grace LPDDR5X used as a KV/weight tier | conference: C-M3, C-M4 · filing: C-M7, C-M10 · platform: P15, P20, P21 · usage: U07 · price report: C-M14 · standard: C-M2 (no server wording) | C-M3, 2025-03-18 | Yes | **Yes** |
| S09 | **Enterprise QLC SSD becomes the persistent KV/context tier and replaces HDD**; NAND prices turn up | platform: P01, P02, P16, P18, P19 · usage: U04, U07 · conference: C-M3, C-M5 · filing: C-M7, C-M10 · price report: C-M13, C-M15 · paper: A1, A17 (counter) | P01 / C-M3, 2025-03-18 | Yes. Substitution driven by the HDD shortage (C-M15) and SSD in the KV data path are both new. | **Yes** |
| S10 | **HBM4**: 2,048-bit interface, 16-high stacks, logic base die made at a foundry, premium above 30% | standard: C-M1 · filing: C-M7, C-M8, C-M10 · price report: C-M12 · conference: C-X1 · paper: A7 | C-M10, 2025-03-20 | No (iteration) | **Yes** |
| S11 | **Hybrid and wafer bonding; 3D DRAM-on-logic** | paper: A8, A18, A40 · conference: C-M9, C-X2 | C-X2, 2025-02-28 | Partly (long-dated) | **Yes** (timing is far out) |
| S12 | **High Bandwidth Flash**: a NAND tier inside the package | standard/MoU: C-M6 · conference: C-M5 (a recap of the same MoU) | C-M6, 2025-08-06 | Yes | Yes by the rule, but only one underlying event |
| S13 | **CXL memory as a KV spill tier** | paper: A5 (+ appendix 2508.11477) · conference: C-M5 | C-M5, 2025-08-11 | Partly | Yes by the rule, but thin and absent from every platform row |
| S14 | **Disaggregated prefill/decode plus wide expert parallelism (EP)**, moving KV and tokens over RDMA (about one NIC per GPU) | platform: P01, P05, P07, P08, P13, P14, P16, P20 · paper: A2, A3, A16 (A4 is a counter-signal) · filing: C-X4 · conference: C-O11 · usage: U07 | P01, 2025-03-18 | Partly. Disaggregation dates from 2024; it became the production default in 2025. | **Yes** |
| S15 | **The rack-scale scale-up domain becomes the serving unit**, and open scale-up fabrics compete (UALink, SUE, NVLink Fusion, Tomahawk Ultra) | platform: P10, P11, P21 · standard: C-O6, C-O7, C-P4 · conference: C-O8, C-O11 · filing: C-O9, C-O15, C-X4 · usage: U07 · paper: A7, A19 | A19, 2025-02-06 | Yes | **Yes** |
| S16 | **Optical circuit switching (OCS) and reconfigurable photonic fabrics** replace electrical switch tiers | paper: A19, A20, A21, A22, A23, A27 (+ appendix 2507.18889) · conference: C-O10 (adjacent) | A19, 2025-02-06 | Yes | Yes by recurrence, but nearly all evidence is papers |
| S17 | **Co-packaged optics (CPO) with external laser sources (ELSFP)** and silicon-photonics engines | conference: C-O1, C-O4, C-O10, C-X1, C-X2 · standard: C-O2 · filing: C-O9 · paper: A24, A25, A26, A28 | C-O2, 2025-03-12 | Yes | **Yes** |
| S18 | **Ramp of 1.6T / 200G-per-lane pluggables**, with 448G next | standard: C-O2, C-O5 · conference: C-O4 · filing: C-O13, C-O14, C-X4 · usage: U07 | C-O2, 2025-03-12 | No (iteration; 448G is new) | **Yes** |
| S19 | **DSPs displaced at short reach** (LPO, DSP-free coherent, active or passive copper) | standard: C-O2, C-O3 · paper: A24, A25, A28 · filing: C-O9, C-O15 | C-O2, 2025-03-12 | Partly | **Yes** (direction contested) |
| S20 | **Scale-across**: multi-site AI clusters that need data-center interconnect (DCI) | conference: C-O12 · standard: C-O2 (800ZR at ECOC) · usage: U09 | C-O12, 2025-08-22 | Yes (as a label) | Yes by the rule, but no numbers |
| S21 | **Synchronous AI-load power swings** cause grid oscillation and call for power stabilization and buffering | paper: A29, A30, A31, A32, A33, A34 · filing: C-P10 · usage: U01 | A34, 2025-01-28 | Yes | **Yes** (paper-heavy) |
| S22 | **±400/800 VDC distribution, 1 MW racks, solid-state transformers (SST), SiC/GaN** | conference: C-P1, C-P5, C-X1, C-X2 · platform: C-P2 · filing: C-P3, C-P10 · standard: C-P4 · paper: A32, A34 | C-P1, 2025-04-29 | Yes | **Yes** |
| S23 | **Liquid cooling becomes the default** in AI halls | price report: C-P8 · usage: U04, U07, U09 · conference: C-O1, C-P1, C-P4, C-P5 · filing: C-P9, C-P12 · paper: A35, A36, A38 | A38, 2024-08-25 (in-window: C-P1, 2025-04-29) | No (a step-up in penetration) | **Yes** |
| S24 | **Cooling beyond cold plates** (in-silicon microfluidics, two-phase, ECAM) and thermal limits of 3D stacks | filing/company: C-P7 · conference: C-P6, C-X2 · paper: A37, A39, A40, A41 | A37, 2025-02-25 | Yes | **Yes** (long-dated) |
| S25 | **GW-scale contracted capacity** and a backlog in power generation | usage: U01, U04, U08, U09 · filing: C-P11, C-X6, C-X7 · conference: C-O12 | U01, 2025-04-30 | No (the scale is new) | **Yes** |
| S26 | **Glass cores and glass photonic interposers** at panel scale | paper: A41, A42 · conference: C-X2 | C-X2, 2025-02-28 | Partly | Yes by the rule, but no filing |
| S27 | **Test escapes, silent data corruption (SDC) and chiplet test cost** | paper: A43, A44, A45 | A44, 2025-03-18 | No | Yes by recurrence, but a single source type |
| S28 | **CoWoS at 9.5 reticles, SoW-X, integrated voltage regulators (IVR)** | conference: C-X1 | C-X1, 2025-04-23 | Partly | No |
| S29 | **Off-peak and batch pricing to raise utilization** | model: M08, M14 | M08, 2025-07-07 | Yes | No (2 rows, 1 type) |
| S30 | **SmartNIC-offloaded KV fetch** | paper: A2 | A2, 2025-09-21 | Yes | No |
| S31 | **Edge/client inference** (gpt-oss-20b in 16 GB) | model: M12 | M12, 2025-08-05 | Yes | No |
| S32 | **Hiring for KV-cache and storage-for-LLM roles** | none dated (B §3) | — | — | No (no admissible evidence) |

---

## 2. Mechanism answers (promoted signals)

| Signal | (a) If it goes 10x, what gets bound or scarce | (b) What becomes worthless | (c) Where pricing power moves | (d) Who absorbs the cost |
|---|---|---|---|---|
| S01 KV tiers below HBM | Host DRAM/LPDDR per GPU, NVMe bandwidth per GPU (GDS), RDMA NICs, CPU–GPU link bandwidth (C2C/PCIe) | GPU-hours spent re-running prefill; serving setups that rely on HBM alone | DRAM/NAND suppliers, and whoever owns the KV-movement layer (NVIDIA Dynamo/NIXL, Grace C2C) | Cloud and neocloud capex (memory and storage BOM per GPU), partly passed to users through long-context price tiers (M17) |
| S02 Retained KV as a product | GB-hours of retained KV (capacity × TTL) | Pricing built mainly on uncached prefill | Providers with the largest and cheapest retention tiers, and the memory vendors behind them | Providers today: the 75–90% discounts are margin they give up |
| S03 Long-horizon agents | Session state kept for hours (KV, containers, memory files); CPU sandbox fleets for agent RL | Assumptions of stateless chat serving; cache TTLs measured in minutes | Memory and storage suppliers; agent platforms with high cache hit rates | Model providers selling flat-fee seats or quotas (Claude Code, Codex) |
| S04 1M–10M context | KV bytes per request, hence HBM capacity per GPU, KV spread across GPUs, and scale-up bandwidth | 80 GB-class GPUs for frontier long-context serving | HBM-rich rack systems and HBM makers | API users, through long-context surcharges (M17: 2x above 128K) |
| S05 KV shrinking (counter) | Compute for quantization and indexers; HBM bandwidth still binds | Part of the DRAM/SSD capacity bought per token | Model and algorithm owners. Memory vendors lose leverage if bytes per token fall faster than tokens grow. | Memory makers (fewer bits per token), unless the savings are spent again on more context or batch (P04, P21) |
| S06 Token volume beats efficiency | Total installed capacity: accelerators, memory, power | API price per token (M18 cuts it by 50% or more) | Owners of scarce capacity and of bottleneck components | Hyperscaler free cash flow (C-X6: about $88B of capex in one quarter) |
| S07 Non-HBM DRAM tight | DRAM wafer starts (diverted to HBM); legacy DDR4 lines | The price floor for consumer memory | DRAM makers (CSPs are "flexible on price") | PC, mobile and consumer OEMs first (C-M14), then CSPs |
| S08 LPDDR in servers | LPDDR5X dies and SOCAMM module capacity qualified with NVIDIA | DDR5 RDIMM on Grace-class nodes | The few LPDDR suppliers qualified with NVIDIA (Micron first, C-M3) | Mobile OEMs competing for LPDDR (LPDDR4X up more than 10%) |
| S09 QLC eSSD / HDD substitution | NAND wafer output after cuts of more than 10%, high-layer QLC dies, controller substrates | Nearline HDD in the warm tiers of CSPs | NAND makers with high-capacity eSSD (SK Group, Sandisk, Kioxia) | CSPs (price increases; Sandisk +10%) |
| S10 HBM4 | TSV and stacking capacity, foundry N12/N3 base-die wafers, CoWoS | The HBM3E premium; HBM lines that fail qualification | SK hynix (more than 50% of HBM4, by estimate) and TSMC (base die) | GPU/ASIC vendors through the >30% premium, then their customers |
| S11 Hybrid bonding / 3D DRAM | Hybrid and wafer-bonding tools; bonded-wafer yield | Eventually, MR-MUF and TC bonding at the high end | Bonding-tool makers, and memory makers that get yield right | Memory-maker capex |
| S12 HBF | NAND-in-package bandwidth; CBA wafer bonding | Part of HBM's capacity role for weights that are mostly read | Sandisk and SK hynix, if their spec becomes the standard | Accelerator vendors' package area and power budget |
| S13 CXL for KV | CXL controllers and expanders, and the DDR behind them | Some HBM capacity per long-context request | CXL controller vendors | Server OEMs and operators |
| S14 Disaggregated P/D + wide EP | RDMA NICs per GPU, scale-out switch ports, cross-node bandwidth | Serving everything on a single monolithic node | NIC and switch vendors (NVIDIA networking +98%) | Operators, as networking's share of capex rises |
| S15 Rack-scale scale-up | Scale-up switch ASICs, retimers, AEC/copper, rack power and liquid cooling | The 8-GPU node as the unit; RDMA inside the rack (P10) | Whoever owns the scale-up protocol: NVIDIA today; Broadcom, Astera Labs or Marvell if open specs win | Hyperscalers through rack prices; custom-XPU vendors through NVLink Fusion licensing |
| S16 OCS | Optical circuit switches and fast-switching photonics | High-radix electrical packet switches | OCS makers | No buyer disclosed (papers only) |
| S17 CPO + ELSFP | High-power CW lasers, fiber attach, silicon-photonics engine capacity (TSMC COUPE, SPIL) | Pluggable modules on the switch side, and their DSPs | Switch-ASIC owners and laser makers; module assemblers lose | Pluggable-module makers and optical-DSP vendors |
| S18 1.6T pluggables | EML and silicon-photonics lasers, 200G DSPs, module test capacity | 400G/800G-generation modules | Laser-chip makers | Hyperscalers (optics' share of networking capex) |
| S19 DSP displacement | Linear drivers and TIAs, AEC chips, copper reach | DSPs in short-reach links | Analog and AEC suppliers | DSP vendors' margins |
| S20 Scale-across | Coherent DCI optics; long-haul fiber | Scaling within one site only | DCI and coherent-optics vendors | Operators that spread across sites |
| S21 Power swings | Fast energy buffers, grid damping, GPU power-smoothing | UPS designs sized for slow-moving loads | Power-electronics and storage suppliers; utilities, which set interconnection terms | DC operators (stabilization capex), or GPU throughput (power capping) |
| S22 ±400/800 VDC | SiC/GaN devices, SSTs, DC protection, sidecar power racks | In-rack AC PSUs, 54 V busbars, about 45% of the copper | Power-semiconductor makers and electrical majors (Eaton, Vertiv) | DC builders up front, recovered through about 5% better efficiency |
| S23 Liquid cooling | CDUs, cold plates, quick disconnects, chillers | Air-cooled AI halls | CDU and thermal vendors | DC operators |
| S24 Beyond cold plates | Process steps for etched-silicon cooling; two-phase fluids | Cold plates, within about 5 years (C-P7) | Chip and package owners | Cold-plate vendors |
| S25 GW capacity | Generation (gas turbines), transformers, interconnection, powered land | Sites without power | Power-equipment owners and owners of powered land | Hyperscalers and AI labs (capex); vendor financing (NVIDIA, up to $100B) |
| S26 Glass | Glass panels and TGV processing | Silicon interposers at the largest sizes | Glass-substrate makers | OSATs and packagers |
| S27 Test escapes | System-level test, burn-in, in-field detection | — | Test-equipment makers | Chip vendors |

---

## 3. Theses (ranked by conviction)

### Thesis 1: Inference state spills out of HBM into conventional server DRAM and LPDDR

```json
{
  "thesis_key": "inference_state_commodity_dram",
  "title": "Inference state spills out of HBM: conventional server DRAM and LPDDR become AI-attached",
  "statement": "Between April and September 2025 every major inference stack (NVIDIA Dynamo, llm-d, SGLang HiCache, TensorRT-LLM 1.0, LMCache) made host DRAM/LPDDR a formal KV-cache tier, and API providers started selling retained KV (75-90% cached-input discounts, implicit caching by default, 1 h TTL) to long-horizon agents whose sessions grew from 7 h to 30 h+. KV demand scales with users x context x retention time (about 40 GB per user at 128K on Llama-3-70B), not with FLOPs, so each added GPU pulls more non-HBM DRAM: SGLang sizes the host pool at 2x the GPU KV pool, GH200 pairs 96 GB HBM with 480 GB LPDDR, and NVL72 racks pool 14 TB. This lands on a DRAM supply already crowded out by HBM (Micron: 'HBM ramp constraining non-HBM DRAM supply'), and the price data has turned: conventional DRAM contract +8-13% for 4Q25 with US CSPs 'more flexible on price', DDR4 nearly doubled in 3Q25, Micron Cloud Memory BU +214% YoY with gross margin guided to 51.5%. The market still frames memory as 'HBM = structural AI, everything else = cyclical commodity'; the chain says the commodity bits are becoming AI-attached too, which argues for a longer and less price-sensitive upcycle at SK hynix, Samsung and Micron.",
  "chain": [
    {"step": "Demand driver: inference tokens and long-horizon agent sessions grow faster than per-token efficiency (Google 9.7T -> 480T -> 980T monthly tokens; Microsoft 5-7x; Claude Code usage >10x in 3 months; agent autonomy 7 h -> 30 h+).", "rows": ["U01", "U02", "U03", "U04", "U05", "M06", "M16", "M19"]},
    {"step": "Requirement: retained KV state scales with users x context x retention (about 40 GB/user at 128K, linear in users; 1M-10M contexts; cache TTL up to 1 h; >90% prefix-cache hit in agentic coding).", "rows": ["P15", "P04", "M01", "M02", "M05", "M06", "M13", "M15", "M17"]},
    {"step": "Bottleneck moves to the capacity tier just below HBM: reference stacks make host DRAM/LPDDR a formal KV tier (HiCache host pool 2x the GPU KV pool, TTFT -80%; TRT-LLM 1.0 host-memory mapping on GB200; KV capacity gates decode throughput, batch 1,408 vs 768 = -10%).", "rows": ["P01", "P08", "P09", "P16", "P20", "P21", "A1", "A6", "A13"]},
    {"step": "Component: server DRAM plus LPDDR5X/SOCAMM on Grace-class nodes (SOCAMM in volume for GB300; SK hynix to supply a server LPDDR module within 2025; 14 TB pooled memory per NVL72 rack).", "rows": ["C-M3", "C-M7", "C-M10", "U07"]},
    {"step": "Supply/price: HBM ramp constrains non-HBM DRAM; 2Q25 DRAM revenue +17.1% QoQ with DDR4 shortage; 4Q25 conventional DRAM contract +8-13%, LPDDR4X >+10%; US CSPs to sharply increase 2026 procurement.", "rows": ["C-M10", "C-M13", "C-M14"]},
    {"step": "Companies: Micron Cloud Memory BU $4,543M (+214% YoY), FQ1-26 GM guide 51.5%; SK hynix record 41% OP margin with investment pulled forward; Samsung 32.7% DRAM share.", "rows": ["C-M11", "C-M7", "C-M13"]}
  ],
  "novelty": "new_structure",
  "novelty_reason": "KV offload was a 2023-24 research idea (A1 note). In Mar-Sep 2025 it became default code in NVIDIA's and the open-source reference stacks (P01, P16, P19, P20) and a priced API product (M02, M05, M06, M15). That changes DRAM attach per GPU structurally. The 4Q25 contract-price turn (C-M14) is the new data that shows it reaching commodity DRAM.",
  "what_market_misses": "Memory is priced as 'HBM structural, conventional DRAM cyclical', but inference KV tiering and server LPDDR are making conventional DRAM bits AI-attached, so the non-HBM upcycle may be longer and less price-sensitive than a normal commodity cycle.",
  "beneficiaries": [
    {"company": "SK hynix", "ticker/exchange": "000660 / KRX (KOSPI)", "role": "primary", "why": "Largest DRAM share (38.7%, +25.8% QoQ); starting a server LPDDR module in 2025; record 41% OP margin; also exposed to eSSD (Thesis 2)."},
    {"company": "Micron Technology", "ticker/exchange": "MU / Nasdaq", "role": "primary", "why": "First SOCAMM in volume for GB300; Cloud Memory BU +214% YoY; GM guided +~580 bp QoQ to 51.5%; stated non-HBM DRAM supply constraint."},
    {"company": "Samsung Electronics", "ticker/exchange": "005930 / KRX (KOSPI)", "role": "primary", "why": "32.7% DRAM share. DRAM revenue grew less than SK hynix's (+13.7% vs +25.8%), which suggests a lower HBM mix, so a conventional-DRAM price turn is its biggest lever (inference). No primary Samsung data in the files."}
  ],
  "losers": [
    {"company": "PC / smartphone / consumer-device OEMs (e.g. HP Inc)", "ticker/exchange": "HPQ / NYSE", "why": "C-M14 says suppliers prioritise server DRAM/HBM and PC/mobile/consumer supply is squeezed; memory BOM rises with weaker pass-through."},
    {"company": "GPU prefill recompute (not a listed company)", "ticker/exchange": "n/a", "why": "Cached KV replaces recomputation (P01, P06, P16), so less GPU time is spent on prefill per agent turn."}
  ],
  "drivers": [
    {"metric": "4Q25 conventional DRAM contract price QoQ (TrendForce)", "latest": "+8-13% (incl. HBM +13-18%); LPDDR4X >+10%; DDR4 nearly doubled in 3Q25", "row": "C-M14 (2025-09-24)"},
    {"metric": "Global DRAM revenue", "latest": "$31.63B in 2Q25, +17.1% QoQ", "row": "C-M13"},
    {"metric": "Micron Cloud Memory BU revenue / FQ1-26 GM guide", "latest": "$4,543M (+214% YoY, +34% QoQ) / 51.5%; revenue guide $12.5B +/-0.3B", "row": "C-M11 (2025-09-23)"},
    {"metric": "Micron Core Data Center BU (counter-driver)", "latest": "$1,577M, -23% YoY", "row": "C-M11"},
    {"metric": "SK hynix operating margin", "latest": "41% (2Q25, record)", "row": "C-M7"},
    {"metric": "Host-DRAM KV pool vs GPU KV pool in reference config", "latest": "2x (SGLang --hicache-ratio 2)", "row": "P16"},
    {"metric": "KV per user at 128K (Llama-3-70B)", "latest": "about 40 GB, linear in users", "row": "P15"},
    {"metric": "Google monthly tokens processed", "latest": "980T (Jul-2025), about 2x in two months", "row": "U03"},
    {"metric": "Agent autonomy / cache TTL / cached-input discount", "latest": ">30 h / 1 h / 75-90%", "row": "M19, M06, M02, M15"}
  ],
  "first_signal": {"metric": "Micron FQ1-26 non-GAAP GM at or above the 51.5% guide with DRAM ASP up QoQ and Cloud Memory BU growing QoQ; SK hynix 3Q25 reporting conventional DRAM ASP up and server LPDDR module shipments started", "where": "Micron 8-K Ex.99.1 (Dec 2025); SK hynix 3Q25 newsroom release (late Oct 2025)", "expected_by": "2025-12-31"},
  "falsifiers": [
    {"what": "SK hynix 3Q25 results show conventional DRAM ASP flat/down QoQ, or the server LPDDR module slips into 2026", "due": "2025-11-15"},
    {"what": "Two or more of Alphabet/Meta/Microsoft/Amazon guide 2026 capex flat or down on 3Q25 calls", "due": "2025-11-07"},
    {"what": "Micron FQ1-26 revenue below $12.2B (guide low end) or non-GAAP GM below 50%", "due": "2025-12-31"},
    {"what": "TrendForce 1Q26 conventional DRAM contract forecast flat or down", "due": "2026-01-15"},
    {"what": "Reference stacks (Dynamo, SGLang, llm-d, TRT-LLM) make KV compression or hybrid attention the default and drop the host tier from recommended configs (host:GPU KV pool below 1x)", "due": "2026-06-30"}
  ],
  "stage": 1,
  "conviction": 4,
  "counter_evidence": [
    {"rows": ["A9", "A15", "A14", "A5"], "point": "KV compression/reuse cuts KV memory 47-90% with little accuracy loss; if it becomes default, bytes per token could fall faster than context grows."},
    {"rows": ["P12", "P17", "M12"], "point": "Hybrid-linear and sliding-window architectures cut KV per token (MiniMax-M1: -83% memory at 100K)."},
    {"rows": ["C-M11"], "point": "Micron Core Data Center BU -23% YoY: non-hyperscale server memory was weak through Aug-2025, so the tightness may be confined to a few CSP buyers."},
    {"rows": ["C-M7"], "point": "SK hynix pulled planned investment forward; a supply response could shorten the upcycle."},
    {"rows": ["A1"], "point": "For online serving, cheaper instances without offloading beat KV offload on cost-efficiency (up to 73.7%); offload pays mainly for offline batch."},
    {"rows": ["A4", "A8"], "point": "Alternatives keep KV on the accelerator (intra-GPU disaggregation; 512 MB on-die memory) and need no host tier."},
    {"rows": ["C-M2", "C-M3"], "point": "The LPDDR6 standard has no server wording and SOCAMM had no JEDEC module standard in the window, so server LPDDR depends on one platform (NVIDIA Grace)."},
    {"rows": ["C-M4"], "point": "No supplier-side source uses the words 'KV cache'; the platform-to-DRAM link is inferred, not disclosed."}
  ]
}
```

**Reasoning**
- This thesis has the strongest confirmation across source types of any here. Platform code (14 P rows), API pricing (M rows), usage disclosures (U rows), supplier filings and price reports all point the same way within six months.
- What is new is not that "memory is tight" but where the next byte goes. P04, P16, P20 and P21 show stacks spending HBM savings (FP8 KV, FP4 weights) on more context and bigger batches, and pushing the overflow to host DRAM. C-M10 and C-M14 show that commodity DRAM supply is already squeezed by HBM.
- **Stage 1:** prices, margins and business-unit revenue are already moving (C-M11, C-M14).
- **Conviction 4, not 5:**
  - Suppliers never name KV as a driver.
  - There is no primary Samsung data.
  - Micron's Core Data Center BU is down 23%.
  - S05 efficiency gains are the obvious way this could break.
- The cheapest early tests are SK hynix's 3Q25 results, Micron's FQ1-26 gross margin against the 51.5% guide, and TrendForce's 1Q26 forecast.

### Thesis 2: Enterprise QLC flash becomes the persistent context tier and the HDD substitute

```json
{
  "thesis_key": "qlc_flash_context_and_nearline_tier",
  "title": "Enterprise QLC flash becomes the persistent inference-context tier and the HDD substitute",
  "statement": "Inference stacks now push KV past DRAM into local NVMe and networked flash. Dynamo's KV Cache Manager 'can scale to petabytes', LMCache's persistent SSD cache is now inside Dynamo, SGLang HiCache's L3 runs on 3FS/Mooncake, and GPUDirect Storage delivers about 35 GB/s into one H100. Agentic coding keeps that cache resident for hours with >90% hit rates. At the same time the nearline tier is short: TrendForce says HDD shortages push CSPs to QLC enterprise SSD and forecasts NAND contract prices +5-10% for 4Q25; Sandisk raised prices 10%; Micron cut NAND wafer capacity >10%; and 245-256 TB QLC drives on 2 Tb dies make the swap economic at rack scale. NAND has been the least-loved memory segment and is read through phones and PCs; the chain implies enterprise-SSD bits become a structural AI attach (per-GPU storage bandwidth plus HDD replacement), with the gains going to share-gaining eSSD suppliers rather than the whole NAND basket.",
  "chain": [
    {"step": "Demand driver: long-lived agent sessions and multi-turn reuse keep context resident for hours (1 h cache TTL; >90% prefix-cache hit; >7 h Codex sessions with container caching; memory tool backed by external storage; coding-agent cache hit 40% -> 80% with an L3 tier).", "rows": ["M06", "M15", "M16", "M19", "P16", "U05"]},
    {"step": "Requirement: KV and session state beyond DRAM enter the inference data path on SSD/networked flash (petabyte-scale KV; NIXL GDS backend; VAST ~35 GB/s per H100, WEKA 270 GB/s across 8 H100; persistent SSD cache in Dynamo; 'every GPU requires storage').", "rows": ["P01", "P02", "P09", "P18", "P19", "U04", "U07"]},
    {"step": "Bottleneck: nearline capacity is short (HDD shortage pushes CSPs to QLC) and NAND supply was disciplined (Micron NAND wafer capacity cut >10%; CY25 supply growth below demand; controller substrate lead times).", "rows": ["C-M15", "C-M10", "C-M13"]},
    {"step": "Component: high-capacity QLC eSSD (Kioxia LC9 245 TB, Micron 6600 ION 245 TB, Sandisk SN670 256 TB; SK hynix expanding QLC eSSD and 321-high NAND; Micron 6550 ION 44 PB per rack).", "rows": ["C-M5", "C-M7", "C-M3"]},
    {"step": "Price/companies: NAND contract +5-10% in 4Q25, Sandisk +10% price increase; top-5 eSSD revenue >$5.1B (+12.7% QoQ), SK Group +47.1% (record), Kioxia +32.5%.", "rows": ["C-M15", "C-M13"]}
  ],
  "novelty": "new_issue",
  "novelty_reason": "Two things first appear inside the window. An HDD shortage forcing QLC substitution at CSPs (C-M15, 2025-09-25) coincides with SSD becoming a persistent KV tier inside NVIDIA's own reference stack (P18, P19, Sep-2025). Neither existed as an investable link a year earlier.",
  "what_market_misses": "The market reads NAND through consumer devices and capex discipline, not as an AI attach; the inference stacks' SSD KV tier plus an HDD shortage make enterprise QLC demand both AI-linked and capacity-constrained at the same time.",
  "beneficiaries": [
    {"company": "Sandisk", "ticker/exchange": "SNDK / Nasdaq", "role": "primary", "why": "Pure-play NAND; 256 TB SN670 QLC; announced a 10% price increase; HBF option with SK hynix (C-M6)."},
    {"company": "SK hynix", "ticker/exchange": "000660 / KRX (KOSPI)", "role": "primary", "why": "SK Group eSSD $1.46B, +47.1% QoQ (record); expanding QLC eSSD; HBF partner."},
    {"company": "Samsung Electronics", "ticker/exchange": "005930 / KRX (KOSPI)", "role": "secondary", "why": "Largest eSSD revenue ($1.9B) but flat QoQ, so it is losing share; benefits from price, less from mix."},
    {"company": "Micron Technology", "ticker/exchange": "MU / Nasdaq", "role": "secondary", "why": "245 TB 6600 ION and Gen6 SSD, but eSSD revenue -7.9% QoQ in 2Q25; NAND capacity cut helps price."}
  ],
  "losers": [
    {"company": "Seagate Technology", "ticker/exchange": "STX / Nasdaq", "why": "Two-sided: the same HDD shortage supports near-term pricing, but C-M15 says CSPs are shifting nearline bits to QLC, which costs share over the medium term."},
    {"company": "Western Digital", "ticker/exchange": "WDC / Nasdaq", "why": "Same two-sided exposure as Seagate (HDD-only after the Sandisk separation)."}
  ],
  "drivers": [
    {"metric": "4Q25 NAND contract price QoQ (TrendForce)", "latest": "+5-10%; Sandisk announced +10%", "row": "C-M15 (2025-09-25)"},
    {"metric": "Top-5 enterprise SSD revenue", "latest": ">$5.1B in 2Q25, +12.7% QoQ", "row": "C-M13"},
    {"metric": "eSSD revenue by supplier, 2Q25", "latest": "Samsung $1.9B flat; SK Group $1.46B +47.1%; Micron $784.6M -7.9%; Kioxia $750M +32.5%", "row": "C-M13"},
    {"metric": "Largest QLC eSSD shown", "latest": "245-256 TB on 2 Tb dies; >120 TB drives driving 2026 orders", "row": "C-M5, C-M15"},
    {"metric": "Flash-to-GPU bandwidth via GDS", "latest": "~35 GB/s into one H100 (VAST); up to 270 GB/s across 8 H100 (WEKA)", "row": "P18"},
    {"metric": "Micron NAND wafer capacity", "latest": "cut >10% exiting FY25", "row": "C-M10"},
    {"metric": "HBF timeline", "latest": "samples 2H CY2026; devices sampling early 2027", "row": "C-M6"}
  ],
  "first_signal": {"metric": "3Q25 enterprise-SSD revenue ranking: top-5 revenue up >=10% QoQ with high-capacity QLC cited as the driver", "where": "TrendForce / DRAMeXchange press center", "expected_by": "2025-12-15"},
  "falsifiers": [
    {"what": "Sandisk Sep-quarter results/guide show data-center revenue down QoQ or the announced price increase not holding", "due": "2025-11-15"},
    {"what": "TrendForce 1Q26 NAND contract forecast flat or down, or the HDD shortage reported as resolved", "due": "2026-01-15"},
    {"what": "NVIDIA/llm-d/SGLang recommended configs keep KV offload to CPU memory only, with the SSD tier off by default", "due": "2026-03-31"},
    {"what": "Nearline HDD vendors add enough capacity that HDD lead times normalise and CSP QLC substitution stalls", "due": "2026-03-31"}
  ],
  "stage": 1,
  "conviction": 3,
  "counter_evidence": [
    {"rows": ["A17"], "point": "SSD offload of MoE experts raises per-token energy up to ~12x vs HBM; SSD only viable if flash read energy falls ~10x (about weights, not KV, but shows SSD-in-the-loop is costly)."},
    {"rows": ["C-M13"], "point": "eSSD gains are uneven: Micron -7.9% QoQ, Samsung flat. This is a share story, not a rising-tide story."},
    {"rows": ["P15", "P21"], "point": "NVIDIA's first offload tier is Grace LPDDR over 900 GB/s C2C; SSD is a lower tier that may see little traffic."},
    {"rows": ["A1"], "point": "KV offloading pays mainly for offline batch jobs (20.19% saving); online serving prefers no offload."},
    {"rows": ["C-M10"], "point": "NAND wafer cuts earlier in 2025 signal weak demand before the turn; the price recovery rests heavily on supply discipline, which can reverse."},
    {"rows": ["C-M4"], "point": "Suppliers attribute demand to 'AI inference' but never to KV cache; the platform-to-NAND link is inferred."}
  ]
}
```

**Reasoning**
- Two independent forces pull on the same product. Inference stacks now put SSD in the KV path (P18, P19), and a nearline shortage is pushing CSPs from HDD to QLC (C-M15). Either one alone would be weak; together they make high-capacity eSSD both AI-linked and short of supply.
- **Conviction 3, below Thesis 1:**
  - Supplier data is uneven.
  - The key forward data point is a single TrendForce forecast.
  - NVIDIA itself routes the first offload to LPDDR, not SSD.
- Pick share gainers (SK Group, Sandisk), not the whole NAND basket. HDD makers are on both sides of the trade.

### Thesis 3: The rack becomes the inference unit: scale-up fabric silicon and active copper

```json
{
  "thesis_key": "rack_scale_scaleup_fabric",
  "title": "The rack becomes the inference unit: scale-up fabric silicon and active copper beyond NVIDIA",
  "statement": "The inference gains reported in the window come from the rack-scale scale-up domain rather than per-GPU FLOPs. On GB200 NVL72, SGLang reports 3.8x prefill and 4.8x decode per GPU vs H100, with multi-node NVLink replacing RDMA; TensorRT-LLM adds MNNVL all-to-all for wide expert parallelism; and Microsoft's Fairwater racks pool 14 TB of memory over 1.8 TB/s NVLink. The non-NVIDIA world is standardising the same thing within five months: UALink 1.0 (1,024 accelerators, load/store/atomic memory semantics), Broadcom Scale-Up Ethernet with Tomahawk 6/Ultra, and NVLink Fusion licensed to Marvell, Astera Labs and MediaTek. The first generation is copper-first at 200G per lane. NVIDIA networking revenue +98% YoY and Credo +274% show the spend has started. The market reads this as 'NVIDIA networking'. The under-read part is that every custom-XPU program now needs its own scale-up switch, retimers and active copper, a per-accelerator content line that ASIC racks did not have a year ago, and that memory pooling turns the scale-up fabric into a memory fabric.",
  "chain": [
    {"step": "Demand driver: MoE models served with wide expert parallelism and long contexts need heavy cross-GPU expert and KV traffic (EP across 96 H100; wide-EP as default llm-d recipe; attention/FFN disaggregation with M2N comms).", "rows": ["M01", "M04", "P05", "P13", "A16"]},
    {"step": "Requirement: a low-latency, high-bandwidth domain larger than 8 GPUs (pure NVLink across 14 nodes replaces RDMA, 2.7x; MNNVL MoE all-to-all; 3.8x/4.8x per GPU on NVL72; 14 TB pooled memory per rack; scale-up interconnect named a primary decode barrier).", "rows": ["P10", "P11", "P21", "U07", "A7"]},
    {"step": "Bottleneck/standard: a scale-up protocol and switch silicon for non-NVIDIA accelerators (UALink 1.0 with memory semantics; Tomahawk 6 512-XPU scale-up with 200G passive copper; SUE at OCP; Tomahawk Ultra; NVLink Fusion adopters; UEC 1.0 for scale-out).", "rows": ["C-O6", "C-O9", "C-P4", "C-O11", "C-O8", "C-O7"]},
    {"step": "Component and companies: scale-up switch ASICs, retimers, active electrical cables (NVIDIA networking $7.252B +98% YoY on NVLink fabric; Credo $223.1M +274% YoY; Broadcom AI semis $5.2B +63% on custom XPUs and networking).", "rows": ["C-X4", "C-O15", "C-X5"]}
  ],
  "novelty": "new_structure",
  "novelty_reason": "Scale-up stopped being NVIDIA-only inside the window: three competing open or licensed scale-up specifications appeared within five months (UALink 1.0 on 2025-04-08, NVLink Fusion on 2025-05-18, SUE on 2025-06-03 and at OCP on 2025-08-05).",
  "what_market_misses": "Investors attribute scale-up spend to NVIDIA, but custom-XPU racks now need their own scale-up switches, retimers and active copper, so a new per-accelerator content line is forming at Broadcom, Astera Labs, Credo and Marvell.",
  "beneficiaries": [
    {"company": "Broadcom", "ticker/exchange": "AVGO / Nasdaq", "role": "primary", "why": "Tomahawk 6 / Tomahawk Ultra / SUE for scale-up Ethernet plus custom XPUs; AI semis $5.2B (+63%), Q4 guide $6.2B."},
    {"company": "Astera Labs", "ticker/exchange": "ALAB / Nasdaq", "role": "primary", "why": "Named NVLink Fusion silicon adopter (C-O8) and on the UALink board (C-O6): it sits in both scale-up camps."},
    {"company": "Credo Technology", "ticker/exchange": "CRDO / Nasdaq", "role": "primary", "why": "Active electrical cables for copper-first scale-up; revenue +274% YoY, GM 67.6%."},
    {"company": "NVIDIA", "ticker/exchange": "NVDA / Nasdaq", "role": "secondary", "why": "Incumbent NVLink/NVL72 owner; networking +98% YoY; NVLink Fusion monetises third-party XPUs."},
    {"company": "Marvell Technology", "ticker/exchange": "MRVL / Nasdaq", "role": "secondary", "why": "NVLink Fusion adopter and custom-XPU vendor that needs scale-up attach."}
  ],
  "losers": [
    {"company": "RDMA NIC content inside the rack (category)", "ticker/exchange": "n/a", "why": "P10 shows multi-node NVLink replacing RDMA within the NVL72 domain; NIC count per GPU matters more for scale-out than for intra-rack traffic."},
    {"company": "Short-reach optics for intra-rack links through the 200G generation (category)", "ticker/exchange": "n/a", "why": "UALink and TH6 are copper-first at 200G (C-O6, C-O9), which delays optical scale-up content."}
  ],
  "drivers": [
    {"metric": "NVIDIA networking revenue", "latest": "$7.252B in FQ2-26, +98% YoY, +46% QoQ", "row": "C-X4 (2025-08-27)"},
    {"metric": "Credo revenue / guide", "latest": "$223.1M (+274% YoY, +31% QoQ) / $230-240M", "row": "C-O15 (2025-09-03)"},
    {"metric": "Broadcom AI semiconductor revenue / next-quarter guide", "latest": "$5.2B (+63%) / $6.2B", "row": "C-X5 (2025-09-04)"},
    {"metric": "GB200 NVL72 per-GPU throughput vs H100", "latest": "3.8x prefill / 4.8x decode", "row": "P21 (2025-09-25)"},
    {"metric": "UALink milestones", "latest": "1.0 spec Apr-2025; In-Network Collectives spec expected Dec-2025; 128G DL/PL in IP review", "row": "C-O6"},
    {"metric": "Pooled memory per NVL72 rack", "latest": "14 TB", "row": "U07"}
  ],
  "first_signal": {"metric": "NVIDIA FQ3-26 networking revenue up QoQ, and Broadcom FQ4-25 AI revenue at or above the $6.2B guide with scale-up Ethernet / Tomahawk Ultra customer commentary", "where": "NVIDIA 8-K CFO commentary (Nov 2025); Broadcom 8-K (Dec 2025)", "expected_by": "2025-12-15"},
  "falsifiers": [
    {"what": "NVIDIA FQ3-26 networking revenue declines QoQ", "due": "2025-11-30"},
    {"what": "Credo FQ2-26 revenue below the $230M guide low end", "due": "2025-12-15"},
    {"what": "UALink In-Network Collectives spec slips past Dec-2025 and no member announces UALink switch silicon sampling by mid-2026", "due": "2026-06-30"},
    {"what": "Hyperscaler custom-XPU racks announced for 2026 adopt optical scale-up (photonic fabric / optical I/O) instead of copper", "due": "2026-06-30"}
  ],
  "stage": 1,
  "conviction": 3,
  "counter_evidence": [
    {"rows": ["A19"], "point": "An OCS-in-transceiver high-bandwidth domain claims 31% of NVL-72 cost and >10x lower GPU waste, so optics could leapfrog copper scale-up."},
    {"rows": ["C-O10"], "point": "Hot Chips shows optical I/O moving into the XPU package (Celestial AI, Ayar Labs, Lightmatter), which would bypass AEC and retimers."},
    {"rows": ["A4"], "point": "Intra-GPU prefill/decode disaggregation matches or beats disaggregated vLLM without inter-node transfer."},
    {"rows": ["P21"], "point": "NVFP4 dispatch halves network bytes per token, so less fabric is needed per token."},
    {"rows": ["M12"], "point": "gpt-oss-120b fits one 80 GB GPU; some serving stays single-node."},
    {"rows": ["C-O15"], "point": "Credo does not split AEC vs DSP revenue, so attributing growth to scale-up copper is inference."},
    {"rows": ["C-O6", "C-O8", "C-O9"], "point": "Three competing scale-up standards may fragment volume, and NVIDIA's licensed path may keep most of the value."}
  ]
}
```

**Reasoning**
- Platform rows show the per-GPU inference gains coming from the rack domain (P10, P21). Three rival scale-up specs appearing within five months (C-O6, C-O8, C-O9/C-P4) is a structural change, not an iteration.
- **Stage 1:** revenue is already moving (C-X4, C-O15). The under-read part is the non-NVIDIA scale-up content line for custom XPUs (C-X5), not NVIDIA itself.
- **Conviction 3:** copper-first has a time limit. Optical I/O at Hot Chips (C-O10) and the OCS papers (A19) are the medium-term threat.
- Attribution is weak for some names. Credo does not split AEC from DSP revenue, and Astera Labs' role comes from adopter and board lists, not revenue.

### Thesis 4: Lasers, not modules: 1.6T now and CPO/ELSFP next move optical value to InP laser makers

```json
{
  "thesis_key": "laser_bound_optics_cpo_transition",
  "title": "Lasers, not modules: 1.6T now and CPO/ELSFP next shift optical value to InP laser makers",
  "statement": "Scale-out bandwidth per GPU is stepping up. Fairwater runs 800 Gbps non-blocking fat-trees, Tomahawk 6 reaches 102.4 Tb/s for 100,000+ XPUs in two tiers, Coherent has started 1.6T revenue shipments, 802.3dj (200G/lane) is nearing a technically complete draft, and 448G was demoed at OFC and ECOC. In parallel NVIDIA and Broadcom committed to co-packaged optics with external laser sources: Quantum-X Photonics later in 2025, Spectrum-X Photonics in 2026, and ELSFP multi-vendor interop at both OFC and ECOC. CPO moves value out of the pluggable module and its DSP into high-power CW lasers, fiber attach and silicon-photonics engines, while 1.6T pluggables meanwhile pull EMLs. In both paths the indium-phosphide laser is the common scarce input, and Lumentum's results already show it (Cloud & Networking +66.5%, EML strength, a target above $600M per quarter by June 2026). The market treats optics as one AI-transceiver basket; the chain says laser chips and fiber connectivity keep their content under CPO while module assembly and pluggable DSPs lose it.",
  "chain": [
    {"step": "Demand driver: scale-out to 100k+ accelerators and multi-GW sites (Fairwater 'hundreds of thousands' of GB200 on 800 Gbps non-blocking fat-trees; 10 GW OpenAI-NVIDIA; Stargate ~7 GW; NVIDIA networking +98%).", "rows": ["U07", "U08", "U09", "C-O9", "C-X4"]},
    {"step": "Requirement: 1.6T ports at 200G/lane and lower power per bit (802.3dj; OFC 1.6T/3.2T laser source assemblies; CEI-224G and first CEI-448G; Coherent 1.6T shipments).", "rows": ["C-O5", "C-O4", "C-O2", "C-O14"]},
    {"step": "Bottleneck: switch-port optics power forces CPO with external lasers (3.5x power efficiency; ELSFP at OFC and ECOC; TH6 CPO version; TSMC COUPE; CPO materials at ECTC; papers put laser optical power and comb lasers as the binding resource).", "rows": ["C-O1", "C-O2", "C-O9", "C-X1", "C-X2", "A24", "A26"]},
    {"step": "Companies: laser-chip owners named as CPO partners and reporting the ramp (Lumentum revenue +55.9%, EML and pump-laser strength; Coherent networking ~+39%; partners also include Corning and Fabrinet).", "rows": ["C-O13", "C-O14", "C-O1"]}
  ],
  "novelty": "new_technology",
  "novelty_reason": "First CPO switches from the GPU vendor (C-O1, 2025-03-18) and first multi-vendor interop of pluggable external laser sources (ELSFP at OFC 2025-03-12 and ECOC 2025-09-17). The 1.6T ramp itself is iteration.",
  "what_market_misses": "Optics is priced as a single AI-transceiver basket; under CPO the module and DSP content shrinks while external high-power lasers and fiber attach keep theirs, so laser-chip owners hold value as the architecture changes.",
  "beneficiaries": [
    {"company": "Lumentum", "ticker/exchange": "LITE / Nasdaq", "role": "primary", "why": "EML and CW laser chips; named CPO partner; revenue +55.9%, guide $510-540M, target >$600M per quarter by Jun-2026."},
    {"company": "Coherent", "ticker/exchange": "COHR / NYSE", "role": "primary", "why": "InP lasers plus 1.6T transceivers (revenue shipments started); named CPO partner; networking $945.2M."},
    {"company": "Corning", "ticker/exchange": "GLW / NYSE", "role": "secondary", "why": "Fiber and connectivity partner for NVIDIA CPO; fiber attach rises with CPO and 800G fat-trees."},
    {"company": "Fabrinet", "ticker/exchange": "FN / NYSE", "role": "secondary", "why": "Named both as CPO partner and as pluggable supplier. Hedged between the two paths, but its module-assembly value is at risk."}
  ],
  "losers": [
    {"company": "Marvell Technology (optical DSP portion)", "ticker/exchange": "MRVL / Nasdaq", "why": "Partial: CPO and LPO remove the DSP from switch-side and short-reach optics (C-O1, C-O3, A25). Offset by 800ZR and pluggables still supported."},
    {"company": "Non-US pluggable module assemblers (Innolight, Eoptolink; outside universe)", "ticker/exchange": "n/a (China-listed)", "why": "CPO moves switch-side optics into the switch package (C-O1)."}
  ],
  "drivers": [
    {"metric": "Lumentum quarterly revenue / guide / target", "latest": "$480.7M (+55.9%) / $510-540M / >$600M by Jun-2026", "row": "C-O13 (2025-08-12)"},
    {"metric": "Coherent networking revenue; 1.6T status", "latest": "$945.2M (~+39% YoY); 1.6T revenue shipments commenced", "row": "C-O14 (2025-08-13)"},
    {"metric": "NVIDIA networking revenue", "latest": "$7.252B, +98% YoY", "row": "C-X4"},
    {"metric": "CPO switch timing", "latest": "Quantum-X Photonics later 2025; Spectrum-X Photonics 2026", "row": "C-O1"},
    {"metric": "ELSFP interop venues", "latest": "OFC Mar-2025 and ECOC Sep-2025, 35 OIF members each", "row": "C-O2"},
    {"metric": "Lasers per CPO switch vs pluggable (counter-driver)", "latest": "~4x fewer", "row": "C-O1"}
  ],
  "first_signal": {"metric": "Lumentum FQ1-26 revenue at or above $540M (top of guide) with laser-capacity commentary, and first Quantum-X Photonics customer shipments", "where": "Lumentum 8-K Ex.99.1 (early Nov 2025); NVIDIA releases", "expected_by": "2025-11-30"},
  "falsifiers": [
    {"what": "Lumentum FQ1-26 revenue below the $510M guide low end", "due": "2025-11-15"},
    {"what": "Quantum-X Photonics CPO switches slip into 2026 without a named customer deployment", "due": "2026-03-31"},
    {"what": "Lumentum or Coherent report EML/CW laser supply loosening or laser price cuts", "due": "2026-06-30"},
    {"what": "Copper (TH6 200G passive, AEC) and LPO take most incremental short-reach links and 1.6T optics volume commentary is cut", "due": "2026-06-30"}
  ],
  "stage": 1,
  "conviction": 3,
  "counter_evidence": [
    {"rows": ["C-O1"], "point": "CPO uses ~4x fewer lasers per switch, so laser unit volume falls. The thesis depends on higher value per external laser, which no row quantifies."},
    {"rows": ["C-O1"], "point": "Pluggables remain supported (Coherent, Eoptolink, Fabrinet, Innolight), so the CPO transition timing is open."},
    {"rows": ["C-O9", "C-O15"], "point": "200G passive copper reach and AEC growth take short links that optics might otherwise get."},
    {"rows": ["C-O3"], "point": "LPO removes DSPs but keeps the module, which weakens the CPO value-shift argument."},
    {"rows": ["A19", "A20", "A21"], "point": "OCS designs move optical value toward switching, not lasers (papers only)."},
    {"rows": ["C-O13", "C-O14"], "point": "Laser makers already report strong growth, so part of this is visible and possibly priced; the edge is only the value-shift detail."}
  ]
}
```

**Reasoning**
- The 1.6T ramp is an iteration and is already visible in Lumentum and Coherent results. The new element is CPO plus standardized external lasers (C-O1, C-O2), which changes who owns the value in optics.
- Lasers are the input common to both paths: EMLs for pluggables and high-power CW lasers for ELSFP. That claim is supported by conference, standard, filing and paper rows, and A24 and A26 treat laser power as the binding resource.
- **Conviction 3.** C-O1's "~4x fewer lasers" is a real counter on unit volume, and no row quantifies value per laser. The CPO part of the thesis is stage 0; the 1.6T laser revenue part is stage 1.

### Thesis 5: ±400/800 VDC and power stabilization raise power-electronics content per MW

```json
{
  "thesis_key": "hvdc_power_electronics_per_mw",
  "title": "+/-400/800 VDC and power stabilisation raise power-electronics content per MW",
  "statement": "Rack power is moving from 130-140 kW (GB200/GB300 NVL72) toward 1 MW: NVIDIA's Kyber targets 2027, and Google says 'more than 500 kW per IT rack before 2030'. 54 V distribution breaks down above about 200 kW; TI says a 1 MW rack at 48 V needs almost 450 lbs of copper. Google, Meta and Microsoft published Diablo 400 (a +/-400 VDC sidecar) v0.5 at OCP; NVIDIA published an 800 VDC reference architecture with Eaton, Schneider and Vertiv; Infineon and TI announced HVDC parts with power-semi content 'similar or larger' than AC; and Eaton bought Resilient Power Systems (solid-state transformers) and Fibrebond. Separately, six papers show synchronous training power swings (tens of MW in the 0.2-3 Hz band) threatening grid stability, which adds fast energy buffering per row. The market values DC power names on MW growth. The chain says content per MW also rises (SSTs, SiC/GaN, DC protection, buffering) while in-rack AC PSUs and copper lose, and the electrical majors are buying the new technology rather than ceding it.",
  "chain": [
    {"step": "Demand driver: GW-scale AI builds and rising rack density (Microsoft >2 GW in 12 months; OpenAI-NVIDIA 10 GW; Stargate ~7 GW; GB200/GB300 at 130-140 kW per rack; 'short power' in places).", "rows": ["U04", "U08", "U09", "C-P8", "U01"]},
    {"step": "Requirement: racks of 500 kW to 1 MW, beyond what 54 V can carry, and loads that swing tens of MW (54 V limit above ~200 kW; 1 MW Kyber from 2027; 450 lbs of copper at 48 V; grid oscillations from AI training).", "rows": ["C-P1", "C-P2", "C-P3", "A29", "A30", "A32"]},
    {"step": "Bottleneck/standard: HVDC distribution with SSTs and fast buffering (Diablo 400 v0.5; NVIDIA 800 VDC architecture, up to 5% efficiency and 45% less copper; +/-400 Vdc row with SSTs replacing UPS/STS; TSMC IVR; ECTC power-delivery plenary).", "rows": ["C-P4", "C-P2", "A32", "C-X1", "C-X2", "C-P5"]},
    {"step": "Components/companies: SiC/GaN and HVDC conversion (Infineon, TI), electrical majors adding solid-state power (Eaton: Resilient Power Systems, Fibrebond; Electrical Americas backlog +17%), Vertiv (800 VDC partner; backlog $8.5B, book-to-bill ~1.2x).", "rows": ["C-P3", "C-P10", "C-P9", "C-P2"]}
  ],
  "novelty": "new_technology",
  "novelty_reason": "+/-400/800 VDC for IT racks has no deployed incumbent. The first open spec (Diablo 400 v0.5, 2025-08-05) and the GPU vendor's reference architecture (2025-05-20) both appeared inside the window.",
  "what_market_misses": "Power equipment is valued on data-center MW growth, but the HVDC/SST transition and AI-load buffering raise power-electronics content per MW and move it from rack PSUs to facility- and row-level converters that the electrical majors are acquiring.",
  "beneficiaries": [
    {"company": "Eaton", "ticker/exchange": "ETN / NYSE", "role": "primary", "why": "Named 800 VDC partner; bought an SST maker (Resilient Power Systems) and a modular power-enclosure maker (Fibrebond); backlog +17%."},
    {"company": "Vertiv", "ticker/exchange": "VRT / NYSE", "role": "primary", "why": "Named 800 VDC partner; backlog $8.5B; FY25 organic growth guide raised to 24%."},
    {"company": "Texas Instruments", "ticker/exchange": "TXN / Nasdaq", "role": "secondary", "why": "800 V HVDC power management and sensing with NVIDIA (C-P3)."},
    {"company": "onsemi", "ticker/exchange": "ON / Nasdaq", "role": "secondary", "why": "SiC supplier; mapped by business line only (not named in the files)."},
    {"company": "LS Electric", "ticker/exchange": "010120 / KRX (KOSPI)", "role": "secondary", "why": "Korean power-distribution/DC equipment maker; mapped by business line only (not named in the files)."}
  ],
  "losers": [
    {"company": "In-rack AC/54 V PSU and busbar content (category; main makers Taiwan-listed, outside universe)", "ticker/exchange": "n/a", "why": "800 VDC removes in-rack AC PSUs and cuts conductor copper by ~45% (C-P2)."},
    {"company": "UPS/STS-centric product lines (inside incumbents)", "ticker/exchange": "n/a", "why": "A32 proposes HVDC rows with SSTs and dynamic response units replacing UPS/STS. This is a mix shift inside Eaton and Vertiv, not a clean loser."}
  ],
  "drivers": [
    {"metric": "Rack power, current generation vs target", "latest": "130-140 kW (GB200/GB300) vs 1 MW from 2027", "row": "C-P8, C-P2"},
    {"metric": "Diablo 400 spec version", "latest": "v0.5 (Aug-2025)", "row": "C-P4"},
    {"metric": "Claimed 800 VDC benefit", "latest": "up to 5% efficiency, 45% less copper, up to 30% lower TCO", "row": "C-P2"},
    {"metric": "Vertiv backlog / book-to-bill / FY25 organic growth guide", "latest": "$8.5B / ~1.2x / 24%", "row": "C-P9 (2025-07-30)"},
    {"metric": "Eaton Electrical Americas backlog", "latest": "+17% YoY", "row": "C-P10 (2025-08-05)"},
    {"metric": "AI DC load oscillation magnitude", "latest": "tens of MW in the 0.2-3 Hz band", "row": "A32"}
  ],
  "first_signal": {"metric": "Diablo 400 moves past v0.5 toward v1.0, and Eaton or Vertiv names first +/-400/800 VDC sidecar or SST product orders", "where": "OCP Global Summit 2025 releases (Oct 2025); Eaton and Vertiv 3Q25 releases", "expected_by": "2025-11-15"},
  "falsifiers": [
    {"what": "OCP Global Summit 2025 passes without a Diablo 400 revision or a dated deployment plan from Google/Meta/Microsoft", "due": "2025-10-31"},
    {"what": "NVIDIA moves 800 VDC/Kyber 1 MW racks beyond 2027 or keeps 54 V busbars for its next rack generation", "due": "2026-03-31"},
    {"what": "Eaton and Vertiv 2026 outlooks contain no HVDC/SST revenue or order commentary", "due": "2026-02-28"},
    {"what": "Vertiv organic orders decline YoY in two consecutive quarters", "due": "2026-04-30"}
  ],
  "stage": 0,
  "conviction": 2,
  "counter_evidence": [
    {"rows": ["C-P2"], "point": "1 MW racks only from 2027; most benefits are vendor 'up to' claims, and no HVDC revenue exists yet."},
    {"rows": ["A33"], "point": "Software-only grid flexibility cut cluster power 25% for 3 h with no storage or hardware changes, weakening the buffering half."},
    {"rows": ["C-P11"], "point": "GE Vernova's gas backlog grows but its release does not mention data centers; generation, not DC power electronics, may be the binding constraint."},
    {"rows": ["C-P1"], "point": "400 V was chosen to reuse the EV supply chain, which may commoditise the parts quickly."},
    {"rows": ["C-P10", "C-P2"], "point": "Incumbents are already buying and partnering into HVDC, so the shift may already be in their multiples; the cleanest SiC/GaN exposure (Infineon) is outside the US/Korea universe."}
  ]
}
```

**Reasoning**
- The evidence is broad: an OCP spec, NVIDIA's architecture, Infineon and TI releases, Eaton's acquisitions and six papers on power swings. But there is no revenue line yet and 1 MW racks start in 2027. **Stage 0, conviction 2.**
- The useful insight is content per MW and where conversion happens (sidecar or row-level SSTs instead of in-rack PSUs), not "more data centers".
- A33 shows software can provide much of the grid flexibility without hardware, which directly counters the buffering half of the thesis.

---

## 4. Rejected candidates

1. **HBM4 drives a re-rating of HBM makers.** Rejected as consensus: it appears in JEDEC, TrendForce and every filing. The incremental KV byte is going to DRAM and flash tiers (T1, T2), and compression papers (A9, A15) cap HBM per token. Nothing here is under-read.
2. **Bear case: KV compression and hybrid attention collapse memory demand.** Rejected as a primary thesis. Platform rows show the savings being spent on longer context and bigger batches (P04, P21), and DSA keeps a dense 656 B/token KV (P22). Kept as the falsifier for T1 and T2.
3. **High Bandwidth Flash as a new tier (Sandisk / SK hynix).** One underlying announcement (C-M6, plus its FMS recap). Samples only arrive in 2H26, and A17 raises an energy critique. Kept as an option inside T2.
4. **CXL memory expanders for KV (e.g., Astera Labs Leo).** Only one paper and some FMS booths. The CXL Consortium issued no release in the window, and every platform row routes KV through Grace C2C/LPDDR and GDS instead.
5. **Optical circuit switching replaces the electrical spine.** Seven rows, but essentially all are papers, with no filing, platform or standard evidence. This fails the single-source-type rule.
6. **Liquid cooling (Vertiv, Modine, nVent).** Real and multi-source, but consensus and already visible in backlogs (C-P8, C-P9, C-P12), so there is no "what the market misses". Long-term risk to cold plates comes from C-P7.
7. **Microfluidic in-silicon cooling displaces cold plates.** Only a Microsoft lab test, one Hot Chips talk and papers. There is no listed pure play, and the horizon is about 5 years.
8. **Gas turbines and generation (GE Vernova) as the AI bottleneck.** Consensus. C-P11 does not mention data centers, so the link is inferred.
9. **LPO and DSP-free optics kill DSP vendors (short Marvell or Credo).** Contradicted by Credo's +274%, five-vendor 800ZR DSP interop (C-O2) and Coherent's DSP-based 1.6T ramp. The LPO MSA has no revenue evidence yet.
10. **Hybrid-bonding equipment for HBM and 3D DRAM.** SK hynix's HBM4 still uses MR-MUF (C-M8). 4F²/3D DRAM is long-dated (C-M9). Otherwise the evidence is papers only.
11. **Glass substrates (e.g., SKC/Absolics).** Papers plus one ECTC session, with no filing or customer signal.
12. **Scale-across DCI (coherent 800ZR, DCI vendors).** One NVIDIA release with no numbers, plus an interop demo. Too thin.
13. **Test escapes and SDC drive test and burn-in demand.** Three papers only, a single source type.
14. **Disaggregated P/D means an RDMA NIC per GPU, as a stand-alone thesis.** Real (P16: 8 NICs for 8 GPUs), but multi-node NVLink replacing RDMA inside NVL72 racks (P10) cuts against it. Folded into T3.
15. **Server LPDDR/SOCAMM as a stand-alone thesis.** Same suppliers and same chain as T1, so merged into it. There was also no JEDEC module standard in the window (C-M3).
16. **AI storage arrays and software (Pure Storage, NetApp).** The vendors named in the files (VAST, WEKA) are private, and the listed vendors do not appear in the files.
17. **Edge inference memory (gpt-oss-20b in 16 GB).** A single row (M12).
18. **Oracle and contracted-capacity backlog (RPO $455B) as an Oracle thesis.** Demand-side and outside the three hardware chains. Used only as a driver.

---

## 5. What I could not judge from these files

- **Samsung's supply response.** Samsung's primary 2Q25 results and IR deck were denied, so I could not see its HBM qualification status, conventional-DRAM capacity plans, or eSSD strategy. Samsung is the swing supplier for T1 and T2.
- **The HBM vs conventional DRAM split.** Micron's FQ4 release gives no HBM figure, so I cannot tell how much of the +214% Cloud Memory BU growth is HBM and how much is conventional DRAM or LPDDR.
- **The size of the KV tier in deployed hardware.** No source discloses GB of host DRAM or TB of SSD per deployed GPU. No supplier-side source uses the words "KV cache". The link from platform code to memory revenue is inferred.
- **Valuations.** The files contain no share prices or multiples, so "what the market misses" is judged against the narrative in the sources, not against valuation.
- **2026 supply response.** Apart from SK hynix's capex pull-forward and Micron's ~$14B FY25 capex, there is no data on DRAM/NAND capacity additions or on HDD capacity plans. A fast supply response would break T1 and T2.
- **Optics unit economics.** There are no laser ASPs, no external-laser content per CPO port, no CPO attach-rate forecast, and no AEC vs DSP split at Credo.
- **HVDC sizing.** There is no revenue or order data for HVDC or SSTs, and the spec is only at v0.5. The Korean power names are mapped by business line, not by file evidence.
- **Hiring.** No dated job postings were admissible (B §3), so the hiring channel is empty.
- **Residual contamination and bias.**
  - Paper discovery used post-cutoff search ranking (A method note), which may over-represent topics that later became popular.
  - Rows marked † (P06, P18, P19, U07) and C-P2 have post-cutoff page edits.
  - None of these is the sole support for a chain step, but they are not fully clean.
