"""General Ledger API endpoints.

Covers Chart of Accounts management, journal entry lifecycle, trial balance,
accounting periods, and currency listing.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth_utils import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.gl import (
    Currency,
    GLAccount,
    GLAccountAudit,
    AccountingPeriod,
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    JournalSourceType,
    AccountCategory,
    AccountType,
    AccountStatus,
    PeriodStatus,
)
from app.services.gl import journal_engine, coa_service, period_service, mapping_engine
from app.services.gl import export_service, reports_service
from app.services.gl import anomaly_detector, classifier, nl_query, forecasting, reconciliation
from app.services.error_logger import log_error

logger = logging.getLogger(__name__)
router = APIRouter()

STAFF_ROLES = (UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER, UserRole.JUNIOR_UNDERWRITER)


# ===================================================================
# Pydantic Schemas
# ===================================================================

# -- Currency --

class CurrencyResponse(BaseModel):
    id: int
    code: str
    name: str
    symbol: str
    decimal_places: int
    is_base: bool
    is_active: bool

    model_config = {"from_attributes": True}


# -- GL Account --

class AccountCreateRequest(BaseModel):
    name: str
    account_category: str
    account_type: str
    currency_code: str = "JMD"
    parent_id: Optional[int] = None
    account_code: Optional[str] = None
    description: Optional[str] = None
    is_control_account: bool = False


class AccountUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_control_account: Optional[bool] = None


class AccountResponse(BaseModel):
    id: int
    account_code: str
    name: str
    description: Optional[str] = None
    account_category: str
    account_type: str
    currency_id: int
    parent_id: Optional[int] = None
    level: int
    is_control_account: bool
    is_system_account: bool
    status: str
    children_count: int = 0

    model_config = {"from_attributes": True}


class AccountBalanceResponse(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    debit_total: float
    credit_total: float
    balance: float


class AccountAuditResponse(BaseModel):
    id: int
    field_changed: str
    old_value: Optional[str]
    new_value: Optional[str]
    changed_by: Optional[int]
    changed_at: str

    model_config = {"from_attributes": True}


# -- Accounting Period --

class PeriodCreateRequest(BaseModel):
    year: int


class PeriodResponse(BaseModel):
    id: int
    fiscal_year: int
    period_number: int
    name: str
    start_date: str
    end_date: str
    status: str

    model_config = {"from_attributes": True}


# -- Journal Entry --

class JournalLineInput(BaseModel):
    gl_account_id: int
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    description: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    loan_reference: Optional[str] = None
    tags: Optional[dict] = None


class JournalEntryCreateRequest(BaseModel):
    lines: list[JournalLineInput] = Field(..., min_length=2)
    description: str
    source_type: str = "manual"
    source_reference: Optional[str] = None
    transaction_date: Optional[str] = None
    effective_date: Optional[str] = None
    currency_code: str = "JMD"
    exchange_rate: float = 1.0
    narrative: Optional[str] = None


class JournalEntryRejectRequest(BaseModel):
    reason: str


class JournalEntryReverseRequest(BaseModel):
    reason: str
    effective_date: Optional[str] = None


class JournalLineResponse(BaseModel):
    id: int
    line_number: int
    gl_account_id: int
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    debit_amount: float
    credit_amount: float
    base_currency_amount: float
    description: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    loan_reference: Optional[str] = None
    tags: Optional[dict] = None

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: int
    entry_number: str
    transaction_date: str
    effective_date: str
    posting_date: Optional[str] = None
    accounting_period_id: Optional[int] = None
    source_type: str
    source_reference: Optional[str] = None
    description: str
    currency_id: int
    exchange_rate: float
    status: str
    total_debits: float = 0
    total_credits: float = 0
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    posted_by: Optional[int] = None
    created_at: Optional[str] = None
    approved_at: Optional[str] = None
    posted_at: Optional[str] = None
    reversal_of_id: Optional[int] = None
    reversed_by_id: Optional[int] = None
    narrative: Optional[str] = None
    rejection_reason: Optional[str] = None
    lines: list[JournalLineResponse] = []

    model_config = {"from_attributes": True}


# -- Trial Balance --

class TrialBalanceRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_category: str
    level: int
    debit_balance: float
    credit_balance: float


class TrialBalanceResponse(BaseModel):
    period_id: Optional[int] = None
    as_of_date: Optional[str] = None
    rows: list[TrialBalanceRow]
    total_debits: float
    total_credits: float
    is_balanced: bool


# -- Ledger --

class LedgerTransaction(BaseModel):
    date: str
    entry_number: str
    entry_id: int
    description: str
    debit: float
    credit: float
    running_balance: float
    source_type: str


class AccountLedgerResponse(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    opening_balance: float
    transactions: list[LedgerTransaction]
    closing_balance: float


# ===================================================================
# Helpers
# ===================================================================

def _serialize_date(d) -> str | None:
    if d is None:
        return None
    if hasattr(d, "isoformat"):
        return d.isoformat()
    return str(d)


def _entry_to_response(entry: JournalEntry) -> dict:
    lines = []
    for ln in (entry.lines or []):
        acct = ln.gl_account if hasattr(ln, "gl_account") and ln.gl_account else None
        lines.append(JournalLineResponse(
            id=ln.id,
            line_number=ln.line_number,
            gl_account_id=ln.gl_account_id,
            account_code=acct.account_code if acct else None,
            account_name=acct.name if acct else None,
            debit_amount=float(ln.debit_amount),
            credit_amount=float(ln.credit_amount),
            base_currency_amount=float(ln.base_currency_amount),
            description=ln.description,
            department=ln.department,
            branch=ln.branch,
            loan_reference=ln.loan_reference,
            tags=ln.tags,
        ))

    return JournalEntryResponse(
        id=entry.id,
        entry_number=entry.entry_number,
        transaction_date=_serialize_date(entry.transaction_date),
        effective_date=_serialize_date(entry.effective_date),
        posting_date=_serialize_date(entry.posting_date),
        accounting_period_id=entry.accounting_period_id,
        source_type=entry.source_type.value if entry.source_type else "manual",
        source_reference=entry.source_reference,
        description=entry.description,
        currency_id=entry.currency_id,
        exchange_rate=float(entry.exchange_rate),
        status=entry.status.value if entry.status else "draft",
        total_debits=float(entry.total_debits),
        total_credits=float(entry.total_credits),
        created_by=entry.created_by,
        approved_by=entry.approved_by,
        posted_by=entry.posted_by,
        created_at=_serialize_date(entry.created_at),
        approved_at=_serialize_date(entry.approved_at),
        posted_at=_serialize_date(entry.posted_at),
        reversal_of_id=entry.reversal_of_id,
        reversed_by_id=entry.reversed_by_id,
        narrative=entry.narrative,
        rejection_reason=entry.rejection_reason,
        lines=lines,
    ).model_dump()


# ===================================================================
# Currency Endpoints
# ===================================================================

@router.get("/currencies", response_model=list[CurrencyResponse])
async def list_currencies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        result = await db.execute(
            select(Currency).order_by(Currency.code)
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="list_currencies")
        raise


# ===================================================================
# Chart of Accounts Endpoints
# ===================================================================

@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(
    category: Optional[str] = None,
    status: Optional[str] = None,
    parent_id: Optional[int] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        cat = AccountCategory(category) if category else None
        st = AccountStatus(status) if status else None
        accounts = await coa_service.list_accounts(
            db, category=cat, status=st, parent_id=parent_id, search=search
        )
        result = []
        for a in accounts:
            # Count children
            child_result = await db.execute(
                select(sa_func.count(GLAccount.id)).where(GLAccount.parent_id == a.id)
            )
            children_count = child_result.scalar() or 0
            resp = AccountResponse(
                id=a.id,
                account_code=a.account_code,
                name=a.name,
                description=a.description,
                account_category=a.account_category.value,
                account_type=a.account_type.value,
                currency_id=a.currency_id,
                parent_id=a.parent_id,
                level=a.level,
                is_control_account=a.is_control_account,
                is_system_account=a.is_system_account,
                status=a.status.value,
                children_count=children_count,
            )
            result.append(resp)
        return result
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="list_accounts")
        raise


@router.post("/accounts", response_model=AccountResponse)
async def create_account(
    data: AccountCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            account = await coa_service.create_account(
                db,
                name=data.name,
                account_category=AccountCategory(data.account_category),
                account_type=AccountType(data.account_type),
                currency_code=data.currency_code,
                parent_id=data.parent_id,
                account_code=data.account_code,
                description=data.description,
                is_control_account=data.is_control_account,
                created_by=current_user.id,
            )
            return AccountResponse(
                id=account.id,
                account_code=account.account_code,
                name=account.name,
                description=account.description,
                account_category=account.account_category.value,
                account_type=account.account_type.value,
                currency_id=account.currency_id,
                parent_id=account.parent_id,
                level=account.level,
                is_control_account=account.is_control_account,
                is_system_account=account.is_system_account,
                status=account.status.value,
            )
        except coa_service.COAError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="create_account")
        raise


@router.put("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    data: AccountUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            fields = data.model_dump(exclude_unset=True)
            account = await coa_service.update_account(
                db, account_id, user_id=current_user.id, **fields
            )
            return AccountResponse(
                id=account.id,
                account_code=account.account_code,
                name=account.name,
                description=account.description,
                account_category=account.account_category.value,
                account_type=account.account_type.value,
                currency_id=account.currency_id,
                parent_id=account.parent_id,
                level=account.level,
                is_control_account=account.is_control_account,
                is_system_account=account.is_system_account,
                status=account.status.value,
            )
        except coa_service.COAError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="update_account")
        raise


@router.post("/accounts/{account_id}/freeze")
async def freeze_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            account = await coa_service.freeze_account(db, account_id, current_user.id)
            return {"status": "frozen", "account_code": account.account_code}
        except coa_service.COAError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="freeze_account")
        raise


@router.get("/accounts/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance(
    account_id: int,
    period_id: Optional[int] = None,
    as_of_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        account = await coa_service.get_account(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        d = date.fromisoformat(as_of_date) if as_of_date else None
        balance = await coa_service.get_account_balance(
            db, account_id, as_of_date=d, period_id=period_id
        )
        return AccountBalanceResponse(
            account_id=account_id,
            account_code=account.account_code,
            account_name=account.name,
            **balance,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="get_account_balance")
        raise


@router.get("/accounts/{account_id}/audit", response_model=list[AccountAuditResponse])
async def get_account_audit(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        result = await db.execute(
            select(GLAccountAudit)
            .where(GLAccountAudit.gl_account_id == account_id)
            .order_by(GLAccountAudit.changed_at.desc())
        )
        rows = result.scalars().all()
        return [
            AccountAuditResponse(
                id=r.id,
                field_changed=r.field_changed,
                old_value=r.old_value,
                new_value=r.new_value,
                changed_by=r.changed_by,
                changed_at=_serialize_date(r.changed_at),
            )
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="get_account_audit")
        raise


@router.get("/accounts/{account_id}/ledger", response_model=AccountLedgerResponse)
async def get_account_ledger(
    account_id: int,
    period_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """T-account view: all posted transactions for an account with running balance."""
    try:
        account = await coa_service.get_account(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        q = (
            select(JournalEntryLine, JournalEntry)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .where(
                JournalEntryLine.gl_account_id == account_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
            .order_by(JournalEntry.effective_date, JournalEntry.id)
        )
        if period_id:
            q = q.where(JournalEntry.accounting_period_id == period_id)
        if date_from:
            q = q.where(JournalEntry.effective_date >= date.fromisoformat(date_from))
        if date_to:
            q = q.where(JournalEntry.effective_date <= date.fromisoformat(date_to))

        result = await db.execute(q)
        rows = result.all()

        is_debit_normal = account.account_type == AccountType.DEBIT
        running = 0.0
        transactions = []
        for line, entry in rows:
            dr = float(line.debit_amount)
            cr = float(line.credit_amount)
            if is_debit_normal:
                running += dr - cr
            else:
                running += cr - dr
            transactions.append(LedgerTransaction(
                date=_serialize_date(entry.effective_date),
                entry_number=entry.entry_number,
                entry_id=entry.id,
                description=line.description or entry.description,
                debit=dr,
                credit=cr,
                running_balance=round(running, 2),
                source_type=entry.source_type.value,
            ))

        return AccountLedgerResponse(
            account_id=account_id,
            account_code=account.account_code,
            account_name=account.name,
            opening_balance=0.0,
            transactions=transactions,
            closing_balance=round(running, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="get_account_ledger")
        raise


# ===================================================================
# Journal Entry Endpoints
# ===================================================================

@router.get("/entries")
async def list_journal_entries(
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    period_id: Optional[int] = None,
    account_id: Optional[int] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    loan_id: Optional[str] = None,
    q: Optional[str] = None,
    entry_number: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """List journal entries with comprehensive filtering."""
    try:
        query = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.gl_account))
            .order_by(JournalEntry.id.desc())
        )

        if status:
            statuses = [JournalEntryStatus(s.strip()) for s in status.split(",")]
            query = query.where(JournalEntry.status.in_(statuses))
        if source_type:
            types = [JournalSourceType(s.strip()) for s in source_type.split(",")]
            query = query.where(JournalEntry.source_type.in_(types))
        if date_from:
            query = query.where(JournalEntry.transaction_date >= date.fromisoformat(date_from))
        if date_to:
            query = query.where(JournalEntry.transaction_date <= date.fromisoformat(date_to))
        if period_id:
            query = query.where(JournalEntry.accounting_period_id == period_id)
        if entry_number:
            query = query.where(JournalEntry.entry_number.ilike(f"%{entry_number}%"))
        if q:
            query = query.where(JournalEntry.description.ilike(f"%{q}%"))
        if loan_id:
            query = query.where(JournalEntry.source_reference.ilike(f"%{loan_id}%"))

        # Account filter — entries that have a line for this account
        if account_id:
            query = query.where(
                JournalEntry.id.in_(
                    select(JournalEntryLine.journal_entry_id)
                    .where(JournalEntryLine.gl_account_id == account_id)
                )
            )

        # Count
        from sqlalchemy import func as sqla_func
        count_q = select(sqla_func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        entries = result.scalars().all()

        # Amount filter (post-query since it involves line aggregation)
        items = []
        for entry in entries:
            resp = _entry_to_response(entry)
            total_amt = resp["total_debits"]
            if amount_min and total_amt < amount_min:
                continue
            if amount_max and total_amt > amount_max:
                continue
            items.append(resp)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="list_journal_entries")
        raise


@router.post("/entries")
async def create_journal_entry_endpoint(
    data: JournalEntryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Create a new journal entry in DRAFT status."""
    try:
        try:
            lines = [
                {
                    "gl_account_id": ln.gl_account_id,
                    "debit_amount": ln.debit_amount,
                    "credit_amount": ln.credit_amount,
                    "description": ln.description,
                    "department": ln.department,
                    "branch": ln.branch,
                    "loan_reference": ln.loan_reference,
                    "tags": ln.tags,
                }
                for ln in data.lines
            ]
            entry = await journal_engine.create_journal_entry(
                db,
                lines=lines,
                source_type=JournalSourceType(data.source_type),
                source_reference=data.source_reference,
                description=data.description,
                transaction_date=date.fromisoformat(data.transaction_date) if data.transaction_date else None,
                effective_date=date.fromisoformat(data.effective_date) if data.effective_date else None,
                currency_code=data.currency_code,
                exchange_rate=Decimal(str(data.exchange_rate)),
                created_by=current_user.id,
                narrative=data.narrative,
            )
            # Reload with account info
            entry = await db.execute(
                select(JournalEntry)
                .where(JournalEntry.id == entry.id)
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.gl_account))
            )
            entry = entry.scalar_one()
            return _entry_to_response(entry)
        except (journal_engine.JournalEngineError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="create_journal_entry_endpoint")
        raise


