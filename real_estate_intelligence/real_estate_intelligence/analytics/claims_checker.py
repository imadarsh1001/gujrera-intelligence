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
    ) -> Dict[str, Any]:
        """Compare broker/sales claims against official sworn statutory disclosures."""
        cur = self.con.cursor()
        cur.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        proj = cur.fetchone()
        if not proj:
            return {"error": f"Project {project_id} not found in database"}

        pricing_data = self.pricing.get_project_pricing_summary(project_id)
        overall_stats = pricing_data.get("overall_rate_per_sqft") or {}

        checks = []

        # 1. Price Verification
        if claimed_rate_sqft and overall_stats.get("median"):
            median_rate = overall_stats["median"]
            min_rate = overall_stats["min"]
            max_rate = overall_stats["max"]
            diff_pct = round(100.0 * (claimed_rate_sqft - median_rate) / median_rate, 1)

            if diff_pct > 15.0:
                verdict = "EXAGGERATED / PREMIUM"
                detail = f"Claimed rate of Rs. {claimed_rate_sqft:,.0f}/sq.ft is {diff_pct}% ABOVE the median registered rate of Rs. {median_rate:,.0f}/sq.ft paid by existing buyers."
                guidance = f"Use registered benchmark of Rs. {median_rate:,.0f}/sq.ft to negotiate. The lowest registered unit in this project was booked at Rs. {min_rate:,.0f}/sq.ft."
            elif diff_pct < -10.0:
                verdict = "DISCOUNTED"
                detail = f"Claimed rate of Rs. {claimed_rate_sqft:,.0f}/sq.ft is {abs(diff_pct)}% below the median registered rate of Rs. {median_rate:,.0f}/sq.ft."
                guidance = "Check whether unit is on a lower floor, facing a dead wall, or if additional mandatory charges (parking/amenities) are omitted."
            else:
                verdict = "VERIFIED IN MARKET RANGE"
                detail = f"Claimed rate of Rs. {claimed_rate_sqft:,.0f}/sq.ft is aligned with the median registered rate of Rs. {median_rate:,.0f}/sq.ft."
                guidance = "Rate is consistent with prior registered agreements in this scheme."

            checks.append({
                "metric": "Price per Sq.Ft",
                "claimed": f"Rs. {claimed_rate_sqft:,.0f}",
                "statutory_actual": f"Median Rs. {median_rate:,.0f} (Range Rs. {min_rate:,.0f} - Rs. {max_rate:,.0f})",
                "verdict": verdict,
                "detail": detail,
                "buyer_guidance": guidance,
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
