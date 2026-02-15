"""Collections engine — case sync, NBA, compliance, settlement calculator, PTP checker, snapshots."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, and_, or_, case as sa_case, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.loan import LoanApplication, LoanStatus
from app.models.payment import PaymentSchedule, ScheduleStatus, Payment, PaymentStatus
from app.models.collection import CollectionRecord
from app.models.collections_ext import (
    CollectionCase,
    CaseStatus,
    DelinquencyStage,
    PromiseToPay,
    PTPStatus,
    SettlementOffer,
    SettlementOfferType,
    SettlementOfferStatus,
    ComplianceRule,
    SLAConfig,
    CollectionsDashboardSnapshot,
    dpd_to_stage,
)

logger = logging.getLogger(__name__)

# ── Grace period (days after promise_date before marking broken) ──
PTP_GRACE_DAYS = 3


# ────────────────────────────────────────────────────────────────────
# 1. sync_collection_cases
# ────────────────────────────────────────────────────────────────────

async def sync_collection_cases(db: AsyncSession) -> dict[str, int]:
    """Scan disbursed loans, create/update CollectionCase rows.

    Returns counts: {"created": N, "updated": N, "closed": N}
    """
    today = date.today()
    stats: dict[str, int] = {"created": 0, "updated": 0, "closed": 0}

    # Find all disbursed loans that have at least one overdue schedule line
    overdue_sq = (
        select(
            PaymentSchedule.loan_application_id,
            func.min(PaymentSchedule.due_date).label("earliest_overdue"),
            func.sum(PaymentSchedule.amount_due - PaymentSchedule.amount_paid).label("total_overdue"),
        )
        .where(
            PaymentSchedule.status.in_([ScheduleStatus.OVERDUE, ScheduleStatus.DUE, ScheduleStatus.PARTIAL]),
            PaymentSchedule.due_date < today,
            PaymentSchedule.amount_paid < PaymentSchedule.amount_due,
        )
        .group_by(PaymentSchedule.loan_application_id)
        .subquery()
    )

    loans_q = (
        select(
            LoanApplication.id,
            overdue_sq.c.earliest_overdue,
            overdue_sq.c.total_overdue,
        )
        .join(overdue_sq, LoanApplication.id == overdue_sq.c.loan_application_id)
        .where(LoanApplication.status == LoanStatus.DISBURSED)
    )
    rows = (await db.execute(loans_q)).all()

    existing_cases_q = select(CollectionCase).where(
        CollectionCase.status.notin_([CaseStatus.CLOSED, CaseStatus.WRITTEN_OFF])
    )
    existing_cases = {
        c.loan_application_id: c
        for c in (await db.execute(existing_cases_q)).scalars().all()
    }

    active_loan_ids: set[int] = set()
    for loan_id, earliest_overdue, total_overdue in rows:
        active_loan_ids.add(loan_id)
        dpd = (today - earliest_overdue).days
        stage = dpd_to_stage(dpd)
        total_overdue_dec = Decimal(str(total_overdue)) if total_overdue else Decimal("0")
        priority = _compute_priority(dpd, float(total_overdue_dec))

        if loan_id in existing_cases:
            cc = existing_cases[loan_id]
            cc.dpd = dpd
            cc.delinquency_stage = stage
            cc.total_overdue = total_overdue_dec
            cc.priority_score = priority
            if cc.status == CaseStatus.OPEN and dpd > 0:
                cc.status = CaseStatus.IN_PROGRESS
            stats["updated"] += 1
        else:
            cc = CollectionCase(
                loan_application_id=loan_id,
                dpd=dpd,
                delinquency_stage=stage,
                total_overdue=total_overdue_dec,
                priority_score=priority,
                status=CaseStatus.OPEN,
            )
            # Set SLA deadline for first contact
            sla = await _get_sla_for_stage(db, stage.value)
            if sla:
                cc.sla_first_contact_deadline = datetime.now(timezone.utc) + timedelta(hours=sla.hours_allowed)
            db.add(cc)
            stats["created"] += 1

    # Close cases where loans are no longer overdue
    for loan_id, cc in existing_cases.items():
        if loan_id not in active_loan_ids:
            cc.status = CaseStatus.CLOSED
            stats["closed"] += 1

    await db.flush()
    return stats


def _compute_priority(dpd: int, total_overdue: float) -> float:
    """Simple priority score: higher = more urgent."""
    # Weighted: 40% DPD factor + 60% amount factor (normalized by 10k)
    dpd_factor = min(dpd / 90, 1.0)
    amount_factor = min(total_overdue / 10000, 1.0)
    return round(dpd_factor * 0.4 + amount_factor * 0.6, 4)


async def _get_sla_for_stage(db: AsyncSession, stage_value: str) -> SLAConfig | None:
    q = select(SLAConfig).where(SLAConfig.delinquency_stage == stage_value, SLAConfig.is_active == True)
    return (await db.execute(q)).scalars().first()


# ────────────────────────────────────────────────────────────────────
# 2. compute_next_best_action
# ────────────────────────────────────────────────────────────────────

async def compute_next_best_action(
    case: CollectionCase,
    db: AsyncSession,
) -> dict[str, Any]:
    """Rule-based NBA engine. Returns {"action", "confidence", "reasoning"}."""

    # Flags take precedence
    if case.do_not_contact:
        return {"action": "hold_do_not_contact", "confidence": 1.0,
                "reasoning": "Borrower flagged as Do Not Contact."}
    if case.dispute_active:
        return {"action": "hold_dispute", "confidence": 1.0,
                "reasoning": "Active dispute — contact paused until resolution."}
    if case.vulnerability_flag:
        return {"action": "hold_vulnerability_review", "confidence": 0.95,
                "reasoning": "Vulnerability flag — route to specialist."}
    if case.hardship_flag:
        return {"action": "offer_hardship_plan", "confidence": 0.90,
                "reasoning": "Hardship flag — offer restructuring options."}

    # Count broken promises
    broken_count_q = select(func.count()).where(
        PromiseToPay.collection_case_id == case.id,
        PromiseToPay.status == PTPStatus.BROKEN,
    )
    broken_count = (await db.execute(broken_count_q)).scalar() or 0

    # DPD-based rules
    dpd = case.dpd

    if dpd < 7 and not case.first_contact_at:
        return {"action": "send_whatsapp_reminder", "confidence": 0.85,
                "reasoning": f"Early delinquency ({dpd} DPD), no contact yet. WhatsApp reminder recommended."}

    if dpd < 7:
        return {"action": "send_sms_reminder", "confidence": 0.80,
                "reasoning": f"Early delinquency ({dpd} DPD), follow-up SMS."}

    if dpd <= 30:
        if broken_count >= 2:
            return {"action": "escalate_supervisor", "confidence": 0.85,
                    "reasoning": f"{broken_count} broken promises in early stage. Escalate to supervisor."}
        return {"action": "call_now", "confidence": 0.80,
                "reasoning": f"{dpd} DPD — phone call recommended."}

    if dpd <= 60:
        if broken_count >= 2:
            return {"action": "escalate_field", "confidence": 0.85,
                    "reasoning": f"{dpd} DPD with {broken_count} broken promises. Field visit recommended."}
        return {"action": "call_now", "confidence": 0.75,
                "reasoning": f"{dpd} DPD — mid-stage, phone outreach."}

    if dpd <= 90:
        return {"action": "send_demand_letter", "confidence": 0.80,
                "reasoning": f"{dpd} DPD — demand letter and settlement discussion."}

    # 90+
    return {"action": "escalate_legal", "confidence": 0.90,
            "reasoning": f"{dpd} DPD — severe delinquency, escalate to legal."}


async def update_case_nba(case: CollectionCase, db: AsyncSession) -> None:
    """Compute and persist NBA on a case."""
    nba = await compute_next_best_action(case, db)
    case.next_best_action = nba["action"]
    case.nba_confidence = nba["confidence"]
    case.nba_reasoning = nba["reasoning"]


# ────────────────────────────────────────────────────────────────────
# 3. check_compliance
# ────────────────────────────────────────────────────────────────────

async def check_compliance(
    case: CollectionCase,
    jurisdiction: str,
    db: AsyncSession,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Check if contacting a borrower right now is permitted.

    Returns {"allowed": bool, "reasons": [str], "next_allowed_at": datetime|None}
    """
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []

    # Hard blocks
    if case.do_not_contact:
        return {"allowed": False, "reasons": ["Borrower flagged Do Not Contact."], "next_allowed_at": None}
    if case.dispute_active:
        return {"allowed": False, "reasons": ["Active dispute — cannot contact."], "next_allowed_at": None}

    rule_q = select(ComplianceRule).where(
        ComplianceRule.jurisdiction == jurisdiction,
        ComplianceRule.is_active == True,
    )
    rule = (await db.execute(rule_q)).scalars().first()
    if not rule:
        # No rule for this jurisdiction — allow (lenient default)
        return {"allowed": True, "reasons": [], "next_allowed_at": None}

    next_allowed_at: datetime | None = None
    current_hour = now.hour

    # Check permitted hours
    if current_hour < rule.contact_start_hour or current_hour >= rule.contact_end_hour:
        reasons.append(
            f"Outside contact hours ({rule.contact_start_hour}:00 – {rule.contact_end_hour}:00)."
        )
        # Next allowed is start hour today (or tomorrow if past end)
        next_day = now.date() if current_hour < rule.contact_start_hour else now.date() + timedelta(days=1)
        next_allowed_at = datetime(
            next_day.year, next_day.month, next_day.day,
            rule.contact_start_hour, 0, 0, tzinfo=timezone.utc,
        )

    # Check cooling off
    if case.last_contact_at:
        cooling_off_end = case.last_contact_at + timedelta(hours=rule.cooling_off_hours)
        if now < cooling_off_end:
            reasons.append(
                f"Cooling-off period ({rule.cooling_off_hours}h) not elapsed since last contact."
            )
            if not next_allowed_at or cooling_off_end > next_allowed_at:
                next_allowed_at = cooling_off_end

    # Check daily cap
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    today_count_q = select(func.count()).where(
        CollectionRecord.loan_application_id == case.loan_application_id,
        CollectionRecord.created_at >= today_start,
    )
    today_count = (await db.execute(today_count_q)).scalar() or 0
    if today_count >= rule.max_contacts_per_day:
        reasons.append(f"Daily contact limit ({rule.max_contacts_per_day}) reached.")
        tomorrow_start = today_start + timedelta(days=1)
        adj = datetime(
            tomorrow_start.year, tomorrow_start.month, tomorrow_start.day,
            rule.contact_start_hour, 0, 0, tzinfo=timezone.utc,
        )
        if not next_allowed_at or adj > next_allowed_at:
            next_allowed_at = adj

    # Check weekly cap
    week_start = today_start - timedelta(days=now.weekday())
    week_count_q = select(func.count()).where(
        CollectionRecord.loan_application_id == case.loan_application_id,
        CollectionRecord.created_at >= week_start,
    )
    week_count = (await db.execute(week_count_q)).scalar() or 0
    if week_count >= rule.max_contacts_per_week:
        reasons.append(f"Weekly contact limit ({rule.max_contacts_per_week}) reached.")

    return {
        "allowed": len(reasons) == 0,
        "reasons": reasons,
        "next_allowed_at": next_allowed_at.isoformat() if next_allowed_at else None,
    }


