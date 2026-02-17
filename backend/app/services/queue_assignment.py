"""Queue assignment engine.

Supports pull, auto, hybrid, and manager assignment modes.
Auto-assignment considers workload, skills, authority, speed, and continuity.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import (
    QueueConfig, QueueEntry, QueueEntryStatus, QueueEvent,
    StaffQueueProfile, AssignmentMode,
)
from app.models.loan import LoanApplication
from app.models.user import User, UserRole
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_ASSIGNMENT_WEIGHTS = {
    "workload": 0.40,
    "skills_match": 0.25,
    "authority_fit": 0.15,
    "processing_speed": 0.10,
    "continuity": 0.10,
}


def _get_assignment_weights(config: QueueConfig | None) -> dict:
    if config and config.ai_config and "assignment_weights" in config.ai_config:
        return {**DEFAULT_ASSIGNMENT_WEIGHTS, **config.ai_config["assignment_weights"]}
    return DEFAULT_ASSIGNMENT_WEIGHTS


def _score_staff_for_entry(
    profile: StaffQueueProfile,
    user: User,
    entry: QueueEntry,
    application: LoanApplication,
    weights: dict,
    config: QueueConfig | None,
) -> tuple[float, dict[str, Any]]:
    """Score how well a staff member fits a particular entry."""
    factors: dict[str, Any] = {}

    # 1. Workload: lower is better
    load_ratio = profile.current_load_count / max(1, profile.max_concurrent)
    workload_score = max(0.0, 1.0 - load_ratio)
    factors["workload"] = {
        "current": profile.current_load_count,
        "max": profile.max_concurrent,
        "score": round(workload_score, 3),
    }

    # 2. Skills match
    skills_score = 0.5  # baseline when no skills configured
    if config and config.skills_routing_enabled and profile.skills:
        skills = profile.skills
        product_types = skills.get("product_types", [])
        sectors = skills.get("sectors", [])
        complexity = skills.get("complexity_levels", [])

        matches = 0
        checks = 0

        if product_types and application.purpose:
            checks += 1
            if application.purpose.value in product_types:
                matches += 1

        if sectors and hasattr(application, "applicant") and application.applicant:
            ap = getattr(application.applicant, "applicant_profile", None)
            if ap and getattr(ap, "employer_sector", None):
                checks += 1
                if ap.employer_sector in sectors:
                    matches += 1

        if complexity:
            checks += 1
            amount = float(application.amount_requested or 0)
            if amount > 500000 and "complex" in complexity:
                matches += 1
            elif amount <= 500000 and "standard" in complexity:
                matches += 1

        skills_score = matches / max(1, checks) if checks > 0 else 0.5

    factors["skills_match"] = {"score": round(skills_score, 3)}

    # 3. Authority fit: can this person approve without escalation?
    authority_score = 1.0
    if config and config.authority_limits_enabled and profile.authority_max_amount is not None:
        amount = float(application.amount_requested or 0)
        if amount <= float(profile.authority_max_amount):
            authority_score = 1.0
        else:
            authority_score = 0.3  # still possible via referral
    factors["authority_fit"] = {"score": round(authority_score, 3)}

    # 4. Processing speed
    speed_score = 0.5
    if profile.avg_processing_hours:
        if profile.avg_processing_hours < 4:
            speed_score = 0.9
        elif profile.avg_processing_hours < 8:
            speed_score = 0.7
        elif profile.avg_processing_hours < 24:
            speed_score = 0.5
        else:
            speed_score = 0.3
    factors["processing_speed"] = {"score": round(speed_score, 3)}

    # 5. Continuity: same borrower preference
    continuity_score = 0.0
    if application.assigned_underwriter_id == profile.user_id:
        continuity_score = 1.0
    factors["continuity"] = {"score": round(continuity_score, 3)}

    total = (
        weights["workload"] * workload_score
        + weights["skills_match"] * skills_score
        + weights["authority_fit"] * authority_score
        + weights["processing_speed"] * speed_score
        + weights["continuity"] * continuity_score
    )

    factors["total"] = round(total, 4)
    return (round(total, 4), factors)


async def suggest_assignment(
    entry: QueueEntry,
    db: AsyncSession,
    config: QueueConfig | None = None,
) -> tuple[int | None, str]:
    """Suggest the best staff member for an entry. Returns (user_id, explanation)."""
    if not config:
        cfg_result = await db.execute(select(QueueConfig).limit(1))
        config = cfg_result.scalar_one_or_none()

    weights = _get_assignment_weights(config)

    # Load application
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == entry.application_id)
    )
    application = app_result.scalar_one_or_none()
    if not application:
        return None, "Application not found"

    # Load available staff profiles
    profiles_result = await db.execute(
        select(StaffQueueProfile, User)
        .join(User, StaffQueueProfile.user_id == User.id)
        .where(
            StaffQueueProfile.is_available == True,
            User.is_active == True,
            User.role.in_([UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN]),
        )
    )

    best_user_id = None
    best_score = -1.0
    best_explanation = "No available staff"
    best_factors: dict = {}

    for profile, user in profiles_result.all():
        if profile.current_load_count >= profile.max_concurrent:
            continue

        score, factors = _score_staff_for_entry(
            profile, user, entry, application, weights, config,
        )
        if score > best_score:
            best_score = score
            best_user_id = profile.user_id
            best_factors = factors
            best_explanation = (
                f"Assigned to {user.first_name} {user.last_name}: "
                f"workload {factors['workload']['current']}/{factors['workload']['max']}, "
                f"skills {factors['skills_match']['score']:.0%}, "
                f"authority {factors['authority_fit']['score']:.0%}"
            )

    return best_user_id, best_explanation


async def auto_assign_pending(db: AsyncSession) -> int:
    """Batch auto-assign unassigned entries. Returns number assigned."""
    config_result = await db.execute(select(QueueConfig).limit(1))
    config = config_result.scalar_one_or_none()

    if not config or config.assignment_mode not in (
        AssignmentMode.AUTO.value, AssignmentMode.HYBRID.value,
    ):
        return 0

    is_hybrid = config.assignment_mode == AssignmentMode.HYBRID.value

    # Get unassigned entries sorted by priority
    entries_result = await db.execute(
        select(QueueEntry)
        .where(
            QueueEntry.status == QueueEntryStatus.NEW.value,
            QueueEntry.assigned_to_id.is_(None),
            QueueEntry.suggested_for_id.is_(None) if is_hybrid else QueueEntry.assigned_to_id.is_(None),
        )
        .order_by(QueueEntry.priority_score.desc())
        .limit(50)
    )
    entries = entries_result.scalars().all()

    assigned_count = 0
    for entry in entries:
        user_id, explanation = await suggest_assignment(entry, db, config)
        if user_id:
            if is_hybrid:
                entry.suggested_for_id = user_id
            else:
                entry.assigned_to_id = user_id
                entry.status = QueueEntryStatus.IN_PROGRESS.value

            event = QueueEvent(
                queue_entry_id=entry.id,
                application_id=entry.application_id,
                event_type="assigned" if not is_hybrid else "suggested",
                to_value={"user_id": user_id, "explanation": explanation},
            )
            db.add(event)

            # Update staff load
            profile_result = await db.execute(
                select(StaffQueueProfile).where(StaffQueueProfile.user_id == user_id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                profile.current_load_count = profile.current_load_count + 1

            assigned_count += 1

    await db.flush()
    logger.info("Auto-assigned %d entries (mode=%s)", assigned_count, config.assignment_mode)
    return assigned_count


async def rebalance(db: AsyncSession) -> int:
    """Redistribute work from unavailable/overloaded staff."""
    config_result = await db.execute(select(QueueConfig).limit(1))
    config = config_result.scalar_one_or_none()

    if not config or config.assignment_mode == AssignmentMode.PULL.value:
        return 0

    # Find unavailable staff with assigned unstarted work
    unavail_result = await db.execute(
        select(StaffQueueProfile).where(StaffQueueProfile.is_available == False)
    )
    unavailable_profiles = unavail_result.scalars().all()
    unavailable_ids = [p.user_id for p in unavailable_profiles]

    if not unavailable_ids:
        return 0

    # Get their unstarted entries (new status, not yet claimed)
    entries_result = await db.execute(
        select(QueueEntry).where(
            QueueEntry.assigned_to_id.in_(unavailable_ids),
            QueueEntry.status == QueueEntryStatus.NEW.value,
            QueueEntry.claimed_at.is_(None),
        )
    )
    entries = entries_result.scalars().all()

    redistributed = 0
    for entry in entries:
        old_user = entry.assigned_to_id
        entry.assigned_to_id = None
        entry.suggested_for_id = None

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="reassigned",
            actor_id=None,
            from_value={"user_id": old_user},
            to_value={"user_id": None, "reason": "staff_unavailable"},
        )
        db.add(event)
        redistributed += 1

    await db.flush()

    # Re-assign them if auto mode
    if config.assignment_mode in (AssignmentMode.AUTO.value, AssignmentMode.HYBRID.value):
        await auto_assign_pending(db)

    logger.info("Rebalanced %d entries from %d unavailable staff", redistributed, len(unavailable_ids))
    return redistributed


async def explain_assignment(entry_id: int, db: AsyncSession) -> str:
    """Explain why an entry was assigned to its current person."""
    entry_result = await db.execute(
        select(QueueEntry).where(QueueEntry.id == entry_id)
    )
    entry = entry_result.scalar_one_or_none()
    if not entry:
        return "Entry not found."

    if not entry.assigned_to_id and not entry.suggested_for_id:
        return "This application is in the shared pool and has not been assigned to anyone."

    # Find the assignment event
    event_result = await db.execute(
        select(QueueEvent)
        .where(
            QueueEvent.queue_entry_id == entry_id,
            QueueEvent.event_type.in_(["assigned", "suggested"]),
        )
        .order_by(QueueEvent.created_at.desc())
        .limit(1)
    )
    event = event_result.scalar_one_or_none()

    if event and event.to_value and "explanation" in event.to_value:
        return event.to_value["explanation"]

    user_id = entry.assigned_to_id or entry.suggested_for_id
    return f"Assigned to user #{user_id} based on workload balancing."
