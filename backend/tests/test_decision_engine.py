"""Tests for the decision engine scoring and rules modules."""

import pytest
from app.services.decision_engine.scoring import ScoringInput, calculate_score
from app.services.decision_engine.rules import RuleInput, evaluate_rules


class TestScoring:
    def test_excellent_profile(self):
        """High-income, good payment history should score well."""
        inp = ScoringInput(
            bureau_score=780,
            payment_history_score=0.95,
            outstanding_debt=10000,
            num_inquiries=1,
            credit_history_years=10,
            monthly_income=15000,
            monthly_expenses=5000,
            existing_debt=10000,
            loan_amount_requested=50000,
            years_employed=8,
            employment_type="employed",
        )
        result = calculate_score(inp)
        assert result.total_score >= 700
        assert result.risk_band in ("A", "B")

    def test_poor_profile(self):
        """Low income, high debt should score poorly."""
        inp = ScoringInput(
            bureau_score=420,
            payment_history_score=0.3,
            outstanding_debt=100000,
            num_inquiries=8,
            credit_history_years=1,
            monthly_income=3000,
            monthly_expenses=2500,
            existing_debt=50000,
            loan_amount_requested=100000,
            years_employed=0,
            employment_type="unemployed",
        )
        result = calculate_score(inp)
        assert result.total_score < 550
        assert result.risk_band in ("D", "E")

    def test_score_in_valid_range(self):
        """Score should always be 300-850."""
        inp = ScoringInput()
        result = calculate_score(inp)
        assert 300 <= result.total_score <= 850

    def test_breakdown_has_all_factors(self):
        """Breakdown should contain all scoring factors."""
        inp = ScoringInput(monthly_income=10000)
        result = calculate_score(inp)
        expected_keys = {
            "payment_history", "outstanding_debt", "credit_history",
            "inquiries", "debt_to_income", "employment", "loan_to_income",
        }
        assert expected_keys == set(result.breakdown.keys())


class TestRules:
    def test_auto_approve_high_score(self):
        """High score with all criteria met should auto-approve."""
        inp = RuleInput(
            credit_score=780,
            risk_band="A",
            debt_to_income_ratio=0.25,
            loan_to_income_ratio=1.5,
            loan_amount_requested=100000,
            monthly_income=15000,
            applicant_age=35,
            years_employed=5,
            national_id="19880315001",
            is_id_verified=True,
        )
        result = evaluate_rules(inp)
        assert result.outcome == "auto_approve"
        assert result.suggested_rate is not None

    def test_auto_decline_low_score(self):
        """Very low score should auto-decline."""
        inp = RuleInput(
            credit_score=400,
            risk_band="E",
            debt_to_income_ratio=0.8,
            loan_amount_requested=100000,
            loan_to_income_ratio=3.0,
            monthly_income=3000,
            applicant_age=35,
            years_employed=1,
            national_id="test123",
            is_id_verified=True,
        )
        result = evaluate_rules(inp)
        assert result.outcome == "auto_decline"

    def test_underage_declined(self):
        """Applicant under 18 should be declined."""
        inp = RuleInput(
            credit_score=700,
            risk_band="B",
            debt_to_income_ratio=0.2,
            loan_to_income_ratio=1.0,
            loan_amount_requested=10000,
            monthly_income=5000,
            applicant_age=17,
            years_employed=0,
            national_id="test123",
            is_id_verified=True,
        )
        result = evaluate_rules(inp)
        assert result.outcome == "auto_decline"
        assert any("18" in r for r in result.reasons)

    def test_low_income_declined(self):
        """Income below minimum should be declined."""
        inp = RuleInput(
            credit_score=700,
            risk_band="B",
            debt_to_income_ratio=0.3,
            loan_to_income_ratio=2.0,
            loan_amount_requested=20000,
            monthly_income=2000,
            applicant_age=30,
            years_employed=2,
            national_id="test123",
            is_id_verified=True,
        )
        result = evaluate_rules(inp)
        assert result.outcome == "auto_decline"

    def test_manual_review_mid_range(self):
        """Mid-range score with soft fails should go to manual review."""
        inp = RuleInput(
            credit_score=650,
            risk_band="C",
            debt_to_income_ratio=0.35,
            loan_to_income_ratio=2.5,
            loan_amount_requested=80000,
            monthly_income=8000,
            applicant_age=28,
            years_employed=2,
            national_id="test456",
            is_id_verified=False,
        )
        result = evaluate_rules(inp)
        assert result.outcome == "manual_review"
