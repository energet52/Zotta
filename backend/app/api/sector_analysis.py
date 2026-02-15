from app.services.error_logger import log_error
import logging
"""Sector Analysis API — portfolio concentration and risk management endpoints.

Provides:
  - Portfolio concentration dashboard (FR-2)
  - Sector detail & risk metrics (FR-3)
  - Sector heatmap / comparison (FR-6)
  - Alert rules management (FR-4)
  - Alert lifecycle (FR-4)
  - Sector policy management (FR-5)
  - Macro indicator CRUD (FR-4)
  - Stress testing (FR-8)
  - Monthly snapshot generation
  - Concentration enforcement check
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.sector_analysis import (
    SectorPolicy,
    SectorPolicyStatus,
    SectorRiskRating,
    SectorAlertRule,
    SectorAlertSeverity,
    SectorAlert,
    SectorAlertStatus,
    SectorMacroIndicator,
    SectorSnapshot,
    SECTOR_TAXONOMY,
)
from app.auth_utils import require_roles, get_current_user
from app.services.sector_analysis import (
    get_portfolio_dashboard,
    get_sector_detail,
    get_sector_heatmap,
    run_stress_test,
    check_sector_origination,
    generate_monthly_snapshot,
    evaluate_alert_rules,
)

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)
SENIOR_ROLES = (UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


# ── Schemas ──────────────────────────────────────────────────

class PolicyCreateRequest(BaseModel):
    sector: str
    exposure_cap_pct: Optional[float] = None
    exposure_cap_amount: Optional[float] = None
    origination_paused: bool = False
    pause_effective_date: Optional[str] = None
    pause_expiry_date: Optional[str] = None
    pause_reason: Optional[str] = None
    max_loan_amount_override: Optional[float] = None
    min_credit_score_override: Optional[int] = None
    max_term_months_override: Optional[int] = None
    require_collateral: bool = False
    require_guarantor: bool = False
    risk_rating: str = "medium"
    on_watchlist: bool = False
    watchlist_review_frequency: Optional[str] = None
    justification: Optional[str] = None


class PolicyUpdateRequest(BaseModel):
    exposure_cap_pct: Optional[float] = None
    exposure_cap_amount: Optional[float] = None
    origination_paused: Optional[bool] = None
    pause_effective_date: Optional[str] = None
    pause_expiry_date: Optional[str] = None
    pause_reason: Optional[str] = None
    max_loan_amount_override: Optional[float] = None
    min_credit_score_override: Optional[int] = None
    max_term_months_override: Optional[int] = None
    require_collateral: Optional[bool] = None
    require_guarantor: Optional[bool] = None
    risk_rating: Optional[str] = None
    on_watchlist: Optional[bool] = None
    watchlist_review_frequency: Optional[str] = None
    justification: Optional[str] = None


class AlertRuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    sector: Optional[str] = None
    metric: str
    operator: str
    threshold: float
    consecutive_months: int = 1
    severity: str = "warning"
    recommended_action: Optional[str] = None


class AlertUpdateRequest(BaseModel):
    status: Optional[str] = None
    action_notes: Optional[str] = None


class MacroIndicatorCreateRequest(BaseModel):
    sector: str
    indicator_name: str
    indicator_value: float
    period: str  # ISO date
    source: Optional[str] = None
    notes: Optional[str] = None


class StressTestRequest(BaseModel):
    name: str
    shocks: dict  # {sector: {default_rate_multiplier, exposure_change_pct, lgd}}


class ConcentrationCheckRequest(BaseModel):
    sector: str
    loan_amount: float


# ── Taxonomy ─────────────────────────────────────────────────

@router.get("/taxonomy")
async def get_taxonomy():
    """Return the standardized sector taxonomy."""
    return {"sectors": SECTOR_TAXONOMY}


# ── Dashboard (FR-2) ────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Real-time portfolio concentration dashboard."""
    return await get_portfolio_dashboard(db)


# ── Sector Detail (FR-3) ────────────────────────────────────

