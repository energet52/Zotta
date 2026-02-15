"""GL standard reports service.

Provides 12 standard financial reports, each returning structured data
suitable for rendering in the UI or exporting to CSV/Excel/PDF.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gl import (
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    JournalSourceType,
    GLAccount,
    AccountCategory,
    AccountType,
    AccountStatus,
    AccountingPeriod,
    GLAccountAudit,
)
from app.services.gl.coa_service import get_account_balance

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _fmt(val) -> float:
    """Convert Decimal/int to float for JSON serialisation."""
    if isinstance(val, Decimal):
        return float(val)
    return float(val) if val else 0.0


# ---------------------------------------------------------------------------
# 1. GL Detail Report
# ---------------------------------------------------------------------------

async def gl_detail_report(
    db: AsyncSession,
    *,
    period_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Every posted journal entry line with full detail."""
    q = (
        select(JournalEntryLine, JournalEntry, GLAccount)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .join(GLAccount, JournalEntryLine.gl_account_id == GLAccount.id)
        .where(JournalEntry.status == JournalEntryStatus.POSTED)
        .order_by(JournalEntry.effective_date, JournalEntry.entry_number, JournalEntryLine.line_number)
    )
    if period_id:
        q = q.where(JournalEntry.accounting_period_id == period_id)
    if date_from:
        q = q.where(JournalEntry.effective_date >= date_from)
    if date_to:
        q = q.where(JournalEntry.effective_date <= date_to)

    result = await db.execute(q)
    rows = []
    for line, entry, account in result.all():
        rows.append({
            "date": str(entry.effective_date),
            "entry_number": entry.entry_number,
            "source_type": entry.source_type.value,
            "source_reference": entry.source_reference,
            "description": line.description or entry.description,
            "account_code": account.account_code,
            "account_name": account.name,
            "debit": _fmt(line.debit_amount),
            "credit": _fmt(line.credit_amount),
            "department": line.department,
            "branch": line.branch,
            "loan_reference": line.loan_reference,
        })
    return rows


# ---------------------------------------------------------------------------
# 2. Trial Balance
# ---------------------------------------------------------------------------

async def trial_balance_report(
    db: AsyncSession,
    *,
    period_id: int | None = None,
    as_of_date: date | None = None,
    level: int = 3,
) -> list[dict]:
    """Trial balance with optional comparative period."""
    accounts = await db.execute(
        select(GLAccount)
        .where(GLAccount.level <= level, GLAccount.status != AccountStatus.CLOSED)
        .order_by(GLAccount.account_code)
    )
    rows = []
    for acct in accounts.scalars().all():
        bal = await get_account_balance(db, acct.id, as_of_date=as_of_date, period_id=period_id)
        balance = bal["balance"]
        if balance == 0:
            continue
        dr = max(0, balance) if acct.account_type == AccountType.DEBIT else max(0, -balance)
        cr = max(0, balance) if acct.account_type == AccountType.CREDIT else max(0, -balance)
        rows.append({
            "account_code": acct.account_code,
            "account_name": acct.name,
            "category": acct.account_category.value,
            "level": acct.level,
            "debit_balance": round(dr, 2),
            "credit_balance": round(cr, 2),
        })
    return rows


# ---------------------------------------------------------------------------
# 3. Journal Entry Register
# ---------------------------------------------------------------------------

async def journal_register(
    db: AsyncSession,
    *,
    period_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: JournalEntryStatus | None = None,
) -> list[dict]:
    """All journal entries (header level) with totals."""
    q = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .order_by(JournalEntry.transaction_date, JournalEntry.entry_number)
    )
    if period_id:
        q = q.where(JournalEntry.accounting_period_id == period_id)
    if date_from:
        q = q.where(JournalEntry.transaction_date >= date_from)
    if date_to:
        q = q.where(JournalEntry.transaction_date <= date_to)
    if status:
        q = q.where(JournalEntry.status == status)

    result = await db.execute(q)
    rows = []
    for entry in result.scalars().all():
        rows.append({
            "entry_number": entry.entry_number,
            "date": str(entry.transaction_date),
            "effective_date": str(entry.effective_date),
            "source_type": entry.source_type.value,
            "source_reference": entry.source_reference,
            "description": entry.description,
            "status": entry.status.value,
            "total_debit": _fmt(entry.total_debits),
            "total_credit": _fmt(entry.total_credits),
            "line_count": len(entry.lines),
            "created_by": entry.created_by,
        })
    return rows


