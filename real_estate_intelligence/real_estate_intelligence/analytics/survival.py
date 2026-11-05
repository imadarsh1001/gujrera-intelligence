"""Completion Delay Survival Model using Cox Proportional Hazards & Kaplan-Meier Estimation.

Models time-to-completion, estimates handover delivery probabilities across project lifecycles,
and forecasts schedule delay percentiles (50th, 75th, 90th percentile delivery dates)
based on construction velocity, expenditure burn, and regulatory friction.
"""

import datetime
import math
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


class CompletionDelaySurvivalModel:
    """Semi-parametric Cox Proportional Hazards and time-to-event survival model for GujRERA projects."""

    def __init__(self, learning_rate: float = 0.05, max_iter: int = 100):
        self.learning_rate = learning_rate
        self.max_iter = max_iter
        self.feature_names: List[str] = [
            "velocity_ratio",
            "incurred_cost_ratio",
            "has_complaints",
            "default_quarters",
        ]
        self.beta: List[float] = [0.0] * len(self.feature_names)
        self.baseline_hazard: List[Tuple[float, float]] = []  # List of (time_months, d_H0)
        self.training_durations: List[float] = []
        self.training_events: List[int] = []
        self.training_covariates: List[List[float]] = []
        self.training_project_ids: List[int] = []
        self._trained = False

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime.date]:
        if not date_str:
            return None
        try:
            return datetime.datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    def fit(
        self,
        durations: List[float],
        events: List[int],
        covariates: List[List[float]],
        project_ids: Optional[List[int]] = None,
    ) -> "CompletionDelaySurvivalModel":
        """Fit Cox Proportional Hazards model using partial likelihood gradient ascent."""
        n = len(durations)
        if n == 0 or len(events) != n or len(covariates) != n:
            raise ValueError("Mismatched durations, events, or covariates")

        self.training_durations = durations
        self.training_events = events
        self.training_covariates = covariates
        self.training_project_ids = project_ids or list(range(n))

        k = len(self.feature_names)
        beta = [0.0] * k

        # Sort indices by duration ascending
        sorted_indices = sorted(range(n), key=lambda i: durations[i])

        # Gradient ascent to maximize partial log-likelihood:
        # l(beta) = sum_{i: E_i=1} [ beta^T X_i - ln(sum_{j in R(T_i)} exp(beta^T X_j)) ]
        for _ in range(self.max_iter):
            grad = [0.0] * k

            for idx in sorted_indices:
                if events[idx] == 0:
                    continue

                t_i = durations[idx]
                x_i = covariates[idx]

                # Risk set R(t_i): all projects with duration >= t_i
                risk_set = [j for j in sorted_indices if durations[j] >= t_i]

                # exp(beta^T X_j)
                exp_scores = []
                for j in risk_set:
                    score = sum(beta[m] * covariates[j][m] for m in range(k))
                    # Clip score to prevent exp overflow
                    clipped = max(-20.0, min(20.0, score))
                    exp_scores.append(math.exp(clipped))

                denom = sum(exp_scores)
                if denom <= 0:
                    continue

                for m in range(k):
                    numer = sum(covariates[risk_set[r_idx]][m] * exp_scores[r_idx] for r_idx in range(len(risk_set)))
                    grad[m] += x_i[m] - (numer / denom)

            # Check convergence
            grad_norm = math.sqrt(sum(g ** 2 for g in grad))
            if grad_norm < 1e-5:
                break

            # Gradient update with L2 regularization penalty
            l2_reg = 0.05
            for m in range(k):
                beta[m] += self.learning_rate * (grad[m] - l2_reg * beta[m])

        self.beta = beta

        # Breslow Estimator for Baseline Cumulative Hazard H_0(t)
        self.baseline_hazard = []
        event_indices = [i for i in sorted_indices if events[i] == 1]
        unique_event_times = sorted(set(durations[i] for i in event_indices))

        cum_hazard = 0.0
        for t_val in unique_event_times:
            # Number of events at time t_val
            d_i = sum(1 for i in event_indices if abs(durations[i] - t_val) < 1e-4)
            risk_set = [j for j in sorted_indices if durations[j] >= t_val]

            denom = 0.0
            for j in risk_set:
                score = sum(self.beta[m] * covariates[j][m] for m in range(k))
                clipped = max(-20.0, min(20.0, score))
                denom += math.exp(clipped)

            step = d_i / max(1e-9, denom)
            cum_hazard += step
            self.baseline_hazard.append((t_val, cum_hazard))

        self._trained = True
        return self

    def predict_hazard_ratio(self, x: List[float]) -> float:
        """Calculate relative hazard ratio: exp(beta^T X). High ratio indicates faster event/completion rate."""
        if not self._trained:
            raise RuntimeError("Model is not trained.")
        score = sum(self.beta[m] * x[m] for m in range(len(self.beta)))
        clipped = max(-20.0, min(20.0, score))
        return math.exp(clipped)

    def predict_survival_probability(self, x: List[float], t_months: float) -> float:
        """Estimate survival probability S(t) = P(Completion > t | X)."""
        if not self._trained or not self.baseline_hazard:
            return 1.0

        hr = self.predict_hazard_ratio(x)

        # Look up baseline cumulative hazard H_0(t)
        h0 = 0.0
        for t_b, h_cum in self.baseline_hazard:
            if t_b <= t_months:
                h0 = h_cum
            else:
                break

        # Extrapolate linearly if t_months > max observation
        if t_months > self.baseline_hazard[-1][0]:
            last_t, last_h = self.baseline_hazard[-1]
            rate = last_h / max(1.0, last_t)
            h0 = last_h + rate * (t_months - last_t)

        cum_hazard_project = h0 * hr
        # S(t) = exp(-H(t))
        return math.exp(-max(0.0, cum_hazard_project))

    def forecast_project_timeline(
        self,
        project_id: int,
        start_date_str: str,
        reg_completion_date_str: str,
        covariates: List[float],
        name: str = "",
    ) -> Dict[str, Any]:
        """Forecast milestone delivery percentiles and schedule delay probability for a project."""
        start_date = self._parse_date(start_date_str)
        reg_date = self._parse_date(reg_completion_date_str)

        if not start_date or not reg_date:
            return {"error": "Invalid start or completion dates"}

        scheduled_duration_months = max(1.0, (reg_date - start_date).days / 30.4375)
        hr = self.predict_hazard_ratio(covariates)

        # Find delivery percentiles: t where P(Completion <= t) = 1 - S(t) >= target
        def find_percentile_month(target_pct: float) -> float:
            target_surv = 1.0 - target_pct
            # Search from 1 month to 150 months
            for step in range(1, 1500):
                t_m = step * 0.1
                surv = self.predict_survival_probability(covariates, t_m)
                if surv <= target_surv:
                    return round(t_m, 1)
            return round(scheduled_duration_months * 1.5, 1)

        t_p50 = find_percentile_month(0.50)  # Median completion time
        t_p75 = find_percentile_month(0.75)  # Conservative completion time
        t_p90 = find_percentile_month(0.90)  # High-confidence completion time

        est_p50_date = start_date + datetime.timedelta(days=int(t_p50 * 30.4375))
        est_p75_date = start_date + datetime.timedelta(days=int(t_p75 * 30.4375))
        est_p90_date = start_date + datetime.timedelta(days=int(t_p90 * 30.4375))

        delay_months_p50 = max(0.0, round(t_p50 - scheduled_duration_months, 1))

        # Risk classification
        if delay_months_p50 <= 0.0 and covariates[0] >= 1.0:
            risk_label = "ON_TRACK"
            confidence_note = "Project construction velocity outpaces schedule timeline."
        elif delay_months_p50 <= 4.0:
            risk_label = "MODERATE_DELAY"
            confidence_note = f"Mild velocity lag indicates estimated completion slippage of ~{delay_months_p50} months."
        else:
            risk_label = "HIGH_DELAY_RISK"
            confidence_note = f"Critical construction friction indicates projected delay of {delay_months_p50}+ months beyond registered RERA deadline."

        # Generate discrete points for Chart.js survival curve (0 to 120 months)
        curve_points = []
        for m in range(0, 125, 3):
            s_val = self.predict_survival_probability(covariates, float(m))
            curve_points.append({
                "month": m,
                "survival_prob": round(s_val, 4),
                "completion_prob": round(1.0 - s_val, 4),
            })

        return {
            "project_id": project_id,
            "project_name": name,
            "scheduled_start_date": start_date.isoformat(),
            "registered_completion_date": reg_date.isoformat(),
            "scheduled_duration_months": round(scheduled_duration_months, 1),
            "hazard_ratio": round(hr, 3),
            "delay_risk_label": risk_label,
            "forecasted_delay_months": delay_months_p50,
            "confidence_assessment": confidence_note,
            "forecasted_handover_dates": {
                "p50_median_expected_date": est_p50_date.isoformat(),
                "p50_duration_months": t_p50,
                "p75_conservative_date": est_p75_date.isoformat(),
                "p75_duration_months": t_p75,
                "p90_high_confidence_date": est_p90_date.isoformat(),
                "p90_duration_months": t_p90,
            },
            "survival_curve": curve_points,
        }

    def calculate_concordance_index(self) -> float:
        """Harrell's Concordance Index (C-index) for evaluating survival model discrimination.
        
        Pairs (i, j) where duration_i < duration_j and event_i = 1 are evaluated.
        Pair is concordant if hazard_i > hazard_j.
        """
        if not self._trained:
            return 0.0

        n = len(self.training_durations)
        concordant = 0
        admissible = 0

        hazards = [self.predict_hazard_ratio(self.training_covariates[i]) for i in range(n)]

        for i in range(n):
            if self.training_events[i] != 1:
                continue  # Censored events cannot be the earlier failure in an admissible pair
            for j in range(n):
                if self.training_durations[i] < self.training_durations[j]:
                    admissible += 1
                    if hazards[i] > hazards[j]:
                        concordant += 1
                    elif abs(hazards[i] - hazards[j]) < 1e-6:
                        concordant += 0.5

        return round(concordant / max(1, admissible), 4)

    def train_from_db(
        self, con: sqlite3.Connection, as_of_date_str: str = "2026-10-15"
    ) -> "CompletionDelaySurvivalModel":
        """Extract project timelines, milestones, and covariates from database and fit model."""
        cur = con.cursor()
        query = """
        SELECT project_id, name, start_date, completion_date, latest_form_one_progress_pct,
               velocity_ratio, estimated_cost_inr, incurred_cost_inr, complaints_count,
               default_quarters_count, bu_status
        FROM projects
        """
        rows = cur.fetchall() if cur.execute(query) else []
        if not rows:
            raise ValueError("No project records found in database")

        now = self._parse_date(as_of_date_str) or datetime.date(2026, 10, 15)

        durations: List[float] = []
        events: List[int] = []
        covariates: List[List[float]] = []
        p_ids: List[int] = []

        for r in rows:
            start = self._parse_date(r[2])
            if not start:
                continue

            # Event = 1 if BU approved or progress >= 99%
            is_completed = (r[4] or 0.0) >= 99.0 or ("Approved" in str(r[10] or ""))
            event = 1 if is_completed else 0

            # Duration in months from start date to observation or completion
            t_months = max(1.0, (now - start).days / 30.4375)

            vel = float(r[5] or 0.0)
            est_cost = float(r[6] or 1.0)
            incurred = float(r[7] or 0.0)
            cost_r = incurred / max(1.0, est_cost)
            complaints = 1.0 if (r[8] or 0) > 0 else 0.0
            def_quarters = float(r[9] or 0)

            cov = [vel, min(1.5, cost_r), complaints, def_quarters]

            durations.append(round(t_months, 2))
            events.append(event)
            covariates.append(cov)
            p_ids.append(r[0])

        return self.fit(durations, events, covariates, p_ids)

    def forecast_project_by_id(self, con: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
        """Convenience method to query a project from SQLite and produce its completion forecast."""
        if not self._trained:
            self.train_from_db(con)

        row = con.execute(
            """
            SELECT project_id, name, start_date, completion_date, latest_form_one_progress_pct,
                   velocity_ratio, estimated_cost_inr, incurred_cost_inr, complaints_count,
                   default_quarters_count, bu_status
            FROM projects WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if not row:
            return {"error": f"Project {project_id} not found"}

        vel = float(row[5] or 0.0)
        est_cost = float(row[6] or 1.0)
        incurred = float(row[7] or 0.0)
        cost_r = incurred / max(1.0, est_cost)
        complaints = 1.0 if (row[8] or 0) > 0 else 0.0
        def_quarters = float(row[9] or 0)

        cov = [vel, min(1.5, cost_r), complaints, def_quarters]
        return self.forecast_project_timeline(
            project_id=row[0],
            start_date_str=row[2],
            reg_completion_date_str=row[3],
            covariates=cov,
            name=row[1],
        )
