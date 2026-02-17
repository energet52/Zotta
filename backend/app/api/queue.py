"""Application Queue Management API.

Core queue, stages, assignment, staff, config, exceptions, analytics endpoints.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import require_roles
from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.audit import AuditLog
from app.models.queue import (
    QueueConfig, QueueEntry, QueueEntryStatus, QueueStage,
    StaffQueueProfile, QueueEvent, QueueException,
    AssignmentMode, SLAMode, ExceptionStatus,
)
from app.services.queue_priority import explain_priority, recalculate_all_priorities
from app.services.queue_assignment import (
    suggest_assignment, auto_assign_pending, rebalance, explain_assignment,
)
from app.services.queue_ai import (
    generate_handoff_summary, generate_insights, compute_completeness,
    estimate_complexity, analyze_exception_precedent,
)
from app.services.queue_sla import (
    check_sla_status, pause_sla, resume_sla, calculate_sla_deadline,
    calculate_sla_warning,
)

try:
    from app.services.error_logger import log_error
except ImportError:
    async def log_error(*a, **kw):
        pass

logger = logging.getLogger(__name__)

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)
ADMIN_ROLES = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)


# ── Pydantic Schemas ─────────────────────────────────────────

class ConfigUpdate(BaseModel):
    assignment_mode: Optional[str] = None
    stages_enabled: Optional[bool] = None
    sla_mode: Optional[str] = None
    authority_limits_enabled: Optional[bool] = None
    skills_routing_enabled: Optional[bool] = None
    exceptions_formal: Optional[bool] = None
    segregation_of_duties: Optional[bool] = None
    target_turnaround_hours: Optional[int] = None
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None
    business_days: Optional[list[int]] = None
    holidays: Optional[list[str]] = None
    timezone: Optional[str] = None
    auto_expire_days: Optional[int] = None
    follow_up_days: Optional[list[int]] = None
    ai_config: Optional[dict] = None


class StageCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    sort_order: int = 0
    is_mandatory: bool = True
    assignment_mode: Optional[str] = None
    allowed_roles: Optional[list[str]] = None
    skip_conditions: Optional[dict] = None
    can_parallel_with: Optional[list[str]] = None
    sla_target_hours: Optional[int] = None
    sla_warning_hours: Optional[int] = None


class StageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    is_mandatory: Optional[bool] = None
    assignment_mode: Optional[str] = None
    allowed_roles: Optional[list[str]] = None
    skip_conditions: Optional[dict] = None
    can_parallel_with: Optional[list[str]] = None
    sla_target_hours: Optional[int] = None
    sla_warning_hours: Optional[int] = None


class StaffProfileUpdate(BaseModel):
    is_available: Optional[bool] = None
    max_concurrent: Optional[int] = None
    skills: Optional[dict] = None
    authority_max_amount: Optional[float] = None
    authority_risk_grades: Optional[list[str]] = None
    authority_products: Optional[list[int]] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None


class ReturnToBorrowerRequest(BaseModel):
    reason: str


class ExceptionCreate(BaseModel):
    exception_type: str
    recommendation: Optional[str] = None


class ExceptionResolve(BaseModel):
    status: str  # approved or declined
    notes: Optional[str] = None


class AdvanceStageRequest(BaseModel):
    stage_slug: Optional[str] = None


class ReturnToStageRequest(BaseModel):
    stage_slug: str
    reason: str


# ── Helpers ──────────────────────────────────────────────────

async def _get_or_create_config(db: AsyncSession) -> QueueConfig:
    result = await db.execute(select(QueueConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = QueueConfig()
        db.add(config)
        await db.flush()
        await db.refresh(config)
    return config


SYNCABLE_STATUSES = [
    LoanStatus.SUBMITTED,
    LoanStatus.UNDER_REVIEW,
    LoanStatus.CREDIT_CHECK,
    LoanStatus.DECISION_PENDING,
    LoanStatus.AWAITING_DOCUMENTS,
]

DECIDED_STATUSES = [
    LoanStatus.APPROVED,
    LoanStatus.DECLINED,
    LoanStatus.DISBURSED,
    LoanStatus.CANCELLED,
    LoanStatus.VOIDED,
]


async def _ensure_queue_entries(db: AsyncSession) -> int:
    """Inline sync: create QueueEntry records for applications that lack one.

    This runs on every queue read so the queue works even without Celery.
    It is idempotent and fast — only inserts missing entries.
    """
    # IDs that already have an entry
    existing_result = await db.execute(select(QueueEntry.application_id))
    existing_ids = {row[0] for row in existing_result.all()}

    # Applications that should be in the queue
    apps_result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.status.in_(SYNCABLE_STATUSES),
        )
    )
    apps = apps_result.scalars().all()

    created = 0
    for app in apps:
        if app.id in existing_ids:
            continue

        status_val = QueueEntryStatus.NEW.value
        if app.status == LoanStatus.AWAITING_DOCUMENTS:
            status_val = QueueEntryStatus.WAITING_BORROWER.value
        elif app.assigned_underwriter_id:
            status_val = QueueEntryStatus.IN_PROGRESS.value

        entry = QueueEntry(
            application_id=app.id,
            status=status_val,
            assigned_to_id=app.assigned_underwriter_id,
            claimed_by_id=app.assigned_underwriter_id,
            stage_entered_at=app.submitted_at or app.created_at,
        )
        db.add(entry)
        created += 1

    # Also mark decided applications
    if existing_ids:
        decided_apps_result = await db.execute(
            select(LoanApplication.id).where(
                LoanApplication.status.in_(DECIDED_STATUSES),
                LoanApplication.id.in_(existing_ids),
            )
        )
        decided_app_ids = {row[0] for row in decided_apps_result.all()}

        if decided_app_ids:
            active_result = await db.execute(
                select(QueueEntry).where(
                    QueueEntry.application_id.in_(decided_app_ids),
                    QueueEntry.status != QueueEntryStatus.DECIDED.value,
                )
            )
            for entry in active_result.scalars().all():
                entry.status = QueueEntryStatus.DECIDED.value

    if created > 0:
        await db.flush()
        logger.info("Inline queue sync: created %d entries", created)

    return created


def _entry_to_dict(
    entry: QueueEntry,
    application: LoanApplication | None = None,
    config: QueueConfig | None = None,
    applicant_name: str | None = None,
    applicant_id: int | None = None,
    assigned_to_name: str | None = None,
) -> dict:
    """Convert a QueueEntry to a dict. All data must be pre-loaded — no lazy access."""
    app = application
    sla_status = check_sla_status(entry, config) if config else "none"

    d: dict[str, Any] = {
        "id": entry.id,
        "application_id": entry.application_id,
        "priority_score": entry.priority_score,
        "priority_factors": entry.priority_factors,
        "status": entry.status,
        "queue_stage_id": entry.queue_stage_id,
        "assigned_to_id": entry.assigned_to_id,
        "suggested_for_id": entry.suggested_for_id,
        "claimed_at": entry.claimed_at.isoformat() if entry.claimed_at else None,
        "claimed_by_id": entry.claimed_by_id,
        "waiting_since": entry.waiting_since.isoformat() if entry.waiting_since else None,
        "waiting_reason": entry.waiting_reason,
        "sla_status": sla_status,
        "sla_deadline": entry.sla_deadline.isoformat() if entry.sla_deadline else None,
        "return_count": entry.return_count,
        "is_stuck": entry.is_stuck,
        "is_flagged": entry.is_flagged,
        "flag_reasons": entry.flag_reasons,
        "ai_summary": entry.ai_summary,
        "completeness_score": entry.completeness_score,
        "complexity_estimate_hours": entry.complexity_estimate_hours,
        "channel": entry.channel,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }

    if app:
        d["reference_number"] = app.reference_number
        d["amount_requested"] = float(app.amount_requested) if app.amount_requested else None
        d["term_months"] = app.term_months
        d["purpose"] = app.purpose.value if app.purpose else None
        d["loan_status"] = app.status.value if app.status else None
        d["submitted_at"] = app.submitted_at.isoformat() if app.submitted_at else None

    d["applicant_name"] = applicant_name
    d["applicant_id"] = applicant_id or (app.applicant_id if app else None)
    d["assigned_to_name"] = assigned_to_name

    return d


def _stage_to_dict(stage: QueueStage) -> dict:
    return {
        "id": stage.id,
        "name": stage.name,
        "slug": stage.slug,
        "description": stage.description,
        "sort_order": stage.sort_order,
        "is_active": stage.is_active,
        "is_mandatory": stage.is_mandatory,
        "assignment_mode": stage.assignment_mode,
        "allowed_roles": stage.allowed_roles,
        "skip_conditions": stage.skip_conditions,
        "can_parallel_with": stage.can_parallel_with,
        "sla_target_hours": stage.sla_target_hours,
        "sla_warning_hours": stage.sla_warning_hours,
    }


def _event_to_dict(event: QueueEvent) -> dict:
    return {
        "id": event.id,
        "queue_entry_id": event.queue_entry_id,
        "application_id": event.application_id,
        "event_type": event.event_type,
        "actor_id": event.actor_id,
        "from_value": event.from_value,
        "to_value": event.to_value,
        "details": event.details,
        "ai_summary": event.ai_summary,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


# ══════════════════════════════════════════════════════════════
# CORE QUEUE ENDPOINTS
# ══════════════════════════════════════════════════════════════


@router.post("/sync")
async def sync_queue(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Manually sync queue entries from loan applications."""
    try:
        created = await _ensure_queue_entries(db)
        return {"message": f"Synced {created} new entries", "created": created}
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="sync_queue")
        raise


