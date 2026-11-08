# Goldfish Annotated Review Report

> **Process artifact (2026-11-09).** Machine-generated audit trail of the six-round EGM contract review. Terminology: EGM = Elephant-and-Goldfish Model; "Goldfish" reviewers are fresh-context subagent auditors; a "round" is one review → resolve → fix cycle; "auto accept" marks user-approved fix batches. Outcome: 96 findings raised, 94 fixes applied to the `EGM.md` contracts (which are authoritative), 2 recorded partial declines. Several file paths referenced here (`gujrera_pipeline/`, `legacy/`) belong to the private repository or gitignored directories and are absent from a public clone; the seven `legacy/**/EGM.md` contracts were reviewed but are not published anywhere.

Status: resolved (Round 0 — 9/9 PROPOSE FIX accepted via "auto accept"; 0 contested, 0 escalated, 0 declined)

## Round 1

Status: resolved (35/35 PROPOSE FIX accepted via "auto accept", applied as 32 edits across 9 files; 0 contested, 0 escalated, 0 declined)

**Target:** Round 0 — drift-report findings over 8 EGM contracts (`full file` each):
`real_estate_intelligence/real_estate_intelligence/agent/EGM.md`, `real_estate_intelligence/real_estate_intelligence/analytics/EGM.md`, `real_estate_intelligence/scripts/EGM.md`, `real_estate_intelligence/EGM.md`, `gujrera_pipeline/data/discovery/EGM.md`, `legacy/eda_prototypes/webapp/EGM.md`, `legacy/research_samples/EGM.md`, `legacy/scrapy_crawler/RERA/EGM.md`

**Source:** `2026-11-06_DRIFT_REPORT.md` (drift review verified every claim against source; findings reproduced here for resolution).

## Prioritized Findings & AI Suggestions

### [Issue 1] [`codebase_details`] - Severity: Blocker
*   **Affected Scope:** agent/EGM.md L15 (Invariants, key resolution order bullet)
*   **Discrepancy Description:** Contract states "if the explicit key starts with `\"sk-\"` or env `OPENAI_API_KEY` is set, the OpenAI loop is used instead." Actual code (`agent/copilot.py:224-232`): `key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")`; any truthy `api_key` — including `sk-`-prefixed — is passed directly to `_run_gemini_loop` and sent to the Gemini endpoint. The `sk-` branch is dead code for explicit keys (reachable only when `key` is falsy, which requires `api_key` falsy). The OpenAI loop runs only when no Gemini-family key resolves AND env `OPENAI_API_KEY` is set.
*   **Rationale:** The documented routing of explicit `sk-` keys to OpenAI does not exist in the source; the contract asserts an invariant the code does not implement.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Factual error in a fresh contract; the fix makes the invariant match the code exactly, including noting the unreachable branch.
*   ***Proposed Edit:***
    *   Location: agent/EGM.md, Invariants bullet "Key resolution order"
    *   Change: Replace the single bullet with two bullets:
        "- Key resolution order: explicit `api_key` arg, else env `GEMINI_API_KEY`, else env `GOOGLE_API_KEY` — whichever resolves first drives the Gemini loop; an explicit key is never rerouted, so an `sk-`-prefixed key is still sent to the Gemini endpoint [copilot.py:run_query]
        - The OpenAI loop runs only when no Gemini-family key resolves at all and env `OPENAI_API_KEY` is set; its key comes from `OPENAI_API_KEY` (the `sk-`-prefix test inside the OpenAI key selection is unreachable when an explicit key is supplied) [copilot.py:run_query]"

### [Issue 2] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L7 (Interface, `ProjectAuditor.audit_project` bullet)
*   **Discrepancy Description:** Contract says "(9 deterministic checks)"; `audit.py:14-296` contains 10 lead-emitting check blocks — checks 1-3, then the separate `# 3b. Statutory Section 4(2)(l)(D) Escrow Over-Withdrawal Audit` block (line 128, emits its own `CRITICAL` lead), then checks 4-9.
*   **Rationale:** Count understates the emitted lead vocabulary by one; the contract's own Invariants section documents the CRITICAL over-withdrawal check.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** One-word factual fix that removes an internal inconsistency in the same document.
*   ***Proposed Edit:***
    *   Location: analytics/EGM.md, Interface first bullet
    *   Change: "(9 deterministic checks)" → "(10 deterministic checks: checks 1-3, the separate statutory Section 4(2)(l)(D) escrow over-withdrawal block, then checks 4-9)"

### [Issue 3] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** scripts/EGM.md L4 (Overview)
*   **Discrepancy Description:** "All three ... reconfigure stdout to UTF-8 before printing" is false for `verify_server.py` (`scripts/verify_server.py:1-5` never imports `sys`); only `run_ingest.py:7` and `build_graph.py:6` do.
*   **Rationale:** Universal claim contradicted by one of the three scripts.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** Precise scope correction; cheap.
*   ***Proposed Edit:***
    *   Location: scripts/EGM.md, Overview sentence
    *   Change: "All three import the installed `real_estate_intelligence` package and reconfigure stdout to UTF-8 before printing." → "All three import the installed `real_estate_intelligence` package; `run_ingest.py` and `build_graph.py` reconfigure stdout to UTF-8 before printing (`verify_server.py` does not)."

### [Issue 4] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L21 (Global Invariants, dependency-direction bullet)
*   **Discrepancy Description:** Blueprint claims strict (acyclic) layering, but `db/loader.py:16` imports `from ..documents.parser import classify_document_type, extract_pdf_pages` while `documents/worker.py:12-13` imports `..db.database` and `..db.fts` — `db` ↔ `documents` mutual dependency; the `db -> documents` edge is missing from the map. All individually listed edges do exist.
*   **Rationale:** The dependency map is the contract's architectural claim; a hidden cycle misleads future editors.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** Document the actual seam rather than an idealized layering; the cycle is real and deliberate (inline PDF extraction during ingestion).
*   ***Proposed Edit:***
    *   Location: real_estate_intelligence/EGM.md, Global Invariants last bullet
    *   Change: "Cross-package dependency direction is strict: `models` has no internal imports; `db` depends on `models`/`config`; `analytics`/`graph`/`documents` depend on `db`; `mcp` composes analytics; `agent` and `ui` compose `mcp`; `cli` composes everything" → "Cross-package dependency direction is strict with one deliberate seam: `models` has no internal imports; `db` depends on `models`/`config`; `analytics`/`graph`/`documents` depend on `db`; `mcp` composes analytics; `agent` and `ui` compose `mcp`; `cli` composes everything. The seam: `db.loader` imports `documents.parser` for inline PDF text extraction during ingestion, while `documents.worker` imports `db` for queue persistence — a mutual `db` ↔ `documents` dependency [db/loader.py:16, documents/worker.py:12-13]"

