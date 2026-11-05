"""Geospatial (GIS) micro-market analytics and spatial clustering engine.

Operates over project GPS coordinates (latitude, longitude) and Town Planning (TP) schemes.
"""

import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config import DEFAULT_DB_PATH
from ..db.database import get_connection


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in kilometers."""
    r = 6371.0  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 3)


class SpatialAnalytics:
    """Computes micro-market spatial clusters, radius benchmarks, and TP scheme absorption."""

    def __init__(self, con_or_path: Optional[Union[sqlite3.Connection, Path, str]] = None):
        if isinstance(con_or_path, sqlite3.Connection):
            self.con = con_or_path
            self._owns_con = False
        elif isinstance(con_or_path, (Path, str)):
            self.con = get_connection(Path(con_or_path))
            self._owns_con = True
        else:
            self.con = get_connection(DEFAULT_DB_PATH)
            self._owns_con = True

    def get_nearby_projects(self, project_id: int, radius_km: float = 3.0) -> Dict[str, Any]:
        """Find registered projects within a radius and compute micro-market benchmarks."""
        cur = self.con.cursor()
        origin = cur.execute(
            "SELECT project_id, name, latitude, longitude, district, tp_scheme FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()

        if not origin:
            return {"error": f"Project {project_id} not found"}

        olat, olng = origin["latitude"], origin["longitude"]
        if olat is None or olng is None:
            return {
                "project_id": project_id,
                "error": "Project lacks valid GPS coordinates (latitude/longitude)",
                "nearby_count": 0,
                "nearby_projects": [],
            }

        all_projects = cur.execute(
            """
            SELECT project_id, name, registration_number, promoter_name, district,
                   latitude, longitude, booking_rate_pct, velocity_ratio, complaints_count
            FROM projects
            WHERE project_id != ? AND latitude IS NOT NULL AND longitude IS NOT NULL
            """,
            (project_id,),
        ).fetchall()

        nearby = []
        for p in all_projects:
            dist = haversine_distance_km(olat, olng, p["latitude"], p["longitude"])
            if dist <= radius_km:
                # Fetch median rate if available
                m_rate = cur.execute(
                    """
                    SELECT AVG(rate_per_sqft) FROM unit_transactions
                    WHERE project_id = ? AND status = 'BOOKED' AND rate_per_sqft > 0
                    """,
                    (p["project_id"],),
                ).fetchone()[0]

                nearby.append({
                    "project_id": p["project_id"],
                    "name": p["name"],
                    "promoter_name": p["promoter_name"],
                    "distance_km": dist,
                    "booking_rate_pct": p["booking_rate_pct"],
                    "velocity_ratio": p["velocity_ratio"],
                    "complaints_count": p["complaints_count"] or 0,
                    "avg_registered_rate_sqft": round(m_rate, 0) if m_rate else None,
                })

        nearby.sort(key=lambda x: x["distance_km"])

        # Spatial cluster statistics
        rates = [p["avg_registered_rate_sqft"] for p in nearby if p["avg_registered_rate_sqft"]]
        avg_rate = round(sum(rates) / len(rates), 0) if rates else None
        delayed_cnt = sum(1 for p in nearby if (p["velocity_ratio"] or 1.0) < 0.75)

        return {
            "origin_project_id": project_id,
            "origin_name": origin["name"],
            "radius_km": radius_km,
            "nearby_count": len(nearby),
            "micro_market_avg_rate_sqft": avg_rate,
            "delayed_projects_count": delayed_cnt,
            "delayed_project_ratio": round(delayed_cnt / len(nearby), 2) if nearby else 0.0,
            "nearby_projects": nearby,
        }

    def get_tp_scheme_summary(self, tp_scheme: str, district: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate real estate activity within a municipal Town Planning (TP) scheme."""
        cur = self.con.cursor()
        sql = "SELECT * FROM projects WHERE tp_scheme LIKE ?"
        params: List[Any] = [f"%{tp_scheme}%"]
        if district:
            sql += " AND district = ?"
            params.append(district)

        rows = cur.execute(sql, params).fetchall()
        if not rows:
            return {"tp_scheme": tp_scheme, "projects_count": 0, "projects": []}

        total_units = sum(r["total_units"] or 0 for r in rows)
        booked_units = sum(r["booked_units"] or 0 for r in rows)
        absorption = round(100.0 * booked_units / total_units, 2) if total_units else 0.0

        pids = [r["project_id"] for r in rows]
        placeholders = ",".join("?" for _ in pids)
        rates = cur.execute(
            f"""
            SELECT rate_per_sqft FROM unit_transactions
            WHERE project_id IN ({placeholders}) AND status = 'BOOKED' AND rate_per_sqft > 0
            """,
            pids,
        ).fetchall()
        rate_list = [r[0] for r in rates]
        rate_list.sort()

        median_rate = round(rate_list[len(rate_list) // 2], 0) if rate_list else None

        return {
            "tp_scheme": tp_scheme,
            "district": district or (rows[0]["district"] if rows else None),
            "projects_count": len(rows),
            "total_units": total_units,
            "booked_units": booked_units,
            "absorption_rate_pct": absorption,
            "median_registered_rate_sqft": median_rate,
            "projects": [
                {
                    "project_id": r["project_id"],
                    "name": r["name"],
                    "booking_rate_pct": r["booking_rate_pct"],
                    "velocity_ratio": r["velocity_ratio"],
                }
                for r in rows
            ],
        }

    def close(self) -> None:
        if self._owns_con and self.con:
            self.con.close()
