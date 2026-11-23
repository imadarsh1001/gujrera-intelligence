"""Knowledge Graph engine for cross-entity network analysis, promoter portfolio resolution, and contagion risk tracing."""

from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from ..db.redaction import redact_payload, redact_record, redact_value

MAX_GRAPH_TOKENS = 4000
MAX_CHAR_BUDGET = MAX_GRAPH_TOKENS * 4

COMMON_GUJARAT_PREFIXES = (
    "SHREEJI",
    "SHIV",
    "SHREE",
    "MARUTI",
    "KRISHNA",
    "GANESH",
    "RADHE",
    "OM",
    "SWASTIK",
    "BALAJI",
    "JAY",
    "SHYAM",
)

GOVT_AUTHORITY_KEYWORDS = (
    "AUDA",
    "VUDA",
    "SUDA",
    "RUDA",
    "GUDA",
    "GIDC",
    "PMAY",
    "GHB",
    "MUNICIPAL",
    "CORPORATION",
    "NIGAM",
    "BOARD",
    "AUTHORITY",
    "HOUSING BOARD",
    "URBAN DEVELOPMENT",
)


class TruncatedList(list):
    """Standard list subclass carrying an explicit truncation flag."""

    def __init__(self, *args, truncated: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.truncated = truncated


def _estimate_tokens(obj: Any) -> int:
    try:
        return len(json.dumps(obj)) // 4
    except Exception:
        return 0


def _enforce_token_cap_list(items: List[Any], max_tokens: int = MAX_GRAPH_TOKENS) -> TruncatedList:
    max_chars = max_tokens * 4
    serialized = json.dumps(items)
    if len(serialized) <= max_chars:
        return TruncatedList(items, truncated=False)

    low = 0
    high = len(items)
    best_idx = 0
    while low <= high:
        mid = (low + high) // 2
        cand_str = json.dumps(items[:mid])
        if len(cand_str) <= max_chars:
            best_idx = mid
            low = mid + 1
        else:
            high = mid - 1

    return TruncatedList(items[:best_idx], truncated=True)


def resolve_promoter_portfolio(
    con: sqlite3.Connection,
    project_id: Optional[int] = None,
    promoter_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve cross-project promoter portfolio with composite entity linkage, homonym warnings,

    and modern expired scheme risk analysis.
    """
    cur = con.cursor()
    target_pname = promoter_name
    target_prom_id = None

    if project_id and not target_pname:
        p_row = cur.execute(
            "SELECT promoter_name, promoter_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if p_row:
            target_pname = p_row[0]
            target_prom_id = p_row[1]

    if not target_pname and target_prom_id is None:
        return {
            "promoter_name": None,
            "project_id": project_id,
            "portfolio_count": 0,
            "resolved_projects": [],
            "linkage_confidence": "NONE",
            "homonym_warning": False,
            "warning_message": None,
            "modern_expired_no_bu_count": 0,
            "shared_anchors": {"shared_licenses": [], "shared_banks": []},
            "truncated": False,
        }

    pname_str = (target_pname or "").strip()
    pname_upper = pname_str.upper()

    # 1. Homonym warning detection for common Gujarat brand prefixes
    matched_prefix = None
    for prefix in COMMON_GUJARAT_PREFIXES:
        if (
            pname_upper == prefix
            or pname_upper.startswith(prefix + " ")
            or pname_upper.startswith(prefix + "-")
            or pname_upper.startswith(prefix + "_")
            or pname_upper.startswith(prefix)
        ):
            matched_prefix = prefix
            break

    homonym_warning = bool(matched_prefix)
    warning_msg = (
        f"High homonym risk: '{pname_str}' uses common Gujarat brand prefix '{matched_prefix}'. "
        "Cross-entity linkage may conflate distinct legal entities without shared professional license or bank verification."
        if homonym_warning
        else None
    )

    # 2. Query portfolio candidate projects
    norm_pname = "".join(c for c in pname_upper if c.isalnum() or c == " ").strip()
    query = """
        SELECT 
            p.project_id, p.name, p.registration_number, p.promoter_id, p.promoter_name,
            p.district, p.completion_date, p.project_status, p.start_date,
            COALESCE(s.has_bu_noc, 0) as has_bu_noc,
            s.bu_certificate_no,
            s.tier,
            s.total_units,
            s.booked_units
        FROM projects p
        LEFT JOIN project_summaries s ON s.project_id = p.project_id
        WHERE (? IS NOT NULL AND p.promoter_id = ?)
           OR (UPPER(TRIM(p.promoter_name)) = ?)
           OR (? != '' AND UPPER(TRIM(p.promoter_name)) LIKE ? || '%')
        ORDER BY p.project_id ASC
    """
    cur.execute(query, (target_prom_id, target_prom_id, pname_upper, norm_pname, norm_pname))
    raw_candidates = [dict(r) for r in cur.fetchall()]

    # Collect shared anchors (licenses & bank accounts)
    project_ids = [c["project_id"] for c in raw_candidates]
    prof_licenses: Dict[int, Set[str]] = {}
    bank_anchors: Dict[int, Set[str]] = {}
    INVALID_ANCHOR_TOKENS: Set[str] = {
        "", "NA", "N/A", "NONE", "NULL", "0", "-", "--", "N.A", "N.A.", "UNKNOWN",
        "NOT APPLICABLE", "NOT APPLIED", "REDACTED", "NOT AVAILABLE"
    }

    if project_ids:
        placeholders = ",".join("?" for _ in project_ids)
        cur.execute(
            f"SELECT project_id, license_or_reg_no FROM professionals "
            f"WHERE project_id IN ({placeholders}) AND license_or_reg_no IS NOT NULL AND trim(license_or_reg_no) != ''",
            project_ids,
        )
        for pid_val, lic in cur.fetchall():
            scrubbed_l = redact_value("license_or_reg_no", lic)
            if not scrubbed_l or "[REDACTED" in str(scrubbed_l):
                continue
            clean_l = "".join(c for c in str(scrubbed_l).upper() if c.isalnum())
            if clean_l and clean_l not in INVALID_ANCHOR_TOKENS and len(clean_l) >= 3:
                prof_licenses.setdefault(pid_val, set()).add(clean_l)

        cur.execute(
            f"SELECT project_id, ifsc_code, bank_name, branch_name FROM banks "
            f"WHERE project_id IN ({placeholders}) AND (ifsc_code IS NOT NULL OR (bank_name IS NOT NULL AND branch_name IS NOT NULL))",
            project_ids,
        )
        for pid_val, ifsc, bname, branch in cur.fetchall():
            clean_ifsc = "".join(c for c in str(ifsc or "").upper() if c.isalnum())
            if clean_ifsc and clean_ifsc not in INVALID_ANCHOR_TOKENS and len(clean_ifsc) >= 4 and "[REDACTED" not in clean_ifsc:
                bank_anchors.setdefault(pid_val, set()).add(f"IFSC:{clean_ifsc}")
            elif bname and branch:
                # Require both bank_name and branch_name - NEVER bare bank_name
                clean_bn = "".join(c for c in str(bname).upper() if c.isalnum())
                clean_br = "".join(c for c in str(branch).upper() if c.isalnum())
                if (
                    clean_bn and clean_br
                    and clean_bn not in INVALID_ANCHOR_TOKENS
                    and clean_br not in INVALID_ANCHOR_TOKENS
                    and len(clean_bn) >= 3 and len(clean_br) >= 3
                    and "[REDACTED" not in clean_bn and "[REDACTED" not in clean_br
                ):
                    bank_anchors.setdefault(pid_val, set()).add(f"BRANCH:{clean_bn}_{clean_br}")

    # Build adjacency graph between candidate projects via Composite Key (c)
    cand_by_id = {c["project_id"]: c for c in raw_candidates}
    adj: Dict[int, Set[int]] = {pid: set() for pid in project_ids}

    for i in range(len(project_ids)):
        for j in range(i + 1, len(project_ids)):
            p1, p2 = project_ids[i], project_ids[j]
            c1, c2 = cand_by_id[p1], cand_by_id[p2]
            
            shared_l = prof_licenses.get(p1, set()) & prof_licenses.get(p2, set())
            shared_b = bank_anchors.get(p1, set()) & bank_anchors.get(p2, set())
            shared_prom_id = (
                c1.get("promoter_id") is not None
                and c2.get("promoter_id") is not None
                and c1["promoter_id"] == c2["promoter_id"]
            )

            if shared_l or shared_b or shared_prom_id:
                adj[p1].add(p2)
                adj[p2].add(p1)

    # Connected components (disjoint clusters)
    visited: Set[int] = set()
    clusters: List[Dict[str, Any]] = []
    cluster_idx = 1
    ref_today = datetime.now(timezone.utc).date().isoformat()

    for pid in project_ids:
        if pid in visited:
            continue
        comp_pids: List[int] = []
        q = [pid]
        visited.add(pid)
        while q:
            curr = q.pop(0)
            comp_pids.append(curr)
            for neighbor in adj.get(curr, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    q.append(neighbor)

        comp_pids.sort()
        comp_projects = [cand_by_id[p] for p in comp_pids]
        
        # Calculate cluster-specific shared anchors
        cl_shared_lics: Set[str] = set()
        cl_shared_banks: Set[str] = set()
        for i in range(len(comp_pids)):
            for j in range(i + 1, len(comp_pids)):
                p1, p2 = comp_pids[i], comp_pids[j]
                cl_shared_lics.update(prof_licenses.get(p1, set()) & prof_licenses.get(p2, set()))
                cl_shared_banks.update(bank_anchors.get(p1, set()) & bank_anchors.get(p2, set()))

        # Calculate cluster-specific modern_expired_no_bu_count
        cl_modern_expired = 0
        for cand in comp_projects:
            c_pname = str(cand.get("promoter_name") or "")
            c_name = str(cand.get("name") or "")
            c_reg = str(cand.get("registration_number") or "")
            full_text = f"{c_pname} {c_name} {c_reg}".upper()
            if any(g in full_text for g in GOVT_AUTHORITY_KEYWORDS):
                continue
            c_date = str(cand.get("completion_date") or "").strip()
            year_match = re.search(r"\b(20\d\d)\b", c_date)
            if not year_match:
                continue
            if int(year_match.group(1)) >= 2020:
                is_exp = (c_date and c_date < ref_today) or (cand.get("project_status") in ("EXPIRED", "REVOKED"))
                has_bu = bool(cand.get("has_bu_noc")) or bool(cand.get("bu_certificate_no"))
                if is_exp and not has_bu:
                    cl_modern_expired += 1

        # Cluster confidence scoring
        if len(comp_projects) <= 1:
            cl_confidence = "LOW" if homonym_warning else "MEDIUM"
        elif cl_shared_lics or cl_shared_banks or (cand_by_id[comp_pids[0]].get("promoter_id") is not None and len(comp_projects) > 1):
            cl_confidence = "HIGH"
        elif homonym_warning:
            cl_confidence = "LOW"
        else:
            cl_confidence = "MEDIUM"

        cl_districts = sorted(list({str(p.get("district") or "Unknown") for p in comp_projects}))
        
        clusters.append({
            "cluster_id": cluster_idx,
            "districts": cl_districts,
            "portfolio_count": len(comp_projects),
            "linkage_confidence": cl_confidence,
            "shared_anchors": {
                "shared_licenses": sorted(list(cl_shared_lics)),
                "shared_banks": sorted(list(cl_shared_banks)),
            },
            "modern_expired_no_bu_count": cl_modern_expired,
            "projects": comp_projects,
        })
        cluster_idx += 1

    # Sort clusters by portfolio_count DESC
    clusters.sort(key=lambda c: (c["portfolio_count"], c["districts"]), reverse=True)

    # Compute overall modern_expired_no_bu_count
    total_modern_expired_no_bu_count = sum(c["modern_expired_no_bu_count"] for c in clusters)
    
    # Compute all shared anchors across verified clusters
    all_shared_lics: Set[str] = set()
    all_shared_banks: Set[str] = set()
    for c in clusters:
        all_shared_lics.update(c["shared_anchors"]["shared_licenses"])
        all_shared_banks.update(c["shared_anchors"]["shared_banks"])

    # Determine primary linkage confidence and project list
    target_cluster: Optional[Dict[str, Any]] = None
    if project_id:
        for cl in clusters:
            if any(p["project_id"] == project_id for p in cl["projects"]):
                target_cluster = cl
                break

    if target_cluster is not None:
        primary_confidence = target_cluster["linkage_confidence"]
        primary_projects = target_cluster["projects"]
        target_cluster_id = target_cluster["cluster_id"]
    elif len(raw_candidates) <= 1:
        primary_confidence = "LOW" if homonym_warning else "MEDIUM"
        primary_projects = raw_candidates
        target_cluster_id = 1 if clusters else None
    elif len(clusters) > 1:
        primary_confidence = "PARTITIONED_MULTI_CLUSTER"
        primary_projects = raw_candidates
        target_cluster_id = None
    else:
        primary_confidence = clusters[0]["linkage_confidence"]
        primary_projects = clusters[0]["projects"]
        target_cluster_id = clusters[0]["cluster_id"]

    # Compact clusters representation for token safety (<= 6k tokens)
    compact_clusters: List[Dict[str, Any]] = []
    for cl in clusters:
        compact_clusters.append({
            "cluster_id": cl["cluster_id"],
            "districts": cl["districts"],
            "portfolio_count": cl["portfolio_count"],
            "linkage_confidence": cl["linkage_confidence"],
            "shared_anchors": cl["shared_anchors"],
            "modern_expired_no_bu_count": cl["modern_expired_no_bu_count"],
            "project_ids": [p["project_id"] for p in cl["projects"]],
            "sample_projects": [p.get("name") for p in cl["projects"][:3]],
        })

    # Apply PII redaction and token cap
    redacted_projects = [redact_record(c) for c in primary_projects]
    capped_candidates = _enforce_token_cap_list(redacted_projects)

    return {
        "promoter_name": redact_value("name", pname_str),
        "project_id": project_id,
        "target_cluster_id": target_cluster_id,
        "portfolio_count": len(raw_candidates),
        "cluster_count": len(clusters),
        "clusters": compact_clusters,
        "resolved_projects": list(capped_candidates),
        "linkage_confidence": primary_confidence,
        "homonym_warning": homonym_warning,
        "warning_message": warning_msg,
        "modern_expired_no_bu_count": total_modern_expired_no_bu_count,
        "shared_anchors": {
            "shared_licenses": sorted(list(all_shared_lics)),
            "shared_banks": sorted(list(all_shared_banks)),
        },
        "truncated": getattr(capped_candidates, "truncated", False),
    }


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
        """Populate graph nodes and edges from curated relational tables.

        Replaces legacy promoter:None edges with Composite Keys (c) anchored by
        promoter_name + professional license or bank branch.
        """
        cur = self.con.cursor()

        # 1. Projects
        cur.execute("SELECT project_id, name, registration_number, district FROM projects")
        for row in cur.fetchall():
            pid = row["project_id"]
            p_node = f"project:{pid}"
            p_props = json.dumps({
                "registration_number": row["registration_number"],
                "district": row["district"],
            })
            self._insert_node(p_node, "Project", redact_value("name", row["name"]), properties_json=p_props)

        # 2. Promoters
        cur.execute("SELECT promoter_id, name, promoter_type FROM promoters WHERE promoter_id IS NOT NULL")
        for row in cur.fetchall():
            prom_id = row["promoter_id"]
            if prom_id is None or str(prom_id).strip().lower() in ("", "none"):
                continue
            prom_node = f"promoter:{prom_id}"
            prom_props = json.dumps({"promoter_type": row["promoter_type"]})
            self._insert_node(prom_node, "Promoter", redact_value("name", row["name"]), properties_json=prom_props)

        # Edge Project -> DevelopedBy -> Promoter
        # Composite Key derived from projects.promoter_name + shared professional license OR bank branch
        cur.execute("SELECT project_id, promoter_id, promoter_name FROM projects")
        for row in cur.fetchall():
            pid = row["project_id"]
            prom_id = row["promoter_id"]
            raw_pname = row["promoter_name"]

            has_valid_id = prom_id is not None and str(prom_id).strip().lower() not in ("", "none")
            has_valid_name = raw_pname is not None and str(raw_pname).strip().lower() not in ("", "none")

            if not has_valid_id and not has_valid_name:
                continue

            if has_valid_id:
                prom_node = f"promoter:{prom_id}"
            else:
                pname_clean = str(raw_pname).strip()
                norm_pname = "".join(c for c in pname_clean.upper() if c.isalnum() or c == " ").strip().replace(" ", "_")

                cur_prof = self.con.execute(
                    "SELECT license_or_reg_no FROM professionals WHERE project_id = ? AND license_or_reg_no IS NOT NULL AND trim(license_or_reg_no) != '' LIMIT 1",
                    (pid,),
                ).fetchone()
                anchor = ""
                if cur_prof and cur_prof[0]:
                    lic_clean = "".join(c for c in str(cur_prof[0]).upper() if c.isalnum())
                    if lic_clean and "[REDACTED" not in lic_clean:
                        anchor = f":lic:{lic_clean[:16]}"
                if not anchor:
                    cur_bank = self.con.execute(
                        "SELECT ifsc_code, branch_name FROM banks WHERE project_id = ? AND (ifsc_code IS NOT NULL OR branch_name IS NOT NULL) LIMIT 1",
                        (pid,),
                    ).fetchone()
                    if cur_bank:
                        b_ident = str(cur_bank[0] or cur_bank[1] or "").strip().upper()
                        b_clean = "".join(c for c in b_ident if c.isalnum())
                        if b_clean:
                            anchor = f":bank:{b_clean[:16]}"

                prom_node = f"promoter:comp:{norm_pname}{anchor}"
                self._insert_node(prom_node, "Promoter", redact_value("name", pname_clean))

            self._insert_edge(f"project:{pid}", "DEVELOPED_BY", prom_node)

        # 3. Professionals
        cur.execute("SELECT project_id, role, name, firm_name, license_or_reg_no FROM professionals")
        for row in cur.fetchall():
            role = row["role"].lower()
            name = redact_value("name", row["name"].strip())
            reg_no = redact_value("license_or_reg_no", row["license_or_reg_no"])
            firm = redact_value("firm_name", row["firm_name"])
            is_verified = bool(reg_no and str(reg_no).strip() and "[REDACTED" not in str(reg_no))

            norm_name = "".join(c for c in name.lower() if c.isalnum() or c == " ").strip().replace(" ", "_")
            prof_node = f"professional:{role}:{norm_name}"
            prof_props = json.dumps({
                "role": role,
                "firm_name": firm,
                "license_or_reg_no": reg_no,
                "is_verified": is_verified,
            })
            self._insert_node(prof_node, role.capitalize(), name, properties_json=prof_props)

            rel_name = {
                "architect": "DESIGNED_BY",
                "engineer": "ENGINEERED_BY",
                "ca": "AUDITED_BY",
                "contractor": "CONSTRUCTED_BY",
            }.get(role, "ASSOCIATED_WITH")

            edge_props = json.dumps({
                "role": role,
                "firm_name": firm,
                "license_or_reg_no": reg_no,
            })
            self._insert_edge(f"project:{row['project_id']}", rel_name, prof_node, properties_json=edge_props)

        # 4. Banks
        cur.execute("SELECT project_id, bank_name, branch_name FROM banks")
        for row in cur.fetchall():
            bname = redact_value("bank_name", row["bank_name"].strip())
            branch = redact_value("branch_name", row["branch_name"] or "Main")
            norm_bank = "".join(c for c in bname.lower() if c.isalnum() or c == " ").strip().replace(" ", "_")
            bank_node = f"bank:{norm_bank}"
            bank_props = json.dumps({"branch_name": branch})
            self._insert_node(bank_node, "Bank", bname, properties_json=bank_props)
            self._insert_edge(f"project:{row['project_id']}", "ESCROW_AT", bank_node)

        # 5. Previous Projects — self-links excluded
        cur.execute(
            "SELECT project_id, linked_project_name, linked_project_id FROM previous_projects "
            "WHERE linked_project_id IS NOT NULL AND linked_project_id != project_id"
        )
        for row in cur.fetchall():
            lp_name = redact_value("name", row["linked_project_name"] or f"Project_{row['linked_project_id']}")
            lp_id = row["linked_project_id"] or "".join(c for c in lp_name.lower() if c.isalnum())
            prev_node = f"prior_project:{lp_id}"
            self._insert_node(prev_node, "PriorProject", lp_name)
            self._insert_edge(f"project:{row['project_id']}", "PRIOR_PORTFOLIO", prev_node)

        self.con.commit()

        nodes_count = self.con.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
        edges_count = self.con.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        return {"nodes": nodes_count, "edges": edges_count}

    def _insert_node(self, node_id: str, kind: str, label: str, properties_json: Optional[str] = None):
        self.con.execute(
            "INSERT OR REPLACE INTO graph_nodes (node_id, kind, label, properties_json) VALUES (?, ?, ?, ?)",
            (node_id, kind, label, properties_json),
        )

    def _insert_edge(self, src_id: str, relation: str, dst_id: str, properties_json: Optional[str] = None):
        self.con.execute(
            "INSERT OR REPLACE INTO graph_edges (src_id, relation, dst_id, properties_json) VALUES (?, ?, ?, ?)",
            (src_id, relation, dst_id, properties_json),
        )

    def find_shared_entities(self, project_id: int) -> List[Dict[str, Any]]:
        """Find other projects sharing an architect, engineer, CA, or bank with this project.

        Filters out legacy promoter:None edges and enforces <= 4,000 token cap.
        Uses a two-step indexed lookup to avoid unindexed string-concatenation joins on projects.
        """
        src_proj = f"project:{project_id}"
        query = """
            SELECT 
                e1.relation AS connection_type,
                n.label AS shared_entity_name,
                n.kind AS entity_kind,
                e2.src_id AS linked_project_node
            FROM graph_edges e1
            JOIN graph_nodes n ON n.node_id = e1.dst_id
            JOIN graph_edges e2 ON e2.dst_id = e1.dst_id AND e2.src_id != e1.src_id
            WHERE e1.src_id = ?
              AND e1.dst_id NOT LIKE 'promoter:None%'
              AND e1.dst_id != 'promoter:'
              AND e1.dst_id IS NOT NULL
              AND e2.dst_id NOT LIKE 'promoter:None%'
              AND e2.dst_id != 'promoter:'
              AND e2.dst_id IS NOT NULL
              AND n.node_id NOT LIKE 'promoter:None%'
              AND n.node_id != 'promoter:'
              AND e1.src_id NOT LIKE 'promoter:None%'
              AND e2.src_id NOT LIKE 'promoter:None%'
              AND e2.src_id LIKE 'project:%'
        """
        cur = self.con.execute(query, (src_proj,))
        raw_rows = cur.fetchall()

        # Step 2: resolve project names via primary key index
        pid_set: Set[int] = set()
        parsed_rows: List[Tuple[Any, Any, Any, int]] = []
        for r in raw_rows:
            node_str = str(r["linked_project_node"])
            if node_str.startswith("project:"):
                raw_id = node_str.split(":", 1)[1]
                if raw_id.isdigit():
                    pid_int = int(raw_id)
                    pid_set.add(pid_int)
                    parsed_rows.append((r["connection_type"], r["shared_entity_name"], r["entity_kind"], pid_int))

        name_map: Dict[int, str] = {}
        if pid_set:
            pids_list = list(pid_set)
            chunk_size = 500
            for i in range(0, len(pids_list), chunk_size):
                chunk = pids_list[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                cur_p = self.con.execute(
                    f"SELECT project_id, name FROM projects WHERE project_id IN ({placeholders})",
                    chunk,
                )
                for pr in cur_p.fetchall():
                    name_map[pr["project_id"]] = pr["name"]

        results = []
        for conn_type, entity_name, entity_kind, linked_pid in parsed_rows:
            if linked_pid in name_map:
                results.append({
                    "connection_type": conn_type,
                    "shared_entity_name": redact_value("name", entity_name),
                    "entity_kind": entity_kind,
                    "linked_project_id": linked_pid,
                    "linked_project_name": redact_value("name", name_map[linked_pid]),
                })

        return _enforce_token_cap_list(results)

    def trace_contagion_risk(self, project_id: int) -> List[Dict[str, Any]]:
        """Multi-hop query: check if any professional or promoter linked to this project

        is also linked to projects that have registered consumer complaints or cost reversals.
        """
        shared = self.find_shared_entities(project_id)
        contagion_leads = []

        for item in shared:
            linked_pid = item["linked_project_id"]
            complaints = self.con.execute(
                "SELECT COUNT(*) FROM applications WHERE project_id = ? AND application_type = 'Complaint'",
                (linked_pid,),
            ).fetchone()[0]

            if complaints > 0:
                lead = {
                    "risk_type": "PROFESSIONAL_LINKED_COMPLAINT",
                    "severity": "MEDIUM",
                    "shared_entity": redact_value("name", item["shared_entity_name"]),
                    "entity_role": item["entity_kind"],
                    "linked_project": redact_value("name", item["linked_project_name"]),
                    "linked_project_id": linked_pid,
                    "detail": (
                        f"{item['entity_kind']} '{item['shared_entity_name']}' is also engaged on "
                        f"{item['linked_project_name']} (ID {linked_pid}), which has {complaints} active "
                        "consumer complaint application(s)."
                    ),
                }
                contagion_leads.append(redact_record(lead))

        return _enforce_token_cap_list(contagion_leads)

    def get_ego_network(
        self,
        project_id: int,
        depth: int = 2,
        max_nodes: int = 250,
    ) -> Dict[str, Any]:
        """Compute the bounded 1st and 2nd degree ego-network for a given project.

        Ignores legacy promoter:None edges and enforces <= 4,000 token cap.
        Returns Vis.js compatible nodes and edges dictionaries.
        """
        root_id = f"project:{project_id}"
        cur = self.con.cursor()

        visited_nodes = {root_id}
        frontier = {root_id}
        collected_edges: List[Dict[str, Any]] = []

        for _ in range(depth):
            if not frontier or len(visited_nodes) >= max_nodes:
                break
            placeholders = ",".join("?" for _ in frontier)
            frontier_list = list(frontier)
            query = f"""
                SELECT src_id, relation, dst_id 
                FROM graph_edges 
                WHERE (src_id IN ({placeholders}) OR dst_id IN ({placeholders}))
                  AND src_id NOT LIKE 'promoter:None%'
                  AND dst_id NOT LIKE 'promoter:None%'
                  AND src_id != 'promoter:'
                  AND dst_id != 'promoter:'
                  AND src_id IS NOT NULL
                  AND dst_id IS NOT NULL
            """
            cur.execute(query, frontier_list + frontier_list)
            rows = cur.fetchall()

            next_frontier = set()
            for r in rows:
                src, dst = r["src_id"], r["dst_id"]
                if "promoter:none" in src.lower() or "promoter:none" in dst.lower():
                    continue
                if src == "promoter:" or dst == "promoter:":
                    continue

                collected_edges.append({
                    "from": src,
                    "to": dst,
                    "label": r["relation"],
                    "color": {"color": "#94a3b8", "highlight": "#2563eb"},
                })
                for nid in (src, dst):
                    if nid not in visited_nodes:
                        if len(visited_nodes) < max_nodes:
                            visited_nodes.add(nid)
                            next_frontier.add(nid)

            frontier = next_frontier

        seen_edges = set()
        final_edges = []
        for e in collected_edges:
            if e["from"] in visited_nodes and e["to"] in visited_nodes:
                edge_key = (e["from"], e["label"], e["to"])
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    final_edges.append(e)

        color_map = {
            "Project": "#2563eb",
            "Promoter": "#7c3aed",
            "Engineer": "#d97706",
            "Architect": "#0d9488",
            "Ca": "#059669",
            "Bank": "#e11d48",
            "PriorProject": "#64748b",
        }
        placeholders = ",".join("?" for _ in visited_nodes)
        cur.execute(
            f"SELECT node_id, kind, label FROM graph_nodes "
            f"WHERE node_id IN ({placeholders}) "
            f"  AND node_id NOT LIKE 'promoter:None%' AND node_id != 'promoter:'",
            list(visited_nodes),
        )
        nodes = [
            {
                "id": r["node_id"],
                "label": redact_value("name", r["label"]),
                "group": r["kind"],
                "color": color_map.get(r["kind"], "#3b82f6"),
            }
            for r in cur.fetchall()
        ]

        # Enforce <= 4,000 token cap
        is_truncated = False
        token_est = _estimate_tokens({"nodes": nodes, "edges": final_edges})
        if token_est > MAX_GRAPH_TOKENS:
            is_truncated = True
            low = 0
            high = len(nodes)
            best_nodes = nodes
            best_edges = final_edges
            while low <= high:
                mid = (low + high) // 2
                cand_nodes = nodes[:mid]
                c_ids = {n["id"] for n in cand_nodes}
                cand_edges = [e for e in final_edges if e["from"] in c_ids and e["to"] in c_ids]
                if _estimate_tokens({"nodes": cand_nodes, "edges": cand_edges}) <= MAX_GRAPH_TOKENS:
                    best_nodes = cand_nodes
                    best_edges = cand_edges
                    low = mid + 1
                else:
                    high = mid - 1
            nodes = best_nodes
            final_edges = best_edges
            token_est = _estimate_tokens({"nodes": nodes, "edges": final_edges})

        return {
            "nodes": nodes,
            "edges": final_edges,
            "truncated": is_truncated,
            "token_estimate": token_est,
        }

    def resolve_promoter_portfolio(
        self,
        project_id: Optional[int] = None,
        promoter_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Instance method shortcut to resolve_promoter_portfolio."""
        return resolve_promoter_portfolio(self.con, project_id=project_id, promoter_name=promoter_name)
