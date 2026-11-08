# models — Typed Data Models & Schema Contracts

## Overview
Pure, dependency-free `dataclass` layer defining the typed record contracts exchanged between ingestion (`db.loader`), analytics, and the UI/MCP layers. This package performs no I/O; it only declares the shape of GujRERA statutory facts (projects, promoters, professionals, escrow banks, inventory, finances, compliance) and audit outputs (`DiscrepancyLead`, `DossierReport`).

## Interface
- `ProjectRecord` — master project fact with land/spatial identity (`tp_scheme`, `latitude`), legal handover milestones (`form_four_status`, `bu_status`), construction velocity fields (`velocity_ratio`, `engg_score_pct`), and regulatory radar counters (`complaints_count`, `default_quarters_count`) [schema.py:ProjectRecord]
- `PromoterRecord` — promoter identity with claimed vs. linked project counts (`linked_gujrera_projects_count`) [schema.py:PromoterRecord]
- `ProfessionalRecord` — project professional with `role` documented as `'architect'`, `'engineer'`, `'ca'`, `'contractor'` [schema.py:ProfessionalRecord]
- `BankRecord` — escrow/collection bank account; `account_type` documented as `1` = Retention/Escrow, `2` = Collection [schema.py:BankRecord]
- `QuarterlyProgressRecord` — quarterly Form 1/2/3 progress timeline row [schema.py:QuarterlyProgressRecord]
- `InventoryBlockRecord` — block-level booked/unbooked unit counts and `booking_rate_pct` [schema.py:InventoryBlockRecord]
- `FinancialRecord` — Form 3 financial filing; `filing_type` documented as `'index'` or `'latest'` [schema.py:FinancialRecord]
- `FormFiveRecord` — Form 5 annual CA compliance status per financial year [schema.py:FormFiveRecord]
- `NocBuRecord` — per-block Building Use (BU) permission record [schema.py:NocBuRecord]
- `UnitTransactionRecord` — unit-level Form 3 sale transaction with `status` defaulting to `"UNBOOKED"` [schema.py:UnitTransactionRecord]
- `DiscrepancyLead` — audit finding; `category` documented as `'financial'`, `'schedule'`, `'inventory'`, `'statutory'`, `'regulatory'` and `severity` as `'HIGH'`, `'MEDIUM'`, `'LOW'`, `'INFO'` [schema.py:DiscrepancyLead]
- `DossierReport` — aggregate dossier container composing a `ProjectRecord`, `PromoterRecord`, and lists of professionals, banks, blocks, timeline, finances, compliance history, BU records, leads, and `evidence_hashes` [schema.py:DossierReport]
- Package exports via `__all__`: `ProjectRecord`, `PromoterRecord`, `ProfessionalRecord`, `QuarterlyProgressRecord`, `InventoryBlockRecord`, `FinancialRecord`, `DiscrepancyLead`, `DossierReport` [__init__.py:__all__]

## Invariants
- `models/__init__.py` re-exports only 8 of the 12 dataclasses; `BankRecord`, `FormFiveRecord`, `NocBuRecord`, and `UnitTransactionRecord` are intentionally absent from `__all__` and must be imported from `models.schema` directly [__init__.py:__all__]
- `account_type` semantics are fixed: `1` = 70% Retention/Escrow account, `2` = 100% Collection account; consumers (e.g., `analytics.audit`) rely on this numeric encoding [schema.py:BankRecord]
- All date-bearing fields are plain `Optional[str]` (ISO-style strings), not `date` objects; parsing is deferred to consumers [schema.py:ProjectRecord]
- `DiscrepancyLead.severity` is declared as `'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'` in the schema annotation; note that `analytics/audit.py` additionally emits `'CRITICAL'` for statutory escrow over-withdrawal [schema.py:DiscrepancyLead]

## Side Effects
- None — pure dataclass declarations with no I/O, network, or process state [schema.py]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
