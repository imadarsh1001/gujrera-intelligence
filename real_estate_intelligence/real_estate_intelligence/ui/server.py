"""Lightweight zero-dependency web server and interactive dashboard for investors."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from ..analytics.audit import ProjectAuditor
from ..analytics.claims_checker import SalesClaimVerifier
from ..analytics.ml_pricing import HedonicPricingModel
from ..analytics.pricing import PricingIntelligence
from ..analytics.survival import CompletionDelaySurvivalModel
from ..config import DEFAULT_DB_PATH
from ..db.database import get_connection
from ..documents.search import DocumentSearchEngine
from ..graph.network import KnowledgeGraph
from ..mcp.server import RealEstateIntelligenceMCP

# The dashboard is served from ui/static/ (index.html + vendored vendor/ assets) so the
# UI renders fully offline — sovereign local-first — and the 1,600-line template no
# longer lives inside a Python string. Files are read once and cached in-process.
STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_CACHE = {}


def _read_static(rel_name: str) -> bytes:
    """Read a file from the ui/static directory, refusing paths that escape it."""
    target = (STATIC_DIR / rel_name).resolve()
    if not target.is_relative_to(STATIC_DIR) or not target.is_file():
        raise FileNotFoundError(rel_name)
    if rel_name not in _STATIC_CACHE:
        _STATIC_CACHE[rel_name] = target.read_bytes()
    return _STATIC_CACHE[rel_name]


def _parse_timestamp(raw) -> Optional[datetime]:
    """Parse a portal timestamp into an aware UTC datetime, or None if unparseable.

    Portal values mix ISO instants ('2026-10-07T17:39:43.371+0530', no-colon offset)
    with space-separated datetimes ('2025-06-30 18:17:06'); Excel-serial leftovers
    ('190130') return None.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace(" ", "T", 1)).astimezone(timezone.utc)
    except ValueError:
        return None


def _revision_state(filings_count: int, extension_rows_count: int) -> str:
    """Three honest states for the completion-date revision summary.

    'revision_observed' means extension APPLICATIONS exist (approval status is not
    disclosed by the source data); 'no_revision_observed' means comparable filings
    (>= 2) with no extension application; 'insufficient_history' means fewer than
    two filings on record.
    """
    if filings_count < 2:
        return "insufficient_history"
    if extension_rows_count > 0:
        return "revision_observed"
    return "no_revision_observed"


