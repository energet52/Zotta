"""AI conversation processor for the Customer Support chat flow.

Processes user messages, maintains context from conversation state and application,
and generates appropriate responses. Phase 2: intent classification, entry points, product recommendation.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.conversation import Conversation, ConversationMessage, ConversationState, MessageRole
from app.models.loan import LoanApplication, ApplicantProfile
from app.models.payment import PaymentSchedule, Payment
from app.models.user import User
from app.services.intent_classifier import classify_intent
from app.services.product_recommender import get_recommended_products
from app.services.payment_calculator import calculate_payment as calc_payment
from app.services.pre_qual import pre_qualify

SYSTEM_PROMPT = """You are Zotta Customer Support, a friendly and professional assistant for a consumer lending company in Trinidad and Tobago. You help borrowers with their accounts, loan information, payments, and new applications.

Current conversation state: {current_state}
{entry_point_instruction}

Key information about Zotta:
- Personal loans from TTD 5,000 to TTD 500,000
- Terms from 3 to 84 months
- Interest rates from 8.5% to 22% depending on credit profile
- Eligibility: 18-65 years old, minimum monthly income TTD 3,000

WHAT YOU CAN SHARE (consumer-facing information the customer already has access to in the portal):
- Loan balances, remaining balance, total paid, loan amounts
- Payment schedule details: due dates, installment amounts, principal/interest breakdown
- Arrears information: overdue amounts, days past due, whether they are in arrears
- Application status: submitted, approved, declined, disbursed, etc.
- Payment history: past payments and their dates
- Next payment due date and amount
- Interest rates on their loans
- Loan terms and monthly payment amounts
- Number of installments paid vs total

WHAT YOU MUST NEVER SHARE (internal lender operations):
- Credit scores, credit bureau data, or credit report details
- Decision engine logic, scoring models, or approval criteria
- Internal risk assessments or risk ratings
- Underwriter notes, internal comments, or staff communications
- Debt-service ratios (DSR/DTI) or how they were calculated
- Rule configurations or decision thresholds
- Information about other customers or their accounts
- Internal collection strategies or escalation decisions
- Any backend system details or technical implementation

