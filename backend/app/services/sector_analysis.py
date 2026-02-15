"""Sector Analysis Service — computes portfolio concentration and risk metrics.

Used by the sector analysis API endpoints to generate real-time dashboard
data, sector-level risk profiles, roll-rate analysis, vintage analysis,
and stress-testing scenarios.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, func, case, and_, or_, extract, literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.payment import PaymentSchedule, ScheduleStatus
from app.models.sector_analysis import (
    SectorPolicy,
    SectorPolicyStatus,
    SectorAlert,
    SectorAlertRule,
    SectorAlertSeverity,
    SectorAlertStatus,
    SectorSnapshot,
    SectorMacroIndicator,
    SECTOR_TAXONOMY,
)


# ── Active loan statuses (disbursed = live) ─────────────────

ACTIVE_STATUSES = [LoanStatus.DISBURSED]

DPD_30 = 30
DPD_60 = 60
DPD_90 = 90


def _sector_col():
    """Return the employer_sector column reference for joins."""
    return ApplicantProfile.employer_sector


# ── Helpers ──────────────────────────────────────────────────

def _pct(part: float, total: float) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 2)


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return round(a / b, 2)


# ── Portfolio Dashboard (FR-2) ───────────────────────────────

async def get_portfolio_dashboard(db: AsyncSession) -> dict[str, Any]:
    """Compute real-time sector distribution and concentration metrics."""

    # Join loans with profiles to get sector
    base = (
        select(
            func.coalesce(ApplicantProfile.employer_sector, "MISSING").label("sector"),
            func.count(LoanApplication.id).label("loan_count"),
            func.coalesce(func.sum(LoanApplication.amount_approved), 0).label("total_outstanding"),
            func.coalesce(func.avg(LoanApplication.amount_approved), 0).label("avg_loan_size"),
        )
        .join(ApplicantProfile, ApplicantProfile.user_id == LoanApplication.applicant_id)
        .where(LoanApplication.status.in_(ACTIVE_STATUSES))
        .group_by(func.coalesce(ApplicantProfile.employer_sector, "MISSING"))
    )

    result = await db.execute(base)
    rows = result.all()

    # Compute totals
    total_outstanding = sum(float(r.total_outstanding) for r in rows)
    total_loan_count = sum(r.loan_count for r in rows)

    sectors: list[dict] = []
    for r in rows:
        sectors.append({
            "sector": r.sector,
            "loan_count": r.loan_count,
            "total_outstanding": float(r.total_outstanding),
            "avg_loan_size": round(float(r.avg_loan_size), 2),
            "exposure_pct": _pct(float(r.total_outstanding), total_outstanding),
        })

    # Sort by exposure descending
    sectors.sort(key=lambda s: s["total_outstanding"], reverse=True)

    # Load policies for concentration limit indicators
    policy_q = await db.execute(
        select(SectorPolicy).where(SectorPolicy.status == SectorPolicyStatus.ACTIVE)
    )
    policies = {p.sector: p for p in policy_q.scalars().all()}

    # Attach traffic-light status to each sector
    for s in sectors:
        policy = policies.get(s["sector"])
        cap = policy.exposure_cap_pct if policy else None
        if cap is None:
            s["concentration_status"] = "green"
        elif s["exposure_pct"] >= cap:
            s["concentration_status"] = "red"
        elif s["exposure_pct"] >= cap * 0.8:
            s["concentration_status"] = "amber"
        else:
            s["concentration_status"] = "green"

        s["risk_rating"] = policy.risk_rating.value if policy else "medium"
        s["on_watchlist"] = policy.on_watchlist if policy else False
        s["origination_paused"] = policy.origination_paused if policy else False
        s["exposure_cap_pct"] = cap

    # Recent alerts (top 10)
    alerts_q = await db.execute(
        select(SectorAlert)
        .where(SectorAlert.status.in_([SectorAlertStatus.NEW, SectorAlertStatus.ACKNOWLEDGED]))
        .order_by(SectorAlert.created_at.desc())
        .limit(10)
    )
    recent_alerts = [
        {
            "id": a.id,
            "sector": a.sector,
            "severity": a.severity.value if hasattr(a.severity, 'value') else a.severity,
            "title": a.title,
            "metric_value": a.metric_value,
            "threshold_value": a.threshold_value,
            "status": a.status.value if hasattr(a.status, 'value') else a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts_q.scalars().all()
    ]

    return {
        "total_outstanding": total_outstanding,
        "total_loan_count": total_loan_count,
        "sector_count": len(sectors),
        "sectors": sectors,
        "top_5": sectors[:5],
        "bottom_5": sectors[-5:] if len(sectors) >= 5 else sectors,
        "recent_alerts": recent_alerts,
    }


# ── Sector Detail (FR-3) ────────────────────────────────────

async def get_sector_detail(db: AsyncSession, sector_name: str) -> dict[str, Any]:
    """Compute risk metrics for a specific sector."""

    today = date.today()

    # Loans in this sector
    loan_q = (
        select(LoanApplication)
        .join(ApplicantProfile, ApplicantProfile.user_id == LoanApplication.applicant_id)
        .where(
            LoanApplication.status.in_(ACTIVE_STATUSES),
            func.coalesce(ApplicantProfile.employer_sector, "MISSING") == sector_name,
        )
    )
    loan_result = await db.execute(loan_q)
    loans = loan_result.scalars().all()

    loan_ids = [la.id for la in loans]
    total_outstanding = sum(float(la.amount_approved or 0) for la in loans)
    loan_count = len(loans)

    # Delinquency analysis: look at payment schedules
    if loan_ids:
        sched_q = await db.execute(
            select(PaymentSchedule)
            .where(
                PaymentSchedule.loan_application_id.in_(loan_ids),
                PaymentSchedule.status.in_([ScheduleStatus.OVERDUE, ScheduleStatus.DUE, ScheduleStatus.PARTIAL]),
            )
        )
        overdue_schedules = sched_q.scalars().all()
    else:
        overdue_schedules = []

    # Calculate DPD buckets
    dpd_30_count = 0
    dpd_60_count = 0
    dpd_90_count = 0
    dpd_30_amount = 0.0
    dpd_60_amount = 0.0
    dpd_90_amount = 0.0
    loans_with_overdue = set()

    for sched in overdue_schedules:
        days_past = (today - sched.due_date).days
        remaining = float(sched.amount_due) - float(sched.amount_paid)
        if remaining <= 0:
            continue
        if days_past >= DPD_90:
            dpd_90_count += 1
            dpd_90_amount += remaining
            loans_with_overdue.add(sched.loan_application_id)
        elif days_past >= DPD_60:
            dpd_60_count += 1
            dpd_60_amount += remaining
            loans_with_overdue.add(sched.loan_application_id)
        elif days_past >= DPD_30:
            dpd_30_count += 1
            dpd_30_amount += remaining
            loans_with_overdue.add(sched.loan_application_id)

    delinquent_count = len(loans_with_overdue)
    delinquency_rate = _pct(delinquent_count, loan_count)
    npl_ratio = _pct(dpd_90_amount, total_outstanding)

    # Get all-portfolio totals for comparison
    total_q = await db.execute(
        select(
            func.coalesce(func.sum(LoanApplication.amount_approved), 0),
            func.count(LoanApplication.id),
        )
        .where(LoanApplication.status.in_(ACTIVE_STATUSES))
    )
    total_row = total_q.one()
    portfolio_total = float(total_row[0])
    portfolio_count = total_row[1]

    # Historical snapshots (up to 12 months)
    snapshots_q = await db.execute(
        select(SectorSnapshot)
        .where(SectorSnapshot.sector == sector_name)
        .order_by(SectorSnapshot.snapshot_date.desc())
        .limit(24)
    )
    snapshots = [
        {
            "date": s.snapshot_date.isoformat(),
            "loan_count": s.loan_count,
            "total_outstanding": float(s.total_outstanding),
            "exposure_pct": s.exposure_pct,
            "delinquency_rate": s.delinquency_rate,
            "npl_ratio": s.npl_ratio,
            "dpd_30_count": s.dpd_30_count,
            "dpd_60_count": s.dpd_60_count,
            "dpd_90_count": s.dpd_90_count,
        }
        for s in snapshots_q.scalars().all()
    ]
    snapshots.reverse()  # oldest first

    # Active policy
    policy_q = await db.execute(
        select(SectorPolicy)
        .where(SectorPolicy.sector == sector_name, SectorPolicy.status == SectorPolicyStatus.ACTIVE)
        .limit(1)
    )
    policy = policy_q.scalar_one_or_none()

    # Loan listings (for drill-down)
    loan_list = []
    for la in loans[:100]:  # cap at 100 for performance
        loan_list.append({
            "id": la.id,
            "reference_number": la.reference_number,
            "amount_approved": float(la.amount_approved or 0),
            "status": la.status.value,
            "disbursed_at": la.disbursed_at.isoformat() if la.disbursed_at else None,
        })

    return {
        "sector": sector_name,
        "loan_count": loan_count,
        "total_outstanding": total_outstanding,
        "avg_loan_size": _safe_div(total_outstanding, loan_count),
        "exposure_pct": _pct(total_outstanding, portfolio_total),
        "portfolio_total": portfolio_total,
        "portfolio_count": portfolio_count,
        # Delinquency
        "current_count": loan_count - delinquent_count,
        "delinquent_count": delinquent_count,
        "delinquency_rate": delinquency_rate,
        "npl_ratio": npl_ratio,
        "dpd_30": {"count": dpd_30_count, "amount": dpd_30_amount},
        "dpd_60": {"count": dpd_60_count, "amount": dpd_60_amount},
        "dpd_90": {"count": dpd_90_count, "amount": dpd_90_amount},
        # Roll rates (simplified: from snapshot deltas)
        "roll_rates": _compute_roll_rates(snapshots),
        # Policy
        "policy": _serialize_policy(policy) if policy else None,
        # History
        "snapshots": snapshots,
        # Loans
        "loans": loan_list,
    }


def _compute_roll_rates(snapshots: list[dict]) -> dict:
    """Compute roll-rate approximation from consecutive snapshots."""
    if len(snapshots) < 2:
        return {"current_to_30": 0, "dpd30_to_60": 0, "dpd60_to_90": 0}
    prev = snapshots[-2]
    curr = snapshots[-1]
    return {
        "current_to_30": _safe_div(
            curr.get("dpd_30_count", 0),
            max(prev.get("loan_count", 1) - prev.get("dpd_30_count", 0) - prev.get("dpd_60_count", 0) - prev.get("dpd_90_count", 0), 1),
        ),
        "dpd30_to_60": _safe_div(curr.get("dpd_60_count", 0), max(prev.get("dpd_30_count", 1), 1)),
        "dpd60_to_90": _safe_div(curr.get("dpd_90_count", 0), max(prev.get("dpd_60_count", 1), 1)),
    }


def _serialize_policy(p: SectorPolicy) -> dict:
    return {
        "id": p.id,
        "sector": p.sector,
        "exposure_cap_pct": p.exposure_cap_pct,
        "exposure_cap_amount": float(p.exposure_cap_amount) if p.exposure_cap_amount else None,
        "origination_paused": p.origination_paused,
        "pause_effective_date": p.pause_effective_date.isoformat() if p.pause_effective_date else None,
        "pause_expiry_date": p.pause_expiry_date.isoformat() if p.pause_expiry_date else None,
        "pause_reason": p.pause_reason,
        "max_loan_amount_override": float(p.max_loan_amount_override) if p.max_loan_amount_override else None,
        "min_credit_score_override": p.min_credit_score_override,
        "max_term_months_override": p.max_term_months_override,
        "require_collateral": p.require_collateral,
        "require_guarantor": p.require_guarantor,
        "risk_rating": p.risk_rating.value if hasattr(p.risk_rating, 'value') else p.risk_rating,
        "on_watchlist": p.on_watchlist,
        "watchlist_review_frequency": p.watchlist_review_frequency,
        "status": p.status.value if hasattr(p.status, 'value') else p.status,
        "justification": p.justification,
        "created_by": p.created_by,
        "approved_by": p.approved_by,
    }


# ── Sector Comparison / Heatmap (FR-6) ──────────────────────

async def get_sector_heatmap(db: AsyncSession) -> list[dict]:
    """Compute a heatmap matrix: sectors × risk metrics."""
    dashboard = await get_portfolio_dashboard(db)
    sectors = dashboard["sectors"]

    result = []
    for s in sectors:
        sector_name = s["sector"]
        # Get detail-level metrics
        detail = await get_sector_detail(db, sector_name)
        result.append({
            "sector": sector_name,
            "exposure_pct": s["exposure_pct"],
            "loan_count": s["loan_count"],
            "delinquency_rate": detail["delinquency_rate"],
            "npl_ratio": detail["npl_ratio"],
            "avg_loan_size": detail["avg_loan_size"],
            "risk_rating": s.get("risk_rating", "medium"),
            "concentration_status": s["concentration_status"],
            "on_watchlist": s.get("on_watchlist", False),
            "origination_paused": s.get("origination_paused", False),
        })

    return result


# ── Stress Testing (FR-8) ────────────────────────────────────

async def run_stress_test(
    db: AsyncSession,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Run a what-if stress test scenario.

    scenario = {
        "name": "Tourism Downturn",
        "shocks": {
            "Hospitality & Tourism": {"default_rate_multiplier": 2.0, "exposure_change_pct": -10},
            "Retail & Distribution": {"default_rate_multiplier": 1.5},
        }
    }
    """
    dashboard = await get_portfolio_dashboard(db)

    total = dashboard["total_outstanding"]
    results = []
    total_impact = 0.0

    for sector_data in dashboard["sectors"]:
        sector_name = sector_data["sector"]
        shock = scenario.get("shocks", {}).get(sector_name, {})

        detail = await get_sector_detail(db, sector_name)

        base_npl = detail["npl_ratio"]
        base_default = detail.get("default_rate", 0)
        base_outstanding = sector_data["total_outstanding"]

        # Apply shock
        default_mult = shock.get("default_rate_multiplier", 1.0)
        exposure_change = shock.get("exposure_change_pct", 0)

        stressed_outstanding = base_outstanding * (1 + exposure_change / 100)
        stressed_default_rate = base_default * default_mult
        # Simplified LGD assumption: 40%
        lgd = shock.get("lgd", 0.4)
        expected_loss = stressed_outstanding * (stressed_default_rate / 100) * lgd

        total_impact += expected_loss

        results.append({
            "sector": sector_name,
            "base_outstanding": base_outstanding,
            "stressed_outstanding": round(stressed_outstanding, 2),
            "base_default_rate": base_default,
            "stressed_default_rate": round(stressed_default_rate, 2),
            "expected_loss": round(expected_loss, 2),
            "applied_shock": shock if shock else None,
        })

    return {
        "scenario_name": scenario.get("name", "Custom"),
        "total_portfolio": total,
        "total_expected_loss": round(total_impact, 2),
        "impact_pct_of_portfolio": _pct(total_impact, total),
        "sector_results": results,
    }


