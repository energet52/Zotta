"""Celery periodic task: detect overdue payments and send WhatsApp reminders."""

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.tasks import celery_app
from app.config import settings
from app.models.payment import PaymentSchedule, ScheduleStatus
from app.models.loan import LoanApplication
from app.models.user import User
from app.models.collection import CollectionRecord, CollectionChannel, CollectionOutcome
from app.models.collections_ext import CollectionCase, CaseStatus
from app.services.whatsapp_notifier import send_whatsapp_message
from app.services.collections_engine import (
    sync_collection_cases,
    update_case_nba,
    check_ptp_status as engine_check_ptp_status,
    generate_daily_snapshot,
)

logger = logging.getLogger(__name__)


def _get_async_session():
    engine = create_async_engine(settings.database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Reminder message templates ────────────────────────────────────

REMINDER_TEMPLATES = {
    1: (
        "Hi {first_name}, this is a friendly reminder that your payment of "
        "TTD {amount_due:,.2f} for loan {ref} was due on {due_date}. "
        "Please make your payment at your earliest convenience. "
        "Contact us if you need assistance."
    ),
    7: (
        "Hi {first_name}, your payment of TTD {amount_due:,.2f} for loan {ref} "
        "is now 7 days overdue (due {due_date}). Please arrange payment as soon "
        "as possible to avoid additional charges. Reply to this message if you'd "
        "like to discuss a payment plan."
    ),
    30: (
        "URGENT: Hi {first_name}, your payment of TTD {amount_due:,.2f} for loan "
        "{ref} is 30 days overdue (original due date: {due_date}). Immediate "
        "payment is required. Please contact us today to arrange payment and "
        "avoid further collection action."
    ),
}

REMINDER_DAY_THRESHOLDS = sorted(REMINDER_TEMPLATES.keys())


@celery_app.task(name="app.tasks.collection_reminders.check_overdue_and_notify")
def check_overdue_and_notify() -> dict:
    """Detect overdue payments, update statuses, and send WhatsApp reminders.

    This runs as a synchronous Celery task that wraps an async inner function.
    """

    async def _run():
        session_factory = _get_async_session()
        async with session_factory() as db:
            try:
                stats = await _process_overdue(db)
                await db.commit()
                return stats
            except Exception:
                await db.rollback()
                raise

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


async def _process_overdue(db: AsyncSession) -> dict:
    """Core logic: mark overdue, send reminders, return stats."""

    today = date.today()
    updated_count = 0
    sent_count = 0
    errors = 0

    # 1. Find all unpaid installments whose due_date has passed
    result = await db.execute(
        select(PaymentSchedule).where(
            and_(
                PaymentSchedule.due_date < today,
                PaymentSchedule.status.in_([
                    ScheduleStatus.UPCOMING,
                    ScheduleStatus.DUE,
                    ScheduleStatus.PARTIAL,
                    ScheduleStatus.OVERDUE,
                ]),
            )
        )
    )
    overdue_installments = result.scalars().all()

    if not overdue_installments:
        logger.info("No overdue installments found")
        return {"updated": 0, "sent": 0, "errors": 0}

    # 2. Update non-OVERDUE ones to OVERDUE
    for inst in overdue_installments:
        if inst.status != ScheduleStatus.OVERDUE:
            inst.status = ScheduleStatus.OVERDUE
            updated_count += 1

    # 3. Group by loan application and determine reminder tier
    loan_overdue: dict[int, list[PaymentSchedule]] = {}
    for inst in overdue_installments:
        loan_overdue.setdefault(inst.loan_application_id, []).append(inst)

    for loan_app_id, installments in loan_overdue.items():
        # Worst overdue: furthest past-due installment
        oldest = min(installments, key=lambda i: i.due_date)
        days_overdue = (today - oldest.due_date).days

        # Determine which reminder tier to send
        tier = None
        for threshold in REMINDER_DAY_THRESHOLDS:
            if days_overdue >= threshold:
                tier = threshold

        if tier is None:
            continue

        # Check if this tier reminder was already sent (avoid duplicates)
        existing = await db.execute(
            select(CollectionRecord).where(
                and_(
                    CollectionRecord.loan_application_id == loan_app_id,
                    CollectionRecord.channel == CollectionChannel.WHATSAPP,
                    CollectionRecord.action_taken == f"auto_reminder_{tier}d",
                )
            )
        )
        if existing.scalars().first():
            continue  # Already sent this tier

        # Look up applicant
        app_result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == loan_app_id)
        )
        application = app_result.scalar_one_or_none()
        if not application:
            continue

        user_result = await db.execute(
            select(User).where(User.id == application.applicant_id)
        )
        applicant = user_result.scalar_one_or_none()
        if not applicant or not applicant.phone:
            continue

        # Total overdue amount
        total_overdue = sum(
            float(i.amount_due) - float(i.amount_paid) for i in installments
        )

        template = REMINDER_TEMPLATES[tier]
        msg = template.format(
            first_name=applicant.first_name or "Customer",
            amount_due=total_overdue,
            ref=application.reference_number or f"#{application.id}",
            due_date=oldest.due_date.strftime("%d %b %Y"),
        )

        # Send WhatsApp
        wa_result = await send_whatsapp_message(applicant.phone, msg)

        if wa_result.get("error"):
            errors += 1
            logger.warning(
                "Failed overdue reminder for app %s tier %sd: %s",
                loan_app_id, tier, wa_result["error"],
            )
        else:
            sent_count += 1

        # Record the collection action
        record = CollectionRecord(
            loan_application_id=loan_app_id,
            agent_id=application.applicant_id,  # system-generated
            channel=CollectionChannel.WHATSAPP,
            action_taken=f"auto_reminder_{tier}d",
            outcome=CollectionOutcome.OTHER,
            notes=f"Auto WhatsApp reminder ({tier}d overdue). "
                  f"Twilio SID: {wa_result.get('sid', 'N/A')}",
        )
        db.add(record)

    await db.flush()

    logger.info(
        "Overdue check complete: %d statuses updated, %d reminders sent, %d errors",
        updated_count, sent_count, errors,
    )

    return {"updated": updated_count, "sent": sent_count, "errors": errors}


