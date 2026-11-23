# graph — Cross-Entity Knowledge Graph & Contagion Tracing

## Overview
Relational knowledge-graph engine and promoter portfolio resolution over `data/intelligence.sqlite`. Materializes `graph_nodes` / `graph_edges` tables, resolves promoter portfolios into disjoint clusters via Composite Key (c) (shared verified professional license or bank branch IFSC anchor), answers cross-project overlap queries ("which projects share an architect/engineer/CA/bank?"), and traces contagion risk to complaint-bearing sister schemes.

## Interface
- `KnowledgeGraph(con)` — Constructor initializes `graph_nodes` and `graph_edges` tables with indexes `idx_edge_dst` and `idx_edge_src` [network.py:KnowledgeGraph]
- `resolve_promoter_portfolio(con, project_id=None, promoter_name=None) -> Dict[str, Any]` — Partitions developer portfolios into disjoint `clusters[]` via Composite Key (c) [network.py:resolve_promoter_portfolio]
- `build_graph() -> Dict[str, int]` — Rebuilds nodes/edges from curated tables with Composite Key promoter anchors [network.py:build_graph]
- `find_shared_entities(project_id) -> List[Dict[str, Any]]` — Returns projects sharing an architect, engineer, CA, or bank [network.py:find_shared_entities]
- `trace_contagion_risk(project_id) -> List[Dict[str, Any]]` — Multi-hop lead generation linking projects to complaint-bearing sister schemes [network.py:trace_contagion_risk]
- `get_ego_network(project_id, depth=2, max_nodes=250) -> Dict[str, Any]` — Subgraph scoped to a project ego-network [network.py:get_ego_network]

## Invariants
- Composite Key (c) Partitioning: developer portfolios are partitioned into disjoint clusters using shared Council of Architecture / engineer licenses and bank branch IFSC anchors; projects are never linked on bare `bank_name` [network.py:resolve_promoter_portfolio]
- Anchor Sanitization & PII Safety: raw licenses are sanitized via `redact_value("license_or_reg_no", val)`; any token containing `[REDACTED`, `"NA"`, `"-"`, `"0"`, or shorter than 3 characters is excluded from edge construction and output [network.py:resolve_promoter_portfolio]
- Partitioned Multi-Cluster Labeling: when queried by `promoter_name` without `project_id` and multiple clusters are found (`len(clusters) > 1`), top-level `linkage_confidence` is strictly set to `"PARTITIONED_MULTI_CLUSTER"` (never `"HIGH"`) [network.py:resolve_promoter_portfolio]
- Token Budget Ceiling: `resolve_promoter_portfolio` caps output at 4,000 tokens (16,000 characters) via compact cluster projections to prevent context explosion [network.py:resolve_promoter_portfolio]
- No `promoter:None` Explosion: projects without an official `promoter_id` derive localized composite nodes or remain singletons [network.py:build_graph]

## Side Effects
- Creates `graph_nodes` / `graph_edges` tables if absent upon `KnowledgeGraph` instantiation [network.py:_init_graph_tables]
- Zero writes to primary real estate tables (`projects`, `unit_transactions`, `project_summaries`, etc.) [network.py]

## Verification
- Run test suites:
  - `python -m pytest real_estate_intelligence/tests/test_phase1_5_polish.py`
  - `python -m pytest real_estate_intelligence/tests/test_security_redaction_and_graph.py`
  - `python -m pytest real_estate_intelligence/tests/test_graph_network.py`
