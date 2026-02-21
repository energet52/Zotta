"""Regression tests for the existing single-strategy decision engine.

CRITICAL: These tests use locked fixtures and must pass BEFORE any other
test suite.  If any test here fails, the build is blocked.

These fixtures verify that the existing evaluate_rules() function produces
identical outcomes before and after the Decision Strategy Management changes.
"""

import json
import os
import pytest

from app.services.decision_engine.rules import RuleInput, evaluate_rules


FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "decision_regression.json")


def _load_fixtures():
    with open(FIXTURES_PATH, "r") as f:
        data = json.load(f)
    return data["fixtures"]


FIXTURES = _load_fixtures()


def _fixture_to_rule_input(fix: dict) -> RuleInput:
    return RuleInput(
        credit_score=fix["credit_score"],
        risk_band=fix["risk_band"],
        debt_to_income_ratio=fix["dti"],
        loan_to_income_ratio=fix["lti"],
        loan_amount_requested=fix["amount"],
        monthly_income=fix["income"],
        applicant_age=fix["age"],
        years_employed=float(fix["years_employed"]),
        national_id=fix.get("national_id", ""),
        is_id_verified=fix.get("is_id_verified", False),
        monthly_expenses=fix.get("expenses", 0),
        employment_type=fix.get("employment_type", "employed"),
        term_months=fix.get("term_months", 12),
        has_active_debt_bureau=fix.get("has_active_debt", False),
        has_court_judgment=fix.get("has_judgment", False),
        has_duplicate_within_30_days=fix.get("has_duplicate", False),
        scorecard_score=fix.get("scorecard_score"),
    )


class TestDecisionRegression:
    """Locked regression suite — 50 fixture applications."""

    @pytest.mark.parametrize("fixture", FIXTURES, ids=[f"fixture_{f['id']}" for f in FIXTURES])
    def test_fixture_outcome(self, fixture):
        """Each fixture must produce its expected outcome exactly."""
        rule_input = _fixture_to_rule_input(fixture)
        result = evaluate_rules(rule_input)
        assert result.outcome == fixture["expected_outcome"], (
            f"Fixture #{fixture['id']}: expected {fixture['expected_outcome']}, "
            f"got {result.outcome}. Reasons: {result.reasons}"
        )

    def test_all_fixtures_present(self):
        """Verify exactly 50 fixtures exist."""
        assert len(FIXTURES) == 50, f"Expected 50 fixtures, found {len(FIXTURES)}"

    def test_fixture_file_not_modified(self):
        """Guard against accidental modification of the fixture file."""
        fixtures = _load_fixtures()
        assert fixtures[0]["id"] == 1
        assert fixtures[0]["expected_outcome"] == "auto_approve"
        assert fixtures[-1]["id"] == 50
        assert fixtures[-1]["expected_outcome"] == "auto_approve"

    def test_all_outcome_types_covered(self):
        """Fixtures must cover all three outcome types."""
        outcomes = {f["expected_outcome"] for f in FIXTURES}
        assert "auto_approve" in outcomes
        assert "auto_decline" in outcomes
        assert "manual_review" in outcomes

    def test_scorecard_score_fixtures_present(self):
        """Verify fixtures include scorecard score scenarios."""
        with_scorecard = [f for f in FIXTURES if f.get("scorecard_score") is not None]
        assert len(with_scorecard) >= 3, "Need at least 3 fixtures with scorecard scores"
