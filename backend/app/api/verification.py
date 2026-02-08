"""ID verification endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.loan import ApplicantProfile
from app.models.document import Document
from app.schemas import VerificationRequest, VerificationResponse
from app.auth_utils import get_current_user
from app.services.id_verification import verify_identity

router = APIRouter()


@router.post("/verify", response_model=VerificationResponse)
async def verify_id(
    data: VerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit an ID for verification."""
    # Get the document
    result = await db.execute(select(Document).where(Document.id == data.document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Run verification
    verification_result = await verify_identity(
        national_id=data.national_id,
        document_type=data.document_type,
        document_path=document.file_path,
    )

    # Update profile verification status
    profile_result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile:
        profile.id_verified = verification_result["verified"]
        profile.id_verification_status = verification_result["status"]
        profile.national_id = data.national_id

    return VerificationResponse(
        status=verification_result["status"],
        verified=verification_result["verified"],
        details=verification_result.get("details"),
        message=verification_result["message"],
    )


@router.get("/status", response_model=VerificationResponse)
async def get_verification_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current verification status for the user."""
    result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return VerificationResponse(
        status=profile.id_verification_status or "pending",
        verified=profile.id_verified or False,
        message=f"Verification status: {profile.id_verification_status or 'pending'}",
    )
