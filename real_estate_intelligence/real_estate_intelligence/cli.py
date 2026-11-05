"""Command Line Interface for Real Estate Intelligence."""

import argparse
import json
import sys
from pathlib import Path

from .config import DEFAULT_DB_PATH, DEFAULT_SOURCE_RUN, WORKSPACE_ROOT
from .db.reader import DiskRunReader

from .analytics.audit import ProjectAuditor
from .analytics.investor_dossier import generate_investor_dossier
from .db.database import get_connection
from .db.loader import ingest_from_run
from .documents.search import DocumentSearchEngine
from .graph.network import KnowledgeGraph


def cmd_ingest(args):
    print(f"Starting ingestion from: {args.source}")
    print(f"Target SQLite database: {args.target}")
    reader = DiskRunReader(Path(args.source))
    stats = ingest_from_run(source_run_or_reader=reader, target_db_path=Path(args.target))
    print("\n[SUCCESS] Relational & FTS ingestion complete:")
    print(json.dumps(stats, indent=2))

    # Build Knowledge Graph
    con = get_connection(Path(args.target))
    kg = KnowledgeGraph(con)
    gstats = kg.build_graph()
    con.close()
    print("\n[SUCCESS] Knowledge Graph built:")
    print(json.dumps(gstats, indent=2))


def cmd_dossier(args):
    con = get_connection(Path(args.db))
    try:
        report = generate_investor_dossier(con, args.project_id)
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report, encoding="utf-8")
            print(f"[SUCCESS] Dossier saved to: {out_path}")
        else:
            print(report)
    finally:
        con.close()


def cmd_search(args):
    con = get_connection(Path(args.db))
    try:
        engine = DocumentSearchEngine(con)
        results = engine.search(query=args.query, project_id=args.project_id, limit=args.limit)
        print(f"\nFound {len(results)} matches for query: '{args.query}'\n")
        for idx, r in enumerate(results, 1):
            print(f"{idx}. [{r['doc_type']}] Project {r['project_id']} | Page {r['page_number']} (BM25: {r['rank']})")
            print(f"   File: {r['file_name']}")
            print(f"   Snippet: {r['snippet']}\n")
    finally:
        con.close()


def cmd_network(args):
    con = get_connection(Path(args.db))
    try:
        kg = KnowledgeGraph(con)
        shared = kg.find_shared_entities(args.project_id)
        contagion = kg.trace_contagion_risk(args.project_id)
        print(f"\n=== Entity Network for Project {args.project_id} ===")
        print(f"Shared Entities ({len(shared)}):")
        for s in shared:
            print(f"  - [{s['connection_type']}] {s['entity_kind']}: {s['shared_entity_name']} -> Links to: {s['linked_project_name']} (ID {s['linked_project_id']})")
        print(f"\nContagion Risk Leads ({len(contagion)}):")
        for c in contagion:
            print(f"  - [{c['risk_type']}] {c['detail']}")
    finally:
        con.close()


def cmd_audit(args):
    con = get_connection(Path(args.db))
    try:
        auditor = ProjectAuditor(con)
        if args.project_id:
            pids = [args.project_id]
        else:
            pids = [r["project_id"] for r in con.execute("SELECT project_id FROM projects ORDER BY project_id").fetchall()]

        print(f"\n=== Running Statutory Discrepancy Audit across {len(pids)} project(s) ===\n")
        total_leads = 0
        for pid in pids:
            pname = con.execute("SELECT name FROM projects WHERE project_id = ?", (pid,)).fetchone()["name"]
            leads = auditor.audit_project(pid)
            total_leads += len(leads)
            if leads:
                print(f"Project {pid}: {pname} ({len(leads)} lead(s))")
                for l in leads:
                    print(f"  * [{l.severity}] {l.title}")
                    print(f"    Anomaly: {l.detail}")
                    print(f"    Action: {l.reconciliation_guidance}\n")
            else:
                print(f"Project {pid}: {pname} -> Clean (0 discrepancies detected)\n")
        print(f"Total Discrepancies Detected: {total_leads}")
    finally:
        con.close()


from .analytics.claims_checker import SalesClaimVerifier
from .analytics.pricing import PricingIntelligence
from .ui.server import start_server


