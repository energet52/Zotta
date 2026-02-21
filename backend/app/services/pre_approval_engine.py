"""Pre-approval decision engine.

Lightweight eligibility check using DTI, NDI, and soft bureau data.
Does NOT perform full underwriting — gives a quick pass/refer/decline.
"""

import logging
import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pre_approval import PreApproval
from app.models.catalog import CreditProduct, Merchant
from app.services.credit_bureau.adapter import get_credit_bureau
from app.services.payment_calculator import calculate_payment
from app.services.document_requirements import get_required_documents

logger = logging.getLogger(__name__)

# ── Strategy defaults (configurable per lender) ──────────────────

STRATEGY_VERSION = "v1.0"
MAX_DTI = 0.45
MIN_NDI_TTD = 3000.0
MIN_INCOME_TTD = 3000.0
MIN_AGE = 18
MAX_AGE_AT_MATURITY = 75
MIN_EMPLOYMENT_MONTHS = 6
MAX_DELINQUENCY_DAYS = 60
WRITEOFF_LOOKBACK_MONTHS = 36
MAX_VELOCITY_PER_30_DAYS = 3
DEFAULT_EXPIRY_DAYS = 30
DEFAULT_RATE = 12.0  # fallback annual rate for estimation
DEFAULT_TENURE_MONTHS = 24
GOVERNMENT_EMPLOYEE_STATUSES = {"government_employee", "government"}


def _generate_reference() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"PA-{suffix}"


def _calculate_age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _normalise_monthly_income(income: float, frequency: str) -> float:
    """Convert stated income to monthly equivalent."""
    freq = (frequency or "monthly").lower()
    if freq == "weekly":
        return income * 52 / 12
    elif freq in ("fortnightly", "biweekly"):
        return income * 26 / 12
    elif freq in ("annual", "annually", "yearly"):
        return income / 12
    return income  # monthly


@dataclass
class PreApprovalInput:
    # Consumer
    phone: str
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    national_id: str | None = None
    email: str | None = None
    # Item
    price: float = 0
    currency: str = "TTD"
    downpayment: float = 0
    item_description: str | None = None
    goods_category: str | None = None
    merchant_id: int | None = None
    merchant_name_manual: str | None = None
    branch_id: int | None = None
    # Financial
    monthly_income: float = 0
    income_frequency: str = "monthly"
    employment_status: str = "employed_full_time"
    employment_tenure: str | None = None
    employer_name: str | None = None
    monthly_expenses: float = 0
    existing_loan_payments: float = 0
    # Photo
    photo_url: str | None = None
    photo_extraction_data: dict | None = None


@dataclass
class PreApprovalResult:
    reference_code: str
    outcome: str  # pre_approved, conditionally_approved, referred, declined
    financing_amount: float = 0
    estimated_monthly_payment: float = 0
    estimated_tenure_months: int = 0
    estimated_rate: float = 0
    credit_product_id: int | None = None
    credit_product_name: str | None = None
    dti_ratio: float = 0
    ndi_amount: float = 0
    expires_at: datetime | None = None
    message: str = ""
    reasons: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    alternative_amount: float | None = None
    alternative_payment: float | None = None
    document_checklist: list[dict] = field(default_factory=list)
    merchant_name: str | None = None
    merchant_approved: bool = False


