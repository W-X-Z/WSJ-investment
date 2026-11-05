# Supercap content per MW (Bloom), Sanmina/AcBel layer, INNIO non-Texas backlog — fact base
Compiled 2026-11-05. Builds on fuelcell_supercap.md and engines_market.md (not repeated). Primary/company sources first. [INFERENCE] = my arithmetic/reasoning, not a source claim. Quotes verbatim unless marked (paraphrase).

Research limits: (a) patents.google.com and dart.fss.or.kr were blocked by the fetch provenance rule — the patent full text was read via ipiq.io mirror (paragraph-numbered), DART filings via DigitalToday/Dealsite/THE ELEC transcriptions; (b) the Bloom IEEE deck PDF could not be downloaded (ieee.org TLS chain fails through the proxy), so slide text came from WebFetch extraction only — the relationship of the "200kW" block to the "Step-Load Module (Supercap)" on slide 11 could not be visually confirmed; (c) Vina Tech's 2024 IR Book (pre-Bloom, image-only PDF) has no data-center module spec; no Vina Tech IR deck describing "cells per Bloom module" was found; (d) DCD pages return client errors; (e) no OEM states Texas/non-Texas for any INNIO order.

---

## Q1. Supercapacitor content per MW of Bloom islanded data-center power

### 1a. What the primary sources actually say (no sizing numbers exist in public)

