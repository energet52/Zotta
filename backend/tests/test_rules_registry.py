"""Tests for the declarative rules registry and data-driven rule evaluation.

Critically tests that custom rules (like those created by the AI generator)
actually trigger the correct outcomes when evaluated by the decision engine.
"""

import pytest
from app.services.decision_engine.rules import (
    RuleInput,
    evaluate_rules,
    get_active_registry,
    RULES_REGISTRY,
    DEFAULT_RULES,
    _compare,
    _get_field_value,
)


# ── Helper: a healthy applicant who would normally auto-approve ──────────

def _healthy_input(**overrides) -> RuleInput:
    defaults = dict(
        credit_score=780,
        risk_band="A",
        debt_to_income_ratio=0.25,
        loan_to_income_ratio=1.5,
        loan_amount_requested=100000,
        monthly_income=15000,
        monthly_expenses=5000,
        applicant_age=35,
        years_employed=5,
        national_id="19880315001",
        is_id_verified=True,
        employment_type="employed",
        term_months=12,
    )
    defaults.update(overrides)
    return RuleInput(**defaults)


# ── Registry structure tests ─────────────────────────────────────────────

class TestRegistryStructure:
    def test_default_registry_has_all_expected_rules(self):
        expected_ids = {"R01", "R02", "R03", "R04", "R05", "R06", "R07",
                        "R08", "R09", "R11", "R12", "R13", "R14", "R15",
                        "R16", "R17", "R18", "R20"}
        assert expected_ids == set(RULES_REGISTRY.keys())

    def test_every_rule_has_required_fields(self):
        required = {"name", "description", "field", "operator", "threshold",
                     "outcome", "severity", "type", "is_custom", "enabled"}
        for rule_id, rule in RULES_REGISTRY.items():
            for field in required:
                assert field in rule, f"Rule {rule_id} missing field '{field}'"

    def test_all_default_rules_are_enabled(self):
        for rule_id, rule in RULES_REGISTRY.items():
            assert rule["enabled"] is True, f"Rule {rule_id} should be enabled by default"

    def test_no_default_rules_are_custom(self):
        for rule_id, rule in RULES_REGISTRY.items():
            assert rule["is_custom"] is False, f"Rule {rule_id} should not be custom"


# ── get_active_registry tests ────────────────────────────────────────────

class TestGetActiveRegistry:
    def test_returns_defaults_when_no_config(self):
        registry = get_active_registry(None)
        assert set(registry.keys()) == set(RULES_REGISTRY.keys())

    def test_returns_defaults_when_no_saved_registry(self):
        config = {"rules_registry": None}
        registry = get_active_registry(config)
        assert "R01" in registry

    def test_overrides_threshold_from_config(self):
        config = {
            "rules_registry": {
                "R01": {"threshold": 21},
            },
        }
        registry = get_active_registry(config)
        assert registry["R01"]["threshold"] == 21

    def test_overrides_outcome_from_config(self):
        config = {
            "rules_registry": {
                "R03": {"outcome": "refer", "severity": "refer"},
            },
        }
        registry = get_active_registry(config)
        assert registry["R03"]["outcome"] == "refer"

    def test_adds_custom_rules(self):
        config = {
            "rules_registry": {
                "R_CUSTOM_LOW_INCOME": {
                    "name": "Very Low Income",
                    "description": "Decline if income below 500",
                    "field": "monthly_income",
                    "operator": "gte",
                    "threshold": 500,
                    "outcome": "decline",
                    "severity": "hard",
                    "type": "threshold",
                    "is_custom": True,
                    "enabled": True,
                },
            },
        }
        registry = get_active_registry(config)
        assert "R_CUSTOM_LOW_INCOME" in registry
        assert registry["R_CUSTOM_LOW_INCOME"]["threshold"] == 500

    def test_disabled_rule_preserved(self):
        config = {
            "rules_registry": {
                "R07": {"enabled": False},
            },
        }
        registry = get_active_registry(config)
        assert registry["R07"]["enabled"] is False