async def run_pre_approval(
    data: PreApprovalInput,
    db: AsyncSession,
) -> PreApprovalResult:
    """Execute the pre-approval decision pipeline."""

    ref = _generate_reference()
    # Ensure unique
    for _ in range(5):
        exists = await db.execute(
            select(PreApproval.id).where(PreApproval.reference_code == ref)
        )
        if not exists.scalar():
            break
        ref = _generate_reference()

    financing_amount = max(0, data.price - data.downpayment)
    monthly_income = _normalise_monthly_income(data.monthly_income, data.income_frequency)
    age = _calculate_age(data.date_of_birth)
    decline_reasons: list[str] = []
    refer_reasons: list[str] = []
    suggestions: list[str] = []

    # ── 1. Velocity check ────────────────────────────────
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    vel_result = await db.execute(
        select(func.count(PreApproval.id)).where(
            PreApproval.phone == data.phone,
            PreApproval.created_at >= thirty_days_ago,
        )
    )
    velocity_count = vel_result.scalar() or 0
    if velocity_count >= MAX_VELOCITY_PER_30_DAYS:
        message = "You've reached the maximum number of eligibility checks for this month. Please try again later."
        reasons = ["Maximum 3 checks per 30-day period exceeded"]
        suggestions = ["Wait until next month or visit a branch for assistance"]
        expires_at = datetime.now(timezone.utc) + timedelta(days=DEFAULT_EXPIRY_DAYS)

        # Persist velocity declines too so status lookup by reference always works.
        pa = PreApproval(
            reference_code=ref,
            phone=data.phone,
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            national_id=data.national_id,
            merchant_id=data.merchant_id,
            merchant_name_manual=data.merchant_name_manual,
            branch_id=data.branch_id,
            item_description=data.item_description,
            goods_category=data.goods_category,
            price=data.price,
            currency=data.currency,
            downpayment=data.downpayment,
            monthly_income=data.monthly_income,
            income_frequency=data.income_frequency,
            employment_status=data.employment_status,
            employment_tenure=data.employment_tenure,
            employer_name=data.employer_name,
            monthly_expenses=data.monthly_expenses,
            existing_loan_payments=data.existing_loan_payments,
            financing_amount=financing_amount,
            estimated_monthly_payment=0,
            estimated_tenure_months=0,
            estimated_rate=0,
            credit_product_id=None,
            outcome="declined",
            outcome_details={
                "message": message,
                "reasons": reasons,
                "suggestions": suggestions,
                "alternative_amount": None,
                "alternative_payment": None,
                "document_checklist": [],
                "bureau_checked": False,
            },
            dti_ratio=0,
            ndi_amount=0,
            bureau_data_cached=None,
            decision_strategy_version=STRATEGY_VERSION,
            consent_given_at=datetime.now(timezone.utc),
            consent_soft_inquiry=True,
            consent_data_processing=True,
            status="active",
            expires_at=expires_at,
            photo_url=data.photo_url,
            photo_extraction_data=data.photo_extraction_data,
        )
        db.add(pa)
        await db.flush()

        return _build_result(
            ref, "declined", financing_amount, 0, 0, 0, None, None, 0, 0, message, reasons, suggestions,
        )

    # ── 2. Basic validations ─────────────────────────────
    if age is not None and age < MIN_AGE:
        decline_reasons.append(f"Must be at least {MIN_AGE} years old")

    if monthly_income < MIN_INCOME_TTD:
        decline_reasons.append("Monthly income below minimum requirement")
        suggestions.append("Consider adding a co-borrower or reapply when income increases")

    if financing_amount <= 0:
        decline_reasons.append("Financing amount must be greater than zero")

    # ── 3. Find matching credit product ──────────────────
    product = None
    product_rate = DEFAULT_RATE
    product_tenure = DEFAULT_TENURE_MONTHS
    product_name = None

    if data.merchant_id:
        prod_q = await db.execute(
            select(CreditProduct).where(
                CreditProduct.is_active == True,
                CreditProduct.lifecycle_status == "active",
            ).order_by(CreditProduct.id)
        )
        products = prod_q.scalars().all()
        for p in products:
            if (p.merchant_id == data.merchant_id or p.merchant_id is None):
                if float(p.min_amount) <= financing_amount <= float(p.max_amount):
                    product = p
                    break
        if not product:
            for p in products:
                if float(p.min_amount) <= financing_amount <= float(p.max_amount):
                    product = p
                    break
    else:
        prod_q = await db.execute(
            select(CreditProduct).where(
                CreditProduct.is_active == True,
                CreditProduct.lifecycle_status == "active",
            ).order_by(CreditProduct.id)
        )
        products = prod_q.scalars().all()
        for p in products:
            if float(p.min_amount) <= financing_amount <= float(p.max_amount):
                product = p
                break

    if product:
        product_rate = float(product.interest_rate) if product.interest_rate else DEFAULT_RATE
        product_tenure = product.max_term_months or DEFAULT_TENURE_MONTHS
        product_name = product.name
    elif financing_amount > 0:
        refer_reasons.append("No matching financing product found for this amount")

    # Check amount limits
    if product:
        if financing_amount < float(product.min_amount):
            decline_reasons.append(
                f"Amount below minimum ({product.currency if hasattr(product, 'currency') else 'TTD'} {product.min_amount:,.0f})"
            )
        if financing_amount > float(product.max_amount):
            decline_reasons.append(
                f"Amount exceeds maximum ({product.currency if hasattr(product, 'currency') else 'TTD'} {product.max_amount:,.0f})"
            )
            max_payment = calculate_payment(float(product.max_amount), product_rate, product_tenure)
            suggestions.append(
                f"Consider a smaller amount (up to TTD {product.max_amount:,.0f}) or a larger down payment"
            )

    # ── 4. Calculate payment estimate ────────────────────
    pay_info = calculate_payment(financing_amount, product_rate, product_tenure)
    est_monthly = pay_info["monthly_payment"]

    # ── 5. DTI & NDI ─────────────────────────────────────
    total_debt = float(data.monthly_expenses) + float(data.existing_loan_payments) + est_monthly
    dti = total_debt / monthly_income if monthly_income > 0 else 1.0
    ndi = monthly_income - total_debt

    if dti > MAX_DTI and not decline_reasons:
        # Check if a lower amount would pass
        max_affordable_payment = monthly_income * MAX_DTI - float(data.monthly_expenses) - float(data.existing_loan_payments)
        if max_affordable_payment > 0:
            suggestions.append(
                f"Your monthly obligations are high relative to income. Consider a smaller financing amount or larger down payment."
            )
            refer_reasons.append("Debt-to-income ratio exceeds threshold")
        else:
            decline_reasons.append("Monthly obligations too high relative to income")

    if ndi < MIN_NDI_TTD and not decline_reasons:
        refer_reasons.append("Net disposable income below minimum threshold")
        suggestions.append("Reducing existing obligations could improve eligibility")

    # ── 6. Employment tenure ─────────────────────────────
    emp_status = (data.employment_status or "").lower().replace(" ", "_")
    is_government = emp_status in GOVERNMENT_EMPLOYEE_STATUSES
    tenure_str = (data.employment_tenure or "").lower()
    tenure_months = _parse_tenure_months(tenure_str)

    if tenure_months is not None and tenure_months < MIN_EMPLOYMENT_MONTHS and not is_government:
        refer_reasons.append("Employment tenure shorter than preferred minimum")
        suggestions.append("Building a longer employment history strengthens your profile")

    # ── 7. Soft credit bureau pull ───────────────────────
    bureau_data: dict = {}
    bureau_decline = False
    bureau_refer = False

    if data.national_id and not decline_reasons:
        try:
            bureau = get_credit_bureau()
            bureau_data = await bureau.pull_soft_report(data.national_id)
        except Exception as exc:
            logger.warning("Soft bureau pull failed for %s: %s", data.national_id, exc)
            refer_reasons.append("Credit profile could not be retrieved")

    if bureau_data:
        # Check public records
        public_records = bureau_data.get("public_records") or []
        for rec in public_records:
            rec_type = (rec.get("type") or "").lower()
            status = (rec.get("status") or "").lower()
            if "bankruptcy" in rec_type and status in ("active", "filed"):
                decline_reasons.append("Active bankruptcy on credit profile")
                bureau_decline = True
            if "judgment" in rec_type and status == "active":
                decline_reasons.append("Active judgment on credit profile")
                bureau_decline = True

        # Check tradelines for delinquencies and write-offs
        tradelines = bureau_data.get("tradelines") or []
        writeoff_count = 0
        delinquent_60_plus = False
        for tl in tradelines:
            status = (tl.get("status") or "").lower()
            days_past_due = tl.get("days_past_due", 0) or 0
            if days_past_due >= MAX_DELINQUENCY_DAYS:
                delinquent_60_plus = True
            if "written_off" in status or "write_off" in status or "write-off" in status:
                writeoff_count += 1

        if writeoff_count >= 3:
            decline_reasons.append("Multiple written-off accounts on credit profile")
            bureau_decline = True
        elif writeoff_count > 0:
            refer_reasons.append("Written-off account(s) on credit profile")
            bureau_refer = True

        if delinquent_60_plus and not bureau_decline:
            refer_reasons.append("Recent delinquency of 60+ days on an existing account")
            bureau_refer = True

        # Check for thin file (no tradelines)
        if len(tradelines) == 0 and not bureau_decline:
            refer_reasons.append("Limited credit history — manual review needed")

    # ── 8. Merchant check ────────────────────────────────
    merchant_name = data.merchant_name_manual
    merchant_approved = False
    if data.merchant_id:
        m_result = await db.execute(
            select(Merchant).where(Merchant.id == data.merchant_id, Merchant.is_active == True)
        )
        merchant = m_result.scalar_one_or_none()
        if merchant:
            merchant_name = merchant.name
            merchant_approved = True

    # ── 9. Determine outcome ─────────────────────────────
    if decline_reasons:
        outcome = "declined"
        message = _decline_message(decline_reasons, suggestions)
    elif refer_reasons:
        outcome = "referred"
        message = (
            "We need a little more time to review your eligibility. "
            "This is NOT a decline — many reviewed applications are approved. "
            "A lending officer will contact you within 1 business day."
        )
    elif dti <= MAX_DTI and ndi >= MIN_NDI_TTD:
        outcome = "pre_approved"
        message = (
            f"Great news — you're pre-approved for up to TTD {financing_amount:,.0f}! "
            f"Your estimated monthly payment is TTD {est_monthly:,.0f} over {product_tenure} months."
        )
    else:
        outcome = "referred"
        message = "Your application needs a closer look. We'll be in touch shortly."

    # ── 10. Conditional approval (lower amount) ──────────
    alternative_amount = None
    alternative_payment = None
    if outcome == "declined" and "income" not in " ".join(decline_reasons).lower():
        max_pmt = monthly_income * MAX_DTI - float(data.monthly_expenses) - float(data.existing_loan_payments)
        if max_pmt > 100:
            r = product_rate / 100 / 12
            n = product_tenure
            if r > 0:
                max_principal = max_pmt * ((1 + r) ** n - 1) / (r * (1 + r) ** n)
            else:
                max_principal = max_pmt * n
            if max_principal >= 1000 and max_principal < financing_amount:
                alternative_amount = round(max_principal, -2)
                alt_pay = calculate_payment(alternative_amount, product_rate, product_tenure)
                alternative_payment = alt_pay["monthly_payment"]
                if outcome == "declined" and not bureau_decline:
                    outcome = "conditionally_approved"
                    message = (
                        f"You're pre-approved with a small adjustment! "
                        f"We can offer up to TTD {alternative_amount:,.0f} "
                        f"(estimated TTD {alternative_payment:,.0f}/month over {product_tenure} months). "
                        f"Consider a down payment of TTD {data.price - alternative_amount:,.0f} to cover the full price."
                    )

    # ── 11. Document checklist ───────────────────────────
    doc_checklist = []
    if outcome in ("pre_approved", "conditionally_approved", "referred"):
        emp_type = "self_employed" if "self" in emp_status else "employed"
        doc_checklist = get_required_documents(
            employment_type=emp_type,
            amount=financing_amount,
        )
        # Add hire-purchase specific doc
        doc_checklist.append({
            "type": "quotation",
            "label": "Quotation or proforma invoice from the merchant",
            "why": "Confirms the item and price for financing",
        })

    expires_at = datetime.now(timezone.utc) + timedelta(days=DEFAULT_EXPIRY_DAYS)

    # ── 12. Persist ──────────────────────────────────────
    pa = PreApproval(
        reference_code=ref,
        phone=data.phone,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        national_id=data.national_id,
        merchant_id=data.merchant_id,
        merchant_name_manual=data.merchant_name_manual,
        branch_id=data.branch_id,
        item_description=data.item_description,
        goods_category=data.goods_category,
        price=data.price,
        currency=data.currency,
        downpayment=data.downpayment,
        monthly_income=data.monthly_income,
        income_frequency=data.income_frequency,
        employment_status=data.employment_status,
        employment_tenure=data.employment_tenure,
        employer_name=data.employer_name,
        monthly_expenses=data.monthly_expenses,
        existing_loan_payments=data.existing_loan_payments,
        financing_amount=financing_amount,
        estimated_monthly_payment=est_monthly,
        estimated_tenure_months=product_tenure,
        estimated_rate=product_rate,
        credit_product_id=product.id if product else None,
        outcome=outcome,
        outcome_details={
            "message": message,
            "reasons": decline_reasons or refer_reasons,
            "suggestions": suggestions,
            "alternative_amount": alternative_amount,
            "alternative_payment": alternative_payment,
            "document_checklist": doc_checklist,
            "bureau_checked": bool(bureau_data),
        },
        dti_ratio=round(dti, 4),
        ndi_amount=round(ndi, 2),
        bureau_data_cached=bureau_data or None,
        decision_strategy_version=STRATEGY_VERSION,
        consent_given_at=datetime.now(timezone.utc),
        consent_soft_inquiry=True,
        consent_data_processing=True,
        status="active" if outcome != "pending" else "pending",
        expires_at=expires_at,
        photo_url=data.photo_url,
        photo_extraction_data=data.photo_extraction_data,
    )
    db.add(pa)
    await db.flush()

    return PreApprovalResult(
        reference_code=ref,
        outcome=outcome,
        financing_amount=financing_amount,
        estimated_monthly_payment=est_monthly,
        estimated_tenure_months=product_tenure,
        estimated_rate=product_rate,
        credit_product_id=product.id if product else None,
        credit_product_name=product_name,
        dti_ratio=round(dti, 4),
        ndi_amount=round(ndi, 2),
        expires_at=expires_at,
        message=message,
        reasons=decline_reasons or refer_reasons,
        suggestions=suggestions,
        alternative_amount=alternative_amount,
        alternative_payment=alternative_payment,
        document_checklist=doc_checklist,
        merchant_name=merchant_name,
        merchant_approved=merchant_approved,
    )