@router.get("/shared")
async def get_shared_queue(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    stage: Optional[str] = Query(None),
):
    """The shared prioritized queue -- all unassigned + pool entries."""
    try:
        config = await _get_or_create_config(db)
        await _ensure_queue_entries(db)

        from sqlalchemy.orm import aliased
        Applicant = aliased(User)
        Assignee = aliased(User)

        q = (
            select(
                QueueEntry,
                LoanApplication,
                Applicant.first_name.label("app_first"),
                Applicant.last_name.label("app_last"),
                Applicant.id.label("app_user_id"),
                Assignee.first_name.label("asgn_first"),
                Assignee.last_name.label("asgn_last"),
            )
            .join(LoanApplication, QueueEntry.application_id == LoanApplication.id)
            .join(Applicant, LoanApplication.applicant_id == Applicant.id)
            .outerjoin(Assignee, QueueEntry.assigned_to_id == Assignee.id)
            .where(QueueEntry.status.in_([
                QueueEntryStatus.NEW.value,
                QueueEntryStatus.IN_PROGRESS.value,
            ]))
            .order_by(desc(QueueEntry.priority_score))
        )

        if config.assignment_mode == AssignmentMode.AUTO.value:
            q = q.where(QueueEntry.assigned_to_id.is_(None))
        elif config.assignment_mode == AssignmentMode.MANAGER.value:
            q = q.where(QueueEntry.assigned_to_id.is_(None))

        if stage:
            q = q.join(QueueStage, QueueEntry.queue_stage_id == QueueStage.id).where(
                QueueStage.slug == stage
            )

        # Count
        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        results = await db.execute(q.offset(offset).limit(limit))
        items = [
            _entry_to_dict(
                entry, app, config,
                applicant_name=f"{first} {last}" if first else None,
                applicant_id=uid,
                assigned_to_name=f"{af} {al}" if af else None,
            )
            for entry, app, first, last, uid, af, al in results.all()
        ]

        return {"items": items, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_shared_queue")
        raise


@router.get("/my-queue")
async def get_my_queue(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Applications assigned to or suggested for the current user."""
    try:
        config = await _get_or_create_config(db)
        await _ensure_queue_entries(db)

        from sqlalchemy.orm import aliased
        Applicant = aliased(User)
        Assignee = aliased(User)

        q = (
            select(
                QueueEntry,
                LoanApplication,
                Applicant.first_name.label("app_first"),
                Applicant.last_name.label("app_last"),
                Applicant.id.label("app_user_id"),
                Assignee.first_name.label("asgn_first"),
                Assignee.last_name.label("asgn_last"),
            )
            .join(LoanApplication, QueueEntry.application_id == LoanApplication.id)
            .join(Applicant, LoanApplication.applicant_id == Applicant.id)
            .outerjoin(Assignee, QueueEntry.assigned_to_id == Assignee.id)
            .where(
                QueueEntry.status.in_([
                    QueueEntryStatus.NEW.value,
                    QueueEntryStatus.IN_PROGRESS.value,
                    QueueEntryStatus.ON_HOLD.value,
                ]),
                or_(
                    QueueEntry.assigned_to_id == current_user.id,
                    QueueEntry.suggested_for_id == current_user.id,
                    QueueEntry.claimed_by_id == current_user.id,
                ),
            )
            .order_by(desc(QueueEntry.priority_score))
        )
        results = await db.execute(q)

        items = []
        for entry, app, first, last, uid, af, al in results.all():
            d = _entry_to_dict(
                entry, app, config,
                applicant_name=f"{first} {last}" if first else None,
                applicant_id=uid,
                assigned_to_name=f"{af} {al}" if af else None,
            )
            d["is_suggestion"] = (
                entry.suggested_for_id == current_user.id
                and entry.assigned_to_id != current_user.id
            )
            items.append(d)

        return {"items": items, "total": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_my_queue")
        raise


@router.get("/waiting")
async def get_waiting_queue(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Applications waiting for borrower response."""
    try:
        config = await _get_or_create_config(db)
        await _ensure_queue_entries(db)

        from sqlalchemy.orm import aliased
        Applicant = aliased(User)
        Assignee = aliased(User)

        q = (
            select(
                QueueEntry,
                LoanApplication,
                Applicant.first_name.label("app_first"),
                Applicant.last_name.label("app_last"),
                Applicant.id.label("app_user_id"),
                Assignee.first_name.label("asgn_first"),
                Assignee.last_name.label("asgn_last"),
            )
            .join(LoanApplication, QueueEntry.application_id == LoanApplication.id)
            .join(Applicant, LoanApplication.applicant_id == Applicant.id)
            .outerjoin(Assignee, QueueEntry.assigned_to_id == Assignee.id)
            .where(QueueEntry.status == QueueEntryStatus.WAITING_BORROWER.value)
            .order_by(QueueEntry.waiting_since.asc())
        )
        results = await db.execute(q)
        items = [
            _entry_to_dict(
                entry, app, config,
                applicant_name=f"{first} {last}" if first else None,
                applicant_id=uid,
                assigned_to_name=f"{af} {al}" if af else None,
            )
            for entry, app, first, last, uid, af, al in results.all()
        ]
        return {"items": items, "total": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_waiting_queue")
        raise


@router.post("/{entry_id}/claim")
async def claim_entry(
    entry_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """One-click claim. Atomic: returns 409 if already claimed."""
    try:
        result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        if entry.claimed_by_id and entry.claimed_by_id != current_user.id:
            raise HTTPException(status_code=409, detail="Already claimed by another user")

        if entry.status not in (QueueEntryStatus.NEW.value, QueueEntryStatus.IN_PROGRESS.value):
            raise HTTPException(status_code=400, detail=f"Cannot claim entry in status '{entry.status}'")

        now = datetime.now(timezone.utc)
        entry.claimed_by_id = current_user.id
        entry.claimed_at = now
        entry.assigned_to_id = current_user.id
        entry.status = QueueEntryStatus.IN_PROGRESS.value

        # Update the loan application status too
        app_result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == entry.application_id)
        )
        application = app_result.scalar_one_or_none()
        if application and application.status == LoanStatus.SUBMITTED:
            application.status = LoanStatus.UNDER_REVIEW
            application.assigned_underwriter_id = current_user.id

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="claimed",
            actor_id=current_user.id,
            to_value={"user_id": current_user.id},
        )
        db.add(event)

        # Update staff load
        profile_result = await db.execute(
            select(StaffQueueProfile).where(StaffQueueProfile.user_id == current_user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.current_load_count = profile.current_load_count + 1

        await db.flush()
        return {"message": "Claimed", "entry_id": entry.id, "application_id": entry.application_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="claim_entry")
        raise


@router.post("/{entry_id}/release")
async def release_entry(
    entry_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Release an entry back to the shared pool."""
    try:
        result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        old_user = entry.assigned_to_id
        entry.claimed_by_id = None
        entry.claimed_at = None
        entry.assigned_to_id = None
        entry.suggested_for_id = None
        entry.status = QueueEntryStatus.NEW.value

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="released",
            actor_id=current_user.id,
            from_value={"user_id": old_user},
        )
        db.add(event)

        # Update staff load
        if old_user:
            profile_result = await db.execute(
                select(StaffQueueProfile).where(StaffQueueProfile.user_id == old_user)
            )
            profile = profile_result.scalar_one_or_none()
            if profile and profile.current_load_count > 0:
                profile.current_load_count -= 1

        await db.flush()
        return {"message": "Released back to pool"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="release_entry")
        raise


@router.post("/{entry_id}/return-to-borrower")
async def return_to_borrower(
    entry_id: int,
    body: ReturnToBorrowerRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Mark entry as waiting for borrower. Pauses SLA."""
    try:
        result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        config = await _get_or_create_config(db)

        old_status = entry.status
        entry.status = QueueEntryStatus.WAITING_BORROWER.value
        entry.waiting_since = datetime.now(timezone.utc)
        entry.waiting_reason = body.reason
        entry.return_count += 1

        # Pause SLA
        pause_sla(entry)

        # Update loan status
        app_result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == entry.application_id)
        )
        application = app_result.scalar_one_or_none()
        if application:
            application.status = LoanStatus.AWAITING_DOCUMENTS

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="returned_to_borrower",
            actor_id=current_user.id,
            from_value={"status": old_status},
            to_value={"status": entry.status, "reason": body.reason},
        )
        db.add(event)
        await db.flush()
        return {"message": "Returned to borrower", "waiting_reason": body.reason}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="return_to_borrower")
        raise


