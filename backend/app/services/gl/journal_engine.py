"""Core double-entry journal engine.

All monetary amounts flow through this engine.  The fundamental invariant is:
**total debits == total credits** for every journal entry, enforced at three
layers:

1. Database CHECK constraint on line amounts
2. Application-level validation before persist
3. API-level validation on input schemas

Journal entries are immutable once posted.  Corrections are made exclusively
via reversing entries.
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gl import (
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    JournalSourceType,
    AccountingPeriod,
    PeriodStatus,
    Currency,
    GLAccount,
    AccountStatus,
)

logger = logging.getLogger(__name__)


class JournalEngineError(Exception):
    """Base exception for journal engine errors."""


class BalanceError(JournalEngineError):
    """Debits do not equal credits."""


class StatusTransitionError(JournalEngineError):
    """Invalid status transition attempted."""


class PeriodClosedError(JournalEngineError):
    """Attempted to post to a closed or locked period."""


class AccountFrozenError(JournalEngineError):
    """Attempted to post to a frozen or closed account."""


# ---------------------------------------------------------------------------
# Entry-number generation
# ---------------------------------------------------------------------------

async def _next_entry_number(db: AsyncSession) -> str:
    """Generate the next sequential entry number: JE-YYYY-NNNNNN."""
    year = datetime.now(timezone.utc).year
    prefix = f"JE-{year}-"

    result = await db.execute(
        select(sa_func.max(JournalEntry.entry_number))
        .where(JournalEntry.entry_number.like(f"{prefix}%"))
    )
    last = result.scalar_one_or_none()

    if last:
        seq = int(last.replace(prefix, "")) + 1
    else:
        seq = 1

    return f"{prefix}{seq:06d}"


# ---------------------------------------------------------------------------
# Period lookup
# ---------------------------------------------------------------------------

async def _find_period_for_date(
    db: AsyncSession, effective: date
) -> AccountingPeriod | None:
    """Find the accounting period that contains *effective*."""
    result = await db.execute(
        select(AccountingPeriod)
        .where(
            AccountingPeriod.start_date <= effective,
            AccountingPeriod.end_date >= effective,
        )
        .order_by(AccountingPeriod.start_date)
        .limit(1)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_balance(lines: list[dict]) -> tuple[Decimal, Decimal]:
    """Ensure total debits == total credits.  Returns (total_dr, total_cr)."""
    total_dr = sum(Decimal(str(ln.get("debit_amount", 0))) for ln in lines)
    total_cr = sum(Decimal(str(ln.get("credit_amount", 0))) for ln in lines)
    if total_dr != total_cr:
        raise BalanceError(
            f"Entry is not balanced: debits={total_dr}, credits={total_cr}"
        )
    if total_dr == 0:
        raise BalanceError("Entry has zero total — at least one non-zero line required")
    return total_dr, total_cr


async def _validate_accounts(db: AsyncSession, account_ids: list[int]) -> None:
    """Check all accounts exist and are active."""
    result = await db.execute(
        select(GLAccount).where(GLAccount.id.in_(account_ids))
    )
    accounts = {a.id: a for a in result.scalars().all()}
    for aid in account_ids:
        acct = accounts.get(aid)
        if acct is None:
            raise JournalEngineError(f"GL account {aid} not found")
        if acct.status != AccountStatus.ACTIVE:
            raise AccountFrozenError(
                f"GL account {acct.account_code} ({acct.name}) is {acct.status.value}"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_journal_entry(
    db: AsyncSession,
    *,
    lines: list[dict[str, Any]],
    source_type: JournalSourceType = JournalSourceType.MANUAL,
    source_reference: str | None = None,
    description: str,
    transaction_date: date | None = None,
    effective_date: date | None = None,
    currency_code: str = "JMD",
    exchange_rate: Decimal = Decimal("1.000000"),
    created_by: int | None = None,
    metadata: dict | None = None,
    narrative: str | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """Create a new journal entry in DRAFT status.

    Parameters
    ----------
    lines : list of dicts
        Each dict must have ``gl_account_id``, ``debit_amount``, ``credit_amount``,
        and optionally ``description``, ``department``, ``branch``,
        ``loan_reference``, ``tags``.
    auto_post : bool
        If True, skip the approval workflow and immediately post (used for
        system-generated entries).  The entry goes straight to POSTED.
    """
    if not lines or len(lines) < 2:
        raise JournalEngineError("A journal entry requires at least two lines")

    # 1. Balance validation
    _validate_balance(lines)

    # 2. Account validation
    account_ids = [ln["gl_account_id"] for ln in lines]
    await _validate_accounts(db, account_ids)

    # 3. Currency lookup
    cur_result = await db.execute(
        select(Currency).where(Currency.code == currency_code)
    )
    currency = cur_result.scalar_one_or_none()
    if not currency:
        raise JournalEngineError(f"Currency '{currency_code}' not found")

    # 4. Dates
    today = date.today()
    txn_date = transaction_date or today
    eff_date = effective_date or txn_date

    # 5. Period lookup
    period = await _find_period_for_date(db, eff_date)

    # 6. Entry number
    entry_number = await _next_entry_number(db)

    # 7. Build entry
    status = JournalEntryStatus.DRAFT
    if auto_post:
        if period and period.status in (PeriodStatus.CLOSED, PeriodStatus.LOCKED):
            raise PeriodClosedError(
                f"Cannot auto-post: period {period.name} is {period.status.value}"
            )
        status = JournalEntryStatus.POSTED

    entry = JournalEntry(
        entry_number=entry_number,
        transaction_date=txn_date,
        effective_date=eff_date,
        posting_date=today if auto_post else None,
        accounting_period_id=period.id if period else None,
        source_type=source_type,
        source_reference=source_reference,
        description=description,
        currency_id=currency.id,
        exchange_rate=exchange_rate,
        status=status,
        created_by=created_by,
        posted_by=created_by if auto_post else None,
        posted_at=datetime.now(timezone.utc) if auto_post else None,
        metadata_=metadata,
        narrative=narrative,
    )
    db.add(entry)
    await db.flush()

    # 8. Build lines
    for idx, ln in enumerate(lines, start=1):
        dr = Decimal(str(ln.get("debit_amount", 0)))
        cr = Decimal(str(ln.get("credit_amount", 0)))
        net = dr - cr
        base_amount = net * exchange_rate

        line = JournalEntryLine(
            journal_entry_id=entry.id,
            line_number=idx,
            gl_account_id=ln["gl_account_id"],
            debit_amount=dr,
            credit_amount=cr,
            base_currency_amount=abs(base_amount),
            description=ln.get("description"),
            department=ln.get("department"),
            branch=ln.get("branch"),
            loan_reference=ln.get("loan_reference"),
            tags=ln.get("tags"),
        )
        db.add(line)

    await db.flush()
    await db.refresh(entry, ["lines"])
    logger.info("Created journal entry %s (status=%s)", entry.entry_number, entry.status.value)
    return entry


async def get_journal_entry(
    db: AsyncSession, entry_id: int
) -> JournalEntry | None:
    """Load a journal entry with its lines."""
    result = await db.execute(
        select(JournalEntry)
        .where(JournalEntry.id == entry_id)
        .options(selectinload(JournalEntry.lines))
    )
    return result.scalar_one_or_none()


async def submit_for_approval(
    db: AsyncSession, entry_id: int
) -> JournalEntry:
    """Transition DRAFT → PENDING_APPROVAL."""
    entry = await get_journal_entry(db, entry_id)
    if entry is None:
        raise JournalEngineError(f"Journal entry {entry_id} not found")
    if entry.status != JournalEntryStatus.DRAFT:
        raise StatusTransitionError(
            f"Cannot submit: entry is {entry.status.value}, expected DRAFT"
        )
    if not entry.is_balanced:
        raise BalanceError("Entry is not balanced")

    entry.status = JournalEntryStatus.PENDING_APPROVAL
    await db.flush()
    logger.info("Submitted %s for approval", entry.entry_number)
    return entry


async def approve_entry(
    db: AsyncSession, entry_id: int, approver_id: int
) -> JournalEntry:
    """Transition PENDING_APPROVAL → APPROVED."""
    entry = await get_journal_entry(db, entry_id)
    if entry is None:
        raise JournalEngineError(f"Journal entry {entry_id} not found")
    if entry.status != JournalEntryStatus.PENDING_APPROVAL:
        raise StatusTransitionError(
            f"Cannot approve: entry is {entry.status.value}, expected PENDING_APPROVAL"
        )
    entry.status = JournalEntryStatus.APPROVED
    entry.approved_by = approver_id
    entry.approved_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Approved %s by user %d", entry.entry_number, approver_id)
    return entry


async def post_entry(
    db: AsyncSession, entry_id: int, poster_id: int
) -> JournalEntry:
    """Transition APPROVED → POSTED.

    Validates the accounting period is open before posting.
    """
    entry = await get_journal_entry(db, entry_id)
    if entry is None:
        raise JournalEngineError(f"Journal entry {entry_id} not found")
    if entry.status != JournalEntryStatus.APPROVED:
        raise StatusTransitionError(
            f"Cannot post: entry is {entry.status.value}, expected APPROVED"
        )

    # Period validation
    if entry.accounting_period_id:
        period_result = await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.id == entry.accounting_period_id
            )
        )
        period = period_result.scalar_one_or_none()
        if period and period.status in (PeriodStatus.CLOSED, PeriodStatus.LOCKED):
            raise PeriodClosedError(
                f"Cannot post to period {period.name} — status is {period.status.value}"
            )

    now = datetime.now(timezone.utc)
    entry.status = JournalEntryStatus.POSTED
    entry.posted_by = poster_id
    entry.posted_at = now
    entry.posting_date = now.date()
    await db.flush()
    logger.info("Posted %s by user %d", entry.entry_number, poster_id)
    return entry


async def reject_entry(
    db: AsyncSession, entry_id: int, reason: str
) -> JournalEntry:
    """Transition PENDING_APPROVAL → REJECTED."""
    entry = await get_journal_entry(db, entry_id)
    if entry is None:
        raise JournalEngineError(f"Journal entry {entry_id} not found")
    if entry.status != JournalEntryStatus.PENDING_APPROVAL:
        raise StatusTransitionError(
            f"Cannot reject: entry is {entry.status.value}, expected PENDING_APPROVAL"
        )
    entry.status = JournalEntryStatus.REJECTED
    entry.rejection_reason = reason
    await db.flush()
    logger.info("Rejected %s: %s", entry.entry_number, reason)
    return entry


async def reverse_entry(
    db: AsyncSession,
    entry_id: int,
    *,
    reason: str,
    reverser_id: int,
    effective_date: date | None = None,
) -> JournalEntry:
    """Reverse a posted entry by creating a new mirror entry.

    The original entry status is changed to REVERSED, and the reversal
    entry is immediately posted.
    """
    original = await get_journal_entry(db, entry_id)
    if original is None:
        raise JournalEngineError(f"Journal entry {entry_id} not found")
    if original.status != JournalEntryStatus.POSTED:
        raise StatusTransitionError(
            f"Cannot reverse: entry is {original.status.value}, expected POSTED"
        )
    if original.reversed_by_id is not None:
        raise JournalEngineError(
            f"Entry {original.entry_number} has already been reversed"
        )

    # Build reversal lines (flip debits ↔ credits)
    reversal_lines = []
    for ln in original.lines:
        reversal_lines.append({
            "gl_account_id": ln.gl_account_id,
            "debit_amount": ln.credit_amount,
            "credit_amount": ln.debit_amount,
            "description": f"Reversal: {ln.description or ''}".strip(),
            "department": ln.department,
            "branch": ln.branch,
            "loan_reference": ln.loan_reference,
            "tags": ln.tags,
        })

    # Create reversal entry (auto-posted)
    eff = effective_date or date.today()

    # Get currency code
    cur_result = await db.execute(
        select(Currency).where(Currency.id == original.currency_id)
    )
    currency = cur_result.scalar_one()

    reversal = await create_journal_entry(
        db,
        lines=reversal_lines,
        source_type=JournalSourceType.REVERSAL,
        source_reference=original.entry_number,
        description=f"Reversal of {original.entry_number}: {reason}",
        effective_date=eff,
        currency_code=currency.code,
        exchange_rate=original.exchange_rate,
        created_by=reverser_id,
        auto_post=True,
        metadata={"reversed_entry_id": original.id, "reason": reason},
    )

    # Link original ↔ reversal
    reversal.reversal_of_id = original.id
    original.reversed_by_id = reversal.id
    original.status = JournalEntryStatus.REVERSED
    await db.flush()

    logger.info(
        "Reversed %s → %s by user %d",
        original.entry_number,
        reversal.entry_number,
        reverser_id,
    )
    return reversal