@router.get("/entries/{entry_id}")
async def get_journal_entry_endpoint(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        result = await db.execute(
            select(JournalEntry)
            .where(JournalEntry.id == entry_id)
            .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.gl_account))
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return _entry_to_response(entry)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="get_journal_entry_endpoint")
        raise


@router.post("/entries/{entry_id}/submit")
async def submit_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        try:
            entry = await journal_engine.submit_for_approval(db, entry_id)
            return {"status": entry.status.value, "entry_number": entry.entry_number}
        except journal_engine.JournalEngineError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="submit_entry")
        raise


@router.post("/entries/{entry_id}/approve")
async def approve_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)),
):
    try:
        try:
            entry = await journal_engine.approve_entry(db, entry_id, current_user.id)
            return {"status": entry.status.value, "entry_number": entry.entry_number}
        except journal_engine.JournalEngineError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="approve_entry")
        raise


@router.post("/entries/{entry_id}/post")
async def post_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)),
):
    try:
        try:
            entry = await journal_engine.post_entry(db, entry_id, current_user.id)
            return {"status": entry.status.value, "entry_number": entry.entry_number}
        except journal_engine.JournalEngineError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="post_entry")
        raise


@router.post("/entries/{entry_id}/reject")
async def reject_entry(
    entry_id: int,
    data: JournalEntryRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)),
):
    try:
        try:
            entry = await journal_engine.reject_entry(db, entry_id, data.reason)
            return {"status": entry.status.value, "entry_number": entry.entry_number}
        except journal_engine.JournalEngineError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="reject_entry")
        raise