def _parse_tenure_months(tenure_str: str) -> int | None:
    """Parse tenure description into approximate months."""
    if not tenure_str:
        return None
    t = tenure_str.lower().strip()
    if "less than 6" in t or "<6" in t or "0-6" in t:
        return 3
    if "6-12" in t or "6 to 12" in t:
        return 9
    if "1-2" in t or "1 to 2" in t:
        return 18
    if "2-5" in t or "2 to 5" in t:
        return 42
    if "5+" in t or "5 to" in t or "over 5" in t:
        return 72
    return None


def _decline_message(reasons: list[str], suggestions: list[str]) -> str:
    """Generate consumer-friendly decline message."""
    if any("bankruptcy" in r.lower() or "judgment" in r.lower() for r in reasons):
        msg = "Your current credit profile doesn't meet our requirements for financing at this time."
    elif any("income" in r.lower() for r in reasons):
        msg = "Based on your current income and obligations, the monthly payments would be a stretch right now."
    elif any("age" in r.lower() for r in reasons):
        msg = "Unfortunately, you don't meet the age requirements for this product."
    elif any("amount" in r.lower() for r in reasons):
        msg = "The requested financing amount is outside our current product limits."
    elif any("written" in r.lower() for r in reasons):
        msg = "Your current credit profile doesn't meet our requirements at this time."
    elif any("velocity" in r.lower() or "maximum" in r.lower() for r in reasons):
        msg = "You've reached the limit for eligibility checks this month."
    else:
        msg = "We're unable to pre-approve you at this time based on the information provided."

    if suggestions:
        msg += " Here's what might help: " + "; ".join(suggestions[:3]) + "."
    return msg


def _build_result(
    ref, outcome, financing, payment, tenure, rate,
    prod_id, prod_name, dti, ndi, message, reasons, suggestions,
) -> PreApprovalResult:
    return PreApprovalResult(
        reference_code=ref,
        outcome=outcome,
        financing_amount=financing,
        estimated_monthly_payment=payment,
        estimated_tenure_months=tenure,
        estimated_rate=rate,
        credit_product_id=prod_id,
        credit_product_name=prod_name,
        dti_ratio=dti,
        ndi_amount=ndi,
        message=message,
        reasons=reasons,
        suggestions=suggestions,
    )
