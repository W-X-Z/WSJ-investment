# Reciprocating gas engines for AI data centers outside Texas — supply/demand map and OEM positions

Compiled 2026-11-05. Primary sources (SEC filings, OEM releases, state permit documents, Cleanview) first; trade press second. "[Inference]" marks my own reasoning. No investment conclusions.

Research limits: Web-search budget was exhausted before Ohio EPA/OPSB rules, Nevada, Utah and Virginia project-level permit detail could be run; Cleanview's full OEM/state tables are paywalled; Cummins' Q3 2026 release (expected ~Nov 4–6, 2026) was not yet retrievable from investor.cummins.com (provenance-blocked) or SEC; Caterpillar's 8-K/10-Q on sec.gov returned client errors (used Manufacturing Dive / MarketBeat summaries instead).

---

## 1. OEM-by-OEM: orders, backlog, capacity, lead times, data-center share

### INNIO (Jenbacher / Waukesha) — Austrian, NYSE-listed since mid-2026
| Item | Figure | Source/date |
|---|---|---|
| Q3 2026 revenue | $1,167.9M (+57% YoY); equipment $777.6M (+86%), services $390.3M (+20%) | 8-K ex99.1, Oct 27 2026: https://www.sec.gov/Archives/edgar/data/0002109150/000162828026067394/ex991.htm |
| Equipment order intake | Q3 $2,175.9M (+10%); YTD $6,083.8M vs $3,178.4M (+91%); LTM book-to-bill 3.3x | same + MarketBeat call summary Oct 27 2026 |
| Equipment backlog | $7,963.4M at Sep 30 2026 (+142% YoY from $3,292.9M; $6.6B at Q2) | 8-K |
| Unsatisfied performance obligations (incl. services) | $8.8B at Jun 30 2026; ~79% to be recognized within 24 months | 10-Q Q2 2026: https://www.sec.gov/Archives/edgar/data/0002109150/000119312526319072/d118344d10q.htm |
| Data-center share | 60% of Q3 equipment revenue; 67% of trailing-12-month equipment order intake | MarketBeat call summary Oct 27 2026: https://www.marketbeat.com/instant-alerts/transcript-innio-q3-earnings-call-highlights-2026-10-27/ |
| Data-center equipment revenue | Q2 2026 $232.4M (vs $118.0M); H1 2026 $339.4M (vs $170.3M) | 10-Q Q2 |
| Data-center order intake history | FY2025 $2,282M (vs $27M in 2023); Q1 2026 $1,005M (vs $309M) | S-1/A May 26 2026: https://www.sec.gov/Archives/edgar/data/0002109150/000119312526237848/ck0002109150-20260526.htm |
| Prime vs backup | ~80% of DC equipment backlog at Dec 31 2025 was prime power, ~20% backup | S-1/A |
| Power delivered | 1.2 GW Q3 2026; 3.0 GW YTD; FY2025 3.4 GW (2.5 GW 2024); FY2026 guide ~4.5 GW (~1.5 GW in Q4) | 8-K; call |
| Capacity plan | 3.5 GW/yr (2025) → >10 GW/yr by 2030 ("approximately a tripling"); first Jenbacher genset assembled at Waukesha WI; plants Jenbach/Hall/Kapfenberg (AT), Welland (ON), Waukesha (WI), Waller (TX), Trenton (NJ); capex 6.5% of 2025 revenue, H1 2026 PP&E adds $94.1M vs $39.4M | call; S-1/A; 10-Q |
| Lead times / slots | Slot reservations extend into 2029, 2030, 2031; 2029–30 capacity released in stages; orders mostly take-or-pay with down payments and cancellation fees; "no delays or cancellations" | call |
| Geography (Q2 2026 revenue) | Europe $315.9M (33.7%), North America $439.5M (46.9%), RoW $182.3M (19.4%) of $937.7M | 10-Q Q2 |
| Installed base | ~44 GW at Dec 31 2025; service ~$30k/MW/yr existing fleet, >$50k/MW/yr on backlog; coverage ~100 countries | call; S-1/A |
| Customer policy | No meaningful allocation to neoclouds; focus on hyperscalers, colos, EaaS, rental, IPPs | call |
| FY2026 guidance | Revenue $3.9–4.0B (raised from $3.8–3.9B); adj. EBITDA $780–800M | 8-K |

Named INNIO data-center orders (2025–26):
- Oct 21 2025: VoltaGrid 2.3 GW, 92 × 25 MW power packs (Jenbacher), "one of the world's largest data centers" (Oracle/Vantage Frontier, Shackelford Co. TX per Power Mag) — https://www.businesswire.com/news/home/20251021503080/en/
- Feb 11 2026: VoltaGrid 1.5 GW, 300 Jenbacher J624/J620 in 25 MW units, delivery by 2028, "data center customers across the United States" (sites not named) — https://www.innio.com/en/news-media/press-releases/innio-secures-additional-major-order-from-voltagrid-1-5-gw-for-behind-the-meter-power-generation/
- Apr 9 2026: Rehlko framework 1.25 GW over 3 years (incl. existing 700 MW reservation), delivered via Clarke Energy, "key global markets" — https://www.businesswire.com/news/home/20260409703981/en
- Jul 28 2026: 1.1 GW, >200 J624, unnamed mega-campus developer, "throughout the United States" — https://www.innio.com/en/news-media/press-releases/innio-wins-1-1-gigawatt-gas-engine-order-for-major-data-center-campus/
- Oct 22 2026: 620 MW follow-on from same customer → 1.72 GW cumulative; containerized J624; LTSA on first 500 MW — https://www.sttinfo.fi/tiedote/72437065/...
- Q3 2026: Liberty Energy 450 MW, BTM by 2028; Aggreko ≥450 MW Jenbacher by end-2027, partnership to 2031 — 8-K
- [Inference] Sum of disclosed DC engine orders since Oct 2025 ≈ 2.3+1.5+1.25+1.72+0.45+0.45 ≈ 7.7 GW; only the VoltaGrid 2.3 GW is publicly tied to a state (Texas). INNIO did not disclose state locations or Texas/election exposure in any filing or call reviewed.
- Texas/election: no statements found. S-1 forward-looking language cites "global instability due to United States political environment" only.