@router.post("/{entry_id}/borrower-responded")
async def borrower_responded(
    entry_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Mark that borrower responded. Resumes SLA with priority boost."""
    try:
        result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        config = await _get_or_create_config(db)

        entry.status = QueueEntryStatus.NEW.value
        entry.waiting_since = None
        entry.waiting_reason = None

        # Resume SLA
        resume_sla(entry, config)

        # Priority boost will happen on next recalculation (return_count is already incremented)

        # Update loan status
        app_result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == entry.application_id)
        )
        application = app_result.scalar_one_or_none()
        if application:
            application.status = LoanStatus.UNDER_REVIEW

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="borrower_responded",
            actor_id=current_user.id,
        )
        db.add(event)
        await db.flush()
        return {"message": "Borrower responded, back in queue with priority boost"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="borrower_responded")
        raise


@router.get("/{entry_id}/explain")
async def explain_entry_priority(
    entry_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """AI explains why this entry is at its current position."""
    try:
        explanation = await explain_priority(entry_id, db)
        return {"explanation": explanation}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="explain_entry_priority")
        raise


@router.get("/{entry_id}/timeline")
async def get_entry_timeline(
    entry_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Full event history for a queue entry."""
    try:
        events_result = await db.execute(
            select(QueueEvent)
            .where(QueueEvent.queue_entry_id == entry_id)
            .order_by(QueueEvent.created_at.asc())
        )
        events = events_result.scalars().all()
        return [_event_to_dict(e) for e in events]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_entry_timeline")
        raise


@router.get("/awareness")
async def get_awareness(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Ambient stats: pending count, avg turnaround, personal stats, team workload."""
    try:
        await _ensure_queue_entries(db)
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        # Pending count
        pending_result = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.status.in_([QueueEntryStatus.NEW.value, QueueEntryStatus.IN_PROGRESS.value])
            )
        )
        pending = pending_result.scalar() or 0

        # Waiting count
        waiting_result = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.status == QueueEntryStatus.WAITING_BORROWER.value
            )
        )
        waiting = waiting_result.scalar() or 0

        # Avg turnaround (30 days)
        avg_result = await db.execute(
            select(func.avg(
                func.extract("epoch", LoanApplication.decided_at - LoanApplication.submitted_at) / 3600
            )).where(
                LoanApplication.decided_at.is_not(None),
                LoanApplication.submitted_at.is_not(None),
                LoanApplication.decided_at >= thirty_days_ago,
            )
        )
        avg_turnaround_hours = avg_result.scalar()

        # Personal stats
        my_active = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.assigned_to_id == current_user.id,
                QueueEntry.status.in_([QueueEntryStatus.IN_PROGRESS.value, QueueEntryStatus.NEW.value]),
            )
        )
        my_count = my_active.scalar() or 0

        # Today's decisions
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        my_decided_result = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.claimed_by_id == current_user.id,
                QueueEntry.status == QueueEntryStatus.DECIDED.value,
                QueueEntry.updated_at >= today_start,
            )
        )
        my_decided_today = my_decided_result.scalar() or 0

        # Team workload
        team_result = await db.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                func.coalesce(StaffQueueProfile.current_load_count, 0).label("load"),
                func.coalesce(StaffQueueProfile.max_concurrent, 10).label("max_load"),
                func.coalesce(StaffQueueProfile.is_available, True).label("available"),
            )
            .outerjoin(StaffQueueProfile, User.id == StaffQueueProfile.user_id)
            .where(User.role.in_([r.value for r in STAFF_ROLES]), User.is_active == True)
        )
        team = [
            {
                "user_id": row.id,
                "name": f"{row.first_name} {row.last_name}",
                "load": row.load,
                "max_load": row.max_load,
                "available": row.available,
            }
            for row in team_result.all()
        ]

        config = await _get_or_create_config(db)

        return {
            "pending": pending,
            "waiting": waiting,
            "avg_turnaround_hours": round(avg_turnaround_hours, 1) if avg_turnaround_hours else None,
            "my_active": my_count,
            "my_decided_today": my_decided_today,
            "team": team,
            "config": {
                "assignment_mode": config.assignment_mode,
                "stages_enabled": config.stages_enabled,
                "sla_mode": config.sla_mode,
                "authority_limits_enabled": config.authority_limits_enabled,
                "skills_routing_enabled": config.skills_routing_enabled,
                "exceptions_formal": config.exceptions_formal,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_awareness")
        raise


# ══════════════════════════════════════════════════════════════
# STAGE ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.post("/{entry_id}/advance")
async def advance_stage(
    entry_id: int,
    body: AdvanceStageRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Move entry to next stage (or a specified stage)."""
    try:
        entry_result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = entry_result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        config = await _get_or_create_config(db)
        if not config.stages_enabled:
            raise HTTPException(status_code=400, detail="Stages are not enabled")

        old_stage_id = entry.queue_stage_id

        if body.stage_slug:
            stage_result = await db.execute(
                select(QueueStage).where(QueueStage.slug == body.stage_slug, QueueStage.is_active == True)
            )
            stage = stage_result.scalar_one_or_none()
            if not stage:
                raise HTTPException(status_code=404, detail="Stage not found")
            entry.queue_stage_id = stage.id
        else:
            # Advance to next by sort_order
            if entry.queue_stage_id:
                current_stage_result = await db.execute(
                    select(QueueStage).where(QueueStage.id == entry.queue_stage_id)
                )
                current_stage = current_stage_result.scalar_one_or_none()
                current_order = current_stage.sort_order if current_stage else -1
            else:
                current_order = -1

            next_result = await db.execute(
                select(QueueStage)
                .where(QueueStage.is_active == True, QueueStage.sort_order > current_order)
                .order_by(QueueStage.sort_order.asc())
                .limit(1)
            )
            next_stage = next_result.scalar_one_or_none()
            if next_stage:
                entry.queue_stage_id = next_stage.id
            else:
                entry.queue_stage_id = None  # past last stage

        entry.stage_entered_at = datetime.now(timezone.utc)

        # Generate handoff summary
        summary = await generate_handoff_summary(entry.application_id, db)
        entry.ai_summary = summary

        # Recalculate SLA for new stage
        if entry.queue_stage_id:
            stage_result = await db.execute(
                select(QueueStage).where(QueueStage.id == entry.queue_stage_id)
            )
            new_stage = stage_result.scalar_one_or_none()
            entry.sla_deadline = calculate_sla_deadline(entry, config, new_stage)
            entry.sla_warning_at = calculate_sla_warning(entry, config, new_stage)

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="stage_changed",
            actor_id=current_user.id,
            from_value={"stage_id": old_stage_id},
            to_value={"stage_id": entry.queue_stage_id},
            ai_summary=summary,
        )
        db.add(event)
        await db.flush()
        return {"message": "Advanced to next stage", "stage_id": entry.queue_stage_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="advance_stage")
        raise


@router.post("/{entry_id}/return-to-stage")
async def return_to_stage(
    entry_id: int,
    body: ReturnToStageRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Return entry to a previous stage."""
    try:
        entry_result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = entry_result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        stage_result = await db.execute(
            select(QueueStage).where(QueueStage.slug == body.stage_slug, QueueStage.is_active == True)
        )
        stage = stage_result.scalar_one_or_none()
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")

        old_stage_id = entry.queue_stage_id
        entry.queue_stage_id = stage.id
        entry.stage_entered_at = datetime.now(timezone.utc)
        entry.return_count += 1

        # Priority boost for returned entries
        entry.priority_score += 0.1

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="stage_changed",
            actor_id=current_user.id,
            from_value={"stage_id": old_stage_id},
            to_value={"stage_id": stage.id, "reason": body.reason, "is_return": True},
        )
        db.add(event)
        await db.flush()
        return {"message": f"Returned to stage '{stage.name}'"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="return_to_stage")
        raise


@router.get("/pipeline")
async def get_pipeline(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Pipeline view: counts per stage."""
    try:
        stages_result = await db.execute(
            select(QueueStage).where(QueueStage.is_active == True).order_by(QueueStage.sort_order)
        )
        stages = stages_result.scalars().all()

        pipeline = []
        for stage in stages:
            count_result = await db.execute(
                select(func.count()).select_from(QueueEntry).where(
                    QueueEntry.queue_stage_id == stage.id,
                    QueueEntry.status.in_([QueueEntryStatus.NEW.value, QueueEntryStatus.IN_PROGRESS.value]),
                )
            )
            count = count_result.scalar() or 0
            pipeline.append({**_stage_to_dict(stage), "entry_count": count})

        # Unassigned (no stage)
        no_stage_result = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.queue_stage_id.is_(None),
                QueueEntry.status.in_([QueueEntryStatus.NEW.value, QueueEntryStatus.IN_PROGRESS.value]),
            )
        )
        no_stage_count = no_stage_result.scalar() or 0

        return {"stages": pipeline, "unassigned_stage": no_stage_count}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_pipeline")
        raise


