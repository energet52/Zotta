"""Tests for the WhatsApp notification service (Twilio).

Unit tests (mocked) run in every pytest invocation.
Integration tests marked ``whatsapp_live`` hit the real Twilio API and
deliver an actual WhatsApp message — run them with:

    pytest tests/test_whatsapp_notifier.py -m whatsapp_live -s

They are skipped by default unless TWILIO_ACCOUNT_SID is configured.
"""

import os
import json
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# config.py now resolves the root .env automatically (no symlink needed).
# We still patch the singleton for fields that may not have been set at
# import time if the test runner imported config before env was loaded.
# ---------------------------------------------------------------------------
from app.config import settings

# Patch the already-created settings singleton with env values so that
# live tests work even when the full suite is run from backend/.
_TWILIO_FIELDS = [
    "twilio_account_sid",
    "twilio_auth_token",
    "twilio_whatsapp_number",
    "whatsapp_sandbox_phone",
    "environment",
]
for _field in _TWILIO_FIELDS:
    _env_val = os.environ.get(_field.upper())
    if _env_val:
        object.__setattr__(settings, _field, _env_val)

from app.services.whatsapp_notifier import (  # noqa: E402
    send_whatsapp_message,
    TWILIO_MESSAGES_URL,
    notify_application_approved,
    notify_application_declined,
    notify_documents_requested,
    notify_loan_disbursed,
    notify_overdue_reminder,
    notify_payment_received,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HAS_TWILIO_CREDS = bool(
    settings.twilio_account_sid
    and settings.twilio_auth_token
    and settings.twilio_account_sid not in ("", "your-twilio-sid")
    and settings.twilio_auth_token not in ("", "your-twilio-auth-token")
)

whatsapp_live = pytest.mark.skipif(
    not _HAS_TWILIO_CREDS,
    reason="Live Twilio credentials not configured — set TWILIO_ACCOUNT_SID & TWILIO_AUTH_TOKEN in .env",
)


def _fake_twilio_response(status_code: int = 201, body: dict | None = None):
    """Return a mock httpx.Response that looks like a Twilio reply."""
    if body is None:
        body = {
            "sid": "SM00000000000000000000000000000000",
            "status": "queued",
            "to": "whatsapp:+447432723070",
            "from": "whatsapp:+14155238886",
        }
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    return resp


# ===================================================================
# Unit tests — always run (Twilio API is mocked)
# ===================================================================


class TestMissingCredentials:
    """When Twilio creds are absent the function must return gracefully."""

    @pytest.mark.asyncio
    async def test_empty_sid_returns_error(self):
        with patch.object(settings, "twilio_account_sid", ""), \
             patch.object(settings, "twilio_auth_token", "some-token"):
            result = await send_whatsapp_message("+18681234567", "hi")
        assert "error" in result
        assert "not configured" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_token_returns_error(self):
        with patch.object(settings, "twilio_account_sid", "ACxxx"), \
             patch.object(settings, "twilio_auth_token", ""):
            result = await send_whatsapp_message("+18681234567", "hi")
        assert "error" in result
        assert "not configured" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_both_empty_returns_error(self):
        with patch.object(settings, "twilio_account_sid", ""), \
             patch.object(settings, "twilio_auth_token", ""):
            result = await send_whatsapp_message("+18681234567", "hi")
        assert "error" in result


class TestSandboxOverride:
    """In non-production mode the recipient must be overridden."""

    @pytest.mark.asyncio
    async def test_dev_mode_redirects_to_sandbox_phone(self):
        mock_post = AsyncMock(return_value=_fake_twilio_response())
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "development"), \
             patch.object(settings, "whatsapp_sandbox_phone", "+15551234567"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            await send_whatsapp_message("+18681111111", "test")

        call_kwargs = mock_post.call_args
        sent_to = call_kwargs.kwargs.get("data", call_kwargs[1].get("data", {})).get("To", "")
        assert "+15551234567" in sent_to
        assert "+18681111111" not in sent_to

    @pytest.mark.asyncio
    async def test_production_mode_uses_real_phone(self):
        mock_post = AsyncMock(return_value=_fake_twilio_response())
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch.object(settings, "whatsapp_sandbox_phone", "+15551234567"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            await send_whatsapp_message("+18681111111", "test")

        call_kwargs = mock_post.call_args
        sent_to = call_kwargs.kwargs.get("data", call_kwargs[1].get("data", {})).get("To", "")
        assert "+18681111111" in sent_to


class TestWhatsAppPrefix:
    """The whatsapp: prefix must always be present on To and From."""

    @pytest.mark.asyncio
    async def test_prefix_added_to_plain_number(self):
        mock_post = AsyncMock(return_value=_fake_twilio_response())
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch.object(settings, "twilio_whatsapp_number", "+14155238886"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            await send_whatsapp_message("+18681234567", "hello")

        call_kwargs = mock_post.call_args
        data = call_kwargs.kwargs.get("data", call_kwargs[1].get("data", {}))
        assert data["To"] == "whatsapp:+18681234567"
        assert data["From"] == "whatsapp:+14155238886"

    @pytest.mark.asyncio
    async def test_prefix_not_doubled(self):
        mock_post = AsyncMock(return_value=_fake_twilio_response())
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch.object(settings, "twilio_whatsapp_number", "whatsapp:+14155238886"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            await send_whatsapp_message("whatsapp:+18681234567", "hello")

        call_kwargs = mock_post.call_args
        data = call_kwargs.kwargs.get("data", call_kwargs[1].get("data", {}))
        assert data["To"] == "whatsapp:+18681234567"
        assert data["From"] == "whatsapp:+14155238886"


class TestSuccessResponse:
    """Successful Twilio responses are returned as-is."""

    @pytest.mark.asyncio
    async def test_returns_twilio_json(self):
        expected = {"sid": "SM123", "status": "queued", "to": "whatsapp:+1234"}
        mock_post = AsyncMock(return_value=_fake_twilio_response(201, expected))
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            result = await send_whatsapp_message("+18681234567", "hi")

        assert result == expected
        assert result["sid"] == "SM123"


class TestErrorHandling:
    """Twilio errors and network failures must not raise exceptions."""

    @pytest.mark.asyncio
    async def test_4xx_returns_error_dict(self):
        error_body = {"code": 21211, "message": "Invalid 'To' phone number"}
        mock_post = AsyncMock(return_value=_fake_twilio_response(400, error_body))
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            result = await send_whatsapp_message("+1bad", "hi")

        assert "error" in result
        assert result["status_code"] == 400

    @pytest.mark.asyncio
    async def test_401_returns_error_dict(self):
        error_body = {"code": 20003, "message": "Authenticate"}
        mock_post = AsyncMock(return_value=_fake_twilio_response(401, error_body))
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            result = await send_whatsapp_message("+18681234567", "hi")

        assert "error" in result
        assert result["status_code"] == 401

    @pytest.mark.asyncio
    async def test_network_exception_returns_error(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("DNS failed"))

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            result = await send_whatsapp_message("+18681234567", "hi")

        assert "error" in result
        assert "DNS" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("read timed out"))

        with patch.object(settings, "twilio_account_sid", "ACtest"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            result = await send_whatsapp_message("+18681234567", "hi")

        assert "error" in result


class TestTwilioUrlFormation:
    """The Twilio API URL must contain the account SID."""

    @pytest.mark.asyncio
    async def test_url_contains_sid(self):
        mock_post = AsyncMock(return_value=_fake_twilio_response())
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "AC_my_sid_123"), \
             patch.object(settings, "twilio_auth_token", "tok"), \
             patch.object(settings, "environment", "production"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            await send_whatsapp_message("+18681234567", "hi")

        called_url = mock_post.call_args[0][0] if mock_post.call_args[0] else mock_post.call_args.kwargs.get("url", "")
        assert "AC_my_sid_123" in called_url
        assert called_url.endswith("Messages.json")

    @pytest.mark.asyncio
    async def test_auth_uses_sid_and_token(self):
        mock_post = AsyncMock(return_value=_fake_twilio_response())
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch.object(settings, "twilio_account_sid", "ACsid"), \
             patch.object(settings, "twilio_auth_token", "secret_tok"), \
             patch.object(settings, "environment", "production"), \
             patch("app.services.whatsapp_notifier.httpx.AsyncClient", return_value=mock_client):
            await send_whatsapp_message("+18681234567", "hi")

        call_kwargs = mock_post.call_args
        auth = call_kwargs.kwargs.get("auth", call_kwargs[1].get("auth"))
        assert auth == ("ACsid", "secret_tok")


# ===================================================================
# Live integration tests — actually send a WhatsApp message
# Run with:  pytest tests/test_whatsapp_notifier.py -m whatsapp_live -s
# ===================================================================


class TestLiveWhatsApp:
    """Integration tests that hit the real Twilio API.

    These send actual WhatsApp messages to the configured sandbox phone.
    Skipped when Twilio credentials are not configured.
    """

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_send_real_whatsapp_message(self):
        """Send a real WhatsApp message and verify Twilio accepts it."""
        result = await send_whatsapp_message(
            settings.whatsapp_sandbox_phone,
            "Zotta test suite: WhatsApp integration is working! "
            "This message was sent by an automated test.",
        )
        # Should not have an error
        assert "error" not in result, f"Twilio returned an error: {result}"
        # Twilio should return a message SID
        assert "sid" in result, f"No message SID in response: {result}"
        assert result["sid"].startswith("SM"), f"Unexpected SID format: {result['sid']}"
        # Status should be queued or sent
        assert result.get("status") in ("queued", "sent", "delivered"), \
            f"Unexpected status: {result.get('status')}"
        print(f"\n  ✓ WhatsApp message sent — SID: {result['sid']}, status: {result['status']}")

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_send_with_arbitrary_recipient_redirects_to_sandbox(self):
        """Even with a random 'to' number, dev mode sends to the sandbox phone."""
        result = await send_whatsapp_message(
            "+19999999999",  # fake number — should be overridden in dev mode
            "Zotta test: sandbox redirect working. "
            "This proves non-production messages go to the sandbox phone.",
        )
        assert "error" not in result, f"Twilio returned an error: {result}"
        assert "sid" in result
        # In dev mode the actual recipient should be the sandbox phone
        assert settings.whatsapp_sandbox_phone.lstrip("+") in result.get("to", "").replace("whatsapp:", "").lstrip("+")
        print(f"\n  ✓ Sandbox redirect confirmed — sent to: {result.get('to')}")


# ===================================================================
# Live application status update tests
# These fire real WhatsApp messages for every status notification type.
# Sandbox mode ensures all messages go to +447432723070 regardless of
# the customer's actual number.
#
# Run:  pytest tests/test_whatsapp_notifier.py -m whatsapp_live -s
# ===================================================================


def _assert_sent(result: dict, label: str):
    """Common assertions for a successfully queued Twilio message."""
    assert "error" not in result, f"[{label}] Twilio error: {result}"
    assert "sid" in result, f"[{label}] No SID in response: {result}"
    assert result["sid"].startswith("SM"), f"[{label}] Bad SID: {result['sid']}"
    assert result.get("status") in ("queued", "sent", "delivered"), \
        f"[{label}] Unexpected status: {result.get('status')}"


class TestLiveApplicationApproved:
    """Loan approval notification → real WhatsApp message."""

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_approval_notification(self):
        result = await notify_application_approved(
            to_phone="+18681234567",  # overridden to sandbox in dev
            first_name="John",
            reference="ZOT-2026-0042",
            amount_approved=15_000.00,
            monthly_payment=1_387.50,
        )
        _assert_sent(result, "approval")
        print(f"\n  ✓ APPROVED notification sent — SID: {result['sid']}")

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_approval_without_monthly_payment(self):
        result = await notify_application_approved(
            to_phone="+18681234567",
            first_name="Maria",
            reference="ZOT-2026-0099",
            amount_approved=8_500.00,
            monthly_payment=None,
        )
        _assert_sent(result, "approval-no-pmt")
        print(f"\n  ✓ APPROVED (no monthly pmt) sent — SID: {result['sid']}")


class TestLiveApplicationDeclined:
    """Loan decline notification → real WhatsApp message."""

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_decline_notification(self):
        result = await notify_application_declined(
            to_phone="+18681234567",
            first_name="Sarah",
            reference="ZOT-2026-0055",
        )
        _assert_sent(result, "declined")
        print(f"\n  ✓ DECLINED notification sent — SID: {result['sid']}")


class TestLiveDocumentsRequested:
    """Additional documents requested → real WhatsApp message."""

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_documents_requested_notification(self):
        result = await notify_documents_requested(
            to_phone="+18681234567",
            first_name="Kevin",
            reference="ZOT-2026-0071",
        )
        _assert_sent(result, "docs-requested")
        print(f"\n  ✓ DOCUMENTS REQUESTED notification sent — SID: {result['sid']}")


class TestLiveLoanDisbursed:
    """Loan disbursement notification → real WhatsApp message."""

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_disbursement_notification(self):
        result = await notify_loan_disbursed(
            to_phone="+18681234567",
            first_name="Anika",
            reference="ZOT-2026-0042",
            amount=15_000.00,
            disbursement_ref="DIS-AB1234",
        )
        _assert_sent(result, "disbursed")
        print(f"\n  ✓ DISBURSED notification sent — SID: {result['sid']}")


class TestLiveOverdueReminders:
    """Overdue payment reminders at different severity tiers → real WhatsApp messages."""

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_gentle_reminder_1_day_overdue(self):
        result = await notify_overdue_reminder(
            to_phone="+18681234567",
            first_name="Daniel",
            reference="ZOT-2026-0042",
            amount_due=1_387.50,
            due_date="12 Feb 2026",
            days_overdue=1,
        )
        _assert_sent(result, "overdue-1d")
        print(f"\n  ✓ OVERDUE (1 day, gentle) sent — SID: {result['sid']}")

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_moderate_reminder_7_days_overdue(self):
        result = await notify_overdue_reminder(
            to_phone="+18681234567",
            first_name="Daniel",
            reference="ZOT-2026-0042",
            amount_due=1_387.50,
            due_date="07 Feb 2026",
            days_overdue=7,
        )
        _assert_sent(result, "overdue-7d")
        print(f"\n  ✓ OVERDUE (7 days, moderate) sent — SID: {result['sid']}")

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_urgent_reminder_30_days_overdue(self):
        result = await notify_overdue_reminder(
            to_phone="+18681234567",
            first_name="Daniel",
            reference="ZOT-2026-0042",
            amount_due=1_387.50,
            due_date="15 Jan 2026",
            days_overdue=30,
        )
        _assert_sent(result, "overdue-30d")
        print(f"\n  ✓ OVERDUE (30 days, URGENT) sent — SID: {result['sid']}")


class TestLivePaymentReceived:
    """Payment confirmation notification → real WhatsApp message."""

    @whatsapp_live
    @pytest.mark.asyncio
    async def test_payment_received_notification(self):
        result = await notify_payment_received(
            to_phone="+18681234567",
            first_name="Priya",
            reference="ZOT-2026-0042",
            amount_paid=1_387.50,
            remaining_balance=12_225.00,
        )
        _assert_sent(result, "payment-received")
        print(f"\n  ✓ PAYMENT RECEIVED notification sent — SID: {result['sid']}")
