"""Build a narrow, source-linked relationship graph from an existing run.

No graph server or LLM is required. The private SQLite file lets us test
actual relationship questions before committing to a separate graph system.
"""

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from ..legacy_collector.cli import DEFAULT_DATA
from ..core.storage import RunStore


FORM_NAMES = (
    "index_form_one", "index_form_two", "index_form_three",
    "latest_form_one", "latest_form_two", "latest_form_three",
)


def build(store: RunStore) -> dict:
    output = store.root / "derived" / "graph_pilot.sqlite"
    output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output)
    db.executescript("""
        DROP TABLE IF EXISTS edges;
        DROP TABLE IF EXISTS nodes;
        CREATE TABLE nodes (
            node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL
        );
        CREATE TABLE edges (
            src_id TEXT NOT NULL, relation TEXT NOT NULL, dst_id TEXT NOT NULL,
            evidence_request_key TEXT NOT NULL, json_path TEXT NOT NULL,
            PRIMARY KEY(src_id, relation, dst_id, evidence_request_key, json_path)
        );
        CREATE INDEX edges_dst_idx ON edges(dst_id, relation);
    """)

    def node(node_id: str, kind: str, label: str):
        db.execute("INSERT OR IGNORE INTO nodes VALUES (?, ?, ?)", (node_id, kind, label))

    def edge(src: str, relation: str, dst: str, evidence: str, json_path: str):
        db.execute("INSERT OR IGNORE INTO edges VALUES (?, ?, ?, ?, ?)",
                   (src, relation, dst, evidence, json_path))

    for project in store.project_rows():
        pid = project["project_id"]
        project_node = f"project:{pid}"
        promoter_node = f"promoter:{project['promoter_id']}"
        node(project_node, "project", project["name"])
        node(promoter_node, "promoter", project["promoter_name"] or "Promoter")
        edge(project_node, "registered_by", promoter_node,
             f"project:{pid}:all_data", "data.promoterId")
        for name in FORM_NAMES:
            request = store.get_request(f"project:{pid}:{name}")
            if not request or request["status"] != "ok":
                continue
            match = re.search(r"/(\d+)(?:\?.*)?$", request["url"])
            if not match:
                continue
            form_id = match.group(1)
            form_node = f"filing:{name}:{form_id}"
            node(form_node, "filing", f"{name} {form_id}")
            edge(project_node, "has_filing", form_node, request["request_key"], "data")
            if name != "latest_form_three":
                continue
            ok, root = store.read_json(request["request_key"])
            data = root.get("data") if ok and isinstance(root, dict) else None
            if not isinstance(data, dict):
                continue
            seen_blocks = set()
            for index, unit in enumerate(data.get("formThreeAList") or []):
                if not isinstance(unit, dict) or not unit.get("blockName"):
                    continue
                block = str(unit["blockName"])
                if block in seen_blocks:
                    continue
                seen_blocks.add(block)
                block_hash = hashlib.sha256(block.encode()).hexdigest()[:12]
                block_node = f"block:{pid}:{block_hash}"
                node(block_node, "block", block)
                edge(form_node, "reports_block", block_node,
                     request["request_key"], f"data.formThreeAList[{index}].blockName")

    rows = store._connection().execute("""
        SELECT r.project_id, r.request_key, r.json_path, d.sha256, d.asset_type
        FROM document_refs r JOIN documents d ON d.uid_hash=r.uid_hash
    """)
    for row in rows:
        doc_node = f"document_content:{row['sha256']}"
        node(doc_node, "document_content", f"{row['asset_type']} {row['sha256'][:12]}")
        edge(f"project:{row['project_id']}", "references_document_content",
             doc_node, row["request_key"], row["json_path"])
    db.commit()
    counts = dict(db.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind"))
    relationships = dict(db.execute("SELECT relation, COUNT(*) FROM edges GROUP BY relation"))
    shared_promoters = db.execute("""
        SELECT COUNT(*) FROM (
            SELECT dst_id FROM edges WHERE relation='registered_by'
            GROUP BY dst_id HAVING COUNT(DISTINCT src_id)>1
        )
    """).fetchone()[0]
    shared_documents = db.execute("""
        SELECT COUNT(*) FROM (
            SELECT dst_id FROM edges WHERE relation='references_document_content'
            GROUP BY dst_id HAVING COUNT(DISTINCT src_id)>1
        )
    """).fetchone()[0]
    db.close()
    return {"graph_path": str(output), "nodes": counts, "edges": relationships,
            "promoters_linked_to_multiple_sample_projects": shared_promoters,
            "document_bodies_shared_across_sample_projects": shared_documents}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    expected = args.data_root / "runs" / args.run_id / "manifest.sqlite"
    if not expected.exists():
        raise SystemExit(f"Run not found: {expected}")
    store = RunStore(args.data_root, args.run_id)
    print(json.dumps(build(store), indent=2))
    store.close()


if __name__ == "__main__":
    main()