def cmd_pricing(args):
    db_path = Path(getattr(args, "db", DEFAULT_DB_PATH))
    pricing = PricingIntelligence(con_or_db=db_path)
    data = pricing.get_project_pricing_summary(args.project_id)
    if "error" in data:
        print(f"[ERROR] {data['error']}")
        return

    ov = data.get("overall_rate_per_sqft") or {}
    print(f"\n=== Registered Unit Transaction Pricing for Project {args.project_id} ===")
    print(f"Total Units Analyzed: {data['total_units_evaluated']} (Booked: {data['booked_units']}, Unbooked: {data['unbooked_units']})")
    print(f"Rate / Sq.Ft Benchmark: Min Rs. {ov.get('min', 0):,.0f} | Median Rs. {ov.get('median', 0):,.0f} | Max Rs. {ov.get('max', 0):,.0f}")
    print(f"25th - 75th Percentile Range: Rs. {ov.get('p25', 0):,.0f} - Rs. {ov.get('p75', 0):,.0f} / sq.ft\n")

    print("Block-by-Block Rates:")
    for bname, stats in (data.get("block_benchmarks") or {}).items():
        print(f"  * {bname} ({stats.get('count', 0)} booked): Median Rs. {stats.get('median', 0):,.0f} (Range Rs. {stats.get('min', 0):,.0f} - Rs. {stats.get('max', 0):,.0f})")

    assets = data.get("asset_class_benchmarks") or {}
    if len(assets) > 1:
        print("\nAsset Class Benchmarks (Commercial vs Residential):")
        for aclass, stats in assets.items():
            print(f"  * {aclass} ({stats.get('count', 0)} booked): Median Rs. {stats.get('median', 0):,.0f} / sqft (Range Rs. {stats.get('min', 0):,.0f} - Rs. {stats.get('max', 0):,.0f})")
        premiums = data.get("commercial_premiums") or {}
        if premiums:
            print("  Premiums over Residential:")
            for k, v in premiums.items():
                print(f"    - {k}: {v}x")

    recent = data.get("recent_registered_transactions") or []
    if recent:
        print(f"\nRecent Registered Transactions in Scheme ({len(recent)} shown):")
        print("  Date       | Block              | Carpet     | Consideration | Realized Rate")
        print("  -----------+--------------------+------------+---------------+--------------")
        for r in recent[:8]:
            print(f"  {r['agreement_date']} | {r['block']:<18} | {r['carpet_sqft']:>7.1f} sqft | Rs. {r['consideration_inr']/100000:>6.2f} L | Rs. {r['rate_sqft']:>6,.0f}/sqft")


def cmd_claims(args):
    con = get_connection(Path(args.db))
    try:
        verifier = SalesClaimVerifier(con)
        res = verifier.verify_claim(
            project_id=args.project_id,
            claimed_rate_sqft=args.claimed_rate,
            claimed_sold_pct=args.claimed_sold,
            claimed_completion_date=args.claimed_date,
        )
        print(f"\n=== Broker & Sales Claim Verification: {res['project_name']} (ID {res['project_id']}) ===")
        for c in res.get("verification_checks") or []:
            print(f"\n[VERDICT: {c['verdict']}] {c['metric']}")
            print(f"  * Claimed by Sales: {c['claimed']}")
            print(f"  * Statutory Reality: {c['statutory_actual']}")
            print(f"  * Fact Check: {c['detail']}")
            print(f"  * Buyer Tip: {c['buyer_guidance']}")
    finally:
        con.close()


def cmd_serve(args):
    start_server(port=args.port, db_path=Path(args.db))


def cmd_runway(args):
    con = get_connection(Path(args.db))
    try:
        auditor = ProjectAuditor(con)
        runway = auditor.calculate_escrow_runway(args.project_id)
        if "error" in runway:
            print(f"[ERROR] {runway['error']}")
            return
        print(f"\n=== Escrow Capital Burn-Rate & Cash Runway: Project {args.project_id} ===")
        print(f"Closing Escrow Balance (70% Retention): Rs. {runway['closing_escrow_balance_inr']:,.0f}")
        print(f"Estimated Monthly Construction Burn Rate: Rs. {runway['monthly_construction_burn_inr']:,.0f} / month")
        runway_str = f"{runway['estimated_runway_months']:.1f} months" if runway['estimated_runway_months'] is not None else "N/A"
        print(f"Estimated Escrow Cash Runway: {runway_str}")
        print(f"Remaining Estimated Construction Cost: Rs. {runway['remaining_construction_cost_inr']:,.0f}")
        print(f"Insolvency Risk Assessment: [{runway['insolvency_risk']}]\n")
    finally:
        con.close()


