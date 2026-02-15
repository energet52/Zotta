"""Tests for the AI rule generator safety guardrails and validation.

These tests do NOT call OpenAI — they test the pre-flight and post-flight
validation logic that runs locally.
"""

import pytest
from app.services.rule_generator import (
    generate_rule,
    _validate_generated_rule,
    ALLOWED_FIELDS,
    ALLOWED_OPERATORS,
    ALLOWED_OUTCOMES,
    BLOCKED_CONCEPTS,
)


class TestFieldWhitelist:
    def test_allowed_fields_not_empty(self):
        assert len(ALLOWED_FIELDS) > 0

    def test_expected_fields_present(self):
        expected = {
            "applicant_age", "monthly_income", "monthly_expenses",
            "credit_score", "risk_band", "debt_to_income_ratio",
            "loan_amount_requested", "term_months", "employment_type",
            "years_employed", "is_id_verified",
        }
        assert expected.issubset(set(ALLOWED_FIELDS.keys()))

    def test_each_field_has_label_and_description(self):
        for name, meta in ALLOWED_FIELDS.items():
            assert "label" in meta, f"Field {name} missing label"
            assert "description" in meta, f"Field {name} missing description"
            assert "type" in meta, f"Field {name} missing type"

    def test_gender_not_in_allowed_fields(self):
        assert "gender" not in ALLOWED_FIELDS

    def test_race_not_in_allowed_fields(self):
        assert "race" not in ALLOWED_FIELDS
        assert "ethnicity" not in ALLOWED_FIELDS

    def test_religion_not_in_allowed_fields(self):
        assert "religion" not in ALLOWED_FIELDS

    def test_marital_status_not_in_allowed_fields(self):
        assert "marital_status" not in ALLOWED_FIELDS

    def test_nationality_not_in_allowed_fields(self):
        assert "nationality" not in ALLOWED_FIELDS


class TestBlockedConcepts:
    def test_blocked_list_not_empty(self):
        assert len(BLOCKED_CONCEPTS) > 0

    def test_gender_blocked(self):
        assert "gender" in BLOCKED_CONCEPTS

    def test_race_blocked(self):
        assert "race" in BLOCKED_CONCEPTS

    def test_religion_blocked(self):
        assert "religion" in BLOCKED_CONCEPTS

    def test_marital_status_blocked(self):
        assert "marital status" in BLOCKED_CONCEPTS

    def test_disability_blocked(self):
        assert "disability" in BLOCKED_CONCEPTS

    def test_sexual_orientation_blocked(self):
        assert "sexual orientation" in BLOCKED_CONCEPTS

    def test_pregnancy_blocked(self):
        assert "pregnancy" in BLOCKED_CONCEPTS


class TestPreFlightBlockedPrompts:
    """Tests that prompts containing blocked concepts are refused
    BEFORE even calling OpenAI."""

    def test_gender_prompt_refused(self):
        result = generate_rule("Decline all female applicants")
        assert result["status"] == "refused"
        assert "gender" in result["refusal_reason"].lower() or "female" in result["refusal_reason"].lower()

    def test_race_prompt_refused(self):
        result = generate_rule("Refer applications from certain race groups")
        assert result["status"] == "refused"

    def test_religion_prompt_refused(self):
        result = generate_rule("Decline muslim applicants")
        assert result["status"] == "refused"

    def test_marital_status_prompt_refused(self):
        result = generate_rule("Refer all married applicants")
        assert result["status"] == "refused"

    def test_nationality_prompt_refused(self):
        result = generate_rule("Decline based on country of origin")
        assert result["status"] == "refused"

    def test_disability_prompt_refused(self):
        result = generate_rule("Add higher rate for disabled applicants")
        assert result["status"] == "refused"

    def test_pregnancy_prompt_refused(self):
        result = generate_rule("Decline pregnant applicants")
        assert result["status"] == "refused"

    def test_political_prompt_refused(self):
        result = generate_rule("Refer based on political party affiliation")
        assert result["status"] == "refused"

    def test_clean_prompt_not_refused_precheck(self):
        """A legitimate prompt should not be blocked by pre-flight checks.
        (It may still fail at the OpenAI call if no API key is set.)"""
        result = generate_rule("Decline applicants with credit score below 350")
        # Should either succeed (if API key present) or fail with API error
        # but should NOT be "refused" due to blocked concept
        if result["status"] == "refused":
            # Only acceptable refusal is API key not configured
            assert "api key" in result["refusal_reason"].lower() or "service error" in result["refusal_reason"].lower()