### [Issue 5] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L11 (Interface, `main.js` bullet)
*   **Discrepancy Description:** Cited header filename `main-es2015.194bdfcbbb2428a5709.js.LICENSE.txt`; the actual header at `data/discovery/main.js:1` reads `main-es2015.194bdf7cbbb2428a5709.js.LICENSE.txt` (contract variant appears 0 times in the file).
*   **Rationale:** Typo in a quoted identifier; quotes must match the artifact byte-for-byte.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** Exact-quote accuracy.
*   ***Proposed Edit:***
    *   Location: discovery/EGM.md, Interface `main.js` bullet
    *   Change: `194bdfcbbb2428a5709` → `194bdf7cbbb2428a5709`

### [Issue 6] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** legacy/eda_prototypes/webapp/EGM.md L20 (Side Effects, in-place mutation bullet)
*   **Discrepancy Description:** Claims `process_data` "Mutates the passed DataFrame in place ... (in-column lowercase reassignment and dtype casts)". Only the lowercase reassignment (`gujrera_streamlit.py:20-21`) mutates the caller's frame; the dtype casts run after the local rebinding `df = df[columns_order]` (`gujrera_streamlit.py:47`), which creates a new frame.
*   **Rationale:** Side-effect claim overstates what touches the caller's object.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** Precision fix; matters to anyone reusing the function.
*   ***Proposed Edit:***
    *   Location: webapp/EGM.md, Side Effects second bullet
    *   Change: "- Mutates the passed DataFrame in place inside `process_data` (in-column lowercase reassignment and dtype casts) [gujrera_streamlit.py:process_data]." → "- Partially mutates the passed DataFrame in place inside `process_data`: only the in-column lowercase reassignment touches the caller's frame; the dtype casts and datetime parsing operate on the new frame created by `df = df[columns_order]` [gujrera_streamlit.py:process_data]."

### [Issue 7] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L23 (Invariants, validation bullet)
*   **Discrepancy Description:** "`load_projects()` and `load_ids()` raise `ValueError` when a configured project ID is missing from the index or a project name mismatches" — only `collect_nine_projects.load_projects` validates names (`collect_nine_projects.py:88-89`); `fetch_four_projects.load_ids` (`fetch_four_projects.py:46-63`) raises solely on missing IDs.
*   **Rationale:** Attribute differs per function; the joint claim is wrong for `load_ids`.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** Split the claim per function.
*   ***Proposed Edit:***
    *   Location: research_samples/EGM.md, Invariants second bullet
    *   Change: "- `load_projects()` and `load_ids()` raise `ValueError` when a configured project ID is missing from the index or a project name mismatches [collect_nine_projects.py:load_projects] [fetch_four_projects.py:load_ids]." → "- `collect_nine_projects.load_projects()` raises `ValueError` when a configured project ID is missing from the index or the project name mismatches (casefold compare) [collect_nine_projects.py:load_projects]; `fetch_four_projects.load_ids()` raises `ValueError` only on missing IDs and performs no name validation [fetch_four_projects.py:load_ids]."

### [Issue 8] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L4 (Overview)
*   **Discrepancy Description:** `gujrera_site_api_discovery_2026-10-15.md` exists in the directory but is not mentioned, unlike sibling contracts which enumerate human-maintained docs as non-contracted assets.
*   **Rationale:** Enumeration completeness consistent with sibling contracts.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** One sentence; prevents "is this file governed?" ambiguity.
*   ***Proposed Edit:***
    *   Location: research_samples/EGM.md, end of Overview paragraph
    *   Change: Append: " The directory also holds `gujrera_site_api_discovery_2026-10-15.md` (human-maintained endpoint-discovery notes; non-contracted, left untouched)."

### [Issue 9] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** legacy/scrapy_crawler/RERA/EGM.md L4 (Overview)
*   **Discrepancy Description:** Overview says the directory "holds only the deployment contracts - `scrapy.cfg` and `setup.py` - plus the prebuilt `guj_rera.egg`"; it also contains `build/lib/RERA/` (full duplicate source tree) and `project.egg-info/`, unmentioned.
*   **Rationale:** "holds only" is false; unlisted build artifacts invite confusion about what is governed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:** Scope-accuracy fix.
*   ***Proposed Edit:***
    *   Location: scrapy_crawler/RERA/EGM.md, Overview first sentence
    *   Change: "It holds only the deployment contracts - `scrapy.cfg` and `setup.py` - plus the prebuilt `guj_rera.egg`; the actual code lives in the child `RERA/` package." → "It holds the deployment contracts - `scrapy.cfg` and `setup.py` - plus build artifacts (`guj_rera.egg`, the `build/lib/RERA/` duplicate source tree, `project.egg-info/`; all pruned from contracts); the actual code lives in the child `RERA/` package."

---

Bookkeeping note: the drift report header said "8 findings"; the correct count is 9 findings across 8 files (1 blocker, 8 nits) — 15 of 23 total contracts show no drift (14 child contracts plus the self-verified root). No CONTEST or ESCALATE items in Round 0; every finding cites code the reviewer could read, and each matches the current source.

## Round 1 (reviewer swarm)

Status: resolved (35/35 PROPOSE FIX accepted via "auto accept", applied as 32 edits across 9 files; 0 contested, 0 escalated, 0 declined)

**Target:** the 8 drift-affected contracts (`full file` each) — reviewed post-Round-0-fixes by 4 Goldfish reviewers (all statuses: `completed`; codebase_details completed on retry). 35 deduplicated findings (10 Major, 25 Nit, 0 Blocker). All categorized PROPOSE FIX; evidence spot-verified by the Elephant (loader.py:166, survival.py:218, claims_checker.py:63-64, copilot.py:216, filesystem listings, GLOSSARY.md).

### [R1-1] [`codebase_details`] - Severity: Major
*   **Affected Scope:** research_samples/EGM.md L22 (Invariants) — same wrong claim repeated in legacy/EGM.md L12
*   **Discrepancy Description:** Contract says the required form-index CSV "does not exist in the current tree" and points to `../scrapy_crawler/RERA/collected_data/` for related captures. The exact file exists at the workspace root `collected_data/form_ids_2026-10-11_21_23_00.csv`; the scrapy captures hold only the older `form_ids_2024-10-13 18_55_32.csv`.
*   **Rationale:** Implies the input data is lost and directs restoration to a directory lacking it.
*   ***AI Suggestion:*** PROPOSE FIX — state both facts: CSV survives at workspace root; code-resolved `legacy/collected_data/` path is what's missing.
*   ***Proposed Edit:*** Rewrite the invariant (and the matching cross-cutting note in legacy/EGM.md) to: exact CSV exists at repository-root `collected_data/form_ids_2026-10-11_21_23_00.csv`; collectors fail until it is restored to `legacy/collected_data/` (or `ROOT` pointed at the workspace root).