# ---------------------------------------------------------------------------
# 4. Account Activity Report
# ---------------------------------------------------------------------------

async def account_activity_report(
    db: AsyncSession,
    account_id: int,
    *,
    period_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """All transactions for a specific account."""
    q = (
        select(JournalEntryLine, JournalEntry)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .where(
            JournalEntryLine.gl_account_id == account_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
        .order_by(JournalEntry.effective_date, JournalEntry.entry_number)
    )
    if period_id:
        q = q.where(JournalEntry.accounting_period_id == period_id)
    if date_from:
        q = q.where(JournalEntry.effective_date >= date_from)
    if date_to:
        q = q.where(JournalEntry.effective_date <= date_to)

    result = await db.execute(q)
    rows = []
    for line, entry in result.all():
        rows.append({
            "date": str(entry.effective_date),
            "entry_number": entry.entry_number,
            "description": line.description or entry.description,
            "source_type": entry.source_type.value,
            "debit": _fmt(line.debit_amount),
            "credit": _fmt(line.credit_amount),
            "loan_reference": line.loan_reference,
        })
    return rows


# ---------------------------------------------------------------------------
# 5. Subsidiary Ledger Report
# ---------------------------------------------------------------------------

async def subsidiary_ledger_report(
    db: AsyncSession,
    *,
    control_account_code: str = "1-2000",
    period_id: int | None = None,
) -> list[dict]:
    """Subsidiary breakdown under a control account (e.g. Loan Portfolio)."""
    # Get control account's children
    parent = await db.execute(
        select(GLAccount).where(GLAccount.account_code == control_account_code)
    )
    parent_acct = parent.scalar_one_or_none()
    if not parent_acct:
        return []

    children = await db.execute(
        select(GLAccount).where(GLAccount.parent_id == parent_acct.id).order_by(GLAccount.account_code)
    )
    rows = []
    for child in children.scalars().all():
        bal = await get_account_balance(db, child.id, period_id=period_id)
        rows.append({
            "account_code": child.account_code,
            "account_name": child.name,
            "debit_total": bal["debit_total"],
            "credit_total": bal["credit_total"],
            "balance": bal["balance"],
        })
    return rows


# ---------------------------------------------------------------------------
# 6. Loan Portfolio GL Summary
# ---------------------------------------------------------------------------

async def loan_portfolio_summary(
    db: AsyncSession,
    *,
    period_id: int | None = None,
) -> dict:
    """Summary of the loan portfolio from GL perspective."""
    key_codes = {
        "performing": "1-2001",
        "non_performing": "1-2002",
        "written_off": "1-2003",
        "interest_receivable": "1-3001",
        "allowance": "2-2000",
    }
    summary = {}
    for label, code in key_codes.items():
        acct = await db.execute(select(GLAccount).where(GLAccount.account_code == code))
        acct_obj = acct.scalar_one_or_none()
        if acct_obj:
            bal = await get_account_balance(
                db, acct_obj.id, period_id=period_id, include_children=True,
            )
            summary[label] = bal["balance"]
        else:
            summary[label] = 0

    summary["total_portfolio"] = summary.get("performing", 0) + summary.get("non_performing", 0)
    summary["net_portfolio"] = summary["total_portfolio"] - abs(summary.get("allowance", 0))
    return summary


# ---------------------------------------------------------------------------
# 7. Interest Accrual Report
# ---------------------------------------------------------------------------

async def interest_accrual_report(
    db: AsyncSession,
    *,
    period_id: int | None = None,
) -> list[dict]:
    """All interest accrual entries in a period."""
    q = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.source_type == JournalSourceType.INTEREST_ACCRUAL)
        .order_by(JournalEntry.effective_date)
    )
    if period_id:
        q = q.where(JournalEntry.accounting_period_id == period_id)

    result = await db.execute(q)
    rows = []
    for entry in result.scalars().all():
        for line in entry.lines:
            if line.debit_amount > 0:
                rows.append({
                    "date": str(entry.effective_date),
                    "entry_number": entry.entry_number,
                    "loan_reference": line.loan_reference,
                    "accrued_amount": _fmt(line.debit_amount),
                    "description": line.description,
                    "status": entry.status.value,
                })
    return rows


