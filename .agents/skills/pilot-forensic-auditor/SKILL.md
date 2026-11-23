---
name: pilot-forensic-auditor
description: Forensic compliance and statutory audit playbook for deep Form 1/3/5 filings, Section 4(2)(l)(D) 70% escrow fund segregation, cost drop reversals, and QPR velocity verification.
---

# Pilot Forensic Auditor Playbook (Deep Statutory Due Diligence)

This skill provides an advanced forensic methodology for auditing deep Form 1 (Engineer), Form 2 (Architect), Form 3 (Chartered Accountant), Form 5 (Annual CA Audit), and Section 14 (Layout Amendment) statutory filings available for the deep-audit cohort in GujRERA.

---

## 1. Statutory Ingestion Scope & Transparency Rules

1. **Pilot Project Population**: Full multi-quarter financial and engineering filings exist for the 9 pilot schemes statewide (including Project `16562`, `16104`, `16107`, `16109`, etc.).
2. **Statewide Ingestion Transparency**: For statewide core projects where deep Form 3/Form 5 tables have not been ingested, `audit_discrepancies(project_id, include_skipped=True)` explicitly returns `SKIPPED_UNINGESTED` notices. An uningested table must **never** be cited as clean statutory compliance.
3. **Immutable Repository**: The local SQLite database (`data/intelligence.sqlite`) is tamper-evident and read-only. All audit leads are derived deterministically.

---

## 2. Forensic Audit Modules

### Module A: Section 4(2)(l)(D) 70% Escrow Segregation & Cash Runway
Invoke `get_escrow_and_finances(project_id)`:
- **Designated Banking Structure**:
  - `account_type == 1`: 70% Designated Retention Escrow Account. Funds can only be withdrawn for project construction and land cost in direct proportion to certified progress.
  - `account_type == 2`: 100% Collection Account.
- **Estimated Land Cost Heuristic**:
  - Because GujRERA financial filings do not feature an isolated statutory land expenditure column, Section 4(2)(l)(D) audit algorithms utilize a verified **35% estimated land cost baseline heuristic**.
- **Escrow Cash Runway**:
  $$\text{Monthly Spend Velocity} = \frac{\text{Withdrawals during Period}}{\text{Duration in Months}}$$
  $$\text{Cash Runway (Months)} = \frac{\text{Closing Balance in 70\% Account}}{\text{Monthly Spend Velocity}}$$
  - Runway $< 3\text{ months}$: Developer faces imminent liquidity crunch; high risk of construction halt.
  - Closing balance $< ₹50,000$: Flagged as severe liquidity depletion.

### Module B: Construction Velocity & Physical-Financial Synchrony
Invoke `audit_discrepancies(project_id, include_skipped=True)`:
- **Velocity Ratio ($\text{VR}$)**:
  $$\text{VR} = \frac{\text{Physical Progress \%}}{\text{Calendar Time Elapsed \%}}$$
  - $\text{VR} \ge 1.0x$: On schedule or accelerated.
  - $0.85x \le \text{VR} < 1.0x$: Moderate drag; monitor progress milestones.
  - $\text{VR} < 0.85x$: Severe delivery delay; developer unlikely to meet statutory handover deadline without substantial capital injection.
- **Cost Reversal Anomaly (High Severity)**:
  - If Form 3 cumulative incurred cost decreases between successive quarters ($C_{t} < C_{t-1}$), the auditor triggers a **🔴 HIGH RISK: Incurred Cost Drop** audit lead.
  - In civil engineering, cumulative construction spend is monotonically non-decreasing. A drop indicates that the CA or promoter revised previously reported figures downwards to rectify unverified withdrawals.

### Module C: Section 14 Layout Alteration Tracking
Invoke `get_regulatory_radar(project_id)`:
- RERA Section 14 mandates that developers cannot alter sanctioned layouts, building heights, or common amenity plans without the express written consent of at least two-thirds ($\frac{2}{3}\text{rds}$) of allottees.
- Inspect `alterations_count`:
  - $>0$ Post-Registration Alterations: Cross-examine physical application filings in the portal to verify that statutory 2/3rd allottee consent affidavits are on record.

### Module D: Form 5 CA Annual Compliance Audit
- RERA Section 4(2)(l)(D) third proviso mandates an annual audit by a practicing Chartered Accountant within 6 months of financial year-end.
- Inspect `form5_annual_audits`:
  - Verify every financial year during the project lifecycle has status `SUBMITTED`.
  - Check `isDefault = YES`: indicates formal notice of quarterly QPR disclosure default issued by the GujRERA Authority.
