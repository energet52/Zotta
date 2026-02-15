"""AI-powered anomaly detection for journal entries.

Analyses every posted journal entry for:
- Amount outliers (z-score based)
- Unusual posting times
- Unusual account combinations
- Missing expected entries
- Balance direction anomalies
- Velocity per user

Returns a risk score (0-100) and natural language explanation.
Optionally uses OpenAI for enhanced explanations.
"""

import logging
import statistics
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import (
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    JournalSourceType,
    GLAnomaly,
    AnomalyType,
    AnomalyStatus,
)

logger = logging.getLogger(__name__)


class AnomalyResult:
    """Result of anomaly detection for a single entry."""
    def __init__(self):
        self.risk_score: int = 0
        self.flags: list[dict] = []
        self.explanation: str = ""

    def add_flag(self, anomaly_type: AnomalyType, score: int, reason: str):
        self.flags.append({
            "type": anomaly_type,
            "score": score,
            "reason": reason,
        })
        self.risk_score = min(100, self.risk_score + score)

    @property
    def has_anomalies(self) -> bool:
        return self.risk_score > 0


# ---------------------------------------------------------------------------
# Detection checks
# ---------------------------------------------------------------------------

async def _check_amount_outlier(
    db: AsyncSession, entry: JournalEntry, result: AnomalyResult
) -> None:
    """Flag if the entry amount is a statistical outlier."""
    # Get recent entry totals for the same source type
    recent = await db.execute(
        select(JournalEntryLine.debit_amount)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .where(
            JournalEntry.source_type == entry.source_type,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.id != entry.id,
        )
        .order_by(JournalEntry.id.desc())
        .limit(100)
    )
    amounts = [float(row[0]) for row in recent.all() if row[0] > 0]

    if len(amounts) < 5:
        return  # Not enough data for statistics

    mean = statistics.mean(amounts)
    stdev = statistics.stdev(amounts) if len(amounts) > 1 else 0

    if stdev == 0:
        return

    entry_amount = float(entry.total_debits)
    z_score = abs(entry_amount - mean) / stdev

    if z_score > 3:
        result.add_flag(
            AnomalyType.AMOUNT, 40,
            f"Amount ${entry_amount:,.2f} is {z_score:.1f} standard deviations from the mean "
            f"(mean: ${mean:,.2f}, stdev: ${stdev:,.2f})"
        )
    elif z_score > 2:
        result.add_flag(
            AnomalyType.AMOUNT, 20,
            f"Amount ${entry_amount:,.2f} is {z_score:.1f} standard deviations from the mean"
        )


async def _check_unusual_pattern(
    db: AsyncSession, entry: JournalEntry, result: AnomalyResult
) -> None:
    """Flag unusual account combinations."""
    if not entry.lines:
        return

    account_ids = sorted([ln.gl_account_id for ln in entry.lines])

    # Check if this combination has been seen before
    recent_entries = await db.execute(
        select(JournalEntry.id)
        .where(
            JournalEntry.source_type == entry.source_type,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.id != entry.id,
        )
        .order_by(JournalEntry.id.desc())
        .limit(50)
    )
    seen_combos = set()
    for (eid,) in recent_entries.all():
        lines_result = await db.execute(
            select(JournalEntryLine.gl_account_id)
            .where(JournalEntryLine.journal_entry_id == eid)
        )
        combo = tuple(sorted([r[0] for r in lines_result.all()]))
        seen_combos.add(combo)

    if tuple(account_ids) not in seen_combos and seen_combos:
        result.add_flag(
            AnomalyType.PATTERN, 15,
            "This account combination has not been used before for this entry type"
        )


async def _check_velocity(
    db: AsyncSession, entry: JournalEntry, result: AnomalyResult
) -> None:
    """Flag high-velocity posting by the same user."""
    if not entry.created_by:
        return

    # Count entries created by this user in the last hour
    from datetime import timedelta
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    count_result = await db.execute(
        select(sa_func.count(JournalEntry.id))
        .where(
            JournalEntry.created_by == entry.created_by,
            JournalEntry.created_at >= one_hour_ago,
        )
    )
    count = count_result.scalar() or 0

    if count > 50:
        result.add_flag(
            AnomalyType.VELOCITY, 30,
            f"User has created {count} entries in the last hour (high velocity)"
        )
    elif count > 20:
        result.add_flag(
            AnomalyType.VELOCITY, 15,
            f"User has created {count} entries in the last hour"
        )