# ---------------------------------------------------------------------------
# 8. Provision Movement Report
# ---------------------------------------------------------------------------

async def provision_movement_report(
    db: AsyncSession,
    *,
    period_id: int | None = None,
) -> list[dict]:
    """Provision expense and allowance movements."""
    q = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.source_type == JournalSourceType.PROVISION)
        .order_by(JournalEntry.effective_date)
    )
    if period_id:
        q = q.where(JournalEntry.accounting_period_id == period_id)

    result = await db.execute(q)
    rows = []
    for entry in result.scalars().all():
        for line in entry.lines:
            if line.debit_amount > 0:
                rows.append({
                    "date": str(entry.effective_date),
                    "entry_number": entry.entry_number,
                    "loan_reference": line.loan_reference,
                    "provision_amount": _fmt(line.debit_amount),
                    "description": line.description,
                })
    return rows


# ---------------------------------------------------------------------------
# 9. Suspense Account Aging
# ---------------------------------------------------------------------------

async def suspense_aging_report(
    db: AsyncSession,
) -> list[dict]:
    """Items in suspense accounts with aging."""
    suspense = await db.execute(
        select(GLAccount).where(GLAccount.account_code.like("%-9%")).order_by(GLAccount.account_code)
    )
    rows = []
    for acct in suspense.scalars().all():
        bal = await get_account_balance(db, acct.id)
        if bal["balance"] != 0:
            rows.append({
                "account_code": acct.account_code,
                "account_name": acct.name,
                "balance": bal["balance"],
            })
    return rows


# ---------------------------------------------------------------------------
# 10. Audit Trail Report
# ---------------------------------------------------------------------------

