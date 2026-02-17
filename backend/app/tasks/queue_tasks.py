"""Celery tasks for queue management.

Tasks: sync entries, recalc priority, SLA checks, stuck detection,
auto-assign, auto-expire.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.tasks import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


def _get_session() -> async_sessionmaker:
    engine = create_async_engine(settings.database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(name="app.tasks.queue_tasks.sync_queue_entries")
def sync_queue_entries() -> dict:
    """Create QueueEntry for new SUBMITTED applications, mark decided ones."""
    async def _run():
        from app.models.queue import QueueEntry, QueueEntryStatus, QueueConfig
        from app.models.loan import LoanApplication, LoanStatus
        from app.services.queue_ai import compute_completeness, estimate_complexity

        SessionLocal = _get_session()
        async with SessionLocal() as db:
            try:
                # Find submitted applications without a queue entry
                existing_ids_result = await db.execute(
                    select(QueueEntry.application_id)
                )
                existing_ids = {row[0] for row in existing_ids_result.all()}

                new_apps_result = await db.execute(
                    select(LoanApplication).where(
                        LoanApplication.status.in_([
                            LoanStatus.SUBMITTED,
                            LoanStatus.UNDER_REVIEW,
                            LoanStatus.CREDIT_CHECK,
                            LoanStatus.DECISION_PENDING,
                            LoanStatus.AWAITING_DOCUMENTS,
                        ]),
                    )
                )
                new_apps = new_apps_result.scalars().all()

                created = 0
                for app in new_apps:
                    if app.id not in existing_ids:
                        completeness = await compute_completeness(app.id, db)
                        complexity = await estimate_complexity(app.id, db)

                        entry = QueueEntry(
                            application_id=app.id,
                            status=(
                                QueueEntryStatus.WAITING_BORROWER.value
                                if app.status == LoanStatus.AWAITING_DOCUMENTS
                                else QueueEntryStatus.IN_PROGRESS.value
                                if app.assigned_underwriter_id
                                else QueueEntryStatus.NEW.value
                            ),
                            assigned_to_id=app.assigned_underwriter_id,
                            claimed_by_id=app.assigned_underwriter_id,
                            completeness_score=completeness,
                            complexity_estimate_hours=complexity,
                            stage_entered_at=app.submitted_at or app.created_at,
                        )
                        db.add(entry)
                        created += 1

                # Mark decided applications
                decided_statuses = [
                    LoanStatus.APPROVED, LoanStatus.DECLINED,
                    LoanStatus.DISBURSED, LoanStatus.CANCELLED,
                    LoanStatus.VOIDED,
                ]
                decided_apps_result = await db.execute(
                    select(LoanApplication.id).where(
                        LoanApplication.status.in_(decided_statuses),
                    )
                )
                decided_app_ids = {row[0] for row in decided_apps_result.all()}

                if decided_app_ids:
                    active_entries_result = await db.execute(
                        select(QueueEntry).where(
                            QueueEntry.application_id.in_(decided_app_ids),
                            QueueEntry.status != QueueEntryStatus.DECIDED.value,
                        )
                    )
                    marked = 0
                    for entry in active_entries_result.scalars().all():
                        entry.status = QueueEntryStatus.DECIDED.value
                        marked += 1
                else:
                    marked = 0

                await db.commit()
                result = {"created": created, "marked_decided": marked}
                logger.info("Queue sync: %s", result)
                return result
            except Exception as e:
                await db.rollback()
                logger.error("Queue sync failed: %s", e)
                return {"error": str(e)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.queue_tasks.recalculate_priorities")
def recalculate_priorities() -> dict:
    """Recalculate priority scores for all active queue entries."""
    async def _run():
        from app.services.queue_priority import recalculate_all_priorities

        SessionLocal = _get_session()
        async with SessionLocal() as db:
            try:
                count = await recalculate_all_priorities(db)
                await db.commit()
                return {"recalculated": count}
            except Exception as e:
                await db.rollback()
                logger.error("Priority recalculation failed: %s", e)
                return {"error": str(e)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.queue_tasks.check_sla")
def check_sla() -> dict:
    """Run SLA checks for warnings and breaches."""
    async def _run():
        from app.services.queue_sla import run_sla_checks

        SessionLocal = _get_session()
        async with SessionLocal() as db:
            try:
                result = await run_sla_checks(db)
                await db.commit()
                return result
            except Exception as e:
                await db.rollback()
                logger.error("SLA check failed: %s", e)
                return {"error": str(e)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.queue_tasks.detect_stuck")
def detect_stuck() -> dict:
    """AI stuck detection pass."""
    async def _run():
        from app.services.queue_ai import detect_stuck_applications

        SessionLocal = _get_session()
        async with SessionLocal() as db:
            try:
                stuck_ids = await detect_stuck_applications(db)
                await db.commit()
                return {"stuck_count": len(stuck_ids), "ids": stuck_ids[:20]}
            except Exception as e:
                await db.rollback()
                logger.error("Stuck detection failed: %s", e)
                return {"error": str(e)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.queue_tasks.auto_assign")
def auto_assign() -> dict:
    """Run auto-assignment for pending entries."""
    async def _run():
        from app.services.queue_assignment import auto_assign_pending

        SessionLocal = _get_session()
        async with SessionLocal() as db:
            try:
                count = await auto_assign_pending(db)
                await db.commit()
                return {"assigned": count}
            except Exception as e:
                await db.rollback()
                logger.error("Auto-assign failed: %s", e)
                return {"error": str(e)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.queue_tasks.auto_expire")
def auto_expire() -> dict:
    """Expire incomplete applications past deadline."""
    async def _run():
        from app.models.queue import QueueEntry, QueueEntryStatus, QueueConfig, QueueEvent
        from app.models.loan import LoanApplication, LoanStatus

        SessionLocal = _get_session()
        async with SessionLocal() as db:
            try:
                config_result = await db.execute(select(QueueConfig).limit(1))
                config = config_result.scalar_one_or_none()
                expire_days = config.auto_expire_days if config else 14

                cutoff = datetime.now(timezone.utc) - timedelta(days=expire_days)

                # Find entries waiting too long
                entries_result = await db.execute(
                    select(QueueEntry).where(
                        QueueEntry.status == QueueEntryStatus.WAITING_BORROWER.value,
                        QueueEntry.waiting_since < cutoff,
                    )
                )
                entries = entries_result.scalars().all()

                expired = 0
                for entry in entries:
                    entry.status = QueueEntryStatus.EXPIRED.value

                    # Update loan application
                    app_result = await db.execute(
                        select(LoanApplication).where(LoanApplication.id == entry.application_id)
                    )
                    app = app_result.scalar_one_or_none()
                    if app:
                        app.status = LoanStatus.CANCELLED
                        app.cancellation_reason = "Auto-expired: no borrower response"

                    event = QueueEvent(
                        queue_entry_id=entry.id,
                        application_id=entry.application_id,
                        event_type="expired",
                        details={"reason": "auto_expire", "days_waited": expire_days},
                    )
                    db.add(event)
                    expired += 1

                await db.commit()
                result = {"expired": expired}
                logger.info("Auto-expire: %s", result)
                return result
            except Exception as e:
                await db.rollback()
                logger.error("Auto-expire failed: %s", e)
                return {"error": str(e)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
