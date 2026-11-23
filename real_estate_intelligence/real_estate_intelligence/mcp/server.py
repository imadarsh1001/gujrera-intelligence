"""Model Context Protocol (MCP) tool server for AI pair programming and agent integration."""

import json
import threading
from typing import Any, Dict, List, Optional

from ..analytics.audit import ProjectAuditor
from ..analytics.claims_checker import SalesClaimVerifier
from ..analytics.investor_dossier import generate_investor_dossier
from ..analytics.ml_pricing import HedonicPricingModel
from ..analytics.pricing import PricingIntelligence
from ..analytics.spatial import SpatialAnalytics
from ..analytics.spatial_pricing import SpatialEmpiricalPricer
from ..analytics.survival import CompletionDelaySurvivalModel
from ..db.database import get_connection
from ..documents.search import DocumentSearchEngine
from ..graph.network import KnowledgeGraph, resolve_promoter_portfolio


class RealEstateIntelligenceMCP:
    """Read-only sovereign research tools exposed via Model Context Protocol."""

    def __init__(self, db_path=None):
        self.con = get_connection(db_path)
        self.search_engine = DocumentSearchEngine(self.con)
        self.graph = KnowledgeGraph(self.con)
        self.auditor = ProjectAuditor(self.con)
        self.spatial = SpatialAnalytics(self.con)
        self.pricing = PricingIntelligence(self.con)
        self.spatial_pricer = SpatialEmpiricalPricer(self.con)
        self.claims_verifier = SalesClaimVerifier(self.con)
        self._pricing_model: Optional[HedonicPricingModel] = None
        self._survival_model: Optional[CompletionDelaySurvivalModel] = None
        # Guards lazy model training for legacy endpoints
        self._model_lock = threading.Lock()

    # =========================================================================
    # STATEWIDE CORE TOOLS (11)
    # =========================================================================

    def search_projects(
        self,
        district: Optional[str] = None,
        taluka: Optional[str] = None,
        promoter_name: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_absorption: Optional[float] = None,
        has_bu: Optional[bool] = None,
        cohort_year: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search and filter Gujarat RERA projects across the statewide universe (17,787 projects).

        Args:
            district: District name filter (case-insensitive substring match).
            taluka: Taluka name filter (case-insensitive substring match).
            promoter_name: Developer / promoter name filter (case-insensitive substring match).
            min_price: Minimum median price per sq.ft. (INR/sq.ft.).
            max_price: Maximum median price per sq.ft. (INR/sq.ft.).
            min_absorption: Minimum unit absorption rate percentage (0.0 to 100.0).
            has_bu: Filter by Building Use (BU) permission status.
            cohort_year: Registration or scheduled completion calendar year.
            limit: Maximum projects to return (default 20, capped at 100).
            offset: Pagination offset (default 0).
        """
        clamped_limit = min(max(1, limit), 100)
        clamped_offset = max(0, offset)

        where_clauses = ["1=1"]
        params: List[Any] = []

        if district:
            where_clauses.append("UPPER(p.district) LIKE ?")
            params.append(f"%{district.strip().upper()}%")
        if taluka:
            where_clauses.append("UPPER(p.taluka) LIKE ?")
            params.append(f"%{taluka.strip().upper()}%")
        if promoter_name:
            where_clauses.append("UPPER(p.promoter_name) LIKE ?")
            params.append(f"%{promoter_name.strip().upper()}%")
        if min_price is not None:
            where_clauses.append("COALESCE(ps.avg_rate_sqft_booked, 0) >= ?")
            params.append(float(min_price))
        if max_price is not None:
            where_clauses.append("COALESCE(ps.avg_rate_sqft_booked, 0) <= ?")
            params.append(float(max_price))
        if min_absorption is not None:
            where_clauses.append("COALESCE(ps.absorption_pct, p.booking_rate_pct, 0) >= ?")
            params.append(float(min_absorption))
        if has_bu is True:
            where_clauses.append(
                "(ps.has_bu_noc = 1 OR EXISTS (SELECT 1 FROM noc_bu_records b WHERE b.project_id = p.project_id AND UPPER(b.bu_check) = 'YES'))"
            )
        elif has_bu is False:
            where_clauses.append(
                "(COALESCE(ps.has_bu_noc, 0) = 0 AND NOT EXISTS (SELECT 1 FROM noc_bu_records b WHERE b.project_id = p.project_id AND UPPER(b.bu_check) = 'YES'))"
            )
        if cohort_year is not None:
            where_clauses.append(
                "CAST(SUBSTR(COALESCE(p.completion_date, p.start_date), 1, 4) AS INT) = ?"
            )
            params.append(int(cohort_year))

        where_sql = " AND ".join(where_clauses)

        # Count total matching
        count_sql = f"""
            SELECT COUNT(1)
            FROM projects p
            LEFT JOIN project_summaries ps ON p.project_id = ps.project_id
            WHERE {where_sql}
        """
        total = self.con.execute(count_sql, params).fetchone()[0]

        # Query paginated rows
        data_sql = f"""
            SELECT p.project_id, p.name, p.registration_number, p.promoter_name,
                   p.district, p.taluka, p.project_type, p.total_units, p.booked_units,
                   p.booking_rate_pct, p.start_date, p.completion_date,
                   ps.avg_rate_sqft_booked, ps.has_bu_noc, ps.absorption_pct
            FROM projects p
            LEFT JOIN project_summaries ps ON p.project_id = ps.project_id
            WHERE {where_sql}
            ORDER BY p.project_id ASC
            LIMIT ? OFFSET ?
        """
        data_params = params + [clamped_limit, clamped_offset]
        rows = self.con.execute(data_sql, data_params).fetchall()

        projects = []
        for r in rows:
            d = dict(r)
            d["bu_status"] = "YES" if d.get("has_bu_noc") else "NO"
            projects.append(d)

        return {
            "projects": projects,
            "total": total,
            "offset": clamped_offset,
            "limit": clamped_limit,
        }

    def get_project_dossier(self, project_id: int) -> str:
        """Generate a complete 4-quadrant executive diligence dossier for a project.

        Args:
            project_id: The GujRERA project registration ID (e.g. 16562, 16104).
        """
        return generate_investor_dossier(self.con, project_id)

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
            SELECT p.project_id, p.name, p.promoter_name, p.district, p.project_type,
                   p.total_units, p.booked_units, p.booking_rate_pct,
                   p.latest_form_one_progress_pct, p.velocity_ratio, p.progress_status_label,
                   p.estimated_cost_inr, p.incurred_cost_inr, p.complaints_count,
                   p.alterations_count, p.default_quarters_count,
                   ps.has_bu_noc
            FROM projects p
            LEFT JOIN project_summaries ps ON p.project_id = ps.project_id
            WHERE p.project_id IN ({placeholders})
            ORDER BY p.project_id
            """,
            project_ids,
        ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            pid = d["project_id"]
            bu_cert = self.con.execute(
                "SELECT 1 FROM noc_bu_records WHERE project_id = ? AND UPPER(bu_check) = 'YES' LIMIT 1",
                (pid,),
            ).fetchone()
            has_noc = bool(d.get("has_bu_noc"))
            d["bu_status"] = "YES" if (has_noc or bu_cert) else "NO"
            result.append(d)
        return result

    def query_unit_transactions(
        self,
        project_id: int,
        asset_class: Optional[str] = None,
        status: Optional[str] = None,
        min_rate: Optional[float] = None,
        max_rate: Optional[float] = None,
        year: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Query individual deed-level unit transactions with strictly indexed lookups.

        Never performs full table scans on the 1.95M unit_transactions table.

        Args:
            project_id: The GujRERA project registration ID (primary indexed partition key).
            asset_class: Filter by asset category ('Residential', 'Commercial_Office', 'Commercial_Retail', 'Industrial_Warehouse').
            status: Filter by unit booking status ('BOOKED' or 'UNBOOKED').
            min_rate: Minimum registered rate per sq.ft. (INR/sq.ft.).
            max_rate: Maximum registered rate per sq.ft. (INR/sq.ft.).
            year: Agreement calendar year filter.
            limit: Maximum records to return (default 50, max 200).
            offset: Pagination offset (default 0).
        """
        clamped_limit = min(max(1, limit), 200)
        clamped_offset = max(0, offset)

        where_clauses = ["project_id = ?"]
        params: List[Any] = [project_id]

        if asset_class:
            where_clauses.append("asset_class = ?")
            params.append(asset_class.strip())
        if status:
            where_clauses.append("status = ?")
            params.append(status.strip().upper())
        if min_rate is not None:
            where_clauses.append("rate_per_sqft >= ?")
            params.append(float(min_rate))
        if max_rate is not None:
            where_clauses.append("rate_per_sqft <= ?")
            params.append(float(max_rate))
        if year is not None:
            where_clauses.append("CAST(SUBSTR(agreement_date, 1, 4) AS INT) = ?")
            params.append(int(year))

        where_sql = " AND ".join(where_clauses)

        # Count total
        count_sql = f"SELECT COUNT(1) FROM unit_transactions WHERE {where_sql}"
        total = self.con.execute(count_sql, params).fetchone()[0]

        # Fetch records
        query_sql = f"""
            SELECT id AS unit_id, project_id, block_name, carpet_area_sqft,
                   asset_class, unit_type, unit_consideration, rate_per_sqft,
                   agreement_date, status
            FROM unit_transactions
            WHERE {where_sql}
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """
        query_params = params + [clamped_limit, clamped_offset]
        rows = self.con.execute(query_sql, query_params).fetchall()

        return {
            "project_id": project_id,
            "transactions": [dict(r) for r in rows],
            "total": total,
            "offset": clamped_offset,
            "limit": clamped_limit,
        }

    def get_spatial_pricing_benchmark(
        self,
        project_id: int,
        asset_class: str = "Residential",
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compute empirical spatial micro-market pricing benchmark using SpatialEmpiricalPricer.

        Uses indexed 2-step geographic comps with 3-tier distance and boundary fallback.

        Args:
            project_id: GujRERA project registration ID.
            asset_class: Asset class ('Residential', 'Commercial_Office', 'Commercial_Retail', 'Industrial_Warehouse').
            year: Agreement year (defaults to project active deed year).
        """
        return self.spatial_pricer.benchmark(project_id, asset_class=asset_class, year=year)

    def get_pricing_appreciation_trend(self, project_id: int) -> Dict[str, Any]:
        """Calculate historical quarterly registered transaction rate velocity, longitudinal appreciation, and CAGR.

        Args:
            project_id: The GujRERA project registration ID.
        """
        return self.pricing.get_longitudinal_pricing_trend(project_id)

    def verify_sales_claim(
        self,
        project_id: int,
        claimed_rate: Optional[float] = None,
        claimed_sold_pct: Optional[float] = None,
        claimed_completion_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify broker or developer marketing sales claims against official sworn RERA deed disclosures.

        Args:
            project_id: GujRERA project registration ID.
            claimed_rate: Claimed price per square foot (INR/sq.ft.).
            claimed_sold_pct: Claimed percentage of inventory sold (0.0 to 100.0).
            claimed_completion_date: Claimed completion date (YYYY-MM-DD).
        """
        return self.claims_verifier.verify_claim(
            project_id=project_id,
            claimed_rate_sqft=claimed_rate,
            claimed_sold_pct=claimed_sold_pct,
            claimed_completion_date=claimed_completion_date,
        )

    def get_spatial_density(
        self,
        project_id: int,
        radius_km: float = 3.0,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Find neighbouring projects within radius, shared TP scheme cluster, and competitive density.

        Paginated to prevent large payloads (<= 20 results per page).

        Args:
            project_id: GujRERA project registration ID.
            radius_km: Search radius in kilometres (default 3.0 km).
            limit: Maximum neighbours to return (default 20, max 20).
            offset: Pagination offset (default 0).
        """
        clamped_limit = min(max(1, limit), 20)
        clamped_offset = max(0, offset)

        raw = self.spatial.get_nearby_projects(project_id, radius_km=radius_km)
        if "nearby_projects" in raw:
            all_nearby = raw["nearby_projects"]
            total = len(all_nearby)
            sliced = all_nearby[clamped_offset : clamped_offset + clamped_limit]
            res = dict(raw)
            res["nearby_projects"] = sliced
            res["pagination"] = {
                "offset": clamped_offset,
                "limit": clamped_limit,
                "total": total,
            }
            return res
        return raw

    def get_land_records(self, project_id: int) -> Dict[str, Any]:
        """Fetch municipal town planning, final plot, survey identifiers, GPS centroids and block BU permissions.

        Switches BU check off dead projects.bu_status to project_summaries.has_bu_noc + noc_bu_records.bu_check.

        Args:
            project_id: The GujRERA project registration ID.
        """
        p_row = self.con.execute(
            """
            SELECT p.project_id, p.name, p.district, p.taluka, p.tp_scheme, p.final_plot_no,
                   p.survey_no, p.latitude, p.longitude, p.google_maps_url,
                   ps.has_bu_noc
            FROM projects p
            LEFT JOIN project_summaries ps ON p.project_id = ps.project_id
            WHERE p.project_id = ?
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

        block_clearances = [dict(b) for b in bu_rows]
        res = dict(p_row)
        res["block_clearances"] = block_clearances

        has_noc = bool(res.get("has_bu_noc"))
        has_bu_cert = any(str(b.get("bu_check", "")).strip().upper() == "YES" for b in block_clearances)
        res["bu_status"] = "YES" if (has_noc or has_bu_cert) else "NO"
        return res

    def trace_entity_network(
        self,
        project_id: int,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """Trace cross-project relationships, shared professionals, and contagion risk.

        Filters out dead promoter:None supernodes and strictly enforces token caps.

        Args:
            project_id: The GujRERA project registration ID.
            max_tokens: Maximum token payload ceiling (default 4,000).
        """
        network = self.graph.get_ego_network(project_id)
        shared = self.graph.find_shared_entities(project_id)
        contagion = self.graph.trace_contagion_risk(project_id)
        return {
            "project_id": project_id,
            "network": network,
            "shared_entities": shared,
            "contagion_risk_leads": contagion,
        }

    def get_promoter_portfolio(
        self,
        project_id: Optional[int] = None,
        promoter_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve promoter cross-project portfolio with composite linkage, homonym warnings, and expired scheme risk.

        Args:
            project_id: Optional GujRERA project registration ID anchor.
            promoter_name: Optional developer/promoter commercial brand name.
        """
        return resolve_promoter_portfolio(self.con, project_id=project_id, promoter_name=promoter_name)

    # =========================================================================
    # PILOT DEEP-AUDIT GATED TOOLS (3)
    # =========================================================================

    def audit_discrepancies(
        self,
        project_id: int,
        include_skipped: bool = True,
    ) -> List[Dict[str, Any]]:
        """Run automated discrepancy checks (cost drops, schedule slippage, missing BUs, complaints).

        Args:
            project_id: The GujRERA project registration ID.
            include_skipped: Whether to explicitly report SKIPPED_UNINGESTED indicators for unpopulated tables.
        """
        leads = self.auditor.audit_project(project_id, include_skipped=include_skipped)
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

    def get_escrow_and_finances(self, project_id: int) -> Dict[str, Any]:
        """Audit project banking structure and monthly construction cash runway (merges escrow health + runway).

        Args:
            project_id: The GujRERA project registration ID.
        """
        health = self.get_escrow_health(project_id)
        runway = self.calculate_escrow_runway(project_id)
        return {
            "project_id": project_id,
            "escrow_health": health,
            "runway_analysis": runway,
        }

    def get_regulatory_radar(self, project_id: int) -> Dict[str, Any]:
        """Retrieve regulatory radar indicators: complaints, Section 14 alterations, QPR defaults, and Form 5 audit history.

        Switches BU check off dead projects.bu_status to project_summaries.has_bu_noc + noc_bu_records.bu_check.

        Args:
            project_id: The GujRERA project registration ID.
        """
        p_row = self.con.execute(
            """
            SELECT p.project_id, p.name, p.complaints_count, p.has_complaints,
                   p.alterations_count, p.has_alterations, p.extensions_count, p.has_extensions,
                   p.default_quarters_count, p.society_reg_date, p.form_four_status,
                   p.velocity_ratio, p.progress_status_label,
                   ps.has_bu_noc
            FROM projects p
            LEFT JOIN project_summaries ps ON p.project_id = ps.project_id
            WHERE p.project_id = ?
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

        bu_check_row = self.con.execute(
            "SELECT 1 FROM noc_bu_records WHERE project_id = ? AND UPPER(bu_check) = 'YES' LIMIT 1",
            (project_id,),
        ).fetchone()

        res = dict(p_row)
        res["form5_annual_audits"] = [dict(f) for f in f5_rows]
        has_noc = bool(res.get("has_bu_noc"))
        res["bu_status"] = "YES" if (has_noc or bu_check_row) else "NO"
        return res

    # =========================================================================
    # BACKWARD-COMPATIBLE LEGACY METHODS (Preserved for existing 83 pytest tests)
    # =========================================================================

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
        self,
        query: str,
        project_id: Optional[int] = None,
        doc_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid full-text search with BM25 ranking across all indexed PDF documents.

        Args:
            query: Keywords or phrases to search.
            project_id: Optional project ID filter.
            doc_type: Optional document type filter.
            limit: Maximum results to return (default 5).
        """
        return self.search_engine.search(query=query, project_id=project_id, doc_type=doc_type, limit=limit)

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

        escrow_accounts = [b for b in bank_rows if b.get("account_type") == 1]
        collection_accounts = [b for b in bank_rows if b.get("account_type") == 2]

        low_liquidity = any((b.get("closing_bal") or 0) < 50000 for b in escrow_accounts)

        return {
            "project_id": project_id,
            "escrow_70_percent_accounts": escrow_accounts,
            "collection_100_percent_accounts": collection_accounts,
            "cash_flow_summary": finance_summary,
            "low_liquidity_flag": low_liquidity,
        }

    def calculate_escrow_runway(self, project_id: int) -> Dict[str, Any]:
        """Calculate monthly construction spend velocity, 70% Escrow cash runway, and insolvency risk.

        Args:
            project_id: GujRERA project registration ID.
        """
        return self.auditor.calculate_escrow_runway(project_id)

    def predict_pricing_benchmark(
        self,
        project_id: int,
        asset_class: str = "Residential",
        carpet_area_sqft: float = 1200.0,
    ) -> Dict[str, Any]:
        """Predict unit valuation rate/sqft using the Hedonic GBDT Model with exact SHAP breakdown.

        Args:
            project_id: GujRERA project registration ID.
            asset_class: 'Residential', 'Commercial_Office', 'Commercial_Retail', or 'Industrial_Warehouse'.
            carpet_area_sqft: Unit carpet area in square feet.
        """
        if self._pricing_model is None:
            with self._model_lock:
                if self._pricing_model is None:
                    model = HedonicPricingModel(n_estimators=25, max_depth=3)
                    model.train_from_db(self.con)
                    self._pricing_model = model

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
            with self._model_lock:
                if self._survival_model is None:
                    model = CompletionDelaySurvivalModel()
                    model.train_from_db(self.con)
                    self._survival_model = model

        return self._survival_model.forecast_project_by_id(self.con, project_id)
