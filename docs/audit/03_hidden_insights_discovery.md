# Empirical Discovery & Hidden Insights Audit: GujRERA Sovereign Data Layer

**Audit Date**: November 22, 2026  
**Target Database**: `data/intelligence.sqlite` (17,787 projects, 1.95M unit transactions, 46.9k NOC records, 17.7k bank accounts)  
**Methodology**: Read-only empirical SQL/Python verification across dense tables (`projects`, `project_summaries`, `unit_transactions`, `noc_bu_records`, `banks`, `professionals`, `graph_nodes`, `graph_edges`). Zero reliance on unverified claims in `docs/mcp_technical_audit_and_roadmap.md`.

---

## 1. Statewide Empirical Baseline

All comparative rates evaluated against the full statutory population (`projects` N = 17,787, `project_summaries` N = 17,787):

| Baseline Indicator | Exact Value | Population % | Source Table & Column |
|---|---|---|---|
| Total Registered Projects | 17,787 | 100.00% | `projects.project_id` |
| Projects with Received BU NOC | 9,590 | 53.92% | `project_summaries.has_bu_noc` (`projects.has_bu_noc` is 0 statewide) |
| Past Statutory Completion Date (`< 2026-11-22`) | 10,491 | 58.98% | `projects.completion_date` |
| **Expired Without BU NOC** | **2,398** | **13.48%** | `projects.completion_date` + `project_summaries.has_bu_noc = 0` |
| Formally Registered Consumer Complaints | 4 | 0.0225% | `projects.has_complaints` (4 projects, 11 total complaints) |
| Non-Null Construction Velocity Ratio | 9 | 0.0506% | `projects.velocity_ratio` (99.95% unpopulated) |
| Non-Null Town Planning Scheme (`tp_scheme`) | 2 | 0.0112% | `projects.tp_scheme` (99.99% unpopulated) |

---

## 2. Hypothesis (a): "Rubber-Stamp" Certifier Empirical Test

### Data Coverage Reality Check
Claims that the platform audits Architects, Engineers, and CAs are empirically refuted by table composition:
- `professionals` table contains **15,565** rows: **15,557 Engineers (99.95%)**, **8 Architects (0.05%)**, and **0 Chartered Accountants (0.00%)**.
- `project_summaries`: `architect_names` (0 non-null), `ca_name` (0 non-null), `engineer_names` (15,469 non-null).
- `graph_nodes`: `Architect` (7 nodes), `CA` (0 nodes), `Engineer` (3,873 nodes).
- **Hypothesis Testability**: Architect and CA certifier analyses fail completely due to zero/near-zero data ingestion. Engineer certifiers are 87.5% populated.

### Top 15 Engineers by Project Volume vs. Baseline
Comparative audit of the top 15 structural/supervising engineers ranked by project portfolio size:

| Engineer Name (Raw String) | Total Projects | Expired Count | Expired % | Expired w/o BU | Expired w/o BU % | BU NOC % | Complaints | Velocity Populated |
|---|---|---|---|---|---|---|---|---|
| **Statewide Baseline** | **17,787** | **10,491** | **58.98%** | **2,398** | **13.48%** | **53.92%** | **4 (0.02%)** | **9 (0.05%)** |
| ZARNA ASSOCIATES | 191 | 159 | 83.2% | 52 | **27.2%** | 59.7% | 0 | 0 |
| VINUBHAI RATILAL PATEL | 161 | 5 | 3.1% | 2 | 1.2% | 3.7% | 0 | 0 |
| VIREN DILIPBHAI PAREKH | 128 | 18 | 14.1% | 6 | 4.7% | 19.5% | 0 | 0 |
| ASHWINKUMAR MANILAL LODHIYA | 108 | 17 | 15.7% | 3 | 2.8% | 29.6% | 0 | 0 |
| HARDIKBHAI PUNAMCHANDRA UPADHYAY | 101 | 3 | 3.0% | 0 | 0.0% | 11.9% | 0 | 2 |
| NELSON NANUBHAI MACWAN | 100 | 10 | 10.0% | 2 | 2.0% | 21.0% | 0 | 2 |
| VIREN D PAREKH | 93 | 82 | 88.2% | 13 | 14.0% | 78.5% | 0 | 0 |
| JAYESH DINESHCHANDRA DESAI | 93 | 9 | 9.7% | 4 | 4.3% | 18.3% | 0 | 0 |
| ASHOK SHAH & ASSOCIATES | 92 | 84 | 91.3% | 27 | **29.3%** | 67.4% | 0 | 0 |
| NITINKUMAR PATEL | 89 | 9 | 10.1% | 2 | 2.2% | 12.4% | 0 | 0 |
| Zarna Associates (case variant) | 86 | 59 | 68.6% | 26 | **30.2%** | 46.5% | 0 | 0 |
| JAYESH D DESAI (variant) | 84 | 75 | 89.3% | 23 | **27.4%** | 65.5% | 0 | 0 |
| UMANG PATEL | 81 | 18 | 22.2% | 1 | 1.2% | 25.9% | 0 | 0 |
| KIRANKUMAR NARSHIBHAI PATEL | 76 | 5 | 6.6% | 0 | 0.0% | 25.0% | 0 | 0 |
| BHAVESH KAPILRAY VYAS | 68 | 4 | 5.9% | 2 | 2.9% | 19.1% | 0 | 0 |

