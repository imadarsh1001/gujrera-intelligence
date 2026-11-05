# GujRERA Real Estate Intelligence

Domain vocabulary for the Gujarat RERA collection pipeline, statutory fact curation, and due-diligence analytics platform.

## Language

### Projects and Filings

**Project**:
A registered real estate development tracked by the Gujarat Real Estate Regulatory Authority with a unique project registration number.
_Avoid_: Scheme, site, property, listing

**Project Snapshot**:
An immutable, source-verified observation of all filings, form disclosures, and document references for a project within a single run.
_Avoid_: Raw run, project folder, JSON dump

**Run**:
An immutable observation period and storage archive capturing RERA portal responses against a verified source index snapshot.
_Avoid_: Crawl, batch, scrape, session

**Quarterly Progress Report (QPR)**:
A statutory quarterly filing submitted by a promoter updating physical milestone progression, booking tallies, and quarter-end status.
_Avoid_: Quarterly return, progress update

**Form 1**:
The statutory architect certificate detailing physical progress, tower construction percentages, and layout compliance.
_Avoid_: Architect report, FormOne

**Form 2**:
The statutory engineer certificate certifying structural construction milestones and quality compliance.
_Avoid_: Engineer report, FormTwo

**Form 3**:
The statutory chartered accountant certificate verifying estimated costs, cumulative incurred expenditure, allottee collections, and allowable escrow withdrawals.
_Avoid_: CA certificate, financial report, FormThree

**Form 4**:
The statutory architect completion certificate attesting that the project has reached physical handover and occupancy readiness.
_Avoid_: Completion certificate, handover report, FormFour

**Form 5**:
The statutory annual audit report submitted under Section 4(2)(l)(D) certifying that collected funds were utilized for the designated project.
_Avoid_: Annual compliance, annual report, FormFive

### Banking and Accounts

**Retention Escrow Account**:
The designated statutory bank account (Account Type 1) holding 70% of all allottee collections exclusively for construction and land costs.
_Avoid_: RERA account, main account, escrow

**Collection Account**:
The bank account (Account Type 2) into which 100% of allottee payments are initially deposited prior to 70% statutory escrow retention.
_Avoid_: Master account, current account

**Section 4(2)(l)(D) Over-Withdrawal**:
A statutory violation occurring when cumulative withdrawals from the 70% Retention Escrow Account exceed the certified allowable spend limit ($\text{Estimated Total Cost} \times \frac{\text{Physical Progress \%}}{100}$).
_Avoid_: Illegal spend, bad withdrawal

**Escrow Cash Runway**:
The modeled duration in months of solvency remaining in the 70% Retention Escrow Account based on the historical monthly construction expenditure burn rate.
_Avoid_: Cash buffer, runway time

### Quantitative & Forensic Analytics

**Longitudinal Price Trajectory & CAGR**:
The chronological quarterly progression of median realized rates per square foot derived exclusively from sworn registered agreement considerations, yielding an annualized Compound Annual Growth Rate.
_Avoid_: Average price trend, portal appreciation

**Completion Survival Curve**:
A semi-parametric time-to-event probability curve $S(t) = P(\text{Complete} > t)$ estimated via Cox Proportional Hazards and Breslow cumulative baseline hazards to forecast delivery delay percentiles ($p_{50}, p_{75}, p_{90}$).
_Avoid_: Delay estimate, target date

**Evidentiary Citation Contract**:
The strict zero-hallucination constraint requiring all analytical conclusions and AI agent assertions to reference verifiable database entities, statutory sections, or cryptographic PDF page SHA-256 hashes.
_Avoid_: LLM citation, source prompt

### Parties and Roles

**Promoter**:
The registered developer, enterprise, or individual holding statutory responsibility for executing and completing the project.
_Avoid_: Builder, sponsor, vendor

**Professional**:
A certified third-party practitioner (architect, structural engineer, chartered accountant, or contractor) who attests statutory project certificates.
_Avoid_: Consultant, vendor, signer
