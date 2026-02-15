"""Reconciliation assistant.

Provides automated reconciliation capabilities:
- Auto-match subsidiary entries to control totals
- Identify discrepancies with suggested corrective entries
- Flag stale suspense items
- Generate reconciliation narratives
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
    AccountStatus,
)
from app.services.gl.coa_service import get_account_balance, get_account_by_code

logger = logging.getLogger(__name__)


async def reconcile_control_account(
    db: AsyncSession,
    control_code: str = "1-2000",
    *,
    period_id: int | None = None,
) -> dict:
    """Reconcile a control account against its subsidiaries.

    Returns the reconciliation result with any discrepancies and
    suggested corrective entries.
    """
    control = await get_account_by_code(db, control_code)
    if not control:
        return {"error": f"Control account {control_code} not found"}

    # Control balance aggregates all descendants (children, grandchildren, …)
    control_bal = await get_account_balance(
        db, control.id, period_id=period_id, include_children=True,
    )

    # Get direct children for the subsidiary breakdown
    children = await db.execute(
        select(GLAccount)
        .where(GLAccount.parent_id == control.id, GLAccount.status != AccountStatus.CLOSED)
        .order_by(GLAccount.account_code)
    )

    subsidiary_total = 0.0
    subsidiaries = []
    for child in children.scalars().all():
        bal = await get_account_balance(
            db, child.id, period_id=period_id, include_children=True,
        )
        subsidiary_total += bal["balance"]
        subsidiaries.append({
            "account_code": child.account_code,
            "account_name": child.name,
            "balance": bal["balance"],
        })

    difference = round(control_bal["balance"] - subsidiary_total, 2)
    is_reconciled = abs(difference) < 0.01

    # Generate narrative
    narrative = (
        f"Reconciliation of {control.name} ({control_code}): "
        f"Control balance is ${control_bal['balance']:,.2f}, "
        f"subsidiary total is ${subsidiary_total:,.2f}. "
    )
    if is_reconciled:
        narrative += "The account is fully reconciled."
    else:
        narrative += (
            f"There is a discrepancy of ${abs(difference):,.2f}. "
            f"A corrective journal entry may be needed."
        )

    # Suggest corrective entry if unreconciled
    suggested_entry = None
    if not is_reconciled:
        suspense = await get_account_by_code(db, "1-9000")
        if suspense:
            if difference > 0:
                suggested_entry = {
                    "description": f"Reconciliation adjustment for {control_code}",
                    "lines": [
                        {"account_code": "1-9000", "debit": 0, "credit": abs(difference)},
                        {"account_code": control_code, "debit": abs(difference), "credit": 0},
                    ],
                }
            else:
                suggested_entry = {
                    "description": f"Reconciliation adjustment for {control_code}",
                    "lines": [
                        {"account_code": control_code, "debit": 0, "credit": abs(difference)},
                        {"account_code": "1-9000", "debit": abs(difference), "credit": 0},
                    ],
                }

    return {
        "control_account": control_code,
        "control_name": control.name,
        "control_balance": control_bal["balance"],
        "subsidiary_total": round(subsidiary_total, 2),
        "difference": difference,
        "is_reconciled": is_reconciled,
        "subsidiaries": subsidiaries,
        "narrative": narrative,
        "suggested_corrective_entry": suggested_entry,
    }


async def find_stale_suspense_items(
    db: AsyncSession,
    *,
    days_threshold: int = 30,
) -> list[dict]:
    """Find entries in suspense accounts older than the threshold."""
    today = date.today()
    cutoff = today - timedelta(days=days_threshold)

    # Find suspense accounts
    suspense_accounts = await db.execute(
        select(GLAccount).where(
            GLAccount.account_code.like("%-9%"),
            GLAccount.status == AccountStatus.ACTIVE,
        )
    )

    stale_items = []
    for acct in suspense_accounts.scalars().all():
        # Find old posted entries for this account
        result = await db.execute(
            select(JournalEntryLine, JournalEntry)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .where(
                JournalEntryLine.gl_account_id == acct.id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.effective_date < cutoff,
            )
            .order_by(JournalEntry.effective_date)
        )

        for line, entry in result.all():
            age_days = (today - entry.effective_date).days
            amount = float(line.debit_amount) if line.debit_amount > 0 else float(line.credit_amount)
            stale_items.append({
                "account_code": acct.account_code,
                "account_name": acct.name,
                "entry_number": entry.entry_number,
                "date": str(entry.effective_date),
                "amount": amount,
                "age_days": age_days,
                "description": line.description or entry.description,
                "urgency": "high" if age_days > 90 else ("medium" if age_days > 60 else "low"),
            })

    return sorted(stale_items, key=lambda x: x["age_days"], reverse=True)


async def auto_match_entries(
    db: AsyncSession,
    account_id: int,
    *,
    tolerance: float = 0.01,
) -> list[dict]:
    """Find entries in an account that can be matched (netted off).

    Useful for suspense/clearing accounts where debits should match credits.
    """
    # Get all posted lines for this account
    result = await db.execute(
        select(JournalEntryLine, JournalEntry)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .where(
            JournalEntryLine.gl_account_id == account_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
        .order_by(JournalEntry.effective_date)
    )

    debits = []
    credits = []
    for line, entry in result.all():
        item = {
            "entry_id": entry.id,
            "entry_number": entry.entry_number,
            "date": str(entry.effective_date),
            "amount": float(line.debit_amount if line.debit_amount > 0 else line.credit_amount),
            "type": "debit" if line.debit_amount > 0 else "credit",
            "description": line.description or entry.description,
        }
        if line.debit_amount > 0:
            debits.append(item)
        else:
            credits.append(item)

    # Simple matching: find debit/credit pairs with matching amounts
    matches = []
    used_credits = set()

    for dr in debits:
        for i, cr in enumerate(credits):
            if i in used_credits:
                continue
            if abs(dr["amount"] - cr["amount"]) <= tolerance:
                matches.append({
                    "debit": dr,
                    "credit": cr,
                    "amount": dr["amount"],
                    "match_confidence": 1.0 if dr["amount"] == cr["amount"] else 0.95,
                })
                used_credits.add(i)
                break

    unmatched_debits = [dr for dr in debits if not any(m["debit"]["entry_id"] == dr["entry_id"] for m in matches)]
    unmatched_credits = [cr for i, cr in enumerate(credits) if i not in used_credits]

    return {
        "matched_pairs": matches,
        "unmatched_debits": unmatched_debits,
        "unmatched_credits": unmatched_credits,
        "match_rate": round(len(matches) / max(len(debits), 1), 2),
    }