def cmd_spatial(args):
    con = get_connection(Path(args.db))
    try:
        from .analytics.spatial import SpatialAnalytics
        spatial = SpatialAnalytics(con)
        nearby = spatial.get_nearby_projects(args.project_id, radius_km=args.radius)
        if "error" in nearby:
            print(f"[ERROR] {nearby['error']}")
            return
        print(f"\n=== Micro-Market Geospatial Radius Analysis for {nearby['origin_name']} (ID {args.project_id}) ===")
        print(f"Search Radius: {nearby['radius_km']} km | Nearby Registered Projects: {nearby['nearby_count']}")
        if nearby["micro_market_avg_rate_sqft"]:
            print(f"Micro-Market Benchmark Average Rate: Rs. {nearby['micro_market_avg_rate_sqft']:,.0f} / sq.ft")
        print(f"Nearby Projects Behind Schedule (< 0.75x velocity): {nearby['delayed_projects_count']} ({nearby['delayed_project_ratio']*100:.0f}%)")
        print("\nNearby Projects Breakdown:")
        for p in nearby["nearby_projects"][:10]:
            rate_s = f"Rs. {p['avg_registered_rate_sqft']:,.0f}/sqft" if p['avg_registered_rate_sqft'] else "No Sales"
            print(f"  * {p['name']} ({p['distance_km']} km away) - {rate_s} | Vel: {p['velocity_ratio'] or 'N/A'}x | Sold: {p['booking_rate_pct'] or 0}%")
    finally:
        con.close()


def cmd_docworker(args):
    con = get_connection(Path(args.db))
    try:
        from .documents.worker import DocumentWorker
        worker = DocumentWorker(con)
        print("\n=== DocumentWorker Asynchronous Job Queue ===")
        print("Queue Status Before:", worker.get_queue_status())
        res = worker.process_batch(max_jobs=args.batch_size)
        print(f"Batch Execution Result: Processed {res['processed']} | Completed {res['completed']} | Failed {res['failed']}")
        print("Queue Status After:", worker.get_queue_status())
    finally:
        con.close()


def cmd_ml_price(args):
    con = get_connection(Path(args.db))
    try:
        from .analytics.ml_pricing import HedonicPricingModel
        model = HedonicPricingModel(n_estimators=args.estimators, max_depth=args.depth)
        model.train_from_db(con)

        p_row = con.execute(
            """
            SELECT p.name, p.district, p.latitude, p.longitude, p.latest_form_one_progress_pct,
                   p.velocity_ratio, pr.total_projects_claimed
            FROM projects p
            LEFT JOIN promoters pr ON p.promoter_id = pr.promoter_id
            WHERE p.project_id = ?
            """,
            (args.project_id,),
        ).fetchone()

        if not p_row:
            print(f"[ERROR] Project {args.project_id} not found in database.")
            return

        p_dict = {
            "district": p_row["district"],
            "latitude": p_row["latitude"],
            "longitude": p_row["longitude"],
            "latest_form_one_progress_pct": p_row["latest_form_one_progress_pct"],
            "velocity_ratio": p_row["velocity_ratio"],
            "total_projects_claimed": p_row["total_projects_claimed"],
        }
        u_dict = {
            "asset_class": args.asset_class,
            "carpet_area_sqft": args.carpet_area,
        }
        feats = model.extract_features(u_dict, p_dict)
        exp = model.explain(feats)

        print(f"\n=== Interpretable Hedonic ML Pricing Valuation: {p_row['name']} (ID {args.project_id}) ===")
        print(f"Asset Class: {args.asset_class} | Carpet Area: {args.carpet_area:,.1f} sq.ft")
        print(f"Predicted Valuation Rate: Rs. {exp['predicted_rate_per_sqft']:,.2f} / sq.ft")
        print(f"Base Market Average:      Rs. {exp['base_market_average_inr']:,.2f} / sq.ft")
        spread = exp["net_spread_from_average"]
        sign = "+" if spread >= 0 else "-"
        print(f"Net Micro-Market Spread:  {sign}Rs. {abs(spread):,.2f} / sq.ft")
        print(f"Total Valuation Estimate: Rs. {exp['predicted_rate_per_sqft'] * args.carpet_area:,.0f}")

        print("\nTop Positive Feature Drivers (Premiums):")
        for p in exp["top_positive_premiums"]:
            print(f"  + {p['feature']}: +Rs. {p['impact_inr_per_sqft']:,.1f}/sqft")

        print("\nTop Negative Feature Drivers (Discounts):")
        for n in exp["top_negative_discounts"]:
            print(f"  - {n['feature']}: -Rs. {abs(n['impact_inr_per_sqft']):,.1f}/sqft")

        print(f"\nSHAP Additive Efficiency Check: {'PASSED (Exact)' if exp['efficiency_check_passed'] else 'FAILED'}")
    finally:
        con.close()