@router.get("/sectors/{sector_name}")
async def sector_detail(
    sector_name: str,
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detailed risk metrics for a specific sector."""
    return await get_sector_detail(db, sector_name)


# ── Heatmap (FR-6) ──────────────────────────────────────────

@router.get("/heatmap")
async def heatmap(
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Sector risk heatmap matrix."""
    return await get_sector_heatmap(db)


# ── Policies (FR-5) ─────────────────────────────────────────

@router.get("/policies")
async def list_policies(
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List all sector policies."""
    try:
        q = await db.execute(
            select(SectorPolicy).order_by(SectorPolicy.sector)
        )
        policies = q.scalars().all()
        return [_policy_to_dict(p) for p in policies]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="list_policies")
        raise


@router.post("/policies")
async def create_policy(
    body: PolicyCreateRequest,
    user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new sector policy (maker). Requires approval (checker) if not admin."""
    try:
        status = SectorPolicyStatus.ACTIVE if user.role == UserRole.ADMIN else SectorPolicyStatus.PENDING_APPROVAL

        policy = SectorPolicy(
            sector=body.sector,
            exposure_cap_pct=body.exposure_cap_pct,
            exposure_cap_amount=body.exposure_cap_amount,
            origination_paused=body.origination_paused,
            pause_effective_date=date.fromisoformat(body.pause_effective_date) if body.pause_effective_date else None,
            pause_expiry_date=date.fromisoformat(body.pause_expiry_date) if body.pause_expiry_date else None,
            pause_reason=body.pause_reason,
            max_loan_amount_override=body.max_loan_amount_override,
            min_credit_score_override=body.min_credit_score_override,
            max_term_months_override=body.max_term_months_override,
            require_collateral=body.require_collateral,
            require_guarantor=body.require_guarantor,
            risk_rating=SectorRiskRating(body.risk_rating),
            on_watchlist=body.on_watchlist,
            watchlist_review_frequency=body.watchlist_review_frequency,
            status=status,
            created_by=user.id,
            approved_by=user.id if user.role == UserRole.ADMIN else None,
            justification=body.justification,
        )
        db.add(policy)
        await db.flush()
        await db.refresh(policy)
        return _policy_to_dict(policy)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="create_policy")
        raise


@router.patch("/policies/{policy_id}")
async def update_policy(
    policy_id: int,
    body: PolicyUpdateRequest,
    user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update a sector policy."""
    try:
        q = await db.execute(select(SectorPolicy).where(SectorPolicy.id == policy_id))
        policy = q.scalar_one_or_none()
        if not policy:
            raise HTTPException(404, "Policy not found")

        for field, value in body.model_dump(exclude_unset=True).items():
            if field == "risk_rating" and value is not None:
                setattr(policy, field, SectorRiskRating(value))
            elif field in ("pause_effective_date", "pause_expiry_date") and value is not None:
                setattr(policy, field, date.fromisoformat(value))
            elif value is not None:
                setattr(policy, field, value)

        await db.flush()
        await db.refresh(policy)
        return _policy_to_dict(policy)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="update_policy")
        raise


@router.post("/policies/{policy_id}/approve")
async def approve_policy(
    policy_id: int,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending policy (checker)."""
    try:
        q = await db.execute(select(SectorPolicy).where(SectorPolicy.id == policy_id))
        policy = q.scalar_one_or_none()
        if not policy:
            raise HTTPException(404, "Policy not found")
        if policy.status != SectorPolicyStatus.PENDING_APPROVAL:
            raise HTTPException(400, "Policy is not pending approval")
        if policy.created_by == user.id:
            raise HTTPException(400, "Maker and checker must be different users")

        policy.status = SectorPolicyStatus.ACTIVE
        policy.approved_by = user.id
        await db.flush()
        return _policy_to_dict(policy)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="approve_policy")
        raise


@router.delete("/policies/{policy_id}")
async def archive_policy(
    policy_id: int,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Archive a sector policy."""
    try:
        q = await db.execute(select(SectorPolicy).where(SectorPolicy.id == policy_id))
        policy = q.scalar_one_or_none()
        if not policy:
            raise HTTPException(404, "Policy not found")
        policy.status = SectorPolicyStatus.ARCHIVED
        await db.flush()
        return {"status": "archived"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="archive_policy")
        raise


# ── Alert Rules (FR-4) ──────────────────────────────────────

@router.get("/alert-rules")
async def list_alert_rules(
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        q = await db.execute(select(SectorAlertRule).order_by(SectorAlertRule.id))
        rules = q.scalars().all()
        return [_rule_to_dict(r) for r in rules]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="list_alert_rules")
        raise


@router.post("/alert-rules")
async def create_alert_rule(
    body: AlertRuleCreateRequest,
    user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        rule = SectorAlertRule(
            name=body.name,
            description=body.description,
            sector=body.sector,
            metric=body.metric,
            operator=body.operator,
            threshold=body.threshold,
            consecutive_months=body.consecutive_months,
            severity=SectorAlertSeverity(body.severity),
            recommended_action=body.recommended_action,
            is_active=True,
            created_by=user.id,
        )
        db.add(rule)
        await db.flush()
        await db.refresh(rule)
        return _rule_to_dict(rule)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="create_alert_rule")
        raise


@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        q = await db.execute(select(SectorAlertRule).where(SectorAlertRule.id == rule_id))
        rule = q.scalar_one_or_none()
        if not rule:
            raise HTTPException(404, "Rule not found")
        rule.is_active = False
        await db.flush()
        return {"status": "deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="delete_alert_rule")
        raise


# ── Alerts (FR-4) ───────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    status_filter: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        q = select(SectorAlert).order_by(SectorAlert.created_at.desc())
        if status_filter:
            q = q.where(SectorAlert.status == SectorAlertStatus(status_filter))
        if sector:
            q = q.where(SectorAlert.sector == sector)
        if severity:
            q = q.where(SectorAlert.severity == SectorAlertSeverity(severity))
        result = await db.execute(q.limit(200))
        alerts = result.scalars().all()
        return [_alert_to_dict(a) for a in alerts]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="list_alerts")
        raise


@router.patch("/alerts/{alert_id}")
async def update_alert(
    alert_id: int,
    body: AlertUpdateRequest,
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        q = await db.execute(select(SectorAlert).where(SectorAlert.id == alert_id))
        alert = q.scalar_one_or_none()
        if not alert:
            raise HTTPException(404, "Alert not found")

        if body.status:
            alert.status = SectorAlertStatus(body.status)
            if body.status in ("acknowledged", "action_taken"):
                alert.acknowledged_by = user.id
                alert.acknowledged_at = datetime.now(timezone.utc)
        if body.action_notes:
            alert.action_notes = body.action_notes
        await db.flush()
        return _alert_to_dict(alert)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="update_alert")
        raise


@router.post("/alerts/evaluate")
async def trigger_alert_evaluation(
    user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger evaluation of all alert rules."""
    fired = await evaluate_alert_rules(db)
    return {"fired_count": len(fired), "alerts": [_alert_to_dict(a) for a in fired]}


# ── Macro Indicators (FR-4) ─────────────────────────────────

@router.get("/macro-indicators")
async def list_macro_indicators(
    sector: Optional[str] = Query(None),
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        q = select(SectorMacroIndicator).order_by(SectorMacroIndicator.period.desc())
        if sector:
            q = q.where(SectorMacroIndicator.sector == sector)
        result = await db.execute(q.limit(500))
        indicators = result.scalars().all()
        return [_macro_to_dict(m) for m in indicators]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="list_macro_indicators")
        raise


@router.post("/macro-indicators")
async def create_macro_indicator(
    body: MacroIndicatorCreateRequest,
    user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        mi = SectorMacroIndicator(
            sector=body.sector,
            indicator_name=body.indicator_name,
            indicator_value=body.indicator_value,
            period=date.fromisoformat(body.period),
            source=body.source,
            notes=body.notes,
            created_by=user.id,
        )
        db.add(mi)
        await db.flush()
        await db.refresh(mi)
        return _macro_to_dict(mi)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="create_macro_indicator")
        raise


# ── Stress Testing (FR-8) ───────────────────────────────────

@router.post("/stress-test")
async def stress_test(
    body: StressTestRequest,
    user: User = Depends(require_roles(*SENIOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Run a what-if stress test scenario."""
    return await run_stress_test(db, {"name": body.name, "shocks": body.shocks})


# ── Snapshots ────────────────────────────────────────────────

@router.get("/snapshots")
async def list_snapshots(
    sector: Optional[str] = Query(None),
    months: int = Query(12),
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        q = select(SectorSnapshot).order_by(SectorSnapshot.snapshot_date.desc())
        if sector:
            q = q.where(SectorSnapshot.sector == sector)
        result = await db.execute(q.limit(months * 25))
        snaps = result.scalars().all()
        return [_snap_to_dict(s) for s in snaps]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.sector_analysis", function_name="list_snapshots")
        raise


@router.post("/snapshots/generate")
async def generate_snapshot(
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Manually generate a monthly snapshot for the current period."""
    count = await generate_monthly_snapshot(db)
    return {"generated": count}


# ── Concentration Check ─────────────────────────────────────

@router.post("/check-origination")
async def check_origination(
    body: ConcentrationCheckRequest,
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Check if a new loan in a sector would be allowed by current policies."""
    return await check_sector_origination(db, body.sector, body.loan_amount)


# ── Serializers ──────────────────────────────────────────────

def _policy_to_dict(p: SectorPolicy) -> dict:
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
        "risk_rating": p.risk_rating.value if hasattr(p.risk_rating, 'value') else str(p.risk_rating),
        "on_watchlist": p.on_watchlist,
        "watchlist_review_frequency": p.watchlist_review_frequency,
        "status": p.status.value if hasattr(p.status, 'value') else str(p.status),
        "justification": p.justification,
        "created_by": p.created_by,
        "approved_by": p.approved_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _rule_to_dict(r: SectorAlertRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "sector": r.sector,
        "metric": r.metric,
        "operator": r.operator,
        "threshold": r.threshold,
        "consecutive_months": r.consecutive_months,
        "severity": r.severity.value if hasattr(r.severity, 'value') else str(r.severity),
        "recommended_action": r.recommended_action,
        "is_active": r.is_active,
        "created_by": r.created_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _alert_to_dict(a: SectorAlert) -> dict:
    return {
        "id": a.id,
        "rule_id": a.rule_id,
        "sector": a.sector,
        "severity": a.severity.value if hasattr(a.severity, 'value') else str(a.severity),
        "title": a.title,
        "description": a.description,
        "metric_name": a.metric_name,
        "metric_value": a.metric_value,
        "threshold_value": a.threshold_value,
        "recommended_action": a.recommended_action,
        "status": a.status.value if hasattr(a.status, 'value') else str(a.status),
        "acknowledged_by": a.acknowledged_by,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "action_notes": a.action_notes,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _macro_to_dict(m: SectorMacroIndicator) -> dict:
    return {
        "id": m.id,
        "sector": m.sector,
        "indicator_name": m.indicator_name,
        "indicator_value": m.indicator_value,
        "period": m.period.isoformat(),
        "source": m.source,
        "notes": m.notes,
        "created_by": m.created_by,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _snap_to_dict(s: SectorSnapshot) -> dict:
    return {
        "id": s.id,
        "snapshot_date": s.snapshot_date.isoformat(),
        "sector": s.sector,
        "loan_count": s.loan_count,
        "total_outstanding": float(s.total_outstanding),
        "total_disbursed": float(s.total_disbursed),
        "avg_loan_size": float(s.avg_loan_size),
        "exposure_pct": s.exposure_pct,
        "current_count": s.current_count,
        "dpd_30_count": s.dpd_30_count,
        "dpd_60_count": s.dpd_60_count,
        "dpd_90_count": s.dpd_90_count,
        "delinquency_rate": s.delinquency_rate,
        "npl_ratio": s.npl_ratio,
        "default_rate": s.default_rate,
        "risk_rating": s.risk_rating,
    }
