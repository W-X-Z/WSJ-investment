# Texas data center pause (2026): what is actually paused, and is behind-the-meter (BTM) gas generation caught?

Research date: 2026-11-05. Primary documents were downloaded and read in full where marked [PRIMARY, full text]. Secondary sources marked [SECONDARY]. Inferences are marked INFERENCE. No investment conclusions.

Downloaded primary PDFs/HTML are in `/tmp/claude-0/-home-claude/aa25ba7a-5d7a-55a2-b37a-539f5344d62c/scratchpad/deep/dl/` (aug3.pdf, tceq.pdf, tceq_resp.pdf, rfi_q.pdf, audit.html, 182126-pls-english.pdf, 19875-nori-english.pdf).

---

## 0. Bottom line on the BTM question

There are TWO distinct pauses with DIFFERENT scopes:

| Pause | Instrument | Scope (by its own text) | Does it reach a fully islanded BTM data center? |
|---|---|---|---|
| A. Aug 3, 2026 — ERCOT/PUCT interconnection pause | Governor's letter to PUCT Chair Gleeson & ERCOT CEO Vegas | "all data centers advancing through ERCOT's interconnection process" | **No, by its text.** Only projects in the ERCOT interconnection process. ERCOT's RFI applies to Batch Zero (≥75 MW) loads and 25–75 MW "Substantiated Loads" reported by TSP/DSPs. A project that never requests grid interconnection is not in this population. (mgrid.org and Texas Tribune both note on-site-generation projects were seen as a way to bypass this pause.) |
| B. Sep 21, 2026 — TCEQ permit pause | Governor's letter to TCEQ ED Kelly Keel | "halt all permits sought by data centers" / "pause the issuance of all permits related to data center projects until ERCOT completes its review" | **Yes, as written — no grid-connection carve-out.** The letter contains no MW threshold, no definition of "data center project", and no exemption for off-grid/on-site generation or for non-ERCOT regions. TCEQ's Oct 19 compliance letter says it paused "all permits related to the construction or development of infrastructure directly supporting data centers" — language that on its face covers an air permit for a gas plant whose purpose is to power a data center. Law firms (Bracewell, Beveridge & Diamond, White & Case) read it as covering islanded projects. BUT: the pause is on **issuance**, not necessarily on **processing** (Governor's office: "the pause applied to approval, not processing"); TCEQ mailed preliminary-decision notices for VoltaGrid ABI-1 (Shackelford) and Nexus Hubbard (self-powered) on Sept 22 and expedited generator applications in October (FracTracker). |

Key undetermined points: (1) TCEQ has published no formal definition of "data center project" or list of covered permit types; it screens case-by-case. (2) Whether a generation facility owned by a separate legal entity (e.g., VoltaGrid as IPP selling to Vantage) is "related to a data center project" is not addressed in any TCEQ document found. (3) PBR / standard-permit registrations that are "claimed" without affirmative issuance: TCEQ says it is "screening claimed authorizations ... and, where possible, is suspending such authorizations for data center activities" — partial, not categorical. (4) Already-issued permits (e.g., Fermi America Project Matador, Feb 2026; Pacifico GW Ranch, Jan 2026; Stargate Abilene's original turbines via PBR/standard permits in 2024) are NOT revoked by anything in either letter; the letters are forward-looking on issuance. INFERENCE: existing authorizations continue; expansions/modifications (e.g., Crusoe NSR 182126, Abilene Master Assoc. 182267) are caught.

---

## 1. Abbott's directives — full text

### 1a. August 3, 2026 letter to PUCT & ERCOT [PRIMARY, full text]
URL (PDF): https://gov.texas.gov/uploads/files/press/Thomas_Gleeson_Pablo_Vegas_Data_Centers_Directive_Letter_to_PUCT_ERCOT_August_2026_.pdf
Press release: https://gov.texas.gov/news/post/governor-abbott-directs-comprehensive-data-center-audit (Aug 3, 2026; subhead "Audit Must Be Completed Before Any Data Center Project Moves Forward")

Operative text (verbatim):
> "The Electric Reliability Council of Texas (ERCOT) is currently considering approximately 474 gigawatts of requests to connect to the Texas grid. That is more than five times Texas' record peak electricity demand for ERCOT. Approximately 90 percent of the new power requests are data centers."
>
> "To keep the grid stable and reliable, I am issuing the following directive: The Public Utility Commission of Texas (PUC) and ERCOT must conduct a comprehensive verification and audit of all data centers advancing through ERCOT's interconnection process before any additional data centers are approved to move forward. Any project that fails to comply with the requirements set forth by the PUC and ERCOT, and by state law, must be denied connection to the Texas grid."
>
> "The failure of some data centers to comply with the PUC's survey measuring water and power usage under the General Appropriations Act makes this necessary."

Information to be obtained "from each data center project" (five bullets, verbatim summary):
1. "all state and local tax incentives, grants, abatements, or other public financial assistance received or expected to be received"
2. "The extent to which data centers are providing their own power or depending on the ERCOT grid for that power. Details should include projected annual and peak electricity consumption; and any effort and progress to construct or procure on-site electric generation, including generation type, or other measures to reduce demand on the ERCOT grid"
3. Water: "projected annual and peak water consumption and anticipated sources of water supply ... cooling technology ... air-cooled, closed-loop, or another water-efficient cooling system"
4. Community: "noise mitigation, light controls, setbacks, traffic improvements, emergency response coordination"
5. "Information detailing the ownership and controlling interests in the project."

> "Any data center project that fails to comply with the verification and audit process to protect the reliability and resilience of the Texas electric grid must be denied. Simply put, Texans must come first."

Observations:
- No definition of "data center". No MW threshold in the letter (ERCOT set 25 MW in its RFI). No deadline in the letter (ERCOT later set Dec 10).
- No exemption language for under-construction or already-approved projects. ERCOT's Chad Seely counted 17 large loads (~6.6 GW) that had cleared stability assessment and expected to energize in 2026 — "They still face the audit" (mgrid.org Sept 5). Inside Climate News (Aug 24) quotes grid operator: "No large data centers will be approved to come online in Texas until after the November midterm elections."
- BTM: the letter *asks about* on-site generation but its operative pause applies only to projects "advancing through ERCOT's interconnection process."

### 1b. September 21, 2026 letter to TCEQ [PRIMARY, full text]
URL (PDF): https://gov.texas.gov/uploads/files/press/TCEQ_Data_Center.pdf
Addressee: Ms. Kelly Keel, Executive Director, TCEQ.

Verbatim:
> "With this letter I am directing the Texas Commission on Environmental Quality (TCEQ) to halt all permits sought by data centers."
>
> "As you know, I directed the Public Utility Commission of Texas (PUC) and the Electric Reliability Council of Texas (ERCOT) to thoroughly audit all data centers undergoing ERCOT's interconnection process ... I also directed the Texas Water Development Board (TWDB) to compel data centers to comply with water use reporting requirements and to impose legal consequences for past and future failure to comply with state law. Additionally, I directed TWDB to partner with ERCOT on its upcoming audit of data centers to seek additional water use information."
>
> "Because the information sought by the PUC, ERCOT, and TWDB is necessary to make informed decisions by each of those agencies, no other state agency shall move forward with regulatory approvals related to data centers until this information is acquired. Therefore, I direct the TCEQ to pause the issuance of all permits related to data center projects until ERCOT completes its review."
>
> "Data center projects must cover all electrical infrastructure costs, result in lower residential electrical bills, and complete the ERCOT and TWDB audits. Further, data centers must not use water needed by local communities, must report electricity and water usage, and must abide by setback requirements that will protect the communities in which they operate. Finally, I will work with the Legislature to eliminate any financial incentives for data centers. TCEQ will play a vital role once these laws are enacted. I am also engaging your agency now, before these additional safeguards are codified, to protect Texans and our natural water resources."
>
> "As ERCOT and TWDB conduct their audits, TCEQ must similarly ensure that its permitting decisions align with my directives. This process will ensure that TCEQ has sufficient information, including information gained from pending audits, and time to thoroughly review all proposed permits to make fully informed permitting decisions."
>
> "TCEQ shall provide an update to my office on its compliance with my directive by Monday, October 19, 2026."

Observations:
- Scope words: "all permits sought by data centers" and "all permits related to data center projects". No definition, no MW threshold, no permit-type list, no carve-out for pending vs new, no exemption for on-site/off-grid or non-ERCOT, no mention of "behind the meter".
- Duration: "until ERCOT completes its review" — ERCOT targets Dec 10, 2026 report to PUCT; nothing says the pause lifts automatically on that date.
- Also binds "no other state agency" (whole-of-government).
- Legal basis: none cited. Beveridge & Diamond: the directive "changes TCEQ's current administrative posture, but it does not amend statutes and rules governing individual TCEQ programs"; notes Tex. Health & Safety Code §382.0518(b) says TCEQ "shall grant within a reasonable time" an NSR permit when findings are met.

### 1c. Related: June 10, 2026 letter (background) [SECONDARY, Holland & Knight Jun 24]
Asked PUCT to use existing authority so "residential electric bills are not negatively affected"; legislative asks: data centers pay own infrastructure costs; add capacity not just demand; water-efficient/closed-loop cooling; annual electricity & water reporting; repeal sales-tax exemption and other incentives; setbacks/noise. Copy: https://s3.documentcloud.org/documents/28225490/thomas-gleeson-pablo-vegas-data-centers-directive-letter-to-puc-ercot-final.pdf

### 1d. Sept 14, 2026 letter to TWDB/ERCOT (referenced in ERCOT RFI) — directs TWDB to "partner with ERCOT to audit water consumption, sources of water supply, and implementation of water-efficient technologies" and penalize non-reporting under Texas Water Code §16.012 (criminal penalties for failure to respond). Not downloaded.

---

## 2. TCEQ implementation

### 2a. TCEQ Oct 19, 2026 compliance letter to Governor [PRIMARY, full text]
URL: https://www.tceq.texas.gov/downloads/response/tceq-response-gov-abbott-dc-directive.pdf
Signed Steven Schar, Interim Executive Director (note: Keel is no longer ED).
> "TCEQ has paused the issuance of all permits related to the construction or development of infrastructure directly supporting data centers."
>
> "TCEQ staff are screening pending permit applications to determine if they are subject to the directive. If a permit application is subject to the directive, TCEQ has paused that permit application in accordance with your directive. In addition, TCEQ is screening claimed authorizations that do not require the agency to affirmatively issue a permit and, where possible, is suspending such authorizations for data center activities."
>
> "TCEQ has met with the Texas Water Development Board (TWDB), the Public Utility Commission of Texas (PUCT), and the Electric Reliability Council of Texas (ERCOT) to ensure that all agency directives are aligned. We have also provided TCEQ resource tools to other state agencies to obtain real-time data on the status of all pending and issued permits."

No definition of "data center", no list of permit types, no MW threshold, no statement on on-site generation owned by third parties.

### 2b. TCEQ website notice (stormwater pages, live as of Nov 5, 2026) [PRIMARY]
URL: https://www.tceq.texas.gov/permitting/stormwater/construction
> "Special Notice: Directive from the Office of the Governor — The Texas Commission on Environmental Quality's electronic filing portal, the State of Texas Environmental Electronic Reporting System (STEERS), has been temporarily shut down to ensure all applications related to data centers are reviewed by TCEQ staff in accordance with the Governor's directive related to data centers dated Sept. 21, 2026. TCEQ is working to modify STEERS functionality to allow staff to review applications before an authorization is issued. TCEQ anticipates that this work will be completed in mid-November."
Also: MSGP TXR050000 renewal deadline extended to Dec 28, 2026; episodic waiver to submit CGP/MSGP/TXG11 documents by email.
Note: STEERS is also the portal for "Air New Source Review and Title V Operating Permits" e-permits (per STEERS login page), so the shutdown affects air e-filings too, not only stormwater.

### 2c. What TCEQ told FracTracker (email, Oct 14) [SECONDARY, FracTracker]
> TCEQ "has paused the issuance of all air and water permits and authorizations" for infrastructure supporting data centers; "Companies can submit applications, but their applications will not advance through the review process."
(Contrast: Governor's press secretary Andrew Mahaleris, Oct 20: "No permits have been approved"; TCEQ "has not taken and will not take any proactive actions related to the approval of data center permits" — i.e., pause = approval, not processing. Texas Tribune Oct 20; KUT/ICN Oct 20.)

### 2d. FracTracker report (Oct 19, 2026; updated Oct 21) [SECONDARY]
URL: https://fractracker.org/2026/10/texas-data-center-permits-after-governor-halt/ (with Public Citizen; author Sam Law). Records checked through Oct 16.
Aggregate: 3 major-source air permit preliminary-decision notices mailed; 11 construction stormwater coverages approved; 14 gas plant/generator applications fast-tracked or assigned to engineer; 7 emission-limit certifications recorded "issued". Oct 21 update: +9 actions, 3 ongoing. Total cited: 35 (then 44).
Named actions:
- **VoltaGrid ABI-1 power plant (Shackelford County; serves Vantage "Frontier" campus)** — major-source air permit, TCEQ item ID 506476502025352; preliminary-decision notice mailed Sept 22, published Sept 23; 30-day comment period. Status: draft/preliminary decision, NOT final issuance.
- **Nexus "self-powered" data center, Hubbard (Hill County)** — major-source air permit, item ID 389559692026054; notice mailed Sept 22, published Sept 24; public hearing requested Oct 13.
- **NRG Prairie Energy Center (Hill County)** — major-source air permit, item ID 344398782026099; notice mailed Sept 22.
- **Edged Dallas** — generator registration Project ID 416298; filed & expedited Oct 6, engineer assigned Oct 7, initial review Oct 9.
- **Crusoe Abilene campus** — construction stormwater coverage TXR1536ZN, new coverage issued after Sept 21.
- **EdgeConneX Cedar Creek** — stormwater TXR1533ZR.
- **Caldwell Valley Technology Park (Tract), Caldwell Co.** — stormwater TXR1574ZM.
- **LCRA Misty substation, Caldwell Co.** — stormwater approved Oct 8.
- **Haskell County Ventures (Maverick Lodge)** — gas-generation application Project ID 416632, expedited Oct 14, engineer Oct 16.
- **Decennial SA01 Data Center (San Antonio/Bexar)** — emission-limit certification recorded "issued" Oct 16 (TCEQ's Guerra later said draft not finalized).
- **Sitespan LLC (Bolton Rd, Bexar/Guadalupe)** — construction stormwater issued Oct 13, later suspended (TPR Oct 22).
- TPR Oct 26: 700-acre authorization in Hudspeth County; 450-acre in Taylor County; Borden County expedited gas plant/generator application.
FracTracker: "Taken together, these actions do not signal an agency trying to pause."
Public Citizen (Oct 22): TCEQ "has suspended at least 17 permits" issued to data center developers; TCEQ's Ryan Vise: "These have been suspended and communication was sent to the applicants communicating this much." TCEQ then shut STEERS (Oct 20–21).
Law firm reading of permit types (Bracewell Sept 23): order "clearly applies to significant permits like New Source Review air permits" and TPDES; PBR/standard permits "potentially caught"; "even those that plan to rely entirely on 'behind-the-meter' generation" are covered; separate-entity generator "to primarily support the operations of a data center" is an open question. Beveridge & Diamond: letter "does not state a megawatt threshold" and does not "create any exception for projects using on-site generation or projects located outside ERCOT ... The directive does not provide a basis to assume those projects are exempt from TCEQ's pause."

---

## 3. PUCT / SB 6 / the $50,000-per-MW figure

### 3a. $50,000/MW — what it is [SECONDARY: White & Case Sept 25; mgrid Sept 21; ICN Aug 24; ERCOT Oct status PDF]
- PUCT adopted the Large Load Interconnection Standards rule on **Sept 18, 2026**, Project No. **58481**, new **16 TAC §25.194** (TCRF at §25.193), under PURA §37.0561 (added by SB 6, 89th Lege, signed June 20, 2025). Filings: https://interchange.puc.texas.gov/Search/Filings?ControlNumber=58481
- The $50,000/MW is **financial security (collateral)**, posted with the interconnecting utility at the Intermediate Agreement stage "prior to interconnection studies", on **gross contracted peak demand** ("$50,000 per MW of requested capacity"). PUCT "denied requests to exempt co-located generation or base collateral on net grid imports"; developers "cannot avoid these requirements by using behind-the-meter backup generation" (White & Case). Refund: full return (less amounts owed) if withdrawn before study or allocated 0 MW; 20% forfeit if withdrawn after capacity allocated; released in stages after energization. Under the Standard LLIA, security = greater of $50,000/MW or allocated transmission upgrade cost.
- The proposed rule (March 2026) had a **non-refundable interconnection fee of $50,000/MW**; the final rule dropped it in favor of a flat **$100,000 study charge** per customer (mgrid headline's "$100,000 to $50,000 per MW" is not supported by its own body text). PUC Senior Counsel Jessie Horn: the $50,000/MW commitment "is an incentive to rightsize a project."
- Batch Zero projects with agreements executed on/before June 1, 2025 keep prior direct-cost terms.
- Threshold: **≥75 MW at a single site** in ERCOT (and expansions crossing 75 MW). Not data-center-specific.

### 3b. SB 6 large-load provisions & implementation status [ERCOT "89th Legislative Session ERCOT Status October 2026" PDF, SECONDARY-official]
URL: https://www.ercot.com/files/docs/2025/09/15/89th-Legislative-Session-PPTX-ERCOT-Status-October-2026-Final-PDF.pdf
- PURA §37.0561 (interconnection standards, cost recovery): PUCT Projects 58481 (complete 9/16–9/18/2026) and 58541; ERCOT implementation "Not Started, TBD".
- §37.0561(e) (75 MW, on-site backup generation disclosure): ERCOT in progress, TBD — set EEA threshold for notifying large loads with backup gen; process to receive backup-gen info; "curtailment procedures for customers with on-site backup serving at least 50% of load"; count as firm load shed.
- §39.170(a) transmission-voltage curtailment protocol: PUCT Project 58482, target Jan 2027; TDU protocol "Not Started, pending PUC direction". §39.170(b) Large Load Demand Management Service (≥75 MW) in progress, TBD.
- §39.169 co-location/net-metering review: PUCT Project 58479 (ERCOT monitoring complete March 2026); interim notice/SIS/120-day report processes complete July 2026; curtailment operating procedures for co-located loads in progress.
- Transmission cost allocation (4CP): Project 58484 complete May 2026; Project 58000 rulemaking deadline 12/31/2026.
- Large-load forecasting (§37.0561(m)): Project 58480 complete Feb 2026.

### 3c. ERCOT audit mechanics [PRIMARY: ERCOT RFI page + RFI v1.0 question reference]
URL: https://www.ercot.com/about/legal/data-center-impact-rfi ; https://www.ercot.com/files/docs/2026/09/18/State-and-Community-Impact-RFI_Question-Reference-9.18.26.pdf
> "ERCOT is issuing an RFI to obtain this information from all developers of data centers 25 MW or more that are pursuing interconnection to the ERCOT System. ERCOT has established a deadline of October 12, 2026 ... ERCOT intends to collaborate with the PUCT to analyze the information and develop a report that will be published on or before December 10, 2026."
Respondents (verbatim): (i) "Any Interconnecting Large Load Entity (ILLE) that is developing a Data Center Facility that has been provisionally classified by ERCOT as base load or studied load in ERCOT's Batch Zero interconnection process and that has not yet energized its facility or facility addition at transmission voltage (60 kV or above); or" (ii) "Any developer of a proposed Data Center Facility with a peak requested load of at least 25 MW but less than 75 MW that a TSP or DSP reported in response to ERCOT's August 19, 2026 Medium Load RFI..."
Definition: "Data Center Developer: ... any entity developing a data center or virtual currency mining facility proposed to connect to transmission or distribution facilities in the ERCOT Region that has not yet energized..." Includes crypto mining.
"Failure to respond to the RFI or any part of it will be reported to the Public Utility Commission of Texas (PUCT) and the Office of the Governor." Water Section C: "any failure to fully respond ... may subject a respondent to criminal penalties" (Texas Water Code §16.012). Notarized attestation required; foreign-ownership question in Section F.
Scale: ~300 Batch Zero projects (≥75 MW); medium-load snapshot 157 facilities ≈8,800 MW (mgrid Sept 5). Batch Zero classification deadline (Aug 7) waived by PUCT good-cause exception; Batch Zero study will miss April 9, 2027 deadline, no new date (ERCOT GC at Aug 20 open meeting).
BTM: the RFI population is defined by grid interconnection; a facility that never seeks interconnection is not a respondent. INFERENCE: islanded BTM is outside Pause A but is asked about (Section B) for grid-connected projects.

---

## 4. AG Paxton "18 counties"

[PRIMARY, full text] Sept 24, 2026 press release: https://www.texasattorneygeneral.gov/news/releases/attorney-general-paxton-launches-landmark-investigation-hundreds-data-center-developments-texas
> "Attorney General Ken Paxton is investigating Texas data center developments that have not provided a response to the Texas Water Development Board's ('TWDB') water use survey ... Data centers are under initial investigation in counties across Texas, including Harris, Montgomery, Travis, Dallas, Tarrant, Smith, Bexar, Tom Green, Potter, Randall, Lubbock, Midland, Ector, Wichita, Victoria, Brazos, Nueces, and El Paso."
That list is exactly **18 counties** — this is the "Paxton names 18 counties" item. It is a water-use-survey compliance **investigation** (not a lawsuit, not a permitting action). Legal hook: TWDB statutory water-use survey (Water Code §16.012).
Follow-up [PRIMARY] Oct 15, 2026: 156 letters to data center developments in **32 counties** (Bexar, Brazos, Cameron, Collin, Dallas, Denton, Ector, El Paso, Glasscock, Harris, Hidalgo, Hood, Lubbock, Maverick, McLennan, Midland, Montgomery, Nacogdoches, Nueces, Pecos, Potter, Randall, Sherman, Tarrant, Tom Green, Travis, Victoria, Waller, Ward, Webb, Wichita, Williamson): https://www.texasattorneygeneral.gov/news/releases/attorney-general-ken-paxton-sends-letters-data-center-developments-across-texas-ensure-reporting — "letters that notify data center developments that they must provide up-to-date and accurate information regarding water usage." No penalties or deadline stated.
Context: PUC April water survey got responses from only 28 companies (~28%) (ICN Aug 24; Texas Tribune Sept 21).
Paxton's Aug 24 four-point Senate-campaign plan (fox4news): ban Chinese tech in data centers; criminal liability for AI chatbots harming children; co-sponsor federal DATA Act; support Abbott's state initiatives "including repealing sales tax exemptions." (Paxton lost the Senate race to Talarico per task context; not independently verified here.)

---

## 5. Hinojosa platform / Talarico blueprint

### 5a. Hinojosa (Governor-elect; takes office Jan 19, 2027)
- July 23, 2026 campaign release [SECONDARY-campaign]: https://ginafortexas.com/2026/07/new-hinojosa-calls-on-greg-abbott-to-put-moratorium-on-data-centers-until-a-legislative-session-that-puts-texans-first/ — asked Abbott to sign "an emergency executive order imposing a moratorium on data centers" until "a legislative session that puts Texans first." "Texans First Data Center Priorities": licensed skilled **union** workers and reverse "fast-track rollbacks"; **local control** (communities decide); **ban NDAs**; companies must **prove households won't pay more** for electricity or water incl. pass-through grid/transmission/capacity costs; **end subsidies** so data centers "pay for themselves"; make any water contract "unenforceable if it threatens a community's water supply."
- Oct 22, 2026 video (Texas Tribune Nov 4; KFOX Nov 4): "a moratorium — a ban — on all data center approvals until laws can be passed by the Legislature"; lift when Legislature passes "real protections so Texans can have a seat at the table." Priorities restated: union labor, water, NDA ban, no electricity cost increases, end tax subsidies. "We can have economic development and we can have protections for Texans." Called Abbott's action an "election year pause" (Yahoo/Bloomberg Nov 4).
- Texas Tribune Nov 4 (https://www.texastribune.org/2026/11/04/data-center-texas-pause-gina-hinojosa-governor-policies/): "Under Hinojosa, Texas data center approvals could stay paused." Article gives NO legal mechanism and NO expert on whether a governor can extend the pause by executive action. Data Center Coalition (Jess Heck): industry "looks forward to working with state leadership."
- Can she extend without the Legislature? UNDETERMINED in sources. Facts: Abbott's pauses are letters, not executive orders or rules, and carry no cited statutory basis; TCEQ and PUCT commissioners are gubernatorial appointees (B&D notes directive does not amend statutes/rules; §382.0518(b) "shall grant" duty). INFERENCE: a successor governor can issue the same kind of letter and, as appointing authority, has practical leverage; durability against a mandamus/ultra vires challenge by a permit applicant is untested. No litigation found as of Nov 5.
- No statement found from Hinojosa specifically on behind-the-meter/on-site gas generation; "all data center approvals" is the operative phrase.
- Tax: Comptroller estimates foregone revenue from the 2013/2015 sales-tax exemption at "approximately $3.3 billion"; Senate Finance hearing July 27, 2026 showed bipartisan support for repeal (Holland & Knight Jul 30). Abbott also pledged repeal (June 10 and Sept 21 letters).

### 5b. Talarico (Senate winner per task) — July 22, 2026 plan [Texas Tribune]
https://www.texastribune.org/2026/07/22/texas-james-talarico-data-centers-regulation-senate-2026/ — federal minimum standards ("preventing a race to the bottom"); large users pay own infrastructure/interconnection costs; repeal state sales-tax exemption ("sweetheart tax deals"); closed-loop water; local approval authority; publish per-facility tax-break data. Did NOT call for a moratorium. No NDA ban in his plan (that is Hinojosa's). Talarico: "I don't take money from data centers."

---

## 6. Status of specific Texas BTM projects (as of Nov 5, 2026)

| Project | On-site generation | TCEQ air permit status | Evidence |
|---|---|---|---|
| **VoltaGrid ABI-1 / Vantage "Frontier" (Stargate Frontier), Shackelford Co.** — Cleanview: 1,820 MW full build; task says 1.4 GW/620 Jenbacher engines (Cleanview project page is paywalled; engine count not verified) | VoltaGrid gas recips (IPP, separate entity) | **Pending major-source NSR**; TCEQ mailed Notice of Application & Preliminary Decision Sept 22, 2026 (the day after the pause); 30-day comment period. Not finally issued as of FracTracker's Oct 16 cutoff. Campus "under construction" (Cleanview, Nov 3). | FracTracker; Cleanview TX page |
| **Stargate Abilene (Crusoe/Oracle/OpenAI), Taylor Co.** — 300 MW operating, 1,200 MW full build (Cleanview) | 2024: 10 gas turbines + 62 diesel gensets via PBR/standard permits (Floodlight/Wired). Existing Permit 177263. | Original turbines **already authorized** (2024, minor permits). **Pending**: NSR Permit 182126 / PSDTX1688 / GHGPSDTX263 (Crusoe Energy Systems, "additional power generation equipment for onsite consumption in data center buildings", NOx 760 t/yr) and Permit 182267 (Abilene Data Center Campus Master Association; 5× GE LM2500, 34.1 MW each, modification of 177263) — both listed on TCEQ pending-permit notices page; no dates in the notices. Stormwater coverage TXR1536ZN issued after Sept 21 (FracTracker). | TCEQ pending notices (downloaded); FracTracker |
| **Fermi America "Project Matador", Amarillo/Carson Co.** — 11 GW private grid | 90 Siemens turbines (ACOEL) | **ISSUED** Feb 2026 ("nation's second-largest Clean Air permit", final approval ~Feb 25, 2026; construction had paused Feb 6 awaiting it). Applied ~March 2026 for ~5 GW more — status of the follow-on not found; INFERENCE: caught by pause if not issued before Sept 21. | NewsChannel10 Feb 25; ACOEL |
| **Pacifico Energy "GW Ranch", Pecos Co.** | 7.65 GW gas + storage/solar | **ISSUED** (press release Jan 26, 2026). | ACOEL; turbomachinerymag Jan 28 |
| **Generate Capital 516 MW** | — | Not found in any pause-related source. ACOEL mentions TCEQ "reportedly granted one 519 MW reciprocating-engine plant its permit three weeks after application" (no name) — possibly this project; UNVERIFIED. | — |
| **Sailfish (Comanche Circle / Project Panther, DFW area)** | multi-GW planned | No TCEQ permit record found in pause coverage. | baxtel/DCD only |
| **xAI** | — | No Texas permit action found. | — |
| **Nexus Data Centers, Hubbard (Hill Co.)** "self-powered" | gas | Pending major-source air permit; preliminary decision notice Sept 22; hearing requested Oct 13; Hill County also passed a 1-year rural data center construction ban (later walked back after $100M suit — Law360). | FracTracker; TPR |
| **NRG Prairie Energy Center (Hill Co.)** | gas plant for data centers | Pending; preliminary decision notice Sept 22. | FracTracker |
| **Meta El Paso** ($14B campus; outside ERCOT) | $473M gas plant | Not covered by Pause A (non-ERCOT); Pause B applies statewide. No TCEQ status found. | KFOX; hostingadvice |

---

## 7. Capacity figures

- **Wells Fargo "27%"**: NOT located in any accessible source (searched Wells Fargo + 27% + Texas; hostingadvice, BGov, Utility Dive, Yahoo). Closest found: Bloomberg/Yahoo Nov 4: Texas "accounts for more than 25% of planned US capacity by 2030." Treat the 27% as unverified.
- **BNEF (Aug 5, 2026)**: pause "affects almost 49.8 GW of projects" = "about 20% of the total U.S. data center pipeline at risk of delay"; BNEF tracks ~50 GW of Texas projects, >70% early stage; expects ~8.25 GW ERCOT data center additions through 2030; revenue loss up to $8B by Q1 2027 (Utility Dive Aug 6).
- **ERCOT queue**: ~474 GW, ~90% data centers (Abbott letter); Batch Zero ~300 projects ≥75 MW; medium-load 157 facilities ≈8.8 GW.
- **Cleanview BTM**: landing page (mid-2026): "59 behind-the-meter data centers with ~90 GW of announced capacity", ">25% of all planned data center capacity in the United States", "Just five states account for 83% of all proposed BTM capacity", "Texas leads total announced capacity by a wide margin" — **Texas GW NOT given publicly** (full report paywalled). Earlier Feb 3, 2026 newsletter: 46 projects / 56 GW, ~75% of identified equipment (23 GW) gas. Floodlight/Texas Tribune map: "At least 15 data centers plan to build their own 'behind the meter' gas plants in Texas"; nine could emit >130 Mt CO2e/yr. Floodlight/Wired (Jul 2026): 74 US gas plants ≥100 MW proposed for data centers, 32 in Texas. Cleanview TX page (Nov 3, 2026): 773 data centers / 252 campuses in Texas; 28 campuses planned ≥1 GW.
- EIA (Aug 11): Texas power demand growth forecast cut to 5.6% for 2027 from a July forecast of 14% after the Aug 3 audit decision (BGov).

---

## 8. 2027 session (90th Legislature)

- Calendar: bill **prefiling begins Nov 9, 2026** (so as of Nov 5 there are NO prefiled bills); session convenes **Jan 12, 2027**; bill-filing deadline Mar 12, 2027; sine die May 31, 2027 (texaspolicyresearch.com calendar). Hinojosa inaugurated Jan 19, 2027.
- Known legislative vectors (no bill numbers yet): sales-tax exemption repeal (Abbott June 10 & Sept 21; Senate Finance July 27 hearing, bipartisan; Comptroller $3.3B; 6 of 20 audited data centers non-compliant with job requirements); cost allocation codification; water reporting/closed-loop; setbacks/noise; Hinojosa's NDA ban, union labor, local control, ratepayer-proof; Talarico's items are federal. Abbott (Sept 21): "I will work with the Legislature to eliminate any financial incentives for data centers. TCEQ will play a vital role once these laws are enacted."
- Interim: House/Senate committees studying AI data centers ahead of session (Courier Texas, Apr 1, 2026). Special session calls (Aug 2026) were not granted.

---

## 9. Timeline (consolidated)
- 2025-06-20 SB 6 signed. 2025-01-30 TCEQ natural-gas-engine standard permit effective.
- 2026-01-26 Pacifico GW Ranch 7.65 GW permit. 2026-02-25 Fermi Matador permit final.
- 2026-03 PUCT proposed large-load rule (58481). 2026-06-10 Abbott letter to PUCT/ERCOT (bills, incentives). 2026-06-18 ERCOT Batch Zero approved.
- 2026-07-22 Talarico plan; 07-23 Hinojosa moratorium call; 07-27 Senate Finance hearing on exemption.
- 2026-08-03 Pause A (ERCOT/PUCT audit). 08-07 Batch Zero classification deadline waived. 08-19 ERCOT Medium Load RFI. 08-20 PUCT open meeting; ERCOT: Dec 10 target.
- 2026-09-14 Abbott letter to TWDB/ERCOT (water); ERCOT RFI issued. 09-18 PUCT adopts 16 TAC §25.194 ($50k/MW security). 09-21 Pause B (TCEQ). 09-22 TCEQ mails VoltaGrid/Nexus/NRG preliminary-decision notices. 09-24 Paxton 18-county investigation.
- 2026-10-12 RFI responses due. 10-15 Paxton 156 letters/32 counties. 10-19 FracTracker report; TCEQ compliance letter. 10-20/21 TCEQ suspends ≥17 stormwater authorizations; shuts STEERS (restore target mid-Nov). 10-22 Hinojosa "ban on all approvals" video.
- 2026-11-03 Hinojosa elected. 11-09 prefiling opens. 12-10 ERCOT/PUCT audit report due. 2027-01-12 session; 01-19 inauguration.

---

## 10. Open questions
1. Does TCEQ treat an air permit for a generation facility owned by a third-party IPP (VoltaGrid ABI-1) as "related to a data center project"? The Sept 22 notices suggest processing continued; final issuance status after Oct 16 unknown.
2. Will TCEQ publish a formal scope (permit types, definition, MW threshold)? None exists as of Nov 5.
3. Are already-issued PBR/standard-permit registrations (Stargate Abilene 2024 turbines; Fermi) being "suspended" under TCEQ's "claimed authorizations" language? No evidence of revocation.
4. Legal durability: any applicant challenge (mandamus under §382.0518(b)) to the issuance hold? None found.
5. Does Hinojosa intend to continue Pause B by letter after Jan 19, or seek legislation first? Her statements say "ban on all approvals until laws can be passed" but give no instrument.
6. What does ERCOT's Dec 10 report recommend, and will the PUCT lift Pause A at a December open meeting before the new governor takes office?
7. Wells Fargo 27% and Cleanview Texas-GW figures remain unverified from primary text.
8. Generate Capital 516 MW and Sailfish permit status not found.

## Blocked / inaccessible
- WebFetch provenance block on gov.texas.gov PDFs (worked around with curl). ERCOT RFI page and AG releases blocked via WebFetch, fetched via curl. Cleanview full report paywalled. BGov article truncated.
