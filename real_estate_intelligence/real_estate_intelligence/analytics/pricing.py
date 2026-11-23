"""Unit-level pricing intelligence and transaction rate realization engine.

Queries the curated unit_transactions relational table rather than decompressing raw JSON at runtime.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config import DEFAULT_DB_PATH, DEFAULT_SOURCE_RUN
from ..db.database import get_connection


class PricingIntelligence:
    """Calculates registered unit-level transaction realization rates and benchmarks."""

    def __init__(
        self,
        con_or_db: Optional[Union[sqlite3.Connection, Path, str]] = None,
        source_run_dir: Optional[Path] = None,
    ):
        if isinstance(con_or_db, sqlite3.Connection):
            self.con = con_or_db
            self._owns_con = False
        elif isinstance(con_or_db, (Path, str)):
            path = Path(con_or_db)
            if path.suffix == ".sqlite" or path.is_file():
                self.con = get_connection(path)
                self._owns_con = True
            else:
                # Provided a directory; assume default DB
                self.con = get_connection(DEFAULT_DB_PATH)
                self._owns_con = True
        else:
            self.con = get_connection(DEFAULT_DB_PATH)
            self._owns_con = True

        self.source_run_dir = source_run_dir or DEFAULT_SOURCE_RUN

    def get_project_pricing_summary(self, project_id: int, asset_class: Optional[str] = "Residential") -> Dict[str, Any]:
        """Calculate registered unit-level transaction rates, median rate/sqft,
        block-by-block pricing benchmarks, and trailing-4Q realizations from curated unit_transactions.
        """
        cur = self.con.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(unit_transactions)").fetchall()}
        aclass_sel = "asset_class," if "asset_class" in cols else "'Residential' AS asset_class,"
        cur.execute(
            f"""
            SELECT block_name, unit_type, {aclass_sel} carpet_area_sqm, carpet_area_sqft,
                   unit_consideration, rate_per_sqft, rate_per_sqm, status, agreement_date
            FROM unit_transactions WHERE project_id = ?
            """,
            (project_id,),
        )
        rows = cur.fetchall()

        if not rows:
            # Check if project exists in database
            cur.execute("SELECT 1 FROM projects WHERE project_id = ?", (project_id,))
            if not cur.fetchone():
                return {"error": f"Project {project_id} not found in database"}
            return {
                "project_id": project_id,
                "total_units_evaluated": 0,
                "booked_units": 0,
                "unbooked_units": 0,
                "overall_rate_per_sqft": {},
                "overall_rate_per_sqm": {},
                "trailing_four_quarters_rate_per_sqft": {},
                "trailing_window_start": None,
                "trailing_window_end": None,
                "stale_deed_warning": False,
                "asset_class": asset_class or "All",
                "block_benchmarks": {},
                "inventory_type_benchmarks": {},
                "asset_class_benchmarks": {},
                "commercial_premiums": {},
                "recent_registered_transactions": [],
            }

        overall_rates_sqft: List[float] = []
        overall_rates_sqm: List[float] = []
        block_rates: Dict[str, List[float]] = {}
        type_rates: Dict[str, List[float]] = {}
        asset_rates: Dict[str, List[float]] = {}
        recent_agreements: List[Dict[str, Any]] = []

        total_booked_units = 0
        total_unbooked_units = 0

        # Normalization of requested asset class
        norm_ac = str(asset_class).strip().lower() if asset_class else ""
        is_all_ac = norm_ac in ("", "all", "none")
        matching_booked_rates: List[Tuple[str, float]] = []

        for r in rows:
            status = str(r["status"] or "").upper()
            if status != "BOOKED":
                total_unbooked_units += 1
                continue

            total_booked_units += 1
            ca_sqft = float(r["carpet_area_sqft"] or 0.0)
            ca_sqm = float(r["carpet_area_sqm"] or 0.0)
            cons = float(r["unit_consideration"] or 0.0)
            rate_sqft = float(r["rate_per_sqft"] or 0.0)
            rate_sqm = float(r["rate_per_sqm"] or 0.0)
            bname = str(r["block_name"] or "Unspecified").strip()
            utype = str(r["unit_type"] or "Residential").strip()
            
            # Asset class classification (with fallback for legacy or default rows)
            aclass = r["asset_class"] if "asset_class" in r.keys() and r["asset_class"] else None
            lower_u = utype.lower()
            if not aclass or (aclass == "Residential" and "residential" not in lower_u and lower_u):
                if any(k in lower_u for k in ["office"]):
                    aclass = "Commercial_Office"
                elif any(k in lower_u for k in ["shop", "retail", "showroom", "store"]):
                    aclass = "Commercial_Retail"
                elif any(k in lower_u for k in ["warehouse", "industrial", "shed"]):
                    aclass = "Industrial_Warehouse"
                elif "commercial" in lower_u:
                    aclass = "Commercial_Retail"
                else:
                    aclass = "Residential"

            agr_date = r["agreement_date"]

            if rate_sqft > 0:
                overall_rates_sqft.append(rate_sqft)
                block_rates.setdefault(bname, []).append(rate_sqft)
                type_rates.setdefault(utype, []).append(rate_sqft)
                asset_rates.setdefault(aclass, []).append(rate_sqft)

                # Check if matches target asset_class for trailing 4Q
                if agr_date:
                    d_str = str(agr_date)[:10]
                    matches_target = False
                    if is_all_ac:
                        matches_target = True
                    elif norm_ac.startswith("res") and ("res" in str(aclass).lower() or "res" in lower_u):
                        matches_target = True
                    elif norm_ac.startswith("com") and ("com" in str(aclass).lower() or any(k in lower_u for k in ["shop", "retail", "office", "commercial"])):
                        matches_target = True
                    elif norm_ac in str(aclass).lower() or norm_ac in lower_u:
                        matches_target = True

                    if matches_target:
                        matching_booked_rates.append((d_str, rate_sqft))

            if rate_sqm > 0:
                overall_rates_sqm.append(rate_sqm)

            if agr_date and rate_sqft > 0:
                recent_agreements.append({
                    "block": bname,
                    "carpet_sqft": round(ca_sqft, 1),
                    "consideration_inr": cons,
                    "rate_sqft": round(rate_sqft, 0),
                    "agreement_date": str(agr_date)[:10],
                })

        def stats_dict(rates: List[float]) -> Dict[str, float]:
            if not rates:
                return {}
            s = sorted(rates)
            n = len(s)
            return {
                "count": n,
                "min": round(s[0], 0),
                "p25": round(s[n // 4], 0),
                "median": round(s[n // 2], 0),
                "p75": round(s[(3 * n) // 4], 0),
                "max": round(s[-1], 0),
            }

        # Sort recent agreements by date descending
        recent_agreements.sort(key=lambda x: x["agreement_date"], reverse=True)

        asset_benchmarks = {a: stats_dict(r) for a, r in asset_rates.items()}
        res_med = asset_benchmarks.get("Residential", {}).get("median")
        retail_med = asset_benchmarks.get("Commercial_Retail", {}).get("median")
        office_med = asset_benchmarks.get("Commercial_Office", {}).get("median")

        commercial_premiums = {}
        if res_med and res_med > 0:
            if retail_med:
                commercial_premiums["retail_to_residential_ratio"] = round(retail_med / res_med, 2)
            if office_med:
                commercial_premiums["office_to_residential_ratio"] = round(office_med / res_med, 2)

        # Compute trailing-4Q stats from matching booked deeds
        trailing_stats: Dict[str, float] = {}
        trailing_window_start: Optional[str] = None
        trailing_window_end: Optional[str] = None
        stale_deed_warning: bool = False

        if matching_booked_rates:
            matching_booked_rates.sort(key=lambda x: x[0], reverse=True)
            max_d_str = matching_booked_rates[0][0]
            try:
                max_d = datetime.strptime(max_d_str, "%Y-%m-%d").date()
                start_d = max_d - timedelta(days=365)
                trailing_window_start = start_d.isoformat()
                trailing_window_end = max_d.isoformat()
                today_utc = datetime.now(timezone.utc).date()
                stale_deed_warning = (today_utc - max_d).days > 548  # 18 months

                t4q_rates = [rate for d_str, rate in matching_booked_rates if d_str >= trailing_window_start]
                trailing_stats = stats_dict(t4q_rates)
            except Exception:
                pass

        trend = self.get_longitudinal_pricing_trend(project_id, asset_class=asset_class)

        return {
            "project_id": project_id,
            "total_units_evaluated": len(rows),
            "booked_units": total_booked_units,
            "unbooked_units": total_unbooked_units,
            "overall_rate_per_sqft": stats_dict(overall_rates_sqft),
            "overall_rate_per_sqm": stats_dict(overall_rates_sqm),
            "trailing_four_quarters_rate_per_sqft": trailing_stats,
            "trailing_window_start": trailing_window_start,
            "trailing_window_end": trailing_window_end,
            "stale_deed_warning": stale_deed_warning,
            "asset_class": "All" if is_all_ac else (asset_class or "Residential"),
            "block_benchmarks": {b: stats_dict(r) for b, r in block_rates.items()},
            "inventory_type_benchmarks": {t: stats_dict(r) for t, r in type_rates.items()},
            "asset_class_benchmarks": asset_benchmarks,
            "commercial_premiums": commercial_premiums,
            "longitudinal_pricing_trend": trend,
            "recent_registered_transactions": recent_agreements[:10],
        }

    def get_longitudinal_pricing_trend(self, project_id: int, asset_class: Optional[str] = "Residential") -> Dict[str, Any]:
        """Calculate historical quarterly registered transaction rate velocity,
        longitudinal median appreciation, and Compound Annual Growth Rate (CAGR).
        """
        cur = self.con.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(unit_transactions)").fetchall()}
        aclass_sel = "asset_class" if "asset_class" in cols else "'Residential' AS asset_class"
        cur.execute(
            f"""
            SELECT agreement_date, rate_per_sqft, unit_consideration, carpet_area_sqft, unit_type, {aclass_sel}
            FROM unit_transactions
            WHERE project_id = ? AND status = 'BOOKED' AND agreement_date IS NOT NULL AND rate_per_sqft > 0
            ORDER BY agreement_date ASC
            """,
            (project_id,),
        )
        rows = cur.fetchall()
        
        norm_ac = str(asset_class).strip().lower() if asset_class else ""
        is_all_ac = norm_ac in ("", "all", "none")

        if not rows:
            return {
                "quarterly_trajectory": [],
                "first_quarter": None,
                "latest_quarter": None,
                "price_appreciation_pct": 0.0,
                "cagr_pct": 0.0,
                "total_agreements_analyzed": 0,
                "asset_class": "All" if is_all_ac else (asset_class or "Residential"),
            }

        q_groups: Dict[str, List[float]] = {}
        q_volumes: Dict[str, float] = {}
        total_filtered_agreements = 0

        for r in rows:
            # Asset class filter
            if not is_all_ac:
                r_ac = r["asset_class"] if "asset_class" in r.keys() and r["asset_class"] else None
                lower_u = str(r["unit_type"] or "").lower()
                if not r_ac or (r_ac == "Residential" and "residential" not in lower_u and lower_u):
                    if any(k in lower_u for k in ["office"]):
                        r_ac = "Commercial_Office"
                    elif any(k in lower_u for k in ["shop", "retail", "showroom", "store", "commercial"]):
                        r_ac = "Commercial_Retail"
                    elif any(k in lower_u for k in ["warehouse", "industrial", "shed"]):
                        r_ac = "Industrial_Warehouse"
                    else:
                        r_ac = "Residential"

                if norm_ac.startswith("res") and not ("res" in str(r_ac).lower() or "res" in lower_u):
                    continue
                elif norm_ac.startswith("com") and not ("com" in str(r_ac).lower() or any(k in lower_u for k in ["shop", "retail", "office", "commercial"])):
                    continue
                elif norm_ac not in ("", "all") and norm_ac not in str(r_ac).lower() and norm_ac not in lower_u:
                    continue

            d_str = str(r["agreement_date"])[:10]
            try:
                parts = d_str.split("-")
                year = parts[0]
                month = int(parts[1])
                quarter = (month - 1) // 3 + 1
                q_label = f"{year}-Q{quarter}"
            except Exception:
                continue

            rate = float(r["rate_per_sqft"] or 0.0)
            cons = float(r["unit_consideration"] or 0.0)
            if rate > 0:
                q_groups.setdefault(q_label, []).append(rate)
                q_volumes[q_label] = q_volumes.get(q_label, 0.0) + cons
                total_filtered_agreements += 1

        if not q_groups:
            return {
                "quarterly_trajectory": [],
                "first_quarter": None,
                "latest_quarter": None,
                "price_appreciation_pct": 0.0,
                "cagr_pct": 0.0,
                "total_agreements_analyzed": 0,
                "asset_class": "All" if is_all_ac else (asset_class or "Residential"),
            }

        sorted_quarters = sorted(q_groups.keys())
        trajectory = []
        for q in sorted_quarters:
            rates = sorted(q_groups[q])
            n = len(rates)
            med = rates[n // 2]
            trajectory.append({
                "quarter": q,
                "transaction_count": n,
                "median_rate_sqft": round(med, 1),
                "avg_rate_sqft": round(sum(rates) / n, 1),
                "min_rate_sqft": round(rates[0], 1),
                "max_rate_sqft": round(rates[-1], 1),
                "total_consideration_inr": round(q_volumes.get(q, 0.0), 0),
            })

        first_q = trajectory[0]
        latest_q = trajectory[-1]
        first_med = first_q["median_rate_sqft"]
        latest_med = latest_q["median_rate_sqft"]

        growth_pct = round(((latest_med - first_med) / first_med) * 100.0, 2) if first_med > 0 else 0.0

        num_quarters = len(sorted_quarters)
        delta_years = max(0.25, (num_quarters - 1) * 0.25)
        cagr = 0.0
        if first_med > 0 and latest_med > 0 and num_quarters > 1:
            try:
                cagr = round((((latest_med / first_med) ** (1.0 / delta_years)) - 1.0) * 100.0, 2)
            except Exception:
                cagr = 0.0

        return {
            "quarterly_trajectory": trajectory,
            "first_quarter": first_q["quarter"],
            "latest_quarter": latest_q["quarter"],
            "base_median_rate_sqft": first_med,
            "latest_median_rate_sqft": latest_med,
            "price_appreciation_pct": growth_pct,
            "cagr_pct": cagr,
            "total_agreements_analyzed": total_filtered_agreements,
            "asset_class": "All" if is_all_ac else (asset_class or "Residential"),
        }

    def close(self) -> None:
        if self._owns_con and self.con:
            self.con.close()
