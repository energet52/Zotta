"""Queue priority scoring engine.

Computes a float score for each QueueEntry (higher = work sooner).
Factors: time aging, return priority, value signal, borrower engagement, completeness.
All weights configurable via QueueConfig.ai_config.
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import QueueConfig, QueueEntry, QueueEntryStatus
from app.models.loan import LoanApplication, LoanStatus
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "time_aging": 0.40,
    "return_priority": 0.25,
    "value_signal": 0.15,
    "borrower_engagement": 0.10,
    "completeness": 0.10,
}


def _get_weights(config: QueueConfig | None) -> dict:
    if config and config.ai_config and "priority_weights" in config.ai_config:
        return {**DEFAULT_WEIGHTS, **config.ai_config["priority_weights"]}
    return DEFAULT_WEIGHTS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def compute_priority(
    entry: QueueEntry,
    application: LoanApplication,
    config: QueueConfig | None = None,
    portfolio_median_amount: float = 50000.0,
) -> tuple[float, dict]:
    """Compute priority score and factor breakdown for a single entry."""
    weights = _get_weights(config)
    now = _now()
    factors: dict[str, Any] = {}

    # 1. Time aging: log-scaled hours since submission
    submitted = application.submitted_at or application.created_at
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)
    hours_waiting = max(0.1, (now - submitted).total_seconds() / 3600)
    time_score = min(1.0, math.log1p(hours_waiting) / math.log1p(720))  # 30 days = 1.0
    factors["time_aging"] = {
        "hours_waiting": round(hours_waiting, 1),
        "score": round(time_score, 3),
    }

    # 2. Return priority: boost for borrower-responded apps
    return_score = 0.0
    if entry.return_count > 0 and entry.status == QueueEntryStatus.NEW.value:
        return_score = min(1.0, 0.6 + 0.1 * entry.return_count)
    elif entry.status == QueueEntryStatus.NEW.value and entry.waiting_since is None and entry.return_count > 0:
        return_score = 0.8
    factors["return_priority"] = {
        "return_count": entry.return_count,
        "score": round(return_score, 3),
    }

    # 3. Value signal: amount normalized against portfolio median
    amount = float(application.amount_requested or 0)
    if portfolio_median_amount > 0:
        value_score = min(1.0, amount / (portfolio_median_amount * 3))
    else:
        value_score = 0.5
    factors["value_signal"] = {
        "amount": amount,
        "median": portfolio_median_amount,
        "score": round(value_score, 3),
    }

    # 4. Borrower engagement: recent activity signals
    engagement_score = 0.3  # baseline
    if entry.return_count > 0:
        engagement_score += 0.3
    if entry.completeness_score and entry.completeness_score > 80:
        engagement_score += 0.2
    engagement_score = min(1.0, engagement_score)
    factors["borrower_engagement"] = {"score": round(engagement_score, 3)}

    # 5. Completeness
    completeness_score = (entry.completeness_score or 50.0) / 100.0
    factors["completeness"] = {
        "raw": entry.completeness_score,
        "score": round(completeness_score, 3),
    }

    # Weighted sum
    total = (
        weights["time_aging"] * time_score
        + weights["return_priority"] * return_score
        + weights["value_signal"] * value_score
        + weights["borrower_engagement"] * engagement_score
        + weights["completeness"] * completeness_score
    )

    # Deterministic tiebreaker: earlier application_id wins (tiny contribution)
    tiebreaker = 1.0 / (1.0 + entry.application_id)
    total += tiebreaker * 0.001

    # Stuck boost
    if entry.is_stuck:
        total += 0.15

    # Flagged boost
    if entry.is_flagged:
        total += 0.05

    factors["total"] = round(total, 5)
    return (round(total, 5), factors)


async def recalculate_all_priorities(db: AsyncSession) -> int:
    """Batch recalculate priority scores for all active queue entries."""
    config_result = await db.execute(select(QueueConfig).limit(1))
    config = config_result.scalar_one_or_none()

    # Get portfolio median
    median_result = await db.execute(
        select(func.percentile_cont(0.5).within_group(LoanApplication.amount_requested))
        .where(LoanApplication.status.in_([
            LoanStatus.SUBMITTED.value, LoanStatus.UNDER_REVIEW.value,
            LoanStatus.CREDIT_CHECK.value, LoanStatus.DECISION_PENDING.value,
        ]))
    )
    median_val = median_result.scalar() or 50000.0

    # Load active entries with their applications
    entries_result = await db.execute(
        select(QueueEntry, LoanApplication)
        .join(LoanApplication, QueueEntry.application_id == LoanApplication.id)
        .where(QueueEntry.status.in_([
            QueueEntryStatus.NEW.value,
            QueueEntryStatus.IN_PROGRESS.value,
            QueueEntryStatus.ON_HOLD.value,
        ]))
    )

    count = 0
    for entry, application in entries_result.all():
        score, factors = compute_priority(entry, application, config, float(median_val))
        entry.priority_score = score
        entry.priority_factors = factors
        count += 1

    await db.flush()
    logger.info("Recalculated priorities for %d queue entries", count)
    return count


def explain_priority_deterministic(
    entry: QueueEntry,
    position: int,
    total: int,
) -> str:
    """Generate a deterministic explanation of why an entry is at its position."""
    factors = entry.priority_factors or {}
    parts = [f"This application is ranked #{position} of {total} in the queue."]

    time_info = factors.get("time_aging", {})
    hours = time_info.get("hours_waiting", 0)
    if hours > 48:
        parts.append(f"It has been waiting {hours:.0f} hours ({hours/24:.1f} days), which raises its priority.")
    elif hours > 0:
        parts.append(f"It has been waiting {hours:.1f} hours.")

    ret = factors.get("return_priority", {})
    if ret.get("return_count", 0) > 0:
        parts.append(
            f"The borrower has responded after being asked for information "
            f"({ret['return_count']} return(s)), giving it a significant priority boost."
        )

    val = factors.get("value_signal", {})
    amount = val.get("amount", 0)
    if amount > 0:
        parts.append(f"Loan amount: ${amount:,.0f}.")

    if entry.is_stuck:
        parts.append("This application has been flagged as potentially stuck.")

    return " ".join(parts)


async def explain_priority(entry_id: int, db: AsyncSession) -> str:
    """Explain queue position using AI if available, else deterministic."""
    entry_result = await db.execute(
        select(QueueEntry).where(QueueEntry.id == entry_id)
    )
    entry = entry_result.scalar_one_or_none()
    if not entry:
        return "Entry not found."

    # Determine position
    count_result = await db.execute(
        select(func.count()).select_from(QueueEntry).where(
            QueueEntry.status.in_([
                QueueEntryStatus.NEW.value,
                QueueEntryStatus.IN_PROGRESS.value,
            ]),
            QueueEntry.priority_score >= entry.priority_score,
        )
    )
    position = count_result.scalar() or 1

    total_result = await db.execute(
        select(func.count()).select_from(QueueEntry).where(
            QueueEntry.status.in_([
                QueueEntryStatus.NEW.value,
                QueueEntryStatus.IN_PROGRESS.value,
            ])
        )
    )
    total = total_result.scalar() or 1

    # Try AI
    if settings.openai_api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            factors_str = str(entry.priority_factors or {})
            resp = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": (
                        "You explain queue priority rankings to loan processors. "
                        "Be concise (2-3 sentences), reference specific data points, "
                        "and explain why this application should be worked before/after others."
                    )},
                    {"role": "user", "content": (
                        f"Application is ranked #{position} of {total}. "
                        f"Priority factors: {factors_str}. "
                        f"Explain this ranking in plain language."
                    )},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            return resp.choices[0].message.content or explain_priority_deterministic(entry, position, total)
        except Exception as e:
            logger.warning("AI priority explain failed: %s", e)

    return explain_priority_deterministic(entry, position, total)
