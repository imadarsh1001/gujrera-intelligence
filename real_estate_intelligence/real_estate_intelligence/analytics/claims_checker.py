"""Broker and developer sales claim verification engine."""

import sqlite3
from typing import Any, Dict, Optional

from .pricing import PricingIntelligence


class SalesClaimVerifier:
    def __init__(self, con: sqlite3.Connection):
        self.con = con
        self.pricing = PricingIntelligence(con)

    def verify_claim(
        self,
        project_id: int,
        claimed_rate_sqft: Optional[float] = None,
        claimed_sold_pct: Optional[float] = None,
        claimed_completion_date: Optional[str] = None,
        asset_class: Optional[str] = "Residential",
    ) -> Dict[str, Any]:
        """Compare broker/sales claims against official sworn statutory disclosures."""
        cur = self.con.cursor()
        cur.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        proj = cur.fetchone()
        if not proj:
            return {"error": f"Project {project_id} not found in database"}

        pricing_data = self.pricing.get_project_pricing_summary(project_id, asset_class=asset_class)
        trailing_stats = pricing_data.get("trailing_four_quarters_rate_per_sqft") or {}
        asset_benchmarks = pricing_data.get("asset_class_benchmarks") or {}
        
        norm_ac = str(asset_class).strip().lower() if asset_class else ""
        is_all_ac = norm_ac in ("", "all", "none")
        if not is_all_ac:
            if norm_ac.startswith("res"):
                ac_stats = asset_benchmarks.get("Residential") or {}
            elif norm_ac.startswith("com"):
                ac_stats = asset_benchmarks.get("Commercial") or asset_benchmarks.get("Commercial_Retail") or {}
            else:
                ac_stats = asset_benchmarks.get(asset_class) or {}
        else:
            ac_stats = pricing_data.get("overall_rate_per_sqft") or {}

        if not ac_stats:
            ac_stats = pricing_data.get("overall_rate_per_sqft") or {}

        checks = []

        # 1. Price Verification
        if claimed_rate_sqft:
            deed_count = 0
            if trailing_stats.get("median") and trailing_stats.get("count", 0) >= 3:
                median_rate = trailing_stats["median"]
                min_rate = trailing_stats.get("min", median_rate)
                max_rate = trailing_stats.get("max", median_rate)
                deed_count = int(trailing_stats.get("count", 0))
                benchmark_type = "Trailing 4-Quarter Booked Median"
                stat_actual_str = f"Trailing 4Q Median Rs. {median_rate:,.0f} (Range Rs. {min_rate:,.0f} - Rs. {max_rate:,.0f}, {deed_count} deeds)"
            elif ac_stats.get("median"):
                median_rate = ac_stats["median"]
                min_rate = ac_stats.get("min", median_rate)
                max_rate = ac_stats.get("max", median_rate)
                deed_count = int(ac_stats.get("count", 0))
                ac_label = "All Assets" if is_all_ac else (asset_class or "Residential")
                benchmark_type = f"{ac_label} Lifetime Median"
                stat_actual_str = f"Lifetime Median Rs. {median_rate:,.0f} (Range Rs. {min_rate:,.0f} - Rs. {max_rate:,.0f}, {deed_count} deeds)"
            else:
                median_rate = None

            if median_rate:
                diff_pct = round(100.0 * (claimed_rate_sqft - median_rate) / median_rate, 1)

                if diff_pct > 15.0:
                    verdict = "EXAGGERATED / PREMIUM"
                    detail = f"Claimed rate of Rs. {claimed_rate_sqft:,.0f}/sq.ft is {diff_pct}% ABOVE the {benchmark_type.lower()} of Rs. {median_rate:,.0f}/sq.ft."
                    guidance = f"Use registered benchmark of Rs. {median_rate:,.0f}/sq.ft to negotiate. The lowest registered deed in this bracket was booked at Rs. {min_rate:,.0f}/sq.ft."
                elif diff_pct < -10.0:
                    verdict = "DISCOUNTED"
                    detail = f"Claimed rate of Rs. {claimed_rate_sqft:,.0f}/sq.ft is {abs(diff_pct)}% below the {benchmark_type.lower()} of Rs. {median_rate:,.0f}/sq.ft."
                    guidance = "Check whether unit is on a lower floor, facing a dead wall, or if additional mandatory charges (parking/amenities) are omitted."
                else:
                    verdict = "VERIFIED IN MARKET RANGE"
                    detail = f"Claimed rate of Rs. {claimed_rate_sqft:,.0f}/sq.ft is aligned ({diff_pct:+.1f}%) with the {benchmark_type.lower()} of Rs. {median_rate:,.0f}/sq.ft."
                    guidance = "Rate is consistent with contemporary registered agreements in this scheme."

                historical_ctx = {
                    "lifetime_median_rate_sqft": ac_stats.get("median"),
                    "lifetime_min_rate_sqft": ac_stats.get("min"),
                    "lifetime_max_rate_sqft": ac_stats.get("max"),
                    "lifetime_total_deeds": ac_stats.get("count", 0),
                }

                checks.append({
                    "metric": "Price per Sq.Ft",
                    "claimed": f"Rs. {claimed_rate_sqft:,.0f}",
                    "statutory_actual": stat_actual_str,
                    "verdict": verdict,
                    "detail": detail,
                    "buyer_guidance": guidance,
                    "benchmark_type": benchmark_type,
                    "trailing_window_start": pricing_data.get("trailing_window_start"),
                    "trailing_window_end": pricing_data.get("trailing_window_end"),
                    "stale_deed_warning": pricing_data.get("stale_deed_warning", False),
                    "empirical_median": round(float(median_rate), 2),
                    "spread_pct": float(diff_pct),
                    "deed_count": deed_count,
                    "historical_context": historical_ctx,
                })

        # 2. Absorption / Sold Out % Verification
        if claimed_sold_pct is not None and proj["booking_rate_pct"] is not None:
            actual_pct = proj["booking_rate_pct"]
            unsold_units = proj["unbooked_units"] or 0
            diff = claimed_sold_pct - actual_pct

            if diff > 10.0:
                verdict = "ARTIFICIAL SCARCITY"
                detail = f"Broker claimed {claimed_sold_pct}% sold, but official filing reports only {actual_pct:.1f}% booked. {unsold_units} units remain unsold."
                guidance = "Do not rush. The developer has significant inventory overhang and is creating false urgency to prevent price bargaining."
            else:
                verdict = "VERIFIED ACCURATE"
                detail = f"Reported statutory booking rate is {actual_pct:.1f}%, consistent with claim."
                guidance = "Inventory claim is reliable."

            checks.append({
                "metric": "Booking & Inventory Absorption",
                "claimed": f"{claimed_sold_pct}% Sold",
                "statutory_actual": f"{actual_pct:.1f}% Booked ({unsold_units} Units Unsold)",
                "verdict": verdict,
                "detail": detail,
                "buyer_guidance": guidance,
            })

        # 3. Handover Date Verification
        if claimed_completion_date and proj["completion_date"]:
            statutory_date = str(proj["completion_date"])[:10]
            claimed_str = str(claimed_completion_date)[:10]

            if claimed_str < statutory_date:
                verdict = "AGGRESSIVE SALES PROMISE"
                detail = f"Broker promised handover by {claimed_str}, but statutory GujRERA registered deadline is {statutory_date}."
                guidance = f"The promoter is legally protected under RERA until {statutory_date}. You cannot claim delayed possession compensation for any delay prior to {statutory_date}."
            else:
                verdict = "ALIGNED WITH RERA"
                detail = f"Statutory completion date is {statutory_date}."
                guidance = "Possession timeline aligns with legal commitments."

            checks.append({
                "metric": "Possession & Handover Deadline",
                "claimed": claimed_str,
                "statutory_actual": statutory_date,
                "verdict": verdict,
                "detail": detail,
                "buyer_guidance": guidance,
            })

        return {
            "project_id": project_id,
            "project_name": proj["name"],
            "verification_checks": checks,
        }