### [R1-2] [`style`+`comprehension`] - Severity: Major
*   **Affected Scope:** rei/EGM.md L6 (Data flow) vs L19 (Global Invariants)
*   **Discrepancy Description:** Data flow calls `documents` one of the "read-side engines"; Global Invariants list `documents.worker` among database mutators (worker.py does UPDATE/commit document_jobs).
*   **Rationale:** The root blueprint contradicts its own write-boundary invariant on the same page.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "-> `analytics`, `graph`, `documents`, `mcp`, `agent`, and `ui` subsystems (read-side except `documents.worker`, which mutates job rows; see Global Invariants) ->"

### [R1-3] [`style`] - Severity: Major
*   **Affected Scope:** agent/EGM.md L4 (Overview)
*   **Discrepancy Description:** "guarantees grounded answers" — no enforcing mechanism; `run_query` returns `final_text` as-is.
*   **Rationale:** Uncalibrated capability claim.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "grounds answers in tool output by injecting `project_id` and returning tool citations".

### [R1-4] [`style`] - Severity: Major
*   **Affected Scope:** research_samples/EGM.md L4 (Overview)
*   **Discrepancy Description:** "capture redacted GujRERA portal API samples" contradicts the privacy invariants — raw captures are unredacted; redaction applies only to report outputs. (Raised independently by style and codebase_details.)
*   **Rationale:** Privacy-property inversion on the exact artifacts the contract says to keep private.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "capture GujRERA portal API samples ... and build a redacted, human-readable due-diligence report (redaction applies to the generated report outputs, not the raw captures)".

### [R1-5] [`comprehension`] - Severity: Major
*   **Affected Scope:** analytics/EGM.md L16/26/27 (Invariants)
*   **Discrepancy Description:** `velocity_ratio` — the metric behind every HIGH/MEDIUM/delayed classification — is never defined.
*   **Rationale:** Thresholds are uninterpretable without the formula.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Define at first use: "velocity ratio (`velocity_ratio` = engineer-progress % ÷ time-elapsed %, computed in `db/loader.py:166`)".

### [R1-6] [`comprehension`] - Severity: Major
*   **Affected Scope:** analytics/EGM.md L16 (Invariants)
*   **Discrepancy Description:** "Form 5" never grounded.
*   **Rationale:** Hard-coded business rule unverifiable without statutory context.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Form 5 (the statutory annual CA audit report under Section 4(2)(l)(D); see GLOSSARY.md)".

### [R1-7] [`comprehension`] - Severity: Major
*   **Affected Scope:** analytics/EGM.md L27 (Invariants)
*   **Discrepancy Description:** "BU" never expanded at the survival-model event definition.
*   **Rationale:** Event definition drives what the model learns.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "`\"Approved\"` in `bu_status` (BU = Building Use permission)".

### [R1-8] [`comprehension`] - Severity: Major
*   **Affected Scope:** analytics/EGM.md L12 (Interface)
*   **Discrepancy Description:** "TP scheme" never expanded.
*   **Rationale:** Public API keyed on an undefined domain entity.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "get_tp_scheme_summary(tp_scheme, district=None) (TP = Town Planning scheme, a land-identifier grouping)".

### [R1-9] [`comprehension`] - Severity: Major
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L4/7/14-15
*   **Discrepancy Description:** "Form 3" never grounded though it is the directory's raison d'être.
*   **Rationale:** Statutory artifact unidentified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Gloss in Overview: "Form 3 PDFs — the statutory quarterly chartered-accountant certificates (see GLOSSARY.md)".

### [R1-10] [`comprehension`] - Severity: Major
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L9 (Interface)
*   **Discrepancy Description:** FRN / UDIN never expanded.
*   **Rationale:** They are the literal search terms the script greps for.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "FRN (ICAI Firm Registration Number)/UDIN (Unique Document Identification Number)".

### [R1-11] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L28 (Invariants)
*   **Discrepancy Description:** survival_curve "spans 0-120 months"; `survival.py:218` uses `range(0, 125, 3)` → 0-123.
*   **Rationale:** Consumer sizing the curve mis-handles the final point.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "spans 0-123 months in 3-month steps (`range(0, 125, 3)`)".

### [R1-12] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L14 (Invariants)
*   **Discrepancy Description:** "when both LLM loops fail" — only one loop runs per call; no cross-provider fallback.
*   **Rationale:** Implies a fallback chain that does not exist.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "when no key is resolvable or the single selected LLM loop fails (one loop per call: Gemini if a Gemini-family key resolves, otherwise OpenAI)".

### [R1-13] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L10 (Interface)
*   **Discrepancy Description:** `provider="gemini"` parameter is never read (copilot.py:216 only occurrence) — dead parameter.
*   **Rationale:** Documenting an inert parameter as meaningful invites wrong caller behavior.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Append: "(note: `provider` is currently never read — loop selection is driven solely by key resolution)".

### [R1-14] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** rei/EGM.md L19 (Global Invariants)
*   **Discrepancy Description:** "`analytics`, `mcp`, `ui`, and `agent` are read-only consumers" — their constructors apply DDL via `get_connection` and `KnowledgeGraph.__init__` (graph_nodes/graph_edges CREATE TABLE + commit).
*   **Rationale:** Core safety invariant only true of data mutation; exception undocumented.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "...are read-only consumers (their constructors may apply idempotent schema/DDL via `get_connection` and `KnowledgeGraph.__init__`)".

### [R1-15] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L10 (Interface)
*   **Discrepancy Description:** Three captured probes unmentioned: `architect157.json`, `architect_coa.json`, `engineer10717.json`.
*   **Rationale:** Partial inventory presented as complete.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Append to the probe list: "plus additional captured probes `architect157.json`, `architect_coa.json`, `engineer10717.json`".

### [R1-16] [`comprehension`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L4 (Overview)
*   **Discrepancy Description:** "deterministic UI copilot" — bare concept, no cross-reference.
*   **Rationale:** Failure-mode behavior half-specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "the deterministic, keyword-routed copilot in the `ui` subsystem (see [../ui/EGM.md])".

### [R1-17] [`comprehension`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L7/16/18 (Invariants)
*   **Discrepancy Description:** Section 4(2)(l)(D) not connected to the 70% retention rule it mandates.
*   **Rationale:** The over-withdrawal threshold looks arbitrary without the connection.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(RERA Section 4(2)(l)(D) — the section mandating the 70% retention escrow; see GLOSSARY.md)".

### [R1-18] [`comprehension`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L19 (Invariants)
*   **Discrepancy Description:** "statutory booking rate" has no antecedent.
*   **Rationale:** Ambiguous denominator in the ARTIFICIAL SCARCITY rule.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "the filing's official booked percentage (`booking_rate_pct`)".

### [R1-19] [`comprehension`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L20 (Invariants)
*   **Discrepancy Description:** "contagion risk" unexplained at point of use; no cross-reference to the graph contract.
*   **Rationale:** Domain jargon whose project-specific meaning is unstated.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(contagion = shared professionals/banks linking this project to complaint-bearing sister projects; see [../graph/EGM.md])".

