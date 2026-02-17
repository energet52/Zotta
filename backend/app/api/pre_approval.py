"""Pre-Approval API — consumer-facing and admin endpoints."""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth_utils import get_current_user, require_roles
from app.config import settings
from app.models.pre_approval import PreApproval, PreApprovalOTP
from app.models.catalog import Merchant, Branch, CreditProduct
from app.models.user import User
from app.models.loan import LoanApplication, LoanStatus, LoanPurpose, ApplicantProfile, ApplicationItem
from app.schemas import (
    PreApprovalStartRequest,
    PreApprovalConsentRequest,
    PreApprovalOTPRequest,
    PreApprovalCheckLowerRequest,
    PreApprovalAdminDecideRequest,
    PreApprovalStatusLookupRequest,
    PreApprovalResponse,
    PreApprovalAdminListItem,
    PreApprovalAnalyticsResponse,
)
from app.services.pre_approval_engine import (
    run_pre_approval,
    PreApprovalInput,
)
from app.services.otp_service import send_otp, verify_otp
from app.services.price_tag_parser import parse_price_tag
from app.services.document_requirements import get_required_documents

logger = logging.getLogger(__name__)

router = APIRouter()

UNDERWRITER_ROLES = ("admin", "underwriter", "senior_underwriter", "loan_officer")


# ──────────────────────────────────────────────────────────────────
# Consumer endpoints (public — no auth required)
# ──────────────────────────────────────────────────────────────────

@router.post("/parse-price-tag")
async def parse_price_tag_photo(
    file: UploadFile = File(...),
):
    """Upload a price tag photo and get AI-extracted data."""
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 10 MB)")

    mime = file.content_type or "image/jpeg"
    result = await parse_price_tag(contents, mime)
    return result


@router.get("/merchants")
async def search_merchants(
    q: str = Query("", description="Search term"),
    db: AsyncSession = Depends(get_db),
):
    """Search active merchants (public endpoint for pre-approval flow)."""
    query = select(Merchant).where(Merchant.is_active == True)
    if q:
        query = query.where(Merchant.name.ilike(f"%{q}%"))
    query = query.order_by(Merchant.name).limit(50)
    result = await db.execute(query)
    merchants = result.scalars().all()
    return [{"id": m.id, "name": m.name} for m in merchants]