# ────────────────────────────────────────────────────────────────────
# 4. calculate_settlement
# ────────────────────────────────────────────────────────────────────

def calculate_settlement(
    total_overdue: Decimal,
    dpd: int,
) -> list[dict[str, Any]]:
    """Compute settlement options based on current balance and DPD.

    Discount tiers:
      - 0–30 DPD: 0 % discount
      - 31–60 DPD: up to 5 %
      - 61–90 DPD: up to 10 %
      - 90+ DPD: up to 20 %
    """
    if total_overdue <= 0:
        return []

    discount_pct = 0.0
    if dpd > 90:
        discount_pct = 20.0
    elif dpd > 60:
        discount_pct = 10.0
    elif dpd > 30:
        discount_pct = 5.0

    discounted = total_overdue * Decimal(str((100 - discount_pct) / 100))
    options: list[dict[str, Any]] = []

    # 1. Full payment (no discount)
    options.append({
        "offer_type": SettlementOfferType.FULL_PAYMENT.value,
        "settlement_amount": float(total_overdue),
        "discount_pct": 0.0,
        "plan_months": None,
        "plan_monthly_amount": None,
        "lump_sum": float(total_overdue),
        "approval_required": False,
    })

    # 2. Partial settlement (discounted lump-sum)
    if discount_pct > 0:
        options.append({
            "offer_type": SettlementOfferType.PARTIAL_SETTLEMENT.value,
            "settlement_amount": float(round(discounted, 2)),
            "discount_pct": discount_pct,
            "plan_months": None,
            "plan_monthly_amount": None,
            "lump_sum": float(round(discounted, 2)),
            "approval_required": discount_pct > 10,
        })

    # 3. Short plan (3–6 months)
    for months in (3, 6):
        monthly = round(total_overdue / months, 2)
        options.append({
            "offer_type": SettlementOfferType.SHORT_PLAN.value,
            "settlement_amount": float(total_overdue),
            "discount_pct": 0.0,
            "plan_months": months,
            "plan_monthly_amount": float(monthly),
            "lump_sum": None,
            "approval_required": False,
        })

    # 4. Long plan (12 months) — for larger amounts
    if total_overdue > Decimal("1000"):
        months = 12
        monthly = round(total_overdue / months, 2)
        options.append({
            "offer_type": SettlementOfferType.LONG_PLAN.value,
            "settlement_amount": float(total_overdue),
            "discount_pct": 0.0,
            "plan_months": months,
            "plan_monthly_amount": float(monthly),
            "lump_sum": None,
            "approval_required": True,
        })

    return options


