import sys
from real_estate_intelligence.config import DEFAULT_DB_PATH
from real_estate_intelligence.db.database import get_connection
from real_estate_intelligence.graph.network import KnowledgeGraph

sys.stdout.reconfigure(encoding="utf-8")

def main():
    print(f"Connecting to: {DEFAULT_DB_PATH}")
    con = get_connection(DEFAULT_DB_PATH)
    kg = KnowledgeGraph(con)
    res = kg.build_graph()
    print("[SUCCESS] Knowledge graph built successfully!")
    print(f"  Nodes: {res['nodes']}")
    print(f"  Edges: {res['edges']}")

    # Check shared professionals
    cur = con.cursor()
    cur.execute("""
        SELECT e.dst_id, n.label, COUNT(DISTINCT e.src_id) as p_count
        FROM graph_edges e
        JOIN graph_nodes n ON n.node_id = e.dst_id
        WHERE e.relation IN ('ENGINEERED_BY', 'DESIGNED_BY', 'AUDITED_BY')
        GROUP BY e.dst_id, n.label
        HAVING p_count > 1
    """)
    shared = cur.fetchall()
    print(f"\nShared cross-project professionals: {len(shared)}")
    for s in shared:
        print(f"  * {s[1]} ({s[0]}): Connected to {s[2]} projects!")

if __name__ == "__main__":
    main()
