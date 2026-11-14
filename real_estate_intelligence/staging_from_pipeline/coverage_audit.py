"""Audit how much of the frozen party network can support app claims.

Reads only the allowlisted party export and the saved project index. Outputs
an allowlisted JSON coverage matrix plus a readable gap report. No network.
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..legacy_collector.cli import DEFAULT_INDEX
from ..legacy_collector.index import read_index
from ..legacy_collector.party_enrichment import PARTY_RUN


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data" / "runs" / PARTY_RUN
LINKS = RUN / "exports" / "party_links_redacted.json"
OUT = RUN / "exports" / "coverage.json"
REPORT = RUN / "reports" / "COVERAGE.md"
SEED_IDS = {13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508}
ROLES = ("promoter", "architect", "architect_form_one", "engineer",
         "engineer_form_two", "ca_certificate", "contractor")
VERIFIED = {"verified_portal_id", "verified_registration_number",
            "verified_certificate_membership"}


def role_coverage(records):
    """Keep role observations distinct; a dated signer is not an assignment."""
    result = {}
    for role in ROLES:
        matches = [item for item in records if item["role"] == role]
        result[role] = {
            "observed_count": len(matches),
            "verified_count": sum(item["match_status"] in VERIFIED for item in matches),
            "statuses": dict(sorted(Counter(item["match_status"] for item in matches).items())),
            "evidence": [{
                "profile_id": item.get("profile_id"),
                "match_status": item["match_status"],
                "source_run_id": item["source"]["run_id"],
                "source_request_key": item["source"]["request_key"],
                "source_sha256": item["source"]["raw_sha256"],
                "source_json_path": item["source"]["json_path"],
                "document_sha256": item["source"].get("document_sha256"),
                "filing_submission": item["source"].get("filing_submission"),
            } for item in matches],
        }
    return result


def gap_codes(roles):
    gaps = []
    for role, code in (("architect", "registration_architect_profile_unverified"),
                       ("architect_form_one", "form_one_signer_profile_unverified"),
                       ("engineer", "registration_engineer_profile_unverified"),
                       ("engineer_form_two", "form_two_signer_profile_unverified"),
                       ("ca_certificate", "ca_certificate_signer_profile_unverified"),
                       ("contractor", "contractor_profile_unverified")):
        value = roles[role]
        if value["verified_count"] == 0:
            gaps.append(code)
        if value["verified_count"] < value["observed_count"]:
            gaps.append(f"{role}_has_unresolved_observations")
    if not roles["ca_certificate"]["observed_count"]:
        gaps.append("no_linked_signed_form_three_certificate_in_archive")
    return gaps


def status(value):
    return f"{value['verified_count']}/{value['observed_count']}"


def main():
    data = json.loads(LINKS.read_text(encoding="utf-8"))
    names = {}
    promoter_ids = set()
    for item in data["links"]:
        if item["role"] == "promoter" and item["profile_id"] is not None:
            promoter_ids.add(str(item["profile_id"]))
    projects_list, _ = read_index(DEFAULT_INDEX)
    for p in projects_list:
        if str(p.promoter_id) in promoter_ids:
            names[p.project_id] = p.name
    grouped = defaultdict(list)
    for item in data["links"]:
        grouped[item["project_id"]].append(item)
    related = defaultdict(set)
    for item in data["promoter_related_projects"]:
        related[item["seed_project_id"]].add(item["related_project_id"])
    projects = []
    for pid in sorted(grouped):
        roles = role_coverage(grouped[pid])
        projects.append({
            "project_id": pid,
            "project_name": names.get(pid),
            "seed": pid in SEED_IDS,
            "roles": roles,
            "known_related_project_ids": sorted(related[pid]),
            "gap_codes": gap_codes(roles),
        })
    index_ids = set(names)
    collected_ids = set(grouped)
    summary = {
        "index_date": "2026-10-11",
        "observation_date": "2026-10-15",
        "indexed_projects_for_sample_promoters": len(index_ids),
        "collected_projects_for_sample_promoters": len(collected_ids),
        "indexed_but_not_collected_project_ids": sorted(index_ids - collected_ids),
        "collected_but_not_in_index_project_ids": sorted(collected_ids - index_ids),
        "profile_role_coverage": {
            role: {
                "projects_with_observation": sum(bool(p["roles"][role]["observed_count"]) for p in projects),
                "projects_with_verified_profile": sum(bool(p["roles"][role]["verified_count"]) for p in projects),
            } for role in ROLES
        },
        "scope": "Only 18 archived project filings; no complete professional work-history API verified.",
    }
    output = {"summary": summary, "projects": projects}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Party and project coverage audit", "",
        "Saved index: 11 October 2026. Party and project archive: 15 October 2026.", "",
        f"The nine verified promoters have **{len(index_ids)} project IDs in the saved "
        f"17,634-project index**. **{len(collected_ids)}** are archived. "
        f"Indexed IDs still uncollected: **{len(index_ids - collected_ids)}**. "
        "This checks promoter IDs in that index, not every historical project "
        "or every professional's portfolio.", "",
        "Each table cell is **verified profile links / observed role records**. "
        "A zero can mean no linked observation in this archive; it does not prove "
        "that the project has no professional in that role. Registration roles "
        "and dated filing signers are separate.", "",
        "| Project | Promoter | Registered architect | Form 1 signer | "
        "Registered engineer | Form 2 signer | Form 3 CA signer |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for p in projects:
        r = p["roles"]
        label = f"{p['project_id']} {p['project_name'] or ''}".replace("|", "/")
        if p["seed"]:
            label += " **(seed)**"
        lines.append("| " + " | ".join([label] + [status(r[role]) for role in ROLES[:6]]) + " |")
    lines += [
        "", "## Open gaps", "",
        "- **CA:** A signed Form 3 certificate and a verified CA membership/profile "
        "link exist for 11/18 projects, including 7/9 seeds. Seed projects "
        "17855 (PROVINCE) and 20523 (PRAMUKH PENTAGON) have no linked signed "
        "certificate in this archive. The other open CA links are 1153, 6465, "
        "10911, 12318, and 19653. Their CA identities remain open, not absent.",
        "- **Architect:** Registration architect profiles are verified for 15/18 "
        "projects (7/9 seeds). The project registration has no architect assignment "
        "for 17255. The two AUDA ENGG 966 credential variants returned HTTP 500 "
        "from the profile lookup. Form 1 signer profiles are verified for "
        "10/18 projects (3/9 seeds); many other Form 1 signer rows omit a CoA "
        "number. Same-name matches remain unmerged until supported by a credential.",
        "- **Engineer:** Registration engineer profiles are verified for 7/18 "
        "projects. Other rows include unresolved licences and name-only candidates. "
        "Dated Form 2 signers have separate links and can differ from registration roles.",
        "- **Contractor:** Ten project assignment records are retained, with no "
        "verified contractor profile IDs from the tried route.",
        "- **Project data:** Project 29189 has a retained Form 8 HTTP 500 failure. "
        "The rest of its collected responses remain archived; that endpoint is open.",
        "- **Portfolio completeness:** No verified public endpoint enumerated all "
        "projects for an architect, engineer, or CA. Their graph edges show only "
        "the 18 sampled project filings. The 27 archived architect, engineer and "
        "CA profile responses have no populated project list: `enqiryList` is "
        "empty for all 27; architect and engineer records carry only summary "
        "experience/completion fields. The nine promoter profiles' self-reported "
        "project counts are not a verified project list.",
        "", "## App use", "",
        "`exports/coverage.json` gives each project role's observation count, "
        "verified count, match statuses, gap codes, and source hashes. Show "
        "`verified`, `candidate`, and `unresolved` explicitly. Present Form 1/2/3 "
        "signers with filing dates. Never infer an absent person or an adverse "
        "finding from a missing link.", "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(projects)} projects audited; {len(index_ids - collected_ids)} index projects uncollected")
    print(OUT)
    print(REPORT)


if __name__ == "__main__":
    main()