# ════════════════════════════════════════════════════════════════════
# New periodic tasks for the upgraded collections module
# ════════════════════════════════════════════════════════════════════

@celery_app.task(name="app.tasks.collection_reminders.sync_cases")
def sync_cases() -> dict:
    """Periodic (every 15 min): sync collection cases and compute NBA."""

    async def _run():
        session_factory = _get_async_session()
        async with session_factory() as db:
            try:
                stats = await sync_collection_cases(db)
                # Compute NBA for all open/in_progress cases
                result = await db.execute(
                    select(CollectionCase).where(
                        CollectionCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS])
                    )
                )
                cases = result.scalars().all()
                for c in cases:
                    await update_case_nba(c, db)
                await db.commit()
                stats["nba_computed"] = len(cases)
                return stats
            except Exception:
                await db.rollback()
                logger.exception("sync_cases task failed")
                raise

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.collection_reminders.check_ptps")
def check_ptps() -> dict:
    """Daily: check pending PTPs, mark broken if past grace period."""

    async def _run():
        session_factory = _get_async_session()
        async with session_factory() as db:
            try:
                stats = await engine_check_ptp_status(db)
                await db.commit()
                return stats
            except Exception:
                await db.rollback()
                logger.exception("check_ptps task failed")
                raise

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.collection_reminders.execute_sequence_steps")
def execute_sequence_steps() -> dict:
    """Execute due sequence steps for all active enrollments."""

    async def _run():
        from app.models.collection_sequence import (
            SequenceEnrollment, SequenceStep, StepExecution, CollectionSequence,
        )
        from app.services.whatsapp_notifier import send_whatsapp_message
        from app.services.sequence_ai import render_template

        session_factory = _get_async_session()
        async with session_factory() as db:
            try:
                # Get active enrollments with their cases and sequences
                result = await db.execute(
                    select(SequenceEnrollment)
                    .where(SequenceEnrollment.status == "active")
                )
                enrollments = result.scalars().all()

                executed = 0
                paused = 0
                skipped = 0

                for enrollment in enrollments:
                    # Load the case
                    case_result = await db.execute(
                        select(CollectionCase).where(CollectionCase.id == enrollment.case_id)
                    )
                    case = case_result.scalar_one_or_none()
                    if not case:
                        continue

                    # Auto-pause checks
                    if case.do_not_contact or case.dispute_active or case.hardship_flag:
                        enrollment.status = "paused"
                        reason = []
                        if case.do_not_contact:
                            reason.append("DNC flag")
                        if case.dispute_active:
                            reason.append("Dispute active")
                        if case.hardship_flag:
                            reason.append("Hardship flag")
                        enrollment.paused_reason = ", ".join(reason)
                        paused += 1
                        continue

                    # Get sequence steps
                    steps_result = await db.execute(
                        select(SequenceStep)
                        .where(
                            SequenceStep.sequence_id == enrollment.sequence_id,
                            SequenceStep.is_active == True,
                        )
                        .order_by(SequenceStep.step_number)
                    )
                    steps = steps_result.scalars().all()

                    # Find the next due step
                    for step in steps:
                        if step.step_number <= enrollment.current_step_number:
                            continue
                        if step.day_offset > case.dpd:
                            break

                        # Check if already executed
                        existing = await db.execute(
                            select(StepExecution.id).where(
                                StepExecution.enrollment_id == enrollment.id,
                                StepExecution.step_id == step.id,
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue

                        # Render message
                        msg_body = step.custom_message or ""
                        if step.template_id:
                            from app.models.collection_sequence import MessageTemplate as MT
                            tmpl_result = await db.execute(
                                select(MT).where(MT.id == step.template_id)
                            )
                            tmpl = tmpl_result.scalar_one_or_none()
                            if tmpl:
                                msg_body = tmpl.body

                        # Build context from case
                        loan = None
                        user_profile = None
                        try:
                            loan_result = await db.execute(
                                select(LoanApplication).where(
                                    LoanApplication.id == case.loan_application_id
                                )
                            )
                            loan = loan_result.scalar_one_or_none()
                            if loan:
                                from app.models.loan import ApplicantProfile
                                profile_result = await db.execute(
                                    select(ApplicantProfile).where(
                                        ApplicantProfile.user_id == loan.user_id
                                    )
                                )
                                user_profile = profile_result.scalar_one_or_none()
                        except Exception:
                            pass

                        context = {
                            "name": f"{user_profile.first_name} {user_profile.last_name}" if user_profile else "Customer",
                            "first_name": user_profile.first_name if user_profile else "Customer",
                            "amount_due": f"{float(case.total_overdue or 0):,.2f}",
                            "total_overdue": f"{float(case.total_overdue or 0):,.2f}",
                            "dpd": str(case.dpd),
                            "ref": f"ZL-{loan.id}" if loan else "N/A",
                        }
                        rendered = render_template(msg_body, context)

                        # Send via channel
                        delivery_status = "sent"
                        if step.channel == "whatsapp" and step.action_type == "send_message":
                            phone = None
                            if user_profile and hasattr(user_profile, 'phone'):
                                phone = user_profile.phone
                            if phone:
                                send_result = send_whatsapp_message(phone, rendered)
                                if "error" in send_result:
                                    delivery_status = "failed"
                                else:
                                    delivery_status = "delivered"

                        # Record execution
                        db.add(StepExecution(
                            enrollment_id=enrollment.id,
                            step_id=step.id,
                            channel=step.channel,
                            message_sent=rendered,
                            delivery_status=delivery_status,
                        ))

                        enrollment.current_step_number = step.step_number
                        executed += 1

                        # Check if last step
                        if step.step_number >= len(steps):
                            enrollment.status = "completed"
                            enrollment.completed_at = datetime.now()

                        break  # One step per cycle per enrollment

                await db.commit()
                return {"executed": executed, "paused": paused, "skipped": skipped}
            except Exception:
                await db.rollback()
                logger.exception("execute_sequence_steps task failed")
                raise

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="app.tasks.collection_reminders.daily_snapshot")
def daily_snapshot() -> dict:
    """Daily: generate collections dashboard snapshot."""

    async def _run():
        session_factory = _get_async_session()
        async with session_factory() as db:
            try:
                snap = await generate_daily_snapshot(db)
                await db.commit()
                return {"snapshot_date": str(snap.snapshot_date), "accounts": snap.total_delinquent_accounts}
            except Exception:
                await db.rollback()
                logger.exception("daily_snapshot task failed")
                raise

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
