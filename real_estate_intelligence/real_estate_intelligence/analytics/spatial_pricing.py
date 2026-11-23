"""Spatial empirical micro-market pricing intelligence engine.

Pure Python empirical pricing comps utilizing indexed two-step queries over
spatial coordinates and unit transactions. Zero machine learning dependencies.
"""

import math
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config import DEFAULT_DB_PATH
from ..db.database import get_connection


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two GPS coordinates in kilometers."""
    r = 6371.0  # Earth's mean radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(r * c, 3)


def _percentile(sorted_vals: List[float], p: float) -> float:
    """Calculate percentile p (0-100) from an already-sorted list of floats using linear interpolation."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


class SpatialEmpiricalPricer:
    """Empirical micro-market spatial pricing engine with 3-tier fallback."""

    STATEWIDE_MARKUP_BASELINE_PCT: float = 12.63

    def __init__(self, con_or_db: Optional[Union[sqlite3.Connection, Path, str]] = None):
        if isinstance(con_or_db, sqlite3.Connection):
            self.con = con_or_db
            if self.con.row_factory is None:
                self.con.row_factory = sqlite3.Row
            self._owns_con = False
        elif isinstance(con_or_db, (Path, str)):
            path = Path(con_or_db)
            if path.suffix == ".sqlite" or path.is_file():
                self.con = get_connection(path)
                self._owns_con = True
            else:
                self.con = get_connection(DEFAULT_DB_PATH)
                self._owns_con = True
        else:
            self.con = get_connection(DEFAULT_DB_PATH)
            self._owns_con = True

    def _fetch_rates_for_pids(
        self, pids: List[int], asset_class: str, year_strs: List[str]
    ) -> List[float]:
        """Fetch cleaned booked transaction rates for a list of project IDs using chunked indexed queries."""
        if not pids or not year_strs:
            return []
        rates: List[float] = []
        chunk_size = 400
        for i in range(0, len(pids), chunk_size):
            chunk = pids[i : i + chunk_size]
            ph = ",".join("?" for _ in chunk)
            y_ph = ",".join("?" for _ in year_strs)
            query = f"""
                SELECT rate_per_sqft
                FROM unit_transactions
                WHERE project_id IN ({ph})
                  AND status = 'BOOKED'
                  AND asset_class = ?
                  AND rate_per_sqft BETWEEN 500 AND 50000
                  AND carpet_area_sqft > 0
                  AND SUBSTR(agreement_date, 1, 4) IN ({y_ph})
            """
            rows = self.con.execute(query, (*chunk, asset_class, *year_strs)).fetchall()
            rates.extend(r[0] for r in rows)
        return rates

    def benchmark(
        self,
        project_id: int,
        asset_class: str = "Residential",
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compute empirical spatial price-per-sqft benchmark for a project.

        Contract:
            Returns a dictionary containing:
            {
                "median_rate_sqft": float | None,
                "p25": float | None,
                "p75": float | None,
                "iqr": float | None,
                "sample_size": int,
                "benchmark_tier": str | None,
                "year_used": int | None,
                "project_booked_median": float | None,
                "project_unbooked_median": float | None,
                "unbooked_markup_pct": float | None,
                "statewide_markup_baseline_pct": 12.63,
            }
        """
        prow = self.con.execute(
            """
            SELECT project_id, name, district, taluka, latitude, longitude,
                   start_date, completion_date
            FROM projects WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if not prow:
            return {
                "error": f"Project {project_id} not found in database",
                "median_rate_sqft": None,
                "p25": None,
                "p75": None,
                "iqr": None,
                "sample_size": 0,
                "benchmark_tier": None,
                "year_used": year,
                "project_booked_median": None,
                "project_unbooked_median": None,
                "unbooked_markup_pct": None,
                "statewide_markup_baseline_pct": self.STATEWIDE_MARKUP_BASELINE_PCT,
            }

        # Resolve year_used
        year_used = year
        if year_used is None:
            # First attempt: most recent booked agreement year for the subject project
            row = self.con.execute(
                """
                SELECT CAST(SUBSTR(agreement_date, 1, 4) AS INTEGER)
                FROM unit_transactions
                WHERE project_id = ? AND status = 'BOOKED'
                  AND agreement_date IS NOT NULL AND length(agreement_date) >= 4
                ORDER BY agreement_date DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if row and row[0]:
                year_used = row[0]
            elif prow["completion_date"]:
                try:
                    year_used = int(str(prow["completion_date"])[:4])
                except (ValueError, TypeError):
                    pass
            if year_used is None and prow["start_date"]:
                try:
                    year_used = int(str(prow["start_date"])[:4])
                except (ValueError, TypeError):
                    pass
            if year_used is None:
                year_used = 2026

        # Compute subject project's own booked and unbooked medians
        b_rows = [
            r[0]
            for r in self.con.execute(
                """
                SELECT rate_per_sqft FROM unit_transactions
                WHERE project_id = ? AND status = 'BOOKED'
                  AND rate_per_sqft BETWEEN 500 AND 50000
                  AND carpet_area_sqft > 0
                """,
                (project_id,),
            ).fetchall()
        ]

        u_rows = [
            r[0]
            for r in self.con.execute(
                """
                SELECT rate_per_sqft FROM unit_transactions
                WHERE project_id = ? AND status = 'UNBOOKED'
                  AND rate_per_sqft BETWEEN 500 AND 50000
                  AND carpet_area_sqft > 0
                """,
                (project_id,),
            ).fetchall()
        ]

        project_booked_median = round(statistics.median(b_rows), 2) if b_rows else None
        project_unbooked_median = round(statistics.median(u_rows), 2) if u_rows else None
        unbooked_markup_pct: Optional[float] = None
        if project_booked_median and project_unbooked_median and project_booked_median > 0:
            unbooked_markup_pct = round(
                ((project_unbooked_median - project_booked_median) / project_booked_median) * 100.0,
                2,
            )

        lat = prow["latitude"]
        lon = prow["longitude"]
        district = prow["district"]
        taluka = prow["taluka"]

        benchmark_tier: Optional[str] = None
        benchmark_rates: List[float] = []

        # Tier 1 & Tier 2: Spatial Proximity Queries (Two-step indexed lookup)
        if lat is not None and lon is not None:
            # Step 1: Bounding box query on projects table (17.7k rows)
            d_lat = 5.0 / 111.0
            d_lon = 5.0 / (111.0 * max(0.01, math.cos(math.radians(lat))))

            nearby_prows = self.con.execute(
                """
                SELECT project_id, latitude, longitude FROM projects
                WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?
                """,
                (lat - d_lat, lat + d_lat, lon - d_lon, lon + d_lon),
            ).fetchall()

            pids_2km: List[int] = []
            pids_5km: List[int] = []
            for np in nearby_prows:
                dist = haversine_distance_km(lat, lon, np["latitude"], np["longitude"])
                if dist <= 2.0:
                    pids_2km.append(np["project_id"])
                if dist <= 5.0:
                    pids_5km.append(np["project_id"])

            # Tier 1: 2km same (asset_class, year) if N >= 5
            if pids_2km:
                t1_rates = self._fetch_rates_for_pids(pids_2km, asset_class, [str(year_used)])
                if len(t1_rates) >= 5:
                    benchmark_tier = "Tier 1"
                    benchmark_rates = t1_rates

            # Tier 2: 5km (asset_class, year ± 1) if N >= 5
            if not benchmark_tier and pids_5km:
                t2_years = [str(year_used - 1), str(year_used), str(year_used + 1)]
                t2_rates = self._fetch_rates_for_pids(pids_5km, asset_class, t2_years)
                if len(t2_rates) >= 5:
                    benchmark_tier = "Tier 2"
                    benchmark_rates = t2_rates

        # Tier 3: (district, taluka, asset_class, year) fallback
        if not benchmark_tier:
            if district and taluka:
                t3_rows = self.con.execute(
                    """
                    SELECT rate_per_sqft FROM unit_transactions
                    WHERE project_id IN (
                        SELECT project_id FROM projects WHERE district = ? AND taluka = ?
                    )
                      AND status = 'BOOKED'
                      AND asset_class = ?
                      AND rate_per_sqft BETWEEN 500 AND 50000
                      AND carpet_area_sqft > 0
                      AND SUBSTR(agreement_date, 1, 4) = ?
                    """,
                    (district, taluka, asset_class, str(year_used)),
                ).fetchall()
                t3_rates = [r[0] for r in t3_rows]
                if len(t3_rates) >= 5:
                    benchmark_tier = "Tier 3"
                    benchmark_rates = t3_rates

            if not benchmark_tier and district:
                t3_dist_rows = self.con.execute(
                    """
                    SELECT rate_per_sqft FROM unit_transactions
                    WHERE project_id IN (
                        SELECT project_id FROM projects WHERE district = ?
                    )
                      AND status = 'BOOKED'
                      AND asset_class = ?
                      AND rate_per_sqft BETWEEN 500 AND 50000
                      AND carpet_area_sqft > 0
                      AND SUBSTR(agreement_date, 1, 4) = ?
                    """,
                    (district, asset_class, str(year_used)),
                ).fetchall()
                t3_dist_rates = [r[0] for r in t3_dist_rows]
                if len(t3_dist_rates) >= 5:
                    benchmark_tier = "Tier 3"
                    benchmark_rates = t3_dist_rates

            if not benchmark_tier:
                # Final fallback: statewide asset_class and year
                sw_rows = self.con.execute(
                    """
                    SELECT rate_per_sqft FROM unit_transactions
                    WHERE asset_class = ?
                      AND status = 'BOOKED'
                      AND rate_per_sqft BETWEEN 500 AND 50000
                      AND carpet_area_sqft > 0
                      AND SUBSTR(agreement_date, 1, 4) = ?
                    LIMIT 10000
                    """,
                    (asset_class, str(year_used)),
                ).fetchall()
                benchmark_tier = "Tier 3"
                benchmark_rates = [r[0] for r in sw_rows]

        sorted_rates = sorted(benchmark_rates)
        n = len(sorted_rates)
        med = round(_percentile(sorted_rates, 50.0), 2) if n > 0 else None
        p25 = round(_percentile(sorted_rates, 25.0), 2) if n > 0 else None
        p75 = round(_percentile(sorted_rates, 75.0), 2) if n > 0 else None
        iqr = round(p75 - p25, 2) if p25 is not None and p75 is not None else None

        return {
            "median_rate_sqft": med,
            "p25": p25,
            "p75": p75,
            "iqr": iqr,
            "sample_size": n,
            "benchmark_tier": benchmark_tier,
            "year_used": year_used,
            "project_booked_median": project_booked_median,
            "project_unbooked_median": project_unbooked_median,
            "unbooked_markup_pct": unbooked_markup_pct,
            "statewide_markup_baseline_pct": self.STATEWIDE_MARKUP_BASELINE_PCT,
        }