def cmd_survival(args):
    con = get_connection(Path(args.db))
    try:
        from .analytics.survival import CompletionDelaySurvivalModel
        model = CompletionDelaySurvivalModel()
        model.train_from_db(con)

        c_index = model.calculate_concordance_index()
        print(f"\n=== Completion Delay Survival Model (Harrell C-Index: {c_index:.3f}) ===")

        if args.project_id:
            pids = [args.project_id]
        else:
            pids = [r[0] for r in con.execute("SELECT project_id FROM projects ORDER BY project_id").fetchall()]

        for pid in pids:
            fc = model.forecast_project_by_id(con, pid)
            print(f"\nProject: {fc['project_name']} (ID {pid})")
            print(f"  RERA Registered Timeline: {fc['scheduled_start_date']} -> {fc['registered_completion_date']} ({fc['scheduled_duration_months']} mo)")
            print(f"  Delivery Risk Category:   [{fc['delay_risk_label']}]")
            print(f"  Forecasted Delay:         {fc['forecasted_delay_months']} months")
            print(f"  Relative Hazard Ratio:    {fc['hazard_ratio']}x")
            print(f"  Assessment:               {fc['confidence_assessment']}")
            dates = fc["forecasted_handover_dates"]
            print("  Handover Percentiles:")
            print(f"    - p50 (Median Completion):        {dates['p50_median_expected_date']} ({dates['p50_duration_months']} mo)")
            print(f"    - p75 (Conservative Estimate):   {dates['p75_conservative_date']} ({dates['p75_duration_months']} mo)")
            print(f"    - p90 (High-Confidence Horizon): {dates['p90_high_confidence_date']} ({dates['p90_duration_months']} mo)")
    finally:
        con.close()


