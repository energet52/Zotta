"""Back-office underwriter endpoints."""

import io
import random
import string
from datetime import datetime, date, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from passlib.context import CryptContext

from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile
from app.models.decision import Decision, UnderwriterAction
from app.models.document import Document
from app.models.audit import AuditLog
from app.models.credit_report import CreditReport
from app.models.payment import PaymentSchedule
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
    LoanBookEntry,
    StaffCreateApplicationRequest,
)
from app.auth_utils import get_current_user, require_roles
from app.services.decision_engine.engine import run_decision_engine

import logging

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()

UNDERWRITER_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


@router.get("/queue", response_model=list[LoanApplicationResponse])
async def get_queue(
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get the underwriter queue of applications (newest first)."""
    query = (
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .order_by(LoanApplication.created_at.desc())
    )

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
    entries = []
    for row in result.all():
        app = row[0]
        # Build response dict from ORM model, then inject applicant_name
        resp = LoanApplicationResponse.model_validate(app)
        resp.applicant_name = f"{row[1]} {row[2]}"
        entries.append(resp)
    return entries


@router.post("/applications/{application_id}/run-engine", response_model=DecisionResponse)
async def run_engine(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Manually (re-)run the decision engine for an application."""
    decision = await run_decision_engine(application_id, db)
    await db.flush()
    await db.refresh(decision)
    return decision


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


# ── Loan Book ─────────────────────────────────────────

@router.get("/loans", response_model=list[LoanBookEntry])
async def get_loan_book(
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get disbursed loans with enriched data for the loan book."""
    query = (
        select(LoanApplication, User.first_name, User.last_name)
        .join(User, LoanApplication.applicant_id == User.id)
        .order_by(LoanApplication.created_at.desc())
    )
    # Loan Book only shows disbursed applications by default
    if status and status != "all":
        query = query.where(LoanApplication.status == LoanStatus(status))
    else:
        query = query.where(LoanApplication.status == LoanStatus.DISBURSED)

    result = await db.execute(query)
    entries = []
    today = date.today()

    for row in result.all():
        app = row[0]
        first_name = row[1]
        last_name = row[2]

        # Get latest decision for risk band / score
        dec_result = await db.execute(
            select(Decision)
            .where(Decision.loan_application_id == app.id)
            .order_by(Decision.created_at.desc())
            .limit(1)
        )
        decision = dec_result.scalar_one_or_none()

        # Calculate outstanding and DPD from schedule
        sched_result = await db.execute(
            select(PaymentSchedule)
            .where(PaymentSchedule.loan_application_id == app.id)
            .order_by(PaymentSchedule.installment_number)
        )
        schedules = sched_result.scalars().all()
        total_paid = sum(float(s.amount_paid) for s in schedules)
        outstanding = float(app.amount_approved or app.amount_requested) - total_paid if app.amount_approved else None
        days_past_due = 0
        next_payment = None
        for s in schedules:
            if s.status != "paid":
                if s.due_date <= today and float(s.amount_paid) < float(s.amount_due):
                    dpd = (today - s.due_date).days
                    if dpd > days_past_due:
                        days_past_due = dpd
                if next_payment is None and s.due_date >= today:
                    next_payment = s.due_date

        entries.append(LoanBookEntry(
            id=app.id,
            reference_number=app.reference_number,
            applicant_name=f"{first_name} {last_name}",
            amount_requested=float(app.amount_requested),
            amount_approved=float(app.amount_approved) if app.amount_approved else None,
            term_months=app.term_months,
            interest_rate=float(app.interest_rate) if app.interest_rate else None,
            monthly_payment=float(app.monthly_payment) if app.monthly_payment else None,
            status=app.status.value,
            risk_band=decision.risk_band if decision else None,
            credit_score=decision.credit_score if decision else None,
            disbursed_date=app.decided_at if app.status == LoanStatus.DISBURSED else None,
            outstanding_balance=max(outstanding, 0) if outstanding is not None else None,
            days_past_due=days_past_due,
            next_payment_date=next_payment,
            purpose=app.purpose.value,
            created_at=app.created_at,
        ))
    return entries


# ── Credit Bureau Report ──────────────────────────────

@router.get("/applications/{application_id}/credit-report")
async def get_credit_report(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get the full credit bureau report for an application."""
    result = await db.execute(
        select(CreditReport)
        .where(CreditReport.loan_application_id == application_id)
        .order_by(CreditReport.created_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No credit report found")
    return {
        "id": report.id,
        "provider": report.provider,
        "score": report.bureau_score,
        "report_data": report.report_data,
        "tradelines": report.tradelines,
        "inquiries": report.inquiries,
        "public_records": report.public_records,
        "status": report.status,
        "pulled_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/applications/{application_id}/credit-report/download")
async def download_credit_report(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Download credit report as CSV."""
    result = await db.execute(
        select(CreditReport)
        .where(CreditReport.loan_application_id == application_id)
        .order_by(CreditReport.created_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No credit report found")

    import csv
    output = io.StringIO()
    writer = csv.writer(output)

    data = report.report_data or {}

    writer.writerow(["AV Knowles Credit Bureau Report"])
    writer.writerow(["Report Date", data.get("report_date", "")])
    writer.writerow(["National ID (Last 4)", data.get("national_id_last4", "")])
    writer.writerow([])

    # Summary
    summary = data.get("summary", {})
    writer.writerow(["=== SUMMARY ==="])
    writer.writerow(["Credit Score", summary.get("score", data.get("score", ""))])
    writer.writerow(["Risk Level", summary.get("risk_level", data.get("risk_level", ""))])
    writer.writerow(["Total Debt", summary.get("total_debt", "")])
    writer.writerow(["Active Accounts", summary.get("active_accounts", "")])
    writer.writerow(["Payment History Rating", summary.get("payment_history_rating", "")])
    writer.writerow([])

    # Tradelines
    tradelines = data.get("tradelines", [])
    if tradelines:
        writer.writerow(["=== TRADELINES ==="])
        writer.writerow(["Lender", "Type", "Opened", "Original Amount", "Balance", "Monthly Payment", "Status", "DPD"])
        for t in tradelines:
            writer.writerow([
                t.get("lender"), t.get("type"), t.get("opened_date"),
                t.get("original_amount"), t.get("current_balance"),
                t.get("monthly_payment"), t.get("status"), t.get("days_past_due"),
            ])
        writer.writerow([])

    # Inquiries
    inquiries = data.get("inquiries", [])
    if inquiries:
        writer.writerow(["=== INQUIRIES ==="])
        writer.writerow(["Lender", "Date", "Purpose", "Type"])
        for inq in inquiries:
            writer.writerow([inq.get("lender"), inq.get("date"), inq.get("purpose"), inq.get("type", "")])
        writer.writerow([])

    # Public records
    records = data.get("public_records", [])
    if records:
        writer.writerow(["=== PUBLIC RECORDS ==="])
        writer.writerow(["Type", "Date", "Amount", "Status"])
        for r in records:
            writer.writerow([r.get("type"), r.get("date"), r.get("amount"), r.get("status")])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=credit_report_{application_id}.csv"},
    )


# ── Staff Create Application ─────────────────────────

def _generate_reference() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=8))
    year = datetime.now().year
    return f"ZOT-{year}-{suffix}"


@router.post("/applications/create-on-behalf", response_model=LoanApplicationResponse)
async def create_on_behalf(
    data: StaffCreateApplicationRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Staff creates an application on behalf of a walk-in customer."""
    # Check if user with email already exists
    existing = await db.execute(
        select(User).where(User.email == data.email)
    )
    user = existing.scalar_one_or_none()

    if not user:
        # Create user with a random password
        temp_password = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        user = User(
            email=data.email,
            hashed_password=pwd_context.hash(temp_password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            role=UserRole.APPLICANT,
        )
        db.add(user)
        await db.flush()

    # Create or update profile
    profile_result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        profile = ApplicantProfile(user_id=user.id)
        db.add(profile)

    for field_name in [
        "date_of_birth", "national_id", "gender", "address_line1",
        "city", "parish", "employer_name", "job_title", "employment_type",
        "years_employed", "monthly_income", "monthly_expenses", "existing_debt",
    ]:
        val = getattr(data, field_name, None)
        if val is not None:
            setattr(profile, field_name, val)

    await db.flush()

    # Create application (submitted immediately)
    application = LoanApplication(
        reference_number=_generate_reference(),
        applicant_id=user.id,
        amount_requested=data.amount_requested,
        term_months=data.term_months,
        purpose=LoanPurpose(data.purpose),
        purpose_description=data.purpose_description,
        status=LoanStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(application)

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=0,  # Will update after flush
        action="staff_created",
        user_id=current_user.id,
        new_values={
            "applicant_email": data.email,
            "amount": float(data.amount_requested),
            "created_by": f"{current_user.first_name} {current_user.last_name}",
        },
    )
    db.add(audit)
    await db.flush()

    # Update audit with actual application ID
    audit.entity_id = application.id
    await db.flush()

    # Run the decision engine automatically
    try:
        await run_decision_engine(application.id, db)
        await db.flush()
    except Exception as exc:
        logger.warning("Decision engine failed for staff-created application %s: %s", application.id, exc)

    await db.refresh(application)
    return application