### [R1-20] [`comprehension`] - Severity: Nit
*   **Affected Scope:** rei/EGM.md L4 (Overview)
*   **Discrepancy Description:** "eight subsystems" never enumerated.
*   **Rationale:** Organizing claim the reader cannot verify.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "eight subsystems (`models`, `db`, `documents`, `analytics`, `graph`, `mcp`, `agent`, `ui`)".

### [R1-21] [`comprehension`+`style`] - Severity: Nit
*   **Affected Scope:** rei/EGM.md L19 (Global Invariants)
*   **Discrepancy Description:** "the `ingest`/docworker scripts" — no such files exist; these are CLI subcommands (cmd_ingest, cmd_docworker in cli.py).
*   **Rationale:** Sends a reader hunting for nonexistent files in the write-boundary invariant.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "the `ingest` and `docworker` CLI subcommands (`cli.py:cmd_ingest`, `cli.py:cmd_docworker`)".

### [R1-22] [`comprehension`] - Severity: Nit
*   **Affected Scope:** legacy/eda_prototypes/webapp/EGM.md L4 (Overview)
*   **Discrepancy Description:** "Form 3 Parquet dataset" unexplained in this contract.
*   **Rationale:** The rendered dataset's meaning is unclear.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(Form 3 = the statutory quarterly CA certificate whose unit rows carry booking/transaction data)".

### [R1-23] [`comprehension`] - Severity: Nit
*   **Affected Scope:** research_samples/EGM.md L14 (Interface, stage 2)
*   **Discrepancy Description:** Form 1/2/3 numbering unexplained.
*   **Rationale:** Stage purpose decipherable only with GujRERA form knowledge.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Form 1/2/3 IDs (the quarterly architect/engineer/CA certificates; see GLOSSARY.md)".

### [R1-24] [`structural`] - Severity: Nit
*   **Affected Scope:** legacy/eda_prototypes/webapp/EGM.md L9 (Interface) / L24-25 (Verification)
*   **Discrepancy Description:** Launch command placed as an Interface bullet; Peanut template reserves run commands for Verification, and sibling contracts follow that.
*   **Rationale:** Section-role inconsistency.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Remove the Interface bullet; Verification becomes "- Run (manual): `streamlit run gujrera_streamlit.py` - no automated tests, manifests, or lint configuration exist for this standalone UI prototype."

### [R1-25] [`style`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L19 (Invariants)
*   **Discrepancy Description:** "Gemini endpoint is fixed to" lacks the article vs. parallel "The OpenAI loop reads".
*   **Rationale:** Sentence-level parallelism.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "The Gemini endpoint is fixed to".

### [R1-26] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L4 (Overview)
*   **Discrepancy Description:** "Seven independent modules" contradicted by line 20 (dossier composes auditor + graph).
*   **Rationale:** "Independent" is undefined and contradicted in-file.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Seven modules:" (drop the adjective).

### [R1-27] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L31 (Side Effects)
*   **Discrepancy Description:** "Read-mostly" hedge implies writes exist while the clause says none write curated tables.
*   **Rationale:** Speculative hedge in a factual claim (but constructors do apply DDL — see R1-14 nuance).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Read-only over curated rows: all modules query the shared SQLite connection; none write curated rows (a module that owns its connection applies schema DDL via `get_connection` at construction)".

### [R1-28] [`style`] - Severity: Nit
*   **Affected Scope:** scripts/EGM.md L8/L9/L10 (Interface ×3)
*   **Discrepancy Description:** "reconnects" (no prior connection), "boots setup_backends()" (verb mismatch), "`python scripts/<name>.py`-style executable" (ungrammatical).
*   **Rationale:** Copy accuracy.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "connects to the default database" / "initializes backends via `IntelligenceRequestHandler.setup_backends()` on an ephemeral HTTPServer" / "Each file is executable as `python scripts/<name>.py` via its `if __name__ == \"__main__\"` block".

### [R1-29] [`style`] - Severity: Nit
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L10 (Interface)
*   **Discrepancy Description:** "large" is an unquantified size word (file is 2,962,906 bytes).
*   **Rationale:** Uncalibrated descriptor in an evidence-cited inventory.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(2.9 MB engineer listing dump)".

### [R1-30] [`style`] - Severity: Nit
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L4 vs L26
*   **Discrepancy Description:** "One-off" vs "ad-hoc" — two labels for one concept.
*   **Rationale:** Terminology consistency.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Verification: "these ad-hoc scripts" → "these one-off scripts".

### [R1-31] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/eda_prototypes/webapp/EGM.md L20 (Side Effects)
*   **Discrepancy Description:** "in-column lowercase reassignment" is a coined compound (introduced by the Round 0 fix).
*   **Rationale:** The key mutation claim hinges on an unclear phrase.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "only the per-column lowercase reassignment (`df[col] = ...` inside the loop) touches the caller's frame".

### [R1-32] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/scrapy_crawler/RERA/EGM.md L14 (Invariants)
*   **Discrepancy Description:** "frozen build artifact" ambiguous.
*   **Rationale:** Undefined state adjective; operative fact is non-auto-update.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "a prebuilt artifact that does not update automatically".

### [R1-33] [`style`] - Severity: Nit
*   **Affected Scope:** rei/EGM.md L21 (Global Invariants)
*   **Discrepancy Description:** "strict with one deliberate seam: ... The seam:" — double-colon structure misdirects (introduced by the Round 0 fix).
*   **Rationale:** Reader must reread to find the exception.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "strict, with one deliberate seam. `models` has no internal imports; ...".

No CONTEST or ESCALATE items in Round 1; every finding was verified against source or filesystem before categorization.

## Round 2

Status: resolved (15/15 PROPOSE FIX accepted via "auto accept", applied as 20 edits across 7 files; 1 partial DECLINE recorded [R2-15 suite-wide dash normalization]; 0 contested, 0 escalated. Comprehension reviewer: **not run** — failed twice on harness concurrency limit, so Round 2 is not a clean round by rule.)

**Target:** the same 8 contracts (`full file` each), post-Round-1-fixes. Reviewer statuses: codebase_details `completed` (on retry), structural `completed`, style `completed` (on retry), comprehension **not run** (failed twice on harness concurrency limit). 16 deduplicated findings (3 Major, 13 Nit): 15 PROPOSE FIX, 1 DECLINE (partial). Elephant spot-verified the key evidence (discovery scripts resolve `../runs/...`; `network.py` contagion includes promoters/prior projects; `engineer10717.json` is an error body; `get_connection` applies DDL).

### [R2-1] [`style`] - Severity: Major
*   **Affected Scope:** scripts/EGM.md L20 (Side Effects)
*   **Discrepancy Description:** "it does not write to the database" contradicted by its own parenthetical and by `setup_backends()` → `get_connection` (pragmas/DDL, creates the DB if absent).
*   ***AI Suggestion:*** PROPOSE FIX — "it writes no data rows, but `setup_backends()` applies schema pragmas/DDL via `get_connection` (which creates the default database if absent)".

