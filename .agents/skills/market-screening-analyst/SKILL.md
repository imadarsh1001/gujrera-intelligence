---
name: market-screening-analyst
description: Macro and micro-market intelligence playbook for developer portfolio de-duplication, empirical spatial pricing spreads, micro-market absorption density, and quarterly appreciation trends.
---

# Market Screening & Developer Portfolio Analyst Playbook

This skill provides analytical guidance for investment committees, real estate funds, and market research teams evaluating developer track records, submarket price appreciation trends, and spatial supply-absorption dynamics across Gujarat.

---

## 1. Developer Track Record & Composite Key (c) Screening

Common developer brand names in Gujarat (such as *Shreeji*, *Radhe*, *Shivam*, *Nilkanth*, *Shaligram*) are frequently reused across separate, unrelated partnership LLPs in different cities. Merging them by name alone creates severe false-contagion distortions.

### De-Duplication Protocol
Invoke `get_promoter_portfolio(promoter_name="BRAND_NAME")`:
- **Disjoint Partitioning**: The engine builds an adjacency graph where edges require a verified Composite Key (c) anchor:
  1. A shared normalized professional license (`prof_licenses` with sensitive IDs scrubbed).
  2. OR a shared bank anchor (`ifsc_code` or `bank_name + branch_name`; never bare bank name).
  3. OR an identical non-null `promoter_id`.
- Projects without shared anchors remain in separate singleton clusters.
- **Linkage Confidence Assessment**:
  - `HIGH`: Cluster contains $\ge 2$ projects linked by verified professional licenses, bank IFSCs, or promoter IDs.
  - `MEDIUM`: Cluster contains a single project under an uncommon brand name.
  - `LOW`: Cluster contains an unanchored singleton under a common Gujarat brand prefix (homonym warning).
  - `PARTITIONED_MULTI_CLUSTER`: Returned at the top level when a search spans multiple disjoint clusters.
- **Portfolio Delivery Track Record**:
  - Compute total units developed vs. `modern_expired_no_bu_count`.
  - Developer Default Rate: $\text{DDR} = \frac{\text{modern\_expired\_no\_bu\_count}}{\text{total\_projects\_in\_cluster}}$.
  - Tier-1 Developers maintain $\text{DDR} = 0.0$ and have verified BU certificates across all completed schemes.

---

## 2. Micro-Market Spatial Density & Saturation Analysis

Invoke `get_spatial_density(project_id, radius_km=3.0, limit=20)`:
- Identifies competing registered developments within the immediate micro-market.
- **Key Screening Metrics**:
  - **Competitive Supply Index (CSI)**: Total active units under construction within 3 km.
  - **Micro-Market Absorption**: Weighted average `booking_rate_pct` across neighbouring developments.
  - **Unsold Overhang**: Total unbooked units across competitors. If micro-market unsold inventory exceeds 2,500 units, price realization will face downward pressure.
  - **Shared Infrastructure**: Pinpoints nearby schemes sharing identical Town Planning Scheme (TPS) boundaries or final plot layouts.

---

## 3. Longitudinal Price Velocity & Appreciation Trajectory

Invoke `get_pricing_appreciation_trend(project_id, asset_class="Residential")`:
- Evaluates registered quarterly transaction rates ($₹/\text{sq.ft.}$) from statutory deed disclosures.
- **Asset Class Isolation**: Always pass `asset_class="Residential"` (or `"Commercial"`) to prevent high-rate retail shops (which can reach $₹15,000+/ \text{sq.ft.}$) from distorting residential trends.
- **CAGR Calculation**:
  $$\text{CAGR} = \left(\frac{\text{Latest Quarter Median}}{\text{Base Quarter Median}}\right)^{\frac{1}{\Delta \text{Years}}} - 1$$
  - Sustainable Annual Real Estate Growth in Gujarat prime corridors: $6\% \text{ to } 12\%$.
  - Speculative Acceleration: $\text{CAGR} > 18\%$ indicates overheated marketing rounds or aggressive price escalation by the promoter.
- **Transaction Rate Velocity**:
  - Check `transaction_count` per quarter: a sudden drop from 40 deeds/quarter to $<5$ deeds/quarter signifies project stagnation or buyer fatigue.

---

## 4. Multi-Scheme Comparative Screening

Invoke `compare_projects(project_ids=[id1, id2, ...])`:
- Conducts side-by-side benchmarking across competing investment candidates.
- Evaluates:
  1. `booking_rate_pct` vs. `latest_form_one_progress_pct`.
  2. Construction velocity ratio ($>1.0x$ indicates ahead of schedule; $<0.85x$ indicates construction delay).
  3. Total complaints count and statutory quarterly defaults (`isDefault = YES`).
  4. BU clearance status across schemes.