# ────────────────────────────────────────────────────────────────────
# 5. check_ptp_status
# ────────────────────────────────────────────────────────────────────

async def check_ptp_status(db: AsyncSession) -> dict[str, int]:
    """Check all pending PTPs; mark broken if past due + grace. Returns counts."""
    today = date.today()
    cutoff = today - timedelta(days=PTP_GRACE_DAYS)
    stats = {"broken": 0, "reminded": 0}

    ptps_q = select(PromiseToPay).where(PromiseToPay.status == PTPStatus.PENDING)
    ptps = (await db.execute(ptps_q)).scalars().all()

    for ptp in ptps:
        if ptp.promise_date < cutoff:
            ptp.status = PTPStatus.BROKEN
            ptp.broken_at = datetime.now(timezone.utc)
            stats["broken"] += 1
        elif ptp.promise_date <= today and not ptp.reminded_at:
            # Due today or in grace window — mark as reminded
            ptp.reminded_at = datetime.now(timezone.utc)
            stats["reminded"] += 1

    await db.flush()
    return stats


# ────────────────────────────────────────────────────────────────────
# 6. generate_daily_snapshot
# ────────────────────────────────────────────────────────────────────

async def generate_daily_snapshot(db: AsyncSession) -> CollectionsDashboardSnapshot:
    """Aggregate portfolio metrics into a daily snapshot."""
    today = date.today()

    # Check if snapshot already exists for today
    existing = (await db.execute(
        select(CollectionsDashboardSnapshot).where(
            CollectionsDashboardSnapshot.snapshot_date == today
        )
    )).scalars().first()
    if existing:
        snap = existing
    else:
        snap = CollectionsDashboardSnapshot(snapshot_date=today)
        db.add(snap)

    active_statuses = [CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.LEGAL]

    # Total delinquent accounts
    total_q = select(func.count()).where(CollectionCase.status.in_(active_statuses))
    snap.total_delinquent_accounts = (await db.execute(total_q)).scalar() or 0

    # Total overdue amount
    overdue_q = select(func.coalesce(func.sum(CollectionCase.total_overdue), 0)).where(
        CollectionCase.status.in_(active_statuses)
    )
    snap.total_overdue_amount = Decimal(str((await db.execute(overdue_q)).scalar() or 0))

    # By stage
    stage_q = (
        select(
            CollectionCase.delinquency_stage,
            func.count().label("cnt"),
            func.coalesce(func.sum(CollectionCase.total_overdue), 0).label("amt"),
        )
        .where(CollectionCase.status.in_(active_statuses))
        .group_by(CollectionCase.delinquency_stage)
    )
    stage_rows = (await db.execute(stage_q)).all()
    snap.by_stage = {
        row.delinquency_stage.value if hasattr(row.delinquency_stage, "value") else str(row.delinquency_stage): {
            "count": row.cnt, "amount": float(row.amt)
        }
        for row in stage_rows
    }

    # PTP rates
    total_ptp_q = select(func.count()).select_from(PromiseToPay)
    total_ptps = (await db.execute(total_ptp_q)).scalar() or 0
    kept_ptp_q = select(func.count()).where(PromiseToPay.status == PTPStatus.KEPT)
    kept_ptps = (await db.execute(kept_ptp_q)).scalar() or 0

    snap.ptp_rate = round(total_ptps / max(snap.total_delinquent_accounts, 1), 4)
    snap.ptp_kept_rate = round(kept_ptps / max(total_ptps, 1), 4)

    # Cure rate (closed / total all-time)
    total_ever_q = select(func.count()).select_from(CollectionCase)
    total_ever = (await db.execute(total_ever_q)).scalar() or 0
    closed_q = select(func.count()).where(
        CollectionCase.status.in_([CaseStatus.CLOSED, CaseStatus.SETTLED])
    )
    closed_count = (await db.execute(closed_q)).scalar() or 0
    snap.cure_rate = round(closed_count / max(total_ever, 1), 4)

    # Recovered MTD
    first_of_month = today.replace(day=1)
    recovered_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= first_of_month,
    )
    snap.total_recovered_mtd = Decimal(str((await db.execute(recovered_q)).scalar() or 0))

    # Avg days to collect (from closed cases)
    avg_q = select(
        func.avg(
            func.extract("epoch", CollectionCase.updated_at - CollectionCase.created_at) / 86400
        )
    ).where(CollectionCase.status.in_([CaseStatus.CLOSED, CaseStatus.SETTLED]))
    avg_val = (await db.execute(avg_q)).scalar()
    snap.avg_days_to_collect = round(float(avg_val), 2) if avg_val else 0.0

    await db.flush()
    return snap