### [R2-2] [`style`] - Severity: Major
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L23 (Side Effects)
*   **Discrepancy Description:** "No files are written by any script in this directory" contradicted two lines earlier by `sqlite3.connect` creating an empty `manifest.sqlite` when missing.
*   ***AI Suggestion:*** PROPOSE FIX — "No script here writes reports, captures, or data files; the only disk mutation is `sqlite3.connect` creating an empty `manifest.sqlite` when the run manifest is missing."

### [R2-3] [`style`] - Severity: Major
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L10 (Interface)
*   **Discrepancy Description:** "additional captured probes" states no distinguishing criterion and misgroups: `architect157.json`/`architect_coa.json` are successful profile payloads; `engineer10717.json` is an error body ("No value present").
*   ***AI Suggestion:*** PROPOSE FIX — regroup as "not-found/error probes ... `engineer10717.json`, and successful profile probes `architect157.json`, `architect_coa.json`".

### [R2-4] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L14 (Invariants)
*   **Discrepancy Description:** "run directory exists relative to this folder" — code resolves `Path(__file__).parent.parent / "runs" / ...`, i.e. relative to `data/`, not `discovery/`.
*   ***AI Suggestion:*** PROPOSE FIX — "`../runs/nine_projects_2026_10_15` (resolved from this folder's parent, `data/`)".

### [R2-5] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L20 (Invariants)
*   **Discrepancy Description:** Contagion gloss says "shared professionals/banks" but `trace_contagion_risk` matches any shared edge target — promoters (`DEVELOPED_BY`) and `PriorProject` (`PRIOR_PORTFOLIO`) also trigger.
*   ***AI Suggestion:*** PROPOSE FIX — "any shared entity — professionals, banks, promoters, or prior projects".

### [R2-6] [`structural`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L16, discovery/EGM.md L4, research_samples/EGM.md L14
*   **Discrepancy Description:** "see GLOSSARY.md" is a bare filename that does not resolve from those directories (GLOSSARY.md lives at the repository root); every other cross-file pointer in the corpus is a resolvable relative path.
*   ***AI Suggestion:*** PROPOSE FIX — convert to markdown links: `../../../GLOSSARY.md` (analytics, discovery), `../../GLOSSARY.md` (research_samples).

### [R2-7] [`structural`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L21 (Global Invariants)
*   **Discrepancy Description:** Citation `[db/loader.py:16, documents/worker.py:12-13]` omits the `real_estate_intelligence/` prefix every other reference in the blueprint uses.
*   ***AI Suggestion:*** PROPOSE FIX — `[real_estate_intelligence/db/loader.py:16, real_estate_intelligence/documents/worker.py:12-13]`.

### [R2-8] [`style`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L4 (Overview)
*   **Discrepancy Description:** "Falls back to `None`" inverts the direction — `run_query` returns `None`; the caller falls back.
*   ***AI Suggestion:*** PROPOSE FIX — "Returns `None` when no API key is configured or the API loop fails; the caller then falls back to the deterministic, keyword-routed copilot in the `ui` subsystem (see [../ui/EGM.md])."

### [R2-9] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L31 (Side Effects)
*   **Discrepancy Description:** "Read-only over curated rows ... none write curated rows" — synonym redundancy in one bullet.
*   ***AI Suggestion:*** PROPOSE FIX — "all modules query the shared SQLite connection and write no curated rows".

### [R2-10] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L16 (Invariants)
*   **Discrepancy Description:** Section 4(2)(l)(D) glossed twice and "see GLOSSARY.md" twice in one sentence (artifact of the Round 1 fix).
*   ***AI Suggestion:*** PROPOSE FIX — Form 5 gloss becomes "the statutory annual CA audit report; see [GLOSSARY.md](../../../GLOSSARY.md)".

### [R2-11] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/eda_prototypes/webapp/EGM.md L4 (Overview)
*   **Discrepancy Description:** "archived"/"kept read-only"/"for historical reference" triple-restates status and diverges from sibling legacy contracts' phrasing.
*   ***AI Suggestion:*** PROPOSE FIX — "Archived legacy material from the 2024-2025 exploratory phase of the GujRERA project, superseded by the `gujrera_pipeline` rewrite and kept read-only."

### [R2-12] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L4 (Overview)
*   **Discrepancy Description:** "intentionally privacy-aware" is a self-assessing buzzword; the facts carry the claim.
*   ***AI Suggestion:*** PROPOSE FIX — drop the lead-in.

### [R2-13] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L32 (Side Effects)
*   **Discrepancy Description:** "`probe_site_endpoints.py` also probes but discards bodies" — missing objects force the reader to supply them.
*   ***AI Suggestion:*** PROPOSE FIX — "also issues requests to the portal but discards the response bodies".

### [R2-14] [`style`] - Severity: Nit
*   **Affected Scope:** cross-file: discovery/EGM.md L8, webapp/EGM.md, research_samples/EGM.md L10 vs analytics/scripts
*   **Discrepancy Description:** "hardcoded" vs "hard-coded" — two spellings for one concept across the suite.
*   ***AI Suggestion:*** PROPOSE FIX — standardize on "hard-coded".

### [R2-15] [`style`] - Severity: Nit
*   **Affected Scope:** discovery/EGM.md L4 (same-paragraph mix) + suite-wide dash/e.g. normalization
*   **Discrepancy Description:** Em dash and spaced hyphen mixed in one paragraph; suite-wide dash and "e.g." punctuation varies.
*   ***AI Suggestion:*** PROPOSE FIX for the same-paragraph mix ("analysis tooling only — it is not imported"); **DECLINE** the suite-wide normalization (cosmetic churn; each legacy file is internally consistent).

### [R2-16] [`style`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L10 (Interface), real_estate_intelligence/EGM.md System Verification
*   **Discrepancy Description:** "note:" markers are filler in self-flagging parentheticals.
*   ***AI Suggestion:*** PROPOSE FIX — drop "note:" in both spots.

## Round 3

Status: resolved (5/5 PROPOSE FIX accepted via "auto accept"; 0 contested, 0 escalated, 0 declined. Reviewer statuses: codebase_details `completed`, comprehension `completed` (first successful run), structural `completed` — "No findings"; style **not run** (failed twice on the harness concurrency limit), so Round 3 is not a clean round by rule.)

**Target:** the same 8 contracts (`full file` each), post-Round-2-fixes (59 cumulative fixes). Reviewer statuses: codebase_details `completed`, comprehension `completed` (first successful run of this persona), structural `completed` — **"No findings"**, full clean structural pass; style **not run** (failed twice on the harness concurrency limit). Round 3 is therefore not clean by rule, and 1 Major was raised. 5 findings: 1 Major, 4 Nit — all PROPOSE FIX, every factual claim verified by the Elephant (`db/` has zero `models` imports; `graph/network.py` imports only `sqlite3`/`typing`; `analytics/audit.py:7` imports `DiscrepancyLead`; `mcp/server.py:6-13` imports analytics+db+documents+graph; `agent/copilot.py` has no internal imports; `source_run_dir` stored but never read; `blockName` semantics).

