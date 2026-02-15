"""Tests for API schemas covering StaffCreateApplicationRequest, LoanApplicationResponse."""

from datetime import datetime

import pytest

from app.schemas import (
    StaffCreateApplicationRequest,
    LoanApplicationResponse,
    ApplicationItemResponse,
)


class TestStaffCreateApplicationRequest:
    """Staff create-on-behalf schema accepts extended profile fields."""

    def test_accepts_marital_status(self):
        """Schema accepts marital_status field."""
        data = StaffCreateApplicationRequest(
            email="test@example.com",
            first_name="Jane",
            last_name="Doe",
            amount_requested=10000,
            term_months=12,
            purpose="personal",
            marital_status="married",
        )
        assert data.marital_status == "married"

    def test_accepts_address_line2(self):
        """Schema accepts address_line2 field."""
        data = StaffCreateApplicationRequest(
            email="test@example.com",
            first_name="Jane",
            last_name="Doe",
            amount_requested=10000,
            term_months=12,
            purpose="personal",
            address_line2="Apt 4B",
        )
        assert data.address_line2 == "Apt 4B"

    def test_accepts_other_income(self):
        """Schema accepts other_income field."""
        data = StaffCreateApplicationRequest(
            email="test@example.com",
            first_name="Jane",
            last_name="Doe",
            amount_requested=10000,
            term_months=12,
            purpose="personal",
            other_income=500.0,
        )
        assert data.other_income == 500.0

    def test_accepts_dependents(self):
        """Schema accepts dependents field."""
        data = StaffCreateApplicationRequest(
            email="test@example.com",
            first_name="Jane",
            last_name="Doe",
            amount_requested=10000,
            term_months=12,
            purpose="personal",
            dependents=3,
        )
        assert data.dependents == 3

    def test_minimal_payload_valid(self):
        """Minimal required fields still validate."""
        data = StaffCreateApplicationRequest(
            email="min@example.com",
            first_name="Min",
            last_name="Med",
            amount_requested=5000,
            term_months=6,
            purpose="vehicle",
        )
        assert data.marital_status is None
        assert data.address_line2 is None
        assert data.other_income is None
        assert data.dependents is None


class TestLoanApplicationResponse:
    """LoanApplicationResponse includes Shopping + Plan Selection fields."""

    def test_has_merchant_branch_product_names(self):
        """Response includes merchant_name, branch_name, credit_product_name."""
        data = LoanApplicationResponse(
            id=1,
            reference_number="ZOT-2026-ABC123",
            applicant_id=10,
            amount_requested=15000,
            term_months=12,
            purpose="personal",
            purpose_description=None,
            interest_rate=None,
            amount_approved=None,
            monthly_payment=None,
            merchant_id=1,
            branch_id=2,
            credit_product_id=3,
            merchant_name="Test Merchant",
            branch_name="Main Branch",
            credit_product_name="HP Standard",
            downpayment=500,
            total_financed=14500,
            items=[],
            status="submitted",
            assigned_underwriter_id=None,
            proposed_amount=None,
            proposed_rate=None,
            proposed_term=None,
            counterproposal_reason=None,
            contract_signed_at=None,
            contract_typed_name=None,
            submitted_at=datetime.now(),
            decided_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert data.merchant_name == "Test Merchant"
        assert data.branch_name == "Main Branch"
        assert data.credit_product_name == "HP Standard"

    def test_has_items_list(self):
        """Response includes items list."""
        item = ApplicationItemResponse(
            id=1,
            loan_application_id=1,
            category_id=5,
            category_name="Electronics",
            description="AC Unit",
            price=5000.0,
            quantity=1,
            created_at=datetime.now(),
        )
        data = LoanApplicationResponse(
            id=1,
            reference_number="ZOT-2026-XYZ",
            applicant_id=10,
            amount_requested=5000,
            term_months=12,
            purpose="personal",
            purpose_description=None,
            interest_rate=None,
            amount_approved=None,
            monthly_payment=None,
            merchant_id=1,
            branch_id=2,
            credit_product_id=3,
            merchant_name=None,
            branch_name=None,
            credit_product_name=None,
            downpayment=0,
            total_financed=5000,
            items=[item],
            status="draft",
            assigned_underwriter_id=None,
            proposed_amount=None,
            proposed_rate=None,
            proposed_term=None,
            counterproposal_reason=None,
            contract_signed_at=None,
            contract_typed_name=None,
            submitted_at=None,
            decided_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert len(data.items) == 1
        assert data.items[0].category_name == "Electronics"
        assert data.items[0].price == 5000.0