### Findings
1. **Severe Name Fracture**: Top certifiers are split across string casings and abbreviations (e.g., `ZARNA ASSOCIATES` [191] + `Zarna Associates` [86] = 277 projects; `VIREN DILIPBHAI PAREKH` [128] + `VIREN D PAREKH` [93] = 221 projects; `JAYESH DINESHCHANDRA DESAI` [93] + `JAYESH D DESAI` [84] = 177 projects).
2. **Elevated Default Clusters**: Projects certified by `Zarna Associates` (combined 78 expired w/o BU, 28.2%), `ASHOK SHAH & ASSOCIATES` (29.3%), and `JAYESH D DESAI` (27.4%) exhibit expired-without-occupancy rates **more than double the statewide baseline (13.48%)**.
3. **Dead Metrics**: Comparing certifiers on `velocity_ratio` or `has_complaints` is impossible; 13 of top 15 certifiers have zero velocity records and zero complaint flags due to upstream scraping truncation.

---

## 3. Hypothesis (b): Hidden SPV Clustering & Split-Risk Developers

### Entity Clustering Methodology
- Raw statutory records contain **12,191 unique promoter strings** across 17,787 projects.
- Legal affix normalization (stripping `PVT LTD`, `LLP`, `BUILDERS`, `DEVELOPERS`, `INFRA`, `REALTY`, `GROUP`, `ENTERPRISE`, punctuation) consolidates them into **9,457 distinct brand clusters**.
- Multi-SPV detection: Groups with $\ge 2$ legal entity names.
- Split-risk detection: Groups holding $\ge 1$ expired project lacking BU NOC while concurrently launching/operating $\ge 1$ active project (`completion_date >= 2026-11-22`).

| Metric | Empirical Count |
|---|---|
| Multi-SPV Clusters ($\ge 2$ distinct SPV legal entities) | 1,067 clusters (4,394 projects) |
| **Split-Risk Developer Clusters** | **350 clusters** |
| Masked Bank Accounts Shared Across $\ge 2$ Unrelated Promoters | 110 unique `(ifsc, masked_acc)` keys (243 projects) |
| Graph Knowledge Edges with Broken `promoter:None` Destination | **17,778 of 17,787 edges (99.95%)** |

### Top Split-Risk Developer Brand Clusters

| Normalized Brand Cluster | Distinct SPV Entities | Total Registered Projects | Stalled / Expired w/o BU | Active / Ongoing Projects | Sample Registered Legal Entities |
|---|---|---|---|---|---|
| **SHREEJI** | 23 | 190 | 37 | 71 | Shreeji Realtors, Shreeji Corporation, Shreeji Group, Shreeji Infra |
| **SHIV** | 15 | 110 | 10 | 56 | Shiv Associates, Shiv Developers, Shiv Corporation, Shiv Builders |
| **SHREE** | 15 | 105 | 10 | 52 | Shree Corporation, Shree Realty, Shree Developers, Shree Infra |
| **SHIVAM** | 16 | 96 | 13 | 27 | Shivam Realty, Shivam Associates, Shivam Enterprise, Shivam Buildcon |
| **MARUTI** | 13 | 70 | 9 | 31 | Maruti Builders, Maruti Realty, Maruti Enterprise, Maruti Corporation |
| **KRISHNA** | 14 | 68 | 9 | 28 | Krishna Associates, Krishna Realty, Krishna Developers, Krishna Builders |
| **SHREE HARI** | 12 | 63 | 7 | 21 | Shree Hari Developer, Shree Hari Infra, Shree Hari Group |
| **RADHE** | 9 | 59 | 7 | 23 | Radhe Associates, Radhe Infrastructure, Radhe Realty, Radhe Developers |
| **NILKANTH** | 13 | 56 | 5 | 29 | Nilkanth Corporation, Nilkanth Infra, Nilkanth Realty, Nilkanth Developers |
| **SHUBH** | 14 | 58 | 2 | 22 | Shubh Corporation, Shubh Builders, Shubh Associates |