# ── Concentration enforcement (for loan approval) ───────────

async def check_sector_origination(
    db: AsyncSession,
    sector: str,
    loan_amount: float,
) -> dict[str, Any]:
    """Check if a new loan in this sector is allowed by policies.

    Returns {allowed: bool, reasons: [...], policy: {...}}
    """
    reasons = []

    # Get active policy
    policy_q = await db.execute(
        select(SectorPolicy)
        .where(SectorPolicy.sector == sector, SectorPolicy.status == SectorPolicyStatus.ACTIVE)
        .limit(1)
    )
    policy = policy_q.scalar_one_or_none()

    if not policy:
        return {"allowed": True, "reasons": [], "policy": None}

    today = date.today()

    # Check pause
    if policy.origination_paused:
        eff = policy.pause_effective_date
        exp = policy.pause_expiry_date
        if (eff is None or eff <= today) and (exp is None or exp >= today):
            reasons.append(f"Origination paused for {sector}: {policy.pause_reason or 'No reason specified'}")

    # Check exposure cap
    if policy.exposure_cap_pct:
        total_q = await db.execute(
            select(func.coalesce(func.sum(LoanApplication.amount_approved), 0))
            .where(LoanApplication.status.in_(ACTIVE_STATUSES))
        )
        portfolio_total = float(total_q.scalar())

        sector_q = await db.execute(
            select(func.coalesce(func.sum(LoanApplication.amount_approved), 0))
            .join(ApplicantProfile, ApplicantProfile.user_id == LoanApplication.applicant_id)
            .where(
                LoanApplication.status.in_(ACTIVE_STATUSES),
                func.coalesce(ApplicantProfile.employer_sector, "MISSING") == sector,
            )
        )
        sector_total = float(sector_q.scalar())

        new_exposure_pct = _pct(sector_total + loan_amount, portfolio_total + loan_amount)
        if new_exposure_pct > policy.exposure_cap_pct:
            reasons.append(
                f"Exposure cap breached: {sector} would be {new_exposure_pct}% "
                f"(cap: {policy.exposure_cap_pct}%)"
            )

    blocked = len(reasons) > 0
    return {
        "allowed": not blocked,
        "reasons": reasons,
        "policy": _serialize_policy(policy),
    }


