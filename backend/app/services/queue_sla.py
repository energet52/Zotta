"""Queue SLA engine.

Business-hours aware SLA calculation, pause/resume on borrower wait,
warning/breach detection, and escalation cascade execution.
"""

import logging
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import (
    QueueConfig, QueueEntry, QueueEntryStatus, QueueEvent,
    QueueStage, StaffQueueProfile, SLAMode,
)
from app.models.loan import LoanApplication

logger = logging.getLogger(__name__)


def _parse_time(t) -> time:
    if isinstance(t, time):
        return t
    if isinstance(t, str):
        parts = t.split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    return time(8, 0)


def _get_business_hours(config: QueueConfig | None) -> tuple[time, time]:
    if not config:
        return time(8, 0), time(17, 0)
    return _parse_time(config.business_hours_start), _parse_time(config.business_hours_end)


def _get_business_days(config: QueueConfig | None) -> list[int]:
    if not config or not config.business_days:
        return [1, 2, 3, 4, 5]
    return list(config.business_days)


def _get_holidays(config: QueueConfig | None) -> set[str]:
    if not config or not config.holidays:
        return set()
    return set(config.holidays)


def _is_business_day(d: date, config: QueueConfig | None) -> bool:
    holidays = _get_holidays(config)
    business_days = _get_business_days(config)
    return d.isoweekday() in business_days and d.isoformat() not in holidays


def business_hours_between(
    start: datetime,
    end: datetime,
    config: QueueConfig | None = None,
) -> timedelta:
    """Calculate business hours between two datetimes, respecting weekends and holidays."""
    if start >= end:
        return timedelta(0)

    bh_start, bh_end = _get_business_hours(config)
    bh_start_seconds = bh_start.hour * 3600 + bh_start.minute * 60
    bh_end_seconds = bh_end.hour * 3600 + bh_end.minute * 60
    daily_seconds = bh_end_seconds - bh_start_seconds

    if daily_seconds <= 0:
        daily_seconds = 32400  # fallback 9 hours

    total_seconds = 0
    current = start

    # Process day by day
    max_days = 365  # safety limit
    days_processed = 0
    while current < end and days_processed < max_days:
        days_processed += 1
        current_date = current.date()

        if not _is_business_day(current_date, config):
            current = datetime.combine(current_date + timedelta(days=1), bh_start, tzinfo=current.tzinfo)
            continue

        day_start = datetime.combine(current_date, bh_start, tzinfo=current.tzinfo)
        day_end = datetime.combine(current_date, bh_end, tzinfo=current.tzinfo)

        # Clamp to business hours
        effective_start = max(current, day_start)
        effective_end = min(end, day_end)

        if effective_start < effective_end:
            total_seconds += (effective_end - effective_start).total_seconds()

        current = datetime.combine(current_date + timedelta(days=1), bh_start, tzinfo=current.tzinfo)

    return timedelta(seconds=total_seconds)


def calculate_sla_deadline(
    entry: QueueEntry,
    config: QueueConfig | None,
    stage: QueueStage | None = None,
) -> Optional[datetime]:
    """Calculate SLA deadline in business hours from stage_entered_at or created_at."""
    if not config or config.sla_mode == SLAMode.NONE.value:
        return None

    target_hours = None
    if stage and stage.sla_target_hours:
        target_hours = stage.sla_target_hours
    elif config.target_turnaround_hours:
        target_hours = config.target_turnaround_hours

    if not target_hours:
        return None

    start_time = entry.stage_entered_at or entry.created_at
    if not start_time:
        return None

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    bh_start, bh_end = _get_business_hours(config)
    daily_hours = (
        (bh_end.hour * 60 + bh_end.minute) - (bh_start.hour * 60 + bh_start.minute)
    ) / 60.0
    if daily_hours <= 0:
        daily_hours = 9.0

    # Rough estimate: add calendar days based on business-hour ratio
    business_days_needed = target_hours / daily_hours
    calendar_days_needed = business_days_needed * 7 / 5  # account for weekends

    # Subtract already elapsed business time
    now = datetime.now(timezone.utc)
    elapsed = business_hours_between(start_time, now, config)
    elapsed_hours = elapsed.total_seconds() / 3600

    # Subtract paused time
    paused_hours = entry.sla_elapsed_seconds / 3600

    remaining_hours = target_hours - elapsed_hours + paused_hours
    if remaining_hours <= 0:
        return now  # already breached

    remaining_days = remaining_hours / daily_hours * 7 / 5
    return now + timedelta(days=remaining_days)


def calculate_sla_warning(
    entry: QueueEntry,
    config: QueueConfig | None,
    stage: QueueStage | None = None,
) -> Optional[datetime]:
    """Calculate SLA warning timestamp."""
    if not config or config.sla_mode == SLAMode.NONE.value:
        return None

    warning_hours = None
    if stage and stage.sla_warning_hours:
        warning_hours = stage.sla_warning_hours
    elif config.target_turnaround_hours:
        warning_hours = int(config.target_turnaround_hours * 0.75)

    if not warning_hours:
        return None

    deadline = calculate_sla_deadline(entry, config, stage)
    if not deadline:
        return None

    target_hours = (stage.sla_target_hours if stage and stage.sla_target_hours
                    else config.target_turnaround_hours or 24)
    buffer_hours = target_hours - warning_hours
    return deadline - timedelta(hours=buffer_hours)


