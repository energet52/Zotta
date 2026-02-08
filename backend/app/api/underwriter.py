"""Back-office underwriter endpoints."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile
from app.models.decision import Decision, UnderwriterAction
from app.models.document import Document
from app.models.audit import AuditLog
from app.schemas import (
    LoanApplicationResponse,
    DecisionResponse,
    UnderwriterDecision,
    FullApplicationResponse,
    ApplicantProfileResponse,
    DocumentResponse,
    AuditLogResponse,
    ContractResponse,
    ApplicationEditRequest,
    CounterproposalRequest,
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

    if status_filter and status_filter != "all":
        query = query.where(LoanApplication.status == LoanStatus(status_filter))
    elif status_filter != "all":
        # Default: show actionable statuses
        query = query.where(
            LoanApplication.status.in_([
                LoanStatus.SUBMITTED,
                LoanStatus.UNDER_REVIEW,
                LoanStatus.DECISION_PENDING,
                LoanStatus.CREDIT_CHECK,
            ])
        )
    # else "all" — no filter, show everything

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


@router.get("/applications/{application_id}/full", response_model=FullApplicationResponse)
async def get_full_application(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get full application details including profile, documents, decisions, and audit log."""
    # Application
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Profile
    profile_result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == application.applicant_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Documents
    docs_result = await db.execute(
        select(Document).where(Document.loan_application_id == application_id)
        .order_by(Document.created_at.desc())
    )
    documents = docs_result.scalars().all()

    # All decisions (not just latest)
    decisions_result = await db.execute(
        select(Decision).where(Decision.loan_application_id == application_id)
        .order_by(Decision.created_at.desc())
    )
    decisions = decisions_result.scalars().all()

    # Audit log with user names
    audit_result = await db.execute(
        select(AuditLog, User.first_name, User.last_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(
            AuditLog.entity_type == "loan_application",
            AuditLog.entity_id == application_id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    audit_entries = []
    for row in audit_result.all():
        audit_log = row[0]
        first_name = row[1] or ""
        last_name = row[2] or ""
        entry = AuditLogResponse(
            id=audit_log.id,
            entity_type=audit_log.entity_type,
            entity_id=audit_log.entity_id,
            action=audit_log.action,
            user_id=audit_log.user_id,
            user_name=f"{first_name} {last_name}".strip() or None,
            old_values=audit_log.old_values,
            new_values=audit_log.new_values,
            details=audit_log.details,
            created_at=audit_log.created_at,
        )
        audit_entries.append(entry)

    # Contract
    contract = None
    if application.contract_signed_at:
        contract = ContractResponse(
            signature_data=application.contract_signature_data,
            typed_name=application.contract_typed_name,
            signed_at=application.contract_signed_at,
        )

    return FullApplicationResponse(
        application=application,
        profile=profile,
        documents=documents,
        decisions=decisions,
        audit_log=audit_entries,
        contract=contract,
    )


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


@router.get("/applications/{application_id}/audit", response_model=list[AuditLogResponse])
async def get_audit_log(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get audit history for a specific application."""
    audit_result = await db.execute(
        select(AuditLog, User.first_name, User.last_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(
            AuditLog.entity_type == "loan_application",
            AuditLog.entity_id == application_id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    entries = []
    for row in audit_result.all():
        audit_log = row[0]
        first_name = row[1] or ""
        last_name = row[2] or ""
        entries.append(AuditLogResponse(
            id=audit_log.id,
            entity_type=audit_log.entity_type,
            entity_id=audit_log.entity_id,
            action=audit_log.action,
            user_id=audit_log.user_id,
            user_name=f"{first_name} {last_name}".strip() or None,
            old_values=audit_log.old_values,
            new_values=audit_log.new_values,
            details=audit_log.details,
            created_at=audit_log.created_at,
        ))
    return entries


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


@router.patch("/applications/{application_id}/edit")
async def edit_application(
    application_id: int,
    data: ApplicationEditRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Edit application/profile fields. Creates audit log with old/new values."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Load profile
    profile_result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == application.applicant_id)
    )
    profile = profile_result.scalar_one_or_none()

    old_values = {}
    new_values = {}

    # Application fields
    app_fields = {"term_months", "purpose", "purpose_description"}
    for field_name in app_fields:
        new_val = getattr(data, field_name, None)
        if new_val is not None:
            old_val = getattr(application, field_name)
            if field_name == "purpose":
                old_val = old_val.value if old_val else None
                new_val_enum = LoanPurpose(new_val)
                old_values[field_name] = old_val
                new_values[field_name] = new_val
                application.purpose = new_val_enum
            else:
                old_values[field_name] = old_val
                new_values[field_name] = new_val
                setattr(application, field_name, new_val)

    # Profile fields
    if profile:
        profile_fields = {
            "monthly_income", "monthly_expenses", "existing_debt",
            "employer_name", "job_title", "employment_type", "years_employed",
        }
        for field_name in profile_fields:
            new_val = getattr(data, field_name, None)
            if new_val is not None:
                old_val = getattr(profile, field_name)
                if old_val is not None:
                    old_val = float(old_val) if isinstance(old_val, (int, float)) else str(old_val)
                old_values[field_name] = old_val
                new_values[field_name] = new_val
                setattr(profile, field_name, new_val)

    if not new_values:
        return {"message": "No changes provided"}

    # Audit log
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="underwriter_edit",
        user_id=current_user.id,
        old_values=old_values,
        new_values=new_values,
        details=f"Edited by {current_user.first_name} {current_user.last_name}",
    )
    db.add(audit)
    await db.flush()

    return {"message": "Application updated", "changes": new_values}


@router.post("/applications/{application_id}/counterpropose", response_model=LoanApplicationResponse)
async def counterpropose(
    application_id: int,
    data: CounterproposalRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Underwriter counterpropose different loan terms."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = application.status.value

    application.proposed_amount = data.proposed_amount
    application.proposed_rate = data.proposed_rate
    application.proposed_term = data.proposed_term
    application.counterproposal_reason = data.reason
    application.status = LoanStatus.COUNTER_PROPOSED
    application.assigned_underwriter_id = current_user.id

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="counterproposal",
        user_id=current_user.id,
        old_values={"status": old_status},
        new_values={
            "status": "counter_proposed",
            "proposed_amount": float(data.proposed_amount),
            "proposed_rate": float(data.proposed_rate),
            "proposed_term": data.proposed_term,
            "reason": data.reason,
        },
    )
    db.add(audit)
    await db.flush()
    await db.refresh(application)
    return application


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