### [R3-1] [`codebase_details`] - Severity: Major
*   **Affected Scope:** real_estate_intelligence/EGM.md L21 (Global Invariants, dependency-direction bullet)
*   **Discrepancy Description:** The bullet asserts "`db` depends on `models`/`config`" and "`analytics`/`graph`/`documents` depend on `db`", but two edges are false at import level: no module under `db/` imports `models` at all (the `models` consumer is `analytics/audit.py:7`), and `graph/network.py` imports only `sqlite3`/`typing` — `KnowledgeGraph` receives a live connection by injection, as `AgenticCopilot` receives the MCP server (verified: `mcp/server.py:6-13` imports analytics+db+documents+graph; `ui/server.py:11-20` imports and wires everything including mcp; `agent/copilot.py` has no internal imports).
*   **Rationale:** This is the contract's normative layering statement citing import line numbers as evidence; two false edges corrupt the refactor-safety reasoning the invariant exists to guarantee.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Rewrite the bullet with verified import edges: "Import edges: `models` has no internal imports; `db` imports `config`; `analytics` imports `db` and `models` (`audit.py` consumes `DiscrepancyLead`); `documents` imports `db`; `mcp` imports `analytics`, `db`, `documents`, and `graph`; `ui` imports `analytics`/`config`/`db`/`documents`/`graph`/`mcp`; `cli` composes everything. `graph` and `agent` take their collaborators by injection, not import (`KnowledgeGraph` receives a live connection; `AgenticCopilot` receives the MCP server)." (Seam sentence unchanged.)

### [R3-2] [`comprehension`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L11 (Interface)
*   **Discrepancy Description:** `PricingIntelligence(con_or_db=None, source_run_dir=None)` declares `source_run_dir` with no stated purpose (sibling `con_or_db` gets full semantic treatment).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Gloss: "(`source_run_dir` defaults to `config.DEFAULT_SOURCE_RUN` and is stored but currently not read elsewhere in the module)".

### [R3-3] [`comprehension`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L4 (Overview)
*   **Discrepancy Description:** "RERA" — the central statutory term — is never expanded in the entry-point blueprint, and unlike the subsystem contracts it introduces, this file never links GLOSSARY.md.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "an evidence-backed due-diligence platform for Gujarat RERA (GujRERA — the Gujarat Real Estate Regulatory Authority; see [GLOSSARY.md](../GLOSSARY.md))".

### [R3-4] [`comprehension`] - Severity: Nit
*   **Affected Scope:** legacy/eda_prototypes/webapp/EGM.md L4 (Overview)
*   **Discrepancy Description:** "CA" is never expanded to "chartered accountant" in the Form 3 gloss, and this is the only Form-glossing contract without a GLOSSARY.md link ("CA certificate" invites the certificate-authority misreading).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(Form 3 = the statutory quarterly certificate of the chartered accountant (CA) — see [GLOSSARY.md](../../../GLOSSARY.md) — whose unit rows carry booking/transaction data)".

### [R3-5] [`comprehension`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L14/L18 (Interface)
*   **Discrepancy Description:** "block" (per-block booking/photo calls; block inventory) is undefined anywhere in the corpus — GLOSSARY.md does not define it either.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Gloss at first use: "(a block is one named building/tower grouping of units within a project; the portal keys unit inventories by `blockName`)".

## Round 4