### Caterpillar (Cat large engines + Solar Turbines)
| Item | Figure | Source |
|---|---|---|
| Q3 2026 (Oct 29–30 2026) | Sales $20.7B (+17%); Power & Energy segment $8.8B (+18%), profit $2.1B (+31%); power generation sales +30% (Manufacturing Dive) / "power-generation sales rose 75%" with sales-to-users +36% (MarketBeat summary — note discrepancy; verify against 8-K) | https://www.manufacturingdive.com/news/caterpillar-posts-highest-sales-quarter-ever-data-centers-q3-2026/873176/ ; https://www.marketbeat.com/instant-alerts/transcript-caterpillar-q3-earnings-call-highlights-2026-10-30/ |
| Backlog | Record $78B, +~$38B (+96%) YoY; 4th straight quarter of sequential growth in every segment | same |
| Lead times | "taking orders for large reciprocating engines into 2029 and turbine orders into 2030" | MarketBeat |
| Capacity | "nearly tripling large reciprocating-engine capacity from 2024 levels by 2030"; Winston-Salem NC becomes second 3600-series assembly/test site; restarted 10 MW MaK units ship Q4 2026, ramp through 2027; May 1 2026: triple large-engine capacity by 2029, rollout 2027–29; large-engine backlog >3.5x since Jan 2026 | MarketBeat; https://www.pulse.bot/energy/news/caterpillar-to-triple-power-generation-capacity-raises-2030-targets-... |
| Tariffs | Q3 ~$600M cost; FY2026 ~$2.2B ex ~$520M IEEPA recoveries | Manufacturing Dive |
| Texas/election | Not mentioned in any summary reviewed | — |
| Cleanview share | 33% of tracked BTM OEM share; >8.8 GW permitted Cat engines + Solar Turbines (recips and turbines are NOT separated) | Cleanview, see §3 |
| Named non-TX recips | Socrates South (OH): 15 × Cat 3520 + 3 Titan 250 + 9 PGM 130 (Solar) + 3 Siemens SGT-400 for 200 MW (OPSB approved Jun 9 2025) | https://www.power-eng.com/onsite-power/onsite-gas-turbines-reciprocating-engines-to-power-meta-data-center/ |

### Cummins
| Item | Figure | Source |
|---|---|---|
| Q3 2026 | NOT YET AVAILABLE in retrievable sources at time of writing (Q3 2025 was Nov 6 2025). | — |
| Q2 2026 (Aug 4 2026) | Power Systems segment sales $2.3B (+19%; NA +19%, intl +19%) "driven mainly by power generation demand for data centers in the U.S., China and Asia Pacific"; segment EBITDA $552M (24.5%); external power-generation product line $744M (+27.4%), H1 $1,384M (+34.5%); Circe Energy agreement for natural gas gensets for a Texas data center, deliveries 2026–2030; FY revenue growth raised to 10–13% | https://investor.cummins.com/news/detail/701/... ; 10-Q: https://www.sec.gov/Archives/edgar/data/0000026172/000002617226000029/cmi-20260630.htm |
| Capacity | "disciplined capacity and product investments" announced at May 2026 Analyst Day; no MW/units disclosed in retrieved text | Q2 release |
| Positioning | Mostly diesel standby (Centum series); gas prime-power exposure is the Circe/Texas deal; Cummins also supplying BESS for a large US DC | Q2 release; Q3 2025 release |

### Wärtsilä (Finnish; 34SG / 50SG / 46TS medium-speed)
| Item | Figure | Source |
|---|---|---|
| Q3 2026 (Oct 27 2026) | Marine+Energy order intake €2,368M (+47%); 9M €7,178M (+40%); order book €9,876M (+22%); Energy order intake "increased" (no split); "Engine lead times continue to increase"; outlook: Energy demand next 12 months similar to comparison period | https://www.wartsila.com/usa/media/news/27-10-2026-wartsila-s-interim-report-january-september-2026-3806530 |
| Q3 named DC order | 282 MW, 15 × 50SG, US data center (unnamed) | same |
| Cumulative US DC | >1.6 GW sold into US data center market as of Apr 16 2026 (4th US DC order) | https://www.wartsila.com/media/news/16-04-2026-wartsila-s-34sg-engine-makes-its-data-center-debut-with-new-412-mw-u-s-project-3740972 |
| Ohio | 412 MW, 40 × 34SG, hyperscale DC in Ohio, off-grid, COD early 2028 (Apr 16 2026) | same |
| Other US | 507 MW, 27 × 50SG, deliveries from 2027 (Nov 27 2025); Liberty Energy 34SG order €292M, deliveries 2029–2030 (Jun 29 2026); 429 MW turbines to US DC plant (Feb 2026, DCD — not fetched) | https://bebeez.eu/2025/11/27/... ; https://www.wartsila.com/media/news/29-06-2026-... |
| Lead time | Liberty order delivering 2029–30 implies ≥3-year lead for new 34SG orders placed mid-2026 [Inference] | — |