# ────────────────────────────────────────────────────────────────────
# 7. get_collections_analytics
# ────────────────────────────────────────────────────────────────────

async def get_collections_analytics(
    db: AsyncSession,
    period_days: int = 30,
) -> dict[str, Any]:
    """Return dashboard analytics for the frontend."""
    today = date.today()

    # Latest snapshot
    latest_q = (
        select(CollectionsDashboardSnapshot)
        .order_by(CollectionsDashboardSnapshot.snapshot_date.desc())
        .limit(1)
    )
    latest = (await db.execute(latest_q)).scalars().first()

    # Trend data
    cutoff = today - timedelta(days=period_days)
    trend_q = (
        select(CollectionsDashboardSnapshot)
        .where(CollectionsDashboardSnapshot.snapshot_date >= cutoff)
        .order_by(CollectionsDashboardSnapshot.snapshot_date.asc())
    )
    trend_rows = (await db.execute(trend_q)).scalars().all()
    trend = [
        {
            "date": str(s.snapshot_date),
            "total_overdue": float(s.total_overdue_amount),
            "accounts": s.total_delinquent_accounts,
            "recovered": float(s.total_recovered_mtd),
        }
        for s in trend_rows
    ]

    # Agent performance
    agent_q = (
        select(
            CollectionCase.assigned_agent_id,
            func.count().label("cases"),
            func.coalesce(func.sum(CollectionCase.total_overdue), 0).label("overdue"),
        )
        .where(
            CollectionCase.assigned_agent_id.isnot(None),
            CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS]),
        )
        .group_by(CollectionCase.assigned_agent_id)
        .order_by(func.count().desc())
        .limit(10)
    )
    agent_rows = (await db.execute(agent_q)).all()
    from app.models.user import User
    agents = []
    for row in agent_rows:
        user = (await db.execute(select(User).where(User.id == row.assigned_agent_id))).scalars().first()
        agents.append({
            "agent_id": row.assigned_agent_id,
            "name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "active_cases": row.cases,
            "total_overdue": float(row.overdue),
        })

    kpis: dict[str, Any] = {}
    if latest:
        kpis = {
            "total_delinquent_accounts": latest.total_delinquent_accounts,
            "total_overdue_amount": float(latest.total_overdue_amount),
            "cure_rate": latest.cure_rate,
            "ptp_kept_rate": latest.ptp_kept_rate,
            "avg_days_to_collect": latest.avg_days_to_collect,
            "total_recovered_mtd": float(latest.total_recovered_mtd),
            "by_stage": latest.by_stage,
        }
    else:
        # Fallback: compute live
        active_statuses = [CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.LEGAL]
        total_q = select(func.count()).where(CollectionCase.status.in_(active_statuses))
        total = (await db.execute(total_q)).scalar() or 0
        overdue_q = select(func.coalesce(func.sum(CollectionCase.total_overdue), 0)).where(
            CollectionCase.status.in_(active_statuses)
        )
        overdue = float((await db.execute(overdue_q)).scalar() or 0)
        kpis = {
            "total_delinquent_accounts": total,
            "total_overdue_amount": overdue,
            "cure_rate": 0,
            "ptp_kept_rate": 0,
            "avg_days_to_collect": 0,
            "total_recovered_mtd": 0,
            "by_stage": {},
        }

    return {
        "kpis": kpis,
        "trend": trend,
        "agents": agents,
    }