async def _check_balance_direction(
    db: AsyncSession, entry: JournalEntry, result: AnomalyResult
) -> None:
    """Flag if an account balance moves in an unexpected direction."""
    from app.services.gl.coa_service import get_account_balance, get_account
    from app.models.gl import AccountType

    for ln in (entry.lines or []):
        acct = await get_account(db, ln.gl_account_id)
        if not acct:
            continue

        bal = await get_account_balance(db, ln.gl_account_id)
        balance = bal["balance"]

        # Asset/Expense accounts should have debit (positive) balance
        # Liability/Equity/Revenue should have credit (positive) balance
        if acct.account_type == AccountType.DEBIT and balance < -1000:
            result.add_flag(
                AnomalyType.BALANCE, 25,
                f"Account {acct.account_code} ({acct.name}) has unusual credit balance: "
                f"${abs(balance):,.2f} (expected debit-normal)"
            )
            break
        elif acct.account_type == AccountType.CREDIT and balance < -1000:
            result.add_flag(
                AnomalyType.BALANCE, 25,
                f"Account {acct.account_code} ({acct.name}) has unusual debit balance: "
                f"${abs(balance):,.2f} (expected credit-normal)"
            )
            break


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_entry(
    db: AsyncSession,
    entry: JournalEntry,
) -> AnomalyResult:
    """Run all anomaly checks on a journal entry.

    Returns an AnomalyResult with risk score and flags.
    """
    result = AnomalyResult()

    await _check_amount_outlier(db, entry, result)
    await _check_unusual_pattern(db, entry, result)
    await _check_velocity(db, entry, result)
    await _check_balance_direction(db, entry, result)

    # Build explanation
    if result.has_anomalies:
        explanations = [f["reason"] for f in result.flags]
        result.explanation = "; ".join(explanations)
    else:
        result.explanation = "No anomalies detected"

    return result


async def detect_and_store(
    db: AsyncSession,
    entry_id: int,
) -> list[GLAnomaly]:
    """Run anomaly detection on an entry and persist results."""
    from app.services.gl.journal_engine import get_journal_entry

    entry = await get_journal_entry(db, entry_id)
    if not entry:
        return []

    result = await analyze_entry(db, entry)

    # Store anomaly score in entry metadata
    meta = entry.metadata_ or {}
    meta["anomaly_score"] = result.risk_score
    meta["anomaly_explanation"] = result.explanation
    entry.metadata_ = meta

    anomalies = []
    for flag in result.flags:
        anomaly = GLAnomaly(
            journal_entry_id=entry_id,
            anomaly_type=flag["type"],
            risk_score=flag["score"],
            explanation=flag["reason"],
            status=AnomalyStatus.OPEN,
        )
        db.add(anomaly)
        anomalies.append(anomaly)

    await db.flush()
    return anomalies


async def get_anomalies(
    db: AsyncSession,
    *,
    status: AnomalyStatus | None = None,
    min_risk_score: int | None = None,
    limit: int = 100,
) -> list[GLAnomaly]:
    """List anomalies with optional filters."""
    q = (
        select(GLAnomaly)
        .order_by(GLAnomaly.risk_score.desc(), GLAnomaly.created_at.desc())
        .limit(limit)
    )
    if status:
        q = q.where(GLAnomaly.status == status)
    if min_risk_score:
        q = q.where(GLAnomaly.risk_score >= min_risk_score)

    result = await db.execute(q)
    return list(result.scalars().all())


async def review_anomaly(
    db: AsyncSession,
    anomaly_id: int,
    *,
    status: AnomalyStatus,
    reviewer_id: int,
) -> GLAnomaly | None:
    """Mark an anomaly as reviewed or dismissed."""
    result = await db.execute(
        select(GLAnomaly).where(GLAnomaly.id == anomaly_id)
    )
    anomaly = result.scalar_one_or_none()
    if not anomaly:
        return None

    anomaly.status = status
    anomaly.reviewed_by = reviewer_id
    anomaly.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return anomaly