### Rolls-Royce Power Systems (mtu Series 4000)
| Item | Figure | Source |
|---|---|---|
| H1 2026 (Jul 30 2026) | Underlying revenue £2,604M (+28%); op. profit £528M (+72%), margin 20.3%; order intake £4.6B (+>50%), book-to-bill 1.8x; power generation revenue +41%; power generation order intake +55% "driven by backup and prime power demand for data centres"; OE order coverage ~100% of 2026, >50% of 2027; PG OE revenue growth target raised to 25% p.a. to 2030 (from 20%); CFO: DC energy orders +>50% (contracted pipeline) | https://www.rolls-royce.com/~/media/Files/R/Rolls-Royce/documents/investors/rr-holdings-plc-2026-half-year-results-press-release.pdf ; MarketScale Aug 11 2026 |
| FY2025 (Feb 27 2026) | Revenue €5.72B (+19%), RoS 17.4%, order intake €7.14B (+21%); capex "high three-digit million euro"; new Friedrichshafen Series 4000 plant from 2028; Aiken SC and Mankato MN expansions (Mankato +23,000 m²; $24M, opened Jul 2026) | https://mtu-solutions.com/eu/en/pressreleases/2026/Strong-results-and-record-investments-... ; MPR News Jul 9 2026 |
| Product | Fast-start mtu gas gensets for DC launched Oct 2 2025; "growing demand for Series 4000 gas reciprocating engines as prime power" | RR H1 2026 |
| Data-center share | Not disclosed | — |

### Everllence (ex-MAN Energy Solutions; 51/60G, 35/44G)
- Jul 29 2026: 480 MW, 24 × 18V51/60G, off-grid US hyperscale DC (unnamed, state not given), two phases from mid-2026, SCR + oxidation catalyst; 51/60 family installed base 8 GW — https://www.everllence.com/company/press-releases/details/2026/07/29/everllence-to-supply-480-mw-for-off-grid-data-center-in-the-u.s
- Order backlog/capacity for DC not disclosed.

### Bergen Engines (Langley Holdings; B36:45 medium-speed)
- Jun 3 2026 (body dated Oct 12 2026): Crusoe ~750 MW = 438 MW firm (27 × B36:45V20AG2 @12.5 MWe + 20 × B36:45L9AG @5 MWe) + 310 MW LOI; multiple unnamed US sites; phased through 2027; Marelli alternators + Piller SHIELD-X — https://crusoe.ai/resources/newsroom/bergen-engines-signs-approx-750mw-u-s-power-agreement-with-crusoe-for-ai-data-centers
- May 8 2026: Liberty Energy 500 MW of orders (Langley release, not fetched).

### Mitsubishi (MHI / MHIET)
- Gas turbines dominate: FY H1 (to Sep 30 2025) 23 large-frame GT units, >2x prior pace, mostly US/Asian DC & semiconductor; order intake up ~¥675B; MHI plans to double GT manufacturing capacity through 2028 (WoodMac via Power Engineering Apr 1 2026). No MHIET reciprocating-engine data-center orders found. — https://www.energytech.com/data-center-power/article/55329126/... ; https://www.power-eng.com/gas/turbines/gas-turbine-prices-climb-195-...

### Kohler / Rehlko
- Jun 1 2026: new Kenosha WI assembly site for eFRAME enclosures up to 4 MW; initial production late 2026, full early 2027; plans to "expand capacity by more than 400% through the decade" — https://www.businesswire.com/news/home/20260601364088/en/
- Apr 9 2026: 1.25 GW INNIO Jenbacher framework (see INNIO). Jun 17 2026: Liebherr engine capacity partnership (not fetched).

### Generac
- Q3 2026 (Oct 28 2026): net sales $1,294.8M (+16%); C&I $552.1M (+28%) "ramping revenue from products sold into the global data center market"; data-center backlog "approximately $4.5 billion"; Amazon long-term supply agreement, initial deliveries $2.4B in 2027–2028; FY26 adj. EBITDA margin 20.5–21.0% — https://www.sec.gov/Archives/edgar/data/0001474735/000143774926033685/ex_1032565.htm
- Positioning: large diesel standby; no gas prime-power DC orders found.

### Other engine OEMs surfaced
- 2G Energy (Germany): largest order in history, "lower triple-digit MW" containerized CHP for a North American DC client, deliveries late 2026; 2026 revenue guide raised to $484–539M (May 28 2026) — https://www.pulse.bot/climatetech/news/2g-energy-benefits-from-the-ai-boom-...

---

## 2. Non-Texas BTM gas projects (status, OEM, technology)

Technology key: R = reciprocating engines, T = gas turbines, FC = fuel cells, CC = combined cycle. Permit status per cited source.

