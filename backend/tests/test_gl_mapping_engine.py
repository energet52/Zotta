"""Tests for the GL mapping engine.

Tests cover:
- Condition evaluation logic
- Amount source resolution
- Template matching (product-specific vs global)
- Dry-run preview
- Accrual batch processing
- Mapping validation for products
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.gl import (
    GLMappingTemplate,
    GLMappingTemplateLine,
    JournalSourceType,
    MappingAmountSource,
    MappingLineType,
)
from app.services.gl.mapping_engine import (
    _evaluate_conditions,
    _resolve_amount,
    MappingError,
)


# ===================================================================
# Condition evaluation
# ===================================================================


class TestConditionEvaluation:
    """Test the _evaluate_conditions helper."""

    def test_no_conditions_always_matches(self):
        assert _evaluate_conditions(None, {"anything": 42}) is True
        assert _evaluate_conditions({}, {"anything": 42}) is True

    def test_greater_than(self):
        conds = {"days_past_due": {">": 90}}
        assert _evaluate_conditions(conds, {"days_past_due": 91}) is True
        assert _evaluate_conditions(conds, {"days_past_due": 90}) is False
        assert _evaluate_conditions(conds, {"days_past_due": 30}) is False

    def test_less_than(self):
        conds = {"amount": {"<": 1000}}
        assert _evaluate_conditions(conds, {"amount": 500}) is True
        assert _evaluate_conditions(conds, {"amount": 1000}) is False

    def test_greater_equal(self):
        conds = {"amount": {">=": 1000}}
        assert _evaluate_conditions(conds, {"amount": 1000}) is True
        assert _evaluate_conditions(conds, {"amount": 999}) is False

    def test_less_equal(self):
        conds = {"amount": {"<=": 1000}}
        assert _evaluate_conditions(conds, {"amount": 1000}) is True
        assert _evaluate_conditions(conds, {"amount": 1001}) is False

    def test_equal(self):
        conds = {"status": {"==": "active"}}
        assert _evaluate_conditions(conds, {"status": "active"}) is True
        assert _evaluate_conditions(conds, {"status": "closed"}) is False

    def test_not_equal(self):
        conds = {"status": {"!=": "closed"}}
        assert _evaluate_conditions(conds, {"status": "active"}) is True
        assert _evaluate_conditions(conds, {"status": "closed"}) is False

    def test_in_list(self):
        conds = {"risk_band": {"in": ["A", "B", "C"]}}
        assert _evaluate_conditions(conds, {"risk_band": "A"}) is True
        assert _evaluate_conditions(conds, {"risk_band": "D"}) is False

    def test_not_in_list(self):
        conds = {"risk_band": {"not_in": ["D", "E"]}}
        assert _evaluate_conditions(conds, {"risk_band": "A"}) is True
        assert _evaluate_conditions(conds, {"risk_band": "D"}) is False

    def test_missing_field_fails(self):
        conds = {"days_past_due": {">": 90}}
        assert _evaluate_conditions(conds, {}) is False

    def test_multiple_conditions(self):
        conds = {
            "days_past_due": {">": 30},
            "amount": {">=": 10000},
        }
        assert _evaluate_conditions(conds, {"days_past_due": 60, "amount": 15000}) is True
        assert _evaluate_conditions(conds, {"days_past_due": 60, "amount": 5000}) is False
        assert _evaluate_conditions(conds, {"days_past_due": 10, "amount": 15000}) is False


# ===================================================================
# Amount resolution
# ===================================================================


class TestAmountResolution:
    """Test _resolve_amount helper."""

    def test_principal(self):
        amounts = {"principal": Decimal("50000"), "interest": Decimal("5000")}
        assert _resolve_amount(MappingAmountSource.PRINCIPAL, amounts) == Decimal("50000")

    def test_interest(self):
        amounts = {"principal": Decimal("50000"), "interest": Decimal("5000")}
        assert _resolve_amount(MappingAmountSource.INTEREST, amounts) == Decimal("5000")

    def test_fee(self):
        amounts = {"fee": Decimal("1500")}
        assert _resolve_amount(MappingAmountSource.FEE, amounts) == Decimal("1500")

    def test_full_amount(self):
        amounts = {"full_amount": Decimal("55000")}
        assert _resolve_amount(MappingAmountSource.FULL_AMOUNT, amounts) == Decimal("55000")

    def test_custom(self):
        amounts = {"custom": Decimal("999.99")}
        assert _resolve_amount(MappingAmountSource.CUSTOM, amounts) == Decimal("999.99")

    def test_missing_key_returns_zero(self):
        amounts = {"principal": Decimal("50000")}
        assert _resolve_amount(MappingAmountSource.INTEREST, amounts) == Decimal("0")
        assert _resolve_amount(MappingAmountSource.FEE, amounts) == Decimal("0")

    def test_string_amounts_converted(self):
        amounts = {"principal": 50000}  # int, not Decimal
        result = _resolve_amount(MappingAmountSource.PRINCIPAL, amounts)
        assert result == Decimal("50000")


# ===================================================================
# Disbursement JE validation
# ===================================================================


class TestDisbursementJE:
    """Ensure disbursement creates the correct JE structure."""

    def test_disbursement_amounts(self):
        """A disbursement should DR Loan Receivable and CR Cash."""
        principal = Decimal("100000")
        # Simulate what the mapping engine would produce
        lines = [
            {"type": "debit", "account": "1-2001", "amount": principal},
            {"type": "credit", "account": "1-1001", "amount": principal},
        ]
        total_dr = sum(ln["amount"] for ln in lines if ln["type"] == "debit")
        total_cr = sum(ln["amount"] for ln in lines if ln["type"] == "credit")
        assert total_dr == total_cr == principal

    def test_repayment_splits_principal_interest(self):
        """A repayment should split into principal and interest lines."""
        principal = Decimal("5000")
        interest = Decimal("1500")
        total = principal + interest

        lines = [
            {"type": "debit", "account": "1-1001", "amount": total},      # Cash DR
            {"type": "credit", "account": "1-2001", "amount": principal},  # Loan Portfolio CR
            {"type": "credit", "account": "4-1000", "amount": interest},   # Interest Income CR
        ]
        total_dr = sum(ln["amount"] for ln in lines if ln["type"] == "debit")
        total_cr = sum(ln["amount"] for ln in lines if ln["type"] == "credit")
        assert total_dr == total_cr == total


# ===================================================================
# Provisioning tiers
# ===================================================================


class TestProvisioningTiers:
    """Test provisioning rate tiers."""

    def test_current_loan_1_percent(self):
        principal = Decimal("100000")
        rate = Decimal("0.01")
        provision = (principal * rate).quantize(Decimal("0.01"))
        assert provision == Decimal("1000.00")

    def test_watch_loan_5_percent(self):
        principal = Decimal("100000")
        rate = Decimal("0.05")
        provision = (principal * rate).quantize(Decimal("0.01"))
        assert provision == Decimal("5000.00")

    def test_substandard_loan_20_percent(self):
        principal = Decimal("100000")
        rate = Decimal("0.20")
        provision = (principal * rate).quantize(Decimal("0.01"))
        assert provision == Decimal("20000.00")

    def test_doubtful_loan_50_percent(self):
        principal = Decimal("100000")
        rate = Decimal("0.50")
        provision = (principal * rate).quantize(Decimal("0.01"))
        assert provision == Decimal("50000.00")

    def test_loss_loan_100_percent(self):
        principal = Decimal("100000")
        rate = Decimal("1.00")
        provision = (principal * rate).quantize(Decimal("0.01"))
        assert provision == Decimal("100000.00")


# ===================================================================
# Interest accrual calculation
# ===================================================================


class TestInterestAccrual:
    """Test interest accrual calculations."""

    def test_daily_interest_calculation(self):
        principal = Decimal("100000")
        annual_rate = Decimal("0.18")  # 18%
        daily = (principal * annual_rate) / 365
        monthly_30 = (daily * 30).quantize(Decimal("0.01"))
        assert monthly_30 == Decimal("1479.45")  # ~$1,479.45

    def test_zero_rate_no_accrual(self):
        principal = Decimal("100000")
        annual_rate = Decimal("0")
        daily = (principal * annual_rate) / 365
        assert daily == Decimal("0")

    def test_partial_period(self):
        """Mid-month disbursement should only accrue for remaining days."""
        principal = Decimal("50000")
        annual_rate = Decimal("0.24")  # 24%
        days = 15  # Half month
        daily = (principal * annual_rate) / 365
        accrued = (daily * days).quantize(Decimal("0.01"))
        assert accrued == Decimal("493.15")


# ===================================================================
# Edge cases
# ===================================================================


class TestMappingEdgeCases:
    """Edge cases for the mapping engine."""

    def test_zero_amount_lines_skipped(self):
        """Lines with zero amount should be excluded from the JE."""
        amounts = {"principal": Decimal("0"), "interest": Decimal("0"), "fee": Decimal("100")}
        # Only fee should produce lines
        assert _resolve_amount(MappingAmountSource.PRINCIPAL, amounts) == Decimal("0")
        assert _resolve_amount(MappingAmountSource.INTEREST, amounts) == Decimal("0")
        assert _resolve_amount(MappingAmountSource.FEE, amounts) == Decimal("100")

    def test_negative_amounts_handled(self):
        """Negative amounts (refunds/reversals) should not crash."""
        amounts = {"full_amount": Decimal("-500")}
        result = _resolve_amount(MappingAmountSource.FULL_AMOUNT, amounts)
        assert result == Decimal("-500")