### Broken Knowledge Graph Finding
In `real_estate_intelligence/graph/network.py:59-62`, developer edges are generated via `SELECT project_id, promoter_id FROM projects`. Because `projects.promoter_id` is populated for only 9 rows (and NULL for 17,778 rows), `DEVELOPED_BY` edges resolve to `promoter:None` in 99.95% of cases. Cross-project contagion queries via the current graph engine fail silently.

---

## 4. Hypothesis (c): Deed Pricing Realization, Spread & Dispersion

### Transaction Dataset Scale (`unit_transactions` N = 1,952,528)
- **Booked Transactions**: 1,093,866 (56.02%)
- **Unbooked Available Units**: 858,662 (43.98%)
- **Valid Sq.Ft Rates (100–50,000 INR/sqft)**: 1,936,180 (99.16%)
- **Dated Form 3 Agreements**: 1,605,327 (82.22%)

### Booked vs. Unbooked Inventory Price Realization Spread

| Transaction Status | Cleaned Units | Mean Rate (₹/sq.ft) | Median Rate (₹/sq.ft) | Mean Consideration (₹ Lakh) | Mean Carpet Area (sq.ft) |
|---|---|---|---|---|---|
| **Booked (Executed Deeds)** | 1,078,989 | **₹4,173.05** | ₹3,716.14 | ₹32.33 L | 764.6 sq.ft |
| **Unbooked (Remaining Stock)** | 857,191 | **₹4,700.10** | ₹4,180.64 | ₹39.18 L | 805.1 sq.ft |
| **Spread (Unbooked vs. Booked)** | — | **+12.63%** | **+12.50%** | **+21.19%** | **+5.30%** |

*Insight*: Developers systematically price unsold residual inventory **12.63% higher per sq.ft** (and 21.19% higher per unit consideration) than historical booked inventory within the exact same project filings.

### Cleaned Geographic Price Dispersion by Taluka (Booked Units $\ge 15,000$)

| District | Taluka | Transaction Volume | Median Rate (₹/sq.ft) | IQR (P75 - P25) | IQR / Median | Mean Rate (₹/sq.ft) | Coeff of Variation (CV) |
|---|---|---|---|---|---|---|---|
| Ahmedabad | AHMEDABAD CITY | 274,157 | ₹4,582.16 | ₹2,752.50 | 0.601 | ₹5,042.16 | 0.522 |
| Vadodara | VADODARA | 180,703 | ₹3,642.96 | ₹2,059.66 | 0.565 | ₹4,130.93 | 0.597 |
| Surat | SURAT CITY | 158,364 | ₹3,432.78 | ₹2,904.56 | 0.846 | ₹3,993.16 | 0.690 |
| Gandhinagar | GANDHINAGAR | 104,275 | ₹4,346.31 | ₹2,475.89 | 0.570 | ₹5,221.75 | 0.719 |
| Rajkot | RAJKOT | 79,481 | ₹2,859.54 | ₹1,419.12 | 0.496 | ₹3,118.52 | 0.546 |
| Ahmedabad | DASKROI | 47,488 | ₹4,432.47 | ₹2,357.14 | 0.532 | ₹4,811.13 | 0.484 |
| Surat | CHORASI | 26,050 | ₹2,818.16 | ₹2,551.40 | 0.905 | ₹3,192.97 | 0.609 |
| Bhavnagar | BHAVNAGAR | 20,052 | ₹1,067.84 | ₹1,524.96 | **1.428** | ₹1,996.81 | **0.918** |
| Ahmedabad | SANAND | 20,036 | ₹5,174.73 | ₹2,587.19 | 0.500 | ₹5,062.61 | 0.431 |
| Surat | KAMREJ | 17,016 | ₹1,948.66 | ₹1,181.91 | 0.607 | ₹2,190.66 | 0.475 |

*TP Scheme Dispersion Failure*: `projects.tp_scheme` is populated for only 2 projects statewide; micro-location TP scheme dispersion analysis fails due to missing tabular data.

### Project-Level Deed Depth for Longitudinal CAGR
Feasibility of calculating quarterly compound annual growth rates (CAGR) per project from Form 3 deeds:

