"""Simple OTP service for pre-approval phone verification.

In development mode the OTP code is returned in the API response.
In production, integrate with Twilio/WhatsApp to deliver via SMS.
"""

import logging
import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.pre_approval import PreApprovalOTP

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 5
MAX_ATTEMPTS = 3
MAX_SENDS_PER_HOUR = 5


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


async def send_otp(phone: str, db: AsyncSession) -> dict:
    """Generate and store an OTP for the given phone number.

    Returns dict with 'sent': True/False and optionally 'code' in dev mode.
    """
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # Rate limit: max sends per hour
    count_result = await db.execute(
        select(func.count(PreApprovalOTP.id)).where(
            PreApprovalOTP.phone == phone,
            PreApprovalOTP.created_at >= one_hour_ago,
        )
    )
    recent_count = count_result.scalar() or 0
    if recent_count >= MAX_SENDS_PER_HOUR:
        return {
            "sent": False,
            "message": "Too many OTP requests. Please try again in an hour.",
        }

    code = _generate_code()
    otp = PreApprovalOTP(
        phone=phone,
        code=code,
        expires_at=now + timedelta(minutes=OTP_EXPIRY_MINUTES),
        attempts=0,
        verified=False,
    )
    db.add(otp)
    await db.flush()

    # In production, send via SMS/WhatsApp here
    logger.info("OTP for %s: %s (dev mode — would send via SMS in production)", phone, code)

    result: dict = {"sent": True, "message": f"Code sent to {phone}"}
    # In dev mode, include the code so tests and developers can use it
    if settings.environment == "development":
        result["code"] = code
    return result


async def verify_otp(phone: str, code: str, db: AsyncSession) -> dict:
    """Verify an OTP code for the given phone number.

    Returns dict with 'verified': True/False and 'message'.
    """
    now = datetime.now(timezone.utc)

    # Find the most recent unexpired, unverified OTP for this phone
    result = await db.execute(
        select(PreApprovalOTP).where(
            PreApprovalOTP.phone == phone,
            PreApprovalOTP.verified == False,
            PreApprovalOTP.expires_at > now,
        ).order_by(PreApprovalOTP.created_at.desc())
    )
    otp = result.scalars().first()

    if not otp:
        return {"verified": False, "message": "No valid code found. Please request a new one."}

    if otp.attempts >= MAX_ATTEMPTS:
        return {"verified": False, "message": "Too many incorrect attempts. Please request a new code."}

    if otp.code != code:
        otp.attempts += 1
        await db.flush()
        remaining = MAX_ATTEMPTS - otp.attempts
        if remaining <= 0:
            return {"verified": False, "message": "Too many incorrect attempts. Please request a new code."}
        return {"verified": False, "message": f"Incorrect code. {remaining} attempt(s) remaining."}

    otp.verified = True
    await db.flush()
    return {"verified": True, "message": "Phone verified successfully."}
