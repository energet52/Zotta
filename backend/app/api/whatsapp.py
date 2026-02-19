"""WhatsApp webhook handler for Twilio integration.

Routes inbound messages to:
1. Customer Support conversations (if the sender has an active WhatsApp conversation)
2. Collections chat (if the sender has an active collection case with prior outbound messages)
"""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.loan import LoanApplication, LoanStatus
from app.models.collection import (
    CollectionChat, ChatDirection, ChatMessageStatus,
)
from app.models.conversation import (
    Conversation, ConversationChannel, ConversationMessage,
    ConversationState, MessageRole,
)
from app.services.error_logger import log_error
from fastapi import HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_twilio_signature(request: Request, body_params: dict) -> bool:
    """Verify the X-Twilio-Signature header to ensure the request is authentic.
    Returns True if verification passes or if Twilio credentials are not configured."""
    if not settings.twilio_auth_token:
        return True  # Skip verification when Twilio is not configured (dev/test)
    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(settings.twilio_auth_token)
        signature = request.headers.get("X-Twilio-Signature", "")

        # Twilio signs against the public URL it sent the request to, but behind
        # ngrok / reverse-proxy the internal request.url differs. Reconstruct the
        # original URL from X-Forwarded-* headers when present.
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        host = request.headers.get("X-Forwarded-Host",
                                   request.headers.get("Host", request.url.netloc))
        url = f"{proto}://{host}{request.url.path}"
        if request.url.query:
            url += f"?{request.url.query}"

        return validator.validate(url, body_params, signature)
    except Exception:
        logger.warning("Twilio signature verification failed", exc_info=True)
        return False


async def _route_to_conversations(phone: str, body: str, db: AsyncSession) -> bool:
    """Deliver the inbound message to any active Customer Support conversations
    that match this phone number (directly or via user).

    Returns True if at least one message was stored.
    """
    # Closed/terminal states where we should NOT append new messages
    _CLOSED_STATES = {
        ConversationState.EXPIRED,
        ConversationState.WITHDRAWN,
        ConversationState.DECLINED,
    }

    # Find conversations by participant_phone
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.channel == ConversationChannel.WHATSAPP,
            Conversation.participant_phone == phone,
            Conversation.current_state.notin_(_CLOSED_STATES),
        ).order_by(Conversation.last_activity_at.desc())
    )
    conversations = list(conv_result.scalars().all())

    # Also try matching via user phone → participant_user_id
    if not conversations:
        user_result = await db.execute(
            select(User.id).where(User.phone == phone)
        )
        user_ids = [row[0] for row in user_result.all()]
        if user_ids:
            conv_result2 = await db.execute(
                select(Conversation).where(
                    Conversation.channel == ConversationChannel.WHATSAPP,
                    Conversation.participant_user_id.in_(user_ids),
                    Conversation.current_state.notin_(_CLOSED_STATES),
                ).order_by(Conversation.last_activity_at.desc())
            )
            conversations = list(conv_result2.scalars().all())

    if not conversations:
        return False

    for conv in conversations:
        msg = ConversationMessage(
            conversation_id=conv.id,
            role=MessageRole.USER,
            content=body,
        )
        db.add(msg)
        logger.info(
            "WhatsApp inbound routed to conversation %s from %s",
            conv.id, phone,
        )

    await db.flush()
    return True


async def _route_to_collections(phone: str, body: str, db: AsyncSession) -> bool:
    """Store the inbound message in CollectionChat for any disbursed loan
    belonging to this phone number, so it appears in the collection timeline.

    Returns True if at least one CollectionChat record was created.
    """
    # Find borrower(s) by phone number
    user_result = await db.execute(
        select(User.id).where(User.phone == phone)
    )
    user_ids = [row[0] for row in user_result.all()]
    if not user_ids:
        return False

    # Find their disbursed loans (the ones that appear in collections)
    loan_result = await db.execute(
        select(LoanApplication.id).where(
            LoanApplication.applicant_id.in_(user_ids),
            LoanApplication.status == LoanStatus.DISBURSED,
        )
    )
    loan_ids = [row[0] for row in loan_result.all()]
    if not loan_ids:
        return False

    for loan_id in loan_ids:
        inbound = CollectionChat(
            loan_application_id=loan_id,
            agent_id=None,
            phone_number=phone,
            direction=ChatDirection.INBOUND,
            message=body,
            channel="whatsapp",
            status=ChatMessageStatus.DELIVERED,
        )
        db.add(inbound)
        logger.info(
            "Collections inbound message stored for loan %s from %s",
            loan_id, phone,
        )

    await db.flush()
    return True


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming WhatsApp messages from Twilio.

    Routes to Customer Support conversations and/or Collections chat.
    """
    try:
        # Parse ALL form parameters — Twilio signs over every field it sends
        form_data = await request.form()
        body_params: dict[str, str] = {k: str(v) for k, v in form_data.items()}

        Body = body_params.get("Body", "")
        From = body_params.get("From", "")
        To = body_params.get("To", "")

        # Verify Twilio signature using ALL form params
        if not _verify_twilio_signature(request, body_params):
            raise HTTPException(status_code=403, detail="Invalid request signature")

        phone_number = From.replace("whatsapp:", "").strip()
        # URL-encoded form data converts '+' to space — restore it
        if phone_number and not phone_number.startswith("+"):
            phone_number = "+" + phone_number.lstrip()

        # ── Conversation routing (Customer Support chat) ───────────────
        conv_routed = await _route_to_conversations(phone_number, Body, db)

        # ── Collections routing ───────────────────────────────────────
        coll_routed = await _route_to_collections(phone_number, Body, db)

        if conv_routed or coll_routed:
            targets = []
            if conv_routed:
                targets.append("conversations")
            if coll_routed:
                targets.append("collections")
            logger.info("Inbound WhatsApp from %s routed to %s", phone_number, " + ".join(targets))
        else:
            logger.info("Inbound WhatsApp from %s — no matching conversation or collection, message acknowledged", phone_number)

        await db.commit()

        # Return empty TwiML (no auto-reply — Customer Support chat is web-only)
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return Response(content=twiml, media_type="application/xml")
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.whatsapp", function_name="whatsapp_webhook")
        raise
