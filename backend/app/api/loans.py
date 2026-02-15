"""Loan application endpoints for consumer portal."""

import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile, ApplicationItem
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.audit import AuditLog
from app.models.comment import ApplicationComment
from app.models.collection import CollectionChat, ChatDirection
from app.schemas import (
    LoanApplicationCreate,
    LoanApplicationUpdate,
    LoanApplicationResponse,
    ApplicationItemResponse,
    LoanSubmitResponse,
    ApplicantProfileCreate,
    ApplicantProfileResponse,
    DocumentResponse,
    ContractSignRequest,
    SubmitWithConsentRequest,
    ParsedIdResponse,
)
from app.auth_utils import get_current_user, require_roles
from app.models.user import UserRole
from app.config import settings
from app.services.decision_engine.engine import run_decision_engine
from app.services.id_parser import parse_id_images

import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()


# ── ID Parsing (OCR) ─────────────────────────────────

@router.post("/parse-id", response_model=ParsedIdResponse)
async def parse_id_consumer(
    front_image: UploadFile = File(...),
    back_image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Accept front and back photos of an ID card and return parsed fields (consumer portal)."""
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


def generate_reference() -> str:
    """Generate a unique loan reference number like ZOT-2026-ABCD1234."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=8))
    year = datetime.now().year
    return f"ZOT-{year}-{suffix}"


# ── Profile ───────────────────────────────────────────

@router.get("/profile", response_model=ApplicantProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile", response_model=ApplicantProfileResponse)
async def update_profile(
    data: ApplicantProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = ApplicantProfile(user_id=current_user.id)
        db.add(profile)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)
    return profile


# ── Loan Applications ─────────────────────────────────

@router.post("/", response_model=LoanApplicationResponse, status_code=201)
async def create_application(
    data: LoanApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    application = LoanApplication(
        reference_number=generate_reference(),
        applicant_id=current_user.id,
        amount_requested=data.amount_requested,
        term_months=data.term_months,
        purpose=LoanPurpose(data.purpose),
        purpose_description=data.purpose_description,
        merchant_id=data.merchant_id,
        branch_id=data.branch_id,
        credit_product_id=data.credit_product_id,
        downpayment=data.downpayment,
        total_financed=data.total_financed,
        status=LoanStatus.DRAFT,
    )
    db.add(application)
    await db.flush()

    # Optional hire-purchase basket items
    for item in data.items:
        db.add(
            ApplicationItem(
                loan_application_id=application.id,
                category_id=item.category_id,
                description=item.description,
                price=item.price,
                quantity=item.quantity,
            )
        )
    await db.flush()
    await db.refresh(application)
    return application


@router.get("/", response_model=list[LoanApplicationResponse])
async def list_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication)
        .where(LoanApplication.applicant_id == current_user.id)
        .order_by(LoanApplication.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{application_id}", response_model=LoanApplicationResponse)
async def get_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication)
        .where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
        )
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
    return LoanApplicationResponse(
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


@router.put("/{application_id}", response_model=LoanApplicationResponse)
async def update_application(
    application_id: int,
    data: LoanApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status == LoanStatus.DRAFT,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not editable")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "purpose" and value:
            value = LoanPurpose(value)
        setattr(application, field, value)

    await db.flush()
    await db.refresh(application)
    return application


@router.post("/{application_id}/submit", response_model=LoanSubmitResponse)
async def submit_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status == LoanStatus.DRAFT,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or already submitted")

    application.status = LoanStatus.SUBMITTED
    application.submitted_at = datetime.now(timezone.utc)
    await db.flush()

    # Run the decision engine (scoring + business rules) immediately.
    # If the engine fails for any reason the application still stays SUBMITTED
    # so an underwriter can review it manually later.
    engine_message = "Application submitted successfully. You will be notified of updates."
    try:
        decision = await run_decision_engine(application.id, db)
        await db.flush()
        if decision.final_outcome == "auto_approve":
            engine_message = "Application submitted and pre-approved! Review your offer on the status page."
        elif decision.final_outcome == "auto_decline":
            engine_message = "Application submitted. Unfortunately it was not approved at this time."
        else:
            engine_message = "Application submitted and is under review. You will be notified of updates."
    except Exception as exc:
        logger.warning("Decision engine failed for application %s: %s", application.id, exc)
        # Application remains in SUBMITTED status — underwriters can pick it up.

    return LoanSubmitResponse(
        id=application.id,
        reference_number=application.reference_number,
        status=application.status.value,
        message=engine_message,
    )


@router.post("/{application_id}/submit-with-consent", response_model=LoanSubmitResponse)
async def submit_with_consent(
    application_id: int,
    data: SubmitWithConsentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a draft application with signed consent/contract in one step."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status == LoanStatus.DRAFT,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or already submitted")

    if not data.agreed:
        raise HTTPException(status_code=400, detail="You must agree to the terms")

    # Store consent / contract signature
    application.contract_signature_data = data.signature_data
    application.contract_typed_name = data.typed_name
    application.contract_signed_at = datetime.now(timezone.utc)

    # Transition to SUBMITTED and run decision engine (same as submit endpoint)
    application.status = LoanStatus.SUBMITTED
    application.submitted_at = datetime.now(timezone.utc)
    await db.flush()

    engine_message = "Application submitted successfully. You will be notified of updates."
    try:
        decision = await run_decision_engine(application.id, db)
        await db.flush()
        if decision.final_outcome == "auto_approve":
            engine_message = "Application submitted and pre-approved! Review your offer on the status page."
        elif decision.final_outcome == "auto_decline":
            engine_message = "Application submitted. Unfortunately it was not approved at this time."
        else:
            engine_message = "Application submitted and is under review. You will be notified of updates."
    except Exception as exc:
        logger.warning("Decision engine failed for application %s: %s", application.id, exc)

    # Audit log
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="consent_signed_and_submitted",
        user_id=current_user.id,
        new_values={
            "typed_name": data.typed_name,
            "signed_at": application.contract_signed_at.isoformat(),
        },
    )
    db.add(audit)
    await db.flush()

    return LoanSubmitResponse(
        id=application.id,
        reference_number=application.reference_number,
        status=application.status.value,
        message=engine_message,
    )


# ── Documents ─────────────────────────────────────────

@router.post("/{application_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    application_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    final_statuses = (
        LoanStatus.DECLINED,
        LoanStatus.REJECTED_BY_APPLICANT,
        LoanStatus.DISBURSED,
        LoanStatus.CANCELLED,
        LoanStatus.APPROVED,
    )
    if application.status in final_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upload documents when application status is {application.status.value}",
        )

    # Validate file size
    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    # Save file
    upload_dir = os.path.join(settings.upload_dir, str(application_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        loan_application_id=application_id,
        uploaded_by=current_user.id,
        document_type=DocumentType(document_type),
        file_name=file.filename,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        status=DocumentStatus.UPLOADED,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


@router.get("/{application_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Application not found")

    result = await db.execute(
        select(Document).where(Document.loan_application_id == application_id)
    )
    return result.scalars().all()


@router.get("/{application_id}/documents/{document_id}/download")
async def download_document(
    application_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication, Document).join(
            Document, Document.loan_application_id == LoanApplication.id
        ).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
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


@router.delete("/{application_id}/documents/{document_id}")
async def delete_document(
    application_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoanApplication, Document).join(
            Document, Document.loan_application_id == LoanApplication.id
        ).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            Document.id == document_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    application, doc = row
    final_statuses = (
        LoanStatus.DECLINED,
        LoanStatus.REJECTED_BY_APPLICANT,
        LoanStatus.DISBURSED,
        LoanStatus.CANCELLED,
        LoanStatus.APPROVED,
    )
    if application.status in final_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete documents when application status is {application.status.value}",
        )
    if os.path.isfile(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass
    await db.delete(doc)
    await db.flush()
    return {"message": "Document deleted"}


# ── Counterproposal ─────────────────────────────────

@router.post("/{application_id}/accept-counterproposal", response_model=LoanApplicationResponse)
async def accept_counterproposal(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumer accepts the underwriter's counterproposal."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status == LoanStatus.COUNTER_PROPOSED,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not in counter-proposed status")

    # Accept the proposed terms
    application.amount_approved = application.proposed_amount
    application.interest_rate = application.proposed_rate
    if application.proposed_term:
        application.term_months = application.proposed_term

    # Calculate monthly payment
    if application.proposed_rate and application.proposed_term:
        r = float(application.proposed_rate) / 100 / 12
        n = application.proposed_term
        principal = float(application.proposed_amount or application.amount_requested)
        if r > 0:
            pmt = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        else:
            pmt = principal / n
        application.monthly_payment = round(pmt, 2)

    application.status = LoanStatus.APPROVED
    application.decided_at = datetime.now(timezone.utc)

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="counterproposal_accepted",
        user_id=current_user.id,
        new_values={
            "accepted_amount": float(application.proposed_amount) if application.proposed_amount else None,
            "accepted_rate": float(application.proposed_rate) if application.proposed_rate else None,
            "accepted_term": application.proposed_term,
        },
    )
    db.add(audit)
    await db.flush()
    await db.refresh(application)
    return application


@router.post("/{application_id}/reject-counterproposal", response_model=LoanApplicationResponse)
async def reject_counterproposal(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumer rejects the underwriter's counterproposal."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status == LoanStatus.COUNTER_PROPOSED,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not in counter-proposed status")

    application.status = LoanStatus.REJECTED_BY_APPLICANT

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="counterproposal_rejected",
        user_id=current_user.id,
        new_values={"status": "rejected_by_applicant"},
    )
    db.add(audit)
    await db.flush()
    await db.refresh(application)
    return application


# ── Contract Signature ───────────────────────────────

@router.post("/{application_id}/sign-contract", response_model=LoanApplicationResponse)
async def sign_contract(
    application_id: int,
    data: ContractSignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumer signs the loan contract."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status not in (LoanStatus.APPROVED, LoanStatus.OFFER_SENT, LoanStatus.ACCEPTED):
        raise HTTPException(status_code=400, detail="Application must be approved before signing")

    if not data.agreed:
        raise HTTPException(status_code=400, detail="You must agree to the terms")

    application.contract_signature_data = data.signature_data
    application.contract_typed_name = data.typed_name
    application.contract_signed_at = datetime.now(timezone.utc)
    application.status = LoanStatus.ACCEPTED

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="contract_signed",
        user_id=current_user.id,
        new_values={
            "typed_name": data.typed_name,
            "signed_at": application.contract_signed_at.isoformat(),
        },
    )
    db.add(audit)
    await db.flush()
    await db.refresh(application)
    return application


# ── Accept / Decline Offer ───────────────────────────

@router.post("/{application_id}/accept-offer", response_model=LoanApplicationResponse)
async def accept_offer(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumer accepts the approved loan offer."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status.in_([LoanStatus.APPROVED, LoanStatus.OFFER_SENT]),
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not in approved status")

    application.status = LoanStatus.ACCEPTED

    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="offer_accepted",
        user_id=current_user.id,
        new_values={"status": "accepted"},
    )
    db.add(audit)
    await db.flush()
    await db.refresh(application)
    return application


@router.post("/{application_id}/decline-offer", response_model=LoanApplicationResponse)
async def decline_offer(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumer declines the approved loan offer."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status.in_([LoanStatus.APPROVED, LoanStatus.OFFER_SENT]),
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not in approved status")

    application.status = LoanStatus.REJECTED_BY_APPLICANT

    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="offer_declined",
        user_id=current_user.id,
        new_values={"status": "rejected_by_applicant"},
    )
    db.add(audit)
    await db.flush()
    await db.refresh(application)
    return application


# ── Consent PDF Download ─────────────────────────────

@router.get("/{application_id}/consent-pdf")
async def download_consent_pdf(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the signed contract as DOCX (from template).

    Accessible by:
    * The applicant who owns the application
    * Any staff member (admin / underwriter)
    """
    from fastapi.responses import StreamingResponse
    from app.services.contract_generator import generate_contract_docx as gen_docx
    from app.models.catalog import CreditProduct, ProductCategory
    from sqlalchemy.orm import selectinload as _sl

    STAFF = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER)

    # Load application with items
    result = await db.execute(
        select(LoanApplication)
        .options(_sl(LoanApplication.items))
        .where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Access check
    is_owner = application.applicant_id == current_user.id
    is_staff = current_user.role in STAFF
    if not is_owner and not is_staff:
        raise HTTPException(status_code=404, detail="Application not found")

    if not application.contract_signed_at:
        raise HTTPException(status_code=400, detail="Contract has not been signed yet")

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
    applicant_name = application.contract_typed_name or ""
    if not applicant_name and applicant_user:
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
    amount_val = float(application.amount_requested)
    monthly_payment = float(application.monthly_payment or 0)
    downpayment = float(application.downpayment or 0)
    term_months = application.term_months
    total_repayment = monthly_payment * term_months
    interest_and_fees = total_repayment - (amount_val - downpayment) if total_repayment > (amount_val - downpayment) else 0

    docx_buffer = gen_docx(
        applicant_name=applicant_name,
        applicant_address=applicant_address,
        national_id=profile.national_id if profile else "",
        reference_number=application.reference_number,
        product_name=product_name,
        items=items_list if items_list else None,
        amount=amount_val,
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

    # Convert DOCX to PDF for download (always succeeds — reportlab fallback)
    from app.services.docx_to_pdf import convert_docx_to_pdf
    pdf_buffer = convert_docx_to_pdf(docx_buffer)
    filename = f"hire-purchase-agreement-{application.reference_number}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Application References ─────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel, Field as _Field
from app.models.reference import ApplicationReference


class _ReferenceRequest(_BaseModel):
    name: str = _Field(..., min_length=1, max_length=200)
    relationship_type: str = _Field(..., min_length=1, max_length=100)
    phone: str = _Field(..., min_length=1, max_length=30)
    address: str = _Field(..., min_length=1, max_length=500)
    directions: str | None = _Field(None, max_length=2000)


def _ref_to_dict(r: ApplicationReference) -> dict:
    return {
        "id": r.id,
        "application_id": r.application_id,
        "name": r.name,
        "relationship_type": r.relationship_type,
        "phone": r.phone,
        "address": r.address,
        "directions": r.directions,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def _verify_app_access(
    application_id: int, current_user: User, db: AsyncSession
) -> LoanApplication:
    """Verify that the current user (owner or staff) can access the application."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    from app.models.user import UserRole
    STAFF = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER)
    if application.applicant_id != current_user.id and current_user.role not in STAFF:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.get("/{application_id}/references")
async def list_references(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all references for an application."""
    await _verify_app_access(application_id, current_user, db)
    result = await db.execute(
        select(ApplicationReference)
        .where(ApplicationReference.application_id == application_id)
        .order_by(ApplicationReference.created_at.asc())
    )
    return [_ref_to_dict(r) for r in result.scalars().all()]


@router.post("/{application_id}/references", status_code=201)
async def add_reference(
    application_id: int,
    data: _ReferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a reference to an application."""
    await _verify_app_access(application_id, current_user, db)
    ref = ApplicationReference(
        application_id=application_id,
        name=data.name,
        relationship_type=data.relationship_type,
        phone=data.phone,
        address=data.address,
        directions=data.directions,
    )
    db.add(ref)
    await db.commit()
    await db.refresh(ref)
    return _ref_to_dict(ref)


@router.put("/{application_id}/references/{reference_id}")
async def update_reference(
    application_id: int,
    reference_id: int,
    data: _ReferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a reference."""
    await _verify_app_access(application_id, current_user, db)
    result = await db.execute(
        select(ApplicationReference).where(
            ApplicationReference.id == reference_id,
            ApplicationReference.application_id == application_id,
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Reference not found")
    ref.name = data.name
    ref.relationship_type = data.relationship_type
    ref.phone = data.phone
    ref.address = data.address
    ref.directions = data.directions
    await db.commit()
    await db.refresh(ref)
    return _ref_to_dict(ref)


@router.delete("/{application_id}/references/{reference_id}")
async def delete_reference(
    application_id: int,
    reference_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a reference."""
    await _verify_app_access(application_id, current_user, db)
    result = await db.execute(
        select(ApplicationReference).where(
            ApplicationReference.id == reference_id,
            ApplicationReference.application_id == application_id,
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Reference not found")
    await db.delete(ref)
    await db.commit()
    return {"status": "deleted"}


# ── Application Comments (consumer ↔ underwriter messaging) ───────────────


class _AddCommentRequest(_BaseModel):
    content: str = _Field(..., min_length=1, max_length=5000)


@router.get("/{application_id}/comments")
async def list_comments(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all comments for an application (visible to both applicant and staff)."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Access: owner or staff
    from app.models.user import UserRole
    STAFF = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER)
    if application.applicant_id != current_user.id and current_user.role not in STAFF:
        raise HTTPException(status_code=404, detail="Application not found")

    comments_result = await db.execute(
        select(ApplicationComment)
        .where(ApplicationComment.application_id == application_id)
        .order_by(ApplicationComment.created_at.asc())
    )
    comments = comments_result.scalars().all()

    return [
        {
            "id": c.id,
            "content": c.content,
            "is_from_applicant": c.is_from_applicant,
            "author_name": f"{c.user.first_name} {c.user.last_name}" if c.user else "Unknown",
            "author_role": c.user.role if c.user else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ]


@router.post("/{application_id}/comments", status_code=201)
async def add_comment(
    application_id: int,
    data: _AddCommentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to an application. Consumers are marked as applicant comments."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Access: owner or staff
    from app.models.user import UserRole
    STAFF = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER)
    is_owner = application.applicant_id == current_user.id
    is_staff = current_user.role in STAFF
    if not is_owner and not is_staff:
        raise HTTPException(status_code=404, detail="Application not found")

    comment = ApplicationComment(
        application_id=application_id,
        user_id=current_user.id,
        content=data.content,
        is_from_applicant=is_owner and not is_staff,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    # Eagerly load user relationship
    await db.refresh(comment, attribute_names=["user"])

    return {
        "id": comment.id,
        "content": comment.content,
        "is_from_applicant": comment.is_from_applicant,
        "author_name": f"{comment.user.first_name} {comment.user.last_name}" if comment.user else "Unknown",
        "author_role": comment.user.role if comment.user else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.get("/notifications/messages")
async def get_message_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all staff messages across all of the consumer's applications.
    Returns unread count and recent messages grouped by application."""
    from datetime import datetime, timezone as tz

    # Get all applications belonging to this user
    apps_result = await db.execute(
        select(LoanApplication).where(LoanApplication.applicant_id == current_user.id)
    )
    apps = apps_result.scalars().all()
    app_ids = [a.id for a in apps]
    app_map = {a.id: a.reference_number for a in apps}

    if not app_ids:
        return {"unread_count": 0, "notifications": []}

    # Get all staff comments on these applications (not from applicant)
    comments_result = await db.execute(
        select(ApplicationComment)
        .where(
            ApplicationComment.application_id.in_(app_ids),
            ApplicationComment.is_from_applicant == False,  # noqa: E712
        )
        .order_by(ApplicationComment.created_at.desc())
    )
    comments = comments_result.scalars().all()

    unread_count = sum(1 for c in comments if c.read_at is None)

    notifications = [
        {
            "id": c.id,
            "application_id": c.application_id,
            "reference_number": app_map.get(c.application_id, ""),
            "content": c.content,
            "author_name": f"{c.user.first_name} {c.user.last_name}" if c.user else "Staff",
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "read": c.read_at is not None,
        }
        for c in comments
    ]

    return {"unread_count": unread_count, "notifications": notifications}


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all staff messages as read for the current consumer."""
    from datetime import datetime, timezone as tz
    from sqlalchemy import update

    # Get all application IDs belonging to this user
    apps_result = await db.execute(
        select(LoanApplication.id).where(LoanApplication.applicant_id == current_user.id)
    )
    app_ids = [row[0] for row in apps_result.all()]

    if app_ids:
        await db.execute(
            update(ApplicationComment)
            .where(
                ApplicationComment.application_id.in_(app_ids),
                ApplicationComment.is_from_applicant == False,  # noqa: E712
                ApplicationComment.read_at.is_(None),
            )
            .values(read_at=datetime.now(tz.utc))
        )
        await db.commit()

    return {"status": "ok"}


@router.post("/{application_id}/comments/mark-read")
async def mark_application_comments_read(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all staff messages on a specific application as read."""
    from datetime import datetime, timezone as tz
    from sqlalchemy import update

    # Verify ownership
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application or application.applicant_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")

    await db.execute(
        update(ApplicationComment)
        .where(
            ApplicationComment.application_id == application_id,
            ApplicationComment.is_from_applicant == False,  # noqa: E712
            ApplicationComment.read_at.is_(None),
        )
        .values(read_at=datetime.now(tz.utc))
    )
    await db.commit()

    return {"status": "ok"}


# ── Collection messages (consumer-facing) ─────────────────────


@router.get("/notifications/collection-messages")
async def get_collection_messages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all collection WhatsApp messages for the consumer's loans.

    Allows borrowers to see messages sent by the collections team.
    """
    # Get all applications belonging to this user
    apps_result = await db.execute(
        select(LoanApplication).where(LoanApplication.applicant_id == current_user.id)
    )
    apps = apps_result.scalars().all()
    app_ids = [a.id for a in apps]
    app_map = {a.id: a.reference_number for a in apps}

    if not app_ids:
        return {"messages": []}

    # Fetch all collection chat messages for these applications
    chats_result = await db.execute(
        select(CollectionChat)
        .where(CollectionChat.loan_application_id.in_(app_ids))
        .order_by(CollectionChat.created_at.desc())
    )
    chats = chats_result.scalars().all()

    messages = [
        {
            "id": c.id,
            "application_id": c.loan_application_id,
            "reference_number": app_map.get(c.loan_application_id, ""),
            "direction": c.direction.value.lower(),
            "message": c.message,
            "channel": c.channel,
            "status": c.status.value.lower(),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in chats
    ]

    return {"messages": messages}


@router.get("/{application_id}/collection-messages")
async def get_application_collection_messages(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return collection WhatsApp messages for a specific application.

    Allows borrowers to see their collection conversation.
    """
    # Verify ownership
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application or application.applicant_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")

    chats_result = await db.execute(
        select(CollectionChat)
        .where(CollectionChat.loan_application_id == application_id)
        .order_by(CollectionChat.created_at.asc())
    )
    chats = chats_result.scalars().all()

    return [
        {
            "id": c.id,
            "application_id": c.loan_application_id,
            "reference_number": application.reference_number,
            "direction": c.direction.value.lower(),
            "message": c.message,
            "channel": c.channel,
            "status": c.status.value.lower(),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in chats
    ]
