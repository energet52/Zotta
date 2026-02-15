"""Intent classification for conversation routing.

Classifies borrower intent within 2-3 exchanges. Used to route to
application flow, servicing, or other paths.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.loan import LoanApplication, LoanStatus
from app.models.user import User

INTENT_CATEGORIES = [
    "new_loan",
    "top_up_refinance",
    "pre_qual_check",
    "rate_inquiry",
    "status_check",
    "servicing",
    "complaint",
    "general_info",
]


async def classify_intent(
    message: str,
    history: list[tuple[str, str]],
    db: AsyncSession,
    user_id: int | None = None,
) -> tuple[str, float]:
    """Classify intent from the latest message and history.

    Returns (intent_category, confidence_0_to_1).
    """
    # Quick heuristics for common patterns
    msg_lower = message.lower().strip()
    if any(w in msg_lower for w in ["balance", "payment", "pay", "overdue", "statement", "payoff"]):
        if user_id:
            apps = await _get_user_loans(user_id, db)
            if apps:
                return "servicing", 0.9
        return "servicing", 0.7
    if any(w in msg_lower for w in ["status", "check", "update", "application", "zot-"]):
        return "status_check", 0.85
    if any(w in msg_lower for w in ["rate", "interest", "cost", "how much would"]):
        return "rate_inquiry", 0.8
    if any(w in msg_lower for w in ["qualify", "eligible", "how much can i"]):
        return "pre_qual_check", 0.8
    if any(w in msg_lower for w in ["apply", "loan", "borrow", "need money", "want to buy"]):
        return "new_loan", 0.85
    if any(w in msg_lower for w in ["top up", "top-up", "refinance", "restructure"]):
        return "top_up_refinance", 0.8
    if any(w in msg_lower for w in ["complaint", "unhappy", "speak to human", "manager"]):
        return "complaint", 0.9
    if any(w in msg_lower for w in ["hi", "hello", "hey"]):
        return "general_info", 0.5

    # Use LLM for nuanced classification
    try:
        if settings.openai_api_key and settings.openai_api_key != "your-openai-api-key":
            import json
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            history_text = "\n".join([f"{r}: {c}" for r, c in history[-4:]])
            prompt = f"""Classify the borrower's intent from this loan/lending conversation.

Recent messages:
{history_text}

Latest user message: {message}

Reply with JSON only: {{"intent": "one of {INTENT_CATEGORIES}", "confidence": 0.0-1.0}}
"""
            resp = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80,
                temperature=0,
            )
            text = resp.choices[0].message.content.strip()
            # Extract JSON
            start = text.find("{")
            if start >= 0:
                data = json.loads(text[start : text.rfind("}") + 1])
                intent = data.get("intent", "general_info")
                if intent not in INTENT_CATEGORIES:
                    intent = "general_info"
                conf = float(data.get("confidence", 0.6))
                return intent, conf
    except Exception:
        pass

    return "general_info", 0.5


async def _get_user_loans(user_id: int, db: AsyncSession) -> list:
    """Get user's disbursed or active loans."""
    result = await db.execute(
        select(LoanApplication).where(
            LoanApplication.applicant_id == user_id,
            LoanApplication.status.in_([
                LoanStatus.DISBURSED,
                LoanStatus.ACCEPTED,
                LoanStatus.OFFER_SENT,
            ]),
        )
    )
    return result.scalars().all()