| Minimum Deed Volume / Span Criterion | Project Count | % of Statewide Projects (N=17,787) | Feasibility Verdict |
|---|---|---|---|
| Any dated booked deed ($\ge 1$) | 14,038 | 78.92% | Baseline presence |
| $\ge 10$ dated booked deeds | 11,892 | 66.86% | Viable for cross-sectional median |
| $\ge 20$ dated booked deeds | 9,646 | 54.23% | Viable for regression controls |
| Deeds spanning $\ge 4$ distinct quarters (1 year) | 9,604 | 53.99% | Robust 1-Year Quarterly CAGR |
| Deeds spanning $\ge 8$ distinct quarters (2 years) | 5,699 | **32.04%** | Highly robust Multi-Year Trend Analysis |

---

## 5. Hypothesis (d): Ghost Inventory, Trapped Buyers & Safety Deficits

### Expired Without BU NOC by Booking Bracket
Of the **2,398 projects** past their completion date with no registered BU NOC (`has_bu_noc = 0`), buyer exposure breaks down into clear risk tiers:

| Absorption Bracket | Expired Projects | Category Classification | Buyer Exposure Severity |
|---|---|---|---|
| **81% – 100% Sold** | **493** | **Trapped Buyer Crisis** | Complete buyer capital lock-in without occupancy |
| **51% – 80% Sold** | **365** | Severe Buyer Exposure | Majority sold, project stranded |
| **21% – 50% Sold** | **246** | Moderate Exposure | Mixed distressed project |
| **1% – 20% Sold** | **122** | Low Exposure | Early-stage distressed failure |
| **0% Sold** | **1,172** | **Ghost / Abandoned Inventory** | Shell projects or failed pre-launch inventory |

### Geographic Concentration of Trapped Buyers (Expired w/o BU)

| District | Total Expired w/o BU | 0% Booked (Ghost) | 1-50% Booked | 51-80% Booked | **>80% Booked (Trapped)** |
|---|---|---|---|---|---|
| **Vadodara** | 528 | 189 | 62 | 99 | **178** (33.7%) |
| **Ahmedabad** | 759 | 481 | 69 | 92 | **117** (15.4%) |
| **Rajkot** | 311 | 190 | 41 | 31 | **49** (15.8%) |
| **Gandhinagar** | 184 | 75 | 25 | 37 | **47** (25.5%) |
| **Surat** | 238 | 101 | 57 | 42 | **38** (16.0%) |
| **Bhavnagar** | 100 | 34 | 25 | 12 | **29** (29.0%) |

*Key finding*: Vadodara accounts for **36.1% (178 of 493)** of all trapped high-sold buyer projects statewide despite having only 53% of Ahmedabad's project volume.

### Zombie Projects & Statutory Safety NOC Deficits
1. **Aged Zombie Projects**: **2,943 projects (16.55%)** have elapsed $>50\%$ of their statutory construction timeline but have achieved $<20\%$ booking absorption.
2. **Safety NOC Deficits in Highly Absorbed Projects**: Among the **5,133 projects** statewide with $\ge 80\%$ bookings:
   - **3,254 projects (63.39%)** have **NO Fire NOC** recorded in `noc_bu_records`.
   - **3,316 projects (64.60%)** have **NO Lift Inspection NOC** recorded in `noc_bu_records`.
   - **3,249 projects (63.30%)** are missing **BOTH Fire and Lift NOCs**.
   - **1,179 projects (22.97%)** have zero BU NOC despite being $>80\%$ sold out.

---

## 6. Hypothesis (e): Bank Escrow Concentration & Deposit Anomaly

### Escrow Accounts Population (`banks` N = 17,739)
The `banks` table acts almost exclusively as an **account identity directory**, not a cash-flow ledger:
- Non-null/positive deposit records: **7 out of 17,739 rows (0.039%)**.
- Non-null/positive closing balance records: **7 out of 17,739 rows (0.039%)**.
- High-absorption projects ($\ge 70\%$ booked, N = 6,775): **6,772 projects (99.96%) report 0 or NULL for deposits and balances**.
- Cash flow testing under Section 4(2)(l)(D) is unviable using `banks` alone; multi-quarter deposits and withdrawals live only in the 18 sample rows of `finances`.

### Bank Exposure & Delay Concentration ($\ge 200$ Projects)

| Bank Name (Curated) | Projects Backed | Expired w/o BU Projects | Expired w/o BU Rate | Zero-Deposit Record Rate |
|---|---|---|---|---|
| **Bank of Baroda** | 270 | 82 | **30.37%** | 100.0% |
| **Central Bank of India** | 197 | 51 | **25.89%** | 100.0% |
| **Yes Bank** | 172 | 45 | **26.16%** | 100.0% |
| **Kotak Mahindra Bank** | 1,059 | 225 | **21.25%** | 100.0% |
| **Bank of India** | 225 | 48 | **21.33%** | 100.0% |
| **Kalupur Commercial Co-op Bank** | 393 | 78 | **19.85%** | 100.0% |
| **Axis Bank** | 1,240 | 215 | **17.34%** | 100.0% |
| **ICICI Bank** | 2,557 | 374 | **14.63%** | 99.96% |
| **HDFC Bank** | 2,564 | 352 | **13.73%** | 100.0% |
| **State Bank of India** | 1,910 | 224 | **11.73%** | 99.90% |

