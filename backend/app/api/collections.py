"""Collection endpoints for managing overdue loan recovery."""

import logging
import random
from datetime import datetime, date, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.whatsapp_notifier import send_whatsapp_message

logger = logging.getLogger(__name__)
from app.models.user import User, UserRole
from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.payment import Payment, PaymentSchedule, ScheduleStatus
from app.models.collection import (
    CollectionRecord, CollectionChannel, CollectionOutcome,
    CollectionChat, ChatDirection, ChatMessageStatus,
)
from app.schemas import (
    CollectionRecordCreate,
    CollectionRecordResponse,
    CollectionChatCreate,
    CollectionChatResponse,
    CollectionQueueEntry,
)
from app.auth_utils import require_roles

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)

# Simulated auto-reply messages
AUTO_REPLIES = [
    "Thank you for reaching out. I'll review my account and get back to you.",
    "I understand. Can we discuss a payment arrangement?",
    "I'm aware of the outstanding balance. I'll make a payment this week.",
    "Could you send me the details of what's owed?",
    "I'm having financial difficulties right now. Can we work something out?",
    "Thanks for the reminder. I'll log in to check my account.",
]


@router.get("/queue", response_model=list[CollectionQueueEntry])
async def get_collection_queue(
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get overdue loans needing collection action."""
    # Get disbursed loans
    result = await db.execute(
        select(LoanApplication, User.first_name, User.last_name, User.phone)
        .join(User, LoanApplication.applicant_id == User.id)
        .where(LoanApplication.status == LoanStatus.DISBURSED)
        .order_by(LoanApplication.decided_at.asc())
    )
    rows = result.all()

    entries = []
    today = date.today()
    for row in rows:
        app = row[0]
        first_name = row[1]
        last_name = row[2]
        phone = row[3]

        # Calculate overdue info from payment schedule
        sched_result = await db.execute(
            select(PaymentSchedule).where(
                PaymentSchedule.loan_application_id == app.id
            ).order_by(PaymentSchedule.installment_number)
        )
        schedules = sched_result.scalars().all()

        total_due = 0
        days_past_due = 0
        next_action_date = None
        total_paid = 0
        outstanding = float(app.amount_approved or app.amount_requested)

        for s in schedules:
            total_paid += float(s.amount_paid)
            if s.status in (ScheduleStatus.OVERDUE, ScheduleStatus.DUE) or (
                s.due_date <= today and s.status != ScheduleStatus.PAID
            ):
                overdue_amount = float(s.amount_due) - float(s.amount_paid)
                if overdue_amount > 0:
                    total_due += overdue_amount
                    dpd = (today - s.due_date).days
                    if dpd > days_past_due:
                        days_past_due = dpd

        outstanding = outstanding - total_paid

        if days_past_due <= 0 and total_due <= 0:
            continue  # Not overdue

        # Last contact
        last_record = await db.execute(
            select(CollectionRecord)
            .where(CollectionRecord.loan_application_id == app.id)
            .order_by(CollectionRecord.created_at.desc())
            .limit(1)
        )
        last = last_record.scalar_one_or_none()
        last_contact = last.created_at if last else None
        next_action = last.next_action_date if last else None

        entries.append(CollectionQueueEntry(
            id=app.id,
            reference_number=app.reference_number,
            applicant_id=app.applicant_id,
            applicant_name=f"{first_name} {last_name}",
            amount_approved=float(app.amount_approved) if app.amount_approved else None,
            amount_due=total_due,
            days_past_due=days_past_due,
            last_contact=last_contact,
            next_action=next_action,
            total_paid=total_paid,
            outstanding_balance=max(outstanding, 0),
            phone=phone,
        ))

    # Sort by days_past_due descending
    entries.sort(key=lambda x: x.days_past_due, reverse=True)
    return entries


@router.get("/{application_id}/history", response_model=list[CollectionRecordResponse])
async def get_collection_history(
    application_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get all collection interaction records for a loan."""
    result = await db.execute(
        select(CollectionRecord, User.first_name, User.last_name)
        .join(User, CollectionRecord.agent_id == User.id)
        .where(CollectionRecord.loan_application_id == application_id)
        .order_by(CollectionRecord.created_at.desc())
    )
    entries = []
    for row in result.all():
        record = row[0]
        entries.append(CollectionRecordResponse(
            id=record.id,
            loan_application_id=record.loan_application_id,
            agent_id=record.agent_id,
            agent_name=f"{row[1]} {row[2]}",
            channel=record.channel.value,
            notes=record.notes,
            action_taken=record.action_taken,
            outcome=record.outcome.value,
            next_action_date=record.next_action_date,
            promise_amount=float(record.promise_amount) if record.promise_amount else None,
            promise_date=record.promise_date,
            created_at=record.created_at,
        ))
    return entries


@router.post("/{application_id}/record", response_model=CollectionRecordResponse)
async def add_collection_record(
    application_id: int,
    data: CollectionRecordCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Add a collection interaction record."""
    record = CollectionRecord(
        loan_application_id=application_id,
        agent_id=current_user.id,
        channel=CollectionChannel(data.channel),
        notes=data.notes,
        action_taken=data.action_taken,
        outcome=CollectionOutcome(data.outcome),
        next_action_date=data.next_action_date,
        promise_amount=data.promise_amount,
        promise_date=data.promise_date,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return CollectionRecordResponse(
        id=record.id,
        loan_application_id=record.loan_application_id,
        agent_id=record.agent_id,
        agent_name=f"{current_user.first_name} {current_user.last_name}",
        channel=record.channel.value,
        notes=record.notes,
        action_taken=record.action_taken,
        outcome=record.outcome.value,
        next_action_date=record.next_action_date,
        promise_amount=float(record.promise_amount) if record.promise_amount else None,
        promise_date=record.promise_date,
        created_at=record.created_at,
    )


@router.get("/{application_id}/chat", response_model=list[CollectionChatResponse])
async def get_chat_history(
    application_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get WhatsApp chat history for a loan."""
    result = await db.execute(
        select(CollectionChat)
        .where(CollectionChat.loan_application_id == application_id)
        .order_by(CollectionChat.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{application_id}/send-whatsapp", response_model=list[CollectionChatResponse])
async def send_whatsapp(
    application_id: int,
    data: CollectionChatCreate,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Send a WhatsApp message via Twilio. Returns the outbound message record."""
    # Get applicant's phone
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    app = app_result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    user_result = await db.execute(
        select(User).where(User.id == app.applicant_id)
    )
    applicant = user_result.scalar_one_or_none()
    phone = applicant.phone if applicant else "+1868-555-0000"

    # Send via Twilio
    twilio_result = await send_whatsapp_message(phone, data.message)
    twilio_sid = twilio_result.get("sid", "")
    twilio_error = twilio_result.get("error")

    status = ChatMessageStatus.FAILED if twilio_error else ChatMessageStatus.SENT

    # Outbound message
    outbound = CollectionChat(
        loan_application_id=application_id,
        agent_id=current_user.id,
        phone_number=phone,
        direction=ChatDirection.OUTBOUND,
        message=data.message,
        channel="whatsapp",
        status=status,
    )
    db.add(outbound)
    await db.flush()
    await db.refresh(outbound)

    if twilio_error:
        logger.warning(
            "WhatsApp send failed for app %s: %s", application_id, twilio_error
        )

    return [outbound]
