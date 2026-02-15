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
from app.services.error_logger import log_error
import logging

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


# ── Consumer loan dashboard summary ──────────────────────────────────────

@router.get("/summary/my-loans")
async def get_my_loans_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a summary of all disbursed loans for the current consumer,
    including next payment, remaining balance, and arrears info."""
    try:
        today = date.today()

        # Get all disbursed applications for this user
        apps_result = await db.execute(
            select(LoanApplication).where(
                LoanApplication.applicant_id == current_user.id,
                LoanApplication.status == LoanStatus.DISBURSED,
            )
        )
        apps = apps_result.scalars().all()

        if not apps:
            return {"loans": []}

        summaries = []
        for app in apps:
            # Fetch schedule for this application
            sched_result = await db.execute(
                select(PaymentSchedule)
                .where(PaymentSchedule.loan_application_id == app.id)
                .order_by(PaymentSchedule.installment_number)
            )
            schedules = sched_result.scalars().all()

            total_due = sum(float(s.amount_due) for s in schedules)
            total_paid = sum(float(s.amount_paid) for s in schedules)
            remaining_balance = round(total_due - total_paid, 2)

            # Next unpaid installment
            next_payment = None
            for s in schedules:
                if s.status != ScheduleStatus.PAID:
                    next_payment = {
                        "due_date": s.due_date.isoformat(),
                        "amount_due": round(float(s.amount_due) - float(s.amount_paid), 2),
                        "installment_number": s.installment_number,
                    }
                    break

            # Overdue installments (due_date < today and not fully paid)
            overdue_items = [
                s for s in schedules
                if s.due_date < today and s.status != ScheduleStatus.PAID
            ]
            overdue_amount = round(
                sum(float(s.amount_due) - float(s.amount_paid) for s in overdue_items), 2
            )
            days_past_due = 0
            if overdue_items:
                earliest_overdue = min(s.due_date for s in overdue_items)
                days_past_due = (today - earliest_overdue).days

            total_installments = len(schedules)
            paid_installments = sum(1 for s in schedules if s.status == ScheduleStatus.PAID)

            summaries.append({
                "application_id": app.id,
                "reference_number": app.reference_number,
                "loan_amount": float(app.amount_approved or app.proposed_amount or app.amount_requested),
                "monthly_payment": float(app.monthly_payment or 0),
                "interest_rate": float(app.interest_rate or app.proposed_rate or 0),
                "term_months": app.proposed_term or app.term_months,
                "remaining_balance": remaining_balance,
                "total_paid": round(total_paid, 2),
                "total_installments": total_installments,
                "paid_installments": paid_installments,
                "next_payment": next_payment,
                "overdue_amount": overdue_amount,
                "days_past_due": days_past_due,
                "in_arrears": overdue_amount > 0,
            })

        return {"loans": summaries}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.payments", function_name="get_my_loans_summary")
        raise


@router.post("/{application_id}/record", response_model=PaymentResponse)
async def record_payment(
    application_id: int,
    data: PaymentCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Staff records a manual payment for a loan."""
    try:
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

        # ── Post to General Ledger ──────────────────────
        try:
            from app.services.gl.mapping_engine import generate_journal_entry
            from app.models.gl import JournalSourceType
            from decimal import Decimal as _Decimal

            await generate_journal_entry(
                db,
                event_type=JournalSourceType.REPAYMENT,
                source_reference=f"PAY-{ref}",
                amount_breakdown={
                    "principal": _Decimal(str(data.amount)),
                    "full_amount": _Decimal(str(data.amount)),
                },
                product_id=getattr(app, "credit_product_id", None),
                description=f"Payment recorded for loan #{application_id} — {ref}",
                created_by=current_user.id,
                loan_reference=f"LOAN-{application_id}",
                auto_post=True,
            )
        except Exception:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "GL posting for payment %s failed (no mapping template?)", ref, exc_info=True
            )

        return payment
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.payments", function_name="record_payment")
        raise


async def _can_access_application(db: AsyncSession, application_id: int, user: User) -> bool:
    """Staff can access any application; applicants only their own."""
    if user.role in (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER):
        return True
    app_result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.id == application_id,
            LoanApplication.applicant_id == user.id,
        )
    )
    return app_result.scalar_one_or_none() is not None


@router.get("/{application_id}/history", response_model=list[PaymentResponse])
async def get_payment_history(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payment history for an application."""
    try:
        if not await _can_access_application(db, application_id, current_user):
            raise HTTPException(status_code=404, detail="Application not found")
        result = await db.execute(
            select(Payment)
            .where(Payment.loan_application_id == application_id)
            .order_by(Payment.payment_date.desc())
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.payments", function_name="get_payment_history")
        raise


@router.get("/{application_id}/schedule", response_model=list[PaymentScheduleResponse])
async def get_payment_schedule(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payment schedule for an application."""
    try:
        if not await _can_access_application(db, application_id, current_user):
            raise HTTPException(status_code=404, detail="Application not found")
        result = await db.execute(
            select(PaymentSchedule)
            .where(PaymentSchedule.loan_application_id == application_id)
            .order_by(PaymentSchedule.installment_number)
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.payments", function_name="get_payment_schedule")
        raise


@router.post("/{application_id}/pay-online", response_model=PaymentResponse)
async def pay_online(
    application_id: int,
    data: OnlinePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumer makes an online payment (simulated)."""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.payments", function_name="pay_online")
        raise


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