# ── _compare operator tests ──────────────────────────────────────────────

class TestCompareOperator:
    def test_gte(self):
        assert _compare(10, "gte", 10) is True
        assert _compare(11, "gte", 10) is True
        assert _compare(9, "gte", 10) is False

    def test_lte(self):
        assert _compare(10, "lte", 10) is True
        assert _compare(9, "lte", 10) is True
        assert _compare(11, "lte", 10) is False

    def test_gt(self):
        assert _compare(11, "gt", 10) is True
        assert _compare(10, "gt", 10) is False

    def test_lt(self):
        assert _compare(9, "lt", 10) is True
        assert _compare(10, "lt", 10) is False

    def test_eq(self):
        assert _compare(10, "eq", 10) is True
        assert _compare(11, "eq", 10) is False

    def test_neq(self):
        assert _compare(11, "neq", 10) is True
        assert _compare(10, "neq", 10) is False

    def test_in(self):
        assert _compare("A", "in", ["A", "B"]) is True
        assert _compare("C", "in", ["A", "B"]) is False

    def test_not_in(self):
        assert _compare("C", "not_in", ["A", "B"]) is True
        assert _compare("A", "not_in", ["A", "B"]) is False

    def test_between(self):
        assert _compare(5, "between", [1, 10]) is True
        assert _compare(1, "between", [1, 10]) is True
        assert _compare(10, "between", [1, 10]) is True
        assert _compare(11, "between", [1, 10]) is False

    def test_unknown_operator_passes(self):
        assert _compare(10, "unknown_op", 5) is True


# ── _get_field_value tests ───────────────────────────────────────────────

class TestGetFieldValue:
    def test_direct_field(self):
        inp = _healthy_input(monthly_income=12000)
        assert _get_field_value(inp, "monthly_income") == 12000

    def test_computed_employment_months(self):
        inp = _healthy_input(years_employed=2.5)
        assert _get_field_value(inp, "employment_months") == 30.0

    def test_computed_maturity_age(self):
        inp = _healthy_input(applicant_age=30, term_months=60)
        assert _get_field_value(inp, "maturity_age") == 35.0

    def test_unknown_field_returns_none(self):
        inp = _healthy_input()
        assert _get_field_value(inp, "nonexistent_field") is None


# ── Disabled / toggled rules ─────────────────────────────────────────────