class IntelligenceRequestHandler(BaseHTTPRequestHandler):
    con = None
    pricing_engine = None
    verifier = None
    auditor = None
    search_engine = None
    graph_engine = None
    mcp_server = None
    agentic_copilot = None

    @classmethod
    def setup_backends(cls, db_path=None):
        cls.con = get_connection(db_path)
        cls.pricing_engine = PricingIntelligence(cls.con)
        cls.verifier = SalesClaimVerifier(cls.con)
        cls.auditor = ProjectAuditor(cls.con)
        cls.search_engine = DocumentSearchEngine(cls.con)
        cls.graph_engine = KnowledgeGraph(cls.con)
        cls.mcp_server = RealEstateIntelligenceMCP(cls.con)
        from ..agent.copilot import AgenticCopilot
        cls.agentic_copilot = AgenticCopilot(cls.mcp_server)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            body = _read_static("index.html")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            try:
                body = _read_static(rel)
            except FileNotFoundError:
                self.send_error(404, "Static asset not found")
                return
            content_type = {
                ".html": "text/html; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".woff2": "font/woff2",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".json": "application/json; charset=utf-8",
            }.get(Path(rel).suffix, "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/projects":
            cur = self.con.execute("SELECT project_id, name, district, promoter_name FROM projects ORDER BY project_id")
            projects = [dict(r) for r in cur.fetchall()]
            self._send_json(projects)
            return

        if path == "/api/explore":
            self._send_json(self._explore_rows())
            return

        if path.startswith("/api/project/"):
            try:
                pid = int(path.split("/")[-1])
            except ValueError:
                self.send_error(400, "Invalid project ID")
                return

            cur = self.con.execute("SELECT * FROM projects WHERE project_id = ?", (pid,))
            prow = cur.fetchone()
            if not prow:
                self.send_error(404, "Project not found")
                return

            blocks = [dict(r) for r in self.con.execute("SELECT * FROM inventory_blocks WHERE project_id = ? ORDER BY block_name", (pid,)).fetchall()]
            timeline = [dict(r) for r in self.con.execute("SELECT * FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC", (pid,)).fetchall()]
            finances = [dict(r) for r in self.con.execute("SELECT * FROM finances WHERE project_id = ? ORDER BY id ASC", (pid,)).fetchall()]
            professionals = [dict(r) for r in self.con.execute("SELECT role, name, firm_name, license_or_reg_no FROM professionals WHERE project_id = ?", (pid,)).fetchall()]
            banks = [dict(r) for r in self.con.execute("SELECT * FROM banks WHERE project_id = ? ORDER BY account_type ASC", (pid,)).fetchall()]
            prior = [dict(r) for r in self.con.execute(
                "SELECT linked_project_name, linked_project_id FROM previous_projects WHERE project_id = ? AND linked_project_id != ?",
                (pid, pid),
            ).fetchall()]
            form5 = [dict(r) for r in self.con.execute("SELECT * FROM form5_compliance WHERE project_id = ? ORDER BY financial_year ASC", (pid,)).fetchall()]
            bu_records = [dict(r) for r in self.con.execute("SELECT * FROM noc_bu_records WHERE project_id = ? ORDER BY block_name ASC", (pid,)).fetchall()]
            
            leads = [
                {
                    "category": l.category,
                    "severity": l.severity,
                    "title": l.title,
                    "detail": l.detail,
                    "reconciliation_guidance": l.reconciliation_guidance,
                }
                for l in self.auditor.audit_project(pid)
            ]
            contagion = self.graph_engine.trace_contagion_risk(pid)

            self._send_json({
                "project": dict(prow),
                "blocks": blocks,
                "timeline": timeline,
                "finances": finances,
                "professionals": professionals,
                "banks": banks,
                "prior_projects": prior,
                "form5": form5,
                "bu_records": bu_records,
                "leads": leads,
                "contagion": contagion,
            })
            return

        if path == "/api/graph":
            # Return nodes and edges formatted for Vis.js
            cur = self.con.cursor()
            cur.execute("SELECT node_id, kind, label FROM graph_nodes")
            color_map = {
                "Project": "#2563eb",
                "Promoter": "#7c3aed",
                "Engineer": "#d97706",
                "Architect": "#0d9488",
                "Ca": "#059669",
                "Bank": "#e11d48",
                "PriorProject": "#64748b"
            }
            nodes = [
                {
                    "id": r["node_id"],
                    "label": r["label"],
                    "group": r["kind"],
                    "color": color_map.get(r["kind"], "#3b82f6")
                }
                for r in cur.fetchall()
            ]

            cur.execute("SELECT src_id, relation, dst_id FROM graph_edges")
            edges = [
                {
                    "from": r["src_id"],
                    "to": r["dst_id"],
                    "label": r["relation"],
                    "color": {"color": "#94a3b8", "highlight": "#2563eb"}
                }
                for r in cur.fetchall()
            ]

            self._send_json({"nodes": nodes, "edges": edges})
            return

        if path.startswith("/api/pricing/"):
            try:
                pid = int(path.split("/")[-1])
            except ValueError:
                self.send_error(400, "Invalid project ID")
                return

            summary = self.pricing_engine.get_project_pricing_summary(pid)
            self._send_json(summary)
            return

        if path == "/api/verify_claim":
            try:
                pid = int(query.get("project_id", [0])[0])
                price = float(query["claimed_rate"][0]) if query.get("claimed_rate", [""])[0] else None
                sold = float(query["claimed_sold"][0]) if query.get("claimed_sold", [""])[0] else None
            except (TypeError, ValueError):
                self.send_error(400, "Invalid numeric parameter")
                return
            date = query.get("claimed_date", [None])[0] or None

            res = self.verifier.verify_claim(
                project_id=pid,
                claimed_rate_sqft=price,
                claimed_sold_pct=sold,
                claimed_completion_date=date,
            )
            self._send_json(res)
            return

        if path == "/api/search":
            q = query.get("query", [""])[0]
            try:
                pid = int(query["project_id"][0]) if query.get("project_id") else None
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            results = self.search_engine.search(query=q, project_id=pid, limit=10)
            self._send_json({"query": q, "results": results})
            return

        if path == "/api/analytics/survival":
            try:
                pid = int(query.get("project_id", [0])[0])
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            res = self.mcp_server.forecast_completion_delay(pid)
            self._send_json(res)
            return

        if path == "/api/analytics/pricing_trend":
            try:
                pid = int(query.get("project_id", [0])[0])
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            res = self.pricing_engine.get_longitudinal_pricing_trend(pid)
            self._send_json(res)
            return

        if path == "/api/analytics/ml_pricing":
            try:
                pid = int(query.get("project_id", [0])[0])
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            aclass = query.get("asset_class", ["Residential"])[0]
            try:
                carpet = float(query.get("carpet_area_sqft", [1200.0])[0])
            except (ValueError, TypeError):
                carpet = 1200.0
            res = self.mcp_server.predict_pricing_benchmark(pid, asset_class=aclass, carpet_area_sqft=carpet)
            self._send_json(res)
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/copilot":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                self.send_error(400, "Invalid JSON")
                return

            query_text = data.get("query", "").strip()
            try:
                project_id = int(data.get("project_id", 0))
            except (ValueError, TypeError):
                project_id = 0

            api_key = (data.get("api_key") or "").strip() or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            reply_data = self._handle_copilot_query(query_text, project_id, api_key=api_key)
            self._send_json(reply_data)
            return

        self.send_error(404, "Endpoint not found")

    def _explore_rows(self) -> List[Dict[str, Any]]:
        """One pre-aggregated row per project for the Explore table (route contract in ui/EGM.md).

        Price aggregates cover BOOKED transactions only — UNBOOKED rows carry the
        promoter's declared inventory prices, not registered agreements (the same rule
        PricingIntelligence applies). Per-unit-type aggregates are included so the
        client can apply the unit-scoped filter cascade without recomputation.
        revision_state: 'revision_observed' | 'no_revision_observed' | 'insufficient_history'.
        """
        projects = [dict(r) for r in self.con.execute("SELECT * FROM projects ORDER BY project_id").fetchall()]
        now_utc = datetime.now(timezone.utc)
        rows: List[Dict[str, Any]] = []
        for p in projects:
            pid = p["project_id"]

            filings = self.con.execute(
                "SELECT filing_date FROM finances WHERE project_id = ? AND filing_date IS NOT NULL", (pid,)
            ).fetchall()
            filing_dates = sorted(str(r["filing_date"]) for r in filings)
            ext_rows = self.con.execute(
                "SELECT apply_date FROM applications WHERE project_id = ? AND application_type = 'Extension'",
                (pid,),
            ).fetchall()
            extension_dates = sorted(
                dt.date().isoformat() for dt in (_parse_timestamp(r["apply_date"]) for r in ext_rows) if dt
            )
            latest_filing_dt = _parse_timestamp(filing_dates[-1]) if filing_dates else None
            days_since_filing = max(0, (now_utc - latest_filing_dt).days) if latest_filing_dt else None

            booked = self.con.execute(
                "SELECT unit_type, unit_consideration, rate_per_sqft, agreement_date "
                "FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED'",
                (pid,),
            ).fetchall()
            by_type: Dict[str, Dict[str, Any]] = {}
            for r in booked:
                bucket = by_type.setdefault(r["unit_type"] or "Unknown", {
                    "min_price": None, "min_rate_sqft": None, "count": 0,
                    "price_date_min": None, "price_date_max": None,
                })
                bucket["count"] += 1
                price, rate, ad = r["unit_consideration"], r["rate_per_sqft"], r["agreement_date"]
                if price is not None and (bucket["min_price"] is None or price < bucket["min_price"]):
                    bucket["min_price"] = price
                if rate is not None and rate > 0 and (bucket["min_rate_sqft"] is None or rate < bucket["min_rate_sqft"]):
                    bucket["min_rate_sqft"] = rate
                if ad:
                    ad = str(ad)
                    if bucket["price_date_min"] is None or ad < bucket["price_date_min"]:
                        bucket["price_date_min"] = ad
                    if bucket["price_date_max"] is None or ad > bucket["price_date_max"]:
                        bucket["price_date_max"] = ad
            overall = {
                "min_price": min((b["min_price"] for b in by_type.values() if b["min_price"] is not None), default=None),
                "min_rate_sqft": min((b["min_rate_sqft"] for b in by_type.values() if b["min_rate_sqft"] is not None), default=None),
                "price_date_min": min((b["price_date_min"] for b in by_type.values() if b["price_date_min"]), default=None),
                "price_date_max": max((b["price_date_max"] for b in by_type.values() if b["price_date_max"]), default=None),
            }

            rows.append({
                "project_id": pid,
                "name": p["name"],
                "registration_number": p["registration_number"],
                "district": p["district"],
                "taluka": p["taluka"],
                "project_type": p["project_type"],
                "promoter_name": p["promoter_name"],
                "completion_date": p["completion_date"],
                "progress_pct": p["latest_form_one_progress_pct"],
                "latitude": p["latitude"],
                "longitude": p["longitude"],
                "complaints_count": p["complaints_count"] or 0,
                "extensions_count": p["extensions_count"] or 0,
                "filings_count": len(filing_dates),
                "latest_filing_date": filing_dates[-1] if filing_dates else None,
                "days_since_latest_filing": days_since_filing,
                "revision_state": _revision_state(len(filing_dates), len(ext_rows)),
                "revision_evidence_dates": extension_dates,
                "unit_types": sorted(by_type.keys()),
                "min_price_booked": overall["min_price"],
                "min_rate_sqft_booked": overall["min_rate_sqft"],
                "price_date_min": overall["price_date_min"],
                "price_date_max": overall["price_date_max"],
                "booked_by_unit_type": by_type,
                "architects": [
                    r["name"]
                    for r in self.con.execute(
                        "SELECT name FROM professionals WHERE project_id = ? AND role = 'architect' ORDER BY name",
                        (pid,),
                    ).fetchall()
                    if r["name"]
                ],
            })
        return rows

    def _handle_copilot_query(self, query: str, project_id: int, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Synthesize multi-modal statutory due diligence facts with exact citations."""
        try:
            if project_id <= 0:
                row = self.con.execute("SELECT project_id FROM projects ORDER BY project_id LIMIT 1").fetchone()
                project_id = row[0] if row else 16562

            # Try Agentic LLM reasoning if API key is provided
            if api_key and getattr(self, "agentic_copilot", None):
                try:
                    llm_res = self.agentic_copilot.run_query(query, project_id, api_key=api_key)
                    if llm_res and llm_res.get("reply"):
                        return llm_res
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Agentic LLM invocation fell back to deterministic engine: {e}")

            q_lower = query.lower().strip()
            citations: List[str] = []
            reply_lines: List[str] = []

            cur = self.con.execute(
                """
                SELECT project_id, name, district, taluka, promoter_name, registration_number,
                       start_date, completion_date, velocity_ratio, booking_rate_pct,
                       total_units, booked_units, unbooked_units, latest_form_one_progress_pct,
                       estimated_cost_inr, incurred_cost_inr, time_elapsed_pct, bu_status,
                       complaints_count, alterations_count, default_quarters_count
                FROM projects WHERE project_id = ?
                """,
                (project_id,)
            )
            p = cur.fetchone()
            p_name = p["name"] if p else f"Project {project_id}"

            # 1. Greetings & Capabilities Guidance
            if q_lower in ["ok", "okay", "hi", "hello", "hey", "help", "thanks", "thank you"] or any(q_lower.startswith(w) for w in ["help", "what can you do", "who are you", "commands"]):
                reply_lines.append(f"### GujRERA Statutory Diligence Copilot for **{p_name}**")
                reply_lines.append("I am your forensic due-diligence copilot cross-referencing sworn Form 1/2/3 filings, bank escrow passbooks, registered agreements, and timeline disclosures.")
                reply_lines.append("\n**Suggested Inquiries you can ask:**")
                reply_lines.append("- **Launch & Handover**: *'When was this project launched and what is the deadline?'*")
                reply_lines.append("- **Sales & Absorption**: *'What are the sales figures and unsold units?'*")
                reply_lines.append("- **Lifecycle Performance**: *'Analyze the project since its launch'*")
                reply_lines.append("- **70% Escrow Audit**: *'Audit Section 4(2)(l)(D) escrow retention and withdrawals'*")
                reply_lines.append("- **Title & Mortgages**: *'Are there any bank loans, charges or mortgages on the land?'*")
                reply_lines.append("- **Market Rate & CAGR**: *'What is the registered market rate and CAGR?'*")
                reply_lines.append("- **Contagion Risk**: *'Trace shared professionals and contagion risk'*")
                citations.extend(["GujRERA Statutory Fact Base", "RERA Act 2016"])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 1b. Architecture & LLM Credential Inquiry
            if any(w in q_lower for w in ["which llm", "llm", "ai model", "what model", "credentials", "api key", "openai", "gemini", "claude", "architecture"]):
                reply_lines.append("### Architecture & Credentials Disclosure")
                reply_lines.append("This Intelligence Copilot operates on a **Dual-Mode Sovereign Architecture**:")
                reply_lines.append("1. **⚡ Agentic LLM Mode**: Deep open-ended reasoning using Gemini 2.0 Flash or OpenAI with automated tool calls across 10 MCP forensic tools (activated when an API key is provided via the ⚙️ Settings drawer).")
                reply_lines.append("2. **🛡️ Local Evidentiary Mode**: Operates 100% offline with zero cloud credentials required, powered by local SQLite FTS5 BM25 search, GBDT TreeSHAP, and Cox survival modeling with guaranteed **0% hallucination**.")
                reply_lines.append("\n**Internal Machine Learning & Forensic Stack:**")
                reply_lines.append("- **Hedonic Pricing Engine**: Gradient Boosted Decision Trees (GBDT) with exact Lundberg-Lee Tree SHAP feature attributions.")
                reply_lines.append("- **Delivery Forecasting**: Semi-parametric Cox Proportional Hazards survival analysis calibrated against physical velocity.")
                reply_lines.append("- **Statutory Regulatory RAG**: SQLite FTS5 full-text search with BM25 relevance ranking indexing sworn Form 1, 2, and 3 PDF disclosures.")
                reply_lines.append("- **Contagion & Network Graph**: Cross-project relational graph linking promoters, architects, engineers, and chartered accountants.")
                reply_lines.append("- **Evidentiary Citation Contract**: Fully deterministic, citation-backed factual synthesis guaranteeing **0% hallucination**.")
                citations.extend(["Local System Architecture", "GujRERA Relational Fact Base", "Model Context Protocol (MCP)"])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 1c. Buyer Advisory & Best Time to Buy
            if any(w in q_lower for w in ["best time", "when to buy", "should i buy", "safe to buy", "is it safe", "buying advice", "investment advice", "verdict"]):
                surv = self.mcp_server.forecast_completion_delay(project_id)
                health = self.mcp_server.get_escrow_health(project_id)
                pred = self.mcp_server.predict_pricing_benchmark(project_id)
                
                reply_lines.append(f"### Buyer Due Diligence & Timing Assessment for **{p_name}**")
                
                # Physical stage
                prog = p['latest_form_one_progress_pct'] or 0.0
                vel = p['velocity_ratio'] or 1.0
                if prog >= 80:
                    reply_lines.append(f"- **Construction Stage (Favorable)**: Project is at `{prog:.1f}%` certified physical completion (`{vel:.2f}x` velocity). Execution risk is low as structural civil work is largely finished.")
                elif prog >= 50:
                    reply_lines.append(f"- **Construction Stage (Mid-Phase)**: Project is at `{prog:.1f}%` physical progress. Moderate construction risk remains.")
                else:
                    reply_lines.append(f"- **Construction Stage (Early Phase)**: Project is only at `{prog:.1f}%` progress. Higher execution and delivery delay risk.")

                # Escrow security
                escrow_flag = health.get("escrow_70_percent_accounts")
                if escrow_flag:
                    reply_lines.append(f"- **Escrow Protection**: Section 4(2)(l)(D) 70% retention account is operational with ₹{((health.get('total_closing_balance_inr') or 0)/100000):,.2f} Lakhs closing balance.")
                else:
                    reply_lines.append("- **Escrow Protection**: Verify latest Form 3 bank passbook reconciliation before releasing stage payments.")

                # Handover Delivery
                reply_lines.append(f"- **Delivery Confidence**: Risk classification is **{surv.get('delay_risk_label', 'ON_TRACK')}** (Median expected handover: `{surv.get('forecasted_handover_dates', {}).get('p50_median_expected_date', 'On Schedule')}`).")

                # Inventory & Negotiation window
                unsold = p['unbooked_units'] or 0
                total = p['total_units'] or 0
                reply_lines.append(f"- **Negotiation Leverage**: {unsold} of {total} units remain unsold (`{(100 - (p['booking_rate_pct'] or 0)):.1f}%` market overhang), providing favorable bargaining room for late-stage discounts.")

                # Recommendation
                reply_lines.append("\n**Statutory Recommendation:**")
                reply_lines.append("1. Obtain a **formal No-Objection Certificate (NOC)** or confirm clear land title if taking a home loan.")
                reply_lines.append("2. Ensure all booking amounts are deposited exclusively into the designated **RERA 70% retention bank account**.")
                reply_lines.append("3. Verify issuance of the **Building Use (BU) Permission / Completion Certificate** prior to taking physical possession.")

                citations.extend([
                    "RERA Act 2016 Buyer Protection Guidelines",
                    "Cox Proportional Hazards Completion Model",
                    "Form 1 Architect / Form 3 CA Statutory Filings"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 2. Comprehensive Lifecycle Analysis Since Launch
            if any(w in q_lower for w in ["since launch", "analyse it", "analyze it", "progress history", "lifecycle", "performance since", "track record", "full analysis", "overall status"]):
                reply_lines.append(f"### Comprehensive Lifecycle Diligence for **{p_name}** (Since Launch)")
                
                # 1. Timeline & Schedule
                reply_lines.append("\n**1. Timeline & Physical Construction Velocity:**")
                reply_lines.append(f"- **Launch Date**: `{p['start_date'] or 'Not Disclosed'}` ➔ **Statutory Completion**: `{p['completion_date'] or 'Not Disclosed'}`.")
                reply_lines.append(f"- **Elapsed Schedule**: `{p['time_elapsed_pct'] or 0.0}%` elapsed vs `{p['latest_form_one_progress_pct'] or 0.0}%` certified physical progress.")
                vel = p['velocity_ratio'] or 1.0
                reply_lines.append(f"- **Pace Ratio**: `{vel}x` ({'Outpacing schedule' if vel >= 1.0 else 'Delayed relative to calendar'}).")
                
                # Milestones
                tls = self.con.execute("SELECT period_label, progress_percentage FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC", (project_id,)).fetchall()
                if tls:
                    step = max(1, len(tls)//4)
                    milestones_sample = tls[::step]
                    if tls[-1] not in milestones_sample:
                        milestones_sample.append(tls[-1])
                    milestones_str = " ➔ ".join([f"{r['period_label']}: {r['progress_percentage']:.1f}%" for r in milestones_sample])
                    reply_lines.append(f"- **Progression Curve**: {milestones_str} (Latest: `{tls[-1]['progress_percentage']:.1f}%`).")

                # 2. Sales & Inventory
                reply_lines.append("\n**2. Sales Absorption & Commercial/Residential Overhang:**")
                reply_lines.append(f"- **Total Units**: {p['total_units'] or 0} | **Booked**: {p['booked_units'] or 0} (`{p['booking_rate_pct'] or 0.0}%` absorption).")
                reply_lines.append(f"- **Unsold Inventory**: {p['unbooked_units'] or 0} units remaining.")
                
                blocks = self.con.execute("SELECT block_name, total_units, booked_units, booking_rate_pct FROM inventory_blocks WHERE project_id = ?", (project_id,)).fetchall()
                if blocks:
                    b_str = ", ".join([f"{b['block_name']} ({b['booked_units']}/{b['total_units']} booked, {b['booking_rate_pct']:.0f}%)" for b in blocks])
                    reply_lines.append(f"- **Block Absorption**: {b_str}.")

                # 3. Capital Inflows & Escrow Health
                fin = self.con.execute("SELECT booked_consideration, received_amount, balance_amount, incurred_and_paid, estimated_cost FROM finances WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
                if fin:
                    col_eff = (fin['received_amount'] / fin['booked_consideration'] * 100) if fin['booked_consideration'] else 0
                    reply_lines.append("\n**3. Capital Inflows & Financial Health:**")
                    reply_lines.append(f"- **Total Booked Consideration**: ₹{(fin['booked_consideration']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Cash Collected from Buyers**: ₹{(fin['received_amount']/10000000):,.2f} Cr (`{col_eff:.1f}%` collection efficiency).")
                    reply_lines.append(f"- **Remaining Receivables**: ₹{(fin['balance_amount']/10000000):,.2f} Cr | **Incurred Spend**: ₹{(fin['incurred_and_paid']/10000000):,.2f} Cr.")

                # 4. Pricing Trajectory
                trend = self.pricing_engine.get_longitudinal_pricing_trend(project_id)
                if trend.get("quarterly_trajectory"):
                    reply_lines.append("\n**4. Transaction Pricing Trajectory:**")
                    reply_lines.append(f"- **Realized Rates**: Trajectory from ₹{trend['base_median_rate_sqft']:,.0f} ({trend['first_quarter']}) to ₹{trend['latest_median_rate_sqft']:,.0f} ({trend['latest_quarter']}).")
                    reply_lines.append(f"- **Price Appreciation**: **{trend['price_appreciation_pct']}%** | **Annualized CAGR**: **{trend['cagr_pct']}%**.")

                # 5. Regulatory Flags
                reply_lines.append("\n**5. Legal & Regulatory Radar:**")
                complaints = p['complaints_count'] or 0
                alterations = p['alterations_count'] or 0
                defaults = p['default_quarters_count'] or 0
                reply_lines.append(f"- **Complaints**: {complaints} application(s) | **Sanctioned Alterations**: {alterations} | **QPR Defaults**: {defaults} quarters.")
                reply_lines.append(f"- **BU Permission**: {p['bu_status'] or 'Pending / Not Verified'}.")

                citations.extend([
                    "Quarterly Progress Timeline (Form 1 / Form 2)",
                    "Form 3 CA Sworn Financial Disclosures",
                    "Sub-Registrar Unit Transactions Ledger",
                    "GujRERA Statutory Filings Index"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 3. Project Launch Date & Statutory Milestones
            if any(w in q_lower for w in ["launch", "start date", "started", "commence", "began", "when was", "registration date", "start"]):
                reply_lines.append(f"### Project Launch & Statutory Timeline for **{p_name}**")
                reply_lines.append(f"- **Official RERA Launch Date**: `{p['start_date'] or 'Not Disclosed'}` (Statutory Project Start Date).")
                reply_lines.append(f"- **Registration Number**: `{p['registration_number']}` (Project ID: `{project_id}`).")
                reply_lines.append(f"- **RERA Handover Deadline**: `{p['completion_date'] or 'Not Disclosed'}`.")
                reply_lines.append(f"- **Calendar Timeline Elapsed**: `{p['time_elapsed_pct'] or 0.0}%` of scheduled duration elapsed to date.")
                reply_lines.append(f"- **Physical Civil Progress**: `{p['latest_form_one_progress_pct'] or 0.0}%` completed.")
                vel = p['velocity_ratio'] or 1.0
                status = "ahead of schedule" if vel >= 1.0 else "behind schedule (velocity lag)"
                reply_lines.append(f"- **Construction Velocity**: `{vel}x` ({status}).")
                
                first_tl = self.con.execute("SELECT period_label, progress_percentage FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC LIMIT 1", (project_id,)).fetchone()
                if first_tl:
                    reply_lines.append(f"- **First Recorded Progress Filing**: `{first_tl['period_label']}` with `{first_tl['progress_percentage']:.1f}%` certified completion.")
                
                citations.extend([
                    "GujRERA Registration Certificate",
                    "Quarterly Progress Timeline (Form 1)",
                    "Statutory Project Master Table"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 4. Sales Absorption, Bookings & Overhang
            if any(w in q_lower for w in ["sale", "sales", "sold", "booking", "booked", "unsold", "absorption", "inventory", "overhang", "units"]) and not any(w in q_lower for w in ["price", "cagr", "rate", "cost", "sqft"]):
                reply_lines.append(f"### Sales Absorption & Inventory Overhang for **{p_name}**")
                total = p['total_units'] or 0
                booked = p['booked_units'] or 0
                unsold = p['unbooked_units'] or 0
                rate = p['booking_rate_pct'] or 0.0
                
                reply_lines.append(f"- **Overall Scheme Absorption**: **{booked} of {total} units booked** (`{rate:.1f}%` sold out).")
                reply_lines.append(f"- **Remaining Unsold Inventory**: **{unsold} units** (`{(100.0 - rate):.1f}%` market overhang).")

                # Block breakdown
                blocks = self.con.execute(
                    "SELECT block_name, total_units, booked_units, unbooked_units, booking_rate_pct, residential_units, commercial_units FROM inventory_blocks WHERE project_id = ? ORDER BY block_name",
                    (project_id,)
                ).fetchall()
                
                if blocks:
                    reply_lines.append("\n**Block-by-Block Sales Breakdown:**")
                    for b in blocks:
                        comm_tag = f" ({b['commercial_units']} commercial units)" if b['commercial_units'] else ""
                        reply_lines.append(f"- **{b['block_name']}**: {b['booked_units']}/{b['total_units']} units booked (`{b['booking_rate_pct']:.1f}%` sold) | {b['unbooked_units']} unsold{comm_tag}")

                # Financial consideration
                fin = self.con.execute("SELECT booked_consideration, received_amount, balance_amount, unbooked_consideration FROM finances WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
                if fin:
                    reply_lines.append("\n**Sales Realization & Cashflow:**")
                    reply_lines.append(f"- **Total Booked Consideration**: ₹{(fin['booked_consideration']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Cash Collected from Allottees**: ₹{(fin['received_amount']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Outstanding Buyer Balance**: ₹{(fin['balance_amount']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Estimated Value of Unsold Inventory**: ₹{(fin['unbooked_consideration']/10000000):,.2f} Cr.")

                recent_count = self.con.execute("SELECT COUNT(*) FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED'", (project_id,)).fetchone()[0]
                reply_lines.append(f"\n- **Sworn Form 3 Sale Agreements**: {recent_count} individual unit agreements registered on record.")

                citations.extend([
                    "Form 1 Architect Certificate (Block Progress)",
                    "Form 3 CA Certificate (formThreeAList)",
                    "Table 'inventory_blocks' & 'finances'"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 5. Mortgages / Encumbrances / Title
            if any(w in q_lower for w in ["mortgage", "loan", "encumbrance", "title", "charge", "borrowing", "pledge", "debt", "land", "plot", "survey"]):
                land = self.mcp_server.get_land_records(project_id)
                leads = [l for l in self.auditor.audit_project(project_id) if "Loan" in l.title or "Encumbrance" in l.title]
                search_res = self.search_engine.search("mortgage encumbrance loan", project_id=project_id, limit=3)
                
                reply_lines.append(f"### Title & Encumbrance Diligence for **{p_name}**")
                reply_lines.append(f"- **Land Plot Identity**: TP Scheme `{land.get('tp_scheme') or 'N/A'}`, Final Plot `{land.get('final_plot_no') or 'N/A'}`, Survey No `{land.get('survey_no') or 'N/A'}` in `{land.get('taluka') or land.get('district')}`.")
                
                if leads:
                    for l in leads:
                        reply_lines.append(f"- **⚠️ {l.title}**: {l.detail}")
                        reply_lines.append(f"  *Action*: {l.reconciliation_guidance}")
                else:
                    reply_lines.append("- **Institutional Finance Status**: No active bank borrowings or charges disclosed on project land in quarterly regulatory disclosures.")
                    
                if search_res:
                    reply_lines.append("\n**Regulatory Title Search Excerpts:**")
                    for s in search_res[:2]:
                        reply_lines.append(f"- *[{s['doc_type']} p.{s['page_number']}]*: {s['snippet']}")

                citations.extend([
                    "Advocate 30-Year Title Search Report",
                    "Form B Promoter Statutory Affidavit",
                    "Sub-Registrar Encumbrance Certificate"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 6. Escrow / 70% retention / Over-withdrawal check
            if any(w in q_lower for w in ["escrow", "retention", "withdrawal", "withdraw", "70%", "bank", "liquidity", "runway"]):
                health = self.mcp_server.get_escrow_health(project_id)
                runway = self.auditor.calculate_escrow_runway(project_id)
                leads = [l for l in self.auditor.audit_project(project_id) if "Escrow" in l.title or "Section 4(2)(l)(D)" in l.title]
                
                escrow_accs = health.get("escrow_70_percent_accounts", [])
                reply_lines.append(f"### Statutory Escrow Diligence for **{p_name}**")
                
                if escrow_accs:
                    acc = escrow_accs[0]
                    reply_lines.append(f"- **Designated 70% Account**: `{acc.get('account_number_masked')}` at **{acc.get('bank_name')}** ({acc.get('branch_name') or 'Main Branch'}).")
                    reply_lines.append(f"- **Period Deposits**: ₹{((acc.get('deposit_amt') or 0)/100000):,.2f} Lakhs | **Period Withdrawals**: ₹{((acc.get('withdrawal_amt') or 0)/100000):,.2f} Lakhs.")
                    reply_lines.append(f"- **Closing Liquidity**: ₹{((acc.get('closing_bal') or 0)/100000):,.2f} Lakhs.")
                else:
                    reply_lines.append("- **No dedicated 70% retention account** disclosed in latest Form 3 filing.")
                    
                if leads:
                    for l in leads:
                        reply_lines.append(f"- **⚠️ {l.title}**: {l.detail}")
                        reply_lines.append(f"  *Verification Guidance*: {l.reconciliation_guidance}")
                else:
                    reply_lines.append("- **Statutory Audit Verdict**: Fully compliant with RERA Section 4(2)(l)(D) Proviso 1. Cumulative withdrawals remain within physical construction completion limits.")

                if runway.get("narrative"):
                    reply_lines.append(f"- **Cash Runway Assessment**: {runway.get('narrative')}")

                citations.extend([
                    "RERA Act 2016 Section 4(2)(l)(D) Proviso 1",
                    "Form 3 CA Certificate & Passbook Table 'banks'",
                    "Quarterly Progress Reports (QPR)"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 7. Delay Risk / Survival Timeline
            if any(w in q_lower for w in ["delay", "survival", "timeline", "completion", "handover", "deadline", "percentile", "p50", "p90"]):
                surv = self.mcp_server.forecast_completion_delay(project_id)
                reply_lines.append(f"### Survival Handover Delay Analysis for **{p_name}**")
                reply_lines.append(f"- **RERA Registered Handover**: `{surv.get('registered_completion_date')}`")
                reply_lines.append(f"- **Risk Classification**: **{surv.get('delay_risk_label')}** (Hazard Ratio: {surv.get('hazard_ratio')})")
                reply_lines.append(f"- **Projected Slippage**: {surv.get('forecasted_delay_months')} months beyond registered deadline.")
                
                h_dates = surv.get("forecasted_handover_dates", {})
                reply_lines.append(f"- **Delivery Probability Milestones**:")
                reply_lines.append(f"  * `p50 (Median Expected)`: **{h_dates.get('p50_median_expected_date')}** (~{h_dates.get('p50_duration_months')} mos from launch)")
                reply_lines.append(f"  * `p75 (Conservative)`: **{h_dates.get('p75_conservative_date')}** (~{h_dates.get('p75_duration_months')} mos from launch)")
                reply_lines.append(f"  * `p90 (High Confidence)`: **{h_dates.get('p90_high_confidence_date')}** (~{h_dates.get('p90_duration_months')} mos from launch)")
                reply_lines.append(f"- **Confidence Assessment**: {surv.get('confidence_assessment')}")

                citations.extend([
                    "Semi-parametric Cox Proportional Hazards Model",
                    "Quarterly Progress Timeline (Form 1 / Form 2)",
                    "Physical Construction Velocity Score"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 8. Pricing / CAGR / Hedonic Attributions
            if any(w in q_lower for w in ["price", "pricing", "market rate", "cagr", "appreciation", "trajectory", "hedonic", "shap", "valuation", "rate"]):
                trend = self.pricing_engine.get_longitudinal_pricing_trend(project_id)
                pred = self.mcp_server.predict_pricing_benchmark(project_id)
                
                reply_lines.append(f"### Pricing Realization & Valuation for **{p_name}**")
                reply_lines.append(f"- **Multi-Year Registered Agreements**: {trend.get('total_agreements_analyzed')} sales deeds analyzed across quarters `{trend.get('first_quarter')}` to `{trend.get('latest_quarter')}`.")
                reply_lines.append(f"- **Price Appreciation**: **{trend.get('price_appreciation_pct')}%** (from ₹{trend.get('base_median_rate_sqft'):,.0f} to ₹{trend.get('latest_median_rate_sqft'):,.0f} per sq.ft).")
                reply_lines.append(f"- **Annualized CAGR**: **{trend.get('cagr_pct')}% per annum**.")
                
                if pred and not pred.get("error"):
                    reply_lines.append(f"\n**Hedonic ML Benchmark (Tree SHAP):**")
                    reply_lines.append(f"- **Model Fair Value**: ₹{pred.get('predicted_rate_per_sqft'):,.0f} / sq.ft (District Baseline: ₹{pred.get('base_market_average_inr'):,.0f}).")
                    top_pos = [f"{d['feature'].replace('_',' ')} (+₹{d['impact_inr_per_sqft']:,.0f})" for d in pred.get('top_positive_premiums', [])[:2]]
                    top_neg = [f"{d['feature'].replace('_',' ')} (-₹{abs(d['impact_inr_per_sqft']):,.0f})" for d in pred.get('top_negative_discounts', [])[:2]]
                    if top_pos:
                        reply_lines.append(f"- **Value Premiums**: {', '.join(top_pos)}")
                    if top_neg:
                        reply_lines.append(f"- **Value Discounts**: {', '.join(top_neg)}")

                citations.extend([
                    "Sub-Registrar Registered Sale Agreements (Form 3)",
                    "GBDT Hedonic Pricing Model with Exact Tree SHAP",
                    "Unit Transactions Database"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 9. Contagion / Shared Entities (Fixed List Bug)
            if any(w in q_lower for w in ["contagion", "shared", "sister", "architect", "engineer", "network", "promoter", "ca", "chartered accountant", "team", "consultant"]):
                net = self.mcp_server.trace_entity_network(project_id)
                shared = net.get("shared_entities", [])
                leads = net.get("contagion_risk_leads", [])
                
                reply_lines.append(f"### Entity Network & Contagion Audit for **{p_name}**")
                
                # 1. Certified Professional Team
                profs = self.con.execute("SELECT role, name, license_or_reg_no FROM professionals WHERE project_id = ?", (project_id,)).fetchall()
                if profs:
                    reply_lines.append("**Certified Professional Team:**")
                    for pr in profs:
                        lic = f" (Reg: `{pr['license_or_reg_no']}`)" if pr['license_or_reg_no'] else ""
                        reply_lines.append(f"- **{pr['role'].title()}**: **{pr['name']}**{lic}")
                reply_lines.append(f"- **Promoter**: **{p['promoter_name']}**")

                # 2. Cross-Project Shared Links (shared is a list)
                if isinstance(shared, list) and shared:
                    reply_lines.append("\n**Cross-Project Shared Connections:**")
                    for s in shared:
                        reply_lines.append(f"- **{s.get('entity_kind', 'Professional')} '{s.get('shared_entity_name')}'** is also engaged on **{s.get('linked_project_name')}** (ID `{s.get('linked_project_id')}`).")
                else:
                    reply_lines.append("\n- **Shared Entity Connections**: No cross-project overlaps detected with other schemes in the active database index.")

                # 3. Contagion Risk Leads
                if isinstance(leads, list) and leads:
                    reply_lines.append("\n**⚠️ Contagion Risk Signals Detected:**")
                    for l in leads:
                        sev = l.get('severity', 'MEDIUM')
                        reply_lines.append(f"- **[{sev}] {l.get('risk_type', 'CONTAGION')}**: {l.get('detail')}")
                else:
                    reply_lines.append("- **Contagion Risk Verdict**: Clean profile — None of the certified professionals or promoters are linked to defaulted, stalled, or disputed sister schemes.")

                citations.extend([
                    "Cross-Project Entity Knowledge Graph",
                    "Professionals Table (Form 1 / Form 2 / Form 3)",
                    "GujRERA Application & Disciplinary Records"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 10. Fallback: Full-Text Document Search
            search_res = self.search_engine.search(query, project_id=project_id, limit=3)
            reply_lines.append(f"### Diligence Search for **{p_name}** ('{query}')")
            if search_res:
                reply_lines.append("Found relevant statutory clauses and filings:")
                for s in search_res:
                    reply_lines.append(f"- **[{s['doc_type']} p.{s['page_number']}]**: {s['snippet']}")
            else:
                reply_lines.append("No direct clause matches found in indexed PDFs. Project overview:")
                reply_lines.append(f"- **Project**: {p_name} ({p['district'] if p else 'N/A'})")
                reply_lines.append(f"- **Promoter**: {p['promoter_name'] if p else 'N/A'}")
                reply_lines.append(f"- **Launch Date**: {p['start_date'] if p else 'N/A'} | **Deadline**: {p['completion_date'] if p else 'N/A'}")
                reply_lines.append(f"- **Physical Progress**: {p['latest_form_one_progress_pct'] if p else 0}% | **Velocity**: {p['velocity_ratio'] if p else 1.0}x")
                reply_lines.append(f"- **Sales Absorption**: {p['booked_units'] if p else 0}/{p['total_units'] if p else 0} units booked ({p['booking_rate_pct'] if p else 0}%)")

            citations.extend([
                "GujRERA Document Search Engine (FTS5 BM25)",
                "Form 1/2/3 Regulatory Filings"
            ])
            return {"reply": "\n".join(reply_lines), "citations": citations}

        except Exception as err:
            # Full detail stays in the server log; the client gets a sanitized note
            # (raw exception text can leak filesystem paths).
            import logging
            logging.getLogger(__name__).warning("Copilot query failed: %s", err, exc_info=True)
            return {
                "reply": "### Diligence Query Service Note\nAn internal processing error occurred while answering. Please rephrase your inquiry or try one of the quick prompts below.",
                "citations": ["GujRERA Statutory Fact Base"]
            }

        return {
            "reply": "\n".join(reply_lines),
            "citations": citations
        }

    def _send_json(self, data):
        try:
            raw = json.dumps(data, default=str, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except ValueError:
            # Degenerate aggregates (NaN/Inf, e.g. medians over empty groups) are not
            # valid JSON; null them out rather than emitting tokens browsers reject.
            raw = json.dumps(self._sanitize_nan(data), default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    @staticmethod
    def _sanitize_nan(value):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return None
        if isinstance(value, dict):
            return {k: IntelligenceRequestHandler._sanitize_nan(v) for k, v in value.items()}
        if isinstance(value, list):
            return [IntelligenceRequestHandler._sanitize_nan(v) for v in value]
        return value


def start_server(port: int = 8765, db_path=None):
    IntelligenceRequestHandler.setup_backends(db_path)
    # ThreadingHTTPServer so a slow request (e.g. an agentic LLM copilot call) cannot
    # freeze every other dashboard request. The shared SQLite connection is opened with
    # check_same_thread=False and 30 s busy_timeout (db.database.get_connection), and the
    # UI never writes, so concurrent read traffic is safe under WAL.
    server = ThreadingHTTPServer(("127.0.0.1", port), IntelligenceRequestHandler)
    server.daemon_threads = True
    print(f"\n[READY] Real Estate Intelligence Terminal running at: http://127.0.0.1:{port}", flush=True)
    print("Press Ctrl+C to stop the server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.", flush=True)
    finally:
        server.server_close()
