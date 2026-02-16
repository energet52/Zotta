"""Scorecard Performance Monitoring — Gini, KS, PSI, CSI, IV tracking,
vintage analysis, score band analysis, and health alerts.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_, case as sa_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scorecard import (
    Scorecard, ScorecardStatus, ScoreResult,
    ScorecardPerformanceSnapshot, ScorecardAlert,
)
from app.models.loan import LoanApplication, LoanStatus
from app.models.payment import PaymentSchedule, ScheduleStatus

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# 1. Gini Coefficient
# ────────────────────────────────────────────────────────────────────

def calculate_gini(scores: list[float], defaults: list[bool]) -> float:
    """Calculate Gini coefficient from scores and default flags.

    Gini = 2 * AUC - 1
    """
    if len(scores) < 2:
        return 0.0

    paired = list(zip(scores, defaults))
    paired.sort(key=lambda x: x[0])

    n = len(paired)
    n_bad = sum(1 for _, d in paired if d)
    n_good = n - n_bad

    if n_bad == 0 or n_good == 0:
        return 0.0

    cum_bad = 0
    auc = 0.0

    for score, is_default in paired:
        if is_default:
            cum_bad += 1
        else:
            auc += cum_bad

    auc /= (n_bad * n_good)
    gini = 2 * auc - 1
    return round(abs(gini), 4)


# ────────────────────────────────────────────────────────────────────
# 2. KS Statistic
# ────────────────────────────────────────────────────────────────────

def calculate_ks(scores: list[float], defaults: list[bool]) -> float:
    """Kolmogorov-Smirnov statistic — max separation between good/bad CDFs."""
    if len(scores) < 2:
        return 0.0

    paired = sorted(zip(scores, defaults), key=lambda x: x[0])
    n_bad = sum(1 for _, d in paired if d)
    n_good = len(paired) - n_bad

    if n_bad == 0 or n_good == 0:
        return 0.0

    cum_bad = 0
    cum_good = 0
    max_ks = 0.0

    for _, is_default in paired:
        if is_default:
            cum_bad += 1
        else:
            cum_good += 1
        ks = abs(cum_bad / n_bad - cum_good / n_good)
        max_ks = max(max_ks, ks)

    return round(max_ks, 4)


# ────────────────────────────────────────────────────────────────────
# 3. PSI (Population Stability Index)
# ────────────────────────────────────────────────────────────────────

def calculate_psi(
    expected_pcts: list[float],
    actual_pcts: list[float],
) -> float:
    """Calculate PSI between two distributions (as percentage arrays).

    PSI = Σ (actual_i - expected_i) * ln(actual_i / expected_i)
    """
    if len(expected_pcts) != len(actual_pcts):
        return 0.0

    psi = 0.0
    for exp, act in zip(expected_pcts, actual_pcts):
        exp = max(exp, 0.001)  # avoid log(0)
        act = max(act, 0.001)
        psi += (act - exp) * math.log(act / exp)

    return round(abs(psi), 4)


def build_score_distribution_pcts(
    scores: list[float],
    min_score: float,
    max_score: float,
    n_bands: int = 10,
) -> list[float]:
    """Build percentage distribution across score bands."""
    if not scores:
        return [0.0] * n_bands

    band_size = (max_score - min_score) / n_bands
    counts = [0] * n_bands
    total = len(scores)

    for s in scores:
        idx = int((s - min_score) / band_size)
        idx = max(0, min(idx, n_bands - 1))
        counts[idx] += 1

    return [c / total if total > 0 else 0.0 for c in counts]


# ────────────────────────────────────────────────────────────────────
# 4. Information Value (IV)
# ────────────────────────────────────────────────────────────────────

def calculate_iv(
    bin_good_pcts: list[float],
    bin_bad_pcts: list[float],
) -> float:
    """Calculate Information Value for a characteristic.

    IV = Σ (good_pct_i - bad_pct_i) * ln(good_pct_i / bad_pct_i)
    """
    iv = 0.0
    for g, b in zip(bin_good_pcts, bin_bad_pcts):
        g = max(g, 0.001)
        b = max(b, 0.001)
        iv += (g - b) * math.log(g / b)
    return round(abs(iv), 4)


# ────────────────────────────────────────────────────────────────────
# 5. Generate Performance Snapshot
# ────────────────────────────────────────────────────────────────────

async def generate_performance_snapshot(
    scorecard_id: int,
    db: AsyncSession,
    period_months: int = 6,
) -> ScorecardPerformanceSnapshot:
    """Generate a performance snapshot for a scorecard."""
    today = date.today()
    cutoff = today - timedelta(days=period_months * 30)

    # Get score results for this scorecard
    scores_q = (
        select(ScoreResult)
        .where(
            ScoreResult.scorecard_id == scorecard_id,
            ScoreResult.scored_at >= datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=timezone.utc),
        )
    )
    score_results = (await db.execute(scores_q)).scalars().all()

    if not score_results:
        # Check for existing empty snapshot today
        existing_empty = (await db.execute(
            select(ScorecardPerformanceSnapshot).where(
                ScorecardPerformanceSnapshot.scorecard_id == scorecard_id,
                ScorecardPerformanceSnapshot.snapshot_date == today,
            )
        )).scalar_one_or_none()
        if existing_empty:
            return existing_empty
        snap = ScorecardPerformanceSnapshot(
            scorecard_id=scorecard_id, snapshot_date=today,
            total_scored=0, total_approved=0, total_declined=0, total_review=0,
        )
        db.add(snap)
        await db.flush()
        return snap

    # Count decisions
    total = len(score_results)
    approved = sum(1 for s in score_results if s.decision == "AUTO_APPROVE")
    declined = sum(1 for s in score_results if s.decision == "AUTO_DECLINE")
    review = sum(1 for s in score_results if s.decision == "MANUAL_REVIEW")

    # Get scores and default flags
    scores_list: list[float] = []
    defaults_list: list[bool] = []

    for sr in score_results:
        scores_list.append(sr.total_score)
        # Check if loan defaulted (has overdue payments > 90 days)
        overdue_q = (
            select(func.count())
            .where(
                PaymentSchedule.loan_application_id == sr.loan_application_id,
                PaymentSchedule.status == ScheduleStatus.OVERDUE,
                PaymentSchedule.due_date < today - timedelta(days=90),
            )
        )
        overdue_count = (await db.execute(overdue_q)).scalar() or 0
        defaults_list.append(overdue_count > 0)

    # Calculate metrics
    gini = calculate_gini(scores_list, defaults_list)
    ks = calculate_ks(scores_list, defaults_list)

    # Default rate
    n_defaults = sum(1 for d in defaults_list if d)
    default_rate = n_defaults / total if total > 0 else 0

    # Average scores
    avg_score = sum(scores_list) / total if total > 0 else 0
    default_scores = [s for s, d in zip(scores_list, defaults_list) if d]
    non_default_scores = [s for s, d in zip(scores_list, defaults_list) if not d]
    avg_default = sum(default_scores) / len(default_scores) if default_scores else None
    avg_non_default = sum(non_default_scores) / len(non_default_scores) if non_default_scores else None

    # Get scorecard for score range
    sc_q = select(Scorecard).where(Scorecard.id == scorecard_id)
    sc = (await db.execute(sc_q)).scalar_one_or_none()
    min_s = sc.min_score if sc else 100
    max_s = sc.max_score if sc else 850

    # Score distribution
    n_bands = 10
    band_size = (max_s - min_s) / n_bands
    distribution = []
    for i in range(n_bands):
        lower = min_s + i * band_size
        upper = lower + band_size
        count = sum(1 for s in scores_list if lower <= s < upper)
        distribution.append({
            "band": f"{int(lower)}-{int(upper)}",
            "count": count,
            "pct": round(count / total * 100, 1),
        })

    # Score band analysis
    bands_analysis = []
    for i in range(n_bands):
        lower = min_s + i * band_size
        upper = lower + band_size
        band_scores = [(s, d) for s, d in zip(scores_list, defaults_list) if lower <= s < upper]
        if band_scores:
            band_total = len(band_scores)
            band_defaults = sum(1 for _, d in band_scores if d)
            band_approved = sum(
                1 for sr in score_results
                if lower <= sr.total_score < upper and sr.decision == "AUTO_APPROVE"
            )
            bands_analysis.append({
                "band": f"{int(lower)}-{int(upper)}",
                "count": band_total,
                "pct_of_total": round(band_total / total * 100, 1),
                "approved": band_approved,
                "approval_rate": round(band_approved / band_total * 100, 1) if band_total > 0 else 0,
                "default_count": band_defaults,
                "default_rate": round(band_defaults / band_total * 100, 2) if band_total > 0 else 0,
            })

    # PSI (compare first half vs second half as a simple baseline)
    half = len(scores_list) // 2
    if half > 0:
        first_half = scores_list[:half]
        second_half = scores_list[half:]
        exp_pcts = build_score_distribution_pcts(first_half, min_s, max_s)
        act_pcts = build_score_distribution_pcts(second_half, min_s, max_s)
        psi = calculate_psi(exp_pcts, act_pcts)
    else:
        psi = 0.0

    # Check existing snapshot for today
    existing_q = select(ScorecardPerformanceSnapshot).where(
        ScorecardPerformanceSnapshot.scorecard_id == scorecard_id,
        ScorecardPerformanceSnapshot.snapshot_date == today,
    )
    existing = (await db.execute(existing_q)).scalar_one_or_none()

    if existing:
        snap = existing
    else:
        snap = ScorecardPerformanceSnapshot(scorecard_id=scorecard_id, snapshot_date=today)
        db.add(snap)

    snap.total_scored = total
    snap.total_approved = approved
    snap.total_declined = declined
    snap.total_review = review
    snap.approval_rate = round(approved / total * 100, 1) if total > 0 else 0
    snap.default_rate = round(default_rate * 100, 2)
    snap.gini_coefficient = gini
    snap.ks_statistic = ks
    snap.auc_roc = round((gini + 1) / 2, 4)  # AUC = (Gini + 1) / 2
    snap.psi = psi
    snap.avg_score = round(avg_score, 1)
    snap.avg_score_defaulters = round(avg_default, 1) if avg_default else None
    snap.avg_score_non_defaulters = round(avg_non_default, 1) if avg_non_default else None
    snap.score_distribution = distribution
    snap.score_band_analysis = bands_analysis

    await db.flush()
    return snap


# ────────────────────────────────────────────────────────────────────
# 6. Champion vs Challenger Comparison
# ────────────────────────────────────────────────────────────────────

async def champion_challenger_comparison(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Side-by-side comparison of all active scorecards."""
    scorecards_q = (
        select(Scorecard)
        .where(Scorecard.status.in_([
            ScorecardStatus.CHAMPION, ScorecardStatus.CHALLENGER, ScorecardStatus.SHADOW,
        ]))
    )
    scorecards = (await db.execute(scorecards_q)).scalars().all()

    comparisons = []
    for sc in scorecards:
        # Latest snapshot
        snap_q = (
            select(ScorecardPerformanceSnapshot)
            .where(ScorecardPerformanceSnapshot.scorecard_id == sc.id)
            .order_by(ScorecardPerformanceSnapshot.snapshot_date.desc())
            .limit(1)
        )
        snap = (await db.execute(snap_q)).scalar_one_or_none()

        comparisons.append({
            "scorecard_id": sc.id,
            "name": sc.name,
            "version": sc.version,
            "status": sc.status.value,
            "traffic_pct": sc.traffic_pct,
            "applications_scored": snap.total_scored if snap else 0,
            "approval_rate": snap.approval_rate if snap else None,
            "default_rate": snap.default_rate if snap else None,
            "avg_score": snap.avg_score if snap else None,
            "avg_score_defaulters": snap.avg_score_defaulters if snap else None,
            "avg_score_non_defaulters": snap.avg_score_non_defaulters if snap else None,
            "gini_coefficient": snap.gini_coefficient if snap else None,
            "ks_statistic": snap.ks_statistic if snap else None,
            "auc_roc": snap.auc_roc if snap else None,
            "psi": snap.psi if snap else None,
        })

    return comparisons


