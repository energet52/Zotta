"""WhatsApp webhook handler for Twilio integration.

Routes inbound messages to the Collections chat when the sender has an active
collection case, so agents can see borrower replies in the collection detail view.

The Customer Support chat is web-only — WhatsApp inbound messages are NOT forwarded to it.
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
        url = str(request.url)
        return validator.validate(url, body_params, signature)
    except Exception:
        logger.warning("Twilio signature verification failed")
        return False


async def _route_to_collections(phone: str, body: str, db: AsyncSession) -> bool:
    """If this phone has any active collection chat, store the inbound message.

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

    # Only add to loans that already have outbound collection chats
    chat_result = await db.execute(
        select(CollectionChat.loan_application_id)
        .where(
            CollectionChat.loan_application_id.in_(loan_ids),
            CollectionChat.direction == ChatDirection.OUTBOUND,
        )
        .group_by(CollectionChat.loan_application_id)
    )
    active_loan_ids = [row[0] for row in chat_result.all()]

    if not active_loan_ids:
        return False

    for loan_id in active_loan_ids:
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
    Body: str = Form(""),
    From: str = Form(""),
    To: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming WhatsApp messages from Twilio.

    Routes to Collections chat if the sender has an active collection case.
    Otherwise acknowledges the message silently (no auto-reply).
    """
    try:
        # Verify Twilio signature to prevent message injection
        if not _verify_twilio_signature(request, {"Body": Body, "From": From, "To": To}):
            raise HTTPException(status_code=403, detail="Invalid request signature")

        phone_number = From.replace("whatsapp:", "").strip()
        # URL-encoded form data converts '+' to space — restore it
        if phone_number and not phone_number.startswith("+"):
            phone_number = "+" + phone_number.lstrip()

        # ── Collections routing ───────────────────────────────────────
        routed = await _route_to_collections(phone_number, Body, db)

        if routed:
            logger.info("Inbound WhatsApp from %s routed to collections", phone_number)
        else:
            logger.info("Inbound WhatsApp from %s — no active collection case, message acknowledged", phone_number)

        await db.commit()

        # Return empty TwiML (no auto-reply — Customer Support chat is web-only)
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return Response(content=twiml, media_type="application/xml")
    except HTTPException:
        raise
    except Exception as e:
        await log_error(e, db=db, module="api.whatsapp", function_name="whatsapp_webhook")
        raise
