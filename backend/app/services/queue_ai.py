"""Queue AI intelligence service.

Provides: handoff summaries, stuck detection, process insights,
completeness scoring, complexity estimation, exception precedent analysis.
Uses OpenAI when available, deterministic fallbacks always.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.queue import (
    QueueEntry, QueueEntryStatus, QueueEvent, QueueException, QueueConfig,
    StaffQueueProfile,
)
from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.decision import Decision
from app.models.document import Document
from app.models.note import ApplicationNote
from app.models.audit import AuditLog
from app.config import settings

logger = logging.getLogger(__name__)


def _openai_available() -> bool:
    return bool(settings.openai_api_key)


async def _chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


# ── Completeness Scoring ──────────────────────────────────────

REQUIRED_FIELDS = [
    "first_name", "last_name", "date_of_birth", "national_id",
    "address_line1", "city", "employer_name", "monthly_income",
]

OPTIONAL_FIELDS = [
    "employer_sector", "job_title", "years_employed",
    "monthly_expenses", "existing_debt", "other_income",
    "whatsapp_number", "contact_email", "mobile_phone",
]


async def compute_completeness(application_id: int, db: AsyncSession) -> float:
    """Score 0-100 based on required and optional profile fields filled."""
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = app_result.scalar_one_or_none()
    if not application:
        return 0.0

    profile_result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == application.applicant_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        return 10.0

    filled_required = 0
    for field in REQUIRED_FIELDS:
        val = getattr(profile, field, None)
        if val is not None and str(val).strip():
            filled_required += 1

    filled_optional = 0
    for field in OPTIONAL_FIELDS:
        val = getattr(profile, field, None)
        if val is not None and str(val).strip():
            filled_optional += 1

    # Documents count
    doc_result = await db.execute(
        select(func.count()).select_from(Document)
        .where(Document.loan_application_id == application_id)
    )
    doc_count = doc_result.scalar() or 0
    doc_score = min(1.0, doc_count / 3.0)  # 3+ documents = full credit

    required_score = filled_required / max(1, len(REQUIRED_FIELDS))  # 70% weight
    optional_score = filled_optional / max(1, len(OPTIONAL_FIELDS))  # 15% weight
    # doc_score: 15% weight

    total = required_score * 70 + optional_score * 15 + doc_score * 15
    return round(total, 1)


# ── Complexity Estimation ─────────────────────────────────────

async def estimate_complexity(application_id: int, db: AsyncSession) -> float:
    """Estimate hours to process. Returns float."""
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = app_result.scalar_one_or_none()
    if not application:
        return 2.0

    amount = float(application.amount_requested or 0)
    hours = 1.0

    # Amount complexity
    if amount > 1000000:
        hours += 3.0
    elif amount > 500000:
        hours += 2.0
    elif amount > 100000:
        hours += 1.0

    # Product type complexity
    purpose = application.purpose.value if application.purpose else ""
    if purpose in ("business", "debt_consolidation"):
        hours += 1.5
    elif purpose in ("home_improvement", "vehicle"):
        hours += 0.5

    # Document count
    doc_result = await db.execute(
        select(func.count()).select_from(Document)
        .where(Document.loan_application_id == application_id)
    )
    doc_count = doc_result.scalar() or 0
    if doc_count > 5:
        hours += 1.0

    return round(hours, 1)


# ── Handoff Summary ───────────────────────────────────────────

async def generate_handoff_summary(application_id: int, db: AsyncSession) -> str:
    """Generate a brief summary of work done on an application for the next person."""
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = app_result.scalar_one_or_none()
    if not application:
        return "Application not found."

    # Gather context
    notes_result = await db.execute(
        select(ApplicationNote)
        .where(ApplicationNote.application_id == application_id)
        .order_by(ApplicationNote.created_at.desc())
        .limit(5)
    )
    notes = notes_result.scalars().all()

    decisions_result = await db.execute(
        select(Decision)
        .where(Decision.loan_application_id == application_id)
        .order_by(Decision.created_at.desc())
        .limit(1)
    )
    decision = decisions_result.scalar_one_or_none()

    doc_result = await db.execute(
        select(func.count()).select_from(Document)
        .where(Document.loan_application_id == application_id)
    )
    doc_count = doc_result.scalar() or 0

    # Build deterministic summary
    parts = []
    parts.append(
        f"Application {application.reference_number}: "
        f"${float(application.amount_requested):,.0f} for {application.purpose.value.replace('_', ' ')}. "
        f"Status: {application.status.value.replace('_', ' ')}."
    )

    if doc_count > 0:
        parts.append(f"{doc_count} document(s) on file.")

    if decision:
        parts.append(
            f"Decision engine: {decision.engine_outcome}. "
            f"Credit score: {decision.credit_score or 'N/A'}. "
            f"Risk band: {decision.risk_band or 'N/A'}."
        )

    if notes:
        latest_note = notes[0]
        parts.append(f"Latest note: \"{latest_note.content[:100]}\"")

    summary = " ".join(parts)

    if _openai_available():
        try:
            ai_summary = await _chat([
                {"role": "system", "content": (
                    "You write concise handoff notes for loan applications. "
                    "Summarize key findings, flags, and next steps in under 100 words. "
                    "Reference specific data. Never hallucinate."
                )},
                {"role": "user", "content": f"Summarize this for the next processor:\n{summary}"},
            ], max_tokens=200)
            return ai_summary
        except Exception as e:
            logger.warning("AI handoff summary failed: %s", e)

    return summary


# ── Stuck Detection ───────────────────────────────────────────

async def detect_stuck_applications(db: AsyncSession) -> list[int]:
    """Identify queue entries that appear stuck. Returns list of entry IDs."""
    now = datetime.now(timezone.utc)

    # Compute average time in current status
    avg_result = await db.execute(
        select(func.avg(
            func.extract("epoch", now - QueueEntry.updated_at)
        )).where(
            QueueEntry.status.in_([
                QueueEntryStatus.NEW.value,
                QueueEntryStatus.IN_PROGRESS.value,
            ])
        )
    )
    avg_seconds = avg_result.scalar() or 86400  # default 1 day

    # Stuck threshold: 3x average or at least 48 hours
    threshold_seconds = max(3 * avg_seconds, 172800)
    threshold_dt = now - timedelta(seconds=threshold_seconds)

    # Find entries older than threshold
    stuck_result = await db.execute(
        select(QueueEntry.id).where(
            QueueEntry.status.in_([
                QueueEntryStatus.NEW.value,
                QueueEntryStatus.IN_PROGRESS.value,
            ]),
            QueueEntry.updated_at < threshold_dt,
            QueueEntry.is_stuck == False,
        )
    )
    stuck_ids = [row[0] for row in stuck_result.all()]

    # Mark them
    if stuck_ids:
        for entry_id in stuck_ids:
            entry_result = await db.execute(
                select(QueueEntry).where(QueueEntry.id == entry_id)
            )
            entry = entry_result.scalar_one_or_none()
            if entry:
                entry.is_stuck = True
                event = QueueEvent(
                    queue_entry_id=entry.id,
                    application_id=entry.application_id,
                    event_type="stuck_flagged",
                    details={"threshold_hours": round(threshold_seconds / 3600, 1)},
                )
                db.add(event)

        await db.flush()

    logger.info("Detected %d stuck applications", len(stuck_ids))
    return stuck_ids


# ── Process Insights ──────────────────────────────────────────

async def generate_insights(db: AsyncSession) -> list[dict[str, Any]]:
    """Generate proactive process improvement suggestions."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    insights: list[dict[str, Any]] = []

    # 1. Average turnaround trend
    decided_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", LoanApplication.decided_at - LoanApplication.submitted_at)
            )
        ).where(
            LoanApplication.decided_at.is_not(None),
            LoanApplication.submitted_at.is_not(None),
            LoanApplication.decided_at >= thirty_days_ago,
        )
    )
    avg_turnaround_sec = decided_result.scalar()
    if avg_turnaround_sec:
        avg_hours = avg_turnaround_sec / 3600
        insights.append({
            "type": "turnaround",
            "title": "Average Turnaround",
            "description": f"Average time from submission to decision: {avg_hours:.1f} hours ({avg_hours/24:.1f} days) over the last 30 days.",
            "metric": round(avg_hours, 1),
            "unit": "hours",
        })

    # 2. Pending queue depth
    pending_result = await db.execute(
        select(func.count()).select_from(QueueEntry).where(
            QueueEntry.status.in_([QueueEntryStatus.NEW.value, QueueEntryStatus.IN_PROGRESS.value])
        )
    )
    pending = pending_result.scalar() or 0
    if pending > 0:
        insights.append({
            "type": "queue_depth",
            "title": "Queue Depth",
            "description": f"{pending} applications currently in the processing queue.",
            "metric": pending,
        })

    # 3. Stuck applications
    stuck_result = await db.execute(
        select(func.count()).select_from(QueueEntry).where(QueueEntry.is_stuck == True)
    )
    stuck_count = stuck_result.scalar() or 0
    if stuck_count > 0:
        insights.append({
            "type": "stuck_alert",
            "title": "Stuck Applications",
            "description": f"{stuck_count} application(s) appear stuck and may need attention.",
            "metric": stuck_count,
            "severity": "warning",
        })

    # 4. Workload distribution
    staff_result = await db.execute(
        select(
            StaffQueueProfile.user_id,
            StaffQueueProfile.current_load_count,
            StaffQueueProfile.max_concurrent,
        ).where(StaffQueueProfile.is_available == True)
    )
    staff_loads = staff_result.all()
    if staff_loads:
        loads = [s[1] for s in staff_loads]
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)
        idle_count = sum(1 for l in loads if l == 0)

        if max_load > avg_load * 2 and avg_load > 0:
            insights.append({
                "type": "workload_imbalance",
                "title": "Workload Imbalance",
                "description": (
                    f"Workload is unevenly distributed. "
                    f"Average: {avg_load:.1f}, max: {max_load}. "
                    f"Consider enabling AI auto-assignment for better distribution."
                ),
                "severity": "info",
            })

        if idle_count > 0 and pending > 0:
            insights.append({
                "type": "idle_staff",
                "title": "Available Capacity",
                "description": f"{idle_count} team member(s) have no assigned work while {pending} applications are pending.",
                "severity": "info",
            })

    # 5. Approval rate
    recent_decisions = await db.execute(
        select(
            func.count().filter(LoanApplication.status == LoanStatus.APPROVED),
            func.count().filter(LoanApplication.status == LoanStatus.DECLINED),
            func.count(),
        ).where(
            LoanApplication.decided_at >= thirty_days_ago,
            LoanApplication.decided_at.is_not(None),
        )
    )
    row = recent_decisions.one_or_none()
    if row and row[2] > 0:
        approved, declined, total = row
        approval_rate = (approved / total) * 100 if total > 0 else 0
        insights.append({
            "type": "approval_rate",
            "title": "Decision Distribution",
            "description": f"Last 30 days: {approved} approved, {declined} declined out of {total} decisions ({approval_rate:.0f}% approval rate).",
            "metric": round(approval_rate, 1),
        })

    return insights


