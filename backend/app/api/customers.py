from app.services.error_logger import log_error
"""Customer 360 API — staff-only endpoints for the full customer view.

Provides:
- GET  /{user_id}/360       — aggregated customer data
- GET  /{user_id}/timeline  — unified activity timeline
- POST /{user_id}/ai-summary — AI-generated account narrative
- POST /{user_id}/ask-ai    — conversational AI Q&A about the customer
- GET  /{user_id}/alerts     — credit bureau alerts
- PATCH /{user_id}/alerts/{alert_id} — update alert (acknowledge / take action)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth_utils import require_roles
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.models.credit_bureau_alert import (
    CreditBureauAlert, AlertStatus,
)
from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationChannel,
    ConversationEntryPoint,
    ConversationState,
    MessageRole,
)
from app.services.customer360 import (
    get_customer_360,
    get_customer_timeline,
    generate_ai_summary,
    ask_ai_about_customer,
    _row_to_dict, _ser,
)

logger = logging.getLogger(__name__)

router = APIRouter()

STAFF_ROLES = (UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.ADMIN)


# ---------------------------------------------------------------------------
# GET /{user_id}/360
# ---------------------------------------------------------------------------

@router.get("/{user_id}/360")
async def customer_360(
    user_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Return the full Customer 360 payload."""
    try:
        data = await get_customer_360(user_id, db)
        if data is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="customer_360")
        raise


# ---------------------------------------------------------------------------
# GET /{user_id}/timeline
# ---------------------------------------------------------------------------

@router.get("/{user_id}/timeline")
async def customer_timeline(
    user_id: int,
    categories: Optional[str] = Query(None, description="Comma-separated category filter"),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Return a paginated, filterable timeline of customer events."""
    try:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
        events = await get_customer_timeline(
            user_id, db,
            categories=cat_list,
            search=search,
            offset=offset,
            limit=limit,
        )
        return {"events": events, "offset": offset, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="customer_timeline")
        raise


# ---------------------------------------------------------------------------
# POST /{user_id}/ai-summary
# ---------------------------------------------------------------------------

@router.post("/{user_id}/ai-summary")
async def customer_ai_summary(
    user_id: int,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Generate (or regenerate) the AI account summary."""
    try:
        data = await get_customer_360(user_id, db)
        if data is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        summary = await generate_ai_summary(data)
        return summary
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="customer_ai_summary")
        raise


# ---------------------------------------------------------------------------
# POST /{user_id}/ask-ai
# ---------------------------------------------------------------------------

class AskAIRequest(BaseModel):
    question: str
    history: list[dict] | None = None


@router.post("/{user_id}/ask-ai")
async def customer_ask_ai(
    user_id: int,
    body: AskAIRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Ask a free-form question about a customer and get an AI answer."""
    try:
        data = await get_customer_360(user_id, db)
        if data is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        result = await ask_ai_about_customer(data, body.question, body.history)

        # Log to audit trail
        audit = AuditLog(
            entity_type="user",
            entity_id=user_id,
            action="ask_ai",
            user_id=current_user.id,
            details=f"Q: {body.question[:200]}",
        )
        db.add(audit)
        await db.flush()

        return result
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="customer_ask_ai")
        raise


# ---------------------------------------------------------------------------
# GET /{user_id}/alerts — Credit Bureau Alerts
# ---------------------------------------------------------------------------

ALERT_FIELDS = [
    "id", "user_id", "alert_type", "severity", "status",
    "bureau_name", "bureau_reference",
    "title", "description",
    "other_institution", "other_product_type", "other_amount",
    "other_delinquency_days", "other_delinquency_amount",
    "action_taken", "action_notes", "acted_by", "acted_at",
    "alert_date", "received_at", "created_at",
]


@router.get("/{user_id}/alerts")
async def customer_alerts(
    user_id: int,
    status_filter: Optional[str] = Query(None, description="Comma-separated status filter (new,acknowledged,action_taken,dismissed)"),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Return credit bureau alerts for a customer."""
    try:
        q = select(CreditBureauAlert).where(
            CreditBureauAlert.user_id == user_id,
        ).order_by(CreditBureauAlert.alert_date.desc())

        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
            if statuses:
                q = q.where(CreditBureauAlert.status.in_(statuses))

        result = await db.execute(q)
        alerts = result.scalars().all()
        return [_row_to_dict(a, ALERT_FIELDS) for a in alerts]
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="customer_alerts")
        raise


# ---------------------------------------------------------------------------
# PATCH /{user_id}/alerts/{alert_id} — Update alert status / take action
# ---------------------------------------------------------------------------

class AlertActionRequest(BaseModel):
    status: str | None = None  # "acknowledged", "action_taken", "dismissed"
    action_taken: str | None = None  # e.g. "reassess_credit_limit", "freeze_account"
    action_notes: str | None = None


