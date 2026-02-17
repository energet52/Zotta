"""Back-office underwriter endpoints."""

import io
import random
import string
from datetime import datetime, date, timezone, timedelta
from typing import Optional

import os

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from passlib.context import CryptContext

import asyncio
from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile, ApplicationItem
from app.models.decision import Decision, UnderwriterAction
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.audit import AuditLog
from app.models.note import ApplicationNote
from app.models.credit_report import CreditReport
from app.models.bank_analysis import BankStatementAnalysis, AnalysisStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentSchedule, ScheduleStatus
from app.models.disbursement import Disbursement, DisbursementMethod, DisbursementStatus
from app.schemas import (
    LoanApplicationResponse,
    ApplicationItemResponse,
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
    DisbursementRequest,
    DisbursementResponse,
    ParsedIdResponse,
    BankAnalysisResponse,
)
from app.auth_utils import get_current_user, require_roles
from app.config import settings
from app.services.decision_engine.engine import run_decision_engine
from app.services.id_parser import parse_id_images

import logging
from app.services.error_logger import log_error

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()

UNDERWRITER_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


@router.get("/staff")
async def get_staff(
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List all staff users (underwriters and admins)."""
    q = select(User).where(
        User.role.in_([UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN])
    ).order_by(User.first_name)
    result = await db.execute(q)
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "role": u.role.value,
        }
        for u in users
    ]


@router.get("/queue", response_model=list[LoanApplicationResponse])
async def get_queue(
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get the underwriter queue of applications (newest first)."""
    try:
        from sqlalchemy.orm import aliased
        Applicant = aliased(User)
        Assignee = aliased(User)

        query = (
            select(
                LoanApplication,
                Applicant.first_name.label("app_first"),
                Applicant.last_name.label("app_last"),
                Assignee.first_name.label("asgn_first"),
                Assignee.last_name.label("asgn_last"),
            )
            .join(Applicant, LoanApplication.applicant_id == Applicant.id)
            .outerjoin(Assignee, LoanApplication.assigned_underwriter_id == Assignee.id)
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
        for app, app_first, app_last, asgn_first, asgn_last in result.all():
            resp = LoanApplicationResponse.model_validate(app)
            resp.applicant_name = f"{app_first} {app_last}"
            if asgn_first:
                resp.assigned_underwriter_name = f"{asgn_first} {asgn_last}"
            entries.append(resp)
        return entries
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_queue")
        raise


@router.post("/applications/{application_id}/run-engine", response_model=DecisionResponse)
async def run_engine(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Manually (re-)run the decision engine for an application."""
    try:
        decision = await run_decision_engine(application_id, db)
        await db.flush()
        await db.refresh(decision)
        return decision
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="run_engine")
        raise


@router.get("/applications/{application_id}", response_model=LoanApplicationResponse)
async def get_application_detail(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        return application
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_application_detail")
        raise


@router.get("/applications/{application_id}/full", response_model=FullApplicationResponse)
async def get_full_application(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get full application details including profile, documents, decisions, and audit log."""
    try:
        # Application with Shopping + Plan Selection relations (merchant, branch, credit_product, items)
        result = await db.execute(
            select(LoanApplication)
            .where(LoanApplication.id == application_id)
            .options(
                selectinload(LoanApplication.merchant),
                selectinload(LoanApplication.branch),
                selectinload(LoanApplication.credit_product),
                selectinload(LoanApplication.items).selectinload(ApplicationItem.category),
            )
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

        # Build application response with Shopping + Plan Selection data
        app_items = [
            ApplicationItemResponse(
                id=it.id,
                loan_application_id=it.loan_application_id,
                category_id=it.category_id,
                category_name=it.category.name if it.category else None,
                description=it.description,
                price=float(it.price),
                quantity=it.quantity,
                created_at=it.created_at,
            )
            for it in (application.items or [])
        ]
        app_response = LoanApplicationResponse(
            id=application.id,
            reference_number=application.reference_number,
            applicant_id=application.applicant_id,
            applicant_name=None,
            amount_requested=float(application.amount_requested),
            term_months=application.term_months,
            purpose=application.purpose.value if hasattr(application.purpose, "value") else str(application.purpose),
            purpose_description=application.purpose_description,
            interest_rate=float(application.interest_rate) if application.interest_rate else None,
            amount_approved=float(application.amount_approved) if application.amount_approved else None,
            monthly_payment=float(application.monthly_payment) if application.monthly_payment else None,
            merchant_id=application.merchant_id,
            branch_id=application.branch_id,
            credit_product_id=application.credit_product_id,
            merchant_name=application.merchant.name if application.merchant else None,
            branch_name=application.branch.name if application.branch else None,
            credit_product_name=application.credit_product.name if application.credit_product else None,
            credit_product_rate=float(application.credit_product.interest_rate) if application.credit_product and application.credit_product.interest_rate else None,
            downpayment=float(application.downpayment) if application.downpayment else None,
            total_financed=float(application.total_financed) if application.total_financed else None,
            items=app_items,
            status=application.status.value if hasattr(application.status, "value") else str(application.status),
            assigned_underwriter_id=application.assigned_underwriter_id,
            proposed_amount=float(application.proposed_amount) if application.proposed_amount else None,
            proposed_rate=float(application.proposed_rate) if application.proposed_rate else None,
            proposed_term=application.proposed_term,
            counterproposal_reason=application.counterproposal_reason,
            contract_signed_at=application.contract_signed_at,
            contract_typed_name=application.contract_typed_name,
            submitted_at=application.submitted_at,
            decided_at=application.decided_at,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )

        return FullApplicationResponse(
            application=app_response,
            profile=profile,
            documents=documents,
            decisions=decisions,
            audit_log=audit_entries,
            contract=contract,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_full_application")
        raise


@router.post("/applications/{application_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    application_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document to an application (back-office staff). Accepts any document type including 'other'."""
    try:
        result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        try:
            doc_type = DocumentType(document_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid document type '{document_type}'. "
                       f"Allowed: {', '.join(t.value for t in DocumentType)}",
            )

        content = await file.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large")

        # Sanitize filename and validate extension to prevent path traversal
        import uuid as _uuid
        original_name = os.path.basename(file.filename or "upload")
        ext = os.path.splitext(original_name)[1].lower()
        _ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".csv", ".docx", ".xlsx"}
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
            )
        safe_name = f"{_uuid.uuid4().hex}{ext}"
        upload_dir = os.path.join(settings.upload_dir, str(application_id))
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_name)
        with open(file_path, "wb") as f:
            f.write(content)

        doc = Document(
            loan_application_id=application_id,
            uploaded_by=current_user.id,
            document_type=doc_type,
            file_name=original_name,
            file_path=file_path,
            file_size=len(content),
            mime_type=file.content_type or "application/octet-stream",
            status=DocumentStatus.UPLOADED,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)

        audit = AuditLog(
            entity_type="loan_application",
            entity_id=application_id,
            action="document_uploaded",
            user_id=current_user.id,
            new_values={
                "document_id": doc.id,
                "document_type": doc_type.value,
                "file_name": file.filename,
            },
        )
        db.add(audit)
        await db.flush()
        return doc
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="upload_document")
        raise


@router.get("/applications/{application_id}/documents/{document_id}/download")
async def download_document(
    application_id: int,
    document_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(LoanApplication, Document).join(
                Document, Document.loan_application_id == LoanApplication.id
            ).where(
                LoanApplication.id == application_id,
                Document.id == document_id,
            )
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        _, doc = row
        if not os.path.isfile(doc.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(doc.file_path, filename=doc.file_name, media_type=doc.mime_type or "application/octet-stream")
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="download_document")
        raise


@router.delete("/applications/{application_id}/documents/{document_id}")
async def delete_document(
    application_id: int,
    document_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(LoanApplication, Document).join(
                Document, Document.loan_application_id == LoanApplication.id
            ).where(
                LoanApplication.id == application_id,
                Document.id == document_id,
            )
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        _, doc = row
        if os.path.isfile(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError:
                pass
        await db.delete(doc)
        await db.flush()
        audit = AuditLog(
            entity_type="loan_application",
            entity_id=application_id,
            action="document_deleted",
            user_id=current_user.id,
            new_values={"document_id": document_id, "file_name": doc.file_name},
        )
        db.add(audit)
        await db.flush()
        return {"message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="delete_document")
        raise


@router.get("/applications/{application_id}/decision", response_model=DecisionResponse)
async def get_decision(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Decision)
            .where(Decision.loan_application_id == application_id)
            .order_by(Decision.created_at.desc())
        )
        decision = result.scalars().first()
        if not decision:
            raise HTTPException(status_code=404, detail="No decision found for this application")
        return decision
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_decision")
        raise


@router.get("/applications/{application_id}/audit", response_model=list[AuditLogResponse])
async def get_audit_log(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get audit history for a specific application."""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_audit_log")
        raise


@router.post("/applications/{application_id}/assign")
async def assign_application(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Assign an application to the current underwriter."""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="assign_application")
        raise


@router.patch("/applications/{application_id}/edit")
async def edit_application(
    application_id: int,
    data: ApplicationEditRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Edit application/profile fields. Creates audit log with old/new values."""
    try:
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
                "employer_name", "employer_sector", "job_title", "employment_type", "years_employed",
                "whatsapp_number", "contact_email", "mobile_phone", "home_phone", "employer_phone",
            }
            for field_name in profile_fields:
                new_val = getattr(data, field_name, None)
                if new_val is not None:
                    old_val = getattr(profile, field_name, None)
                    if old_val is not None:
                        old_val = float(old_val) if isinstance(old_val, (int, float)) else str(old_val)
                    old_values[field_name] = old_val
                    new_values[field_name] = new_val
                    setattr(profile, field_name, new_val)

        if not new_values:
            return {"message": "No changes provided"}

        # Keep User.phone in sync with profile contact numbers
        if profile:
            phone_fields_changed = {"whatsapp_number", "mobile_phone", "home_phone"} & set(new_values.keys())
            if phone_fields_changed:
                user_result = await db.execute(
                    select(User).where(User.id == application.applicant_id)
                )
                app_user = user_result.scalar_one_or_none()
                if app_user:
                    best = profile.whatsapp_number or profile.mobile_phone or profile.home_phone
                    if best and best != app_user.phone:
                        app_user.phone = best

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
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="edit_application")
        raise


@router.post("/applications/{application_id}/counterpropose", response_model=LoanApplicationResponse)
async def counterpropose(
    application_id: int,
    data: CounterproposalRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Underwriter counterpropose different loan terms."""
    try:
        result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # ── Prevent counterproposal after approval or disbursement ──
        _LOCKED = (
            LoanStatus.APPROVED,
            LoanStatus.ACCEPTED,
            LoanStatus.OFFER_SENT,
            LoanStatus.DISBURSED,
        )
        if application.status in _LOCKED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot counterpropose — loan is already '{application.status.value}'. "
                       f"Changes are not allowed once approved or disbursed.",
            )

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
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="counterpropose")
        raise


@router.post("/applications/{application_id}/decide", response_model=DecisionResponse)
async def make_decision(
    application_id: int,
    data: UnderwriterDecision,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Underwriter makes a decision on an application."""
    try:
        result = await db.execute(
            select(LoanApplication)
            .where(LoanApplication.id == application_id)
            .options(selectinload(LoanApplication.credit_product))
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # ── Prevent changing decision after approval or disbursement ──
        LOCKED_STATUSES = (
            LoanStatus.APPROVED,
            LoanStatus.ACCEPTED,
            LoanStatus.OFFER_SENT,
            LoanStatus.DISBURSED,
        )
        if application.status in LOCKED_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot change decision — loan is already '{application.status.value}'. "
                       f"Decisions are final once approved or disbursed.",
            )

        # Get latest engine decision if exists
        dec_result = await db.execute(
            select(Decision)
            .where(Decision.loan_application_id == application_id)
            .order_by(Decision.created_at.desc())
        )
        decision = dec_result.scalars().first()

        action = UnderwriterAction(data.action)

        # ── Sector concentration enforcement (FR-5) ──
        if action == UnderwriterAction.APPROVE:
            from app.services.sector_analysis import check_sector_origination
            profile_q = await db.execute(
                select(ApplicantProfile).where(ApplicantProfile.user_id == application.applicant_id)
            )
            profile = profile_q.scalar_one_or_none()
            sector = profile.employer_sector if profile else "MISSING"
            if not sector:
                sector = "MISSING"
            conc_check = await check_sector_origination(
                db, sector, float(application.amount_requested)
            )
            if not conc_check["allowed"]:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Sector concentration policy blocks this approval",
                        "reasons": conc_check["reasons"],
                        "sector": sector,
                    },
                )

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
            # Use decision engine values only; underwriter cannot override
            requested = float(application.amount_requested)
            cap = float(decision.suggested_amount) if decision and decision.suggested_amount is not None else requested
            application.amount_approved = min(requested, cap)
            # Rate priority: credit product > decision engine > default
            cp = application.credit_product
            if cp and cp.interest_rate is not None:
                application.interest_rate = float(cp.interest_rate)
            elif decision and decision.suggested_rate is not None:
                application.interest_rate = float(decision.suggested_rate)
            elif application.interest_rate is None:
                application.interest_rate = 12.0  # Default fallback
            # Calculate monthly payment if not already set
            if not application.monthly_payment and application.interest_rate and application.term_months:
                r = float(application.interest_rate) / 100 / 12
                n = application.term_months
                principal = float(application.amount_approved or application.amount_requested)
                if r > 0:
                    pmt = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
                else:
                    pmt = principal / n
                application.monthly_payment = round(pmt, 2)
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

        # ── Send WhatsApp notification for status change ──
        try:
            from app.services.whatsapp_notifier import (
                notify_application_approved,
                notify_application_declined,
                notify_documents_requested,
            )

            # Look up applicant for phone + name
            applicant_result = await db.execute(
                select(User).where(User.id == application.applicant_id)
            )
            applicant = applicant_result.scalar_one_or_none()
            if applicant and applicant.phone:
                first = applicant.first_name or "Customer"
                ref = application.reference_number or f"#{application.id}"

                if action == UnderwriterAction.APPROVE:
                    asyncio.ensure_future(notify_application_approved(
                        to_phone=applicant.phone,
                        first_name=first,
                        reference=ref,
                        amount_approved=float(application.amount_approved or application.amount_requested),
                        monthly_payment=float(application.monthly_payment) if application.monthly_payment else None,
                    ))
                elif action == UnderwriterAction.DECLINE:
                    asyncio.ensure_future(notify_application_declined(
                        to_phone=applicant.phone,
                        first_name=first,
                        reference=ref,
                    ))
                elif action == UnderwriterAction.REQUEST_INFO:
                    asyncio.ensure_future(notify_documents_requested(
                        to_phone=applicant.phone,
                        first_name=first,
                        reference=ref,
                    ))
        except Exception:
            logger.exception("Non-blocking WhatsApp send failed on status change")

        return decision
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="make_decision")
        raise


# ── Disbursement ──────────────────────────────────────

DISBURSABLE_STATUSES = (
    LoanStatus.APPROVED,
    LoanStatus.ACCEPTED,
    LoanStatus.OFFER_SENT,
)


def _generate_disbursement_ref() -> str:
    """Generate a unique disbursement reference like DIS-AB1234."""
    chars = string.ascii_uppercase + string.digits
    return "DIS-" + "".join(random.choices(chars, k=6))


def _generate_payment_schedule(
    writer_fn,
    loan_application_id: int,
    principal: float,
    annual_rate: float,
    term_months: int,
    start_date: date,
) -> list[PaymentSchedule]:
    """Amortisation schedule generation (principal + interest).

    Returns a list of PaymentSchedule ORM objects (not yet added to session).
    ``writer_fn`` is ignored — kept for signature compat.
    """
    monthly_rate = annual_rate / 100 / 12
    if monthly_rate > 0:
        pmt = principal * (monthly_rate * (1 + monthly_rate) ** term_months) / (
            (1 + monthly_rate) ** term_months - 1
        )
    else:
        pmt = principal / term_months

    balance = principal
    schedules = []
    for i in range(1, term_months + 1):
        interest = round(balance * monthly_rate, 2)
        principal_part = round(pmt - interest, 2)
        if i == term_months:
            principal_part = round(balance, 2)
        balance = max(0, round(balance - principal_part, 2))
        due = start_date + timedelta(days=30 * i)
        amount_due = round(principal_part + interest, 2)

        schedules.append(
            PaymentSchedule(
                loan_application_id=loan_application_id,
                installment_number=i,
                due_date=due,
                principal=principal_part,
                interest=interest,
                amount_due=amount_due,
                amount_paid=0,
                status=ScheduleStatus.UPCOMING,
            )
        )
    return schedules


@router.post("/applications/{application_id}/disburse", response_model=DisbursementResponse)
async def disburse_loan(
    application_id: int,
    data: DisbursementRequest,
    current_user: User = Depends(require_roles(UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Disburse a loan — release funds and generate payment schedule.

    Status transitions: APPROVED/ACCEPTED/OFFER_SENT → DISBURSED

    Creates:
    * A ``Disbursement`` record with method, amount, reference, bank details.
    * A full amortisation ``PaymentSchedule`` for the loan.
    * An ``AuditLog`` entry.

    The endpoint is designed so that a payment-provider adapter can be
    plugged in later (check ``data.method`` → call provider → store
    ``provider_reference`` / ``provider_response``).
    """
    try:
        # ── 1. Load and validate application ──────────────
        result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        if application.status not in DISBURSABLE_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot disburse — current status is '{application.status.value}'. "
                       f"Loan must be approved or accepted first.",
            )

        if not application.amount_approved:
            raise HTTPException(
                status_code=400,
                detail="Cannot disburse — no approved amount on this application.",
            )

        # Prevent double-disbursement
        existing = await db.execute(
            select(Disbursement).where(
                Disbursement.loan_application_id == application_id,
                Disbursement.status.in_(["completed", "processing"]),
            )
        )
        if existing.scalars().first():
            raise HTTPException(status_code=409, detail="This loan has already been disbursed.")

        # ── 2. Validate method ────────────────────────────
        try:
            method = DisbursementMethod(data.method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid disbursement method '{data.method}'. "
                       f"Allowed: {', '.join(m.value for m in DisbursementMethod)}",
            )

        # ── 3. Future: call payment provider here ─────────
        # if method == DisbursementMethod.BANK_TRANSFER:
        #     provider_result = await payment_gateway.initiate_transfer(...)
        #     provider_ref = provider_result.reference
        #     provider_resp = provider_result.raw
        # For now, manual disbursements are completed immediately.

        now = datetime.now(timezone.utc)
        amount = float(application.amount_approved)

        # ── 4. Create disbursement record ─────────────────
        disbursement = Disbursement(
            loan_application_id=application_id,
            amount=amount,
            method=method,
            status=DisbursementStatus.COMPLETED,
            reference_number=_generate_disbursement_ref(),
            disbursed_by=current_user.id,
            notes=data.notes,
            recipient_account_name=data.recipient_account_name,
            recipient_account_number=data.recipient_account_number,
            recipient_bank=data.recipient_bank,
            recipient_bank_branch=data.recipient_bank_branch,
            disbursed_at=now,
        )
        db.add(disbursement)

        # ── 5. Record disbursement as a transaction ────────
        disbursement_payment = Payment(
            loan_application_id=application_id,
            amount=amount,
            payment_type=PaymentType.DISBURSEMENT,
            payment_date=now.date(),
            reference_number=disbursement.reference_number,
            recorded_by=current_user.id,
            status=PaymentStatus.COMPLETED,
            notes=f"Loan disbursement — {method.value.replace('_', ' ')}",
        )
        db.add(disbursement_payment)

        # ── 6. Update loan status ─────────────────────────
        application.status = LoanStatus.DISBURSED
        application.disbursed_at = now

        # ── 7. Generate payment schedule ──────────────────
        schedules = _generate_payment_schedule(
            writer_fn=None,
            loan_application_id=application_id,
            principal=amount,
            annual_rate=float(application.interest_rate or 0),
            term_months=application.term_months,
            start_date=now.date(),
        )
        for s in schedules:
            db.add(s)

        # Update monthly payment on the application if not set
        if schedules and not application.monthly_payment:
            application.monthly_payment = schedules[0].amount_due

        # ── 8. Audit log ──────────────────────────────────
        audit = AuditLog(
            entity_type="loan_application",
            entity_id=application_id,
            action="disbursed",
            user_id=current_user.id,
            new_values={
                "disbursement_id": None,  # filled after flush
                "amount": amount,
                "method": method.value,
                "reference": disbursement.reference_number,
            },
        )
        db.add(audit)

        await db.flush()
        await db.refresh(disbursement)

        # Fix audit with disbursement id
        audit.new_values = {**audit.new_values, "disbursement_id": disbursement.id}

        # ── 9. Post to General Ledger ────────────────────
        try:
            from app.services.gl.mapping_engine import generate_journal_entry, MappingError
            from app.models.gl import JournalSourceType
            from decimal import Decimal as _Decimal

            await generate_journal_entry(
                db,
                event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_reference=f"LOAN-{application_id}",
                amount_breakdown={
                    "principal": _Decimal(str(amount)),
                    "full_amount": _Decimal(str(amount)),
                },
                product_id=getattr(application, "credit_product_id", None),
                description=f"Disbursement for loan #{application_id}",
                created_by=current_user.id,
                loan_reference=f"LOAN-{application_id}",
                auto_post=True,
            )
        except Exception:
            # GL posting is non-blocking — log but don't fail disbursement
            logger.warning("GL posting for disbursement of loan %d failed (no mapping template?)", application_id, exc_info=True)

        # ── 10. Send WhatsApp disbursement notification ────
        try:
            from app.services.whatsapp_notifier import notify_loan_disbursed

            applicant_result = await db.execute(
                select(User).where(User.id == application.applicant_id)
            )
            applicant = applicant_result.scalar_one_or_none()
            if applicant and applicant.phone:
                asyncio.ensure_future(notify_loan_disbursed(
                    to_phone=applicant.phone,
                    first_name=applicant.first_name or "Customer",
                    reference=application.reference_number or f"#{application.id}",
                    amount=amount,
                    disbursement_ref=disbursement.reference_number,
                ))
        except Exception:
            logger.exception("Non-blocking WhatsApp send failed on disbursement")

        # ── 11. Build response ────────────────────────────
        return DisbursementResponse(
            id=disbursement.id,
            loan_application_id=disbursement.loan_application_id,
            amount=float(disbursement.amount),
            method=disbursement.method.value,
            status=disbursement.status.value,
            reference_number=disbursement.reference_number,
            provider=disbursement.provider,
            provider_reference=disbursement.provider_reference,
            recipient_account_name=disbursement.recipient_account_name,
            recipient_account_number=disbursement.recipient_account_number,
            recipient_bank=disbursement.recipient_bank,
            recipient_bank_branch=disbursement.recipient_bank_branch,
            disbursed_by=disbursement.disbursed_by,
            disbursed_by_name=f"{current_user.first_name} {current_user.last_name}",
            notes=disbursement.notes,
            disbursed_at=disbursement.disbursed_at,
            created_at=disbursement.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="disburse_loan")
        raise


# ── Void Application ──────────────────────────────────────────────

# All statuses except DISBURSED can be voided by an underwriter
_VOIDABLE_STATUSES = [
    LoanStatus.DRAFT,
    LoanStatus.SUBMITTED,
    LoanStatus.UNDER_REVIEW,
    LoanStatus.AWAITING_DOCUMENTS,
    LoanStatus.CREDIT_CHECK,
    LoanStatus.DECISION_PENDING,
    LoanStatus.APPROVED,
    LoanStatus.DECLINED,
    LoanStatus.OFFER_SENT,
    LoanStatus.ACCEPTED,
    LoanStatus.COUNTER_PROPOSED,
]


@router.post("/applications/{application_id}/void")
async def void_application(
    application_id: int,
    data: dict | None = None,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Void an application — permanently close it with a reason.

    Underwriters can void any application that has not been disbursed.
    A reason is required.
    """
    try:
        result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        if application.status == LoanStatus.DISBURSED:
            raise HTTPException(
                status_code=400,
                detail="Cannot void a disbursed application. The loan has already been released.",
            )
        if application.status in (LoanStatus.CANCELLED, LoanStatus.VOIDED):
            raise HTTPException(
                status_code=400,
                detail=f"Application is already {application.status.value}.",
            )

        body = data or {}
        reason = body.get("reason", "").strip()
        if not reason:
            raise HTTPException(
                status_code=400,
                detail="A reason is required when voiding an application.",
            )

        old_status = application.status.value
        now = datetime.now(timezone.utc)

        application.status = LoanStatus.VOIDED
        application.cancellation_reason = reason
        application.cancelled_at = now
        application.cancelled_by = current_user.id

        db.add(AuditLog(
            entity_type="loan_application",
            entity_id=application_id,
            action="voided",
            user_id=current_user.id,
            old_values={"status": old_status},
            new_values={"status": "voided", "reason": reason},
            details=f"Application {application.reference_number} voided by "
                    f"{current_user.first_name} {current_user.last_name}: {reason}",
        ))

        await db.flush()
        await db.refresh(application)

        return {
            "status": "ok",
            "message": f"Application {application.reference_number} has been voided",
            "previous_status": old_status,
            "reason": reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="void_application")
        raise


@router.get("/applications/{application_id}/disbursement", response_model=DisbursementResponse)
async def get_disbursement(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get the disbursement record for an application (if disbursed)."""
    try:
        result = await db.execute(
            select(Disbursement, User.first_name, User.last_name)
            .join(User, Disbursement.disbursed_by == User.id)
            .where(Disbursement.loan_application_id == application_id)
            .order_by(Disbursement.created_at.desc())
            .limit(1)
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="No disbursement found for this application")

        d, first, last = row
        return DisbursementResponse(
            id=d.id,
            loan_application_id=d.loan_application_id,
            amount=float(d.amount),
            method=d.method.value,
            status=d.status.value,
            reference_number=d.reference_number,
            provider=d.provider,
            provider_reference=d.provider_reference,
            recipient_account_name=d.recipient_account_name,
            recipient_account_number=d.recipient_account_number,
            recipient_bank=d.recipient_bank,
            recipient_bank_branch=d.recipient_bank_branch,
            disbursed_by=d.disbursed_by,
            disbursed_by_name=f"{first} {last}",
            notes=d.notes,
            disbursed_at=d.disbursed_at,
            created_at=d.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_disbursement")
        raise


# ── Loan Book ─────────────────────────────────────────

@router.get("/loans", response_model=list[LoanBookEntry])
async def get_loan_book(
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get disbursed loans with enriched data for the loan book."""
    try:
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
                applicant_id=app.applicant_id,
                applicant_name=f"{first_name} {last_name}",
                amount_requested=float(app.amount_requested),
                amount_approved=float(app.amount_approved) if app.amount_approved else None,
                term_months=app.term_months,
                interest_rate=float(app.interest_rate) if app.interest_rate else None,
                monthly_payment=float(app.monthly_payment) if app.monthly_payment else None,
                status=app.status.value,
                risk_band=decision.risk_band if decision else None,
                credit_score=decision.credit_score if decision else None,
                disbursed_date=app.disbursed_at or app.decided_at if app.status == LoanStatus.DISBURSED else None,
                outstanding_balance=max(outstanding, 0) if outstanding is not None else None,
                days_past_due=days_past_due,
                next_payment_date=next_payment,
                purpose=app.purpose.value,
                created_at=app.created_at,
            ))
        return entries
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_loan_book")
        raise


# ── Credit Bureau Report ──────────────────────────────

@router.get("/applications/{application_id}/credit-report")
async def get_credit_report(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get the full credit bureau report for an application."""
    try:
        result = await db.execute(
            select(CreditReport)
            .where(CreditReport.loan_application_id == application_id)
            .order_by(CreditReport.pulled_at.desc())
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
            "pulled_at": report.pulled_at.isoformat() if report.pulled_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_credit_report")
        raise


@router.get("/applications/{application_id}/credit-report/download")
async def download_credit_report(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Download credit report as CSV."""
    try:
        result = await db.execute(
            select(CreditReport)
            .where(CreditReport.loan_application_id == application_id)
            .order_by(CreditReport.pulled_at.desc())
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
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="download_credit_report")
        raise


# ── ID Parsing (OCR) ─────────────────────────────────

@router.post("/parse-id", response_model=ParsedIdResponse)
async def parse_id(
    front_image: UploadFile = File(...),
    back_image: UploadFile = File(...),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
):
    """Accept front and back photos of an ID card and return parsed fields via OpenAI Vision."""
    try:
        front_bytes = await front_image.read()
        back_bytes = await back_image.read()

        if len(front_bytes) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Front image too large")
        if len(back_bytes) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Back image too large")

        front_mime = front_image.content_type or "image/jpeg"
        back_mime = back_image.content_type or "image/jpeg"

        parsed = await parse_id_images(front_bytes, back_bytes, front_mime, back_mime)

        return ParsedIdResponse(**{
            k: v for k, v in parsed.items()
            if k in ParsedIdResponse.model_fields
        })
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=None, module="api.underwriter", function_name="parse_id")
        raise


# ── Application Notes ────────────────────────────────


from pydantic import BaseModel, Field


class AddNoteRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


@router.get("/applications/{application_id}/notes")
async def list_notes(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List all notes for an application, newest first."""
    try:
        result = await db.execute(
            select(ApplicationNote)
            .where(ApplicationNote.application_id == application_id)
            .order_by(ApplicationNote.created_at.desc())
        )
        notes = result.scalars().all()
        return [
            {
                "id": n.id,
                "content": n.content,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "user_id": n.user_id,
                "user_name": f"{n.user.first_name} {n.user.last_name}" if n.user else "Unknown",
                "user_email": n.user.email if n.user else None,
            }
            for n in notes
        ]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="list_notes")
        raise


@router.post("/applications/{application_id}/notes", status_code=201)
async def add_note(
    application_id: int,
    data: AddNoteRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Add a note to an application."""
    try:
        # Verify application exists
        result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        note = ApplicationNote(
            application_id=application_id,
            user_id=current_user.id,
            content=data.content,
        )
        db.add(note)
        await db.flush()
        await db.refresh(note, ["user"])

        return {
            "id": note.id,
            "content": note.content,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "user_id": note.user_id,
            "user_name": f"{current_user.first_name} {current_user.last_name}",
            "user_email": current_user.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="add_note")
        raise


# ── Customer Search ──────────────────────────────────


@router.get("/customers/search")
async def search_customers(
    q: str = Query(..., min_length=2, description="Search term (email, name, or phone)"),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Search existing applicant customers by email, name, or phone."""
    try:
        from sqlalchemy import or_

        search = f"%{q.lower()}%"

        result = await db.execute(
            select(User)
            .outerjoin(ApplicantProfile, ApplicantProfile.user_id == User.id)
            .where(
                User.role == UserRole.APPLICANT,
                or_(
                    func.lower(User.email).like(search),
                    func.lower(User.first_name).like(search),
                    func.lower(User.last_name).like(search),
                    func.lower(User.phone).like(search),
                    func.lower(ApplicantProfile.national_id).like(search),
                    func.lower(ApplicantProfile.mobile_phone).like(search),
                ),
            )
            .limit(10)
        )
        users = result.scalars().all()

        # Load profiles for matched users
        results = []
        for u in users:
            prof_result = await db.execute(
                select(ApplicantProfile).where(ApplicantProfile.user_id == u.id)
            )
            profile = prof_result.scalar_one_or_none()

            results.append({
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone": u.phone,
                "profile": {
                    "date_of_birth": str(profile.date_of_birth) if profile and profile.date_of_birth else None,
                    "id_type": profile.id_type if profile else None,
                    "national_id": profile.national_id if profile else None,
                    "gender": profile.gender if profile else None,
                    "marital_status": profile.marital_status if profile else None,
                    "address_line1": profile.address_line1 if profile else None,
                    "address_line2": profile.address_line2 if profile else None,
                    "city": profile.city if profile else None,
                    "parish": profile.parish if profile else None,
                    "whatsapp_number": profile.whatsapp_number if profile else None,
                    "contact_email": profile.contact_email if profile else None,
                    "mobile_phone": profile.mobile_phone if profile else None,
                    "home_phone": profile.home_phone if profile else None,
                    "employer_phone": profile.employer_phone if profile else None,
                    "employer_name": profile.employer_name if profile else None,
                    "employer_sector": profile.employer_sector if profile else None,
                    "job_title": profile.job_title if profile else None,
                    "employment_type": profile.employment_type if profile else None,
                    "years_employed": profile.years_employed if profile else None,
                    "monthly_income": float(profile.monthly_income) if profile and profile.monthly_income else None,
                    "other_income": float(profile.other_income) if profile and profile.other_income else None,
                    "monthly_expenses": float(profile.monthly_expenses) if profile and profile.monthly_expenses else None,
                    "existing_debt": float(profile.existing_debt) if profile and profile.existing_debt else None,
                    "dependents": profile.dependents if profile else None,
                } if profile else None,
            })

        return results
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="search_customers")
        raise


# ── Staff Create Application ─────────────────────────

def _generate_reference() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=8))
    year = datetime.now().year
    return f"ZOT-{year}-{suffix}"


@router.get("/applications/{application_id}/generate-contract")
async def generate_contract_docx(
    application_id: int,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Generate a contract DOCX from the template, pre-populated with application details."""
    try:
        from fastapi.responses import StreamingResponse
        from app.services.contract_generator import generate_contract_docx as gen_docx
        from app.models.catalog import CreditProduct, ProductCategory

        # Load application with items
        result = await db.execute(
            select(LoanApplication)
            .options(selectinload(LoanApplication.items))
            .where(LoanApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # Load applicant profile
        prof_result = await db.execute(
            select(ApplicantProfile).where(ApplicantProfile.user_id == application.applicant_id)
        )
        profile = prof_result.scalar_one_or_none()

        # Load applicant user for name
        user_result = await db.execute(
            select(User).where(User.id == application.applicant_id)
        )
        applicant_user = user_result.scalar_one_or_none()
        applicant_name = ""
        if application.contract_typed_name:
            applicant_name = application.contract_typed_name
        elif applicant_user:
            applicant_name = f"{applicant_user.first_name} {applicant_user.last_name}"

        # Build address from profile
        address_parts = []
        if profile:
            if profile.address_line1:
                address_parts.append(profile.address_line1)
            if profile.address_line2:
                address_parts.append(profile.address_line2)
            if profile.city:
                address_parts.append(profile.city)
            if profile.parish:
                address_parts.append(profile.parish)
        applicant_address = ", ".join(address_parts) or "Address not provided"

        # Product name
        product_name = "Hire Purchase"
        if application.credit_product_id:
            prod_result = await db.execute(
                select(CreditProduct).where(CreditProduct.id == application.credit_product_id)
            )
            prod = prod_result.scalar_one_or_none()
            if prod:
                product_name = prod.name

        # Build items list with category names
        items_list = []
        if application.items:
            cat_ids = [item.category_id for item in application.items]
            if cat_ids:
                cats_result = await db.execute(
                    select(ProductCategory).where(ProductCategory.id.in_(cat_ids))
                )
                cat_map = {c.id: c.name for c in cats_result.scalars().all()}
            else:
                cat_map = {}

            for item in application.items:
                items_list.append({
                    "category_name": cat_map.get(item.category_id, ""),
                    "description": item.description or cat_map.get(item.category_id, ""),
                    "price": float(item.price),
                    "quantity": item.quantity,
                })

        # Contact details
        contact_parts = []
        if profile:
            if profile.mobile_phone:
                contact_parts.append(profile.mobile_phone)
            elif profile.home_phone:
                contact_parts.append(profile.home_phone)
            if profile.contact_email:
                contact_parts.append(profile.contact_email)
        if applicant_user and not contact_parts:
            if applicant_user.phone:
                contact_parts.append(applicant_user.phone)
            if applicant_user.email:
                contact_parts.append(applicant_user.email)
        contact_details = " and ".join(contact_parts) if contact_parts else ""

        # Compute interest + fees
        total_financed = float(application.total_financed or application.amount_requested)
        amount = float(application.amount_requested)
        monthly_payment = float(application.monthly_payment or 0)
        downpayment = float(application.downpayment or 0)
        term_months = application.term_months
        total_repayment = monthly_payment * term_months
        interest_and_fees = total_repayment - (amount - downpayment) if total_repayment > (amount - downpayment) else 0

        docx_buffer = gen_docx(
            applicant_name=applicant_name,
            applicant_address=applicant_address,
            national_id=profile.national_id if profile else "",
            reference_number=application.reference_number,
            product_name=product_name,
            items=items_list if items_list else None,
            amount=amount,
            term_months=term_months,
            monthly_payment=monthly_payment,
            total_financed=total_financed,
            downpayment=downpayment,
            interest_and_fees=interest_and_fees,
            interest_rate=float(application.interest_rate) if application.interest_rate else None,
            signed_at=application.contract_signed_at,
            signature_name=applicant_name,
            signature_data_url=application.contract_signature_data or "",
            contact_details=contact_details,
        )

        filename = f"contract-{application.reference_number}.docx"
        return StreamingResponse(
            docx_buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="generate_contract_docx")
        raise


@router.post("/applications/create-on-behalf", response_model=LoanApplicationResponse, status_code=201)
async def create_on_behalf(
    data: StaffCreateApplicationRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Staff creates an application on behalf of a walk-in customer."""
    try:
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
            "date_of_birth", "id_type", "national_id", "gender", "marital_status",
            "address_line1", "address_line2", "city", "parish",
            "whatsapp_number", "contact_email", "mobile_phone",
            "home_phone", "employer_phone", "employer_name", "employer_sector",
            "job_title", "employment_type",
            "years_employed", "monthly_income", "other_income", "monthly_expenses",
            "existing_debt", "dependents",
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
            merchant_id=data.merchant_id,
            branch_id=data.branch_id,
            credit_product_id=data.credit_product_id,
            downpayment=data.downpayment,
            total_financed=data.total_financed,
        )
        db.add(application)
        await db.flush()

        # Create application items if provided (hire-purchase)
        if data.items:
            for item_data in data.items:
                item = ApplicationItem(
                    loan_application_id=application.id,
                    category_id=item_data.get("category_id"),
                    description=item_data.get("description"),
                    price=item_data.get("price", 0),
                    quantity=item_data.get("quantity", 1),
                )
                db.add(item)

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
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="create_on_behalf")
        raise


# ── Bank Statement Analysis ───────────────────────────────────────────────

@router.post("/applications/{application_id}/analyze-bank-statement", response_model=BankAnalysisResponse)
async def analyze_bank_statement_endpoint(
    application_id: int,
    document_id: Optional[int] = Query(None, description="Specific bank statement document ID. If omitted, uses the latest bank_statement."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
):
    """Trigger AI analysis of a bank statement document."""
    try:
        import asyncio
        import json as _json
        from app.services.bank_statement_analyzer import analyze_bank_statement as run_analysis

        # Verify application exists
        app_q = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        app = app_q.scalar_one_or_none()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        # Find the bank statement document
        if document_id:
            doc_q = await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.loan_application_id == application_id,
                    Document.document_type == DocumentType.BANK_STATEMENT,
                )
            )
        else:
            doc_q = await db.execute(
                select(Document).where(
                    Document.loan_application_id == application_id,
                    Document.document_type == DocumentType.BANK_STATEMENT,
                ).order_by(Document.created_at.desc()).limit(1)
            )
        doc = doc_q.scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail="No bank statement document found for this application. Please upload one first.",
            )

        # Create the analysis record
        analysis = BankStatementAnalysis(
            loan_application_id=application_id,
            document_id=doc.id,
            analyzed_by=current_user.id,
            status=AnalysisStatus.PENDING,
        )
        db.add(analysis)
        await db.flush()

        # Run AI analysis (synchronous OpenAI call, offloaded to thread)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, run_analysis, doc.file_path, doc.mime_type
        )

        if result.get("status") == "error":
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = result.get("error", "Unknown error")
        else:
            analysis.status = AnalysisStatus.COMPLETED
            analysis.summary = result.get("summary")
            analysis.cashflow_data = result.get("categories")
            analysis.flags = result.get("flags", [])
            analysis.monthly_stats = result.get("monthly_stats", [])
            analysis.risk_assessment = result.get("risk_assessment")
            try:
                analysis.volatility_score = float(result.get("volatility_score", 0))
            except (TypeError, ValueError):
                analysis.volatility_score = 0

        await db.flush()
        await db.refresh(analysis)

        summary_str = analysis.summary if isinstance(analysis.summary, str) else (
            _json.dumps(analysis.summary) if analysis.summary else None
        )

        return BankAnalysisResponse(
            id=analysis.id,
            loan_application_id=analysis.loan_application_id,
            document_id=analysis.document_id,
            status=analysis.status.value if hasattr(analysis.status, "value") else str(analysis.status),
            summary=summary_str,
            cashflow_data=analysis.cashflow_data,
            flags=[
                {"type": f.get("type", ""), "severity": f.get("severity", "low"), "detail": f.get("detail", ""), "amount_involved": f.get("amount_involved"), "occurrences": f.get("occurrences")}
                for f in (analysis.flags or [])
            ],
            volatility_score=float(analysis.volatility_score) if analysis.volatility_score else None,
            monthly_stats=analysis.monthly_stats,
            risk_assessment=analysis.risk_assessment,
            income_stability=result.get("income_stability") if result.get("status") != "error" else None,
            avg_monthly_inflow=result.get("avg_monthly_inflow") if result.get("status") != "error" else None,
            avg_monthly_outflow=result.get("avg_monthly_outflow") if result.get("status") != "error" else None,
            avg_monthly_net=result.get("avg_monthly_net") if result.get("status") != "error" else None,
            error_message=analysis.error_message,
            created_at=analysis.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="analyze_bank_statement_endpoint")
        raise


@router.get("/applications/{application_id}/bank-analysis", response_model=BankAnalysisResponse)
async def get_bank_analysis(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
):
    """Get the latest bank statement analysis for an application."""
    try:
        import json as _json

        result = await db.execute(
            select(BankStatementAnalysis).where(
                BankStatementAnalysis.loan_application_id == application_id,
            ).order_by(BankStatementAnalysis.created_at.desc()).limit(1)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise HTTPException(status_code=404, detail="No bank statement analysis found for this application.")

        summary_str = analysis.summary if isinstance(analysis.summary, str) else (
            _json.dumps(analysis.summary) if analysis.summary else None
        )

        return BankAnalysisResponse(
            id=analysis.id,
            loan_application_id=analysis.loan_application_id,
            document_id=analysis.document_id,
            status=analysis.status.value if hasattr(analysis.status, "value") else str(analysis.status),
            summary=summary_str,
            cashflow_data=analysis.cashflow_data,
            flags=[
                {"type": f.get("type", ""), "severity": f.get("severity", "low"), "detail": f.get("detail", ""), "amount_involved": f.get("amount_involved"), "occurrences": f.get("occurrences")}
                for f in (analysis.flags or [])
            ],
            volatility_score=float(analysis.volatility_score) if analysis.volatility_score else None,
            monthly_stats=analysis.monthly_stats,
            risk_assessment=analysis.risk_assessment,
            error_message=analysis.error_message,
            created_at=analysis.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.underwriter", function_name="get_bank_analysis")
        raise