@router.post("/entries/{entry_id}/reverse")
async def reverse_entry(
    entry_id: int,
    data: JournalEntryReverseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)),
):
    try:
        try:
            eff = date.fromisoformat(data.effective_date) if data.effective_date else None
            reversal = await journal_engine.reverse_entry(
                db, entry_id, reason=data.reason, reverser_id=current_user.id,
                effective_date=eff,
            )
            result = await db.execute(
                select(JournalEntry)
                .where(JournalEntry.id == reversal.id)
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.gl_account))
            )
            reversal = result.scalar_one()
            return _entry_to_response(reversal)
        except journal_engine.JournalEngineError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="reverse_entry")
        raise


# ===================================================================
# Trial Balance
# ===================================================================

@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def get_trial_balance(
    period_id: Optional[int] = None,
    as_of_date: Optional[str] = None,
    level: int = Query(3, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Generate trial balance for a period or as-of date."""
    try:
        d = date.fromisoformat(as_of_date) if as_of_date else None

        accounts = await db.execute(
            select(GLAccount)
            .where(GLAccount.level <= level, GLAccount.status != AccountStatus.CLOSED)
            .order_by(GLAccount.account_code)
        )
        all_accounts = list(accounts.scalars().all())

        rows = []
        total_dr = 0.0
        total_cr = 0.0

        for acct in all_accounts:
            balance_data = await coa_service.get_account_balance(
                db, acct.id, as_of_date=d, period_id=period_id
            )
            bal = balance_data["balance"]

            dr_bal = bal if bal > 0 and acct.account_type == AccountType.DEBIT else (
                abs(bal) if bal < 0 and acct.account_type == AccountType.CREDIT else 0
            )
            cr_bal = bal if bal > 0 and acct.account_type == AccountType.CREDIT else (
                abs(bal) if bal < 0 and acct.account_type == AccountType.DEBIT else 0
            )

            # Simpler: show balance in the natural side
            if acct.account_type == AccountType.DEBIT:
                dr_bal = max(0, bal)
                cr_bal = max(0, -bal)
            else:
                cr_bal = max(0, bal)
                dr_bal = max(0, -bal)

            if dr_bal == 0 and cr_bal == 0:
                continue

            total_dr += dr_bal
            total_cr += cr_bal

            rows.append(TrialBalanceRow(
                account_id=acct.id,
                account_code=acct.account_code,
                account_name=acct.name,
                account_category=acct.account_category.value,
                level=acct.level,
                debit_balance=round(dr_bal, 2),
                credit_balance=round(cr_bal, 2),
            ))

        return TrialBalanceResponse(
            period_id=period_id,
            as_of_date=as_of_date,
            rows=rows,
            total_debits=round(total_dr, 2),
            total_credits=round(total_cr, 2),
            is_balanced=abs(total_dr - total_cr) < 0.01,
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="get_trial_balance")
        raise


# ===================================================================
# Accounting Periods
# ===================================================================

@router.get("/periods", response_model=list[PeriodResponse])
async def list_periods(
    fiscal_year: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        st = PeriodStatus(status) if status else None
        periods = await period_service.list_periods(db, fiscal_year=fiscal_year, status=st)
        return [
            PeriodResponse(
                id=p.id,
                fiscal_year=p.fiscal_year,
                period_number=p.period_number,
                name=p.name,
                start_date=_serialize_date(p.start_date),
                end_date=_serialize_date(p.end_date),
                status=p.status.value,
            )
            for p in periods
        ]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="list_periods")
        raise


@router.post("/periods", response_model=list[PeriodResponse])
async def create_fiscal_year(
    data: PeriodCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            periods = await period_service.create_fiscal_year(db, data.year)
            return [
                PeriodResponse(
                    id=p.id,
                    fiscal_year=p.fiscal_year,
                    period_number=p.period_number,
                    name=p.name,
                    start_date=_serialize_date(p.start_date),
                    end_date=_serialize_date(p.end_date),
                    status=p.status.value,
                )
                for p in periods
            ]
        except period_service.PeriodError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="create_fiscal_year")
        raise


@router.post("/periods/{period_id}/close")
async def close_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            period = await period_service.close_period(db, period_id, current_user.id)
            return {"status": period.status.value, "name": period.name}
        except period_service.PeriodError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="close_period")
        raise


@router.post("/periods/{period_id}/soft-close")
async def soft_close_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            period = await period_service.soft_close_period(db, period_id, current_user.id)
            return {"status": period.status.value, "name": period.name}
        except period_service.PeriodError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="soft_close_period")
        raise


@router.post("/periods/{period_id}/lock")
async def lock_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            period = await period_service.lock_period(db, period_id, current_user.id)
            return {"status": period.status.value, "name": period.name}
        except period_service.PeriodError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="lock_period")
        raise


@router.post("/periods/{period_id}/reopen")
async def reopen_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            period = await period_service.reopen_period(db, period_id, current_user.id)
            return {"status": period.status.value, "name": period.name}
        except period_service.PeriodError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="reopen_period")
        raise


# ===================================================================
# Dashboard Summary
# ===================================================================

@router.get("/dashboard-summary")
async def dashboard_summary(
    period_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Key account balances for dashboard cards."""
    try:
        key_accounts = [
            "1-2000",  # Loan Portfolio
            "1-3000",  # Interest Receivable
            "1-1000",  # Cash and Bank
            "2-2000",  # Allowance for Loan Losses
            "4-1000",  # Interest Income
            "5-1000",  # Provision Expense
        ]

        balances = {}
        for code in key_accounts:
            acct = await coa_service.get_account_by_code(db, code)
            if acct:
                bal = await coa_service.get_account_balance(
                    db, acct.id, period_id=period_id, include_children=True,
                )
                balances[code] = {
                    "name": acct.name,
                    "balance": bal["balance"],
                    "debit_total": bal["debit_total"],
                    "credit_total": bal["credit_total"],
                }

        # Entry counts by status
        for st in [JournalEntryStatus.DRAFT, JournalEntryStatus.PENDING_APPROVAL, JournalEntryStatus.POSTED]:
            q = select(sa_func.count(JournalEntry.id)).where(JournalEntry.status == st)
            if period_id:
                q = q.where(JournalEntry.accounting_period_id == period_id)
            count = (await db.execute(q)).scalar() or 0
            balances[f"entries_{st.value}"] = count

        return balances
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="dashboard_summary")
        raise


# ===================================================================
# GL Mapping Templates (Phase 2)
# ===================================================================

class MappingLineInput(BaseModel):
    line_type: str  # "debit" or "credit"
    gl_account_id: int
    amount_source: str  # "principal", "interest", "fee", "full_amount", "custom"
    description_template: Optional[str] = None


class MappingTemplateCreateRequest(BaseModel):
    name: str
    event_type: str
    credit_product_id: Optional[int] = None
    conditions: Optional[dict] = None
    description: Optional[str] = None
    lines: list[MappingLineInput] = Field(..., min_length=2)


class MappingLineResponse(BaseModel):
    id: int
    line_type: str
    gl_account_id: int
    amount_source: str
    description_template: Optional[str] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None

    model_config = {"from_attributes": True}


class MappingTemplateResponse(BaseModel):
    id: int
    name: str
    event_type: str
    credit_product_id: Optional[int] = None
    is_active: bool
    conditions: Optional[dict] = None
    description: Optional[str] = None
    lines: list[MappingLineResponse] = []

    model_config = {"from_attributes": True}


class DryRunRequest(BaseModel):
    event_type: str
    source_reference: str = "DRY-RUN-TEST"
    amount_breakdown: dict
    product_id: Optional[int] = None
    context: Optional[dict] = None


@router.get("/mappings", response_model=list[MappingTemplateResponse])
async def list_mapping_templates(
    event_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        evt = JournalSourceType(event_type) if event_type else None
        templates = await mapping_engine.list_templates(db, event_type=evt)
        results = []
        for tpl in templates:
            lines = []
            for ln in tpl.lines:
                acct = None
                if ln.gl_account_id:
                    acct = await coa_service.get_account(db, ln.gl_account_id)
                lines.append(MappingLineResponse(
                    id=ln.id,
                    line_type=ln.line_type.value,
                    gl_account_id=ln.gl_account_id,
                    amount_source=ln.amount_source.value,
                    description_template=ln.description_template,
                    account_code=acct.account_code if acct else None,
                    account_name=acct.name if acct else None,
                ))
            results.append(MappingTemplateResponse(
                id=tpl.id,
                name=tpl.name,
                event_type=tpl.event_type.value,
                credit_product_id=tpl.credit_product_id,
                is_active=tpl.is_active,
                conditions=tpl.conditions,
                description=tpl.description,
                lines=lines,
            ))
        return results
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="list_mapping_templates")
        raise


@router.post("/mappings", response_model=MappingTemplateResponse)
async def create_mapping_template(
    data: MappingTemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    try:
        try:
            template = await mapping_engine.create_template(
                db,
                name=data.name,
                event_type=JournalSourceType(data.event_type),
                lines=[ln.model_dump() for ln in data.lines],
                credit_product_id=data.credit_product_id,
                conditions=data.conditions,
                description=data.description,
            )
            lines = []
            for ln in template.lines:
                acct = await coa_service.get_account(db, ln.gl_account_id) if ln.gl_account_id else None
                lines.append(MappingLineResponse(
                    id=ln.id,
                    line_type=ln.line_type.value,
                    gl_account_id=ln.gl_account_id,
                    amount_source=ln.amount_source.value,
                    description_template=ln.description_template,
                    account_code=acct.account_code if acct else None,
                    account_name=acct.name if acct else None,
                ))
            return MappingTemplateResponse(
                id=template.id,
                name=template.name,
                event_type=template.event_type.value,
                credit_product_id=template.credit_product_id,
                is_active=template.is_active,
                conditions=template.conditions,
                description=template.description,
                lines=lines,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="create_mapping_template")
        raise


@router.post("/mappings/dry-run")
async def dry_run_mapping(
    data: DryRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Preview what journal entry would be generated."""
    try:
        try:
            result = await mapping_engine.dry_run(
                db,
                event_type=JournalSourceType(data.event_type),
                source_reference=data.source_reference,
                amount_breakdown=data.amount_breakdown,
                product_id=data.product_id,
                context=data.context,
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="dry_run_mapping")
        raise


@router.get("/mappings/validate/{product_id}")
async def validate_product_mappings(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Check mapping completeness for a product."""
    result = await mapping_engine.validate_product_mappings(db, product_id)
    return result


# ===================================================================
# Search (Phase 3)
# ===================================================================

@router.get("/search")
async def search_gl(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Structured GL search with operator syntax.

    Supported operators:
    - ``amount:>50000`` — filter by amount
    - ``account:2100*`` — filter by account code pattern
    - ``status:posted`` — filter by status
    - ``source:loan_disbursement`` — filter by source type
    - Free text searches descriptions.
    """
    try:
        import re

        filters = {}
        text_parts = []

        # Parse operators
        tokens = q.split()
        for token in tokens:
            if ":" in token:
                key, val = token.split(":", 1)
                filters[key.lower()] = val
            else:
                text_parts.append(token)

        text_search = " ".join(text_parts) if text_parts else None

        query = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.gl_account))
            .order_by(JournalEntry.id.desc())
        )

        if text_search:
            query = query.where(JournalEntry.description.ilike(f"%{text_search}%"))
        if "status" in filters:
            try:
                query = query.where(JournalEntry.status == JournalEntryStatus(filters["status"]))
            except ValueError:
                pass
        if "source" in filters:
            try:
                query = query.where(JournalEntry.source_type == JournalSourceType(filters["source"]))
            except ValueError:
                pass
        if "account" in filters:
            acct_pattern = filters["account"].replace("*", "%")
            query = query.where(
                JournalEntry.id.in_(
                    select(JournalEntryLine.journal_entry_id)
                    .join(GLAccount, JournalEntryLine.gl_account_id == GLAccount.id)
                    .where(GLAccount.account_code.ilike(acct_pattern))
                )
            )
        if "entry" in filters:
            query = query.where(JournalEntry.entry_number.ilike(f"%{filters['entry']}%"))
        if "loan" in filters:
            query = query.where(JournalEntry.source_reference.ilike(f"%{filters['loan']}%"))

        # Count
        from sqlalchemy import func as sqla_func
        count_q = select(sqla_func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        entries = result.scalars().all()

        items = []
        for entry in entries:
            resp = _entry_to_response(entry)
            # Amount filter (post-query)
            if "amount" in filters:
                amt_str = filters["amount"]
                amt_val = float(re.sub(r"[^0-9.]", "", amt_str))
                entry_amt = resp["total_debits"]
                if amt_str.startswith(">") and entry_amt <= amt_val:
                    continue
                elif amt_str.startswith("<") and entry_amt >= amt_val:
                    continue
            items.append(resp)

        return {"items": items, "total": total, "page": page, "page_size": page_size}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="search_gl")
        raise


# ===================================================================
# Financial Statements (Phase 3)
# ===================================================================

@router.get("/balance-sheet")
async def get_balance_sheet(
    period_id: Optional[int] = None,
    as_of_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Generate balance sheet: Assets = Liabilities + Equity."""
    try:
        d = date.fromisoformat(as_of_date) if as_of_date else None
        categories = [AccountCategory.ASSET, AccountCategory.LIABILITY, AccountCategory.EQUITY]
        sections = {}

        for cat in categories:
            accounts = await db.execute(
                select(GLAccount)
                .where(GLAccount.account_category == cat, GLAccount.status != AccountStatus.CLOSED)
                .order_by(GLAccount.account_code)
            )
            items = []
            section_total = 0.0
            for acct in accounts.scalars().all():
                bal = await coa_service.get_account_balance(db, acct.id, as_of_date=d, period_id=period_id)
                if bal["balance"] == 0:
                    continue
                items.append({
                    "account_id": acct.id,
                    "account_code": acct.account_code,
                    "account_name": acct.name,
                    "level": acct.level,
                    "balance": bal["balance"],
                })
                section_total += bal["balance"]
            sections[cat.value] = {"items": items, "total": round(section_total, 2)}

        assets_total = sections.get("asset", {}).get("total", 0)
        liabilities_total = sections.get("liability", {}).get("total", 0)
        equity_total = sections.get("equity", {}).get("total", 0)

        return {
            "period_id": period_id,
            "as_of_date": as_of_date,
            "sections": sections,
            "assets_total": assets_total,
            "liabilities_equity_total": round(liabilities_total + equity_total, 2),
            "is_balanced": abs(assets_total - (liabilities_total + equity_total)) < 0.01,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="get_balance_sheet")
        raise


@router.get("/income-statement")
async def get_income_statement(
    period_id: Optional[int] = None,
    as_of_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Generate income statement: Revenue - Expenses = Net Income."""
    try:
        d = date.fromisoformat(as_of_date) if as_of_date else None
        categories = [AccountCategory.REVENUE, AccountCategory.EXPENSE]
        sections = {}

        for cat in categories:
            accounts = await db.execute(
                select(GLAccount)
                .where(GLAccount.account_category == cat, GLAccount.status != AccountStatus.CLOSED)
                .order_by(GLAccount.account_code)
            )
            items = []
            section_total = 0.0
            for acct in accounts.scalars().all():
                bal = await coa_service.get_account_balance(db, acct.id, as_of_date=d, period_id=period_id)
                if bal["balance"] == 0:
                    continue
                items.append({
                    "account_id": acct.id,
                    "account_code": acct.account_code,
                    "account_name": acct.name,
                    "level": acct.level,
                    "balance": bal["balance"],
                })
                section_total += bal["balance"]
            sections[cat.value] = {"items": items, "total": round(section_total, 2)}

        revenue_total = sections.get("revenue", {}).get("total", 0)
        expense_total = sections.get("expense", {}).get("total", 0)

        return {
            "period_id": period_id,
            "as_of_date": as_of_date,
            "sections": sections,
            "revenue_total": revenue_total,
            "expense_total": expense_total,
            "net_income": round(revenue_total - expense_total, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="get_income_statement")
        raise


# ===================================================================
# Filter Presets (Phase 3)
# ===================================================================

class FilterPresetCreate(BaseModel):
    name: str
    filters: dict
    is_shared: bool = False


class FilterPresetResponse(BaseModel):
    id: int
    name: str
    filters: dict
    is_shared: bool
    user_id: int

    model_config = {"from_attributes": True}


@router.get("/filter-presets", response_model=list[FilterPresetResponse])
async def list_filter_presets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        from app.models.gl import GLFilterPreset
        result = await db.execute(
            select(GLFilterPreset)
            .where(
                (GLFilterPreset.user_id == current_user.id) | (GLFilterPreset.is_shared == True)
            )
            .order_by(GLFilterPreset.name)
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="list_filter_presets")
        raise


@router.post("/filter-presets", response_model=FilterPresetResponse)
async def create_filter_preset(
    data: FilterPresetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        from app.models.gl import GLFilterPreset
        preset = GLFilterPreset(
            user_id=current_user.id,
            name=data.name,
            filters=data.filters,
            is_shared=data.is_shared,
        )
        db.add(preset)
        await db.flush()
        await db.refresh(preset)
        return preset
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="create_filter_preset")
        raise


@router.delete("/filter-presets/{preset_id}")
async def delete_filter_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        from app.models.gl import GLFilterPreset
        result = await db.execute(
            select(GLFilterPreset).where(
                GLFilterPreset.id == preset_id,
                GLFilterPreset.user_id == current_user.id,
            )
        )
        preset = result.scalar_one_or_none()
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        await db.delete(preset)
        await db.flush()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="delete_filter_preset")
        raise


# ===================================================================
# Export (Phase 4)
# ===================================================================

class ExportRequest(BaseModel):
    format: str  # csv, xlsx, pdf, json, xml
    export_type: str = "journal_entries"
    filters: Optional[dict] = None
    columns: Optional[list[str]] = None
    title: str = "GL Export"


@router.post("/export")
async def export_gl_data(
    data: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Export GL data in the specified format."""
    try:
        from fastapi.responses import Response

        # Gather data based on export type
        if data.export_type == "journal_entries":
            entries_result = await db.execute(
                select(JournalEntry)
                .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.gl_account))
                .where(JournalEntry.status == JournalEntryStatus.POSTED)
                .order_by(JournalEntry.transaction_date.desc())
                .limit(5000)
            )
            entries = entries_result.scalars().all()
            rows = []
            for e in entries:
                for ln in e.lines:
                    rows.append({
                        "entry_number": e.entry_number,
                        "date": str(e.effective_date),
                        "source_type": e.source_type.value,
                        "description": ln.description or e.description,
                        "account_code": ln.gl_account.account_code if ln.gl_account else "",
                        "account_name": ln.gl_account.name if ln.gl_account else "",
                        "debit": float(ln.debit_amount),
                        "credit": float(ln.credit_amount),
                        "loan_reference": ln.loan_reference or "",
                    })
        elif data.export_type == "trial_balance":
            rows = await reports_service.trial_balance_report(db)
        elif data.export_type == "chart_of_accounts":
            accounts = await coa_service.list_accounts(db)
            rows = [{
                "code": a.account_code, "name": a.name,
                "category": a.account_category.value, "type": a.account_type.value,
                "level": a.level, "status": a.status.value,
            } for a in accounts]
        else:
            rows = []

        result_bytes = await export_service.export_data(
            db,
            data=rows,
            format=data.format,
            columns=data.columns,
            title=data.title,
            user_id=current_user.id,
            export_type=data.export_type,
            filters=data.filters,
        )

        content_type = export_service.get_content_type(data.format)
        ext = export_service.get_file_extension(data.format)
        filename = f"gl_export_{data.export_type}{ext}"

        return Response(
            content=result_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="export_gl_data")
        raise


# ===================================================================
# Reports (Phase 4)
# ===================================================================

@router.get("/reports/types")
async def list_report_types(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """List available report types."""
    try:
        return [
            {"key": k, "name": v["name"], "description": v["description"]}
            for k, v in reports_service.REPORT_REGISTRY.items()
        ]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=None, module="api.gl", function_name="list_report_types")
        raise


@router.get("/reports/{report_type}")
async def generate_report(
    report_type: str,
    period_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Generate a standard report."""
    try:
        if report_type not in reports_service.REPORT_REGISTRY:
            raise HTTPException(status_code=404, detail=f"Unknown report type: {report_type}")

        report_def = reports_service.REPORT_REGISTRY[report_type]
        fn = report_def["fn"]

        # Build kwargs based on report function signature
        kwargs: dict = {}
        if period_id:
            kwargs["period_id"] = period_id
        if date_from:
            kwargs["date_from"] = date.fromisoformat(date_from)
        if date_to:
            kwargs["date_to"] = date.fromisoformat(date_to)
        if account_id and report_type == "account_activity":
            kwargs["account_id"] = account_id

        try:
            data = await fn(db, **kwargs)
        except TypeError:
            # Function doesn't accept some kwargs — retry with just db
            data = await fn(db)

        return {
            "report_type": report_type,
            "report_name": report_def["name"],
            "data": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="generate_report")
        raise


@router.post("/reports/{report_type}/export")
async def export_report(
    report_type: str,
    data: ExportRequest,
    period_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Generate and export a report in the specified format."""
    try:
        from fastapi.responses import Response

        if report_type not in reports_service.REPORT_REGISTRY:
            raise HTTPException(status_code=404, detail=f"Unknown report type: {report_type}")

        report_def = reports_service.REPORT_REGISTRY[report_type]
        fn = report_def["fn"]

        kwargs: dict = {}
        if period_id:
            kwargs["period_id"] = period_id

        try:
            report_data = await fn(db, **kwargs)
        except TypeError:
            report_data = await fn(db)

        # Handle dict reports (wrap in list)
        if isinstance(report_data, dict):
            rows = [report_data]
        else:
            rows = report_data

        result_bytes = await export_service.export_data(
            db,
            data=rows,
            format=data.format,
            title=report_def["name"],
            user_id=current_user.id,
            export_type=f"report_{report_type}",
            filters=data.filters,
        )

        content_type = export_service.get_content_type(data.format)
        ext = export_service.get_file_extension(data.format)
        filename = f"gl_report_{report_type}{ext}"

        return Response(
            content=result_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="export_report")
        raise


# ===================================================================
# AI — Anomaly Detection (Phase 5)
# ===================================================================

@router.get("/anomalies")
async def list_anomalies(
    status: Optional[str] = None,
    min_risk_score: Optional[int] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        from app.models.gl import AnomalyStatus as AS
        st = AS(status) if status else None
        anomalies = await anomaly_detector.get_anomalies(
            db, status=st, min_risk_score=min_risk_score, limit=limit,
        )
        return [
            {
                "id": a.id,
                "journal_entry_id": a.journal_entry_id,
                "anomaly_type": a.anomaly_type.value,
                "risk_score": a.risk_score,
                "explanation": a.explanation,
                "status": a.status.value,
                "reviewed_by": a.reviewed_by,
                "reviewed_at": _serialize_date(a.reviewed_at),
                "created_at": _serialize_date(a.created_at),
            }
            for a in anomalies
        ]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="list_anomalies")
        raise


@router.post("/anomalies/{anomaly_id}/review")
async def review_anomaly(
    anomaly_id: int,
    action: str = Query(..., pattern="^(reviewed|dismissed)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SENIOR_UNDERWRITER)),
):
    try:
        from app.models.gl import AnomalyStatus as AS
        st = AS.REVIEWED if action == "reviewed" else AS.DISMISSED
        result = await anomaly_detector.review_anomaly(
            db, anomaly_id, status=st, reviewer_id=current_user.id
        )
        if not result:
            raise HTTPException(status_code=404, detail="Anomaly not found")
        return {"status": result.status.value, "id": result.id}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="review_anomaly")
        raise


@router.post("/entries/{entry_id}/detect-anomalies")
async def detect_anomalies(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Run anomaly detection on a specific entry."""
    try:
        anomalies = await anomaly_detector.detect_and_store(db, entry_id)
        return {
            "entry_id": entry_id,
            "anomaly_count": len(anomalies),
            "anomalies": [
                {
                    "id": a.id,
                    "type": a.anomaly_type.value,
                    "risk_score": a.risk_score,
                    "explanation": a.explanation,
                }
                for a in anomalies
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="detect_anomalies")
        raise


# ===================================================================
# AI — Transaction Classifier (Phase 5)
# ===================================================================

@router.get("/suggest-accounts")
async def suggest_accounts_endpoint(
    description: str = Query(..., min_length=1),
    amount: Optional[float] = None,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Suggest GL accounts based on description text."""
    try:
        amt = Decimal(str(amount)) if amount else None
        suggestions = await classifier.suggest_accounts(
            db, description=description, amount=amt, limit=limit,
        )
        return suggestions
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="suggest_accounts_endpoint")
        raise


# ===================================================================
# AI — Natural Language Query (Phase 5)
# ===================================================================

class NLQueryRequest(BaseModel):
    question: str
    context: Optional[dict] = None


@router.post("/query")
async def natural_language_query(
    data: NLQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Answer GL questions in natural language."""
    result = await nl_query.process_query(db, data.question, context=data.context)
    return result


# ===================================================================
# AI — Predictive Analytics (Phase 5)
# ===================================================================

@router.get("/forecast/cash-flow")
async def cash_flow_forecast_endpoint(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    return await forecasting.cash_flow_forecast(db, months_ahead=months)


@router.get("/forecast/revenue")
async def revenue_forecast_endpoint(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    return await forecasting.revenue_forecast(db, months_ahead=months)


@router.get("/forecast/account/{account_id}")
async def account_forecast_endpoint(
    account_id: int,
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    return await forecasting.account_balance_forecast(db, account_id, months_ahead=months)


# ===================================================================
# AI — Reconciliation (Phase 5)
# ===================================================================

@router.get("/reconciliation/suspense/stale")
async def stale_suspense_items(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    return await reconciliation.find_stale_suspense_items(db, days_threshold=days)


@router.get("/reconciliation/match/{account_id}")
async def auto_match_endpoint(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    return await reconciliation.auto_match_entries(db, account_id)


@router.get("/reconciliation/{control_code}")
async def reconcile_endpoint(
    control_code: str,
    period_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    try:
        return await reconciliation.reconcile_control_account(
            db, control_code, period_id=period_id
        )
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="reconcile_endpoint")
        raise


# ===================================================================
# Period-Close Automation (Phase 6)
# ===================================================================

@router.get("/periods/{period_id}/close-readiness")
async def period_close_readiness(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Check if a period is ready to close — automated checklist."""
    try:
        from sqlalchemy import func as sqla_func

        period = await period_service.get_period(db, period_id)
        if not period:
            raise HTTPException(status_code=404, detail="Period not found")

        checks = []

        # 1. No draft entries
        draft_count = (await db.execute(
            select(sqla_func.count(JournalEntry.id)).where(
                JournalEntry.accounting_period_id == period_id,
                JournalEntry.status == JournalEntryStatus.DRAFT,
            )
        )).scalar() or 0
        checks.append({
            "check": "No draft entries",
            "passed": draft_count == 0,
            "detail": f"{draft_count} draft entries remaining" if draft_count else "All clear",
        })

        # 2. No pending approval entries
        pending_count = (await db.execute(
            select(sqla_func.count(JournalEntry.id)).where(
                JournalEntry.accounting_period_id == period_id,
                JournalEntry.status == JournalEntryStatus.PENDING_APPROVAL,
            )
        )).scalar() or 0
        checks.append({
            "check": "No pending approvals",
            "passed": pending_count == 0,
            "detail": f"{pending_count} entries pending approval" if pending_count else "All clear",
        })

        # 3. No approved but unposted entries
        approved_count = (await db.execute(
            select(sqla_func.count(JournalEntry.id)).where(
                JournalEntry.accounting_period_id == period_id,
                JournalEntry.status == JournalEntryStatus.APPROVED,
            )
        )).scalar() or 0
        checks.append({
            "check": "No approved unposted entries",
            "passed": approved_count == 0,
            "detail": f"{approved_count} entries approved but not posted" if approved_count else "All clear",
        })

        # 4. Trial balance is balanced
        from app.services.gl.reports_service import trial_balance_report
        tb_rows = await trial_balance_report(db, period_id=period_id, level=5)
        total_dr = sum(r["debit_balance"] for r in tb_rows)
        total_cr = sum(r["credit_balance"] for r in tb_rows)
        is_balanced = abs(total_dr - total_cr) < 0.01
        checks.append({
            "check": "Trial balance is balanced",
            "passed": is_balanced,
            "detail": f"Debits: ${total_dr:,.2f}, Credits: ${total_cr:,.2f}" + (
                "" if is_balanced else f" — difference: ${abs(total_dr - total_cr):,.2f}"
            ),
        })

        # 5. Control accounts are reconciled
        recon = await reconciliation.reconcile_control_account(db, "1-2000", period_id=period_id)
        checks.append({
            "check": "Loan portfolio reconciled",
            "passed": recon.get("is_reconciled", False),
            "detail": (
                "Reconciled" if recon.get("is_reconciled") else
                f"Difference: ${abs(recon.get('difference', 0)):,.2f}"
            ),
        })

        all_passed = all(c["passed"] for c in checks)

        return {
            "period_id": period_id,
            "period_name": period.name,
            "current_status": period.status.value,
            "checks": checks,
            "is_ready": all_passed,
            "recommendation": "Ready to close" if all_passed else "Action required before closing",
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="period_close_readiness")
        raise


@router.post("/periods/year-end-close/{fiscal_year}")
async def year_end_close(
    fiscal_year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Generate the year-end closing entry (close Revenue/Expense to Retained Earnings)."""
    try:
        try:
            entry = await period_service.generate_year_end_closing(
                db, fiscal_year, current_user.id
            )
            if entry is None:
                return {"status": "no_action", "message": "Net income is zero — no closing entry needed"}
            return {
                "status": "completed",
                "entry_number": entry.entry_number,
                "description": entry.description,
                "narrative": entry.narrative,
            }
        except period_service.PeriodError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="year_end_close")
        raise


# ===================================================================
# GL Backfill — create JEs for historical disbursements and payments
# ===================================================================


@router.post("/backfill")
async def backfill_gl(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """One-time backfill: create GL journal entries for all existing
    disbursements and payments that don't already have a JE."""
    try:
        from app.models.disbursement import Disbursement, DisbursementStatus
        from app.models.payment import Payment, PaymentStatus
        from app.services.gl.mapping_engine import generate_journal_entry, MappingError

        results = {"disbursements": {"processed": 0, "created": 0, "skipped": 0, "errors": []},
                   "payments": {"processed": 0, "created": 0, "skipped": 0, "errors": []}}

        # ── Backfill disbursements ───────────────────────────────
        disb_q = await db.execute(
            select(Disbursement)
            .where(Disbursement.status == DisbursementStatus.COMPLETED)
            .order_by(Disbursement.disbursed_at)
        )
        for disb in disb_q.scalars().all():
            results["disbursements"]["processed"] += 1
            source_ref = f"LOAN-{disb.loan_application_id}"

            # Check if JE already exists
            existing = await db.execute(
                select(JournalEntry.id).where(
                    JournalEntry.source_type == JournalSourceType.LOAN_DISBURSEMENT,
                    JournalEntry.source_reference == source_ref,
                ).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                results["disbursements"]["skipped"] += 1
                continue

            try:
                eff_date = disb.disbursed_at.date() if disb.disbursed_at else None
                await generate_journal_entry(
                    db,
                    event_type=JournalSourceType.LOAN_DISBURSEMENT,
                    source_reference=source_ref,
                    amount_breakdown={
                        "principal": Decimal(str(disb.amount)),
                        "full_amount": Decimal(str(disb.amount)),
                    },
                    description=f"Backfill — Loan disbursement {source_ref}",
                    effective_date=eff_date,
                    currency_code="JMD",
                    created_by=disb.disbursed_by,
                    auto_post=True,
                )
                results["disbursements"]["created"] += 1
            except (MappingError, Exception) as e:
                results["disbursements"]["errors"].append(f"{source_ref}: {e}")

        # ── Backfill payments ────────────────────────────────────
        pay_q = await db.execute(
            select(Payment)
            .where(Payment.status == PaymentStatus.COMPLETED)
            .order_by(Payment.payment_date)
        )
        for pay in pay_q.scalars().all():
            results["payments"]["processed"] += 1
            source_ref = f"PMT-{pay.id}"

            existing = await db.execute(
                select(JournalEntry.id).where(
                    JournalEntry.source_type == JournalSourceType.REPAYMENT,
                    JournalEntry.source_reference == source_ref,
                ).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                results["payments"]["skipped"] += 1
                continue

            try:
                await generate_journal_entry(
                    db,
                    event_type=JournalSourceType.REPAYMENT,
                    source_reference=source_ref,
                    amount_breakdown={
                        "principal": Decimal(str(pay.amount)),
                        "full_amount": Decimal(str(pay.amount)),
                    },
                    description=f"Backfill — Loan repayment {source_ref} for LOAN-{pay.loan_application_id}",
                    effective_date=pay.payment_date,
                    currency_code="JMD",
                    created_by=pay.recorded_by,
                    loan_reference=f"LOAN-{pay.loan_application_id}",
                    auto_post=True,
                )
                results["payments"]["created"] += 1
            except (MappingError, Exception) as e:
                results["payments"]["errors"].append(f"{source_ref}: {e}")

        await db.commit()

        total_created = results["disbursements"]["created"] + results["payments"]["created"]
        return {
            "status": "completed",
            "total_journal_entries_created": total_created,
            "details": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.gl", function_name="backfill_gl")
        raise
