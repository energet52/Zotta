"""Consumer-facing catalog endpoints for hire-purchase flow."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.catalog import Merchant, Branch, ProductCategory, CreditProduct, ProductFee
from app.schemas import (
    MerchantResponse,
    BranchResponse,
    ProductCategoryResponse,
    CreditProductResponse,
    PaymentCalculationRequest,
    PaymentCalculationResponse,
    FeeBreakdownEntry,
    PaymentCalendarEntry,
    ProductScoreRangeResponse,
    ProductFeeResponse,
)

router = APIRouter()


def _product_to_response(product: CreditProduct) -> CreditProductResponse:
    return CreditProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        merchant_id=product.merchant_id,
        merchant_name=product.merchant.name if product.merchant else None,
        min_term_months=product.min_term_months,
        max_term_months=product.max_term_months,
        min_amount=float(product.min_amount),
        max_amount=float(product.max_amount),
        repayment_scheme=product.repayment_scheme,
        grace_period_days=product.grace_period_days,
        is_active=product.is_active,
        score_ranges=[ProductScoreRangeResponse.model_validate(sr) for sr in product.score_ranges],
        fees=[ProductFeeResponse.model_validate(fee) for fee in product.fees],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/merchants", response_model=list[MerchantResponse])
async def list_merchants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Merchant).where(Merchant.is_active == True).order_by(Merchant.name)
    )
    return result.scalars().all()


@router.get("/merchants/{merchant_id}/branches", response_model=list[BranchResponse])
async def list_branches(
    merchant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Branch)
        .where(Branch.merchant_id == merchant_id, Branch.is_active == True)
        .order_by(Branch.is_online.desc(), Branch.name)
    )
    branches = result.scalars().all()
    if not branches:
        raise HTTPException(status_code=404, detail="No branches found for merchant")
    return branches


@router.get("/merchants/{merchant_id}/categories", response_model=list[ProductCategoryResponse])
async def list_categories(
    merchant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductCategory).where(ProductCategory.merchant_id == merchant_id).order_by(ProductCategory.name)
    )
    return result.scalars().all()


@router.get("/products", response_model=list[CreditProductResponse])
async def list_products(
    merchant_id: int,
    amount: float,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CreditProduct)
        .where(
            CreditProduct.is_active == True,
            CreditProduct.min_amount <= amount,
            CreditProduct.max_amount >= amount,
            or_(CreditProduct.merchant_id == None, CreditProduct.merchant_id == merchant_id),
        )
        .options(
            selectinload(CreditProduct.merchant),
            selectinload(CreditProduct.score_ranges),
            selectinload(CreditProduct.fees),
        )
        .order_by(CreditProduct.name)
    )
    return [_product_to_response(p) for p in result.scalars().unique().all()]


def _calculate_fee_amount(fee: ProductFee, purchase_amount: Decimal, financed_amount: Decimal) -> Decimal:
    fee_value = Decimal(fee.fee_amount)
    if fee.fee_base == "purchase_amount":
        base = purchase_amount
    elif fee.fee_base == "financed_amount":
        base = financed_amount
    else:
        base = Decimal("1")

    if fee.fee_type.endswith("_pct"):
        return (base * fee_value).quantize(Decimal("0.01"))
    return fee_value.quantize(Decimal("0.01"))


@router.post("/calculate", response_model=PaymentCalculationResponse)
async def calculate_payment(
    payload: PaymentCalculationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CreditProduct)
        .where(CreditProduct.id == payload.product_id, CreditProduct.is_active == True)
        .options(selectinload(CreditProduct.fees))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Credit product not found")

    if payload.term_months < product.min_term_months or payload.term_months > product.max_term_months:
        raise HTTPException(status_code=400, detail="Selected term is outside product limits")

    purchase_amount = Decimal(str(payload.total_amount))
    downpayment = Decimal("0.00")
    financed_amount = (purchase_amount - downpayment).quantize(Decimal("0.01"))

    fee_entries: list[FeeBreakdownEntry] = []
    upfront_fees = Decimal("0.00")
    monthly_fees = Decimal("0.00")
    for fee in product.fees:
        if not fee.is_available:
            continue
        amount = _calculate_fee_amount(fee, purchase_amount, financed_amount)
        fee_entries.append(
            FeeBreakdownEntry(
                fee_type=fee.fee_type,
                fee_base=fee.fee_base,
                fee_amount=float(amount),
            )
        )
        if fee.fee_type in {"origination_fee_flat", "origination_fee_pct", "admin_fee_pct"}:
            upfront_fees += amount
        else:
            monthly_fees += amount

    total_financed = (financed_amount + monthly_fees).quantize(Decimal("0.01"))

    # Flat APR estimate for plan preview. This can be replaced by product-specific APR later.
    annual_rate = Decimal("0.12")
    monthly_rate = annual_rate / Decimal("12")
    n = Decimal(payload.term_months)
    if monthly_rate > 0:
        monthly_payment = total_financed * (monthly_rate * (1 + monthly_rate) ** n) / (
            ((1 + monthly_rate) ** n) - 1
        )
    else:
        monthly_payment = total_financed / n
    monthly_payment = monthly_payment.quantize(Decimal("0.01"))

    remaining = total_financed
    calendar: list[PaymentCalendarEntry] = []
    for i in range(1, payload.term_months + 1):
        interest = (remaining * monthly_rate).quantize(Decimal("0.01"))
        principal = (monthly_payment - interest).quantize(Decimal("0.01"))
        if i == payload.term_months:
            principal = remaining
            amount_due = (principal + interest).quantize(Decimal("0.01"))
        else:
            amount_due = monthly_payment
        remaining = (remaining - principal).quantize(Decimal("0.01"))
        due_month = ((date.today().month - 1 + i) % 12) + 1
        due_year = date.today().year + ((date.today().month - 1 + i) // 12)
        due_date = date(due_year, due_month, min(date.today().day, 28))
        calendar.append(
            PaymentCalendarEntry(
                installment_number=i,
                due_date=due_date,
                principal=float(principal),
                interest=float(interest),
                fees=0.0,
                amount_due=float(amount_due),
            )
        )

    return PaymentCalculationResponse(
        product_id=product.id,
        total_amount=float(purchase_amount),
        total_financed=float(total_financed),
        downpayment=float(downpayment),
        fees_due_upfront=float(upfront_fees.quantize(Decimal("0.01"))),
        term_months=payload.term_months,
        monthly_payment=float(monthly_payment),
        fees_breakdown=fee_entries,
        payment_calendar=calendar,
    )