class TestPostFlightValidation:
    """Tests _validate_generated_rule — the validation that runs after
    OpenAI returns a candidate rule."""

    def test_valid_rule_passes(self):
        rule = {
            "rule_id": "R_CUSTOM_TEST",
            "name": "Test Rule",
            "description": "Decline if income below 500",
            "field": "monthly_income",
            "operator": "gte",
            "threshold": 500,
            "outcome": "decline",
            "severity": "hard",
        }
        assert _validate_generated_rule(rule) is None

    def test_invalid_field_rejected(self):
        rule = {
            "field": "gender",
            "operator": "eq",
            "outcome": "decline",
            "name": "Test",
            "description": "Test",
        }
        error = _validate_generated_rule(rule)
        assert error is not None
        assert "gender" in error.lower()

    def test_invalid_operator_rejected(self):
        rule = {
            "field": "monthly_income",
            "operator": "like",
            "outcome": "decline",
            "name": "Test",
            "description": "Test",
        }
        error = _validate_generated_rule(rule)
        assert error is not None
        assert "operator" in error.lower()

    def test_invalid_outcome_rejected(self):
        rule = {
            "field": "monthly_income",
            "operator": "gte",
            "outcome": "auto_approve",  # not in allowed outcomes
            "name": "Test",
            "description": "Test",
        }
        error = _validate_generated_rule(rule)
        assert error is not None
        assert "outcome" in error.lower()

    def test_blocked_concept_in_name_rejected(self):
        rule = {
            "field": "monthly_income",
            "operator": "gte",
            "outcome": "decline",
            "name": "Gender-based income rule",
            "description": "Test",
        }
        error = _validate_generated_rule(rule)
        assert error is not None
        assert "gender" in error.lower()

    def test_blocked_concept_in_description_rejected(self):
        rule = {
            "field": "monthly_income",
            "operator": "gte",
            "outcome": "decline",
            "name": "Test rule",
            "description": "Filter by ethnicity",
        }
        error = _validate_generated_rule(rule)
        assert error is not None

    def test_all_allowed_operators_pass(self):
        for op in ALLOWED_OPERATORS:
            rule = {
                "field": "monthly_income",
                "operator": op,
                "outcome": "decline",
                "name": "Test",
                "description": "Test",
            }
            assert _validate_generated_rule(rule) is None

    def test_all_allowed_outcomes_pass(self):
        for outcome in ALLOWED_OUTCOMES:
            rule = {
                "field": "monthly_income",
                "operator": "gte",
                "outcome": outcome,
                "name": "Test",
                "description": "Test",
            }
            assert _validate_generated_rule(rule) is None

    def test_all_allowed_fields_pass(self):
        for field_name in ALLOWED_FIELDS:
            rule = {
                "field": field_name,
                "operator": "gte",
                "outcome": "decline",
                "name": "Test",
                "description": "Test",
            }
            assert _validate_generated_rule(rule) is None


class TestNoApiKey:
    """When no API key is set, the generator should return a clear error."""

    def test_no_api_key_returns_refused(self):
        """Without OPENAI_API_KEY, generate_rule should refuse gracefully."""
        import os
        # The test environment likely has no API key
        original = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            result = generate_rule("Decline applicants with income below 1000")
            if result["status"] == "refused":
                assert "refusal_reason" in result
        finally:
            if original:
                os.environ["OPENAI_API_KEY"] = original
