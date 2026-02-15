"""Natural language query engine for the General Ledger.

Parses natural language questions and converts them into structured GL queries.
Uses pattern matching for common question types, with optional OpenAI
enhancement for complex queries.
"""

import logging
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import (
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    JournalSourceType,
    GLAccount,
    AccountCategory,
    AccountStatus,
    AccountingPeriod,
)
from app.services.gl.coa_service import get_account_balance, get_account_by_code

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query patterns
# ---------------------------------------------------------------------------

PATTERNS = [
    # Net income (must be before generic "show" patterns)
    (r"(?:what is|show|calculate)\s+(?:the\s+)?net\s+income",
     "net_income"),

    # Trial balance (must be before generic "show" patterns)
    (r"(?:show|get|run)\s+(?:the\s+)?trial\s+balance",
     "trial_balance"),

    # Balance queries
    (r"(?:what is|show|get)\s+(?:the\s+)?balance\s+(?:of|for|in)\s+(.+)",
     "account_balance"),
    (r"(?:how much|what)\s+(?:is|are)\s+(?:the\s+)?(?:total\s+)?(.+?)(?:\s+balance)?$",
     "account_balance"),

    # Entry count queries
    (r"how many\s+(?:journal\s+)?entries\s+(?:are|were)\s+(.+)",
     "entry_count"),
    (r"count\s+(?:of\s+)?entries\s+(.+)",
     "entry_count"),

    # Total queries
    (r"(?:what is|show)\s+(?:the\s+)?total\s+(.+?)(?:\s+for\s+(.+))?$",
     "total_amount"),

    # Top/largest (before generic list)
    (r"(?:what are|show)\s+(?:the\s+)?(?:top|largest|biggest)\s+(\d+)?\s*(.+)",
     "top_entries"),

    # List/show queries (catch-all, must be last)
    (r"(?:show|list|display)\s+(?:all\s+)?(.+?)(?:\s+for\s+(.+))?$",
     "list_entries"),
]


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------

async def _handle_account_balance(
    db: AsyncSession, match_groups: tuple, context: dict
) -> dict:
    """Handle 'what is the balance of...' queries."""
    account_query = match_groups[0].strip().rstrip("?")

    # Try to find account by name or code
    acct = await get_account_by_code(db, account_query)
    if not acct:
        # Search by name
        result = await db.execute(
            select(GLAccount)
            .where(GLAccount.name.ilike(f"%{account_query}%"))
            .limit(1)
        )
        acct = result.scalar_one_or_none()

    if not acct:
        return {
            "type": "error",
            "message": f"Could not find account matching '{account_query}'",
            "query_used": f"Search for account: {account_query}",
        }

    bal = await get_account_balance(db, acct.id, include_children=True)
    return {
        "type": "number",
        "value": bal["balance"],
        "formatted": f"${bal['balance']:,.2f}",
        "summary": (
            f"The balance of {acct.name} ({acct.account_code}) is ${bal['balance']:,.2f}. "
            f"Total debits: ${bal['debit_total']:,.2f}, total credits: ${bal['credit_total']:,.2f}."
        ),
        "query_used": f"SELECT balance FROM gl_accounts WHERE code = '{acct.account_code}'",
        "data": [{"account": acct.account_code, "name": acct.name, **bal}],
    }


async def _handle_entry_count(
    db: AsyncSession, match_groups: tuple, context: dict
) -> dict:
    """Handle 'how many entries...' queries."""
    condition = match_groups[0].strip().rstrip("?")

    q = select(sa_func.count(JournalEntry.id))

    if "posted" in condition.lower():
        q = q.where(JournalEntry.status == JournalEntryStatus.POSTED)
    elif "draft" in condition.lower():
        q = q.where(JournalEntry.status == JournalEntryStatus.DRAFT)
    elif "pending" in condition.lower():
        q = q.where(JournalEntry.status == JournalEntryStatus.PENDING_APPROVAL)
    elif "reversed" in condition.lower():
        q = q.where(JournalEntry.status == JournalEntryStatus.REVERSED)

    result = await db.execute(q)
    count = result.scalar() or 0

    return {
        "type": "number",
        "value": count,
        "formatted": f"{count:,}",
        "summary": f"There are {count:,} journal entries matching '{condition}'.",
        "query_used": f"SELECT COUNT(*) FROM journal_entries WHERE {condition}",
    }