# ── Snapshot generation ──────────────────────────────────────

async def generate_monthly_snapshot(db: AsyncSession, snapshot_date: date | None = None) -> int:
    """Generate a monthly sector snapshot for all sectors. Returns count."""
    if snapshot_date is None:
        snapshot_date = date.today().replace(day=1) - timedelta(days=1)  # last day of prev month

    dashboard = await get_portfolio_dashboard(db)
    count = 0

    for s in dashboard["sectors"]:
        sector_name = s["sector"]
        detail = await get_sector_detail(db, sector_name)

        snap = SectorSnapshot(
            snapshot_date=snapshot_date,
            sector=sector_name,
            loan_count=s["loan_count"],
            total_outstanding=s["total_outstanding"],
            total_disbursed=s["total_outstanding"],  # simplified
            avg_loan_size=s["avg_loan_size"],
            exposure_pct=s["exposure_pct"],
            current_count=detail["current_count"],
            dpd_30_count=detail["dpd_30"]["count"],
            dpd_60_count=detail["dpd_60"]["count"],
            dpd_90_count=detail["dpd_90"]["count"],
            dpd_30_amount=detail["dpd_30"]["amount"],
            dpd_60_amount=detail["dpd_60"]["amount"],
            dpd_90_amount=detail["dpd_90"]["amount"],
            delinquency_rate=detail["delinquency_rate"],
            npl_ratio=detail["npl_ratio"],
            default_rate=0,
            risk_rating=s.get("risk_rating", "medium"),
        )
        db.add(snap)
        count += 1

    await db.flush()
    return count