async def audit_trail_report(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """COA modification audit trail."""
    q = select(GLAccountAudit).order_by(GLAccountAudit.changed_at.desc())
    result = await db.execute(q)
    rows = []
    for audit in result.scalars().all():
        rows.append({
            "account_id": audit.gl_account_id,
            "field_changed": audit.field_changed,
            "old_value": audit.old_value,
            "new_value": audit.new_value,
            "changed_by": audit.changed_by,
            "changed_at": str(audit.changed_at),
        })
    return rows


# ---------------------------------------------------------------------------
# 11. Reconciliation Report
# ---------------------------------------------------------------------------

async def reconciliation_report(
    db: AsyncSession,
    *,
    control_account_code: str = "1-2000",
    period_id: int | None = None,
) -> dict:
    """Compare control account balance with subsidiary totals."""
    # Control account balance
    ctrl = await db.execute(
        select(GLAccount).where(GLAccount.account_code == control_account_code)
    )
    ctrl_acct = ctrl.scalar_one_or_none()
    if not ctrl_acct:
        return {"error": f"Account {control_account_code} not found"}

    ctrl_bal = await get_account_balance(
        db, ctrl_acct.id, period_id=period_id, include_children=True,
    )

    # Sum of subsidiaries
    children = await db.execute(
        select(GLAccount).where(GLAccount.parent_id == ctrl_acct.id)
    )
    sub_total = 0.0
    sub_details = []
    for child in children.scalars().all():
        bal = await get_account_balance(
            db, child.id, period_id=period_id, include_children=True,
        )
        sub_total += bal["balance"]
        sub_details.append({
            "account_code": child.account_code,
            "account_name": child.name,
            "balance": bal["balance"],
        })

    difference = round(ctrl_bal["balance"] - sub_total, 2)
    return {
        "control_account": control_account_code,
        "control_balance": ctrl_bal["balance"],
        "subsidiary_total": round(sub_total, 2),
        "difference": difference,
        "is_reconciled": abs(difference) < 0.01,
        "subsidiaries": sub_details,
    }


# ---------------------------------------------------------------------------
# 12. Financial Statements (Balance Sheet + Income Statement)
# ---------------------------------------------------------------------------

async def financial_statements_report(
    db: AsyncSession,
    *,
    period_id: int | None = None,
) -> dict:
    """Combined balance sheet and income statement."""
    categories = {}
    for cat in AccountCategory:
        accounts = await db.execute(
            select(GLAccount)
            .where(GLAccount.account_category == cat, GLAccount.status != AccountStatus.CLOSED)
            .order_by(GLAccount.account_code)
        )
        items = []
        total = 0.0
        for acct in accounts.scalars().all():
            bal = await get_account_balance(db, acct.id, period_id=period_id)
            if bal["balance"] == 0:
                continue
            items.append({
                "account_code": acct.account_code,
                "account_name": acct.name,
                "level": acct.level,
                "balance": bal["balance"],
            })
            total += bal["balance"]
        categories[cat.value] = {"items": items, "total": round(total, 2)}

    assets = categories.get("asset", {}).get("total", 0)
    liabilities = categories.get("liability", {}).get("total", 0)
    equity = categories.get("equity", {}).get("total", 0)
    revenue = categories.get("revenue", {}).get("total", 0)
    expenses = categories.get("expense", {}).get("total", 0)
    net_income = round(revenue - expenses, 2)

    # Accounting equation: A = L + E + (Revenue − Expenses)
    is_balanced = abs(assets - (liabilities + equity + net_income)) < 0.01

    return {
        "balance_sheet": {
            "assets": categories.get("asset", {}),
            "liabilities": categories.get("liability", {}),
            "equity": categories.get("equity", {}),
            "retained_earnings": net_income,
            "is_balanced": is_balanced,
        },
        "income_statement": {
            "revenue": categories.get("revenue", {}),
            "expenses": categories.get("expense", {}),
            "net_income": net_income,
        },
    }


# ---------------------------------------------------------------------------
# Report registry
# ---------------------------------------------------------------------------

REPORT_REGISTRY = {
    "gl_detail": {
        "name": "GL Detail Report",
        "description": "Every posted journal entry line with full detail",
        "fn": gl_detail_report,
    },
    "trial_balance": {
        "name": "Trial Balance",
        "description": "All accounts with debit/credit balances",
        "fn": trial_balance_report,
    },
    "journal_register": {
        "name": "Journal Entry Register",
        "description": "All journal entries with totals",
        "fn": journal_register,
    },
    "account_activity": {
        "name": "Account Activity Report",
        "description": "All transactions for a specific account",
        "fn": account_activity_report,
    },
    "subsidiary_ledger": {
        "name": "Subsidiary Ledger Report",
        "description": "Subsidiary breakdown under a control account",
        "fn": subsidiary_ledger_report,
    },
    "loan_portfolio": {
        "name": "Loan Portfolio GL Summary",
        "description": "Summary of the loan portfolio from GL perspective",
        "fn": loan_portfolio_summary,
    },
    "interest_accrual": {
        "name": "Interest Accrual Report",
        "description": "Interest accrual entries by period",
        "fn": interest_accrual_report,
    },
    "provision_movement": {
        "name": "Provision Movement Report",
        "description": "Provision expense and allowance movements",
        "fn": provision_movement_report,
    },
    "suspense_aging": {
        "name": "Suspense Account Aging",
        "description": "Items in suspense accounts with aging",
        "fn": suspense_aging_report,
    },
    "audit_trail": {
        "name": "Audit Trail Report",
        "description": "Chart of accounts modification history",
        "fn": audit_trail_report,
    },
    "reconciliation": {
        "name": "Reconciliation Report",
        "description": "Control vs subsidiary account reconciliation",
        "fn": reconciliation_report,
    },
    "financial_statements": {
        "name": "Financial Statements",
        "description": "Combined balance sheet and income statement",
        "fn": financial_statements_report,
    },
}