async def _handle_net_income(
    db: AsyncSession, match_groups: tuple, context: dict
) -> dict:
    """Calculate net income (Revenue - Expenses)."""
    revenue_result = await db.execute(
        select(
            sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount), 0) -
            sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount), 0)
        )
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .join(GLAccount, JournalEntryLine.gl_account_id == GLAccount.id)
        .where(
            GLAccount.account_category == AccountCategory.REVENUE,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )
    revenue = float(revenue_result.scalar() or 0)

    expense_result = await db.execute(
        select(
            sa_func.coalesce(sa_func.sum(JournalEntryLine.debit_amount), 0) -
            sa_func.coalesce(sa_func.sum(JournalEntryLine.credit_amount), 0)
        )
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .join(GLAccount, JournalEntryLine.gl_account_id == GLAccount.id)
        .where(
            GLAccount.account_category == AccountCategory.EXPENSE,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )
    expenses = float(expense_result.scalar() or 0)

    net = revenue - expenses
    return {
        "type": "number",
        "value": net,
        "formatted": f"${net:,.2f}",
        "summary": (
            f"Net income is ${net:,.2f}. "
            f"Total revenue: ${revenue:,.2f}, total expenses: ${expenses:,.2f}."
        ),
        "query_used": "Revenue - Expenses from posted entries",
        "data": [
            {"item": "Revenue", "amount": revenue},
            {"item": "Expenses", "amount": expenses},
            {"item": "Net Income", "amount": net},
        ],
    }


async def _handle_trial_balance(
    db: AsyncSession, match_groups: tuple, context: dict
) -> dict:
    """Generate a quick trial balance summary."""
    from app.services.gl.reports_service import trial_balance_report

    rows = await trial_balance_report(db, level=2)
    total_dr = sum(r["debit_balance"] for r in rows)
    total_cr = sum(r["credit_balance"] for r in rows)
    balanced = abs(total_dr - total_cr) < 0.01

    return {
        "type": "table",
        "summary": (
            f"Trial balance has {len(rows)} accounts. "
            f"Total debits: ${total_dr:,.2f}, credits: ${total_cr:,.2f}. "
            f"{'Balanced' if balanced else f'UNBALANCED by ${abs(total_dr - total_cr):,.2f}'}."
        ),
        "query_used": "Trial balance at level 2",
        "data": rows,
        "columns": ["account_code", "account_name", "category", "debit_balance", "credit_balance"],
    }


async def _handle_list_entries(
    db: AsyncSession, match_groups: tuple, context: dict
) -> dict:
    """List recent entries."""
    what = match_groups[0].strip().rstrip("?") if match_groups[0] else ""

    q = (
        select(JournalEntry)
        .where(JournalEntry.status == JournalEntryStatus.POSTED)
        .order_by(JournalEntry.id.desc())
        .limit(20)
    )

    if "disbursement" in what.lower():
        q = q.where(JournalEntry.source_type == JournalSourceType.LOAN_DISBURSEMENT)
    elif "payment" in what.lower() or "repayment" in what.lower():
        q = q.where(JournalEntry.source_type == JournalSourceType.REPAYMENT)
    elif "reversal" in what.lower():
        q = q.where(JournalEntry.source_type == JournalSourceType.REVERSAL)

    result = await db.execute(q)
    entries = result.scalars().all()

    data = [
        {
            "entry_number": e.entry_number,
            "date": str(e.effective_date),
            "description": e.description[:80],
            "source_type": e.source_type.value,
            "total": float(e.total_debits),
            "status": e.status.value,
        }
        for e in entries
    ]

    return {
        "type": "table",
        "summary": f"Found {len(data)} entries matching '{what}'.",
        "query_used": f"Recent journal entries: {what}",
        "data": data,
        "columns": ["entry_number", "date", "description", "source_type", "total", "status"],
    }


async def _handle_top_entries(
    db: AsyncSession, match_groups: tuple, context: dict
) -> dict:
    """Show top N entries by amount."""
    count_str, what = match_groups
    n = int(count_str) if count_str else 10

    result = await db.execute(
        select(JournalEntry)
        .where(JournalEntry.status == JournalEntryStatus.POSTED)
        .order_by(JournalEntry.id.desc())
        .limit(200)
    )
    entries = sorted(
        result.scalars().all(),
        key=lambda e: float(e.total_debits),
        reverse=True,
    )[:n]

    data = [
        {
            "entry_number": e.entry_number,
            "date": str(e.effective_date),
            "description": e.description[:60],
            "amount": float(e.total_debits),
        }
        for e in entries
    ]

    return {
        "type": "table",
        "summary": f"Top {n} entries by amount.",
        "query_used": f"Top {n} journal entries ordered by amount DESC",
        "data": data,
        "columns": ["entry_number", "date", "description", "amount"],
    }


# ---------------------------------------------------------------------------
# Query dispatch
# ---------------------------------------------------------------------------

HANDLERS = {
    "account_balance": _handle_account_balance,
    "entry_count": _handle_entry_count,
    "net_income": _handle_net_income,
    "trial_balance": _handle_trial_balance,
    "list_entries": _handle_list_entries,
    "top_entries": _handle_top_entries,
    "total_amount": _handle_account_balance,  # Reuse
}


async def process_query(
    db: AsyncSession,
    question: str,
    *,
    context: dict | None = None,
) -> dict:
    """Parse a natural language question and execute the corresponding GL query.

    Returns structured data with a natural language summary.
    """
    ctx = context or {}
    question = question.strip()

    for pattern, handler_key in PATTERNS:
        match = re.match(pattern, question, re.IGNORECASE)
        if match:
            handler = HANDLERS.get(handler_key)
            if handler:
                try:
                    return await handler(db, match.groups(), ctx)
                except Exception as e:
                    logger.error("NL query handler error: %s", e)
                    return {
                        "type": "error",
                        "message": f"Error processing query: {str(e)}",
                        "query_used": f"Pattern: {handler_key}",
                    }

    # Fallback: try to search descriptions
    return {
        "type": "suggestion",
        "message": (
            "I couldn't parse that query. Try asking something like:\n"
            "- 'What is the balance of Performing Loans?'\n"
            "- 'How many entries are posted?'\n"
            "- 'Show net income'\n"
            "- 'Show the trial balance'\n"
            "- 'List all disbursement entries'\n"
            "- 'Show top 10 entries'"
        ),
        "query_used": None,
    }