# ── Evaluate alert rules ─────────────────────────────────────

async def evaluate_alert_rules(db: AsyncSession) -> list[SectorAlert]:
    """Evaluate all active alert rules and fire alerts where thresholds are breached."""
    rules_q = await db.execute(
        select(SectorAlertRule).where(SectorAlertRule.is_active == True)
    )
    rules = rules_q.scalars().all()

    dashboard = await get_portfolio_dashboard(db)
    sector_map = {s["sector"]: s for s in dashboard["sectors"]}

    fired: list[SectorAlert] = []

    for rule in rules:
        sectors_to_check = [rule.sector] if rule.sector else list(sector_map.keys())

        for sector_name in sectors_to_check:
            sector_data = sector_map.get(sector_name)
            if not sector_data:
                continue

            detail = await get_sector_detail(db, sector_name)

            # Get metric value
            metric_value = _get_metric_value(rule.metric, sector_data, detail)
            if metric_value is None:
                continue

            # Evaluate
            if _evaluate_condition(metric_value, rule.operator, rule.threshold):
                alert = SectorAlert(
                    rule_id=rule.id,
                    sector=sector_name,
                    severity=rule.severity,
                    title=f"{rule.name}: {sector_name}",
                    description=f"{rule.metric} is {metric_value} (threshold: {rule.operator} {rule.threshold})",
                    metric_name=rule.metric,
                    metric_value=metric_value,
                    threshold_value=rule.threshold,
                    recommended_action=rule.recommended_action,
                    status=SectorAlertStatus.NEW,
                )
                db.add(alert)
                fired.append(alert)

    await db.flush()
    return fired


def _get_metric_value(metric: str, sector_data: dict, detail: dict) -> float | None:
    mapping = {
        "exposure_pct": sector_data.get("exposure_pct"),
        "delinquency_rate": detail.get("delinquency_rate"),
        "npl_ratio": detail.get("npl_ratio"),
        "default_rate": detail.get("default_rate", 0),
        "loan_count": sector_data.get("loan_count"),
        "total_outstanding": sector_data.get("total_outstanding"),
        "avg_loan_size": detail.get("avg_loan_size"),
        "roll_rate_30_60": detail.get("roll_rates", {}).get("dpd30_to_60", 0),
        "roll_rate_60_90": detail.get("roll_rates", {}).get("dpd60_to_90", 0),
    }
    return mapping.get(metric)


def _evaluate_condition(value: float, operator: str, threshold: float) -> bool:
    ops = {
        ">": lambda v, t: v > t,
        ">=": lambda v, t: v >= t,
        "<": lambda v, t: v < t,
        "<=": lambda v, t: v <= t,
        "==": lambda v, t: abs(v - t) < 0.001,
    }
    fn = ops.get(operator)
    return fn(value, threshold) if fn else False