class TestDisabledRules:
    def test_disabled_rule_is_skipped(self):
        """A disabled R01 (min age) should not decline an underage applicant."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R01": {"enabled": False},
        }
        inp = _healthy_input(applicant_age=16)
        result = evaluate_rules(inp, config)
        # R01 should show as "Rule disabled" and pass
        r01 = next(r for r in result.results if r.rule_id == "R01")
        assert r01.passed is True
        assert "disabled" in r01.message.lower()

    def test_outcome_disable_skips_rule(self):
        """Setting outcome to 'disable' should skip the rule."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R03": {"outcome": "disable"},
        }
        inp = _healthy_input(monthly_income=100)
        result = evaluate_rules(inp, config)
        r03 = next(r for r in result.results if r.rule_id == "R03")
        assert r03.passed is True

    def test_outcome_change_decline_to_refer(self):
        """Changing R03 from decline to refer should make low-income a refer."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R03": {"outcome": "refer", "severity": "refer"},
        }
        inp = _healthy_input(monthly_income=100)
        result = evaluate_rules(inp, config)
        # Should be manual_review instead of auto_decline
        assert result.outcome != "auto_decline"


# ── CRITICAL: Custom AI rules affect decisions ───────────────────────────

class TestCustomRulesAffectDecisions:
    """The most important test class: verifies that AI-generated custom rules
    are actually evaluated and produce the correct outcomes."""

    def test_custom_decline_rule_low_income(self):
        """An AI-created rule 'decline if income < 500' should decline."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_LOW_INCOME": {
                "name": "Very Low Income",
                "description": "Decline if income below 500",
                "field": "monthly_income",
                "operator": "gte",
                "threshold": 500,
                "outcome": "decline",
                "severity": "hard",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
        }
        # Applicant with income 400 (below 500 threshold)
        inp = _healthy_input(monthly_income=400)
        result = evaluate_rules(inp, config)
        assert result.outcome == "auto_decline"
        # Should have the custom rule in results
        custom = [r for r in result.results if r.rule_id == "R_CUSTOM_LOW_INCOME"]
        assert len(custom) == 1
        assert custom[0].passed is False

    def test_custom_decline_rule_passes_when_above_threshold(self):
        """Same custom rule should pass when income >= 500."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_LOW_INCOME": {
                "name": "Very Low Income",
                "description": "Decline if income below 500",
                "field": "monthly_income",
                "operator": "gte",
                "threshold": 500,
                "outcome": "decline",
                "severity": "hard",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
        }
        inp = _healthy_input(monthly_income=15000)
        result = evaluate_rules(inp, config)
        custom = [r for r in result.results if r.rule_id == "R_CUSTOM_LOW_INCOME"]
        assert len(custom) == 1
        assert custom[0].passed is True

    def test_custom_refer_rule_high_loan_amount(self):
        """A custom refer rule for high loan amounts should trigger refer."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_BIG_LOAN": {
                "name": "Big Loan Refer",
                "description": "Refer if loan > 200000",
                "field": "loan_amount_requested",
                "operator": "lte",
                "threshold": 200000,
                "outcome": "refer",
                "severity": "refer",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
        }
        inp = _healthy_input(loan_amount_requested=250000)
        result = evaluate_rules(inp, config)
        assert result.outcome == "manual_review"
        custom = [r for r in result.results if r.rule_id == "R_CUSTOM_BIG_LOAN"]
        assert len(custom) == 1
        assert custom[0].passed is False

    def test_custom_rule_disabled_does_not_affect_decision(self):
        """A disabled custom rule should not impact the outcome."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_LOW_INCOME": {
                "name": "Very Low Income",
                "description": "Decline if income below 500",
                "field": "monthly_income",
                "operator": "gte",
                "threshold": 500,
                "outcome": "decline",
                "severity": "hard",
                "type": "threshold",
                "is_custom": True,
                "enabled": False,  # DISABLED
            },
        }
        inp = _healthy_input(monthly_income=400)
        result = evaluate_rules(inp, config)
        # The custom rule should NOT cause a decline because it's disabled
        custom = [r for r in result.results if r.rule_id == "R_CUSTOM_LOW_INCOME"]
        assert len(custom) == 1
        assert custom[0].passed is True  # skipped = treated as pass

    def test_custom_rule_with_credit_score_threshold(self):
        """Custom rule: decline if credit_score < 450."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_MIN_SCORE": {
                "name": "Minimum Credit Score",
                "description": "Decline if credit score below 450",
                "field": "credit_score",
                "operator": "gte",
                "threshold": 450,
                "outcome": "decline",
                "severity": "hard",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
        }
        inp = _healthy_input(credit_score=420)
        result = evaluate_rules(inp, config)
        assert result.outcome == "auto_decline"

    def test_custom_rule_with_employment_months(self):
        """Custom rule: refer if employment < 12 months."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_SHORT_TENURE": {
                "name": "Short Tenure",
                "description": "Refer if employed less than 12 months",
                "field": "employment_months",
                "operator": "gte",
                "threshold": 12,
                "outcome": "refer",
                "severity": "refer",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
        }
        inp = _healthy_input(years_employed=0.5)  # 6 months
        result = evaluate_rules(inp, config)
        assert result.outcome in ("manual_review", "auto_decline")
        custom = [r for r in result.results if r.rule_id == "R_CUSTOM_SHORT_TENURE"]
        assert len(custom) == 1
        assert custom[0].passed is False

    def test_multiple_custom_rules_combined(self):
        """Multiple custom rules can work together."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_MIN_AGE_25": {
                "name": "Min Age 25",
                "description": "Refer if under 25",
                "field": "applicant_age",
                "operator": "gte",
                "threshold": 25,
                "outcome": "refer",
                "severity": "refer",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
            "R_CUSTOM_MAX_DTI": {
                "name": "Max DTI 30%",
                "description": "Decline if DTI over 30%",
                "field": "debt_to_income_ratio",
                "operator": "lte",
                "threshold": 0.30,
                "outcome": "decline",
                "severity": "hard",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
        }
        # DTI 35% exceeds 30% → should decline
        inp = _healthy_input(applicant_age=22, debt_to_income_ratio=0.35)
        result = evaluate_rules(inp, config)
        assert result.outcome == "auto_decline"

    def test_custom_rule_missing_field_is_skipped(self):
        """A custom rule referencing a non-existent field should be skipped."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R_CUSTOM_BAD": {
                "name": "Bad Field Rule",
                "description": "References invalid field",
                "field": "nonexistent_field",
                "operator": "gte",
                "threshold": 100,
                "outcome": "decline",
                "severity": "hard",
                "type": "threshold",
                "is_custom": True,
                "enabled": True,
            },
        }
        inp = _healthy_input()
        result = evaluate_rules(inp, config)
        # Should NOT decline — unknown field rule is skipped
        custom = [r for r in result.results if r.rule_id == "R_CUSTOM_BAD"]
        assert len(custom) == 1
        assert custom[0].passed is True
        assert "not available" in custom[0].message.lower()


# ── Threshold override tests ─────────────────────────────────────────────

class TestThresholdOverrides:
    def test_override_min_age_to_21(self):
        """Admin raises min age from 18 to 21."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R01": {"threshold": 21},
        }
        # Age 19 passes default (18) but fails override (21)
        inp = _healthy_input(applicant_age=19)
        # With defaults — should pass R01
        result_default = evaluate_rules(inp, None)
        r01_default = next(r for r in result_default.results if r.rule_id == "R01")
        assert r01_default.passed is True

        # With override — should fail R01
        result_override = evaluate_rules(inp, config)
        r01_override = next(r for r in result_override.results if r.rule_id == "R01")
        assert r01_override.passed is False

    def test_override_extreme_dsr(self):
        """Admin lowers extreme DSR from 100% to 80%."""
        config = dict(DEFAULT_RULES)
        config["rules_registry"] = {
            "R08": {"threshold": 0.80},
        }
        inp = _healthy_input(debt_to_income_ratio=0.85)
        result = evaluate_rules(inp, config)
        r08 = next(r for r in result.results if r.rule_id == "R08")
        assert r08.passed is False


# ── Backward compatibility ───────────────────────────────────────────────

class TestBackwardCompat:
    def test_evaluate_with_none_config(self):
        """Should work with no config (uses defaults)."""
        inp = _healthy_input()
        result = evaluate_rules(inp, None)
        assert result.outcome in ("auto_approve", "manual_review", "auto_decline")
        assert len(result.results) > 0

    def test_evaluate_with_legacy_config(self):
        """Should work with legacy config that has no rules_registry key."""
        legacy = dict(DEFAULT_RULES)
        assert "rules_registry" in legacy  # exists but None
        inp = _healthy_input()
        result = evaluate_rules(inp, legacy)
        assert result.outcome in ("auto_approve", "manual_review", "auto_decline")

    def test_benchmarks_always_returned(self):
        """Income and expense benchmarks should always be in output."""
        inp = _healthy_input()
        result = evaluate_rules(inp, None)
        assert result.income_benchmark is not None
        assert result.expense_benchmark is not None