### Branch-Level Distressed Project Hotspots

| Bank & Branch Name | Total Backed Projects | Expired w/o BU Projects | Branch Failure Rate |
|---|---|---|---|
| ICICI Bank — JAI HIND PRESS BRANCH | 24 | 11 | **45.83%** |
| Kotak Mahindra Bank — BHAVNAGAR | 22 | 10 | **45.45%** |
| ICICI Bank — KALAWAD ROAD (Rajkot) | 86 | 12 | 13.95% |
| HDFC — KARELIBAUG (Vadodara) | 33 | 10 | **30.30%** |
| ICICI Bank — Kalawad Road (Branch variant) | 20 | 8 | **40.00%** |
| HDFC — VASNA ROAD (Vadodara) | 20 | 4 | 20.00% |

---

## 7. Synthesis: Top 5 Validated Insights vs. Hypotheses Failed Due to Data Deficits

### Top 5 Empirically Validated Discoveries

```
1. UNBOOKED INVENTORY PREMIUM SPREAD (+12.63%)
   Deed ledger analysis across 1.95M units reveals developers systematically list unsold 
   residual stock at a +12.63% rate premium (₹4,700 vs ₹4,173/sq.ft) over certified executed deeds.

2. TRAPPED BUYER CRISIS CONCENTRATED IN VADODARA (493 Projects Statewide, 178 in Vadodara)
   493 expired projects without occupancy are >80% sold out; Vadodara accounts for 36.1% 
   of all statewide trapped buyer schemes, representing the primary regional consumer hazard.

3. 350 "SPLIT-RISK" DEVELOPER NETWORKS LAUNCHING AMID DELAYS
   Normalized promoter entity resolution uncovers 350 multi-SPV brand groups actively launching 
   new schemes while abandoning earlier registered projects in an expired, uncertified state.

4. SAFETY CLEARANCE GAP: 63.4% OF HIGH-SOLD SCHEMES LACK FIRE/LIFT NOCS
   Among 5,133 projects with ≥80% bookings, 3,249 schemes (63.3%) lack statutory fire 
   and elevator NOC filings in municipal clearance tables, exposing buyers to critical occupancy risk.

5. BANK OF BARODA & PSU ESCROW DELAY ASYMMETRY (30.4% vs 11.7% SBI)
   Bank of Baroda exhibits a 30.37% project failure rate (expired w/o BU), more than 2.5x 
   State Bank of India (11.73%), with individual branches reaching 45.8% default concentrations.
```

### Hypotheses That Failed Due to Dirty / Missing Data

| Tested Hypothesis | Presumed Capability | Empirical Reality & Failure Mode | Relevant Source Code Reference |
|---|---|---|---|
| **Architect & CA Certifier Accountability** | Screen certifier track records | `professionals` table has 0 CAs and 8 Architects. `project_summaries.ca_name` is 100% NULL. Only engineers can be audited. | `real_estate_intelligence/graph/network.py:64-89` |
| **Certifier Velocity & Complaint Comparison** | Correlate certifiers with delay and complaints | `projects.velocity_ratio` has only 9 non-null rows (0.05%). `projects.has_complaints` has 4 flagged projects statewide (0.02%). | `real_estate_intelligence/analytics/audit.py:59-65` |
| **TP Scheme Price Dispersion** | Measure micro-market valuation spreads | `projects.tp_scheme` contains only 2 non-null entries statewide (99.99% NULL). Taluka is the finest reliable geographic grain. | `real_estate_intelligence/analytics/spatial.py:45` |
| **Section 4(2)(l)(D) Escrow Balance Audit** | Flag unauthorized escrow withdrawals | `banks` deposit and closing balance fields are 99.96% NULL/0. Longitudinal quarterly finance data exists for only 18 projects. | `real_estate_intelligence/analytics/audit.py:24-32` |
| **Automated Developer Network Traversal** | Trace developer risk contagion via Knowledge Graph | `graph_edges` contains 17,778 `DEVELOPED_BY` edges pointing to `promoter:None` because `projects.promoter_id` is 99.95% NULL. | `real_estate_intelligence/graph/network.py:59-62` |
