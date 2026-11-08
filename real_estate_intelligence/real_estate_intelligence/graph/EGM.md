# graph — Cross-Entity Knowledge Graph & Contagion Tracing

## Overview
Relational knowledge-graph engine over the curated SQLite database. `KnowledgeGraph` materializes `graph_nodes` / `graph_edges` tables from the `projects`, `promoters`, `professionals`, `banks`, and `previous_projects` tables, then answers cross-project overlap queries ("which projects share an architect/engineer/CA/bank?") and traces contagion risk to complaint-bearing sister schemes.

## Interface
- `KnowledgeGraph(con)` — constructor creates (or reuses) the `graph_nodes` and `graph_edges` tables with indexes `idx_edge_dst` and `idx_edge_src` [network.py:KnowledgeGraph]
- `build_graph() -> Dict[str, int]` — rebuilds nodes/edges from curated tables and returns total counts `{"nodes": int, "edges": int}` [network.py:build_graph]
- `find_shared_entities(project_id) -> List[Dict[str, Any]]` — other projects sharing an architect, engineer, CA, or bank; rows carry `connection_type`, `shared_entity_name`, `entity_kind`, `linked_project_id`, `linked_project_name` [network.py:find_shared_entities]
- `trace_contagion_risk(project_id) -> List[Dict[str, Any]]` — multi-hop lead generation over shared entities [network.py:trace_contagion_risk]

## Invariants
- Node IDs follow fixed formats: `project:{id}`, `promoter:{id}`, `professional:{role}:{normalized_name}`, `bank:{normalized_bank_name}`, `prior_project:{id or alphanumeric name}` [network.py:build_graph]
- Edge relations are fixed: `DEVELOPED_BY`, `DESIGNED_BY`, `ENGINEERED_BY`, `AUDITED_BY`, `CONSTRUCTED_BY`, `ESCROW_AT`, `PRIOR_PORTFOLIO`, with `ASSOCIATED_WITH` as the fallback for unknown professional roles [network.py:build_graph]
- `graph_edges` primary key is `(src_id, relation, dst_id)`; both insert helpers use `INSERT OR REPLACE`, so `build_graph()` is idempotent over the same data [network.py:_insert_edge]
- `trace_contagion_risk` only flags linked projects that have rows in `applications` with `application_type = 'Complaint'`; every lead is emitted with `risk_type = 'PROFESSIONAL_LINKED_COMPLAINT'` and `severity = 'MEDIUM'` [network.py:trace_contagion_risk]
- Node `kind` values are `Project`, `Promoter`, `Bank`, `PriorProject`, and the capitalized professional role (`Architect`, `Engineer`, `Ca`, `Contractor`) — note the `Ca` casing, which the UI color map also keys on [network.py:build_graph]

## Side Effects
- Creates `graph_nodes` / `graph_edges` tables in the passed SQLite connection and commits on construction and after `build_graph()` [network.py:_init_graph_tables]
- `build_graph()` rewrites graph rows (`INSERT OR REPLACE`) in the shared database; it does not create a separate database file (the [../config.py:DEFAULT_GRAPH_DB_PATH] constant is not referenced by this module) [network.py:build_graph]
- Contagion tracing reads `applications` but never mutates curated tables [network.py:trace_contagion_risk]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
