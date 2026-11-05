"""Model Context Protocol (MCP) tool server for AI pair programming and agent integration."""

import json
from typing import Any, Dict, List, Optional

from ..analytics.audit import ProjectAuditor
from ..analytics.investor_dossier import generate_investor_dossier
from ..analytics.ml_pricing import HedonicPricingModel
from ..analytics.spatial import SpatialAnalytics
from ..analytics.survival import CompletionDelaySurvivalModel
from ..db.database import get_connection
from ..documents.search import DocumentSearchEngine
from ..graph.network import KnowledgeGraph


class RealEstateIntelligenceMCP:
    """Read-only research tools exposed via Model Context Protocol."""

    def __init__(self, db_path=None):
        self.con = get_connection(db_path)
        self.search_engine = DocumentSearchEngine(self.con)
        self.graph = KnowledgeGraph(self.con)
        self.auditor = ProjectAuditor(self.con)
        self.spatial = SpatialAnalytics(self.con)
        self._pricing_model: Optional[HedonicPricingModel] = None
        self._survival_model: Optional[CompletionDelaySurvivalModel] = None

    def get_project_dossier(self, project_id: int) -> str:
        """Generate a complete 4-quadrant executive diligence dossier for a project.

        Args:
            project_id: The GujRERA project registration ID (e.g. 16562, 16104).
        """
        return generate_investor_dossier(self.con, project_id)

    def query_inventory_breakdown(self, project_id: int) -> List[Dict[str, Any]]:
        """Return block-by-block inventory counts, booking rates, and residential vs commercial mix.

        Args:
            project_id: The GujRERA project registration ID.
        """
        cur = self.con.execute(
            """
            SELECT block_name, total_units, booked_units, unbooked_units,
                   booking_rate_pct, residential_units, commercial_units
            FROM inventory_blocks WHERE project_id = ? ORDER BY block_name
            """,
            (project_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def search_document_evidence(
        self, query: str, project_id: Optional[int] = None, doc_type: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Perform hybrid full-text search with BM25 ranking across all indexed PDF documents.

        Args:
            query: Keywords or phrases to search (e.g. 'title clearance', 'encumbrance', 'mortgage').
            project_id: Optional project ID filter.
            doc_type: Optional document type filter (e.g. 'form_three_ca', 'title_search_report').
            limit: Maximum results to return (default 5).
        """
        return self.search_engine.search(query=query, project_id=project_id, doc_type=doc_type, limit=limit)

    def trace_entity_network(self, project_id: int) -> Dict[str, Any]:
        """Trace cross-project relationships, shared professionals, and contagion risk.

        Args:
            project_id: The GujRERA project registration ID.
        """
        shared = self.graph.find_shared_entities(project_id)
        contagion = self.graph.trace_contagion_risk(project_id)
        return {"project_id": project_id, "shared_entities": shared, "contagion_risk_leads": contagion}

    def audit_discrepancies(self, project_id: int) -> List[Dict[str, Any]]:
        """Run automated discrepancy checks (cost drops, schedule slippage, missing BUs, complaints).

        Args:
            project_id: The GujRERA project registration ID.
        """
        leads = self.auditor.audit_project(project_id)
        return [
            {
                "category": l.category,
                "severity": l.severity,
                "title": l.title,
                "detail": l.detail,
                "evidence_source": l.evidence_source,
                "reconciliation_guidance": l.reconciliation_guidance,
            }
            for l in leads
        ]

    def get_escrow_health(self, project_id: int) -> Dict[str, Any]:
        """Audit project banking structure, separating 70% Designated Retention Escrow from 100% Collection accounts.

        Args:
            project_id: The GujRERA project registration ID.
        """
        cur = self.con.execute(
            """
            SELECT bank_name, branch_name, ifsc_code, account_type, account_name,
                   account_number_masked, deposit_amt, withdrawal_amt, opening_bal,
                   closing_bal, opening_date, closing_date, passbook_id
            FROM banks WHERE project_id = ? ORDER BY account_type ASC
            """,
            (project_id,),
        )
        bank_rows = [dict(r) for r in cur.fetchall()]

        # Financial balances from Form 3
        f_cur = self.con.execute(
            """
            SELECT booked_consideration, received_amount, balance_amount,
                   unbooked_consideration, incurred_and_paid, estimated_cost
            FROM finances WHERE project_id = ? ORDER BY id DESC LIMIT 1
            """,
            (project_id,),
        )
        f_row = f_cur.fetchone()
        finance_summary = dict(f_row) if f_row else {}

        escrow_accounts = [b for b in bank_rows if b["account_type"] == 1]
        collection_accounts = [b for b in bank_rows if b["account_type"] == 2]

        # Liquidity warning
        low_liquidity = any((b.get("closing_bal") or 0) < 50000 for b in escrow_accounts)

        return {
            "project_id": project_id,
            "escrow_70_percent_accounts": escrow_accounts,
            "collection_100_percent_accounts": collection_accounts,
            "cash_flow_summary": finance_summary,
            "low_liquidity_flag": low_liquidity,
        }

    def get_land_records(self, project_id: int) -> Dict[str, Any]:
        """Fetch municipal town planning, final plot, survey identifiers, GPS centroids and block BU permissions.

        Args:
            project_id: The GujRERA project registration ID.
        """
        p_row = self.con.execute(
            """
            SELECT project_id, name, district, taluka, tp_scheme, final_plot_no,
                   survey_no, latitude, longitude, google_maps_url, bu_status
            FROM projects WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if not p_row:
            return {"error": f"Project {project_id} not found"}

        bu_rows = self.con.execute(
            """
            SELECT block_name, bu_check, bu_date, fire_doc_id, lift_doc_id
            FROM noc_bu_records WHERE project_id = ? ORDER BY block_name ASC
            """,
            (project_id,),
        ).fetchall()

        res = dict(p_row)
        res["block_clearances"] = [dict(b) for b in bu_rows]
        return res

    def get_regulatory_radar(self, project_id: int) -> Dict[str, Any]:
        """Retrieve regulatory radar indicators: complaints, Section 14 alterations, QPR defaults, and Form 5 audit history.

        Args:
            project_id: The GujRERA project registration ID.
        """
        p_row = self.con.execute(
            """
            SELECT project_id, name, complaints_count, has_complaints,
                   alterations_count, has_alterations, extensions_count, has_extensions,
                   default_quarters_count, society_reg_date, form_four_status, bu_status,
                   velocity_ratio, progress_status_label
            FROM projects WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if not p_row:
            return {"error": f"Project {project_id} not found"}

        f5_rows = self.con.execute(
            """
            SELECT financial_year, status, submitted_on, doc_uid
            FROM form5_compliance WHERE project_id = ? ORDER BY financial_year ASC
            """,
            (project_id,),
        ).fetchall()

        res = dict(p_row)
        res["form5_annual_audits"] = [dict(f) for f in f5_rows]
        return res

    def compare_projects(self, project_ids: List[int]) -> List[Dict[str, Any]]:
        """Compare multiple projects side-by-side on progress, pricing, velocity, and regulatory risk.

        Args:
            project_ids: List of GujRERA project registration IDs to compare.
        """
        if not project_ids:
            return []
        placeholders = ",".join("?" for _ in project_ids)
        rows = self.con.execute(
            f"""
            SELECT project_id, name, promoter_name, district, project_type,
                   total_units, booked_units, booking_rate_pct,
                   latest_form_one_progress_pct, velocity_ratio, progress_status_label,
                   estimated_cost_inr, incurred_cost_inr, complaints_count,
                   alterations_count, default_quarters_count, bu_status
            FROM projects WHERE project_id IN ({placeholders})
            ORDER BY project_id
            """,
            project_ids,
        ).fetchall()
        return [dict(r) for r in rows]

    def predict_pricing_benchmark(
        self, project_id: int, asset_class: str = "Residential", carpet_area_sqft: float = 1200.0
    ) -> Dict[str, Any]:
        """Predict unit valuation rate/sqft using the Hedonic GBDT Model with exact SHAP breakdown.

        Args:
            project_id: GujRERA project registration ID.
            asset_class: 'Residential', 'Commercial_Office', 'Commercial_Retail', or 'Industrial_Warehouse'.
            carpet_area_sqft: Unit carpet area in square feet.
        """
        if self._pricing_model is None:
            self._pricing_model = HedonicPricingModel(n_estimators=25, max_depth=3)
            self._pricing_model.train_from_db(self.con)

        p_row = self.con.execute(
            """
            SELECT p.district, p.latitude, p.longitude, p.latest_form_one_progress_pct,
                   p.velocity_ratio, pr.total_projects_claimed
            FROM projects p
            LEFT JOIN promoters pr ON p.promoter_id = pr.promoter_id
            WHERE p.project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if not p_row:
            return {"error": f"Project {project_id} not found"}

        p_dict = {
            "district": p_row[0],
            "latitude": p_row[1],
            "longitude": p_row[2],
            "latest_form_one_progress_pct": p_row[3],
            "velocity_ratio": p_row[4],
            "total_projects_claimed": p_row[5],
        }
        u_dict = {"asset_class": asset_class, "carpet_area_sqft": carpet_area_sqft}
        feats = self._pricing_model.extract_features(u_dict, p_dict)
        return self._pricing_model.explain(feats)

    def forecast_completion_delay(self, project_id: int) -> Dict[str, Any]:
        """Forecast handover completion probability percentiles (p50, p75, p90) using Survival Analysis.

        Args:
            project_id: GujRERA project registration ID.
        """
        if self._survival_model is None:
            self._survival_model = CompletionDelaySurvivalModel()
            self._survival_model.train_from_db(self.con)

        return self._survival_model.forecast_project_by_id(self.con, project_id)

    def calculate_escrow_runway(self, project_id: int) -> Dict[str, Any]:
        """Calculate monthly construction spend velocity, 70% Escrow cash runway, and insolvency risk.

        Args:
            project_id: GujRERA project registration ID.
        """
        return self.auditor.calculate_escrow_runway(project_id)

    def get_spatial_density(self, project_id: int, radius_km: float = 3.0) -> Dict[str, Any]:
        """Find neighbouring projects within radius, shared TP scheme cluster, and competitive density.

        Args:
            project_id: GujRERA project registration ID.
            radius_km: Search radius in kilometres (default 3.0 km).
        """
        return self.spatial.get_nearby_projects(project_id, radius_km=radius_km)

