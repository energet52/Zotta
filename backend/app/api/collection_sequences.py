"""Collection sequence management endpoints -- CRUD, enrollments, AI, analytics."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import require_roles
from app.database import get_db
from app.models.user import User, UserRole
from app.models.collection_sequence import (
    CollectionSequence, SequenceStep, MessageTemplate,
    SequenceEnrollment, StepExecution,
)
from app.models.collections_ext import CollectionCase, CaseStatus
from app.services.sequence_ai import (
    generate_sequence as ai_generate_sequence,
    optimize_sequence as ai_optimize_sequence,
    generate_template as ai_generate_template,
    compute_sequence_analytics,
    render_template,
)

try:
    from app.services.error_logger import log_error
except ImportError:
    async def log_error(*a, **kw):
        pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/collection-sequences", tags=["Collection Sequences"])

ADMIN_ROLES = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)


# ── Pydantic schemas ─────────────────────────────────────────

class StepCreate(BaseModel):
    step_number: int
    day_offset: int
    channel: str = "whatsapp"
    action_type: str = "send_message"
    template_id: Optional[int] = None
    custom_message: Optional[str] = None
    condition_json: Optional[dict] = None
    send_time: Optional[str] = None
    is_active: bool = True
    wait_for_response_hours: int = 0


class StepUpdate(BaseModel):
    step_number: Optional[int] = None
    day_offset: Optional[int] = None
    channel: Optional[str] = None
    action_type: Optional[str] = None
    template_id: Optional[int] = None
    custom_message: Optional[str] = None
    condition_json: Optional[dict] = None
    send_time: Optional[str] = None
    is_active: Optional[bool] = None
    wait_for_response_hours: Optional[int] = None


class SequenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    delinquency_stage: str
    is_active: bool = True
    is_default: bool = False
    priority: int = 0
    channels: Optional[list[str]] = None
    steps: Optional[list[StepCreate]] = None


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    delinquency_stage: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    priority: Optional[int] = None
    channels: Optional[list[str]] = None


class TemplateCreate(BaseModel):
    name: str
    channel: str = "whatsapp"
    tone: str = "friendly"
    category: str = "reminder"
    body: str
    subject: Optional[str] = None
    variables: Optional[list[str]] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    channel: Optional[str] = None
    tone: Optional[str] = None
    category: Optional[str] = None
    body: Optional[str] = None
    subject: Optional[str] = None
    variables: Optional[list[str]] = None
    is_active: Optional[bool] = None


class EnrollmentCreate(BaseModel):
    case_id: int
    sequence_id: int


class EnrollmentUpdate(BaseModel):
    status: Optional[str] = None
    paused_reason: Optional[str] = None


class GenerateSequenceRequest(BaseModel):
    description: str
    delinquency_stage: str


class GenerateTemplateRequest(BaseModel):
    channel: str = "whatsapp"
    tone: str = "friendly"
    category: str = "reminder"
    context: Optional[str] = None


class PreviewMessageRequest(BaseModel):
    body: str
    context: Optional[dict] = None


class OptimizeRequest(BaseModel):
    sequence_id: int


class ReorderStepsRequest(BaseModel):
    step_ids: list[int]


# ── Helpers ──────────────────────────────────────────────────

def _seq_to_dict(seq: CollectionSequence) -> dict:
    steps = getattr(seq, "steps", None) or []
    enrollments = getattr(seq, "enrollments", None) or []
    return {
        "id": seq.id,
        "name": seq.name,
        "description": seq.description,
        "delinquency_stage": seq.delinquency_stage,
        "is_active": seq.is_active,
        "is_default": seq.is_default,
        "priority": seq.priority,
        "channels": seq.channels,
        "ai_generated": seq.ai_generated,
        "ai_summary": seq.ai_summary,
        "created_by": seq.created_by,
        "created_at": seq.created_at.isoformat() if seq.created_at else None,
        "updated_at": seq.updated_at.isoformat() if seq.updated_at else None,
        "step_count": len(steps),
        "steps": [_step_to_dict(s) for s in steps],
        "enrollment_count": len(enrollments),
        "active_enrollment_count": sum(1 for e in enrollments if e.status == "active"),
    }


def _step_to_dict(step: SequenceStep) -> dict:
    return {
        "id": step.id,
        "sequence_id": step.sequence_id,
        "step_number": step.step_number,
        "day_offset": step.day_offset,
        "channel": step.channel,
        "action_type": step.action_type,
        "template_id": step.template_id,
        "custom_message": step.custom_message,
        "condition_json": step.condition_json,
        "send_time": step.send_time,
        "is_active": step.is_active,
        "wait_for_response_hours": step.wait_for_response_hours,
        "ai_effectiveness_score": step.ai_effectiveness_score,
    }


def _template_to_dict(t: MessageTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "channel": t.channel,
        "tone": t.tone,
        "category": t.category,
        "body": t.body,
        "subject": t.subject,
        "variables": t.variables,
        "is_ai_generated": t.is_ai_generated,
        "is_active": t.is_active,
        "created_by": t.created_by,
        "usage_count": t.usage_count,
        "response_rate": t.response_rate,
        "payment_rate": t.payment_rate,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _enrollment_to_dict(e: SequenceEnrollment) -> dict:
    case = getattr(e, "collection_case", None)
    seq = getattr(e, "sequence", None)
    loan = getattr(case, "loan_application", None) if case else None
    user = getattr(loan, "applicant_profile", None) if loan else None
    return {
        "id": e.id,
        "case_id": e.case_id,
        "sequence_id": e.sequence_id,
        "sequence_name": seq.name if seq else None,
        "current_step_number": e.current_step_number,
        "status": e.status,
        "paused_reason": e.paused_reason,
        "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        "cancelled_at": e.cancelled_at.isoformat() if e.cancelled_at else None,
        "dpd": case.dpd if case else None,
        "total_overdue": float(case.total_overdue) if case else None,
        "delinquency_stage": case.delinquency_stage.value if case and hasattr(case.delinquency_stage, 'value') else str(case.delinquency_stage) if case else None,
        "borrower_name": f"{user.first_name} {user.last_name}" if user and hasattr(user, 'first_name') else None,
        "loan_ref": f"ZL-{loan.id}" if loan else None,
    }


# ══════════════════════════════════════════════════════════════
# SEQUENCE CRUD
# ══════════════════════════════════════════════════════════════

@router.get("/sequences")
async def list_sequences(
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
    stage: Optional[str] = Query(None),
    active_only: bool = Query(False),
):
    try:
        q = select(CollectionSequence).options(
            selectinload(CollectionSequence.steps),
            selectinload(CollectionSequence.enrollments),
        ).order_by(desc(CollectionSequence.priority), CollectionSequence.name)

        if stage:
            q = q.where(CollectionSequence.delinquency_stage == stage)
        if active_only:
            q = q.where(CollectionSequence.is_active == True)

        result = await db.execute(q)
        seqs = result.scalars().unique().all()
        return [_seq_to_dict(s) for s in seqs]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="list_sequences")
        raise


@router.post("/sequences", status_code=201)
async def create_sequence(
    body: SequenceCreate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        seq = CollectionSequence(
            name=body.name,
            description=body.description,
            delinquency_stage=body.delinquency_stage,
            is_active=body.is_active,
            is_default=body.is_default,
            priority=body.priority,
            channels=body.channels,
            created_by=current_user.id,
        )
        db.add(seq)
        await db.flush()

        if body.steps:
            for s in body.steps:
                step = SequenceStep(
                    sequence_id=seq.id,
                    step_number=s.step_number,
                    day_offset=s.day_offset,
                    channel=s.channel,
                    action_type=s.action_type,
                    template_id=s.template_id,
                    custom_message=s.custom_message,
                    condition_json=s.condition_json,
                    send_time=s.send_time,
                    is_active=s.is_active,
                    wait_for_response_hours=s.wait_for_response_hours,
                )
                db.add(step)

        await db.flush()

        result = await db.execute(
            select(CollectionSequence)
            .options(selectinload(CollectionSequence.steps), selectinload(CollectionSequence.enrollments))
            .where(CollectionSequence.id == seq.id)
        )
        return _seq_to_dict(result.scalar_one())
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="create_sequence")
        raise


@router.get("/sequences/{sequence_id}")
async def get_sequence(
    sequence_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(CollectionSequence)
            .options(selectinload(CollectionSequence.steps), selectinload(CollectionSequence.enrollments))
            .where(CollectionSequence.id == sequence_id)
        )
        seq = result.scalar_one_or_none()
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        return _seq_to_dict(seq)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="get_sequence")
        raise


@router.put("/sequences/{sequence_id}")
async def update_sequence(
    sequence_id: int,
    body: SequenceUpdate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(CollectionSequence)
            .options(selectinload(CollectionSequence.steps), selectinload(CollectionSequence.enrollments))
            .where(CollectionSequence.id == sequence_id)
        )
        seq = result.scalar_one_or_none()
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")

        for field in ("name", "description", "delinquency_stage", "is_active", "is_default", "priority", "channels"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(seq, field, val)

        await db.flush()
        await db.refresh(seq)

        result2 = await db.execute(
            select(CollectionSequence)
            .options(selectinload(CollectionSequence.steps), selectinload(CollectionSequence.enrollments))
            .where(CollectionSequence.id == sequence_id)
        )
        return _seq_to_dict(result2.scalar_one())
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="update_sequence")
        raise


@router.delete("/sequences/{sequence_id}")
async def delete_sequence(
    sequence_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(CollectionSequence).where(CollectionSequence.id == sequence_id)
        )
        seq = result.scalar_one_or_none()
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        seq.is_active = False
        await db.flush()
        return {"message": "Sequence deactivated", "id": sequence_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="delete_sequence")
        raise


@router.post("/sequences/{sequence_id}/duplicate", status_code=201)
async def duplicate_sequence(
    sequence_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(CollectionSequence)
            .options(selectinload(CollectionSequence.steps))
            .where(CollectionSequence.id == sequence_id)
        )
        original = result.scalar_one_or_none()
        if not original:
            raise HTTPException(status_code=404, detail="Sequence not found")

        clone = CollectionSequence(
            name=f"{original.name} (Copy)",
            description=original.description,
            delinquency_stage=original.delinquency_stage,
            is_active=False,
            is_default=False,
            priority=original.priority,
            channels=original.channels,
            ai_generated=original.ai_generated,
            ai_summary=original.ai_summary,
            created_by=current_user.id,
        )
        db.add(clone)
        await db.flush()

        for step in original.steps:
            db.add(SequenceStep(
                sequence_id=clone.id,
                step_number=step.step_number,
                day_offset=step.day_offset,
                channel=step.channel,
                action_type=step.action_type,
                template_id=step.template_id,
                custom_message=step.custom_message,
                condition_json=step.condition_json,
                send_time=step.send_time,
                is_active=step.is_active,
                wait_for_response_hours=step.wait_for_response_hours,
            ))

        await db.flush()

        result2 = await db.execute(
            select(CollectionSequence)
            .options(selectinload(CollectionSequence.steps), selectinload(CollectionSequence.enrollments))
            .where(CollectionSequence.id == clone.id)
        )
        return _seq_to_dict(result2.scalar_one())
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="duplicate_sequence")
        raise


# ══════════════════════════════════════════════════════════════
# STEP MANAGEMENT
# ══════════════════════════════════════════════════════════════

@router.post("/sequences/{sequence_id}/steps", status_code=201)
async def add_step(
    sequence_id: int,
    body: StepCreate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        seq_exists = (await db.execute(
            select(CollectionSequence.id).where(CollectionSequence.id == sequence_id)
        )).scalar_one_or_none()
        if not seq_exists:
            raise HTTPException(status_code=404, detail="Sequence not found")

        step = SequenceStep(
            sequence_id=sequence_id,
            step_number=body.step_number,
            day_offset=body.day_offset,
            channel=body.channel,
            action_type=body.action_type,
            template_id=body.template_id,
            custom_message=body.custom_message,
            condition_json=body.condition_json,
            send_time=body.send_time,
            is_active=body.is_active,
            wait_for_response_hours=body.wait_for_response_hours,
        )
        db.add(step)
        await db.flush()
        return _step_to_dict(step)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="add_step")
        raise


@router.put("/steps/{step_id}")
async def update_step(
    step_id: int,
    body: StepUpdate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(SequenceStep).where(SequenceStep.id == step_id))
        step = result.scalar_one_or_none()
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")

        for field in ("step_number", "day_offset", "channel", "action_type", "template_id",
                      "custom_message", "condition_json", "send_time", "is_active", "wait_for_response_hours"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(step, field, val)

        await db.flush()
        return _step_to_dict(step)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="update_step")
        raise


@router.delete("/steps/{step_id}")
async def delete_step(
    step_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(SequenceStep).where(SequenceStep.id == step_id))
        step = result.scalar_one_or_none()
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")
        await db.delete(step)
        await db.flush()
        return {"message": "Step deleted", "id": step_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="delete_step")
        raise


@router.put("/sequences/{sequence_id}/reorder-steps")
async def reorder_steps(
    sequence_id: int,
    body: ReorderStepsRequest,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(SequenceStep).where(SequenceStep.sequence_id == sequence_id)
        )
        steps = {s.id: s for s in result.scalars().all()}

        for idx, step_id in enumerate(body.step_ids, 1):
            if step_id in steps:
                steps[step_id].step_number = idx

        await db.flush()
        return {"message": "Steps reordered", "order": body.step_ids}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="reorder_steps")
        raise


# ══════════════════════════════════════════════════════════════
# TEMPLATE CRUD
# ══════════════════════════════════════════════════════════════

@router.get("/templates")
async def list_templates(
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
    channel: Optional[str] = Query(None),
    tone: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    try:
        q = select(MessageTemplate).where(MessageTemplate.is_active == True)
        if channel:
            q = q.where(MessageTemplate.channel == channel)
        if tone:
            q = q.where(MessageTemplate.tone == tone)
        if category:
            q = q.where(MessageTemplate.category == category)
        q = q.order_by(MessageTemplate.name)

        result = await db.execute(q)
        return [_template_to_dict(t) for t in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="list_templates")
        raise


@router.post("/templates", status_code=201)
async def create_template(
    body: TemplateCreate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = MessageTemplate(
            name=body.name,
            channel=body.channel,
            tone=body.tone,
            category=body.category,
            body=body.body,
            subject=body.subject,
            variables=body.variables,
            created_by=current_user.id,
        )
        db.add(t)
        await db.flush()
        return _template_to_dict(t)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="create_template")
        raise


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    body: TemplateUpdate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(MessageTemplate).where(MessageTemplate.id == template_id))
        t = result.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")

        for field in ("name", "channel", "tone", "category", "body", "subject", "variables", "is_active"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(t, field, val)

        await db.flush()
        return _template_to_dict(t)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="update_template")
        raise


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(MessageTemplate).where(MessageTemplate.id == template_id))
        t = result.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        t.is_active = False
        await db.flush()
        return {"message": "Template deactivated", "id": template_id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="delete_template")
        raise


# ══════════════════════════════════════════════════════════════
# ENROLLMENT MANAGEMENT
# ══════════════════════════════════════════════════════════════

@router.get("/enrollments")
async def list_enrollments(
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    sequence_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        q = (
            select(SequenceEnrollment)
            .options(
                selectinload(SequenceEnrollment.sequence),
                selectinload(SequenceEnrollment.collection_case),
            )
            .order_by(desc(SequenceEnrollment.enrolled_at))
        )
        if status_filter:
            q = q.where(SequenceEnrollment.status == status_filter)
        if sequence_id:
            q = q.where(SequenceEnrollment.sequence_id == sequence_id)

        count_q = select(func.count()).select_from(SequenceEnrollment)
        if status_filter:
            count_q = count_q.where(SequenceEnrollment.status == status_filter)
        if sequence_id:
            count_q = count_q.where(SequenceEnrollment.sequence_id == sequence_id)
        total = (await db.execute(count_q)).scalar() or 0

        q = q.offset(offset).limit(limit)
        result = await db.execute(q)
        enrollments = result.scalars().unique().all()

        return {
            "enrollments": [_enrollment_to_dict(e) for e in enrollments],
            "total": total,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="list_enrollments")
        raise


@router.post("/enrollments", status_code=201)
async def create_enrollment(
    body: EnrollmentCreate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        # Check case exists
        case_r = await db.execute(
            select(CollectionCase).where(CollectionCase.id == body.case_id)
        )
        if not case_r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Collection case not found")

        # Check sequence exists
        seq_r = await db.execute(
            select(CollectionSequence).where(CollectionSequence.id == body.sequence_id)
        )
        if not seq_r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Sequence not found")

        # Check no active enrollment for this case
        existing = await db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.case_id == body.case_id,
                SequenceEnrollment.status == "active",
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Case already has an active enrollment")

        enrollment = SequenceEnrollment(
            case_id=body.case_id,
            sequence_id=body.sequence_id,
            current_step_number=0,
            status="active",
        )
        db.add(enrollment)
        await db.flush()

        return {
            "id": enrollment.id,
            "case_id": enrollment.case_id,
            "sequence_id": enrollment.sequence_id,
            "status": enrollment.status,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="create_enrollment")
        raise


@router.post("/enrollments/auto-enroll")
async def auto_enroll(
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Batch auto-enroll unenrolled open cases into matching default sequences."""
    try:
        # Get default sequences per stage
        seq_result = await db.execute(
            select(CollectionSequence).where(
                CollectionSequence.is_active == True,
                CollectionSequence.is_default == True,
            )
        )
        default_seqs = {s.delinquency_stage: s for s in seq_result.scalars().all()}

        if not default_seqs:
            return {"enrolled": 0, "message": "No default sequences configured"}

        # Find open/in-progress cases without active enrollments
        already_enrolled_q = select(SequenceEnrollment.case_id).where(
            SequenceEnrollment.status == "active"
        )
        cases_result = await db.execute(
            select(CollectionCase).where(
                CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS]),
                CollectionCase.do_not_contact == False,
                ~CollectionCase.id.in_(already_enrolled_q),
            )
        )
        cases = cases_result.scalars().all()

        enrolled = 0
        for case in cases:
            stage = case.delinquency_stage
            stage_val = stage.value if hasattr(stage, 'value') else str(stage)
            seq = default_seqs.get(stage_val)
            if seq:
                db.add(SequenceEnrollment(
                    case_id=case.id,
                    sequence_id=seq.id,
                    current_step_number=0,
                    status="active",
                ))
                enrolled += 1

        await db.flush()
        return {"enrolled": enrolled, "message": f"{enrolled} cases auto-enrolled"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="auto_enroll")
        raise