def cmd_eval(args):
    try:
        from tests.eval_harness import EvaluationHarness
    except ImportError:
        from real_estate_intelligence.tests.eval_harness import EvaluationHarness

    harness = EvaluationHarness(Path(args.db))
    try:
        print("\n=======================================================")
        print("  GujRERA AI/ML & Agent Evaluation Benchmark Harness   ")
        print("=======================================================\n")
        report = harness.run_full_suite()
        print(json.dumps(report, indent=2))
    finally:
        harness.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Real Estate Intelligence Platform (GujRERA)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest raw pipeline files into typed facts, FTS5, and Knowledge Graph")
    p_ingest.add_argument("--source", default=str(DEFAULT_SOURCE_RUN), help="Source run directory containing raw data")
    p_ingest.add_argument("--target", default=str(DEFAULT_DB_PATH), help="Target SQLite database path")
    p_ingest.set_defaults(func=cmd_ingest)

    # Dossier
    p_dossier = subparsers.add_parser("dossier", help="Generate an institutional due-diligence dossier")
    p_dossier.add_argument("--project-id", type=int, required=True, help="GujRERA project ID")
    p_dossier.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_dossier.add_argument("--output", help="Optional output markdown file path")
    p_dossier.set_defaults(func=cmd_dossier)

    # Pricing
    p_price = subparsers.add_parser("pricing", help="Analyze unit-level registered transaction rates and price benchmarks")
    p_price.add_argument("--project-id", type=int, required=True, help="GujRERA project ID")
    p_price.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_price.set_defaults(func=cmd_pricing)

    # Claims Verifier
    p_claims = subparsers.add_parser("claims", help="Fact-check broker sales claims against statutory RERA filings")
    p_claims.add_argument("--project-id", type=int, required=True, help="GujRERA project ID")
    p_claims.add_argument("--claimed-rate", type=float, help="Claimed rate per sq.ft (e.g. 7500)")
    p_claims.add_argument("--claimed-sold", type=float, help="Claimed percentage sold out (e.g. 90)")
    p_claims.add_argument("--claimed-date", help="Promised handover date (YYYY-MM-DD)")
    p_claims.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_claims.set_defaults(func=cmd_claims)

    # Search
    p_search = subparsers.add_parser("search", help="Hybrid document search over all signed PDFs")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--project-id", type=int, help="Optional project ID filter")
    p_search.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_search.add_argument("--limit", type=int, default=5, help="Result limit")
    p_search.set_defaults(func=cmd_search)

    # Network
    p_net = subparsers.add_parser("network", help="Trace professional and promoter entity network")
    p_net.add_argument("--project-id", type=int, required=True, help="GujRERA project ID")
    p_net.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_net.set_defaults(func=cmd_network)

    # Audit
    p_audit = subparsers.add_parser("audit", help="Audit statutory commitments and cost drops")
    p_audit.add_argument("--project-id", type=int, help="Optional specific project ID to audit")
    p_audit.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_audit.set_defaults(func=cmd_audit)

    # Serve Dashboard
    p_serve = subparsers.add_parser("serve", help="Launch interactive web dashboard terminal")
    p_serve.add_argument("--port", type=int, default=8000, help="Web server port (default 8000)")
    p_serve.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_serve.set_defaults(func=cmd_serve)

    # Runway
    p_runway = subparsers.add_parser("runway", help="Calculate construction cash burn rate and escrow runway")
    p_runway.add_argument("--project-id", type=int, required=True, help="GujRERA project ID")
    p_runway.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_runway.set_defaults(func=cmd_runway)

    # Spatial
    p_spatial = subparsers.add_parser("spatial", help="Analyze micro-market radius and spatial neighborhood benchmarks")
    p_spatial.add_argument("--project-id", type=int, required=True, help="Origin GujRERA project ID")
    p_spatial.add_argument("--radius", type=float, default=3.0, help="Radius in kilometers (default 3.0)")
    p_spatial.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_spatial.set_defaults(func=cmd_spatial)

    # DocWorker
    p_worker = subparsers.add_parser("docworker", help="Process queued background document OCR/indexing jobs")
    p_worker.add_argument("--batch-size", type=int, default=10, help="Max jobs to process (default 10)")
    p_worker.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_worker.set_defaults(func=cmd_docworker)

    # ML Hedonic Pricing
    p_ml = subparsers.add_parser("ml-price", help="Predict unit valuation and exact SHAP feature breakdown via GBDT")
    p_ml.add_argument("--project-id", type=int, required=True, help="GujRERA project ID")
    p_ml.add_argument("--asset-class", default="Residential", choices=["Residential", "Commercial_Office", "Commercial_Retail", "Industrial_Warehouse"], help="Asset class segment")
    p_ml.add_argument("--carpet-area", type=float, default=1200.0, help="Carpet area in sq.ft (default 1200.0)")
    p_ml.add_argument("--estimators", type=int, default=25, help="Number of boosting trees (default 25)")
    p_ml.add_argument("--depth", type=int, default=3, help="Max tree depth (default 3)")
    p_ml.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_ml.set_defaults(func=cmd_ml_price)

    # Survival Analysis
    p_surv = subparsers.add_parser("survival", help="Forecast project handover completion dates and delay percentiles")
    p_surv.add_argument("--project-id", type=int, help="Optional specific GujRERA project ID")
    p_surv.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_surv.set_defaults(func=cmd_survival)

    # Eval Harness
    p_eval = subparsers.add_parser("eval", help="Execute automated AI/ML and agent factuality evaluation harness")
    p_eval.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    p_eval.set_defaults(func=cmd_eval)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