Status: resolved (17/17 findings — 14 numbered entries, all PROPOSE FIX — accepted via "auto accept", applied as 15 edits across 7 files; 0 contested, 0 escalated, 0 declined. All four reviewers `completed` — first full battery since Round 1. Round 4 not clean: 2 Majors were raised (both on Round 3's own additions — the incomplete dependency-bullet enumeration and the nested Form 3 gloss), both now fixed.)

**Target:** the same 8 contracts (`full file` each), post-Round-3-fixes (64 cumulative fixes). Reviewer statuses: **all four `completed`** (codebase_details and comprehension on retry) — first round with full battery since Round 1. 19 raw findings deduplicated to **17 (2 Major, 15 Nit): 14 numbered entries below, all PROPOSE FIX**. Elephant verified every disputed fact with a full import sweep, the eval-harness write, and the `enggScore` provenance (quarterly progress reports — not Form 2 as the reviewer guessed; the gloss states the verified source). Round 4 disproved the "nothing left" expectation: both Majors sit on text introduced by the Round 3 fixes — the rewritten dependency bullet omitted four real import edges, and the new Form 3 gloss nested three parenthesis levels. Round 4 is not clean (Majors raised); the pre-committed exit does not trigger.

### [R4-1] [`codebase_details`+`style`] - Severity: Major
*   **Affected Scope:** real_estate_intelligence/EGM.md L21 (Global Invariants, dependency bullet)
*   **Discrepancy Description:** The Round 3 rewritten bullet's import-edge enumeration is incomplete on four real edges: `analytics` also imports `config` (pricing.py:10, spatial.py:11) and `graph` (investor_dossier.py:6 composes `KnowledgeGraph`); `documents` also imports `config` (worker.py:11); `ui` also imports `agent` (lazily, server.py:1520 in `setup_backends`). Also "Cross-package dependency direction" mislabels intra-subsystem edges (the actual cross-package relation, `gujrera_pipeline`, is documented separately) — style's point, folded here. All four edges verified by the Elephant's full import sweep.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Rewrite the bullet: "Subsystem dependency direction is strict, with one deliberate seam. Import edges: `models` has no intra-package imports (neither does `config`); `db` imports `config`; `documents` imports `config` and `db`; `analytics` imports `config`, `db`, `models` (`audit.py` consumes `DiscrepancyLead`), and `graph` (`investor_dossier.py` composes `KnowledgeGraph`); `mcp` imports `analytics`, `db`, `documents`, and `graph`; `ui` imports `agent` (lazily, in `setup_backends`), `analytics`, `config`, `db`, `documents`, `graph`, and `mcp`; `cli` imports from every subsystem. `graph` and `agent` receive their collaborators by injection (`KnowledgeGraph` is handed a live connection; `AgenticCopilot` is handed the MCP server)." (Seam sentence unchanged.)

### [R4-2] [`codebase_details`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L19 (Global Invariants, read/write boundary)
*   **Discrepancy Description:** The "only ... mutate" enumeration omits the `eval` subcommand: `tests/eval_harness.py:128-152` (`evaluate_retrieval`) seeds benchmark rows via `db.fts.index_page_text` and commits when the FTS index is empty. Verified by the Elephant.
*   **Rationale:** A reader treating the boundary as authoritative would conclude `eval` never writes.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Append to the enumeration: "— plus the `eval` subcommand's harness, which seeds benchmark FTS rows via `db.fts.index_page_text` when the index is empty [tests/eval_harness.py:128-152]".

### [R4-3] [`style`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L4 (Overview)
*   **Discrepancy Description:** Three forms of one referent in a row ("Gujarat RERA (GujRERA — the Gujarat Real Estate Regulatory Authority...)"); "Gujarat" duplicated.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "for GujRERA (the Gujarat Real Estate Regulatory Authority; see [GLOSSARY.md](../GLOSSARY.md))".

### [R4-4] [`style`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L12 vs L31
*   **Discrepancy Description:** The `tests/` contents + verification-only status is stated twice (Subdirectories bullet and System Verification); only the `eval` import at L31 is new information.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Trim L31 to: "The `eval` CLI subcommand imports `tests.eval_harness.EvaluationHarness` directly [cli.py:cmd_eval]."

### [R4-5] [`style`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L14 (Invariants)
*   **Discrepancy Description:** The parenthetical "(one loop per call: Gemini if ... otherwise OpenAI)" restates the selection rule the next two bullets specify in full — the rule now appears three times across adjacent bullets.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Drop the parenthetical: "when no key is resolvable or the single selected LLM loop fails; on success ...".

### [R4-6] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L11 (Interface)
*   **Discrepancy Description:** "stored but currently not read elsewhere in the module" — "elsewhere" has no anchor and implies some in-module read exists; only the constructor assignment occurs.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "stored but currently never read within the module".

### [R4-7] [`style`+`comprehension`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L16 (Invariants) — two issues in one bullet
*   **Discrepancy Description:** (a) First use of "CA" unexpanded in the Form 5 gloss ("chartered accountant" never appears in the file; GLOSSARY's own convention avoids the "CA" initialism). (b) "engineer progress" — the metric behind every threshold and the `velocity_ratio` numerator — has unstated provenance. Elephant verified: it is the `enggScore` field of the portal's quarterly progress reports (`db/loader.py:159-166`), not Form 2 as the reviewer guessed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Form 5 (the statutory annual chartered-accountant audit report; see [GLOSSARY.md](../../../GLOSSARY.md))" and extend the velocity gloss: "...computed in `db/loader.py:166`; engineer progress is the `enggScore` field of the portal's quarterly progress reports)".

### [R4-8] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L23 (Invariants)
*   **Discrepancy Description:** "unknown district falls back to `\"Ahmedabad\"`, latitude `23.0`, longitude `72.5`" — the verb reaches across the comma list (garden path: the district falls back to latitude 23.0).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "unknown district falls back to `\"Ahmedabad\"`; default latitude `23.0`, longitude `72.5`; one-hot features ...".

### [R4-9] [`style`] - Severity: Nit
*   **Affected Scope:** scripts/EGM.md L13 (Invariants)
*   **Discrepancy Description:** "hard-coded default paths" — the paths are config defaults the scripts cannot override, not literals hard-coded in the scripts; also duplicates the "no CLI arguments" clause.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "the default paths defined in [../real_estate_intelligence/config.py:DEFAULT_DB_PATH] and [...DEFAULT_SOURCE_RUN] — they accept no CLI arguments".

### [R4-10] [`style`+`structural`] - Severity: Nit
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L23 (Side Effects)
*   **Discrepancy Description:** The only bullet in the file ending with terminal punctuation (trailing period after the citation); all other bullets omit it. (Found independently by style and structural.)
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Remove the trailing period.

### [R4-11] [`comprehension`+`style`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L14 (Interface, stage 2) — two issues in one sentence
*   **Discrepancy Description:** (a) "CA" unexpanded in the stage-2 gloss ("architect/engineer/CA certificates"); (b) "fetches ... calls" is a zeugma — calls are made, data is fetched. The block gloss itself reads fine.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(the quarterly certificates of the architect, engineer, and chartered accountant; see [GLOSSARY.md](../../GLOSSARY.md))" and "fetches the \"latest\" form set plus per-block booking/photo data".

### [R4-12] [`comprehension`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L4 (Overview)
*   **Discrepancy Description:** "allottee" is RERA statutory jargon (registered buyer of a unit) with no gloss — not defined even in GLOSSARY.md — and the sentence carries the privacy contract.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Raw captures may contain allottee (the registered buyer of a unit), bank, and promoter personal data ...".

### [R4-13] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L35 (Side Effects)
*   **Discrepancy Description:** "fixed sleeps of 0.2 s ..., 0.15 s ..., and 0.7 s per request in the four-project scripts" — the trailing modifier can sweep all three values; only the 0.7 s belongs to the four-project scripts.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "fixed sleeps of 0.2 s and 0.15 s in the nine-project stages [...] and 0.7 s per request in the four-project scripts [...]".

### [R4-14] [`style`] - Severity: Major
*   **Affected Scope:** legacy/eda_prototypes/webapp/EGM.md L4 (Overview)
*   **Discrepancy Description:** The Round 3 Form 3 gloss stacks three nesting levels: parens inside parens, an em-dash pair inside the parens, and "whose unit rows" attaches to "certificate" while describing the dataset; the "(CA)" initialism is never reused.
*   **Rationale:** A fresh reader must re-parse the sentence to find where the definition ends.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "loads a pre-computed unit-level Form 3 Parquet dataset (Form 3 = the statutory quarterly certificate of the chartered accountant; see [GLOSSARY.md](../../../GLOSSARY.md)) whose unit rows carry booking/transaction data, and renders it in a filterable browser table using `streamlit_extras.dataframe_explorer`."

No CONTEST or ESCALATE items in Round 4; every finding verified before categorization. Loop state: all 4 reviewers ran, 2 Majors raised → not clean → Round 5 (the cap round) proceeds after resolution if the user confirms.

## Round 5 (cap round)

Status: resolved — **LOOP CLOSED (accepted at cap)**. 13/13 PROPOSE FIX accepted via "auto accept", applied as 13 edits across 5 files; 0 contested, 0 escalated, 0 declined. All four reviewers `completed` this round. Final tally: **96 deduplicated findings across Rounds 0-5 (9 + 35 + 16 + 5 + 17 + 14); 94 resolved via applied fixes, 2 recorded as partial declines** (R2-15 suite-wide dash normalization; R5-5 corpus-wide punctuation standardization). Final structural verification: 0 problems across all 9 files.

**Target:** the same 8 contracts (`full file` each), post-Round-4-fixes (78 cumulative fixes). Reviewer statuses: **all four `completed`** (comprehension on retry). 15 raw findings deduplicated to **14 (1 Blocker, 2 Major, 11 Nit): 13 numbered entries below, all PROPOSE FIX**. Elephant verified every disputed fact (cli.py import list from the Round 4 sweep; `network.py:8-14` executescript DDL; `audit.py:324-331` fallback condition; `copilot.py:224-230` dead-code reachability). Round 5 is NOT clean (Blocker raised) and the loop is at cap.

### [R5-1] [`codebase_details`] - Severity: Blocker
*   **Affected Scope:** real_estate_intelligence/EGM.md L21 (Global Invariants, dependency bullet — Round 4 rewrite)
*   **Discrepancy Description:** "`cli` imports from every subsystem" is false: `cli.py` imports only `analytics`, `db`, `documents`, `graph`, and `ui` (plus `config` and `tests.eval_harness`); it never imports `agent` or `mcp`, and `models` only transitively (via `analytics.audit`). `mcp` reaches the process only through `ui/server.py:20`'s module-level import, `agent` only inside `ui`'s `setup_backends` (`ui/server.py:1520`). Confirmed against the Round 4 full import sweep.
*   **Rationale:** The bullet is the architecture contract rewritten specifically as a complete enumeration; a false edge corrupts refactor-safety reasoning. The same bullet holds `ui` to a direct-vs-lazy standard, so the blanket clause fails its own accuracy bar.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "`cli` imports `analytics`, `db`, `documents`, `graph`, and `ui` (reaching `models` and `mcp` only transitively via `ui.server`, and `agent` never — it loads only inside `ui`'s `setup_backends`)."

### [R5-2] [`style`] - Severity: Major
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L14 (Invariants — Round 2 fix introduced the error)
*   **Discrepancy Description:** "the run directory `../runs/nine_projects_2026_10_15` (resolved from this folder's parent, `data/`)" — anchoring `../runs/...` at `data/` yields `gujrera_pipeline/runs/...`, contradicting the code (`Path(__file__).parent.parent / "runs"` = `data/runs/...`) and the Verification line's `gujrera_pipeline/data/runs/`.
*   **Rationale:** The invariant tells an operator where artifacts must live; the anchor as written points one level too high.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "the run directory `data/runs/nine_projects_2026_10_15` (resolved via `Path(__file__).parent.parent / \"runs\"`, i.e. `../runs/...` from this directory) exists and contains ...".

### [R5-3] [`style`] - Severity: Major
*   **Affected Scope:** real_estate_intelligence/EGM.md L19 (Global Invariants, read/write boundary — Round 4 amendment)
*   **Discrepancy Description:** "idempotent schema/DDL via `get_connection` and `KnowledgeGraph.__init__`" conflates mechanism with call site: `KnowledgeGraph.__init__` applies its DDL directly via `executescript` on the injected connection (`graph/network.py:8-14`), not via `get_connection`. Verified by the Elephant.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(their constructors may apply idempotent schema/DDL — via `get_connection`, or directly on the injected connection in `KnowledgeGraph.__init__`)".

### [R5-4] [`style`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L25 (Global Side Effects)
*   **Discrepancy Description:** "Outbound network calls occur only in two places: ... and the browser-side CDN assets" — CDN loads are initiated by the browser, not the process; the scope doesn't match both items.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Outbound network calls occur only in `agent/copilot.py` (Gemini/OpenAI HTTP APIs, key-gated); the `ui` dashboard HTML additionally embeds browser-side CDN assets, and the server itself binds to `127.0.0.1` only".

### [R5-5] [`style`+`structural`] - Severity: Nit
*   **Affected Scope:** real_estate_intelligence/EGM.md L31 (System Verification)
*   **Discrepancy Description:** The `eval` bullet (introduced by the Round 4 trim) is the only bullet in the file with a terminal period. (Found independently by style and structural.)
*   ***AI Suggestion:*** PROPOSE FIX — remove the period. Corpus-wide punctuation standardization: DECLINE (each file internally consistent after this fix).

### [R5-6] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L18 (Invariants)
*   **Discrepancy Description:** "falls back to `incurred_cost / 12`" — triggering condition unstated. Code (`audit.py:324-331`): fires only when fewer than two `finances` rows exist (and `incurred_cost > 0`); a zero/negative diff yields burn `0.0`, not the fallback. Verified by the Elephant.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "falls back to `incurred_cost / 12` when fewer than two filings carry `incurred_and_paid`, and labels insolvency risk ...".

### [R5-7] [`style`] - Severity: Nit
*   **Affected Scope:** analytics/EGM.md L24 (Invariants)
*   **Discrepancy Description:** "treats X as a database, and any other argument ... as a trigger to fall back to Y" — indirect; "trigger" adds nothing.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "treats a `.sqlite` suffix or existing file path as a database and falls back to [../config.py:DEFAULT_DB_PATH] for any other argument (e.g., a directory)".

### [R5-8] [`style`] - Severity: Nit
*   **Affected Scope:** agent/EGM.md L16 (Invariants)
*   **Discrepancy Description:** "the `sk-`-prefix test ... is unreachable when an explicit key is supplied" understates its own evidence: the branch runs only when `api_key` is falsy, so the test's operand is always false at execution — dead code in all paths (`copilot.py:224-230`). Verified by the Elephant.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "(the `sk-`-prefix test in the OpenAI fallback is dead code — `api_key` is always falsy by the time that branch runs)".

### [R5-9] [`style`+`comprehension`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L4 (Overview) — two issues in one sentence
*   **Discrepancy Description:** (a) "bank personal data" is a category error — banks are not data subjects; the sense is bank-account details. (b) "promoter" is ungrounded while its sibling "allottee" is glossed in the same sentence; GLOSSARY defines Promoter (registered developer) but this file never links or glosses it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Raw captures may contain allottee (the registered buyer of a unit), bank-account, and promoter (the registered developer) personal data and are git-ignored via [.gitignore]."

### [R5-10] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/research_samples/EGM.md L35 (Side Effects — Round 4 reword)
*   **Discrepancy Description:** "in both nine-project stages ..., with fixed sleeps ... in the nine-project stages" — "nine-project stages" stated twice in one sentence (introduced by the Round 4 fix).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "...with fixed sleeps of 0.2 s and 0.15 s in the same stages [...] and 0.7 s per request in the four-project scripts [...]".

### [R5-11] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/scrapy_crawler/RERA/EGM.md L4 (Overview)
*   **Discrepancy Description:** "the actual code lives..." — "actual" is filler; the contrast is already made by "all pruned from contracts".
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "the code lives in the child `RERA/` package".

### [R5-12] [`style`] - Severity: Nit
*   **Affected Scope:** legacy/scrapy_crawler/RERA/EGM.md L18 (Side Effects)
*   **Discrepancy Description:** The sentence attributes all listed directories to the spiders, but `dbs/` and `eggs/` are written by the Scrapyd server, not the spiders (the parenthetical only hints).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Crawling from this directory makes the spiders write into `collected_data/` (FEEDS and failure CSVs), `jobs/` (JOBDIR resume state), and `logs/`; running via Scrapyd additionally populates `dbs/` and `eggs/` - see the child contract for the exact writers [RERA](./RERA/EGM.md)."

### [R5-13] [`comprehension`] - Severity: Nit
*   **Affected Scope:** gujrera_pipeline/data/discovery/EGM.md L9 (Interface)
*   **Discrepancy Description:** "FRN (ICAI Firm Registration Number)" leaves ICAI unexpanded while every other acronym in the sentence is spelled out; ICAI is defined nowhere in the corpus.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "FRN (Firm Registration Number issued by the Institute of Chartered Accountants of India)/UDIN (Unique Document Identification Number) terms".

No CONTEST or ESCALATE items in Round 5; every finding verified before categorization. **The loop is at cap (5 rounds).**
