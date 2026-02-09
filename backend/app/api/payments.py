"""Payment endpoints for recording and managing loan payments."""

import random
import string
from datetime import datetime, date, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentSchedule, ScheduleStatus
from app.models.audit import AuditLog
from app.schemas import (
    PaymentCreate,
    PaymentResponse,
    PaymentScheduleResponse,
    OnlinePaymentRequest,
)
from app.auth_utils import get_current_user, require_roles

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


def generate_payment_schedule(
    application_id: int,
    principal: float,
    annual_rate: float,
    term_months: int,
    start_date: date,
) -> list[PaymentSchedule]:
    """Generate amortization schedule records."""
    schedules = []
    monthly_rate = annual_rate / 100 / 12
    if monthly_rate > 0:
        pmt = principal * (monthly_rate * (1 + monthly_rate) ** term_months) / (
            (1 + monthly_rate) ** term_months - 1
        )
    else:
        pmt = principal / term_months

    balance = principal
    for i in range(1, term_months + 1):
        interest = round(balance * monthly_rate, 2)
        principal_part = round(pmt - interest, 2)
        if i == term_months:
            principal_part = round(balance, 2)
        balance -= principal_part
        due = start_date + timedelta(days=30 * i)

        schedules.append(PaymentSchedule(
            loan_application_id=application_id,
            installment_number=i,
            due_date=due,
            principal=principal_part,
            interest=interest,
            amount_due=round(principal_part + interest, 2),
            amount_paid=0,
            status=ScheduleStatus.UPCOMING,
        ))
    return schedules


@router.post("/{application_id}/record", response_model=PaymentResponse)
async def record_payment(
    application_id: int,
    data: PaymentCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Staff records a manual payment for a loan."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    ref = data.reference_number or f"PAY-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

    payment = Payment(
        loan_application_id=application_id,
        amount=data.amount,
        payment_type=PaymentType(data.payment_type),
        payment_date=data.payment_date,
        reference_number=ref,
        recorded_by=current_user.id,
        status=PaymentStatus.COMPLETED,
        notes=data.notes,
    )
    db.add(payment)

    # Update payment schedule if exists
    await _apply_payment_to_schedule(db, application_id, data.amount)

    # Audit
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="payment_recorded",
        user_id=current_user.id,
        new_values={"amount": float(data.amount), "type": data.payment_type, "ref": ref},
    )
    db.add(audit)
    await db.flush()
    await db.refresh(payment)
    return payment


@router.get("/{application_id}/history", response_model=list[PaymentResponse])
async def get_payment_history(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payment history for an application."""
    result = await db.execute(
        select(Payment)
        .where(Payment.loan_application_id == application_id)
        .order_by(Payment.payment_date.desc())
    )
    return result.scalars().all()


@router.get("/{application_id}/schedule", response_model=list[PaymentScheduleResponse])
async def get_payment_schedule(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payment schedule for an application."""
    result = await db.execute(
        select(PaymentSchedule)
        .where(PaymentSchedule.loan_application_id == application_id)
        .order_by(PaymentSchedule.installment_number)
    )
    return result.scalars().all()


@router.post("/{application_id}/pay-online", response_model=PaymentResponse)
async def pay_online(
    application_id: int,
    data: OnlinePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumer makes an online payment (simulated)."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == current_user.id,
            LoanApplication.status == LoanStatus.DISBURSED,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not disbursed")

    ref = f"ONL-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
    payment = Payment(
        loan_application_id=application_id,
        amount=data.amount,
        payment_type=PaymentType.ONLINE,
        payment_date=date.today(),
        reference_number=ref,
        recorded_by=current_user.id,
        status=PaymentStatus.COMPLETED,
        notes="Online payment via consumer portal",
    )
    db.add(payment)

    await _apply_payment_to_schedule(db, application_id, data.amount)

    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="online_payment",
        user_id=current_user.id,
        new_values={"amount": float(data.amount), "ref": ref},
    )
    db.add(audit)
    await db.flush()
    await db.refresh(payment)
    return payment


async def _apply_payment_to_schedule(db: AsyncSession, app_id: int, amount: float):
    """Apply a payment amount to the oldest unpaid schedule entries."""
    result = await db.execute(
        select(PaymentSchedule)
        .where(
            PaymentSchedule.loan_application_id == app_id,
            PaymentSchedule.status.in_([ScheduleStatus.UPCOMING, ScheduleStatus.DUE, ScheduleStatus.OVERDUE, ScheduleStatus.PARTIAL]),
        )
        .order_by(PaymentSchedule.installment_number)
    )
    schedules = result.scalars().all()
    remaining = amount
    for sched in schedules:
        if remaining <= 0:
            break
        owed = float(sched.amount_due) - float(sched.amount_paid)
        if owed <= 0:
            continue
        pay_amount = min(remaining, owed)
        sched.amount_paid = float(sched.amount_paid) + pay_amount
        remaining -= pay_amount
        if float(sched.amount_paid) >= float(sched.amount_due) - 0.01:
            sched.status = ScheduleStatus.PAID
            sched.paid_at = datetime.now(timezone.utc)
        else:
            sched.status = ScheduleStatus.PARTIAL