# ────────────────────────────────────────────────────────────────────
# 7. Score Band Analysis (detailed)
# ────────────────────────────────────────────────────────────────────

async def get_score_band_analysis(
    scorecard_id: int,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Detailed score band analysis for a scorecard."""
    snap_q = (
        select(ScorecardPerformanceSnapshot)
        .where(ScorecardPerformanceSnapshot.scorecard_id == scorecard_id)
        .order_by(ScorecardPerformanceSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = (await db.execute(snap_q)).scalar_one_or_none()

    if snap and snap.score_band_analysis:
        return snap.score_band_analysis
    return []


# ────────────────────────────────────────────────────────────────────
# 8. Health Alert Checks
# ────────────────────────────────────────────────────────────────────

async def check_scorecard_health(
    scorecard_id: int,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Run health checks on a scorecard and generate alerts if thresholds breached."""
    snap_q = (
        select(ScorecardPerformanceSnapshot)
        .where(ScorecardPerformanceSnapshot.scorecard_id == scorecard_id)
        .order_by(ScorecardPerformanceSnapshot.snapshot_date.desc())
        .limit(3)
    )
    snaps = (await db.execute(snap_q)).scalars().all()

    if not snaps:
        return []

    latest = snaps[0]
    sc = (await db.execute(select(Scorecard).where(Scorecard.id == scorecard_id))).scalar_one_or_none()
    sc_name = sc.name if sc else f"Scorecard #{scorecard_id}"

    alerts: list[dict] = []

    # PSI breach
    if latest.psi is not None:
        if latest.psi > 0.25:
            alerts.append({
                "type": "psi_breach", "severity": "critical",
                "title": f"PSI Critical: {sc_name}",
                "message": f"Score distribution has shifted significantly (PSI = {latest.psi}). Population may have changed.",
                "recommendation": "Review characteristic-level stability. Consider recalibrating scorecard bins.",
            })
        elif latest.psi > 0.1:
            alerts.append({
                "type": "psi_breach", "severity": "warning",
                "title": f"PSI Warning: {sc_name}",
                "message": f"Score distribution showing drift (PSI = {latest.psi}).",
                "recommendation": "Monitor closely. Review if characteristic distributions have shifted.",
            })

    # Gini decline
    if len(snaps) >= 2 and snaps[0].gini_coefficient and snaps[1].gini_coefficient:
        gini_change = snaps[0].gini_coefficient - snaps[1].gini_coefficient
        if gini_change < -0.05:
            alerts.append({
                "type": "gini_decline", "severity": "warning",
                "title": f"Gini Decline: {sc_name}",
                "message": f"Discrimination power declined from {snaps[1].gini_coefficient} to {snaps[0].gini_coefficient}.",
                "recommendation": "The model may be losing predictive accuracy. Consider revalidation.",
            })

    # Default rate spike
    if latest.default_rate and latest.default_rate > 5.0:
        alerts.append({
            "type": "default_spike", "severity": "warning",
            "title": f"Default Rate Alert: {sc_name}",
            "message": f"Observed default rate is {latest.default_rate}%, exceeding expected range.",
            "recommendation": "Consider tightening cutoff scores or investigating specific segments.",
        })

    # Approval rate drift
    if len(snaps) >= 2 and snaps[0].approval_rate and snaps[1].approval_rate:
        drift = snaps[0].approval_rate - snaps[1].approval_rate
        if abs(drift) > 10:
            direction = "increased" if drift > 0 else "decreased"
            alerts.append({
                "type": "approval_drift", "severity": "warning",
                "title": f"Approval Rate Drift: {sc_name}",
                "message": f"Approval rate has {direction} from {snaps[1].approval_rate}% to {snaps[0].approval_rate}%.",
                "recommendation": "Investigate score inflation/deflation or population shift.",
            })

    # Save alerts to DB
    for alert_data in alerts:
        alert = ScorecardAlert(
            scorecard_id=scorecard_id,
            alert_type=alert_data["type"],
            severity=alert_data["severity"],
            title=alert_data["title"],
            message=alert_data["message"],
            recommendation=alert_data.get("recommendation"),
        )
        db.add(alert)

    await db.flush()
    return alerts


# ────────────────────────────────────────────────────────────────────
# 9. Vintage Analysis
# ────────────────────────────────────────────────────────────────────

async def get_vintage_analysis(
    scorecard_id: int,
    db: AsyncSession,
    n_months: int = 12,
) -> list[dict[str, Any]]:
    """Vintage analysis: default rate by origination month."""
    today = date.today()
    vintages = []

    for i in range(n_months, 0, -1):
        month_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1)

        # Count scored in this vintage
        scored_q = (
            select(func.count())
            .where(
                ScoreResult.scorecard_id == scorecard_id,
                ScoreResult.scored_at >= datetime(month_start.year, month_start.month, month_start.day, tzinfo=timezone.utc),
                ScoreResult.scored_at < datetime(month_end.year, month_end.month, month_end.day, tzinfo=timezone.utc),
            )
        )
        scored = (await db.execute(scored_q)).scalar() or 0

        # Count defaults from those applications
        default_q = (
            select(func.count(func.distinct(ScoreResult.loan_application_id)))
            .where(
                ScoreResult.scorecard_id == scorecard_id,
                ScoreResult.scored_at >= datetime(month_start.year, month_start.month, month_start.day, tzinfo=timezone.utc),
                ScoreResult.scored_at < datetime(month_end.year, month_end.month, month_end.day, tzinfo=timezone.utc),
                ScoreResult.loan_application_id.in_(
                    select(PaymentSchedule.loan_application_id)
                    .where(
                        PaymentSchedule.status == ScheduleStatus.OVERDUE,
                        PaymentSchedule.due_date < today - timedelta(days=90),
                    )
                    .distinct()
                ),
            )
        )
        defaults = (await db.execute(default_q)).scalar() or 0

        vintages.append({
            "vintage": month_start.strftime("%Y-%m"),
            "originated": scored,
            "defaulted": defaults,
            "default_rate": round(defaults / scored * 100, 2) if scored > 0 else 0,
            "months_on_book": i,
        })

    return vintages


# ────────────────────────────────────────────────────────────────────
# 10. Performance History (trend)
# ────────────────────────────────────────────────────────────────────

async def get_performance_history(
    scorecard_id: int,
    db: AsyncSession,
    n_snapshots: int = 12,
) -> list[dict[str, Any]]:
    """Get historical performance snapshots for trend display."""
    q = (
        select(ScorecardPerformanceSnapshot)
        .where(ScorecardPerformanceSnapshot.scorecard_id == scorecard_id)
        .order_by(ScorecardPerformanceSnapshot.snapshot_date.desc())
        .limit(n_snapshots)
    )
    snaps = (await db.execute(q)).scalars().all()
    return [
        {
            "date": s.snapshot_date.isoformat(),
            "total_scored": s.total_scored,
            "approval_rate": s.approval_rate,
            "default_rate": s.default_rate,
            "gini": s.gini_coefficient,
            "ks": s.ks_statistic,
            "psi": s.psi,
            "avg_score": s.avg_score,
        }
        for s in reversed(snaps)
    ]