### Pennsylvania
- **Homer City (Indiana Co.)** — 4.5 GW (EIP lists 4,678 MW), Kiewit EPC, GE Vernova 7HA turbines (T, CC), coal-to-gas redevelopment; announced Apr 2 2025. EIP (Jul 1 2026) counts 6 western-PA DC gas plants. Status beyond announcement not confirmed in retrieved sources. — https://www.businesswire.com/news/home/20250402452555/en/ ; EIP: https://environmentalintegrity.org/wp-content/uploads/2026/06/EIP-Data-Center-Power-Report-EMBARGOED-for-7.1.26.pdf
- **Shippingport Power Station (Beaver Co.)** — 3,641 MW (EIP Appendix C; est. NOx 1,275 t/yr). Technology/OEM not in retrieved text.
- **Amazon Falls Township (Bucks Co.)** — THIS is the "280 engines in Pennsylvania": DEP Plan Approval application (Apr 2026) for **280 natural-gas-fired "critical backup" generator engines at 4,287 hp each (~3.2 MW, consistent with J620-class [Inference]) + 3 diesel emergency engines**, on top of 72 diesel emergency engines approved Jul 2025 (PA 09-0261). **Backup only**, synthetic-minor NOx cap 24.9 t/yr; 1,236 public comments; comment period closed Aug 17 2026; DEP decision date not set. DEP fact sheet does NOT name the OEM. — https://files.dep.state.pa.us/RegionalResources/SERO/SEROPortalFiles/Community%20Info/AmazonDCFallsTwp/Air%20Quality%20Plan%20Approval%20Phase%202%20Fact%20Sheet.pdf ; https://www.inquirer.com/news/pennsylvania/amazon-data-center-bucks-county-permit-20260820.html
  - [Inference] If these are Jenbacher units, 280 × ~3.1 MW ≈ 870 MW of backup-rated engines — a large INNIO order but NOT prime-power BTM; runtime limited to outages/testing.
- **Policy:** Gov. Shapiro EO 2026-05 (Aug 18 2026): DCs >25 MW applying after Aug 18 2026 must "build, bring or buy" incremental capacity; backup must be zero-emission or Tier-4-equivalent; generator runtime limited to emergencies/testing; removed from Permit Fast Track; Clean Firm Energy 10% (2027–29) → 14.5% (2030–34) → 32% (2035+); penalties $25k–100k/MW/day. Does not explicitly ban prime-power recips but adds non-COA track delays. — https://www.morganlewis.com/zh-cn/pubs/2026/08/governor-shapiro-issues-executive-order-...

### Ohio
- **Williams Socrates North & South (New Albany, Meta/"Sidecat LLC")** — 2 × 200 MW; South approved by OPSB Jun 9 2025: 15 × Caterpillar 3520 (R) + 3 Solar Titan 250 + 9 Solar PGM 130 + 3 Siemens SGT-400 (T) + 8 Cat C15 black-start; not grid-connected; target in service Nov 2026. Nvidia reported investing in a "huge Ohio gas plant" (Energy Intelligence, not fetched). — https://www.power-eng.com/onsite-power/onsite-gas-turbines-reciprocating-engines-to-power-meta-data-center/
- **EdgeConneX PowerConneX New Albany Energy Center** — up to 120 MW, primary power for colocated DC; construction Q4 2025, COD as early as Q1 2026; OEM not stated. Cleanview: Meta+EdgeConneX = 736 MW under construction, Ohio leads nation in BTM under construction. — https://www.power-eng.com/news/onsite-gas-plants-proposed-for-data-centers-in-ohio/ ; Cleanview
- **Wärtsilä 412 MW Ohio hyperscale** — 40 × 34SG (R), off-grid, COD early 2028; customer undisclosed (Apr 16 2026). — Wärtsilä release above
- **Portsmouth Powered Land Project (OH)** — 9,200 MW proposed (EIP; est. NOx 3,221 t/yr); technology not retrieved.
- **SB Energy 9.2 GW Ohio gas plant** (US-Japan deal tranche, pulse.bot headline; not fetched).
- EIP counts 10 proposed DC gas plants in Ohio; Ohio paused new DC sales-tax exemption requests May 2026.
- **Correction:** "Nexus Hubbard" is in **Hubbard, Hill County, Texas** (600 MW campus; EIP lists 7,227 MW power plant, NOx 1,550 t/yr; TCEQ major-source air permit notice Sept 2026), not Ohio. — DCD; Texas Tribune Oct 20 2026

