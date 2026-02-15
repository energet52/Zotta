"""Chart of Accounts service.

Handles CRUD operations on GL accounts with:
- Hierarchical validation (parent must exist and be at level N-1)
- Auto-generation of account codes based on parent
- Freeze / close (never delete if transactions exist)
- Append-only audit trail on every modification
"""

import logging
from typing import Any

from sqlalchemy import select, func as sa_func, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gl import (
    GLAccount,
    GLAccountAudit,
    AccountCategory,
    AccountType,
    AccountStatus,
    Currency,
    JournalEntryLine,
)

logger = logging.getLogger(__name__)


class COAError(Exception):
    """Chart of Accounts error."""


# ---------------------------------------------------------------------------
# Account code helpers
# ---------------------------------------------------------------------------

async def _auto_generate_code(
    db: AsyncSession, parent: GLAccount | None, category: AccountCategory
) -> str:
    """Generate the next account code under *parent*.

    Code scheme: ``L1-L2L3-NNN``
    - Level 1: single digit matching category (1=Asset..5=Expense)
    - Level 2: four-digit group code
    - Level 3+: three-digit sequential
    """
    category_prefix = {
        AccountCategory.ASSET: "1",
        AccountCategory.LIABILITY: "2",
        AccountCategory.EQUITY: "3",
        AccountCategory.REVENUE: "4",
        AccountCategory.EXPENSE: "5",
    }

    if parent is None:
        # Level 1
        prefix = category_prefix[category]
        return f"{prefix}-0000"

    parent_code = parent.account_code
    new_level = parent.level + 1

    if new_level == 2:
        # Find highest L2 code under this category prefix
        cat_prefix = parent_code.split("-")[0]
        result = await db.execute(
            select(sa_func.max(GLAccount.account_code))
            .where(
                GLAccount.parent_id == parent.id,
                GLAccount.level == 2,
            )
        )
        last = result.scalar_one_or_none()
        if last:
            group_num = int(last.split("-")[1]) + 1000
        else:
            group_num = 1000
        return f"{cat_prefix}-{group_num:04d}"

    else:
        # Level 3+ — sequential NNN suffix
        result = await db.execute(
            select(sa_func.max(GLAccount.account_code))
            .where(
                GLAccount.parent_id == parent.id,
                GLAccount.level == new_level,
            )
        )
        last = result.scalar_one_or_none()
        if last:
            parts = last.split("-")
            seq = int(parts[-1]) + 1
        else:
            seq = 1
        base = "-".join(parent_code.split("-")[:2])
        return f"{base}-{seq:03d}"


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