def check_sla_status(
    entry: QueueEntry,
    config: QueueConfig | None,
) -> str:
    """Check SLA status: 'ok', 'warning', 'breached', or 'none'."""
    if not config or config.sla_mode == SLAMode.NONE.value:
        return "none"

    if entry.sla_paused_at:
        return "paused"

    now = datetime.now(timezone.utc)

    if entry.sla_deadline:
        deadline = entry.sla_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now >= deadline:
            return "breached"

    if entry.sla_warning_at:
        warning = entry.sla_warning_at
        if warning.tzinfo is None:
            warning = warning.replace(tzinfo=timezone.utc)
        if now >= warning:
            return "warning"

    return "ok"


def pause_sla(entry: QueueEntry) -> None:
    """Pause SLA clock (when waiting for borrower)."""
    if not entry.sla_paused_at:
        entry.sla_paused_at = datetime.now(timezone.utc)


def resume_sla(entry: QueueEntry, config: QueueConfig | None = None) -> None:
    """Resume SLA clock after borrower responds."""
    if entry.sla_paused_at:
        paused_at = entry.sla_paused_at
        if paused_at.tzinfo is None:
            paused_at = paused_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        paused_duration = (now - paused_at).total_seconds()
        entry.sla_elapsed_seconds = (entry.sla_elapsed_seconds or 0) + int(paused_duration)
        entry.sla_paused_at = None

        # Recalculate deadline
        if config:
            entry.sla_deadline = calculate_sla_deadline(entry, config)
            entry.sla_warning_at = calculate_sla_warning(entry, config)


async def run_sla_checks(db: AsyncSession) -> dict:
    """Batch check all active entries for SLA warnings and breaches."""
    config_result = await db.execute(select(QueueConfig).limit(1))
    config = config_result.scalar_one_or_none()

    if not config or config.sla_mode == SLAMode.NONE.value:
        return {"warnings": 0, "breaches": 0}

    entries_result = await db.execute(
        select(QueueEntry).where(
            QueueEntry.status.in_([
                QueueEntryStatus.NEW.value,
                QueueEntryStatus.IN_PROGRESS.value,
            ]),
            QueueEntry.sla_paused_at.is_(None),
        )
    )
    entries = entries_result.scalars().all()

    warnings = 0
    breaches = 0

    for entry in entries:
        status = check_sla_status(entry, config)

        if status == "warning":
            # Check if warning already sent
            existing = await db.execute(
                select(QueueEvent).where(
                    QueueEvent.queue_entry_id == entry.id,
                    QueueEvent.event_type == "sla_warning",
                )
            )
            if not existing.scalar_one_or_none():
                event = QueueEvent(
                    queue_entry_id=entry.id,
                    application_id=entry.application_id,
                    event_type="sla_warning",
                    details={"sla_status": "warning"},
                )
                db.add(event)
                warnings += 1

        elif status == "breached":
            existing = await db.execute(
                select(QueueEvent).where(
                    QueueEvent.queue_entry_id == entry.id,
                    QueueEvent.event_type == "sla_breach",
                )
            )
            if not existing.scalar_one_or_none():
                event = QueueEvent(
                    queue_entry_id=entry.id,
                    application_id=entry.application_id,
                    event_type="sla_breach",
                    details={"sla_status": "breached"},
                )
                db.add(event)
                entry.is_flagged = True
                if not entry.flag_reasons:
                    entry.flag_reasons = []
                if isinstance(entry.flag_reasons, list):
                    entry.flag_reasons = entry.flag_reasons + ["sla_breach"]
                breaches += 1

                # Active SLA: auto-escalate
                if config.sla_mode == SLAMode.ACTIVE.value:
                    await _escalate(entry, config, db)

    await db.flush()
    logger.info("SLA check: %d warnings, %d breaches", warnings, breaches)
    return {"warnings": warnings, "breaches": breaches}


async def _escalate(entry: QueueEntry, config: QueueConfig, db: AsyncSession) -> None:
    """Execute SLA escalation: try to reassign to someone with capacity."""
    if not entry.assigned_to_id:
        return

    # Find someone else with lower workload
    profiles_result = await db.execute(
        select(StaffQueueProfile).where(
            StaffQueueProfile.is_available == True,
            StaffQueueProfile.user_id != entry.assigned_to_id,
        ).order_by(StaffQueueProfile.current_load_count.asc()).limit(1)
    )
    alt_profile = profiles_result.scalar_one_or_none()

    if alt_profile and alt_profile.current_load_count < alt_profile.max_concurrent:
        old_user = entry.assigned_to_id
        entry.assigned_to_id = alt_profile.user_id
        alt_profile.current_load_count += 1

        event = QueueEvent(
            queue_entry_id=entry.id,
            application_id=entry.application_id,
            event_type="reassigned",
            from_value={"user_id": old_user, "reason": "sla_breach_escalation"},
            to_value={"user_id": alt_profile.user_id},
        )
        db.add(event)
        logger.info(
            "SLA escalation: entry %d reassigned from %d to %d",
            entry.id, old_user, alt_profile.user_id,
        )