@router.get("/merchants/{merchant_id}/branches")
async def list_merchant_branches(
    merchant_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List branches for a merchant."""
    result = await db.execute(
        select(Branch).where(
            Branch.merchant_id == merchant_id,
            Branch.is_active == True,
        ).order_by(Branch.name)
    )
    branches = result.scalars().all()
    return [{"id": b.id, "name": b.name, "address": b.address} for b in branches]


@router.get("/products/check-limits")
async def check_product_limits(
    amount: float = Query(...),
    merchant_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Check if an amount is within product financing limits."""
    query = select(CreditProduct).where(
        CreditProduct.is_active == True,
        CreditProduct.lifecycle_status == "active",
    )
    result = await db.execute(query)
    products = result.scalars().all()

    matching = []
    for p in products:
        if float(p.min_amount) <= amount <= float(p.max_amount):
            if merchant_id is None or p.merchant_id == merchant_id or p.merchant_id is None:
                matching.append({
                    "id": p.id,
                    "name": p.name,
                    "min_amount": float(p.min_amount),
                    "max_amount": float(p.max_amount),
                    "rate": float(p.interest_rate) if p.interest_rate else None,
                    "min_term": p.min_term_months,
                    "max_term": p.max_term_months,
                })

    within_limits = len(matching) > 0
    min_limit = min((float(p.min_amount) for p in products), default=0) if products else 0
    max_limit = max((float(p.max_amount) for p in products), default=0) if products else 0

    return {
        "within_limits": within_limits,
        "matching_products": matching,
        "min_limit": min_limit,
        "max_limit": max_limit,
        "message": None if within_limits else f"We finance items between TTD {min_limit:,.0f} and TTD {max_limit:,.0f}.",
    }


@router.post("/start", response_model=PreApprovalResponse)
async def start_pre_approval(
    data: PreApprovalStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit Step 1+2 data and create a pending pre-approval record.

    Returns reference code for subsequent OTP and consent steps.
    """
    dob = None
    if data.date_of_birth:
        try:
            dob = date.fromisoformat(data.date_of_birth)
        except ValueError:
            raise HTTPException(400, "Invalid date_of_birth format. Use YYYY-MM-DD.")

    pa_input = PreApprovalInput(
        phone=data.phone,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=dob,
        national_id=data.national_id,
        email=data.email,
        price=data.price,
        currency=data.currency,
        downpayment=data.downpayment,
        item_description=data.item_description,
        goods_category=data.goods_category,
        merchant_id=data.merchant_id,
        merchant_name_manual=data.merchant_name_manual,
        branch_id=data.branch_id,
        monthly_income=data.monthly_income,
        income_frequency=data.income_frequency,
        employment_status=data.employment_status,
        employment_tenure=data.employment_tenure,
        employer_name=data.employer_name,
        monthly_expenses=data.monthly_expenses,
        existing_loan_payments=data.existing_loan_payments,
        photo_url=data.photo_url,
        photo_extraction_data=data.photo_extraction_data,
    )

    result = await run_pre_approval(pa_input, db)

    return PreApprovalResponse(
        reference_code=result.reference_code,
        outcome=result.outcome,
        status="active",
        financing_amount=result.financing_amount,
        estimated_monthly_payment=result.estimated_monthly_payment,
        estimated_tenure_months=result.estimated_tenure_months,
        estimated_rate=result.estimated_rate,
        credit_product_name=result.credit_product_name,
        dti_ratio=result.dti_ratio,
        ndi_amount=result.ndi_amount,
        expires_at=result.expires_at,
        message=result.message,
        reasons=result.reasons,
        suggestions=result.suggestions,
        alternative_amount=result.alternative_amount,
        alternative_payment=result.alternative_payment,
        document_checklist=result.document_checklist,
        merchant_name=result.merchant_name,
        merchant_approved=result.merchant_approved,
        item_description=data.item_description,
        price=data.price,
        currency=data.currency,
        downpayment=data.downpayment,
        goods_category=data.goods_category,
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
    )


@router.post("/{ref}/send-otp")
async def send_otp_endpoint(
    ref: str,
    db: AsyncSession = Depends(get_db),
):
    """Send OTP to the phone number on the pre-approval."""
    pa = await _get_pre_approval(ref, db)
    result = await send_otp(pa.phone, db)
    return result


@router.post("/{ref}/verify-otp")
async def verify_otp_endpoint(
    ref: str,
    data: PreApprovalOTPRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify OTP code."""
    pa = await _get_pre_approval(ref, db)
    result = await verify_otp(pa.phone, data.code, db)
    if result["verified"]:
        pa.otp_verified_at = datetime.now(timezone.utc)
        await db.flush()
    return result


@router.get("/{ref}/status", response_model=PreApprovalResponse)
async def get_pre_approval_status(
    ref: str,
    phone: str = Query(..., description="Phone for verification"),
    db: AsyncSession = Depends(get_db),
):
    """Check pre-approval status (requires phone for identity verification)."""
    result = await db.execute(
        select(PreApproval).where(
            PreApproval.reference_code == ref,
            PreApproval.phone == phone,
        )
    )
    pa = result.scalar_one_or_none()
    if not pa:
        raise HTTPException(404, "Pre-approval not found or phone does not match")

    # Check expiry
    if pa.status == "active" and pa.expires_at and pa.expires_at < datetime.now(timezone.utc):
        pa.status = "expired"
        await db.flush()

    merchant_name = pa.merchant_name_manual
    if pa.merchant_id and pa.merchant:
        merchant_name = pa.merchant.name

    details = pa.outcome_details or {}
    return PreApprovalResponse(
        reference_code=pa.reference_code,
        outcome=pa.outcome,
        status=pa.status,
        financing_amount=float(pa.financing_amount) if pa.financing_amount else None,
        estimated_monthly_payment=float(pa.estimated_monthly_payment) if pa.estimated_monthly_payment else None,
        estimated_tenure_months=pa.estimated_tenure_months,
        estimated_rate=float(pa.estimated_rate) if pa.estimated_rate else None,
        credit_product_name=pa.credit_product.name if pa.credit_product else None,
        dti_ratio=float(pa.dti_ratio) if pa.dti_ratio else None,
        ndi_amount=float(pa.ndi_amount) if pa.ndi_amount else None,
        expires_at=pa.expires_at,
        message=details.get("message", ""),
        reasons=details.get("reasons", []),
        suggestions=details.get("suggestions", []),
        alternative_amount=details.get("alternative_amount"),
        alternative_payment=details.get("alternative_payment"),
        document_checklist=details.get("document_checklist", []),
        merchant_name=merchant_name,
        merchant_approved=pa.merchant_id is not None,
        item_description=pa.item_description,
        price=float(pa.price),
        currency=pa.currency,
        downpayment=float(pa.downpayment),
        goods_category=pa.goods_category,
        first_name=pa.first_name,
        last_name=pa.last_name,
        phone=pa.phone,
        created_at=pa.created_at,
    )


@router.get("/{ref}/document-checklist")
async def get_document_checklist(
    ref: str,
    db: AsyncSession = Depends(get_db),
):
    """Get personalized document checklist for a pre-approval."""
    pa = await _get_pre_approval(ref, db)
    emp_status = (pa.employment_status or "").lower()
    emp_type = "self_employed" if "self" in emp_status else "employed"
    docs = get_required_documents(
        employment_type=emp_type,
        amount=float(pa.financing_amount or pa.price),
    )
    docs.append({
        "type": "quotation",
        "label": "Quotation or proforma invoice from the merchant",
        "why": "Confirms the item and price for financing",
    })
    return {"reference_code": ref, "documents": docs}


@router.post("/{ref}/check-lower-amount", response_model=PreApprovalResponse)
async def check_lower_amount(
    ref: str,
    data: PreApprovalCheckLowerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Re-run pre-approval at a lower amount using existing data."""
    pa = await _get_pre_approval(ref, db)

    dob = None
    if pa.date_of_birth:
        dob = pa.date_of_birth if isinstance(pa.date_of_birth, date) else date.fromisoformat(str(pa.date_of_birth))

    new_downpayment = float(pa.price) - data.amount
    if new_downpayment < 0:
        new_downpayment = 0

    pa_input = PreApprovalInput(
        phone=pa.phone,
        first_name=pa.first_name,
        last_name=pa.last_name,
        date_of_birth=dob,
        national_id=pa.national_id,
        email=pa.email,
        price=float(pa.price),
        currency=pa.currency,
        downpayment=new_downpayment,
        item_description=pa.item_description,
        goods_category=pa.goods_category,
        merchant_id=pa.merchant_id,
        merchant_name_manual=pa.merchant_name_manual,
        branch_id=pa.branch_id,
        monthly_income=float(pa.monthly_income),
        income_frequency=pa.income_frequency,
        employment_status=pa.employment_status,
        employment_tenure=pa.employment_tenure,
        employer_name=pa.employer_name,
        monthly_expenses=float(pa.monthly_expenses),
        existing_loan_payments=float(pa.existing_loan_payments),
    )

    result = await run_pre_approval(pa_input, db)
    return PreApprovalResponse(
        reference_code=result.reference_code,
        outcome=result.outcome,
        status="active",
        financing_amount=result.financing_amount,
        estimated_monthly_payment=result.estimated_monthly_payment,
        estimated_tenure_months=result.estimated_tenure_months,
        estimated_rate=result.estimated_rate,
        credit_product_name=result.credit_product_name,
        dti_ratio=result.dti_ratio,
        ndi_amount=result.ndi_amount,
        expires_at=result.expires_at,
        message=result.message,
        reasons=result.reasons,
        suggestions=result.suggestions,
        alternative_amount=result.alternative_amount,
        alternative_payment=result.alternative_payment,
        document_checklist=result.document_checklist,
        merchant_name=result.merchant_name,
        merchant_approved=result.merchant_approved,
        item_description=pa.item_description,
        price=float(pa.price),
        currency=pa.currency,
        downpayment=new_downpayment,
        goods_category=pa.goods_category,
        first_name=pa.first_name,
        last_name=pa.last_name,
        phone=pa.phone,
    )


@router.post("/{ref}/convert")
async def convert_to_application(
    ref: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Convert a pre-approval into a full loan application (requires auth)."""
    pa = await _get_pre_approval(ref, db)

    if pa.status == "converted":
        raise HTTPException(400, "This pre-approval has already been converted to an application")
    if pa.status == "expired":
        raise HTTPException(400, "This pre-approval has expired. Please check eligibility again.")
    if pa.outcome not in ("pre_approved", "conditionally_approved"):
        raise HTTPException(400, "Only pre-approved or conditionally approved records can be converted")

    # Create the application
    import random as _random
    import string as _string
    ref_num = "ZOT-" + "".join(_random.choices(_string.ascii_uppercase + _string.digits, k=8))

    financing = float(pa.financing_amount or (float(pa.price) - float(pa.downpayment)))
    application = LoanApplication(
        reference_number=ref_num,
        applicant_id=current_user.id,
        merchant_id=pa.merchant_id,
        branch_id=pa.branch_id,
        credit_product_id=pa.credit_product_id,
        amount_requested=financing,
        term_months=pa.estimated_tenure_months or 24,
        purpose=LoanPurpose.PERSONAL,
        purpose_description=f"Hire purchase: {pa.item_description or 'Item'} (Pre-approval {pa.reference_code})",
        interest_rate=float(pa.estimated_rate) if pa.estimated_rate else None,
        downpayment=float(pa.downpayment),
        total_financed=financing,
        status=LoanStatus.DRAFT,
    )
    db.add(application)
    await db.flush()

    # Update pre-approval
    pa.linked_application_id = application.id
    pa.status = "converted"
    await db.flush()

    # Ensure the user profile has the pre-approval data
    prof_result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == current_user.id)
    )
    profile = prof_result.scalar_one_or_none()
    if profile:
        if not profile.national_id and pa.national_id:
            profile.national_id = pa.national_id
        if not profile.employer_name and pa.employer_name:
            profile.employer_name = pa.employer_name
        if not profile.employment_type and pa.employment_status:
            profile.employment_type = pa.employment_status
        if not profile.monthly_income and pa.monthly_income:
            profile.monthly_income = float(pa.monthly_income)
        if not profile.monthly_expenses and pa.monthly_expenses:
            profile.monthly_expenses = float(pa.monthly_expenses)
        if not profile.existing_debt and pa.existing_loan_payments:
            profile.existing_debt = float(pa.existing_loan_payments)
        await db.flush()

    return {
        "application_id": application.id,
        "reference_number": ref_num,
        "pre_approval_reference": pa.reference_code,
        "message": "Application created from pre-approval. Complete the remaining steps to submit.",
    }


# ──────────────────────────────────────────────────────────────────
# Admin / Backoffice endpoints (auth required)
# ──────────────────────────────────────────────────────────────────

@router.get("/admin/list")
async def list_pre_approvals(
    status: str | None = Query(None),
    outcome: str | None = Query(None),
    merchant_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List pre-approvals with optional filters."""
    query = select(PreApproval).order_by(desc(PreApproval.created_at))
    if status:
        query = query.where(PreApproval.status == status)
    if outcome:
        query = query.where(PreApproval.outcome == outcome)
    if merchant_id:
        query = query.where(PreApproval.merchant_id == merchant_id)
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    items = result.scalars().all()

    return [
        {
            "id": pa.id,
            "reference_code": pa.reference_code,
            "phone": pa.phone,
            "first_name": pa.first_name,
            "last_name": pa.last_name,
            "item_description": pa.item_description,
            "price": float(pa.price),
            "financing_amount": float(pa.financing_amount) if pa.financing_amount else None,
            "outcome": pa.outcome,
            "status": pa.status,
            "merchant_name": (pa.merchant.name if pa.merchant else pa.merchant_name_manual),
            "created_at": pa.created_at.isoformat() if pa.created_at else None,
        }
        for pa in items
    ]


@router.get("/admin/analytics", response_model=PreApprovalAnalyticsResponse)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Pre-approval analytics summary."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Totals by outcome
    outcome_q = await db.execute(
        select(
            PreApproval.outcome,
            func.count(PreApproval.id),
        ).where(PreApproval.created_at >= since)
        .group_by(PreApproval.outcome)
    )
    outcome_counts = {row[0]: row[1] for row in outcome_q.all()}

    total = sum(outcome_counts.values())
    pre_approved = outcome_counts.get("pre_approved", 0)
    conditionally = outcome_counts.get("conditionally_approved", 0)
    referred = outcome_counts.get("referred", 0)
    declined = outcome_counts.get("declined", 0)

    # Converted count
    conv_q = await db.execute(
        select(func.count(PreApproval.id)).where(
            PreApproval.created_at >= since,
            PreApproval.status == "converted",
        )
    )
    converted = conv_q.scalar() or 0
    conversion_rate = (converted / total * 100) if total > 0 else 0

    # Daily volume (last N days)
    daily_q = await db.execute(
        select(
            func.date(PreApproval.created_at).label("day"),
            func.count(PreApproval.id),
        ).where(PreApproval.created_at >= since)
        .group_by(func.date(PreApproval.created_at))
        .order_by(func.date(PreApproval.created_at))
    )
    daily_volume = [{"date": str(row[0]), "count": row[1]} for row in daily_q.all()]

    # Merchant breakdown
    merchant_q = await db.execute(
        select(
            Merchant.name,
            func.count(PreApproval.id),
        ).join(Merchant, PreApproval.merchant_id == Merchant.id, isouter=True)
        .where(PreApproval.created_at >= since)
        .group_by(Merchant.name)
        .order_by(desc(func.count(PreApproval.id)))
        .limit(10)
    )
    merchant_breakdown = [
        {"merchant": row[0] or "Direct / Manual", "count": row[1]}
        for row in merchant_q.all()
    ]

    # Category breakdown
    cat_q = await db.execute(
        select(
            PreApproval.goods_category,
            func.count(PreApproval.id),
        ).where(PreApproval.created_at >= since)
        .group_by(PreApproval.goods_category)
        .order_by(desc(func.count(PreApproval.id)))
    )
    category_breakdown = [
        {"category": row[0] or "Uncategorized", "count": row[1]}
        for row in cat_q.all()
    ]

    return PreApprovalAnalyticsResponse(
        total=total,
        pre_approved=pre_approved,
        conditionally_approved=conditionally,
        referred=referred,
        declined=declined,
        converted=converted,
        conversion_rate=round(conversion_rate, 1),
        top_decline_reasons=[],
        merchant_breakdown=merchant_breakdown,
        category_breakdown=category_breakdown,
        daily_volume=daily_volume,
    )


@router.get("/admin/referred")
async def list_referred(
    limit: int = Query(50),
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List pre-approvals referred for manual review."""
    result = await db.execute(
        select(PreApproval).where(
            PreApproval.outcome == "referred",
            PreApproval.status == "active",
        ).order_by(PreApproval.created_at).limit(limit)
    )
    items = result.scalars().all()
    return [
        {
            "id": pa.id,
            "reference_code": pa.reference_code,
            "phone": pa.phone,
            "first_name": pa.first_name,
            "last_name": pa.last_name,
            "national_id": pa.national_id,
            "item_description": pa.item_description,
            "price": float(pa.price),
            "financing_amount": float(pa.financing_amount) if pa.financing_amount else None,
            "monthly_income": float(pa.monthly_income),
            "monthly_expenses": float(pa.monthly_expenses),
            "existing_loan_payments": float(pa.existing_loan_payments),
            "dti_ratio": float(pa.dti_ratio) if pa.dti_ratio else None,
            "ndi_amount": float(pa.ndi_amount) if pa.ndi_amount else None,
            "outcome_details": pa.outcome_details,
            "merchant_name": (pa.merchant.name if pa.merchant else pa.merchant_name_manual),
            "employment_status": pa.employment_status,
            "employment_tenure": pa.employment_tenure,
            "created_at": pa.created_at.isoformat() if pa.created_at else None,
        }
        for pa in items
    ]


@router.get("/admin/{ref}")
async def get_pre_approval_detail(
    ref: str,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a single pre-approval record."""
    pa = await _get_pre_approval(ref, db)
    merchant_name = pa.merchant_name_manual
    if pa.merchant and pa.merchant_id:
        merchant_name = pa.merchant.name

    return {
        "id": pa.id,
        "reference_code": pa.reference_code,
        "phone": pa.phone,
        "email": pa.email,
        "first_name": pa.first_name,
        "last_name": pa.last_name,
        "date_of_birth": str(pa.date_of_birth) if pa.date_of_birth else None,
        "national_id": pa.national_id,
        "item_description": pa.item_description,
        "goods_category": pa.goods_category,
        "price": float(pa.price),
        "currency": pa.currency,
        "downpayment": float(pa.downpayment),
        "financing_amount": float(pa.financing_amount) if pa.financing_amount else None,
        "estimated_monthly_payment": float(pa.estimated_monthly_payment) if pa.estimated_monthly_payment else None,
        "estimated_tenure_months": pa.estimated_tenure_months,
        "estimated_rate": float(pa.estimated_rate) if pa.estimated_rate else None,
        "monthly_income": float(pa.monthly_income),
        "monthly_expenses": float(pa.monthly_expenses),
        "existing_loan_payments": float(pa.existing_loan_payments),
        "income_frequency": pa.income_frequency,
        "employment_status": pa.employment_status,
        "employment_tenure": pa.employment_tenure,
        "employer_name": pa.employer_name,
        "outcome": pa.outcome,
        "outcome_details": pa.outcome_details,
        "dti_ratio": float(pa.dti_ratio) if pa.dti_ratio else None,
        "ndi_amount": float(pa.ndi_amount) if pa.ndi_amount else None,
        "status": pa.status,
        "merchant_id": pa.merchant_id,
        "merchant_name": merchant_name,
        "credit_product_name": pa.credit_product.name if pa.credit_product else None,
        "consent_given_at": pa.consent_given_at.isoformat() if pa.consent_given_at else None,
        "otp_verified_at": pa.otp_verified_at.isoformat() if pa.otp_verified_at else None,
        "expires_at": pa.expires_at.isoformat() if pa.expires_at else None,
        "linked_application_id": pa.linked_application_id,
        "created_at": pa.created_at.isoformat() if pa.created_at else None,
        "updated_at": pa.updated_at.isoformat() if pa.updated_at else None,
    }


@router.post("/admin/{ref}/decide")
async def admin_decide(
    ref: str,
    data: PreApprovalAdminDecideRequest,
    current_user: User = Depends(require_roles(*UNDERWRITER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Admin decides on a referred pre-approval."""
    pa = await _get_pre_approval(ref, db)
    if pa.outcome != "referred":
        raise HTTPException(400, "Can only decide on referred pre-approvals")

    if data.outcome not in ("pre_approved", "declined"):
        raise HTTPException(400, "Outcome must be 'pre_approved' or 'declined'")

    pa.outcome = data.outcome
    details = pa.outcome_details or {}
    details["admin_decision"] = {
        "decided_by": current_user.id,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "reason": data.reason,
    }
    pa.outcome_details = details
    await db.flush()

    return {"reference_code": ref, "outcome": pa.outcome, "message": f"Pre-approval {data.outcome}"}


# ── Helpers ───────────────────────────────────────────────────────

async def _get_pre_approval(ref: str, db: AsyncSession) -> PreApproval:
    result = await db.execute(
        select(PreApproval).where(PreApproval.reference_code == ref)
    )
    pa = result.scalar_one_or_none()
    if not pa:
        raise HTTPException(404, "Pre-approval not found")
    return pa
