# Goldfish Annotated Review Report

**Target:** `docs/PROPOSED_NEXT_STEPS_PLAN.md` (`full file`)  
**Date:** 2026-11-17  
**Status:** resolved (9/9 PROPOSE FIX accepted and applied to `docs/PROPOSED_NEXT_STEPS_PLAN.md`; 0 contested, 0 escalated, 0 declined)

---

## Executive Summary of Resolutions

All 9 findings raised across the 5 review stages (Zoom Out, Comprehension, Critic, Intermediate Zoom Out, Implementation Readiness) have been resolved:
1. **Tracked Binary Database Conflict:** Added pre-pull checkout to discard local mutations on `real_estate_intelligence/data/intelligence.sqlite`.
2. **Function Signature Correction:** Corrected method invocation to `self.auditor.calculate_escrow_runway(pid)` and `self.auditor.audit_credential_coverage(pid)`.
3. **Omnibus De-Scoping:** Severed large-scale Form 3 Parquet lake ingestion from the immediate milestone to prevent SQLite NOT NULL violations, $O(N)$ 6,001-query storms, Vis.js 10,000-node browser freezes, and benchmark degradation. Lake ingestion and server-side pagination are now formally partitioned into Milestone 2 (Architectural RFC).
4. **Host WDAC Security Constraints:** Formally documented host WDAC blocks on DuckDB/PyArrow C-extensions as prerequisites in the RFC track.
5. **Accurate File Paths:** Corrected all file paths to include the full package namespace (`real_estate_intelligence/real_estate_intelligence/ui/...`).
6. **UI Component Grounding:** Grounded UI cards in `content-dossier` Quadrant 1 (Statutory) and `#projectBanner`/Quadrant 4 (Financial), with explicit DOM element IDs and JavaScript controller binding updates.
7. **Worktree Command Portability:** Provided clean git worktree pruning commands.
8. **Test Runner Command Portability:** Corrected unittest discovery to include `-t real_estate_intelligence`.
9. **Plain-English Nomenclature:** Cleaned up marketing fluff and ungrounded claims throughout the document.

---

## Prioritized Findings & Applied Edits

### [Issue 1] [`implementation_readiness` + `codebase_details`] - Severity: Blocker
* **Affected Scope:** Step 1 (Git Reconciliation)
* **Discrepancy Description:** Tracked binary `intelligence.sqlite` has local modifications; `git pull --ff-only` would fail with an overwrite error.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Added pre-execution `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite`.

### [Issue 2] [`implementation_readiness` + `codebase_details`] - Severity: Blocker
* **Affected Scope:** Step 2 (Backend Route Augmentation)
* **Discrepancy Description:** `calculate_escrow_runway` called as standalone function with `(con, pid)` instead of method on `ProjectAuditor`.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Changed to `self.auditor.calculate_escrow_runway(pid)` and `self.auditor.audit_credential_coverage(pid)`.

### [Issue 3] [`design` + `implementation_readiness`] - Severity: Blocker
* **Affected Scope:** Step 3 (District-Level Lake Ingestion)
* **Discrepancy Description:** Parquet Form 3 files lack master project columns; triggers NOT NULL violation, 6,001-query storm, and browser freeze.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** De-scoped from Milestone 1 into dedicated Milestone 2 Architectural RFC.

### [Issue 4] [`implementation_readiness` + `codebase_details`] - Severity: Blocker
* **Affected Scope:** Step 3 (Dependencies)
* **Discrepancy Description:** Host WDAC blocks `_duckdb.pyd` and `_fs.pyd`.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Documented WDAC C-extension constraint as prerequisite in RFC track.

### [Issue 5] [`codebase_details`] - Severity: Major
* **Affected Scope:** File Paths
* **Discrepancy Description:** Omitted inner package namespace directory in paths.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Updated to `real_estate_intelligence/real_estate_intelligence/ui/server.py` and `ui/static/index.html`.

### [Issue 6] [`design` + `codebase_details`] - Severity: Major
* **Affected Scope:** UI DOM Mounting
* **Discrepancy Description:** Targeted nonexistent "Project Detail tab" without DOM IDs or controller updates.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Grounded in `content-dossier` Quadrant 1 and `#projectBanner`, specified DOM IDs (`#cardGovernanceCredentials`, `#kpiEscrowRunway`), and updated `loadProject(pid)` instructions.

### [Issue 7] [`codebase_details`] - Severity: Major
* **Affected Scope:** Worktree Command
* **Discrepancy Description:** Hardcoded absolute user path `C:/Users/adars/...`.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Replaced with dynamic worktree discovery instructions.

### [Issue 8] [`codebase_details`] - Severity: Major
* **Affected Scope:** Test Runner Command
* **Discrepancy Description:** `python -m unittest discover` failed without top-level directory flag.
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Added `-t real_estate_intelligence`.

### [Issue 9] [`style` + `design`] - Severity: Nit
* **Affected Scope:** Terminology
* **Discrepancy Description:** Jargon and promotional phrasing ("Sovereign Platform", "deep sample").
* ***AI Suggestion:*** PROPOSE FIX — **APPLIED**
* ***Edit Applied:*** Replaced with objective technical phrasing ("Intelligence Platform", "9-project seed dataset").

---

## Final Status & Handoff

* **Accepted Edits Applied:** 9 / 9
* **Contested Items:** 0
* **Escalated Items:** 0
* **Remaining Unaddressed Issues:** 0
* **Final Target Document:** `docs/PROPOSED_NEXT_STEPS_PLAN.md` is now 100% implementation-ready for Milestone 1 execution.
