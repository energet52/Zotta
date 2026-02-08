"""WhatsApp webhook handler for Twilio integration."""

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.chat import ChatSession, ChatMessage
from app.services.whatsapp_bot import process_message

router = APIRouter()


@router.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(""),
    From: str = Form(""),
    To: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming WhatsApp messages from Twilio."""
    phone_number = From.replace("whatsapp:", "")

    # Get or create session
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.phone_number == phone_number, ChatSession.status == "active")
        .order_by(ChatSession.created_at.desc())
    )
    session = result.scalars().first()

    if not session:
        session = ChatSession(phone_number=phone_number)
        db.add(session)
        await db.flush()

    # Save incoming message
    user_msg = ChatMessage(session_id=session.id, role="user", content=Body)
    db.add(user_msg)

    # Get conversation history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    )
    history = history_result.scalars().all()

    # Process with AI
    response_text = await process_message(
        message=Body,
        phone_number=phone_number,
        history=[(m.role, m.content) for m in history],
        db=db,
    )

    # Save bot response
    bot_msg = ChatMessage(session_id=session.id, role="assistant", content=response_text)
    db.add(bot_msg)

    # Return TwiML response
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response_text}</Message>
</Response>"""

    return Response(content=twiml, media_type="application/xml")
