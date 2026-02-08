"""Back-office underwriter endpoints."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus
from app.models.decision import Decision, UnderwriterAction
from app.models.audit import AuditLog
from app.schemas import (
    LoanApplicationResponse,
    DecisionResponse,
    UnderwriterDecision,
)
from app.auth_utils import get_current_user, require_roles

router = APIRouter()

UNDERWRITER_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


@router.get("/queue", response_model=list[LoanApplicationResponse])
async def get_queue(
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get the underwriter queue of applications."""
    query = select(LoanApplication).order_by(LoanApplication.submitted_at.asc())

    if status_filter:
        query = query.where(LoanApplication.status == LoanStatus(status_filter))
    else:
        # Default: show actionable statuses
        query = query.where(
            LoanApplication.status.in_([
                LoanStatus.SUBMITTED,
                LoanStatus.UNDER_REVIEW,
                LoanStatus.DECISION_PENDING,
                LoanStatus.CREDIT_CHECK,
            ])
        )

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/applications/{application_id}", response_model=LoanApplicationResponse)
async def get_application_detail(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.get("/applications/{application_id}/decision", response_model=DecisionResponse)
async def get_decision(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Decision)
        .where(Decision.loan_application_id == application_id)
        .order_by(Decision.created_at.desc())
    )
    decision = result.scalars().first()
    if not decision:
        raise HTTPException(status_code=404, detail="No decision found for this application")
    return decision


@router.post("/applications/{application_id}/assign")
async def assign_application(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Assign an application to the current underwriter."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.assigned_underwriter_id = current_user.id
    if application.status == LoanStatus.SUBMITTED:
        application.status = LoanStatus.UNDER_REVIEW

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="assigned",
        user_id=current_user.id,
        new_values={"assigned_underwriter_id": current_user.id},
    )
    db.add(audit)
    await db.flush()

    return {"message": "Application assigned", "status": application.status.value}


@router.post("/applications/{application_id}/decide", response_model=DecisionResponse)
async def make_decision(
    application_id: int,
    data: UnderwriterDecision,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Underwriter makes a decision on an application."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Get latest engine decision if exists
    dec_result = await db.execute(
        select(Decision)
        .where(Decision.loan_application_id == application_id)
        .order_by(Decision.created_at.desc())
    )
    decision = dec_result.scalars().first()

    action = UnderwriterAction(data.action)

    if decision:
        # Update existing decision with underwriter override
        decision.underwriter_id = current_user.id
        decision.underwriter_action = action
        decision.override_reason = data.reason
        decision.final_outcome = action.value
    else:
        # Create new decision (manual without engine)
        decision = Decision(
            loan_application_id=application_id,
            underwriter_id=current_user.id,
            underwriter_action=action,
            override_reason=data.reason,
            final_outcome=action.value,
        )
        db.add(decision)

    # Update application status
    now = datetime.now(timezone.utc)
    if action == UnderwriterAction.APPROVE:
        application.status = LoanStatus.APPROVED
        application.decided_at = now
        if data.approved_amount:
            application.amount_approved = data.approved_amount
        if data.approved_rate:
            application.interest_rate = data.approved_rate
    elif action == UnderwriterAction.DECLINE:
        application.status = LoanStatus.DECLINED
        application.decided_at = now
    elif action == UnderwriterAction.REQUEST_INFO:
        application.status = LoanStatus.AWAITING_DOCUMENTS

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action=f"underwriter_{action.value}",
        user_id=current_user.id,
        new_values={"action": action.value, "reason": data.reason},
    )
    db.add(audit)
    await db.flush()
    await db.refresh(decision)
    return decision
