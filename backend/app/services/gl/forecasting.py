"""Predictive analytics for the General Ledger.

Provides:
- Cash flow forecast based on scheduled repayments and expected disbursements
- Revenue forecast projecting interest income from active loans
- Account balance forecast using simple time-series projection
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import (
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    GLAccount,
    AccountingPeriod,
)
from app.services.gl.coa_service import get_account_balance, get_account_by_code

logger = logging.getLogger(__name__)


async def cash_flow_forecast(
    db: AsyncSession,
    *,
    months_ahead: int = 6,
) -> list[dict]:
    """Forecast cash flows for the next N months.

    Aggregates:
    - Expected repayments from payment schedules
    - Projected disbursements (based on pipeline)
    - Projected interest income
    """
    from app.models.payment import PaymentSchedule, ScheduleStatus

    today = date.today()
    forecasts = []

    # Statuses representing unpaid scheduled installments
    unpaid_statuses = [
        ScheduleStatus.UPCOMING,
        ScheduleStatus.DUE,
        ScheduleStatus.OVERDUE,
        ScheduleStatus.PARTIAL,
    ]

    for i in range(months_ahead):
        month_start = date(
            today.year + (today.month + i - 1) // 12,
            (today.month + i - 1) % 12 + 1,
            1,
        )
        if month_start.month == 12:
            month_end = date(month_start.year, 12, 31)
        else:
            month_end = date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)

        # Expected repayments from schedule (unpaid instalments due in this month)
        try:
            sched_result = await db.execute(
                select(sa_func.coalesce(sa_func.sum(PaymentSchedule.amount_due), 0))
                .where(
                    PaymentSchedule.due_date >= month_start,
                    PaymentSchedule.due_date <= month_end,
                    PaymentSchedule.status.in_(unpaid_statuses),
                )
            )
            expected_inflow = float(sched_result.scalar() or 0)
        except Exception:
            expected_inflow = 0.0

        # Historical average disbursements for this month (simple average)
        try:
            hist_result = await db.execute(
                select(sa_func.coalesce(sa_func.avg(JournalEntryLine.debit_amount), 0))
                .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
                .join(GLAccount, JournalEntryLine.gl_account_id == GLAccount.id)
                .where(
                    GLAccount.account_code == "1-2001",
                    JournalEntry.status == JournalEntryStatus.POSTED,
                    JournalEntryLine.debit_amount > 0,
                )
            )
            avg_disbursement = float(hist_result.scalar() or 0)
        except Exception:
            avg_disbursement = 0.0

        forecasts.append({
            "month": month_start.strftime("%B %Y"),
            "month_start": str(month_start),
            "month_end": str(month_end),
            "expected_inflow": round(expected_inflow, 2),
            "expected_outflow": round(avg_disbursement, 2),
            "net_cash_flow": round(expected_inflow - avg_disbursement, 2),
        })

    return forecasts


async def revenue_forecast(
    db: AsyncSession,
    *,
    months_ahead: int = 6,
) -> list[dict]:
    """Project interest income from active loans."""
    from app.models.loan import LoanApplication

    # Get active loans
    loans_result = await db.execute(
        select(LoanApplication).where(LoanApplication.status == "disbursed")
    )
    active_loans = list(loans_result.scalars().all())

    # Calculate monthly interest for all active loans
    monthly_interest = Decimal("0")
    for loan in active_loans:
        rate = Decimal(str(getattr(loan, "interest_rate", 0) or 0)) / 100
        principal = Decimal(str(getattr(loan, "amount_approved", 0) or 0))
        if rate > 0 and principal > 0:
            monthly_interest += (principal * rate / 12).quantize(Decimal("0.01"))

    today = date.today()
    forecasts = []
    # Assume gradual decline as loans are repaid (simple linear decay)
    for i in range(months_ahead):
        month_start = date(
            today.year + (today.month + i - 1) // 12,
            (today.month + i - 1) % 12 + 1,
            1,
        )
        # Simple decay: assume 2% of portfolio repaid per month
        decay_factor = Decimal(str(max(0.5, 1 - (i * 0.02))))
        projected = (monthly_interest * decay_factor).quantize(Decimal("0.01"))

        forecasts.append({
            "month": month_start.strftime("%B %Y"),
            "projected_interest_income": float(projected),
            "active_loan_count": len(active_loans),
            "confidence": round(max(0.5, 1 - (i * 0.08)), 2),
        })

    return forecasts


async def account_balance_forecast(
    db: AsyncSession,
    account_id: int,
    *,
    months_ahead: int = 6,
) -> list[dict]:
    """Simple time-series projection for an account balance.

    Uses historical monthly changes to project forward with
    confidence intervals.
    """
    from app.models.gl import AccountType

    # Get historical monthly balances (last 12 months)
    today = date.today()
    monthly_changes = []

    for i in range(12, 0, -1):
        month_date = date(
            today.year - (i // 12),
            today.month - (i % 12) if today.month > (i % 12) else 12 - ((i % 12) - today.month),
            1,
        )
        try:
            bal = await get_account_balance(db, account_id, as_of_date=month_date)
            monthly_changes.append(bal["balance"])
        except Exception:
            continue

    if len(monthly_changes) < 2:
        # Not enough data — return flat projection
        current_bal = await get_account_balance(db, account_id)
        return [{
            "month": (today + timedelta(days=30 * i)).strftime("%B %Y"),
            "projected_balance": current_bal["balance"],
            "confidence_low": current_bal["balance"] * 0.9,
            "confidence_high": current_bal["balance"] * 1.1,
            "confidence": 0.5,
        } for i in range(1, months_ahead + 1)]

    # Calculate average monthly change
    changes = [monthly_changes[i] - monthly_changes[i - 1] for i in range(1, len(monthly_changes))]
    import statistics
    avg_change = statistics.mean(changes) if changes else 0
    stdev = statistics.stdev(changes) if len(changes) > 1 else abs(avg_change * 0.2)

    current = monthly_changes[-1] if monthly_changes else 0
    forecasts = []

    for i in range(1, months_ahead + 1):
        projected = current + (avg_change * i)
        conf = max(0.3, 1 - (i * 0.1))
        margin = stdev * i * 1.5

        forecasts.append({
            "month": (today + timedelta(days=30 * i)).strftime("%B %Y"),
            "projected_balance": round(projected, 2),
            "confidence_low": round(projected - margin, 2),
            "confidence_high": round(projected + margin, 2),
            "confidence": round(conf, 2),
        })

    return forecasts
