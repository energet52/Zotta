"""AI WhatsApp chatbot service using OpenAI."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.loan import LoanApplication, ApplicantProfile
from app.models.user import User

SYSTEM_PROMPT = """You are Zotta, a friendly and professional AI assistant for a consumer lending company in Trinidad and Tobago. You help loan applicants with:

1. Checking their application status (ask for their reference number like ZOT-2026-XXXXXXXX)
2. Answering FAQs about loan products, eligibility, and required documents
3. Guiding new applicants on how to apply
4. Basic eligibility pre-screening questions

Key information about Zotta loans:
- Personal loans from TTD 5,000 to TTD 500,000
- Terms from 3 to 84 months
- Interest rates from 8.5% to 22% depending on credit profile
- Eligibility: 18-65 years old, minimum monthly income TTD 3,000
- Required documents: National ID/Passport, Proof of Income (pay slip or job letter), Utility Bill (proof of address)
- Apply online at our consumer portal

Important rules:
- Never share confidential financial details via WhatsApp
- For status queries, only share high-level status (e.g., "under review", "approved")
- Always be polite and professional
- If you can't help, suggest they call our office or visit the portal
- Keep responses concise (WhatsApp-friendly, short paragraphs)
- Use Trinidad English naturally (e.g., "no problem" rather than overly formal language)
"""


async def process_message(
    message: str,
    phone_number: str,
    history: list[tuple[str, str]],
    db: AsyncSession,
) -> str:
    """Process an incoming WhatsApp message and generate a response.

    Args:
        message: The user's message text.
        phone_number: The user's phone number.
        history: List of (role, content) tuples from conversation history.
        db: Database session for looking up application data.

    Returns:
        Response text to send back via WhatsApp.
    """
    # Check if message contains a reference number
    context = ""
    if "ZOT-" in message.upper():
        # Extract reference number
        words = message.upper().split()
        ref = next((w for w in words if w.startswith("ZOT-")), None)
        if ref:
            context = await _lookup_application(ref, db)

    # Check if we can link by phone number
    if not context:
        user_context = await _lookup_by_phone(phone_number, db)
        if user_context:
            context = user_context

    # Build messages for AI
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context:
        messages.append({
            "role": "system",
            "content": f"Context about this applicant:\n{context}"
        })

    # Add conversation history (last 10 messages)
    for role, content in history[-10:]:
        messages.append({"role": role, "content": content})

    # Add current message
    messages.append({"role": "user", "content": message})

    # Call OpenAI
    try:
        if not settings.openai_api_key or settings.openai_api_key == "your-openai-api-key":
            return _fallback_response(message, context)

        import openai
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content

    except Exception as e:
        return _fallback_response(message, context)


async def _lookup_application(ref_number: str, db: AsyncSession) -> str:
    """Look up an application by reference number."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.reference_number == ref_number)
    )
    app = result.scalar_one_or_none()
    if not app:
        return f"No application found with reference {ref_number}"

    return (
        f"Application {app.reference_number}: Status is '{app.status.value}'. "
        f"Amount requested: TTD {float(app.amount_requested):,.2f}. "
        f"Term: {app.term_months} months."
    )


async def _lookup_by_phone(phone: str, db: AsyncSession) -> str:
    """Look up a user by phone number."""
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        return ""

    apps_result = await db.execute(
        select(LoanApplication)
        .where(LoanApplication.applicant_id == user.id)
        .order_by(LoanApplication.created_at.desc())
    )
    apps = apps_result.scalars().all()
    if not apps:
        return f"Applicant: {user.first_name}. No active applications."

    app_summaries = []
    for a in apps[:3]:
        app_summaries.append(f"  - {a.reference_number}: {a.status.value}")

    return f"Applicant: {user.first_name}. Applications:\n" + "\n".join(app_summaries)


def _fallback_response(message: str, context: str) -> str:
    """Basic rule-based fallback when OpenAI is not available."""
    msg_lower = message.lower()

    if any(w in msg_lower for w in ["status", "application", "check", "update"]):
        if context and "No application found" not in context:
            return f"Here's what I found:\n{context}\n\nFor more details, please log in to our consumer portal."
        return (
            "To check your application status, please provide your reference number "
            "(it looks like ZOT-2026-XXXXXXXX). You can also log in to our consumer portal to see full details."
        )

    if any(w in msg_lower for w in ["apply", "loan", "borrow", "need money"]):
        return (
            "Great! Zotta offers personal loans from TTD 5,000 to TTD 500,000 with terms up to 84 months.\n\n"
            "To apply, you'll need:\n"
            "1. National ID or Passport\n"
            "2. Proof of income (pay slip or job letter)\n"
            "3. A recent utility bill\n\n"
            "Visit our consumer portal to start your application!"
        )

    if any(w in msg_lower for w in ["rate", "interest", "cost"]):
        return (
            "Our interest rates range from 8.5% to 22% per annum, depending on your credit profile.\n"
            "Better credit = lower rates! Apply online to get your personalized quote."
        )

    if any(w in msg_lower for w in ["document", "upload", "required", "need"]):
        return (
            "For your loan application, you'll need to upload:\n"
            "1. National ID card, Passport, or Driver's License\n"
            "2. Proof of income (recent pay slip or employment letter)\n"
            "3. Utility bill (proof of address, less than 3 months old)\n\n"
            "You can upload these in the consumer portal."
        )

    if any(w in msg_lower for w in ["hi", "hello", "hey", "good morning", "good afternoon"]):
        return (
            "Hello! Welcome to Zotta. I can help you with:\n"
            "- Checking your application status\n"
            "- Information about our loan products\n"
            "- Guidance on how to apply\n\n"
            "How can I help you today?"
        )

    return (
        "Thanks for reaching out to Zotta! I can help with:\n"
        "- Application status (share your reference number)\n"
        "- Loan product information\n"
        "- How to apply\n\n"
        "For anything else, please call our office or visit our consumer portal."
    )