# ══════════════════════════════════════════════════════════════
# ASSIGNMENT ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.post("/{entry_id}/assign/{user_id}")
async def assign_entry(
    entry_id: int,
    user_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Manual assign an entry to a specific user."""
    try:
        entry_result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = entry_result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        old_user = entry.assigned_to_id
        entry.assigned_to_id = user_id
        entry.suggested_for_id = None

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="assigned",
            actor_id=current_user.id,
            from_value={"user_id": old_user},
            to_value={"user_id": user_id},
        )
        db.add(event)
        await db.flush()
        return {"message": "Assigned", "assigned_to": user_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="assign_entry")
        raise


@router.post("/{entry_id}/reassign/{user_id}")
async def reassign_entry(
    entry_id: int,
    user_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Reassign entry to a different user."""
    try:
        entry_result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = entry_result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        old_user = entry.assigned_to_id
        entry.assigned_to_id = user_id
        entry.suggested_for_id = None

        # Generate handoff summary
        summary = await generate_handoff_summary(entry.application_id, db)
        entry.ai_summary = summary

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="reassigned",
            actor_id=current_user.id,
            from_value={"user_id": old_user},
            to_value={"user_id": user_id},
            ai_summary=summary,
        )
        db.add(event)

        # Update load counts
        if old_user:
            old_profile_result = await db.execute(
                select(StaffQueueProfile).where(StaffQueueProfile.user_id == old_user)
            )
            old_profile = old_profile_result.scalar_one_or_none()
            if old_profile and old_profile.current_load_count > 0:
                old_profile.current_load_count -= 1

        new_profile_result = await db.execute(
            select(StaffQueueProfile).where(StaffQueueProfile.user_id == user_id)
        )
        new_profile = new_profile_result.scalar_one_or_none()
        if new_profile:
            new_profile.current_load_count += 1

        await db.flush()
        return {"message": "Reassigned", "from_user": old_user, "to_user": user_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="reassign_entry")
        raise