@router.patch("/enrollments/{enrollment_id}")
async def update_enrollment(
    enrollment_id: int,
    body: EnrollmentUpdate,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(SequenceEnrollment).where(SequenceEnrollment.id == enrollment_id)
        )
        enrollment = result.scalar_one_or_none()
        if not enrollment:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        now = datetime.now(timezone.utc)
        if body.status:
            enrollment.status = body.status
            if body.status == "paused":
                enrollment.paused_reason = body.paused_reason or "Manual pause"
            elif body.status == "cancelled":
                enrollment.cancelled_at = now
            elif body.status == "completed":
                enrollment.completed_at = now
            elif body.status == "active":
                enrollment.paused_reason = None

        await db.flush()
        return {
            "id": enrollment.id,
            "status": enrollment.status,
            "paused_reason": enrollment.paused_reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="update_enrollment")
        raise


@router.get("/enrollments/{enrollment_id}/timeline")
async def enrollment_timeline(
    enrollment_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(StepExecution)
            .where(StepExecution.enrollment_id == enrollment_id)
            .order_by(StepExecution.executed_at)
        )
        executions = result.scalars().all()
        return [
            {
                "id": ex.id,
                "step_id": ex.step_id,
                "executed_at": ex.executed_at.isoformat() if ex.executed_at else None,
                "channel": ex.channel,
                "message_sent": ex.message_sent,
                "delivery_status": ex.delivery_status,
                "borrower_responded": ex.borrower_responded,
                "response_at": ex.response_at.isoformat() if ex.response_at else None,
                "payment_after": ex.payment_after,
                "notes": ex.notes,
            }
            for ex in executions
        ]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="enrollment_timeline")
        raise


# ══════════════════════════════════════════════════════════════
# AI ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.post("/ai/generate-sequence")
async def generate_sequence_endpoint(
    body: GenerateSequenceRequest,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await ai_generate_sequence(body.description, body.delinquency_stage, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="generate_sequence_endpoint")
        raise


@router.post("/ai/optimize-sequence")
async def optimize_sequence_endpoint(
    body: OptimizeRequest,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await ai_optimize_sequence(body.sequence_id, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="optimize_sequence_endpoint")
        raise


@router.post("/ai/generate-template")
async def generate_template_endpoint(
    body: GenerateTemplateRequest,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await ai_generate_template(body.channel, body.tone, body.category, body.context, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="generate_template_endpoint")
        raise


@router.post("/ai/preview-message")
async def preview_message(
    body: PreviewMessageRequest,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return {"rendered": render_template(body.body, body.context)}


# ══════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════

@router.get("/analytics")
async def get_analytics(
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await compute_sequence_analytics(None, db)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="get_analytics")
        raise


@router.get("/sequences/{sequence_id}/analytics")
async def get_sequence_analytics(
    sequence_id: int,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await compute_sequence_analytics(sequence_id, db)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.collection_sequences", function_name="get_sequence_analytics")
        raise
