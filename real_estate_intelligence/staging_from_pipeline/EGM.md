# experiments

## Overview
Small, local analysis experiments run over archived run evidence (package docstring: "Small, local experiments over archived evidence"). Each module is a standalone script with a `main()` entry point that derives graph databases and Markdown/JSON reports from previously captured run archives. None of these modules are imported by the production pipeline; they consume package modules (`legacy_collector.cli.DEFAULT_DATA`, `legacy_collector.cli.DEFAULT_INDEX`, `legacy_collector.party_enrichment` run constants and `norm`, `core.storage.RunStore`) as library dependencies.

## Interface
- `coverage_audit.py:main()` - audits how much of the frozen party network can support app claims; reads `party_links_redacted.json` and the saved project index (Parquet or CSV), then writes a JSON coverage matrix and a readable gap report; helpers `role_coverage(records)`, `gap_codes(roles)`, `status(value)` [coverage_audit.py:main, coverage_audit.py:role_coverage, coverage_audit.py:gap_codes, coverage_audit.py:status]
- `graph_pilot.py:build(store)` - builds a narrow source-linked relationship graph (`project`/`promoter`/`filing`/`block`/`document_content` nodes with `registered_by`, `has_filing`, `reports_block`, `references_document_content` edges) into `derived/graph_pilot.sqlite` and returns a counts summary [graph_pilot.py:build]
- `graph_pilot.py:main()` - CLI entry point with required `--run-id` and optional `--data-root`; exits with `SystemExit` when the run's `manifest.sqlite` is missing [graph_pilot.py:main]
- `party_graph.py:build(data_root, party_run_id, pilot_run_id, related_run_id)` - builds the private party network graph (`party_network.sqlite`) with verified profile, unresolved-credential, unresolved-assignment, previous-project-claim and reported-institution-label nodes, and writes `NETWORK.md` plus `PROFILES.md` reports [party_graph.py:build]
- `party_graph.py:main()` - CLI entry point with `--data-root`, `--party-run` (default `PARTY_RUN`), `--pilot-run` (default `PILOT_RUN`), `--related-run` (default `RELATED_RUN`) [party_graph.py:main]
- Shared constants: `SEED_IDS`, `ROLES`, `VERIFIED` match-status set, and output paths derived from `PARTY_RUN` [coverage_audit.py:SEED_IDS, coverage_audit.py:ROLES, coverage_audit.py:VERIFIED, coverage_audit.py:LINKS]

## Invariants
- Every party-graph edge must carry verifiable provenance: `party_graph.py:edge` raises `ValueError` if the evidence `raw_sha256` does not match the archived request's `sha256`, and raises `ValueError` if a claimed `document_sha256` has no `status='ok'` row in `documents` [party_graph.py:edge]
- Unresolved identities are never merged into person nodes: credentials without a profile ID become `unresolved_credential` nodes hashed from the normalized credential, and role rows without credentials become `unresolved_assignment` nodes keyed by project/role/assignment ID [party_graph.py:build, party_graph.py:credential digest, party_graph.py:unresolved_assignment]
- `graph_pilot.py` only includes requests whose `status` is `"ok"`; non-ok requests are skipped, never fabricated [graph_pilot.py:status guard]
- Both graph builders treat the derived SQLite databases as disposable: each build runs `DROP TABLE IF EXISTS` on `nodes`/`edges` before recreating them [graph_pilot.py:executescript, party_graph.py:executescript]
- `coverage_audit.py` reads only the allowlisted party export and the saved project index, with no network access (module docstring) [coverage_audit.py:module docstring]
- Report prose encodes evidence-handling rules: self-reported experience/counts are not a verified work history, portal status labels are not current construction-status determinations, and Form 1/2 signers are kept distinct from registered project-team roles [coverage_audit.py:role_coverage docstring, party_graph.py:report lines]

## Side Effects
- Writes SQLite databases `derived/graph_pilot.sqlite` (per run) and `derived/party_network.sqlite` (per party run), destructively replacing prior `nodes`/`edges` tables [graph_pilot.py:build, party_graph.py:build]
- Writes report/export files into the party run directory: `exports/coverage.json`, `reports/COVERAGE.md` [coverage_audit.py:main], and `reports/NETWORK.md`, `reports/PROFILES.md` [party_graph.py:build]
- Creates parent directories (`mkdir(parents=True, exist_ok=True)`) for those outputs before writing [coverage_audit.py:OUT.parent.mkdir, coverage_audit.py:REPORT.parent.mkdir, graph_pilot.py:output.parent.mkdir, party_graph.py:output.parent.mkdir]
- Prints JSON summaries and audit counts to stdout from each `main()` [graph_pilot.py:main, party_graph.py:main, coverage_audit.py:main]
- No network calls are made by any module in this directory.

## Verification
- Run: `python -m unittest discover -s tests -v` (the test suite does not cover these experiment scripts; they are executed manually with `python -m gujrera_pipeline.experiments.<module>` against archived runs)
