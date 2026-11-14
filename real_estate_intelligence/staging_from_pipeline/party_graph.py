"""Build a private, source-linked graph of the pilot and one-hop projects."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from ..legacy_collector.cli import DEFAULT_DATA
from ..legacy_collector.party_enrichment import PARTY_RUN, RELATED_RUN, PILOT_RUN, norm
from ..core.storage import RunStore


def build(data_root: Path, party_run_id: str, pilot_run_id: str,
          related_run_id: str) -> dict:
    party_root = data_root / "runs" / party_run_id
    summary = json.loads((party_root / "exports" / "party_links_redacted.json").read_text(encoding="utf-8"))
    pilot = RunStore(data_root, pilot_run_id)
    related = RunStore(data_root, related_run_id)
    source_stores = {pilot.run_id: pilot, related.run_id: related}
    output = party_root / "derived" / "party_network.sqlite"
    output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output)
    db.executescript("""
        DROP TABLE IF EXISTS edges;
        DROP TABLE IF EXISTS nodes;
        CREATE TABLE nodes (node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL);
        CREATE TABLE edges (
            src_id TEXT NOT NULL, relation TEXT NOT NULL, dst_id TEXT NOT NULL,
            match_status TEXT NOT NULL, source_run_id TEXT NOT NULL,
            source_request_key TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            source_json_path TEXT NOT NULL, source_document_sha256 TEXT,
            source_page INTEGER, filing_submission TEXT,
            PRIMARY KEY(src_id, relation, dst_id, source_run_id, source_request_key,
                        source_json_path, filing_submission)
        );
        CREATE INDEX edges_dst_idx ON edges(dst_id, relation);
    """)

    def node(node_id, kind, label):
        db.execute("INSERT OR IGNORE INTO nodes VALUES (?, ?, ?)", (node_id, kind, label or kind))

    def edge(src, relation, dst, status, evidence):
        source_store = source_stores[evidence["run_id"]]
        request = source_store.get_request(evidence["request_key"])
        if not request or request["sha256"] != evidence["raw_sha256"]:
            raise ValueError(f"Source hash does not match the archived request: {evidence['request_key']}")
        if evidence.get("document_sha256"):
            document = source_store._connection().execute(
                "SELECT 1 FROM documents WHERE sha256=? AND status='ok' LIMIT 1",
                (evidence["document_sha256"],)).fetchone()
            if not document:
                raise ValueError(f"Missing signed document for {evidence['request_key']}")
        db.execute("""
            INSERT OR IGNORE INTO edges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (src, relation, dst, status, evidence["run_id"], evidence["request_key"],
              evidence["raw_sha256"], evidence["json_path"],
              evidence.get("document_sha256"), evidence.get("document_page"),
              evidence.get("filing_submission")))

    for store in (pilot, related):
        for project in store.project_rows():
            node(f"project:{project['project_id']}", "project", project["name"])

    for link in summary["links"]:
        src = f"project:{link['project_id']}"
        role = link["role"]
        profile_id = link.get("profile_id")
        credential = link.get("professional_credential")
        if profile_id:
            kind = ("ca" if role == "ca_certificate" else
                    "architect" if role == "architect_form_one" else
                    "engineer" if role == "engineer_form_two" else role)
            dst = f"{kind}:{profile_id}"
            node(dst, kind, link.get("verified_profile_name") or link.get("display_name"))
        elif credential:
            digest = hashlib.sha256(norm(credential).encode()).hexdigest()[:20]
            dst = f"unresolved_credential:{role}:{digest}"
            node(dst, "unresolved_credential", link.get("display_name"))
        else:
            dst = f"unresolved_assignment:{link['project_id']}:{role}:{link.get('project_assignment_id')}"
            node(dst, "unresolved_assignment", link.get("display_name"))
        edge(src, role, dst, link["match_status"], link["source"])

    for connection in summary["promoter_related_projects"]:
        src = f"project:{connection['seed_project_id']}"
        dst = f"project:{connection['related_project_id']}"
        edge(src, "listed_as_promoter_related_project", dst,
             "portal_previous_projects_record", connection["source"])
    for claim in summary.get("promoter_declared_prior_projects", []):
        internal_id = claim.get("portal_previous_project_id")
        if not internal_id:
            continue
        src = f"promoter:{claim['promoter_id']}"
        dst = f"previous_project_claim:{claim['promoter_id']}:{internal_id}"
        node(dst, "previous_project_claim", claim.get("project_name"))
        edge(src, "has_previous_project_claim", dst,
             "self_reported_portal_previous_project", claim["source"])
    for item in summary.get("reported_financial_counterparties", []):
        label = item["reported_institution_label"]
        digest = hashlib.sha256(norm(label).encode()).hexdigest()[:20]
        dst = f"reported_institution_label:{digest}"
        node(dst, "reported_institution_label", label)
        edge(f"project:{item['project_id']}", item["relation"], dst,
             "portal_label_unverified_entity", item["source"])
    db.commit()
    kinds = dict(db.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind"))
    relations = dict(db.execute("SELECT relation, COUNT(*) FROM edges GROUP BY relation"))
    shared = db.execute("""
        SELECT n.kind, n.label, COUNT(DISTINCT e.src_id) AS projects
        FROM edges e JOIN nodes n ON n.node_id=e.dst_id
        WHERE n.kind IN ('promoter','architect','engineer','ca')
        GROUP BY n.node_id HAVING COUNT(DISTINCT e.src_id)>1
        ORDER BY projects DESC, n.kind, n.label
    """).fetchall()
    result = {"graph_path": str(output), "nodes": kinds, "edges": relations,
              "verified_entities_on_multiple_projects": [
                  {"kind": kind, "name": label, "project_count": count}
                  for kind, label, count in shared]}
    report_dir = party_root / "reports"
    report_dir.mkdir(exist_ok=True)
    lines = ["# Party network prototype", "",
             f"Pilot run `{pilot_run_id}`; promoter-linked project run `{related_run_id}`; party profile run `{party_run_id}`.",
             "All links retain source run, request key, raw hash and JSON path. CA certificate links also retain document hash, page and filing submission date.",
             "Profiles are not legal or quality endorsements. Self-reported experience and project counts are not a complete work history.", "",
             "## Counts", "",
             f"- Project nodes: {kinds.get('project', 0)}; verified promoter profiles: {kinds.get('promoter', 0)}; verified architect profiles: {kinds.get('architect', 0)}; verified engineer profiles: {kinds.get('engineer', 0)}; verified CA profiles: {kinds.get('ca', 0)}.",
             f"- Unresolved credential nodes: {kinds.get('unresolved_credential', 0)}; unresolved assignment nodes: {kinds.get('unresolved_assignment', 0)}.",
             f"- Project-to-project promoter history links: {relations.get('listed_as_promoter_related_project', 0)}.",
             f"- Entries in promoter previous-project forms without a verified GujRERA project ID: {relations.get('has_previous_project_claim', 0)}.", "",
             f"- Bank/account-bank and loan-lender labels: {sum(relations.get(r, 0) for r in ('project_bank_record','collection_account_bank','reported_loan_lender'))}. These labels are not merged across spelling variants or treated as verified legal entities.", "",
             "## Verified parties appearing on multiple sampled projects", "",
             "| Role | Party | Projects |", "|---|---|---:|"]
    for kind, label, count in shared:
        lines.append(f"| {kind} | {str(label).replace('|', '/')} | {count} |")
    if not shared:
        lines.append("| — | None in this selected sample | — |")
    lines += ["", "## Interpretation", "",
              "An unresolved credential can still connect identical registration numbers across projects, but it is not promoted to a verified profile node. Name-only candidates are never merged into a person node.",
              "The `New`/`Ongoing` values in prior-project responses are portal labels; they are not a current construction-status determination. Verify dates, latest filings, completion documents and site records before such a claim.",
              "The graph is a disposable derived view. `party_links_redacted.json`, both source manifests and the signed PDF remain the evidence trail.", ""]
    lines += ["## Nine seed projects and their parties", "",
              "A CA listed here signed a dated certificate in the archive; the table does not assert a current assignment.", "",
              "| Project | Registered architect | Registered engineer | Form 1 signer | Form 2 signer | CA certificate signer | Promoter |",
              "|---|---|---|---|---|---|---|"]
    pilot_names = {row["project_id"]: row["name"] for row in pilot.project_rows()}
    for pid, name in pilot_names.items():
        grouped = {}
        for link in summary["links"]:
            if link["project_id"] == pid:
                grouped.setdefault(link["role"], []).append(link)
        cells = []
        for role in ("architect", "engineer", "architect_form_one",
                     "engineer_form_two", "ca_certificate", "promoter"):
            values = sorted({(item.get("verified_profile_name") or item.get("display_name") or "Unresolved")
                             + (" [index Form 2]" if role == "engineer_form_two" and
                                item.get("filing_source_endpoint") == "index_form_two" else "")
                             + (" [latest Form 2]" if role == "engineer_form_two" and
                                item.get("filing_source_endpoint") == "latest_form_two" else "")
                             + (" [unresolved profile]" if item["match_status"] in
                                ("unresolved", "candidate_name_only_not_linked") else "")
                             for item in grouped.get(role, [])})
            cells.append("; ".join(values).replace("|", "/") or "No linked record")
        lines.append(f"| {name.replace('|', '/')} (`{pid}`) | " + " | ".join(cells) + " |")
    lines += ["", "The Form 1 and Form 2 signers are archived separately from the registered project team. The index Form 2 may be older than the latest available form.", "",
              "## Financial institution labels on the seed projects", "",
              "Only bank and lender labels are shown. Account numbers are excluded; names are not merged across spelling variants. A loan row is a review lead, not a finding about current debt.", "",
              "| Project | Project bank | Collection bank | Loan lender labels |",
              "|---|---|---|---|"]
    for pid, name in pilot_names.items():
        cells = []
        for relation in ("project_bank_record", "collection_account_bank", "reported_loan_lender"):
            labels = sorted({item["reported_institution_label"] for item in
                             summary.get("reported_financial_counterparties", [])
                             if item["project_id"] == pid and item["relation"] == relation})
            cells.append("; ".join(labels).replace("|", "/") or "No linked record")
        lines.append(f"| {name.replace('|', '/')} (`{pid}`) | " + " | ".join(cells) + " |")
    lines += ["",
              "## Promoter-linked GujRERA projects", "",
              "The listed status is the portal's prior-project label, not a verified current construction state.", "",
              "| Seed project | Related project | Promoter | Portal label | Collection |",
              "|---:|---|---|---|---|"]
    related_rows = {row["project_id"]: row for row in related.project_rows()}
    for item in summary["promoter_related_projects"]:
        related_row = related_rows.get(item["related_project_id"])
        promoter = related_row["promoter_name"] if related_row else "not in run"
        lines.append(f"| {item['seed_project_id']} | "
                     f"{str(item.get('related_project_name') or '').replace('|', '/')} (`{item['related_project_id']}`) | "
                     f"{promoter} | {item.get('portal_project_status')} | "
                     f"{item.get('related_collection_status')} |")
    lines += ["", "## Promoter previous-project form entries", "",
              "These records have no verified GujRERA project ID in this run. Some are placeholders or repeat a known project name; they are claim nodes, not confirmed extra projects.", "",
              "| Seed project | Declared project | Reported status | Reported ongoing |",
              "|---:|---|---|---|"]
    for claim in summary.get("promoter_declared_prior_projects", []):
        lines.append(f"| {claim['seed_project_id']} | "
                     f"{str(claim.get('project_name') or '').replace('|', '/')} | "
                     f"{claim.get('reported_status')} | {claim.get('reported_ongoing')} |")
    lines.append("")
    report = report_dir / "NETWORK.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    result["report_path"] = str(report)

    profiles = {}
    for link in summary["links"]:
        profile_id = link.get("profile_id")
        if not profile_id:
            continue
        kind = ("ca" if link["role"] == "ca_certificate" else
                "architect" if link["role"] == "architect_form_one" else
                "engineer" if link["role"] == "engineer_form_two" else link["role"])
        key = (kind, profile_id)
        entry = profiles.setdefault(key, {
            "name": link.get("verified_profile_name") or link.get("display_name"),
            "summary": link.get("profile_summary") or {}, "project_ids": set(),
            "profile_request_key": link.get("profile_request_key"),
        })
        entry["project_ids"].add(link["project_id"])
    profile_lines = ["# Verified portal profiles in the 18-project sample", "",
                     "These are allowlisted summaries of private raw profile responses. Experience and portfolio counts are portal-reported; linked projects are only those collected here.", "",
                     "| Role | Portal profile ID | Name | Portal status | Reported experience | Reported completed key projects | Sample projects |",
                     "|---|---:|---|---|---|---|---|"]
    for (kind, profile_id), entry in sorted(profiles.items()):
        detail = entry["summary"]
        experience = detail.get("reported_experience_years")
        completed = detail.get("reported_completed_key_projects")
        if kind == "promoter":
            completed = detail.get("claimed_completed_projects")
        profile_lines.append(
            f"| {kind} | {profile_id} | {str(entry['name']).replace('|', '/')} | "
            f"{detail.get('status') or 'not reported'} | "
            f"{experience if experience not in (None, '') else 'not reported'} | "
            f"{completed if completed not in (None, '') else 'not reported'} | "
            f"{', '.join(map(str, sorted(entry['project_ids'])))} |"
        )
    profile_lines += ["", "Full response provenance and fetch times are in the party run's `manifest.sqlite`; the redacted JSON export maps each role to its profile request key and source filing.", ""]
    profiles_path = report_dir / "PROFILES.md"
    profiles_path.write_text("\n".join(profile_lines), encoding="utf-8")
    result["profiles_path"] = str(profiles_path)
    db.close()
    pilot.close()
    related.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--party-run", default=PARTY_RUN)
    parser.add_argument("--pilot-run", default=PILOT_RUN)
    parser.add_argument("--related-run", default=RELATED_RUN)
    args = parser.parse_args()
    print(json.dumps(build(args.data_root, args.party_run, args.pilot_run,
                           args.related_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
