---
name: buyer-due-diligence
description: Institutional buyer due-diligence playbook for verifying GujRERA statutory disclosures, municipal Building Use (BU) ground truth, broker sales claims, spatial pricing benchmarks, and escrow health.
---

# Institutional Buyer Due-Diligence Playbook (GujRERA)

This skill provides an evidence-based institutional protocol for prospective property buyers, legal advisors, and real estate analysts conducting statutory due diligence on registered residential and commercial projects in Gujarat.

---

## 1. Ground-Truth Data Principles
When auditing any project in the GujRERA intelligence repository, adhere strictly to these empirical ground-truth rules:
1. **`projects.bu_status` is Dead**: Never rely on `projects.bu_status` (often unpopulated in portal dumps). Ground-truth Building Use (BU) status is derived from `project_summaries.has_bu_noc` and `noc_bu_records.bu_check == 'YES'`.
2. **Cohort & Authority Differentiation**:
   - Schemes with completion deadlines on or before 2019 ($\le 2019$) without recorded BUs are flagged `is_legacy_grandfathered` (accounting for 47% of statewide missing BUs caused by historical portal transition gaps).
   - Schemes by public development authorities (`AUDA`, `VUDA`, `SUDA`, `RUDA`, `GIDC`, `PMAY`, `GHB`) are flagged `is_govt_authority` and do not carry commercial developer default risk.
   - Only modern private schemes ($\ge 2020$) past deadline without sworn BU clearance carry the active default label `🔴 EXPIRED_WITHOUT_BU`.
3. **Escrow Land Cost Baseline**: `finances` disclosures lack a separate statutory land cost column; Section 4(2)(l)(D) compliance models apply a standard 35% estimated land cost baseline heuristic.
4. **Data Coverage Awareness**: Full Form 1/3/5 filings are available for the 9 pilot projects statewide; for all other 17,700+ projects, statewide core tables (`projects`, `project_summaries`, `unit_transactions`, `noc_bu_records`, `banks`, `professionals`) govern.

---

## 2. Four-Phase Diligence Sequence

### Phase 1: Statutory Executive Dossier & BU Check
Invoke `get_project_dossier(project_id)` to generate the 4-quadrant executive markdown dossier:
- **Quadrant 1**: Escrow cash-flow and designated RERA banking structure.
- **Quadrant 2**: Structural engineer certified progress vs. calendar duration (velocity ratio).
- **Quadrant 3**: Town Planning (TPS), Final Plot (FP), Survey numbers, and inventory absorption.
- **Quadrant 4**: Municipal BU clearance, society formation, complaints, alterations, and professional contagion.

*Verification Checkpoint*: Ensure BU permission is explicitly `✅ BU GRANTED / VERIFIED` with certificate number and approval date. If marked `🔴 EXPIRED_WITHOUT_BU`, halt transaction until developer produces physical municipal BU certificate.

### Phase 2: Broker & Sales Claim Verification
Invoke `verify_sales_claim(project_id, claimed_rate, claimed_sold_pct, claimed_completion_date, asset_class="Residential")`:
- **Price Benchmarking**: Quotes are verified against the **Trailing 4-Quarter Booked Median** for that asset class, not the 5-year lifetime median.
- **Verdict Interpretation**:
  - `VERIFIED IN MARKET RANGE`: Quoted rate is within $[-10\%, +15\%]$ of contemporary registered deeds.
  - `EXAGGERATED / PREMIUM`: Quoted rate exceeds trailing median by $>15\%$. Use registered deed range to counter-negotiate.
  - `DISCOUNTED`: Quoted rate is $>10\%$ below registered median. Inspect floor location, dead-wall facing, or mandatory parking/amenity add-ons.
- **Stale Deed Warning**: If `stale_deed_warning == True`, the latest registered agreement is $>18$ months old; developer may be transacting via unregistered allotment letters.
- **Inventory Urgency**: If broker claims $90\%$ sold but statutory `booking_rate_pct` is $45\%$, flag `ARTIFICIAL SCARCITY`.

### Phase 3: Spatial Price Comps & Micro-Market Realization
Invoke `get_spatial_pricing_benchmark(project_id, asset_class="Residential")`:
- Inspect Tier 1 (2 km radius), Tier 2 (5 km radius), and Tier 3 (taluka-level) empirical transaction medians and Interquartile Ranges (IQR, 25th to 75th percentile).
- Check `unbooked_markup_pct`: measures the spread between developer asking price on unsold inventory and actual registered prices paid by existing buyers (statewide baseline is $+12.63\%$). Markups $>25\%$ indicate aggressive speculative pricing.

### Phase 4: Promoter Portfolio & Sister Scheme Contagion
Invoke `get_promoter_portfolio(project_id)`:
- Examines all projects linked under the developer via Composite Key (c) (shared professional license or bank IFSC/branch).
- Check `modern_expired_no_bu_count` across the promoter's portfolio: sister project abandonment indicates systemic cash-diversion or execution failure.

---

## 3. Red-Flag Escalation Matrix

| Risk Factor | Statutory Metric | Action / Guidance |
| :--- | :--- | :--- |
| **Delivery Default** | `🔴 EXPIRED_WITHOUT_BU` ($>6$ months overdue) | **High Risk**: Mandatory Form 1/2 inspection. Demand physical BU permission before signing. |
| **Pace Lag** | Velocity ratio $< 0.85x$ | **Delay Risk**: Physical progress is lagging calendar schedule. Refuse advance payment milestones. |
| **Escrow Drain** | 70% account closing balance $< ₹50,000$ | **Contagion Risk**: Developer has depleted designated retention account; risk of fund diversion. |
| **Layout Tampering** | Alterations count $> 2$ filings | **Regulatory Risk**: Promoter has modified sanctioned layouts post-launch under Section 14. |
| **Legal Disputes** | Complaints count $> 3$ applications | **Litigation Risk**: Multiple aggrieved allottees have filed formal GujRERA complaints. |