### Louisiana
- **Meta Hyperion (Richland Parish)** — utility-side, not BTM engines: LPSC approved 3 Entergy gas plants (2025); Mar 2026 Meta to fund 7 more → 10 plants, ~7.5 GW, $11B, pending LPSC. Entergy broke ground Dec 2025 on two Richland Parish plants (turbomachinery mag). OEM not in retrieved text (Entergy's CC plants are typically Mitsubishi/GE [Inference, unverified]). — https://thelensnola.org/2026/03/30/...
- "Franklin Farms" = the original codename for the Meta Richland Parish site (Nov 2024 "mystery $5B" reports). No separate BTM engine project found.
- Hut 8 River Bend (West Feliciana) — Entergy-served, $10–12B; no BTM engines found.

### Wyoming
- **Project Jade / Tallgrass (Cheyenne)** — DC 1.8 GW scalable to 10 GW; Tallgrass power hub 2.7 GW from two gas plants (turbines, OEM unspecified), $7B, CO2 to Tallgrass sequestration hub (45Q $85/t). **Crusoe demobilized and left the project** (reported ~Oct 2026); Tallgrass says tenant unchanged, "full steam ahead"; county site plans approved Jan 2026; original schedule: energize Q2 2027. EIP counts 4 WY DC gas plants. — https://www.wyomingnews.com/news/local_news/crusoe-pulls-out-of-project-jade-data-center/...

### Georgia
- **VoltaGrid / Serverfarm, Covington (Newton Co.)** — 90 MW, 33 RICE (OEM not stated in press; VoltaGrid's platform is Jenbacher [Inference]); construction began before air permit; EPD consent orders Sep 30 2026: fines $11,500 (VoltaGrid) + $31,000 (Serverfarm); project allowed to proceed under revised permit, single-source treatment, max 30 of 33 engines running; **Georgia PSC reviewing whether VoltaGrid violates Territorial Act / who may generate & distribute electricity** — unresolved. — https://www.ajc.com/business/2026/10/data-center-power-plants-fines/ ; https://mgrid.org/?p=14380

### Washington
- **VoltaGrid QWA1, Quincy (Grant Co.)** — 14 × Jenbacher J620 (4,601 bhp each) + 1 black-start, 30 MWe, each with SCR + oxidation catalyst; Ecology draft NOC order Jul 2026; synthetic minor; NOx 0.14 lb/hr per engine, facility NOx 8.7 t/yr, NH3 slip 5 ppmv; no annual hour limit (fuel cap 3,481 MMscf/yr). Customer unnamed (Quincy = Microsoft/Sabey/Vantage hub [Inference]). — https://ecology.wa.gov/202606voltagriddrftpermit

### New Mexico
- **Stargate Project Jupiter (Doña Ana Co., STACK/Blue Owl, Oracle tenant)** — 2.45 GW onsite; plan shifted to Bloom fuel cells (FC) (Bloom share rose to 14% in Cleanview on this deal); Energy Transfer gas pipeline permits repeatedly denied by NM State Land Office, pipeline slipped to Feb 1 2027; NMED air permit decision for fuel cells due Nov 23 2026; Oracle sent force majeure notice Sep 24 2026 (Bloomberg); 2028 target; Cleanview: "likely to miss 2027 target". — https://dealroom.co/news/156472-...

### Wisconsin
- **Stargate Port Washington (Vantage "Lighthouse")** — 1.3 GW, **grid-supplied** (developer claims 70% solar/wind/battery), construction from Q1 2026, completion Q4 2028 (Epoch AI Apr 17 2026). No onsite gas generation found. Microsoft Mount Pleasant: not researched (budget).
### Michigan
- **Stargate Saline Township (Related Digital "The Barn", Oracle)** — 1.4 GW, **DTE grid 100%** + Oracle-financed battery; MPSC conditional approval Dec 18 2025 (AG appealed); $16B; "major construction underway" Apr 25 2026. No onsite gas. — https://www.michiganpublic.org/economy/2026-04-25/...
### Oklahoma
- SB 480 (2025) allows DCs to build own plants (must include natural gas). Most announced DCs (Google Muskogee/Stillwater via OG&E; IREN Kiowa via PSO) are grid-connected; only Chickasha and a Tulsa Port manufacturer mention onsite power, no MW/OEM. — https://oklahomavoice.com/?p=20755
### Arizona
- Project Baccara (Maricopa Co., $10B) approved Feb 2026 amid opposition; Glendale "Project Eagle" 700 MW gas plant for DC campus (ACC vote); Balterra 593-acre BTM-optional campus (Planning Commission Aug 6 2026, no MW/OEM). Technology/OEM not retrieved. — newprojectmedia Aug 25 2026
### Virginia
- Vantage Sterling: 8 × Solar SMT-130 turbines operating since Sep 2025 (100% of site load) — Cleanview Jun 3 2026. VA DEQ proposed presumptive BACT for non-emergency DC generators (diesel): NOx 0.60 g/hp-hr with SCR, applies to applications after Jul 1 2026; gas RICE not addressed. — https://trinityconsultants.com/resources/virginia-deq-...
### Utah / Nevada / West Virginia / New Jersey / Mississippi (from EIP/Cleanview)
- Utah: Stratos/Wonder Valley 9,000 MW proposed (EIP; est. NOx 2,660 t/yr); Oracle trucking gas to Utah & Texas sites (DCD). Nevada: not retrieved. WV: Monarch Compute 8,160 MW; Ridgeline 1,656 MW; Tucker Co. hours-restricted to stay minor. NJ: Microsoft/Nebius 400 MW onsite gas plant, air permit pending (7 of 9 compute tranches depend on it). MS: xAI Southaven 1,240 MW turbines (permit Mar 11 for 41 turbines).

### Recips vs turbines vs fuel cells — what the non-Texas record shows
- Recips (confirmed): Socrates South (15 × Cat 3520 — hybrid with turbines), Wärtsilä Ohio 412 MW, VoltaGrid Georgia 90 MW, VoltaGrid Washington 30 MW, Everllence 480 MW (state unknown), Bergen/Crusoe 750 MW (states unknown), INNIO 1.72 GW + 1.5 GW (states unknown).
- Turbines: Homer City 4.5 GW (7HA), Tallgrass WY 2.7 GW, xAI TN/MS ~2.7 GW, Vantage VA 8 × SMT-130, ProEnergy >1 GW (2 projects), Chevron 2.5 GW W. Texas (7HA), Solaris fleet.
- Fuel cells: Project Jupiter NM 2.45 GW (Bloom); AEP up to 1 GW Bloom (2024).
- [Inference] Non-Texas prime-power recip capacity with a known state totals <1 GW confirmed; the multi-GW INNIO/Bergen/Everllence orders are "US, undisclosed," so Texas vs non-Texas exposure of the recip order book cannot be verified from public sources.

---

## 3. Cleanview reports — what is public

**"Bypassing the Grid" (Feb 3 2026):** 46 BTM data centers, 56 GW (~30% of planned US DC capacity); ~90% (~50 GW) announced in 2025; equipment identified at ~2/3 of projects; gas ≈75% of identified equipment (~23 GW of ~31 GW identified); OEMs named GE Vernova, Caterpillar, Siemens, Doosan; turbine lead times 5–7 yrs. No shares. — https://newsletter.cleanview.co/p/bypassing-the-grid-how-data-centers ; Contrary (May 7 2026) adds: five states TX, NM, PA, UT, WY = 83% of proposed BTM capacity (Feb dataset) — https://research.contrary.com/report/mapping-the-shadow-grid

**"Data Center Developers Want to Build Their Own Power Plants" / BTM report (Jun 3 2026, updated mid-2026):** 59 projects, ~90 GW (>25% of planned US DC capacity); 92% (~82 GW) announced since Jan 2025. Status: operating ~2 GW (2.2%), under construction 1.2%, permitted 36%, announced/early 60%. Projections: 2.8–3.2 GW end-2026; 13 GW cumulative end-2027 (on-time) or ~5 GW (delays). Five states = 83% (state list not published on free page; Texas leads announced, Ohio leads under-construction with 736 MW). **OEM share (free page): Caterpillar 33% (>8.8 GW permitted Cat engines + Solar Turbines, combined), Bloom 14%; "top 10 OEM estimates" are in the paid report only.** No reciprocating-engine MW count published anywhere free. — https://cleanview.co/reports/behind-the-meter-data-centers?stream=top ; https://newsletter.cleanview.co/p/data-center-developers-want-to-build

**Alternative primary dataset — EIP (Jul 1 2026, cutoff Apr 30 2026):** 74 proposed DC gas plants ≥100 MW (71 new + 3 expansions), 143 GW; by state count TX 32, OH 10, PA 6, WV 4, WY 4; permit status: 43 no application, 15 pending, 4 draft, 24 final (4 under construction); ≥16 combined-cycle plants = 40,896 MW; simple-cycle turbines "most common" among recent permits; total NOx 44,281 t/yr (assuming 2 ppm with SCR, 8,760 h). EIP does not split recips vs turbines. — EIP PDF above

Gap: a verified recip-specific MW figure for US BTM does not exist in public sources; Cleanview's tracker (paid) is the only candidate.

---

## 4. Energy-as-a-service providers and their OEMs

| Provider | OEM / technology | Scale & status | Source |
|---|---|---|---|
| **VoltaGrid** (Houston) | INNIO Jenbacher J620/J624 in 25 MW QPac; acquiring Propell Energy Technology (manufacturing partner); two Granbury TX plants targeting ~300 MW/month **across reciprocating engines AND turbines** | Order book ~7.5 GW through 2030; Oracle 2.3 GW, Vantage 1 GW, xAI; $1B equity (Blackstone $775M primary + $225M secondary, Halliburton) closing mid-2026; Halliburton JV for Middle East with 400 MW manufacturing for eastern hemisphere; weighing IPO/sale (Bloomberg Feb 24 2026); Georgia & Washington permits above | https://www.datacenterdynamics.com/en/news/voltagrid-raises-1bn-... |
| **Solaris Energy Infrastructure** | Simple-cycle gas turbines (OEM not stated in offering memo; fleet understood to be Solar Turbines/Baker Hughes-class small units [Inference, unverified]) | ~950 MW operated avg Q2 2026; >3,300 MW scheduled by end-2029; contracts: Stateline ~900 MW (7 yr), Hatchbo ~660 MW (to 18 yr), Customer C ~640 MW (10+5 yr); bought 30 turbine slots (>500 MW, 2027–29), 2 turbines $114M (66 MW), Genco ~400 MW; 2026 capex ~$1,955M | https://www.sec.gov/Archives/edgar/data/0001697500/000119312526397255/d182097dex991.htm |
| **ProEnergy** | PE6000 48 MW aeroderivative rebuilt from CF6-80C2 cores | 21 turbines sold for two DC projects (>1 GW); 650 MW of 50 MW units for AI facilities (Apr 2026); 5–7 yr bridging; deliverable 2027 vs OEM 2029+ | https://www.datacenterdynamics.com/en/news/proenergy-offers-repurposed-jet-engines-to-data-cent/ |
| **Crusoe** | Bergen recips ~750 MW; 29 GE Vernova LM2500XPRESS (Jul 2025); Abilene onsite gas; **cancelled $1.25B / 29 × 42 MW Boom Superpower order Sep 25 2026** ("sourcing, not strategy"); left Tallgrass WY | Boom still targets 250 MW deliveries 2027, 1 GW 2028, >4 GW/yr by 2030, with no launch customer | https://baxtel.com/news/crusoe-ends-1-25b-boom-supersonic-turbine-order-for-ai-data-centers |
| **Williams (Socrates)** | Solar Turbines + Siemens SGT-400 + Caterpillar 3520 recips | 400 MW New Albany OH for Meta; in service target 2H/Nov 2026 | Power Eng Jun 11 2025 |
| **Chevron + Engine No. 1 + GE Vernova** | 7HA frame turbines | 2.5 GW West Texas, ops 2027, expandable to 5 GW; partnership for up to 4 GW incl. sites outside Texas (OEM slots secured) | https://gcn.com/?p=14198 |
| **ExxonMobil** | Gas + CCS; with NextEra controls a 1.2 GW Gulf Coast site; 1.5 GW standalone plan | Marketing to DC customers; no FID found | Power Eng Dec 11 2025 |
| **NextEra** | 4 GW GE Vernova turbine slots; "aeroderivatives" as bridge; renewables+storage first | 15 GW DC hubs by 2035 (30 GW upside); gas pipeline >20 GW across 11 states; 4–8 GW new gas through 2032; CEO: "market is heading towards bring your own generation" | https://www.power-eng.com/onsite-power/nextera-leans-into-bring-your-own-generation-... |
| **Constellation/Calpine** | Co-located gas (Freestone 380+380 MW, Bosque 400 MW, Texas/CyrusOne) | "Powered Land" strategy; grid-connected co-location rather than islanded BTM | https://www.energytech.com/data-center-power/article/55356592/... |
| **Vistra** | Not retrieved (budget) | — | — |
| **Liberty Energy** | Multi-OEM: INNIO 450 MW (by 2028), Wärtsilä 34SG €292M (2029–30), Bergen 500 MW (May 2026) | Diversifying recip supply across three OEMs [Inference: indicates allocation constraints at any single OEM] | INNIO 8-K; Wärtsilä; Langley |
| **Aggreko / Rehlko-Clarke** | INNIO Jenbacher (≥450 MW by 2027; 1.25 GW framework) | Rental/EaaS channel | INNIO |

---

## 5. International
- INNIO geography (Q2 2026 revenue): Europe 33.7%, North America 46.9%, RoW 19.4% — so Europe is about one-third, not half, of current revenue; installed-base split by region not disclosed in retrieved filings.
- Europe DC prime-power engines: only small precedents found — Winthrop/Dublin 60 MW, 22 Jenbacher Type 6 (Nov 2022, backup/grid-stabilization). 2G Energy's record order is for North America, not Europe. No 2026 European BTM gas-engine DC order of scale found. [Inference] European demand remains grid/CHP/backup-led; the US is the prime-power market.
- Middle East: VoltaGrid–Halliburton partnership "initially focused on the Middle East" with 400 MW of manufacturing for eastern-hemisphere data centers (DCD, 2026). No specific UAE/Saudi Jenbacher BTM DC project found within search budget.
- Asia: MHI gas-turbine orders from Asian DC/semiconductor customers; Wärtsilä 300 MW Australia (13 × 46TS-SG) is grid balancing, not DC.

---

## 6. Secondary-market turbines and the substitution question
- New-turbine pricing: WoodMac — prices +195%, ~$600/kW by end-2027 (≈3x 2019); 6-year lead times; global GT orders 110 GW at end-2025 vs 60–70 GW/yr capacity; developers seeking 63 GW for 2026–30; GE Vernova to 70–80 large frames/yr by late 2026, MHI doubling to 2028 (Apr 1 2026). JPMorgan — Q2 2026 GT orders ~38 GW record (+71% YoY; Siemens Energy ~12.5, GE Vernova ~11.3, Mitsubishi ~5.3 GW); CCGT delivered 2031 costs ~3x one delivered 2025 (Aug 11 2026). Installed CCGT project costs $1,116–1,427/kW near-term vs ≥$2,000/kW for 2030–31 CODs; $25M slot reservation fees (Latitude Sep 2025).
- Secondary/used turbine prices: no quantified resale price index found in retrievable sources (Bloomberg Apr 1 2026 "Gas-Turbine Prices Surge" paywalled). Rebuilt aero (ProEnergy PE6000, FTAI CFM56→25 MW) marketed on 2027 delivery vs OEM 2029+; Boom order implied ~$1,000/kW (order value/MW, approximate).
- Substitution evidence FOR "recips as stopgap": ProEnergy customers explicitly treat turbines as 5–7-year bridging until grid interconnect; Cleanview/Pipeline & Gas Journal frame speed-to-power as the driver; Crusoe cites "sourcing, not strategy" when switching suppliers.
- Evidence AGAINST fade: (a) INNIO has slot reservations into 2031 and take-or-pay with cancellation fees; (b) Caterpillar is taking large-recip orders into 2029 and tripling capacity to 2029–30 — OEMs are investing on a >2030 horizon; (c) INNIO claims J624 water use <0.1 L/MWh vs ~200 L/MWh for turbines and up to 10-pt efficiency advantage at small block sizes; (d) >90% of planned DC capacity additions come in ≤200 MW increments (S-1), a size band where recips/aeros compete on cost with small frames (small turbines up to 50% higher $/kW than large per PGJ); (e) GasTurbineHub argues the modular lane persists post-normalization. (f) Wärtsilä says engine lead times are still lengthening (Oct 2026).
- [Inference] The public record supports "both": recips are capturing demand that frame turbines cannot serve before ~2029–30, but the contracted structure (take-or-pay, LTSAs of 10–15 years, 7-year EaaS tenors) means revenue through ~2030 is largely locked regardless; the open question is 2030+ order intake, on which no OEM has given guidance.

---

## 7. Emissions and state restrictions on prime-power recips
- Permit-level NOx for Jenbacher J620 with SCR+oxidation catalyst (WA Ecology, VoltaGrid QWA1, Jul 2026): 0.14 lb/hr per 4,601 bhp engine ⇒ ≈0.014 g/bhp-hr ≈ 0.02 g/kWh-e [my conversion]; facility 8.7 t NOx/yr for 30 MWe; NH3 slip 5 ppmv; CO 0.66 lb/hr; formaldehyde 0.10 lb/hr. Uncontrolled lean-burn J620 datasheet basis: 250 or 500 mg/Nm³ NOx @5% O2 (Jenbacher).
- Everllence 51/60G: SCR + oxidation catalyst to meet "strict" US standards (no numbers).
- EIP modeling assumption for DC gas plants: NOx 2 ppm / 0.0075 lb/MMBtu with SCR; engine heat rate 9,025 Btu/kWh vs 10,688 simple-cycle, 7,614 CC.
- Virginia DEQ proposed presumptive BACT (applications after Jul 1 2026): diesel non-emergency DC gensets NOx 0.60 g/hp-hr with SCR (≥30 L/cyl: 1.6 g/kWh or ≥90% control), DOC/DPF Tier-4 equivalent; gas RICE not covered.
- SCR cost (EPA fact sheet, 1999$): 70–90% NOx removal; catalyst life ~40,000 h on gas; $2,000–10,000/ton NOx for small GT; ammonia slip permits 2–10 ppm. No RICE-specific catalyst replacement $ found in budget. [Inference] At 8,000 h/yr, 40,000 h ≈ 5-year catalyst life for prime-power duty.
- State restrictions:
  - **Pennsylvania** EO 2026-05: Tier-4-equivalent or zero-emission backup; runtime limits; non-COA permit track non-rolling; DEP to study cumulative multi-generator impacts. No explicit prime-power recip ban.
  - **Georgia**: EPD consent orders (Sep 30 2026) + PSC jurisdictional review of VoltaGrid under Territorial Act — potential precedent restricting third-party BTM sales.
  - **Texas**: Abbott directed TCEQ Sep 21 2026 to pause all DC-related permits (air permits for gas plants and diesel gensets, stormwater); TCEQ confirmed pause Oct 19–20 2026 and shut automatic filing; no end date; Public Citizen says permits kept issuing (≥6 stormwater; Nexus Hill Co. air notices). Gov.-elect Hinojosa's platform (Jul 23 2026): emergency EO halting new DC approvals until legislature acts; ban NDAs; end subsidies; ratepayer proof; no explicit BTM position. — https://www.texastribune.org/2026/10/20/data-center-permits-tceq-abbott-texas-pause/ ; https://ginafortexas.com/2026/07/...
  - **Ohio**: OPSB siting required for ≥50 MW (Socrates approved); tax-exemption pause May 2026; no engine-specific restriction retrieved (search budget).
  - **Oklahoma**: SB 480 affirmatively permits BTM with gas.
  - **New Mexico**: pipeline permit denials (State Land Office) effectively blocked gas combustion at Jupiter → fuel-cell pivot.
  - **Washington**: synthetic-minor NOC path available (30 MW block).
- Election (Nov 3 2026): no OEM statement found. [Inference] Texas pause + Hinojosa platform raise permitting risk for the Texas-concentrated BTM pipeline (EIP: 32 of 74 plants; Cleanview: Texas leads announced capacity), which could redirect EaaS fleets (VoltaGrid/Liberty/Aggreko units are containerized and redeployable) to OH, PA, OK, WY, WA, GA — subject to PA EO, GA PSC and local opposition.

---

## Open questions
1. Cleanview paid tables: top-10 OEM shares, state GW, and any recip-specific MW.
2. State-level siting of INNIO's 1.72 GW (unnamed mega-campus developer), 1.5 GW VoltaGrid, Everllence 480 MW, Bergen 750 MW — how much is Texas?
3. Cummins Q3 2026 release (due early Nov 2026) — power generation growth, DC backlog, gas prime-power commentary.
4. Caterpillar 8-K/10-Q: reconcile +30% vs +75% power-generation growth; any Texas comment on call.
5. Wärtsilä Ohio 412 MW customer/site and OPSB docket; Williams Socrates Phase 2 / Nvidia involvement.
6. Georgia PSC ruling on VoltaGrid (Territorial Act) — timing and precedent.
7. Texas: duration of TCEQ pause; what Gov.-elect Hinojosa does on Jan 2027 inauguration; any special session.
8. Secondary-market turbine price index (Bloomberg Apr 1 2026) and INNIO/Cat 2030+ order guidance to test the "substitution fades" thesis.
9. Gulf BTM Jenbacher projects via VoltaGrid–Halliburton; INNIO installed base by region.
10. RICE SCR catalyst replacement cost ($/kW or $/MWh) from an engine OEM or permit TSD.
