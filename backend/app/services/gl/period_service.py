"""Accounting period management service.

Manages fiscal years and monthly accounting periods with status transitions:
  OPEN → SOFT_CLOSE → CLOSED → LOCKED

Includes year-end closing entry generation (close Revenue/Expense accounts
into Retained Earnings).
"""

import calendar
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import (
    AccountingPeriod,
    PeriodStatus,
    GLAccount,
    AccountCategory,
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    JournalSourceType,
)

logger = logging.getLogger(__name__)


class PeriodError(Exception):
    """Accounting period error."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def list_periods(
    db: AsyncSession,
    *,
    fiscal_year: int | None = None,
    status: PeriodStatus | None = None,
) -> list[AccountingPeriod]:
    q = select(AccountingPeriod).order_by(
        AccountingPeriod.fiscal_year, AccountingPeriod.period_number
    )
    if fiscal_year:
        q = q.where(AccountingPeriod.fiscal_year == fiscal_year)
    if status:
        q = q.where(AccountingPeriod.status == status)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_period(db: AsyncSession, period_id: int) -> AccountingPeriod | None:
    result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id)
    )
    return result.scalar_one_or_none()


async def create_fiscal_year(
    db: AsyncSession, year: int
) -> list[AccountingPeriod]:
    """Create 12 monthly accounting periods for *year*.

    All periods are created in OPEN status.
    """
    # Check if periods already exist
    existing = await list_periods(db, fiscal_year=year)
    if existing:
        raise PeriodError(f"Fiscal year {year} already has {len(existing)} periods")

    periods = []
    for month in range(1, 13):
        _, last_day = calendar.monthrange(year, month)
        period = AccountingPeriod(
            fiscal_year=year,
            period_number=month,
            name=f"{calendar.month_name[month]} {year}",
            start_date=date(year, month, 1),
            end_date=date(year, month, last_day),
            status=PeriodStatus.OPEN,
        )
        db.add(period)
        periods.append(period)

    await db.flush()
    for p in periods:
        await db.refresh(p)
    logger.info("Created fiscal year %d with 12 periods", year)
    return periods


async def soft_close_period(
    db: AsyncSession, period_id: int, user_id: int
) -> AccountingPeriod:
    """OPEN → SOFT_CLOSE.  Warns on further postings."""
    period = await get_period(db, period_id)
    if period is None:
        raise PeriodError(f"Period {period_id} not found")
    if period.status != PeriodStatus.OPEN:
        raise PeriodError(
            f"Cannot soft-close: period is {period.status.value}, expected OPEN"
        )
    period.status = PeriodStatus.SOFT_CLOSE
    await db.flush()
    logger.info("Soft-closed period %s", period.name)
    return period


async def close_period(
    db: AsyncSession, period_id: int, user_id: int
) -> AccountingPeriod:
    """OPEN or SOFT_CLOSE → CLOSED.  No further postings allowed."""
    period = await get_period(db, period_id)
    if period is None:
        raise PeriodError(f"Period {period_id} not found")
    if period.status not in (PeriodStatus.OPEN, PeriodStatus.SOFT_CLOSE):
        raise PeriodError(
            f"Cannot close: period is {period.status.value}"
        )

    # Check for unresolved draft/pending entries in this period
    result = await db.execute(
        select(sa_func.count(JournalEntry.id))
        .where(
            JournalEntry.accounting_period_id == period_id,
            JournalEntry.status.in_([
                JournalEntryStatus.DRAFT,
                JournalEntryStatus.PENDING_APPROVAL,
                JournalEntryStatus.APPROVED,
            ]),
        )
    )
    pending_count = result.scalar() or 0
    if pending_count > 0:
        raise PeriodError(
            f"Cannot close: {pending_count} unposted journal entries in this period"
        )

    period.status = PeriodStatus.CLOSED
    period.closed_by = user_id
    period.closed_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Closed period %s by user %d", period.name, user_id)
    return period


async def lock_period(
    db: AsyncSession, period_id: int, user_id: int
) -> AccountingPeriod:
    """CLOSED → LOCKED.  Year-end lock; irreversible without admin override."""
    period = await get_period(db, period_id)
    if period is None:
        raise PeriodError(f"Period {period_id} not found")
    if period.status != PeriodStatus.CLOSED:
        raise PeriodError(
            f"Cannot lock: period is {period.status.value}, expected CLOSED"
        )
    period.status = PeriodStatus.LOCKED
    await db.flush()
    logger.info("Locked period %s", period.name)
    return period


async def reopen_period(
    db: AsyncSession, period_id: int, user_id: int
) -> AccountingPeriod:
    """SOFT_CLOSE or CLOSED → OPEN.  Admin override to reopen."""
    period = await get_period(db, period_id)
    if period is None:
        raise PeriodError(f"Period {period_id} not found")
    if period.status == PeriodStatus.LOCKED:
        raise PeriodError("Cannot reopen a LOCKED period")
    if period.status == PeriodStatus.OPEN:
        raise PeriodError("Period is already OPEN")
    period.status = PeriodStatus.OPEN
    period.closed_by = None
    period.closed_at = None
    await db.flush()
    logger.info("Reopened period %s by user %d", period.name, user_id)
    return period


async def generate_year_end_closing(
    db: AsyncSession,
    fiscal_year: int,
    user_id: int,
) -> "JournalEntry | None":
    """Generate the year-end closing entry.

    Closes all Revenue and Expense accounts into Retained Earnings.
    Returns the posted journal entry, or None if net income is zero.
    """
    from app.services.gl.journal_engine import create_journal_entry

    # Find Retained Earnings account
    re_result = await db.execute(
        select(GLAccount).where(GLAccount.account_code == "3-2000")
    )
    retained_earnings = re_result.scalar_one_or_none()
    if not retained_earnings:
        raise PeriodError("Retained Earnings account (3-2000) not found")

    # Find all periods in this fiscal year
    periods = await list_periods(db, fiscal_year=fiscal_year)
    period_ids = [p.id for p in periods]
    if not period_ids:
        raise PeriodError(f"No periods found for fiscal year {fiscal_year}")

    # Sum revenue and expense balances
    # Revenue accounts: credit-normal → net credit = revenue
    # Expense accounts: debit-normal → net debit = expense
    revenue_expense_accounts = await db.execute(
        select(GLAccount).where(
            GLAccount.account_category.in_([
                AccountCategory.REVENUE, AccountCategory.EXPENSE
            ]),
            GLAccount.status != "closed",
        )
    )
    accounts = list(revenue_expense_accounts.scalars().all())

    lines = []
    for acct in accounts:
        # Sum posted entries for this account in the fiscal year
        result = await db.execute(
            select(
                sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount), 0).label("dr"),
                sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount), 0).label("cr"),
            )
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .where(
                JournalEntryLine.gl_account_id == acct.id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.accounting_period_id.in_(period_ids),
            )
        )
        row = result.one()
        dr = Decimal(str(row.dr or 0))
        cr = Decimal(str(row.cr or 0))
        net = dr - cr  # positive = debit balance, negative = credit balance

        if net == 0:
            continue

        # Close by reversing the balance
        if net > 0:
            # Debit balance → credit to close
            lines.append({
                "gl_account_id": acct.id,
                "debit_amount": Decimal("0"),
                "credit_amount": net,
                "description": f"Year-end close: {acct.name}",
            })
        else:
            # Credit balance → debit to close
            lines.append({
                "gl_account_id": acct.id,
                "debit_amount": abs(net),
                "credit_amount": Decimal("0"),
                "description": f"Year-end close: {acct.name}",
            })

    if not lines:
        return None

    # Calculate net income (sum of credits - sum of debits = net to retained earnings)
    total_dr = sum(ln["debit_amount"] for ln in lines)
    total_cr = sum(ln["credit_amount"] for ln in lines)
    net_income = total_cr - total_dr

    # Balance the entry via Retained Earnings
    if net_income > 0:
        lines.append({
            "gl_account_id": retained_earnings.id,
            "debit_amount": net_income,
            "credit_amount": Decimal("0"),
            "description": f"Net income for FY{fiscal_year} to Retained Earnings",
        })
    elif net_income < 0:
        lines.append({
            "gl_account_id": retained_earnings.id,
            "debit_amount": Decimal("0"),
            "credit_amount": abs(net_income),
            "description": f"Net loss for FY{fiscal_year} to Retained Earnings",
        })

    entry = await create_journal_entry(
        db,
        lines=lines,
        source_type=JournalSourceType.SYSTEM,
        source_reference=f"YE-CLOSE-{fiscal_year}",
        description=f"Year-end closing entry for fiscal year {fiscal_year}",
        effective_date=date(fiscal_year, 12, 31),
        created_by=user_id,
        auto_post=True,
        narrative=(
            f"Year-end closing entry transferring net income of "
            f"${float(net_income):,.2f} to Retained Earnings for FY{fiscal_year}."
        ),
    )

    logger.info(
        "Generated year-end closing entry %s for FY%d (net income: %s)",
        entry.entry_number, fiscal_year, net_income,
    )
    return entry