@router.post("/{entry_id}/defer")
async def defer_entry(
    entry_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Defer a suggestion back to pool (hybrid mode)."""
    try:
        entry_result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = entry_result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        entry.suggested_for_id = None
        if entry.assigned_to_id == current_user.id and entry.claimed_at is None:
            entry.assigned_to_id = None

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="deferred",
            actor_id=current_user.id,
        )
        db.add(event)
        await db.flush()
        return {"message": "Deferred back to pool"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="defer_entry")
        raise


@router.post("/rebalance")
async def trigger_rebalance(
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Trigger manual rebalance."""
    try:
        count = await rebalance(db)
        return {"message": f"Rebalanced {count} entries"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="trigger_rebalance")
        raise


@router.get("/{entry_id}/explain-assignment")
async def explain_entry_assignment(
    entry_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """AI explains why this entry was assigned to its current person."""
    try:
        explanation = await explain_assignment(entry_id, db)
        return {"explanation": explanation}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="explain_entry_assignment")
        raise


# ══════════════════════════════════════════════════════════════
# STAFF ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get("/staff")
async def list_staff(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List all staff with current workload and availability."""
    try:
        result = await db.execute(
            select(User, StaffQueueProfile)
            .outerjoin(StaffQueueProfile, User.id == StaffQueueProfile.user_id)
            .where(
                User.role.in_([r.value for r in STAFF_ROLES]),
                User.is_active == True,
            )
            .order_by(User.first_name)
        )

        staff = []
        for user, profile in result.all():
            staff.append({
                "user_id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "role": user.role.value,
                "is_available": profile.is_available if profile else True,
                "current_load": profile.current_load_count if profile else 0,
                "max_concurrent": profile.max_concurrent if profile else 10,
                "skills": profile.skills if profile else None,
                "authority_max_amount": float(profile.authority_max_amount) if profile and profile.authority_max_amount else None,
                "avg_processing_hours": profile.avg_processing_hours if profile else None,
                "has_profile": profile is not None,
            })

        return staff
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="list_staff")
        raise


@router.put("/staff/{user_id}/profile")
async def update_staff_profile(
    user_id: int,
    body: StaffProfileUpdate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update staff queue profile (skills, authority, availability)."""
    try:
        result = await db.execute(
            select(StaffQueueProfile).where(StaffQueueProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = StaffQueueProfile(user_id=user_id)
            db.add(profile)
            await db.flush()

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "shift_start" or key == "shift_end":
                if value:
                    from datetime import time as dt_time
                    parts = value.split(":")
                    value = dt_time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
            setattr(profile, key, value)

        await db.flush()
        return {"message": "Profile updated", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="update_staff_profile")
        raise


@router.post("/staff/{user_id}/need-help")
async def signal_need_help(
    user_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Signal overload, triggers partial rebalance."""
    try:
        # Get lowest priority unstarted entries for this user
        entries_result = await db.execute(
            select(QueueEntry).where(
                QueueEntry.assigned_to_id == user_id,
                QueueEntry.status == QueueEntryStatus.NEW.value,
                QueueEntry.claimed_at.is_(None),
            ).order_by(QueueEntry.priority_score.asc()).limit(3)
        )
        entries = entries_result.scalars().all()

        released = 0
        for entry in entries:
            entry.assigned_to_id = None
            entry.suggested_for_id = None
            event = QueueEvent(
                queue_entry_id=entry.id,
                application_id=entry.application_id,
                event_type="reassigned",
                actor_id=current_user.id,
                from_value={"user_id": user_id, "reason": "need_help"},
                to_value={"user_id": None},
            )
            db.add(event)
            released += 1

        # Update load count
        if released > 0:
            profile_result = await db.execute(
                select(StaffQueueProfile).where(StaffQueueProfile.user_id == user_id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                profile.current_load_count = max(0, profile.current_load_count - released)

        await db.flush()
        return {"message": f"Released {released} items to pool", "released": released}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="signal_need_help")
        raise


# ══════════════════════════════════════════════════════════════
# CONFIG ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get("/config")
async def get_config(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get current queue configuration."""
    try:
        config = await _get_or_create_config(db)
        return {
            "id": config.id,
            "assignment_mode": config.assignment_mode,
            "stages_enabled": config.stages_enabled,
            "sla_mode": config.sla_mode,
            "authority_limits_enabled": config.authority_limits_enabled,
            "skills_routing_enabled": config.skills_routing_enabled,
            "exceptions_formal": config.exceptions_formal,
            "segregation_of_duties": config.segregation_of_duties,
            "target_turnaround_hours": config.target_turnaround_hours,
            "business_hours_start": str(config.business_hours_start) if config.business_hours_start else "08:00",
            "business_hours_end": str(config.business_hours_end) if config.business_hours_end else "17:00",
            "business_days": config.business_days,
            "holidays": config.holidays,
            "timezone": config.timezone,
            "auto_expire_days": config.auto_expire_days,
            "follow_up_days": config.follow_up_days,
            "ai_config": config.ai_config,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_config")
        raise


@router.put("/config")
async def update_config(
    body: ConfigUpdate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update queue configuration."""
    try:
        config = await _get_or_create_config(db)

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in ("business_hours_start", "business_hours_end") and isinstance(value, str):
                from datetime import time as dt_time
                parts = value.split(":")
                value = dt_time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
            setattr(config, key, value)

        await db.flush()
        return {"message": "Configuration updated"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="update_config")
        raise


@router.get("/config/stages")
async def list_stages(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List pipeline stages."""
    try:
        result = await db.execute(
            select(QueueStage).order_by(QueueStage.sort_order)
        )
        stages = result.scalars().all()
        return [_stage_to_dict(s) for s in stages]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="list_stages")
        raise


@router.post("/config/stages", status_code=201)
async def create_stage(
    body: StageCreate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new pipeline stage."""
    try:
        existing = await db.execute(
            select(QueueStage).where(QueueStage.slug == body.slug)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Stage with slug '{body.slug}' already exists")

        stage = QueueStage(
            name=body.name,
            slug=body.slug,
            description=body.description,
            sort_order=body.sort_order,
            is_mandatory=body.is_mandatory,
            assignment_mode=body.assignment_mode,
            allowed_roles=body.allowed_roles,
            skip_conditions=body.skip_conditions,
            can_parallel_with=body.can_parallel_with,
            sla_target_hours=body.sla_target_hours,
            sla_warning_hours=body.sla_warning_hours,
        )
        db.add(stage)
        try:
            await db.flush()
        except Exception as flush_err:
            if "UniqueViolation" in str(type(flush_err).__name__) or "unique" in str(flush_err).lower():
                raise HTTPException(status_code=409, detail=f"Stage with slug '{body.slug}' already exists")
            raise
        await db.refresh(stage)
        return _stage_to_dict(stage)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="create_stage")
        raise


@router.put("/config/stages/{stage_id}")
async def update_stage(
    stage_id: int,
    body: StageUpdate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update a pipeline stage."""
    try:
        result = await db.execute(
            select(QueueStage).where(QueueStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(stage, key, value)

        await db.flush()
        return _stage_to_dict(stage)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="update_stage")
        raise


@router.delete("/config/stages/{stage_id}")
async def deactivate_stage(
    stage_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a pipeline stage."""
    try:
        result = await db.execute(
            select(QueueStage).where(QueueStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")

        stage.is_active = False
        await db.flush()
        return {"message": f"Stage '{stage.name}' deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="deactivate_stage")
        raise


# ══════════════════════════════════════════════════════════════
# EXCEPTION ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get("/exceptions")
async def list_exceptions(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None),
):
    """List exceptions."""
    try:
        q = select(QueueException).order_by(QueueException.created_at.desc())
        if status_filter:
            q = q.where(QueueException.status == status_filter)
        result = await db.execute(q.limit(100))
        exceptions = result.scalars().all()
        return [
            {
                "id": e.id,
                "queue_entry_id": e.queue_entry_id,
                "application_id": e.application_id,
                "exception_type": e.exception_type,
                "raised_by_id": e.raised_by_id,
                "assigned_approver_id": e.assigned_approver_id,
                "status": e.status,
                "recommendation": e.recommendation,
                "approver_notes": e.approver_notes,
                "escalation_level": e.escalation_level,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
            }
            for e in exceptions
        ]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="list_exceptions")
        raise


@router.post("/exceptions", status_code=201)
async def create_exception(
    body: ExceptionCreate,
    entry_id: int = Query(...),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Raise a formal exception on a queue entry."""
    try:
        entry_result = await db.execute(
            select(QueueEntry).where(QueueEntry.id == entry_id)
        )
        entry = entry_result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        exc = QueueException(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            exception_type=body.exception_type,
            raised_by_id=current_user.id,
            recommendation=body.recommendation,
        )
        db.add(exc)

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="exception_raised",
            actor_id=current_user.id,
            details={"exception_type": body.exception_type},
        )
        db.add(event)
        await db.flush()
        return {"id": exc.id, "message": "Exception raised"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="create_exception")
        raise


@router.post("/exceptions/{exception_id}/resolve")
async def resolve_exception(
    exception_id: int,
    body: ExceptionResolve,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Approve or decline an exception."""
    try:
        result = await db.execute(
            select(QueueException).where(QueueException.id == exception_id)
        )
        exc = result.scalar_one_or_none()
        if not exc:
            raise HTTPException(status_code=404, detail="Exception not found")

        if body.status not in ("approved", "declined"):
            raise HTTPException(status_code=400, detail="Status must be 'approved' or 'declined'")

        exc.status = body.status
        exc.assigned_approver_id = current_user.id
        exc.approver_notes = body.notes
        exc.resolved_at = datetime.now(timezone.utc)

        event = QueueEvent(
            queue_entry_id=exc.queue_entry_id,
            application_id=exc.application_id,
            event_type="exception_resolved",
            actor_id=current_user.id,
            details={"exception_id": exc.id, "status": body.status},
        )
        db.add(event)
        await db.flush()
        return {"message": f"Exception {body.status}", "id": exc.id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="resolve_exception")
        raise


@router.get("/exceptions/{exception_id}/precedent")
async def get_exception_precedent(
    exception_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """AI precedent analysis for an exception."""
    try:
        result = await analyze_exception_precedent(exception_id, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_exception_precedent")
        raise


# ══════════════════════════════════════════════════════════════
# ANALYTICS ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get("/analytics/ambient")
async def get_ambient_analytics(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Always-on ambient analytics data."""
    try:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        # Pending count + trend
        pending_result = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.status.in_([QueueEntryStatus.NEW.value, QueueEntryStatus.IN_PROGRESS.value])
            )
        )
        pending = pending_result.scalar() or 0

        pending_7d_result = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.status.in_([QueueEntryStatus.NEW.value, QueueEntryStatus.IN_PROGRESS.value]),
                QueueEntry.created_at >= seven_days_ago,
            )
        )
        new_last_7d = pending_7d_result.scalar() or 0

        # Decided last 7 days
        decided_7d_result = await db.execute(
            select(func.count()).select_from(QueueEntry).where(
                QueueEntry.status == QueueEntryStatus.DECIDED.value,
                QueueEntry.updated_at >= seven_days_ago,
            )
        )
        decided_7d = decided_7d_result.scalar() or 0

        # Avg turnaround
        avg_result = await db.execute(
            select(func.avg(
                func.extract("epoch", LoanApplication.decided_at - LoanApplication.submitted_at) / 3600
            )).where(
                LoanApplication.decided_at.is_not(None),
                LoanApplication.submitted_at.is_not(None),
                LoanApplication.decided_at >= thirty_days_ago,
            )
        )
        avg_turnaround = avg_result.scalar()

        return {
            "pending": pending,
            "new_last_7d": new_last_7d,
            "decided_last_7d": decided_7d,
            "avg_turnaround_hours": round(avg_turnaround, 1) if avg_turnaround else None,
            "trend": "growing" if new_last_7d > decided_7d else "shrinking" if decided_7d > new_last_7d else "stable",
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_ambient_analytics")
        raise


@router.get("/analytics/throughput")
async def get_throughput_analytics(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=7, le=90),
):
    """Throughput: applications in/out per day."""
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        # Submitted per day
        submitted_result = await db.execute(
            select(
                func.date(LoanApplication.submitted_at).label("day"),
                func.count().label("count"),
            ).where(
                LoanApplication.submitted_at >= start,
                LoanApplication.submitted_at.is_not(None),
            ).group_by(func.date(LoanApplication.submitted_at))
            .order_by(func.date(LoanApplication.submitted_at))
        )
        submitted_by_day = [{"date": str(r.day), "count": r.count} for r in submitted_result.all()]

        # Decided per day
        decided_result = await db.execute(
            select(
                func.date(LoanApplication.decided_at).label("day"),
                func.count().label("count"),
            ).where(
                LoanApplication.decided_at >= start,
                LoanApplication.decided_at.is_not(None),
            ).group_by(func.date(LoanApplication.decided_at))
            .order_by(func.date(LoanApplication.decided_at))
        )
        decided_by_day = [{"date": str(r.day), "count": r.count} for r in decided_result.all()]

        return {
            "period_days": days,
            "submitted_by_day": submitted_by_day,
            "decided_by_day": decided_by_day,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_throughput_analytics")
        raise


@router.get("/analytics/team")
async def get_team_analytics(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Per-person performance metrics."""
    try:
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        # Decisions per person (last 30 days)
        decisions_result = await db.execute(
            select(
                LoanApplication.assigned_underwriter_id,
                func.count().label("decisions"),
                func.avg(
                    func.extract("epoch", LoanApplication.decided_at - LoanApplication.submitted_at) / 3600
                ).label("avg_hours"),
            ).where(
                LoanApplication.decided_at >= thirty_days_ago,
                LoanApplication.decided_at.is_not(None),
                LoanApplication.assigned_underwriter_id.is_not(None),
            ).group_by(LoanApplication.assigned_underwriter_id)
        )

        team_stats = []
        for row in decisions_result.all():
            user_result = await db.execute(
                select(User.first_name, User.last_name).where(User.id == row.assigned_underwriter_id)
            )
            user_row = user_result.one_or_none()
            name = f"{user_row[0]} {user_row[1]}" if user_row else f"User #{row.assigned_underwriter_id}"

            team_stats.append({
                "user_id": row.assigned_underwriter_id,
                "name": name,
                "decisions_30d": row.decisions,
                "avg_turnaround_hours": round(row.avg_hours, 1) if row.avg_hours else None,
            })

        return {"period_days": 30, "team": team_stats}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_team_analytics")
        raise


@router.get("/analytics/insights")
async def get_ai_insights(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """AI-generated process insights."""
    try:
        insights = await generate_insights(db)
        return {"insights": insights}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.queue", function_name="get_ai_insights")
        raise