Rules:
- Be conversational and natural, not form-like
- Match the borrower's tone (formal or casual)
- Use Trinidad English naturally
- Keep responses concise but helpful
- When the customer asks about balance, payments, arrears, etc. — use the account context provided to give specific answers
- For application status: use the context data to provide real status information
- If you don't have the data in context, suggest they check the portal or call customer service
- When intent is new_loan and borrower describes a need (e.g. "fix my roof"), recommend products from the product list if provided
- Confirm classified intent with the borrower before proceeding when confidence is below 0.8
- When state is credit_check_consent: you MUST obtain explicit consent before any credit pull. Say: "To continue, I need your permission to check your credit history. This is a standard part of the loan process. It will show as an inquiry on your credit report. Do you agree?" Only proceed once they say yes/I agree.
- If asked about credit scores, decisioning, or internal processes, politely explain that you cannot share that information but can help with their account details.
"""


async def process_conversation_message(
    conversation: Conversation,
    user_message: str,
    db: AsyncSession,
) -> tuple[str, dict | None]:
    """Process a user message and generate an AI response.

    Args:
        conversation: The conversation record with messages loaded.
        user_message: The user's message text.
        db: Database session.

    Returns:
        Tuple of (response_text, metadata_dict or None).
        metadata can include: intent, extracted_data, suggested_state_transition.
    """
    # Build context from application if linked
    context = ""
    if conversation.loan_application_id:
        app_context = await _get_application_context(conversation.loan_application_id, db)
        if app_context:
            context = app_context

    # Build participant context
    if conversation.participant_user_id:
        user_context = await _get_user_context(conversation.participant_user_id, db)
        if user_context:
            context = (context + "\n\n" + user_context).strip() if context else user_context

    # Build message history
    history = []
    if conversation.messages:
        for m in conversation.messages[-10:]:
            role = "user" if m.role == MessageRole.USER else "assistant"
            history.append({"role": role, "content": m.content})

    # Classify intent
    history_tuples = [(m["role"], m["content"]) for m in history]
    intent, confidence = await classify_intent(
        user_message, history_tuples, db, conversation.participant_user_id
    )
    metadata = {"intent": intent, "confidence": confidence}

    # Entry point handling
    entry_instruction = ""
    if conversation.entry_point:
        ep = conversation.entry_point.value
        if ep == "pre_qualified" and conversation.entry_context:
            ctx = conversation.entry_context
            entry_instruction = f"\nEntry context: Borrower arrived via pre-qualified link. Context: {ctx}. Acknowledge and skip redundant discovery."
        elif ep == "returning_applicant":
            entry_instruction = "\nEntry context: Borrower may have an incomplete application. Offer to continue from where they left off."
        elif ep == "existing_customer":
            entry_instruction = "\nEntry context: Borrower is an existing customer. Reference their prior loans if in context."
        elif ep == "servicing":
            entry_instruction = "\nEntry context: Route to servicing flow (balance, payment, payoff, restructure)."

    # Product recommendation when intent is new_loan and user describes a need
    product_context = ""
    if intent == "new_loan" and len(user_message.split()) > 3:
        products = await get_recommended_products(user_message, None, db)
        if products:
            lines = ["Available products that may suit their need:"]
            for p in products:
                lines.append(f"  - {p['name']}: TTD {p['min_amount']:,.0f}-{p['max_amount']:,.0f}, {p['term_range']}. {p['plain_reason']}")
            product_context = "\n".join(lines)

    # Document requirements when in DOCUMENTS_PENDING
    doc_context = ""
    if conversation.current_state == ConversationState.DOCUMENTS_PENDING:
        from app.services.document_requirements import get_required_documents
        employment_type = None
        amount = 0
        if conversation.loan_application_id:
            app_r = await db.execute(select(LoanApplication).where(LoanApplication.id == conversation.loan_application_id))
            app = app_r.scalar_one_or_none()
            if app:
                amount = float(app.amount_requested)
                if conversation.participant_user_id:
                    prof_r = await db.execute(
                        select(ApplicantProfile).where(ApplicantProfile.user_id == conversation.participant_user_id)
                    )
                    prof = prof_r.scalar_one_or_none()
                    if prof:
                        employment_type = prof.employment_type
        docs = get_required_documents(employment_type, amount, is_secured=False)
        lines = ["Required documents for this application:"]
        for d in docs:
            lines.append(f"  - {d['label']}: {d['why']}")
        doc_context = "\n".join(lines)

    # Pre-qualification and payment illustration when we have application + profile
    prequal_context = ""
    if conversation.loan_application_id and conversation.participant_user_id:
        app_ctx = await _get_application_and_profile(
            conversation.loan_application_id, conversation.participant_user_id, db
        )
        if app_ctx:
            prequal_context = app_ctx

    # System prompt with state and entry point
    system = SYSTEM_PROMPT.format(
        current_state=conversation.current_state.value,
        entry_point_instruction=entry_instruction or "",
    )

    messages = [{"role": "system", "content": system}]
    ctx_parts = [context] if context else []
    if product_context:
        ctx_parts.append(product_context)
    if doc_context:
        ctx_parts.append(doc_context)
    if prequal_context:
        ctx_parts.append(prequal_context)
    if ctx_parts:
        messages.append({"role": "system", "content": "Context:\n\n" + "\n\n".join(ctx_parts)})
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Call LLM
    try:
        if not settings.openai_api_key or settings.openai_api_key == "your-openai-api-key":
            reply = _fallback_response(user_message, context, conversation.current_state)
            return reply, None

        import openai
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
        metadata["reasoning"] = "Generated from conversation context"
        return reply, metadata
    except Exception:
        return _fallback_response(user_message, context, conversation.current_state), None


def _fallback_response(
    message: str,
    context: str,
    state: ConversationState,
) -> str:
    """Rule-based fallback when OpenAI is unavailable."""
    msg_lower = message.lower()

    if any(w in msg_lower for w in ["hi", "hello", "hey", "good morning", "good afternoon", "hola"]):
        return (
            "Hello! Welcome to Zotta Customer Support. I can help you with:\n"
            "- Your loan balance and payment schedule\n"
            "- Checking your application status\n"
            "- Arrears and overdue information\n"
            "- Applying for a new loan\n"
            "- Information about our products\n\n"
            "How can I help you today?"
        )

    if any(w in msg_lower for w in ["balance", "owe", "remaining", "outstanding", "how much"]):
        if context and "Remaining balance" in context:
            return f"Here's your account information:\n\n{context}\n\nIs there anything else you'd like to know?"
        return (
            "I'd love to help with your balance! Please log in so I can look up your account, "
            "or visit the 'My Loans' section in your portal to see your current balance."
        )

    if any(w in msg_lower for w in ["arrears", "overdue", "late", "past due", "behind", "delinquen"]):
        if context and ("IN ARREARS" in context or "overdue" in context.lower()):
            return f"Here's your arrears information:\n\n{context}\n\nWould you like to discuss payment options?"
        if context and "current" in context.lower():
            return "Good news — your account is current with no overdue payments! Is there anything else I can help with?"
        return (
            "To check your arrears status, please log in to your account. "
            "You can also visit 'My Loans' in the portal to see your payment status."
        )

    if any(w in msg_lower for w in ["payment", "pay", "next payment", "when", "due"]):
        if context and "Next payment" in context:
            return f"Here's your payment information:\n\n{context}\n\nWould you like to make a payment through the portal?"
        return (
            "To see your payment schedule and next due date, visit 'My Loans' in your portal. "
            "You can also make payments there."
        )

    if any(w in msg_lower for w in ["score", "credit score", "credit report", "bureau"]):
        return (
            "I'm not able to share credit score or credit bureau information. "
            "That's handled by our internal team during the application review process. "
            "Is there anything else I can help you with — like your balance or payment schedule?"
        )

    if any(w in msg_lower for w in ["status", "application", "check", "update"]):
        if context and "No application" not in context:
            return f"Here's what I found:\n\n{context}\n\nFor full details, check your portal."
        return (
            "To check your application status, please share your reference number "
            "(e.g. ZOT-2026-XXXXXXXX) or log in to our consumer portal."
        )

    if any(w in msg_lower for w in ["apply", "loan", "borrow", "need money", "want to apply"]):
        return (
            "Great! I can help you apply. Zotta offers personal loans from TTD 5,000 to TTD 500,000 "
            "with terms up to 84 months.\n\n"
            "To get started, what do you need the loan for? (e.g. home improvement, medical, vehicle, personal)"
        )

    if any(w in msg_lower for w in ["rate", "interest", "cost"]):
        return (
            "Our interest rates range from 8.5% to 22% per annum, depending on your credit profile. "
            "Would you like to apply to get your personalized quote?"
        )

    if any(w in msg_lower for w in ["document", "upload", "required", "need"]):
        return (
            "For a loan application, we typically need:\n"
            "1. National ID or Passport\n"
            "2. Proof of income (pay slip or job letter)\n"
            "3. Utility bill (proof of address, less than 3 months old)\n\n"
            "I can guide you through the application step by step. Ready to start?"
        )

    return (
        "Thanks for your message! I can help with your account balance, payments, arrears, "
        "application status, or a new loan. What would you like to know?"
    )


async def _get_application_context(application_id: int, db: AsyncSession) -> str | None:
    """Build context string from a loan application."""
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        return None
    return (
        f"Application {app.reference_number}: Status '{app.status.value}'. "
        f"Amount: TTD {float(app.amount_requested):,.2f}. Term: {app.term_months} months."
    )


async def _get_application_and_profile(
    application_id: int, user_id: int, db: AsyncSession
) -> str | None:
    """Build pre-qual and payment illustration context from application + profile."""
    from app.models.loan import ApplicantProfile
    from datetime import date
    app_result = await db.execute(select(LoanApplication).where(LoanApplication.id == application_id))
    app = app_result.scalar_one_or_none()
    if not app:
        return None
    profile_result = await db.execute(select(ApplicantProfile).where(ApplicantProfile.user_id == user_id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        return None
    income = float(profile.monthly_income or 0)
    expenses = float(profile.monthly_expenses or 0)
    debt = float(profile.existing_debt or 0)
    amount = float(app.amount_requested)
    term = app.term_months
    age = None
    if profile.date_of_birth:
        today = date.today()
        age = today.year - profile.date_of_birth.year
        if (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day):
            age -= 1
    # Payment illustration at 15% (placeholder - product rate would be used in real flow)
    rate = 15.0
    calc = calc_payment(amount, rate, term)
    pq = pre_qualify(income, expenses, debt, amount, term, age, calc.get("monthly_payment"))
    lines = [
        f"Pre-qual: {pq['outcome']}. DTI: {pq['dti_ratio']*100:.0f}%. {pq['message']}",
        f"Payment illustration at {rate}%: TTD {calc['monthly_payment']:,.2f}/month, total interest TTD {calc['total_interest']:,.2f}.",
    ]
    if pq.get("suggestions"):
        lines.append("Suggestions: " + "; ".join(pq["suggestions"]))
    return "\n".join(lines)


async def _get_user_context(user_id: int, db: AsyncSession) -> str | None:
    """Build rich context string from user's applications, balances, schedules, and arrears."""
    from datetime import date as date_cls

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    apps_result = await db.execute(
        select(LoanApplication)
        .where(LoanApplication.applicant_id == user_id)
        .order_by(LoanApplication.created_at.desc())
        .limit(10)
    )
    apps = apps_result.scalars().all()
    if not apps:
        return f"Customer: {user.first_name or 'Customer'}. No applications or loans yet."

    today = date_cls.today()
    lines = [f"Customer: {user.first_name or 'Customer'} (ID: {user_id})."]
    lines.append(f"Email: {user.email}")
    lines.append("")

    total_outstanding = 0.0
    total_overdue = 0.0

    for app in apps:
        lines.append(f"--- Loan: {app.reference_number} ---")
        lines.append(f"  Status: {app.status.value}")
        lines.append(f"  Amount requested: TTD {float(app.amount_requested):,.2f}")
        if app.amount_approved:
            lines.append(f"  Amount approved: TTD {float(app.amount_approved):,.2f}")
        if app.interest_rate:
            lines.append(f"  Interest rate: {float(app.interest_rate):.1f}%")
        if app.monthly_payment:
            lines.append(f"  Monthly payment: TTD {float(app.monthly_payment):,.2f}")
        lines.append(f"  Term: {app.term_months} months")

        # Get payment schedule for this loan
        sched_result = await db.execute(
            select(PaymentSchedule)
            .where(PaymentSchedule.loan_application_id == app.id)
            .order_by(PaymentSchedule.installment_number)
        )
        schedules = sched_result.scalars().all()

        if schedules:
            total_due = sum(float(s.amount_due) for s in schedules)
            total_paid = sum(float(s.amount_paid) for s in schedules)
            remaining = round(total_due - total_paid, 2)
            total_outstanding += remaining

            paid_count = sum(1 for s in schedules if s.status.value == 'paid')
            total_count = len(schedules)

            lines.append(f"  Total due over life of loan: TTD {total_due:,.2f}")
            lines.append(f"  Total paid so far: TTD {total_paid:,.2f}")
            lines.append(f"  Remaining balance: TTD {remaining:,.2f}")
            lines.append(f"  Installments paid: {paid_count} of {total_count}")

            # Overdue installments
            overdue = [
                s for s in schedules
                if s.due_date < today and s.status.value != 'paid'
            ]
            if overdue:
                overdue_amount = sum(float(s.amount_due) - float(s.amount_paid) for s in overdue)
                total_overdue += overdue_amount
                worst_dpd = max((today - s.due_date).days for s in overdue)
                lines.append(f"  ⚠ IN ARREARS: TTD {overdue_amount:,.2f} overdue, {len(overdue)} overdue installment(s), worst {worst_dpd} days past due")
            else:
                lines.append(f"  Arrears: None — account is current")

            # Next upcoming payment
            upcoming = [s for s in schedules if s.status.value != 'paid' and s.due_date >= today]
            if upcoming:
                nxt = upcoming[0]
                lines.append(f"  Next payment: TTD {float(nxt.amount_due):,.2f} due on {nxt.due_date.strftime('%d %b %Y')} (installment #{nxt.installment_number})")

        # Get recent payment history
        pay_result = await db.execute(
            select(Payment)
            .where(Payment.loan_application_id == app.id)
            .order_by(Payment.payment_date.desc())
            .limit(5)
        )
        payments = pay_result.scalars().all()
        if payments:
            lines.append(f"  Recent payments:")
            for p in payments:
                lines.append(f"    - TTD {float(p.amount):,.2f} on {p.payment_date.strftime('%d %b %Y')} ({p.payment_type.value})")

        lines.append("")

    # Summary
    lines.insert(2, f"Total outstanding across all loans: TTD {total_outstanding:,.2f}")
    if total_overdue > 0:
        lines.insert(3, f"Total overdue: TTD {total_overdue:,.2f}")
    else:
        lines.insert(3, "Total overdue: None — all accounts current")

    return "\n".join(lines)