**Bloom patent US 2026/0129787 A1** (full description via ipiq.io, https://ipiq.io/patents/7436436 ; pub. 2026-05-07):
- [0028] "2-30 power modules, for example 3-12 power modules, such as 6-12 modules"; [0029] "twelve power modules 12 (two rows of six modules stacked side to side)".
- [0048] "storage components, such as batteries and/or ultracapacitors (also known as supercapacitors)" ... "which may support the power system in meeting step load changes".
- [0082] "step load modules containing supercapacitors (i.e., ultracapacitors) used together with the fuel cell system" to "smooth out the power demand spikes from the AI data center".
- [0084] "step load modules (SL7) 306 that include supercapacitors (i.e., ultracapacitors)" to "fill in short gaps in data center 620 load power demand"; "one or more battery modules 611 that include battery backup power supplies"; "one or more optional DC/DC converter modules 615".
- [0090] battery modules "may supply DC power to the DC power shelves 631 ... (when the DC load exceeds the PM 12 DC power output)"; step load modules are "configured to supply DC power quickly to the DC PDU 650 in response to DC power shelf 631 load demand spikes".
- [0094] "The step load modules (SL7) 306 may be arranged on a common base 680 in a pair of rows".
- NOT in the patent: capacitance (F), kJ/kWh/Wh, seconds, kW/MW ratings, module counts per stamp, supercap:fuel-cell ratio. Battery role = backup/deficit supply (not step-load). Claims 1/14 (supercap step-load modules) and 12/18 (battery + DC/DC) as previously noted.

**Bloom IEEE Nashville deck (2026)**, https://ewh.ieee.org/r3/nashville/events/2026/OnSitePowerwithFuelCells.pdf :
- Slide 11 ("The Architecture of a Fuel Cell Server"): DC Energy Server = DC power modules + "Step-Load Module (Supercap)" + system safety; ratings printed: "65kW" ×6, "200kW", "Min.325kW…Max.845kW", 800 V DC, 400–480 V AC. The extracted text does not say what the 200 kW block is. [INFERENCE] 325 and 845 are 5× and 13× 65 kW; 200 kW is not a multiple of 65 kW, so it is plausibly the Step-Load Module's power rating — unconfirmed (deck image not viewable).
- Slide 27: each DC server block, each "SUPERCAPACITORS" block and each inverter block carries the same "0.3MW...3.3MW" range; "MV BUS (max 34.5kV, 26MW)", "1...8 STAMPS", "3500kVA" transformer "0.48kV||34.5kV".
- Slide 29: "Customer AI Load Profile: 45s@90% | 9s@10%" measured with a Fluke 1750.
- No ramp rate, ms response, kJ or cost figure anywhere in the deck.

**NMED Statement of Basis (DRAFT) for NSR Permit 10883, "YGI Microgrid", Yucca Growth Infrastructure LLC, dated 7/29/2026**, https://cloud.env.nm.gov/resources/_translator.php/NmE1OTcwZDc1NzQ2NGE2YjU1MWNiODEzZl8yMzYxNzc~.pdf :
- "Energy Server 'clusters' are routed to a total of 2,275 exhaust stacks as emission sources" (SOFC-1 … SOFC-2275); units of "325 kW of net AC power. A minority of smaller units produce 260 kW of net AC power"; facility table "2.4620 GW"; "operate the Bloom Energy Server System at its maximum rated load for 8,760 hours per year"; GHG 8,820,970 tpy (10,144,115 incl. 15% safety factor removed).
- Supercapacitors, step-load modules, batteries, BESS, inverter counts: NOT mentioned (only "DC-to-AC converters and transformers" and an "inverter group/platform"). Air permits list emission units only, so this is expected, not evidence of absence.
- [INFERENCE] 2,462 MW ÷ 0.325 MW ≈ 7,575 Energy Servers ≈ Oracle's "about 7,000 fuel cells"; ≈3.3 Energy Servers per exhaust stack.

**Vina Tech**: no public document gives cells per Bloom module, F rating or MW equivalent. SK Securities 2025-10-28 (p.1): "향후 3년간 Bloom Energy의 연료전지 시스템에 슈퍼커패시터 셀을 독점 공급하며, 전력 피크 부하 완화와 무정전 전원 공급을 담당한다"; "현재는 셀 단위 공급 단계지만, 시스템 단위 협력으로의 확대도 논의 중". DS Investment 2026-07-01 (p.1): "전일 공시한 슈퍼캡 시스템 공급계약 규모는 412억원이다. 데이터센터용이며 본격적인 공급은 4분기부터 이루어질 예정", "슈퍼캡부터 인클루저까지 고객 사로 직납하는 구조", "시스템은 해외 경쟁사가 존재하기 때문에 독점 공급은 아니지만", "시스템 공급 초기 수익성은 아주 높지 않을 것". DS 2026-05-22: cell CAPA "증설 후 연간 3,000억원 수준(증설 전 CAPA 약 1,500억원)". passive-components.eu 2026-02-26: Bloom LTA "through 2027"; ~30 M cells/month across three Hanoi plants; internal estimate of "up to 20-fold higher added value compared to bare cells" for integrated packages. THE ELEC 2026-10-21: orders since late June total "약 3485억원"; Leadeconomy 2026-10-20: H1 2026 mid/large snap-in output 5.08 M units (vs 4.86 M for all of 2025), utilization mid-70%.
- No MW is stated in any Vina Tech 공시; amounts are "발주서에 기재된 구매수량과 단가를 기준으로 산정" (Dealsite 2026-10-21).

### 1b. Derivation (all [INFERENCE]; ranges, not point estimates)

Step 1 — supercap POWER per MW of fuel cell nameplate.
- From slide 27: supercap block and DC-server block share the same 0.3–3.3 MW range per stamp → design ratio ≈ 1:1 (0.3 MW per ~325 kW Energy Server up to 3.3 MW per 3.25 MW stamp). Lower bound if read literally as minimum: 0.3/3.25 = 0.09.
- From slide 11 (if the 200 kW block is the Step-Load Module): 200 kW per DC Energy Server of 325–845 kW → 0.24–0.62 MW per MW.
- Working band: 0.25–1.0 MW of supercap per MW of fuel cell; Jupiter at 2,462 MW nameplate → 0.6–2.5 GW of supercap power; at the 1,600 MW operating cap → 0.4–1.6 GW. The "~1.6 GW of supercaps" figure in the brief equals the 1,600 MW cap × 1:1.

Step 2 — supercap ENERGY per MW.
- No Bloom figure. Bracket by analogues: Skeleton PCS50 datasheet (2026-04-14): "Peak power 60 kW", "Nominal power 40 kW", "Nominal capacity 100 kJ" → 1.7 s at peak, 2.5 s at nominal; Delta PCS (passive-components.eu 2025-05-06): "can support a 15-kilowatt load for up to five seconds" → 75 kJ (5 s); Microsoft/CMU: 91 kJ for 4.7 kW → 19 s. Bloom whitepaper: fuel cell follows 40→100% "almost instantaneously" with supercaps covering the ramp; test profile holds 90% for 45 s, so supercaps need not carry a full 45 s step.
- Working band: 2–20 s of full supercap power → at 1 MW supercap per MW fuel cell: 2–20 MJ ≈ 0.55–5.6 kWh per MW of fuel cell (at 0.25 MW/MW: 0.14–1.4 kWh/MW). Unit note: "GW of supercaps" is a power figure; energy is MWh-scale for a 2.5 GW site (0.6–14 MWh at Jupiter nameplate).

Step 3 — CELLS per MW.
- Generic 3.0 V / 3,000 F EDLC cell: E = ½CV² = 13.5 kJ; usable 3.0→1.5 V ≈ 10 kJ. Energy-limited count: 2–20 MJ ÷ 10 kJ = 200–2,000 cells per MW. Power-limited count: practical continuous 1–2 kW per large cell → 500–1,000 cells per MW of supercap power. Combined: ~500–2,000 large cells per MW (at 1:1 power ratio). If Vina Tech's data-center product uses mid-size cells (e.g., 300–600 F "mid/large snap-in", 1.3–2.7 kJ), count is 5–10× higher: ~2,500–20,000 cells/MW. Vina Tech's cell type for Bloom is not disclosed. Jupiter at 2.46 GW → 1.2–5 M large cells (or 6–50 M mid-size) — versus Vina Tech's ~30 M cells/month of (mostly small) output and 4.86 M mid/large units in 2025.

Step 4 — KRW/USD revenue per MW (cross-checks, all [INFERENCE]).
- Microsoft/CMU "$20,000 per kWh" × 0.55–5.6 kWh/MW → $11k–112k per MW of fuel cell (system level, older price basis).
- Cell level: 500–2,000 large cells × ~$15–25 (market ASP, not a Vina Tech figure) → $7.5k–50k per MW ≈ 1,000만–6,700만원/MW.
- Contract cross-checks: LS Materials 688.8억 ($51.5M) for Apr 2027–Mar 2028 deliveries to a "미국 수소연료전지 기업" (end customer unconfirmed): if Bloom and if Bloom ships ~2–3 GW in that window → ~$17k–26k/MW (cell level). AcBel 1,230억 ($91.6M) Oct 2026–Feb 2028: AcBel assembles ~90% of Bloom power converters, but also makes 1 MW HVDC/PSU products, so no clean MW mapping. Bloom 412억 system contract (4Q26 start, period not disclosed): at $30M, 0.3–1 GW of coverage would imply $30k–100k/MW (system). Bloom MOU 180억/3 yrs (2025 press) is far below any of these per-MW bands if Bloom shipped >1 GW/yr — consistent with it being an initial-volume LTA, not the run-rate.
- Context: Bloom system pricing implied by AEP ($4B/702 MW incl. CCS ≈ $5.7M/MW) and Nebius ($2.6B/328 MW incl. developer role ≈ $7.9M/MW) → supercap content ≈ 0.2–2% of project cost at the bands above.

Summary table (per MW of Bloom fuel-cell nameplate, [INFERENCE]):
| Metric | Low | High | Basis |
|---|---|---|---|
| Supercap power | 0.25 MW | 1.0 MW | slide 11 200 kW/ES; slide 27 0.3–3.3 MW per stamp |
| Supercap energy | 0.14 kWh | 5.6 kWh | 2–20 s × power band |
| Large (3,000 F-class) cells | ~250 | ~2,000 | 10 kJ usable/cell; 1–2 kW/cell |
| Mid-size cells (300–600 F) | ~2,500 | ~20,000 | if small-format |
| Supplier revenue, cells | $7.5k | $50k | ASP $15–25 (market) |
| Supplier revenue, system | $11k | $112k | $20k/kWh (MS/CMU) |
| Jupiter (2,462 MW) supercap power | 0.6 GW | 2.5 GW | ×band; 0.4–1.6 GW at 1,600 MW cap |

---

## Q2. Sanmina 1,195억 and AcBel contracts — product, customer, layer

### 2a. Disclosure facts
- **Sanmina, 2026-10-21** (Dealsite 2026-10-21 18:38, https://dealsite.co.kr/articles/171094 ; THE ELEC 2026-10-21 https://www.thelec.kr/news/articleView.html?idxno=64073 ): "비나텍이 미국 전자제품 위탁생산 전문기업 산미나와 1195억원 규모의 데이터센터용 슈퍼커패시터 공급계약을 체결했다고 21일 공시했다"; ≈USD 89.97M; period 2026-10-21~2027-12-23; 공급지역 "인도"; "제품은 해외법인을 통해 생산할 예정"; THE ELEC: "약 145.3%" of 2025 revenue (822억). Product wording in the 공시 is only "데이터센터용 슈퍼커패시터" — NOT "power quality auxiliary device"; no UPS wording this time. End customer: not disclosed.
- **Earlier Sanmina**: 2026-07-06, 131.13억, "데이터센터용 슈퍼커패시터 공급계약", 15.95% of 2025 revenue, through 2026-11-27 (KET 2026-07-06); 2026-09-07, 133억, 16.17%, "runs through January 28 of next year", counterparty described as "Indian company Sanmina Corporation" (edaily 2026-09-07) — i.e., the Indian entity, consistent with 공급지역 인도.
- **AcBel, disclosed 2026-10-19** (DigitalToday https://www.digitaltoday.co.kr/disclosure/articleView.html?idxno=708210 ; DART rcpNo 20261019900317): 123,010,501,824원 = USD 91,634,760 @1,342.40; 149.60% of 2025 revenue (82,228,905,359원); period 2026-10-16~2028-02-01; 공급지역 대만; "데이터센터용 슈퍼커패시터 공급계약"; 외주생산 (해외법인); "발주서에 기재된 구매수량과 단가"; AcBel described as 전원공급장치 제조, FY2025 revenue 1,312,853,370,180원, "has completed similar contracts with Vina Tech in the past three years". Leadeconomy 2026-10-20 lists H2 orders: Bloom 412억 (6/30, system), AcBel 384억 (July), Sanmina 131억 (July) + 133억 (9/7), AcBel 1,230억 → "2,290억원" before the Sanmina 1,195억.
- Note: SBS Biz 2026-10-23 wrote both deals were "이틀 사이" — 공시 dates are Oct 19 (AcBel) and Oct 21 (Sanmina).

### 2b. Which layer? (evidence, then [INFERENCE])
- Sanmina: no Sanmina document mentions supercapacitors. Sanmina facts: (i) acquired ZT Systems' data-center infrastructure manufacturing business from AMD (announced 2025-05-19; ZT = "a leading provider of Cloud and AI infrastructure to the world's largest hyperscalers"); (ii) Reliance–Sanmina JV manufactures at "Sanmina's 100-acre campus in Chennai" for "hyperscale data centers" among others (Business Insider India, JV completion 2022); (iii) Dec 2025 Houston "Energy" factory = medium-voltage transformers/switchgear from 2027 — not supercaps. [INFERENCE] 공급지역 인도 + "해외법인 생산" (Vietnam) → cells/modules shipped to Sanmina's Chennai EMS operation to be built into rack-level power equipment (power shelves/BBU-class or UPS modules) for hyperscale/AI server customers; Sanmina does not build fuel-cell plants, so this contract is most likely NOT the Bloom step-load layer. Who the end OEM/hyperscaler is: not disclosed. Leadeconomy (2026-10-20) frames all three customers' products as buffers for "UPS, battery backup units, 800V DC distribution, and PSUs".
- AcBel: dual role — (a) assembler of Bloom power converters (~90% share, prior findings) and (b) PSU/HVDC maker ("nuova linea di alimentatori HVDC ... da 1 MW", DigiTimes via ai-radar 2026-01-23; "Q4 2025 results driven by AI data centers and fuel cell products", DigiTimes 2026-03-12 excerpt). The 공시 ("데이터센터용", Taiwan) does not resolve the split. [INFERENCE] Given the 16-month term and 150% of revenue, the AcBel 1,230억 is more plausibly tied to volume Bloom step-load/converter assembly than to PSU hold-up caps alone, but this is unproven; treat AcBel as mixed.
- Rack-level spec anchors (independent of fuel cells): Nvidia GB300 NVL72 (developer blog 2025-07-28, updated 2025-08-27): "filled the remaining space with 65 joules/GPU of energy storage", "energy storage elements—specifically electrolytic capacitors—", "about half of the volume is occupied by capacitors for energy storage"; peak grid draw −30%. → Nvidia's reference design uses ELECTROLYTIC caps, not supercaps. [INFERENCE] 65 J × 72 GPUs = 4.7 kJ per rack ≈ 0.04 s of a 120 kW rack — a smoothing buffer, not ride-through. Supercap shelves (Skeleton PCS50: 100 kJ, 60 kW peak, "21” ORV3 rack compatible", "Standalone peak shaving"; Delta PCS: 15 kW for 5 s) are 20× larger per shelf and are the optional ORv3 "capacitance shelf" layer; Eaton XLHV "up to 420 kilowatts" in a rack. No OCP/Nvidia document found that mandates supercaps per rack; GB300 uses electrolytics, supercap PCS is vendor-optional. Market size framing: rack-level supercap demand (per Jianghai estimate in prior file: 15–18 M caps for 2026 GB300 racks) exists regardless of fuel cells; Sanmina's order most likely belongs here.

---

## Q3. INNIO data-center orders — Texas vs non-Texas

### 3a. Order-by-order location evidence
| Order | GW | Location evidence | Source |
|---|---|---|---|
| VoltaGrid #1 (Oct 2025) | 2.3 | Oracle/Vantage Frontier, Shackelford Co., **Texas** (POWER) | prior file |
| VoltaGrid #2 (Feb 11 2026) | 1.5 | "data center customers across the United States"; "Delivery is scheduled by 2028"; 300 J624/J620 in 25 MW units | https://www.innio.com/en/news-media/press-releases/innio-secures-additional-major-order-from-voltagrid-1-5-gw-for-behind-the-meter-power-generation/ |
| Mega-campus developer (Jul 28 + Oct 22 2026) | 1.72 | Jul: "developer and operator of large-scale data center campuses", sites "in the US", >200 J624, phased, no state (DCD); Oct 22: "leading developer and operator of mega-scale data center campuses in the U.S.", 620 MW containerized J624, booked Sept 2026, LTSA on "first 500 MW of previously ordered capacity" incl. "all spare parts and labor through a major overhaul"; no state, no delivery year | https://www.sttinfo.fi/tiedote/72437065/... (INNIO PR 2026-10-22) |
| Rehlko framework (Apr 9 2026) | 1.25 | "key global markets"; via Clarke Energy's "authorized territories"; hyperscale/colo/enterprise DCs + flexible generation + hybrid gas+BESS; no state/country; Rehlko's Apr 29 2026 "1.7 GW" DC awards are diesel backup, "multiple hyperscale campuses" in North America, no states | https://www.powermag.com/rehlko-innio-have-deal-for-1-25-gw-of-gas-engine-capacity/ ; https://www.rehlko.com/newsroom-backup-power-orders-secured-for-data-center-growth |
| Liberty Energy (Q3 2026) | 0.45 | INNIO PR 2026-09-17: "a U.S. energy company" (name withheld), "large-scale data center projects in North America", J624 containerized, "expected to be delivered by 2028" (8-K names Liberty). Liberty's own disclosed pipeline: Vantage "up to 1 GW" with "reservation of 400 MW of 2027 power generation capacity" (state not named, 2026-01-05); "330 MW Texas power reservation with phased operations starting Q4 2027" (Q4 2025 results); PowerBridge JV "West Texas" 2 GW campus (DCD headline, 2026-07-22); Q3 2026: ESA ~500 MW with "a leading frontier AI lab and a dedicated infrastructure platform", "phased energization schedule from Q4 2027 through Q1 2029", part of "1.2 GW of integrated power services at data center campuses" (no site) | https://pgjonline.com/news/2026/september/innio-secures-450-mw-order-to-power-next-generation-data-centers ; https://www.powermag.com/liberty-energy-will-develop-gas-fired-power-for-data-center-group/ ; https://offshoresource.com/business-wire/liberty-energy-inc-announces-third-quarter-2026-financial-and-operational-results/ |
| Aggreko (Oct 8 2026) | ≥0.45 | "at least 450 megawatts of Jenbacher Type 4 engine capacity in 2027", partnership through 2031, J620 added from 2028, multiyear service on existing INNIO fleet; geography not stated; Aggreko fleet global ">17GW"; Aggreko DC revenue ~$391M FY to Jan 3 2026 | https://business-news-today.com/innio-commits-450mw-of-engine-capacity-to-aggreko-as-6-6bn-backlog-tests-manufacturing-scale/ |
| INNIO Q3 call (Oct 27 2026) | — | No state/Texas/region statement; DC = 60% of Q3 equipment revenue, 67% of LTM equipment order intake; 2026 deliveries ~4.5 GW (~1.5 GW Q4); slots into 2029–2031; "has not allocated meaningful volumes to neocloud operators" | https://www.marketbeat.com/instant-alerts/transcript-innio-q3-earnings-call-highlights-2026-10-27/ |

### 3b. VoltaGrid's located pipeline (the only INNIO customer with public site detail)
- Order book: "roughly 7.5 GW order book through 2030" (w.media 2026-05-13); planned "more than 4,300 megawatts of data-centre power supply" through 2028 (The Logic 2025-11-11, $2B notes + $3B RCF); Data Center World 2026-04-22 talk: "securing five gigawatts of data center power". No state breakdown published.
- Texas: Oracle/Vantage Frontier 2.3 GW (Shackelford Co.); Vantage TX12 San Antonio — "423 MW of gas-fired generation and 454 MW of diesel backup" across two off-grid sites, EIP/Sierra Club/Public Citizen notice of intent to sue over minor-source TCEQ permits (baxtel 2026-07-24); Granbury TX manufacturing (Propell).
- Georgia, Covington (Serverfarm): "90 megawatts", "33 natural gas-fired engines/generators" (SELC petition 2026-07-13 ¶8; OEM not named); EPD NOV 2026-07-02 for building before air permit; consent orders Sept 30 2026 (prior file); PSC voted unanimously 2026-08-18 "to hold hearings on the legality of the arrangement" under the Territorial Electric Service Act / Cogeneration Act; hearing officer process, no dates set (AJC 2026-08-18). GEM wiki (2026-11-04): 90.1 MW, "Pre-construction". Still unresolved as of Nov 2026.
- Washington, Quincy (Vantage): 14 engines/30 MWe — VoltaGrid "withdrew its permit application the day after the comments were submitted" (>500 comments); Grant County PUD: "We understand that the on-site power generation is no longer needed for that location" (KUOW 2026-07-30). Cancelled.
- Vantage–VoltaGrid Feb 2025 partnership: 1 GW off-grid across Vantage's North American portfolio — Texas (TX12) and Washington (dropped) are the only publicly identified Vantage/VoltaGrid sites.

### 3c. Texas vs non-Texas estimate [INFERENCE]
- Disclosed DC order set since Oct 2025: 2.3 + 1.5 + 1.72 + 1.25 + 0.45 + 0.45 ≈ 7.67 GW (≈ the $7.96B equipment backlog at Sept 30 2026, which also includes non-DC equipment).
- Texas-confirmed: 2.3 GW (Frontier) ≈ 30%. Non-Texas confirmed: ≈ 0.09 GW (Georgia Covington, if Jenbacher; OEM not named) ≈ 1%. Washington 0.03 GW withdrawn. Unlocated: ≈ 5.3 GW ≈ 69% (VoltaGrid #2 1.5 — likely partly San Antonio TX 0.42 GW; mega-campus 1.72; Rehlko 1.25 "global"; Liberty 0.45 — Liberty's named sites are Texas-heavy (330 MW TX reservation; PowerBridge West Texas JV); Aggreko 0.45 global rental).
- Plausible range: Texas share of INNIO's DC engine backlog ≈ 30% (hard floor, Frontier only) to ≈ 50–60% if VoltaGrid #2's located portion, Liberty's Texas reservations and part of the mega-campus order are Texas. Non-US (Rehlko/Aggreko "global") could be 10–20%. No source supports a point estimate; INNIO itself gives none.
- Mega-campus developer identity: no press speculation found; "developer and operator of mega-scale data center campuses" + containerized J624 + LTSA. Candidates by profile only (Vantage, Crusoe, Stack, Aligned, CyrusOne, Related Digital) — none evidenced; Vantage already buys via VoltaGrid and Liberty, which argues against double counting. Left open.

---

## Open questions
1. Is the slide-11 "200kW" block the Step-Load Module rating? (Needs the deck image or a Bloom spec sheet.) That single number would fix the power ratio at 0.24–0.62 MW/MW.
2. Vina Tech cell format for Bloom (3,000 F-class vs mid-size snap-in) — determines cells/MW by 10×; and the 412억 system contract's term/MW.
3. Sanmina's end OEM for the India-destined supercaps (ZT Systems racks? UPS?); whether any Sanmina Chennai product is an ORv3 capacitance shelf.
4. AcBel 1,230억 split between Bloom converter assembly and PSU/HVDC products.
5. State(s) of the 1.72 GW mega-campus order and of VoltaGrid's 1.5 GW; Liberty's Vantage 400 MW (2027) site; Rehlko/Clarke 1.25 GW country split.
6. Georgia PSC hearing schedule/ruling on VoltaGrid Covington (Territorial Act) — precedent for third-party BTM sales outside Texas.
7. INNIO $/MW on DC orders (to convert the $7.96B backlog into GW and reconcile with the ~7.7 GW disclosed).