# ────────────────────────────────────────────────────────────────────
# 8. get_agent_performance
# ────────────────────────────────────────────────────────────────────

async def get_agent_performance(db: AsyncSession) -> list[dict[str, Any]]:
    """Per-agent collection metrics."""
    from app.models.user import User

    agents_q = (
        select(
            CollectionCase.assigned_agent_id,
            func.count().label("total_cases"),
            func.sum(sa_case(
                (CollectionCase.status.in_([CaseStatus.CLOSED, CaseStatus.SETTLED]), 1),
                else_=0,
            )).label("resolved"),
            func.coalesce(func.sum(CollectionCase.total_overdue), 0).label("overdue"),
        )
        .where(CollectionCase.assigned_agent_id.isnot(None))
        .group_by(CollectionCase.assigned_agent_id)
    )
    rows = (await db.execute(agents_q)).all()
    result = []
    for row in rows:
        user = (await db.execute(select(User).where(User.id == row.assigned_agent_id))).scalars().first()

        # Count kept PTPs for this agent
        kept_q = select(func.count()).where(
            PromiseToPay.agent_id == row.assigned_agent_id,
            PromiseToPay.status == PTPStatus.KEPT,
        )
        kept = (await db.execute(kept_q)).scalar() or 0
        total_ptp_q = select(func.count()).where(
            PromiseToPay.agent_id == row.assigned_agent_id,
        )
        total_ptp = (await db.execute(total_ptp_q)).scalar() or 0

        result.append({
            "agent_id": row.assigned_agent_id,
            "name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "total_cases": row.total_cases,
            "resolved_cases": row.resolved or 0,
            "resolution_rate": round((row.resolved or 0) / max(row.total_cases, 1), 4),
            "total_overdue": float(row.overdue),
            "ptp_kept": kept,
            "ptp_total": total_ptp,
            "ptp_kept_rate": round(kept / max(total_ptp, 1), 4),
        })

    return sorted(result, key=lambda x: x["resolution_rate"], reverse=True)
