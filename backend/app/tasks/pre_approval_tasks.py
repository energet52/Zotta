"""Celery tasks for pre-approval lifecycle management."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.tasks import celery_app
from app.database import async_session
from app.models.pre_approval import PreApproval

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.pre_approval_tasks.expire_pre_approvals")
def expire_pre_approvals():
    """Mark pre-approvals past their expiry date as expired."""
    import asyncio

    async def _run():
        async with async_session() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                update(PreApproval)
                .where(
                    PreApproval.status == "active",
                    PreApproval.expires_at != None,
                    PreApproval.expires_at < now,
                )
                .values(status="expired")
                .returning(PreApproval.id)
            )
            expired_ids = result.scalars().all()
            await db.commit()
            if expired_ids:
                logger.info("Expired %d pre-approvals: %s", len(expired_ids), expired_ids)
            return len(expired_ids)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.pre_approval_tasks.purge_old_pre_approvals")
def purge_old_pre_approvals():
    """Purge pre-approval data past retention period.

    Declined: 90 days, Others: 180 days.
    Does NOT purge converted records linked to active applications.
    """
    import asyncio
    from datetime import timedelta

    async def _run():
        async with async_session() as db:
            now = datetime.now(timezone.utc)
            declined_cutoff = now - timedelta(days=90)
            other_cutoff = now - timedelta(days=180)

            # Purge declined
            r1 = await db.execute(
                update(PreApproval)
                .where(
                    PreApproval.outcome == "declined",
                    PreApproval.status != "purged",
                    PreApproval.status != "converted",
                    PreApproval.created_at < declined_cutoff,
                )
                .values(
                    status="purged",
                    bureau_data_cached=None,
                    national_id=None,
                )
                .returning(PreApproval.id)
            )
            purged_declined = len(r1.scalars().all())

            # Purge expired/active (non-converted)
            r2 = await db.execute(
                update(PreApproval)
                .where(
                    PreApproval.outcome != "declined",
                    PreApproval.status.in_(["active", "expired"]),
                    PreApproval.created_at < other_cutoff,
                )
                .values(
                    status="purged",
                    bureau_data_cached=None,
                    national_id=None,
                )
                .returning(PreApproval.id)
            )
            purged_other = len(r2.scalars().all())

            await db.commit()
            total = purged_declined + purged_other
            if total:
                logger.info("Purged %d pre-approvals (%d declined, %d other)", total, purged_declined, purged_other)
            return total

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
