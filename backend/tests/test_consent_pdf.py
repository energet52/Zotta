"""Tests for consent PDF generation and lender config."""

import io
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.services.reporting import generate_consent_pdf


class TestLenderConfig:
    def test_default_lender_name(self):
        """Default lender name should be 'Zotta'."""
        s = Settings(database_url="sqlite:///:memory:", database_url_sync="sqlite:///:memory:")
        assert s.lender_name == "Zotta"

    def test_default_lender_address(self):
        """Default lender address should be set."""
        s = Settings(database_url="sqlite:///:memory:", database_url_sync="sqlite:///:memory:")
        assert "Trinidad" in s.lender_address

    def test_custom_lender_name(self, monkeypatch):
        """Lender name should be configurable via env var."""
        monkeypatch.setenv("LENDER_NAME", "Acme Finance Ltd")
        s = Settings(database_url="sqlite:///:memory:", database_url_sync="sqlite:///:memory:")
        assert s.lender_name == "Acme Finance Ltd"

    def test_custom_lender_address(self, monkeypatch):
        """Lender address should be configurable via env var."""
        monkeypatch.setenv("LENDER_ADDRESS", "42 Main St, Port of Spain")
        s = Settings(database_url="sqlite:///:memory:", database_url_sync="sqlite:///:memory:")
        assert s.lender_address == "42 Main St, Port of Spain"


class TestConsentPdfGeneration:
    """Unit tests for the generate_consent_pdf function."""

    @pytest.fixture
    def pdf_kwargs(self):
        """Standard keyword args for PDF generation."""
        return dict(
            lender_name="Test Lender Inc",
            lender_address="1 Lender Lane, Port of Spain",
            applicant_name="John Doe",
            applicant_address="45 Elm Street, San Fernando",
            national_id="19900515001",
            reference_number="ZOT-2026-TESTPDF1",
            product_name="HP Standard",
            amount=10000.00,
            term_months=12,
            monthly_payment=900.50,
            total_financed=10800.00,
            downpayment=500.00,
            interest_rate=14.5,
            signature_data_url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            signed_at=datetime(2026, 2, 10, 14, 30, 0, tzinfo=timezone.utc),
        )

    def test_returns_bytesio(self, pdf_kwargs):
        """generate_consent_pdf should return a BytesIO object."""
        result = generate_consent_pdf(**pdf_kwargs)
        assert isinstance(result, io.BytesIO)

    def test_pdf_starts_with_correct_header(self, pdf_kwargs):
        """Result should be a valid PDF (starts with %PDF-)."""
        result = generate_consent_pdf(**pdf_kwargs)
        data = result.read()
        assert data[:5] == b"%PDF-"

    def test_pdf_has_content(self, pdf_kwargs):
        """PDF should be reasonably sized (not empty)."""
        result = generate_consent_pdf(**pdf_kwargs)
        data = result.read()
        # A combined 2-part document with tables and a signature should be > 5 KB
        assert len(data) > 5000

    def test_pdf_without_signature(self, pdf_kwargs):
        """PDF should still generate when signature_data_url is empty."""
        pdf_kwargs["signature_data_url"] = ""
        result = generate_consent_pdf(**pdf_kwargs)
        data = result.read()
        assert data[:5] == b"%PDF-"

    def test_pdf_without_interest_rate(self, pdf_kwargs):
        """PDF should handle None interest rate."""
        pdf_kwargs["interest_rate"] = None
        result = generate_consent_pdf(**pdf_kwargs)
        data = result.read()
        assert data[:5] == b"%PDF-"

    def test_pdf_with_bad_signature_data(self, pdf_kwargs):
        """PDF should still generate gracefully with malformed signature data."""
        pdf_kwargs["signature_data_url"] = "not-a-valid-data-url"
        result = generate_consent_pdf(**pdf_kwargs)
        data = result.read()
        assert data[:5] == b"%PDF-"

    def test_pdf_with_zero_downpayment(self, pdf_kwargs):
        """Edge case: zero downpayment should be handled."""
        pdf_kwargs["downpayment"] = 0.0
        result = generate_consent_pdf(**pdf_kwargs)
        data = result.read()
        assert len(data) > 1000
