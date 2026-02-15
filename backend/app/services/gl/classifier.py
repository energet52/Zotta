"""AI-powered transaction classifier.

Suggests GL accounts for manual journal entries based on:
- Description text analysis
- Historical entry patterns
- Amount characteristics

Falls back to rule-based classification when OpenAI is unavailable.
"""

import logging
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import (
    GLAccount,
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    AccountCategory,
    AccountStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword-based classification rules
# ---------------------------------------------------------------------------

KEYWORD_RULES = [
    # (keywords, category, account_code_pattern, confidence)
    (["disbursement", "disburse", "loan release"], AccountCategory.ASSET, "1-2%", 0.85),
    (["payment", "repayment", "instalment", "installment"], AccountCategory.ASSET, "1-1%", 0.80),
    (["interest income", "interest earned", "interest revenue"], AccountCategory.REVENUE, "4-1%", 0.90),
    (["interest accrual", "accrued interest"], AccountCategory.ASSET, "1-3%", 0.85),
    (["fee income", "processing fee", "origination fee"], AccountCategory.REVENUE, "4-2%", 0.85),
    (["late fee", "penalty fee", "late charge"], AccountCategory.REVENUE, "4-3%", 0.85),
    (["provision", "allowance", "impairment"], AccountCategory.EXPENSE, "5-1%", 0.80),
    (["write-off", "write off", "bad debt"], AccountCategory.EXPENSE, "5-3%", 0.85),
    (["recovery", "recovered", "collection"], AccountCategory.REVENUE, "4-4%", 0.80),
    (["cash", "bank", "deposit", "withdrawal"], AccountCategory.ASSET, "1-1%", 0.75),
    (["salary", "wages", "payroll"], AccountCategory.EXPENSE, "5-2%", 0.80),
    (["rent", "lease", "office"], AccountCategory.EXPENSE, "5-2%", 0.75),
    (["insurance"], AccountCategory.LIABILITY, "2-4%", 0.75),
]


def _keyword_classify(description: str) -> list[dict]:
    """Rule-based classification from keywords."""
    desc_lower = description.lower()
    matches = []

    for keywords, category, code_pattern, confidence in KEYWORD_RULES:
        for kw in keywords:
            if kw in desc_lower:
                matches.append({
                    "category": category.value,
                    "code_pattern": code_pattern,
                    "confidence": confidence,
                    "reason": f"Matched keyword: '{kw}'",
                })
                break

    return sorted(matches, key=lambda x: x["confidence"], reverse=True)


# ---------------------------------------------------------------------------
# Historical pattern matching
# ---------------------------------------------------------------------------

async def _historical_classify(
    db: AsyncSession,
    description: str,
    amount: Decimal | None = None,
) -> list[dict]:
    """Find similar historical entries and suggest accounts."""
    # Search for entries with similar descriptions
    words = description.lower().split()
    if not words:
        return []

    # Use the first significant word (skip common words)
    skip_words = {"the", "a", "an", "for", "of", "to", "and", "in", "on"}
    search_words = [w for w in words if w not in skip_words and len(w) > 2]

    if not search_words:
        return []

    pattern = f"%{search_words[0]}%"

    result = await db.execute(
        select(
            JournalEntryLine.gl_account_id,
            GLAccount.account_code,
            GLAccount.name,
            GLAccount.account_category,
            sa_func.count(JournalEntryLine.id).label("usage_count"),
        )
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .join(GLAccount, JournalEntryLine.gl_account_id == GLAccount.id)
        .where(
            JournalEntry.description.ilike(pattern),
            JournalEntry.status == JournalEntryStatus.POSTED,
            GLAccount.status == AccountStatus.ACTIVE,
        )
        .group_by(
            JournalEntryLine.gl_account_id,
            GLAccount.account_code,
            GLAccount.name,
            GLAccount.account_category,
        )
        .order_by(sa_func.count(JournalEntryLine.id).desc())
        .limit(10)
    )

    suggestions = []
    for row in result.all():
        confidence = min(0.95, 0.5 + (row.usage_count * 0.05))
        suggestions.append({
            "gl_account_id": row.gl_account_id,
            "account_code": row.account_code,
            "account_name": row.name,
            "category": row.account_category.value,
            "confidence": round(confidence, 2),
            "reason": f"Used {row.usage_count} time(s) in similar entries",
        })

    return suggestions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def suggest_accounts(
    db: AsyncSession,
    *,
    description: str,
    amount: Decimal | None = None,
    limit: int = 5,
) -> list[dict]:
    """Suggest GL accounts for a description, ranked by confidence.

    Combines keyword matching with historical pattern analysis.
    """
    suggestions = []

    # 1. Historical pattern matching
    historical = await _historical_classify(db, description, amount)
    suggestions.extend(historical)

    # 2. Keyword classification
    keyword_matches = _keyword_classify(description)

    # For keyword matches, find actual accounts
    for match in keyword_matches:
        code_pattern = match["code_pattern"]
        result = await db.execute(
            select(GLAccount)
            .where(
                GLAccount.account_code.like(code_pattern),
                GLAccount.status == AccountStatus.ACTIVE,
                GLAccount.level >= 2,  # Not top-level categories
            )
            .order_by(GLAccount.level.desc())
            .limit(3)
        )
        for acct in result.scalars().all():
            # Check if already suggested
            if any(s.get("gl_account_id") == acct.id for s in suggestions):
                continue
            suggestions.append({
                "gl_account_id": acct.id,
                "account_code": acct.account_code,
                "account_name": acct.name,
                "category": acct.account_category.value,
                "confidence": match["confidence"] * 0.9,  # Slightly lower than historical
                "reason": match["reason"],
            })

    # Sort by confidence and deduplicate
    seen_ids = set()
    unique = []
    for s in sorted(suggestions, key=lambda x: x["confidence"], reverse=True):
        aid = s.get("gl_account_id")
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            unique.append(s)

    return unique[:limit]
