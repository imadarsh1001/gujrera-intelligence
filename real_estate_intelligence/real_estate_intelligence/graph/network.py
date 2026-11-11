"""Knowledge Graph engine for cross-entity network analysis and contagion risk tracing."""

import sqlite3
from typing import Any, Dict, List, Optional


class KnowledgeGraph:
    def __init__(self, con: sqlite3.Connection):
        self.con = con
        self._init_graph_tables()

    def _init_graph_tables(self):
        """Create graph node and edge tables for fast relational traversals."""
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                node_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                properties_json TEXT
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                src_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                dst_id TEXT NOT NULL,
                properties_json TEXT,
                PRIMARY KEY (src_id, relation, dst_id)
            );
            CREATE INDEX IF NOT EXISTS idx_edge_dst ON graph_edges(dst_id, relation);
            CREATE INDEX IF NOT EXISTS idx_edge_src ON graph_edges(src_id, relation);
        """)
        self.con.commit()

    def build_graph(self) -> Dict[str, int]:
        """Populate graph nodes and edges from curated relational tables."""
        cur = self.con.cursor()

        # 1. Projects
        cur.execute("SELECT project_id, name, registration_number, district FROM projects")
        for row in cur.fetchall():
            pid = row["project_id"]
            p_node = f"project:{pid}"
            self._insert_node(p_node, "Project", row["name"])

        # 2. Promoters
        cur.execute("SELECT promoter_id, name, promoter_type FROM promoters")
        for row in cur.fetchall():
            prom_id = row["promoter_id"]
            prom_node = f"promoter:{prom_id}"
            self._insert_node(prom_node, "Promoter", row["name"])

        # Edge Project -> DevelopedBy -> Promoter
        cur.execute("SELECT project_id, promoter_id FROM projects")
        for row in cur.fetchall():
            self._insert_edge(f"project:{row['project_id']}", "DEVELOPED_BY", f"promoter:{row['promoter_id']}")

        # 3. Professionals
        cur.execute("SELECT project_id, role, name, firm_name FROM professionals")
        for row in cur.fetchall():
            role = row["role"].lower()
            name = row["name"].strip()
            # Clean normalized node ID
            norm_name = "".join(c for c in name.lower() if c.isalnum() or c == " ").strip().replace(" ", "_")
            prof_node = f"professional:{role}:{norm_name}"
            self._insert_node(prof_node, role.capitalize(), name)

            rel_name = {
                "architect": "DESIGNED_BY",
                "engineer": "ENGINEERED_BY",
                "ca": "AUDITED_BY",
                "contractor": "CONSTRUCTED_BY",
            }.get(role, "ASSOCIATED_WITH")

            self._insert_edge(f"project:{row['project_id']}", rel_name, prof_node)

        # 4. Banks
        cur.execute("SELECT project_id, bank_name, branch_name FROM banks")
        for row in cur.fetchall():
            bname = row["bank_name"].strip()
            branch = row["branch_name"] or "Main"
            norm_bank = "".join(c for c in bname.lower() if c.isalnum() or c == " ").strip().replace(" ", "_")
            bank_node = f"bank:{norm_bank}"
            self._insert_node(bank_node, "Bank", bname)
            self._insert_edge(f"project:{row['project_id']}", "ESCROW_AT", bank_node)

        # 5. Previous Projects — self-links excluded so a project is never its own prior node
        cur.execute(
            "SELECT project_id, linked_project_name, linked_project_id FROM previous_projects "
            "WHERE linked_project_id IS NOT NULL AND linked_project_id != project_id"
        )
        for row in cur.fetchall():
            lp_name = row["linked_project_name"] or f"Project_{row['linked_project_id']}"
            lp_id = row["linked_project_id"] or "".join(c for c in lp_name.lower() if c.isalnum())
            prev_node = f"prior_project:{lp_id}"
            self._insert_node(prev_node, "PriorProject", lp_name)
            self._insert_edge(f"project:{row['project_id']}", "PRIOR_PORTFOLIO", prev_node)

        self.con.commit()

        nodes_count = self.con.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
        edges_count = self.con.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        return {"nodes": nodes_count, "edges": edges_count}

    def _insert_node(self, node_id: str, kind: str, label: str):
        self.con.execute(
            "INSERT OR REPLACE INTO graph_nodes (node_id, kind, label) VALUES (?, ?, ?)",
            (node_id, kind, label),
        )

    def _insert_edge(self, src_id: str, relation: str, dst_id: str):
        self.con.execute(
            "INSERT OR REPLACE INTO graph_edges (src_id, relation, dst_id) VALUES (?, ?, ?)",
            (src_id, relation, dst_id),
        )

    def find_shared_entities(self, project_id: int) -> List[Dict[str, Any]]:
        """Find other projects sharing an architect, engineer, CA, or bank with this project."""
        src_proj = f"project:{project_id}"
        query = """
            SELECT 
                e1.relation AS connection_type,
                n.label AS shared_entity_name,
                n.kind AS entity_kind,
                e2.src_id AS linked_project_node,
                p.name AS linked_project_name,
                p.project_id AS linked_project_id
            FROM graph_edges e1
            JOIN graph_nodes n ON n.node_id = e1.dst_id
            JOIN graph_edges e2 ON e2.dst_id = e1.dst_id AND e2.src_id != e1.src_id
            JOIN projects p ON ('project:' || p.project_id) = e2.src_id
            WHERE e1.src_id = ?
        """
        cur = self.con.execute(query, (src_proj,))
        results = []
        for r in cur.fetchall():
            results.append({
                "connection_type": r["connection_type"],
                "shared_entity_name": r["shared_entity_name"],
                "entity_kind": r["entity_kind"],
                "linked_project_id": r["linked_project_id"],
                "linked_project_name": r["linked_project_name"],
            })
        return results

    def trace_contagion_risk(self, project_id: int) -> List[Dict[str, Any]]:
        """Multi-hop query: check if any professional or promoter linked to this project

        is also linked to projects that have registered consumer complaints or cost reversals.
        """
        shared = self.find_shared_entities(project_id)
        contagion_leads = []

        for item in shared:
            linked_pid = item["linked_project_id"]
            # Check complaints
            complaints = self.con.execute(
                "SELECT COUNT(*) FROM applications WHERE project_id = ? AND application_type = 'Complaint'",
                (linked_pid,),
            ).fetchone()[0]

            if complaints > 0:
                contagion_leads.append({
                    "risk_type": "PROFESSIONAL_LINKED_COMPLAINT",
                    "severity": "MEDIUM",
                    "shared_entity": item["shared_entity_name"],
                    "entity_role": item["entity_kind"],
                    "linked_project": item["linked_project_name"],
                    "linked_project_id": linked_pid,
                    "detail": f"{item['entity_kind']} '{item['shared_entity_name']}' is also engaged on {item['linked_project_name']} (ID {linked_pid}), which has {complaints} active consumer complaint application(s).",
                })

        return contagion_leads