async def _audit_change(
    db: AsyncSession,
    account_id: int,
    field: str,
    old_val: Any,
    new_val: Any,
    user_id: int | None,
) -> None:
    db.add(GLAccountAudit(
        gl_account_id=account_id,
        field_changed=field,
        old_value=str(old_val) if old_val is not None else None,
        new_value=str(new_val) if new_val is not None else None,
        changed_by=user_id,
    ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def list_accounts(
    db: AsyncSession,
    *,
    category: AccountCategory | None = None,
    status: AccountStatus | None = None,
    parent_id: int | None = None,
    search: str | None = None,
    flat: bool = False,
) -> list[GLAccount]:
    """List GL accounts with optional filters."""
    q = select(GLAccount).order_by(GLAccount.account_code)

    if category:
        q = q.where(GLAccount.account_category == category)
    if status:
        q = q.where(GLAccount.status == status)
    if parent_id is not None:
        q = q.where(GLAccount.parent_id == parent_id)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            GLAccount.name.ilike(pattern) | GLAccount.account_code.ilike(pattern)
        )

    result = await db.execute(q)
    return list(result.scalars().all())


async def get_account(db: AsyncSession, account_id: int) -> GLAccount | None:
    result = await db.execute(
        select(GLAccount)
        .where(GLAccount.id == account_id)
        .options(selectinload(GLAccount.audit_trail))
    )
    return result.scalar_one_or_none()


async def get_account_by_code(db: AsyncSession, code: str) -> GLAccount | None:
    result = await db.execute(
        select(GLAccount).where(GLAccount.account_code == code)
    )
    return result.scalar_one_or_none()


async def create_account(
    db: AsyncSession,
    *,
    name: str,
    account_category: AccountCategory,
    account_type: AccountType,
    currency_code: str = "JMD",
    parent_id: int | None = None,
    account_code: str | None = None,
    description: str | None = None,
    is_control_account: bool = False,
    is_system_account: bool = False,
    created_by: int | None = None,
) -> GLAccount:
    """Create a new GL account.

    If *account_code* is not provided it is auto-generated based on the parent.
    """
    # Currency
    cur = await db.execute(select(Currency).where(Currency.code == currency_code))
    currency = cur.scalar_one_or_none()
    if not currency:
        raise COAError(f"Currency '{currency_code}' not found")

    # Parent validation
    parent = None
    level = 1
    if parent_id:
        parent = await get_account(db, parent_id)
        if parent is None:
            raise COAError(f"Parent account {parent_id} not found")
        level = parent.level + 1
        if level > 5:
            raise COAError("Maximum hierarchy depth is 5 levels")

    # Code
    if not account_code:
        account_code = await _auto_generate_code(db, parent, account_category)

    # Uniqueness check
    existing = await get_account_by_code(db, account_code)
    if existing:
        raise COAError(f"Account code '{account_code}' already exists")

    account = GLAccount(
        account_code=account_code,
        name=name,
        description=description,
        account_category=account_category,
        account_type=account_type,
        currency_id=currency.id,
        parent_id=parent_id,
        level=level,
        is_control_account=is_control_account,
        is_system_account=is_system_account,
        status=AccountStatus.ACTIVE,
        created_by=created_by,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    logger.info("Created GL account %s: %s", account.account_code, account.name)
    return account


async def update_account(
    db: AsyncSession,
    account_id: int,
    *,
    user_id: int | None = None,
    **fields,
) -> GLAccount:
    """Update mutable fields on a GL account and log changes."""
    account = await get_account(db, account_id)
    if account is None:
        raise COAError(f"Account {account_id} not found")

    if account.is_system_account:
        # System accounts: only allow name and description changes
        allowed = {"name", "description"}
        extra = set(fields.keys()) - allowed
        if extra:
            raise COAError(
                f"System account — only name/description can be modified (got {extra})"
            )

    mutable = {"name", "description", "is_control_account", "status"}
    for key, value in fields.items():
        if key not in mutable:
            continue
        old = getattr(account, key)
        if old != value:
            await _audit_change(db, account_id, key, old, value, user_id)
            setattr(account, key, value)

    await db.flush()
    await db.refresh(account)
    return account


async def freeze_account(
    db: AsyncSession, account_id: int, user_id: int | None = None
) -> GLAccount:
    """Freeze (deactivate) an account.  Prevents further postings."""
    return await update_account(
        db, account_id, user_id=user_id, status=AccountStatus.FROZEN
    )


async def close_account(
    db: AsyncSession, account_id: int, user_id: int | None = None
) -> GLAccount:
    """Close an account.  Only allowed if it has no posted transactions."""
    account = await get_account(db, account_id)
    if account is None:
        raise COAError(f"Account {account_id} not found")

    # Check for posted transactions
    has_txns = await db.execute(
        select(
            exists().where(JournalEntryLine.gl_account_id == account_id)
        )
    )
    if has_txns.scalar():
        raise COAError(
            "Cannot close account with posted transactions — freeze it instead"
        )

    return await update_account(
        db, account_id, user_id=user_id, status=AccountStatus.CLOSED
    )


async def _collect_descendant_ids(db: AsyncSession, account_id: int) -> list[int]:
    """Recursively gather all descendant account IDs (children, grandchildren, etc.)."""
    result = await db.execute(
        select(GLAccount.id).where(GLAccount.parent_id == account_id)
    )
    child_ids = list(result.scalars().all())
    all_ids = list(child_ids)
    for cid in child_ids:
        all_ids.extend(await _collect_descendant_ids(db, cid))
    return all_ids


async def get_account_balance(
    db: AsyncSession,
    account_id: int,
    *,
    as_of_date: "date | None" = None,
    period_id: int | None = None,
    include_children: bool = False,
) -> dict:
    """Calculate the running balance for an account.

    Returns ``{"debit_total", "credit_total", "balance"}``
    where balance = debits - credits for debit-normal accounts and
    credits - debits for credit-normal accounts.

    If *include_children* is True, aggregates postings across
    the account **and** all its descendants in the hierarchy.
    """
    from app.models.gl import JournalEntry, JournalEntryStatus

    # Determine which account IDs to aggregate
    account_ids = [account_id]
    if include_children:
        account_ids.extend(await _collect_descendant_ids(db, account_id))

    q = (
        select(
            sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount), 0).label("dr"),
            sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount), 0).label("cr"),
        )
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .where(
            JournalEntryLine.gl_account_id.in_(account_ids),
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )
    if as_of_date:
        q = q.where(JournalEntry.effective_date <= as_of_date)
    if period_id:
        q = q.where(JournalEntry.accounting_period_id == period_id)

    result = await db.execute(q)
    row = result.one()
    dr_total = row.dr or 0
    cr_total = row.cr or 0

    # Determine normal balance direction
    account = await get_account(db, account_id)
    if account and account.account_type == AccountType.DEBIT:
        balance = dr_total - cr_total
    else:
        balance = cr_total - dr_total

    return {
        "debit_total": float(dr_total),
        "credit_total": float(cr_total),
        "balance": float(balance),
    }