@router.patch("/{user_id}/alerts/{alert_id}")
async def update_alert(
    user_id: int,
    alert_id: int,
    body: AlertActionRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Update a credit bureau alert — acknowledge, take action, or dismiss."""
    try:
        result = await db.execute(
            select(CreditBureauAlert).where(
                CreditBureauAlert.id == alert_id,
                CreditBureauAlert.user_id == user_id,
            )
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        if body.status:
            try:
                alert.status = AlertStatus(body.status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

        if body.action_taken:
            alert.action_taken = body.action_taken
            alert.status = AlertStatus.ACTION_TAKEN
        if body.action_notes:
            alert.action_notes = body.action_notes
        if body.action_taken or body.status:
            alert.acted_by = current_user.id
            alert.acted_at = datetime.now(timezone.utc)

        await db.flush()

        # Audit
        db.add(AuditLog(
            entity_type="credit_bureau_alert",
            entity_id=alert_id,
            action=f"alert_{body.action_taken or body.status or 'updated'}",
            user_id=current_user.id,
            details=body.action_notes or f"Alert {alert_id} updated",
        ))
        await db.flush()

        return _row_to_dict(alert, ALERT_FIELDS)
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="update_alert")
        raise


# ── Staff-Initiated Communication ───────────────────────────────

class InitiateConversationRequest(BaseModel):
    channel: str  # "web" or "whatsapp"
    message: str  # The initial outbound message


@router.post("/{user_id}/conversations")
async def initiate_conversation(
    user_id: int,
    body: InitiateConversationRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation with a customer, initiated by staff.

    The agent is automatically assigned and the first message is recorded
    as an agent message (role=agent).
    """
    try:
        # Verify customer exists
        target = await db.execute(select(User).where(User.id == user_id))
        customer = target.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        # Validate channel
        try:
            channel = ConversationChannel(body.channel)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid channel: {body.channel}. Use 'web' or 'whatsapp'.")

        # For WhatsApp, customer needs a phone number
        if channel == ConversationChannel.WHATSAPP and not customer.phone:
            raise HTTPException(status_code=400, detail="Customer has no phone number on file. Cannot initiate WhatsApp conversation.")

        # Create conversation
        conv = Conversation(
            channel=channel,
            participant_user_id=user_id,
            current_state=ConversationState.ESCALATED_TO_HUMAN,
            entry_point=ConversationEntryPoint.SERVICING,
            assigned_agent_id=current_user.id,
            participant_phone=customer.phone if channel == ConversationChannel.WHATSAPP else None,
        )
        db.add(conv)
        await db.flush()

        # Record the staff message
        msg = ConversationMessage(
            conversation_id=conv.id,
            role=MessageRole.AGENT,
            content=body.message.strip(),
        )
        db.add(msg)
        await db.flush()

        # Audit log
        db.add(AuditLog(
            entity_type="conversation",
            entity_id=conv.id,
            action="staff_initiated_conversation",
            user_id=current_user.id,
            details=f"Staff initiated {channel.value} conversation with customer {user_id}",
        ))
        await db.flush()

        # If WhatsApp, attempt to send via WhatsApp notifier (best effort)
        if channel == ConversationChannel.WHATSAPP and customer.phone:
            try:
                from app.services.whatsapp_notifier import send_whatsapp_message
                await send_whatsapp_message(customer.phone, body.message.strip())
            except Exception:
                logger.warning("WhatsApp send failed for conversation %s — message saved to DB", conv.id)

        return {
            "id": conv.id,
            "channel": conv.channel.value,
            "current_state": conv.current_state.value,
            "participant_user_id": conv.participant_user_id,
            "assigned_agent_id": conv.assigned_agent_id,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "message": {
                "id": msg.id,
                "role": msg.role.value,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="initiate_conversation")
        raise


class StaffSendMessageRequest(BaseModel):
    content: str


@router.post("/{user_id}/conversations/{conversation_id}/messages")
async def staff_send_message(
    user_id: int,
    conversation_id: int,
    body: StaffSendMessageRequest,
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Send a message in an existing conversation as a staff agent."""
    try:
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.participant_user_id == user_id,
            )
            .options(selectinload(Conversation.messages))
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found for this customer")

        # Auto-assign agent if not already assigned
        if not conv.assigned_agent_id:
            conv.assigned_agent_id = current_user.id
            conv.current_state = ConversationState.ESCALATED_TO_HUMAN

        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=MessageRole.AGENT,
            content=body.content.strip(),
        )
        db.add(msg)
        await db.flush()

        # If WhatsApp conversation, attempt to send message via WhatsApp
        if conv.channel == ConversationChannel.WHATSAPP and conv.participant_phone:
            try:
                from app.services.whatsapp_notifier import send_whatsapp_message
                await send_whatsapp_message(conv.participant_phone, body.content.strip())
            except Exception:
                logger.warning("WhatsApp send failed for conversation %s", conv.id)

        return {
            "id": msg.id,
            "conversation_id": conversation_id,
            "role": msg.role.value,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.customers", function_name="staff_send_message")
        raise
