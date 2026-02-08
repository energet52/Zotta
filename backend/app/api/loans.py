"""Loan application endpoints for consumer portal."""

import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile
from app.models.document import Document, DocumentType, DocumentStatus
from app.schemas import (
    LoanApplicationCreate,
    LoanApplicationUpdate,
    LoanApplicationResponse,
    LoanSubmitResponse,
    ApplicantProfileCreate,
    ApplicantProfileResponse,
    DocumentResponse,
)
from app.auth_utils import get_current_user
from app.config import settings

import os

router = APIRouter()


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
        status=LoanStatus.DRAFT,
    )
    db.add(application)
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
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


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

    return LoanSubmitResponse(
        id=application.id,
        reference_number=application.reference_number,
        status=application.status.value,
        message="Application submitted successfully. You will be notified of updates.",
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
    # Verify ownership
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Application not found")

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