# ── Exception Precedent Analysis ──────────────────────────────

async def analyze_exception_precedent(exception_id: int, db: AsyncSession) -> dict[str, Any]:
    """Analyze similar past exceptions to provide precedent."""
    exc_result = await db.execute(
        select(QueueException).where(QueueException.id == exception_id)
    )
    exc = exc_result.scalar_one_or_none()
    if not exc:
        return {"error": "Exception not found"}

    # Find similar exceptions by type
    similar_result = await db.execute(
        select(QueueException).where(
            QueueException.exception_type == exc.exception_type,
            QueueException.status.in_(["approved", "declined"]),
            QueueException.id != exc.id,
        ).order_by(QueueException.created_at.desc()).limit(20)
    )
    similar = similar_result.scalars().all()

    approved_count = sum(1 for s in similar if s.status == "approved")
    declined_count = sum(1 for s in similar if s.status == "declined")
    total = len(similar)

    result = {
        "exception_type": exc.exception_type,
        "similar_count": total,
        "approved": approved_count,
        "declined": declined_count,
        "approval_rate": round(approved_count / total * 100, 1) if total > 0 else None,
        "recommendation": None,
    }

    if total >= 5:
        rate = approved_count / total
        if rate > 0.9:
            result["recommendation"] = (
                f"This type of exception is approved {rate:.0%} of the time. "
                f"Consider updating the standard policy to eliminate this exception."
            )
        elif rate > 0.7:
            result["recommendation"] = (
                f"This type of exception is typically approved ({rate:.0%}). "
                f"Historical precedent supports approval."
            )
        elif rate < 0.3:
            result["recommendation"] = (
                f"This type of exception is rarely approved ({rate:.0%}). "
                f"Historical precedent suggests caution."
            )

    return result
