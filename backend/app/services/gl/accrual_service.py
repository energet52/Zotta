"""Accrual batch processing service.

Handles automated batch operations for:
- Interest accrual across all active loans
- Loan loss provisioning based on aging/risk classification
- Fee assessment batches

Each batch creates a single consolidated journal entry with
individual lines per loan.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import (
    AccrualBatch,
    AccrualBatchType,
    AccrualBatchStatus,
    AccountingPeriod,
    JournalSourceType,
    GLAccount,
)
from app.services.gl.journal_engine import create_journal_entry
from app.services.gl.coa_service import get_account_by_code

logger = logging.getLogger(__name__)


class AccrualError(Exception):
    """Accrual processing error."""


async def run_interest_accrual(
    db: AsyncSession,
    period_id: int,
    *,
    user_id: int | None = None,
) -> AccrualBatch:
    """Process interest accrual for all active loans in a period.

    Creates a single journal entry:
    - DR: Interest Receivable (1-3001)
    - CR: Interest Income (4-1000)

    Each loan gets its own line pair.
    """
    from app.models.loan import LoanApplication

    # Get period
    period_result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise AccrualError(f"Period {period_id} not found")

    # Create batch record
    batch = AccrualBatch(
        batch_type=AccrualBatchType.INTEREST_ACCRUAL,
        period_id=period_id,
        status=AccrualBatchStatus.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    await db.flush()

    try:
        # Get active loans (disbursed status)
        loans_result = await db.execute(
            select(LoanApplication).where(
                LoanApplication.status == "disbursed"
            )
        )
        active_loans = list(loans_result.scalars().all())

        if not active_loans:
            batch.status = AccrualBatchStatus.COMPLETED
            batch.loan_count = 0
            batch.total_amount = Decimal("0")
            batch.completed_at = datetime.now(timezone.utc)
            await db.flush()
            return batch

        # Get accounts
        interest_receivable = await get_account_by_code(db, "1-3001")
        interest_income = await get_account_by_code(db, "4-1000")

        if not interest_receivable or not interest_income:
            raise AccrualError(
                "Required accounts not found: 1-3001 (Interest Receivable) "
                "or 4-1000 (Interest Income)"
            )

        # Calculate accrued interest per loan
        lines = []
        total_interest = Decimal("0")
        loan_count = 0

        for loan in active_loans:
            # Daily interest = (principal * annual_rate) / 365
            # Monthly accrual = daily * days_in_period
            rate = Decimal(str(getattr(loan, "approved_rate", 0) or 0)) / 100
            principal = Decimal(str(getattr(loan, "approved_amount", 0) or 0))

            if rate <= 0 or principal <= 0:
                continue

            days_in_period = (period.end_date - period.start_date).days + 1
            daily_interest = (principal * rate) / 365
            accrued = (daily_interest * days_in_period).quantize(Decimal("0.01"))

            if accrued <= 0:
                continue

            loan_ref = f"LOAN-{loan.id}"

            # DR Interest Receivable
            lines.append({
                "gl_account_id": interest_receivable.id,
                "debit_amount": float(accrued),
                "credit_amount": 0.0,
                "description": f"Interest accrual for {loan_ref}",
                "loan_reference": loan_ref,
            })
            # CR Interest Income
            lines.append({
                "gl_account_id": interest_income.id,
                "debit_amount": 0.0,
                "credit_amount": float(accrued),
                "description": f"Interest income accrual for {loan_ref}",
                "loan_reference": loan_ref,
            })

            total_interest += accrued
            loan_count += 1

        if not lines:
            batch.status = AccrualBatchStatus.COMPLETED
            batch.loan_count = 0
            batch.total_amount = Decimal("0")
            batch.completed_at = datetime.now(timezone.utc)
            await db.flush()
            return batch

        # Create single consolidated journal entry
        entry = await create_journal_entry(
            db,
            lines=lines,
            source_type=JournalSourceType.INTEREST_ACCRUAL,
            source_reference=f"ACCRUAL-BATCH-{batch.id}",
            description=f"Interest accrual for {period.name} ({loan_count} loans)",
            effective_date=period.end_date,
            created_by=user_id,
            auto_post=True,
            narrative=(
                f"Automated interest accrual batch for {period.name}. "
                f"Processed {loan_count} active loans with total accrued interest "
                f"of ${float(total_interest):,.2f}."
            ),
        )

        batch.status = AccrualBatchStatus.COMPLETED
        batch.loan_count = loan_count
        batch.total_amount = total_interest
        batch.journal_entry_id = entry.id
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info(
            "Interest accrual batch %d completed: %d loans, total %s",
            batch.id, loan_count, total_interest,
        )

    except Exception as e:
        batch.status = AccrualBatchStatus.FAILED
        batch.error_log = str(e)
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()
        logger.error("Interest accrual batch %d failed: %s", batch.id, e)
        raise

    return batch


async def run_provisioning(
    db: AsyncSession,
    period_id: int,
    *,
    user_id: int | None = None,
) -> AccrualBatch:
    """Run loan loss provisioning based on aging classification.

    Provision rates:
    - Current (0 DPD): 1%
    - Watch (1-30 DPD): 5%
    - Substandard (31-60 DPD): 20%
    - Doubtful (61-90 DPD): 50%
    - Loss (90+ DPD): 100%

    Creates a journal entry:
    - DR: Provision Expense (5-1000)
    - CR: Allowance for Loan Losses (2-2000)
    """
    from app.models.loan import LoanApplication

    period_result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise AccrualError(f"Period {period_id} not found")

    batch = AccrualBatch(
        batch_type=AccrualBatchType.PROVISION,
        period_id=period_id,
        status=AccrualBatchStatus.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    await db.flush()

    try:
        # Get accounts
        provision_expense = await get_account_by_code(db, "5-1000")
        allowance = await get_account_by_code(db, "2-2000")

        if not provision_expense or not allowance:
            raise AccrualError(
                "Required accounts not found: 5-1000 or 2-2000"
            )

        # Get active loans
        loans_result = await db.execute(
            select(LoanApplication).where(
                LoanApplication.status.in_(["disbursed", "delinquent", "default"])
            )
        )
        active_loans = list(loans_result.scalars().all())

        lines = []
        total_provision = Decimal("0")
        loan_count = 0

        provision_rates = {
            (0, 0): Decimal("0.01"),      # Current
            (1, 30): Decimal("0.05"),      # Watch
            (31, 60): Decimal("0.20"),     # Substandard
            (61, 90): Decimal("0.50"),     # Doubtful
            (91, 99999): Decimal("1.00"),  # Loss
        }

        for loan in active_loans:
            principal = Decimal(str(getattr(loan, "approved_amount", 0) or 0))
            dpd = getattr(loan, "days_past_due", 0) or 0

            if principal <= 0:
                continue

            rate = Decimal("0.01")
            for (low, high), r in provision_rates.items():
                if low <= dpd <= high:
                    rate = r
                    break

            provision_amount = (principal * rate).quantize(Decimal("0.01"))
            if provision_amount <= 0:
                continue

            loan_ref = f"LOAN-{loan.id}"

            lines.append({
                "gl_account_id": provision_expense.id,
                "debit_amount": float(provision_amount),
                "credit_amount": 0.0,
                "description": f"Provision for {loan_ref} ({dpd} DPD, {float(rate)*100:.0f}%)",
                "loan_reference": loan_ref,
            })
            lines.append({
                "gl_account_id": allowance.id,
                "debit_amount": 0.0,
                "credit_amount": float(provision_amount),
                "description": f"Allowance for {loan_ref}",
                "loan_reference": loan_ref,
            })

            total_provision += provision_amount
            loan_count += 1

        if not lines:
            batch.status = AccrualBatchStatus.COMPLETED
            batch.loan_count = 0
            batch.total_amount = Decimal("0")
            batch.completed_at = datetime.now(timezone.utc)
            await db.flush()
            return batch

        entry = await create_journal_entry(
            db,
            lines=lines,
            source_type=JournalSourceType.PROVISION,
            source_reference=f"PROVISION-BATCH-{batch.id}",
            description=f"Loan loss provisioning for {period.name} ({loan_count} loans)",
            effective_date=period.end_date,
            created_by=user_id,
            auto_post=True,
            narrative=(
                f"Automated provisioning batch for {period.name}. "
                f"Assessed {loan_count} loans with total provision of "
                f"${float(total_provision):,.2f}."
            ),
        )

        batch.status = AccrualBatchStatus.COMPLETED
        batch.loan_count = loan_count
        batch.total_amount = total_provision
        batch.journal_entry_id = entry.id
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info(
            "Provisioning batch %d completed: %d loans, total %s",
            batch.id, loan_count, total_provision,
        )

    except Exception as e:
        batch.status = AccrualBatchStatus.FAILED
        batch.error_log = str(e)
        batch.completed_at = datetime.now(timezone.utc)
        await db.flush()
        logger.error("Provisioning batch %d failed: %s", batch.id, e)
        raise

    return batch
