"""WhatsApp notification service using Twilio REST API.

Sends WhatsApp messages via the Twilio API.  In non-production environments
the recipient is always overridden with the configured sandbox phone number
so real customers are never contacted during development / testing.
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TWILIO_MESSAGES_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
)


async def send_whatsapp_message(to_phone: str, body: str) -> dict[str, Any]:
    """Send a WhatsApp message via Twilio.

    Parameters
    ----------
    to_phone : str
        Recipient phone number in E.164 format (e.g. ``+18681234567``).
        In non-production mode this is ignored and the sandbox number is
        used instead.
    body : str
        Plain-text message body.

    Returns
    -------
    dict
        Twilio API response JSON on success, or ``{"error": "..."}`` on
        failure.  This function never raises — notification failures must
        not break the calling flow.
    """

    sid = settings.twilio_account_sid
    token = settings.twilio_auth_token

    if not sid or not token:
        logger.warning("Twilio credentials not configured — skipping WhatsApp send")
        return {"error": "Twilio credentials not configured"}

    # In sandbox / development mode always send to the sandbox phone
    if settings.environment != "production":
        to_phone = settings.whatsapp_sandbox_phone

    # Ensure the ``whatsapp:`` prefix
    if not to_phone.startswith("whatsapp:"):
        to_phone = f"whatsapp:{to_phone}"

    from_number = settings.twilio_whatsapp_number
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"

    url = TWILIO_MESSAGES_URL.format(sid=sid)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "To": to_phone,
                    "From": from_number,
                    "Body": body,
                },
                auth=(sid, token),
                timeout=15.0,
            )

        result = response.json()

        if response.status_code >= 400:
            logger.error(
                "Twilio API error %s: %s",
                response.status_code,
                result.get("message", result),
            )
            return {"error": result.get("message", str(result)), "status_code": response.status_code}

        logger.info(
            "WhatsApp message sent — SID %s, to %s",
            result.get("sid"),
            to_phone,
        )
        return result

    except Exception as exc:
        logger.error("Failed to send WhatsApp message: %s", exc)
        return {"error": str(exc)}


# ===================================================================
# Application status notification helpers
# ===================================================================

async def notify_application_approved(
    to_phone: str,
    first_name: str,
    reference: str,
    amount_approved: float,
    monthly_payment: float | None = None,
) -> dict[str, Any]:
    """Notify applicant that their loan has been approved."""
    amt = f"TTD {amount_approved:,.2f}"
    pmt = f"TTD {monthly_payment:,.2f}" if monthly_payment else "TBD"
    msg = (
        f"Hi {first_name}, great news! Your loan application {reference} for "
        f"{amt} has been approved. Monthly payment: {pmt}. "
        f"Log in to your Zotta account to review the details."
    )
    return await send_whatsapp_message(to_phone, msg)


async def notify_application_declined(
    to_phone: str,
    first_name: str,
    reference: str,
) -> dict[str, Any]:
    """Notify applicant that their loan application was declined."""
    msg = (
        f"Hi {first_name}, thank you for your loan application {reference}. "
        f"After careful review, we are unable to approve your application at "
        f"this time. Please contact us if you have any questions or would like "
        f"to discuss your options."
    )
    return await send_whatsapp_message(to_phone, msg)


async def notify_documents_requested(
    to_phone: str,
    first_name: str,
    reference: str,
) -> dict[str, Any]:
    """Notify applicant that additional documents are required."""
    msg = (
        f"Hi {first_name}, regarding your loan application {reference}: "
        f"we need some additional documents to continue processing. "
        f"Please log in to your Zotta account to upload the required documents. "
        f"Feel free to reply if you need help."
    )
    return await send_whatsapp_message(to_phone, msg)


async def notify_loan_disbursed(
    to_phone: str,
    first_name: str,
    reference: str,
    amount: float,
    disbursement_ref: str,
) -> dict[str, Any]:
    """Notify applicant that their loan has been disbursed."""
    amt = f"TTD {amount:,.2f}"
    msg = (
        f"Hi {first_name}, your loan {reference} of {amt} has been disbursed "
        f"(ref: {disbursement_ref}). The funds should arrive in your account "
        f"shortly. Your payment schedule is now available in your Zotta account."
    )
    return await send_whatsapp_message(to_phone, msg)


async def notify_overdue_reminder(
    to_phone: str,
    first_name: str,
    reference: str,
    amount_due: float,
    due_date: str,
    days_overdue: int,
) -> dict[str, Any]:
    """Send an overdue payment reminder."""
    amt = f"TTD {amount_due:,.2f}"
    if days_overdue <= 3:
        msg = (
            f"Hi {first_name}, this is a friendly reminder that your payment of "
            f"{amt} for loan {reference} was due on {due_date}. "
            f"Please make your payment at your earliest convenience. "
            f"Contact us if you need assistance."
        )
    elif days_overdue <= 14:
        msg = (
            f"Hi {first_name}, your payment of {amt} for loan {reference} "
            f"is now {days_overdue} days overdue (due {due_date}). Please arrange "
            f"payment as soon as possible to avoid additional charges. "
            f"Reply to this message if you'd like to discuss a payment plan."
        )
    else:
        msg = (
            f"URGENT: Hi {first_name}, your payment of {amt} for loan "
            f"{reference} is {days_overdue} days overdue (original due date: "
            f"{due_date}). Immediate payment is required. Please contact us "
            f"today to arrange payment and avoid further collection action."
        )
    return await send_whatsapp_message(to_phone, msg)


async def notify_payment_received(
    to_phone: str,
    first_name: str,
    reference: str,
    amount_paid: float,
    remaining_balance: float,
) -> dict[str, Any]:
    """Confirm that a payment has been received."""
    paid = f"TTD {amount_paid:,.2f}"
    bal = f"TTD {remaining_balance:,.2f}"
    msg = (
        f"Hi {first_name}, we've received your payment of {paid} for loan "
        f"{reference}. Thank you! Your remaining balance is {bal}. "
        f"View your full statement in your Zotta account."
    )
    return await send_whatsapp_message(to_phone, msg)
