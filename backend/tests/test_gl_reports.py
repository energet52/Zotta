"""Tests for GL reports, export service, and AI features.

Tests cover:
- Export format renderers (CSV, JSON, XML)
- Report registry completeness
- NL query pattern matching
- Anomaly detection scoring
- Classifier keyword rules
"""

import pytest
import json
from decimal import Decimal

from app.services.gl.export_service import (
    export_csv,
    export_json,
    export_xml,
    DecimalEncoder,
)
from app.services.gl.reports_service import REPORT_REGISTRY
from app.services.gl.nl_query import PATTERNS, process_query
from app.services.gl.anomaly_detector import AnomalyResult
from app.services.gl.classifier import _keyword_classify
from app.services.gl.mapping_engine import _evaluate_conditions
from app.models.gl import AnomalyType


# ===================================================================
# Export service tests
# ===================================================================


class TestCSVExport:
    def test_empty_data(self):
        result = export_csv([])
        assert result == b""

    def test_basic_csv(self):
        data = [
            {"name": "Alice", "amount": 1000},
            {"name": "Bob", "amount": 2000},
        ]
        result = export_csv(data)
        lines = result.decode("utf-8").strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "name" in lines[0]
        assert "Alice" in lines[1]

    def test_column_selection(self):
        data = [
            {"name": "Alice", "amount": 1000, "extra": "skip"},
        ]
        result = export_csv(data, columns=["name", "amount"])
        text = result.decode("utf-8")
        assert "extra" not in text
        assert "name" in text

    def test_special_characters(self):
        data = [{"desc": 'Loan "A" repayment, $1,000'}]
        result = export_csv(data)
        text = result.decode("utf-8")
        assert "Loan" in text


class TestJSONExport:
    def test_basic_json(self):
        data = [{"key": "value"}]
        result = export_json(data)
        parsed = json.loads(result)
        assert parsed["record_count"] == 1
        assert parsed["data"] == [{"key": "value"}]
        assert "exported_at" in parsed

    def test_decimal_encoding(self):
        data = [{"amount": Decimal("1234.56")}]
        result = export_json(data)
        parsed = json.loads(result)
        assert parsed["data"][0]["amount"] == 1234.56

    def test_metadata_included(self):
        data = [{"x": 1}]
        result = export_json(data, metadata={"title": "Test"})
        parsed = json.loads(result)
        assert parsed["metadata"]["title"] == "Test"


class TestXMLExport:
    def test_basic_xml(self):
        data = [{"name": "Test", "value": "123"}]
        result = export_xml(data)
        text = result.decode("utf-8")
        assert "<GLExport" in text
        assert "<Entry>" in text
        assert "<name>Test</name>" in text

    def test_empty_data(self):
        result = export_xml([])
        text = result.decode("utf-8")
        assert 'record_count="0"' in text

    def test_custom_tags(self):
        data = [{"field": "val"}]
        result = export_xml(data, root_tag="Report", row_tag="Row")
        text = result.decode("utf-8")
        assert "<Report" in text
        assert "<Row>" in text


class TestDecimalEncoder:
    def test_decimal_to_float(self):
        result = json.dumps({"amount": Decimal("99.99")}, cls=DecimalEncoder)
        assert "99.99" in result

    def test_non_decimal_raises(self):
        with pytest.raises(TypeError):
            json.dumps({"obj": object()}, cls=DecimalEncoder)


# ===================================================================
# Report registry
# ===================================================================


class TestReportRegistry:
    def test_all_12_reports_registered(self):
        """The plan specifies 12 standard reports."""
        assert len(REPORT_REGISTRY) == 12

    def test_all_reports_have_required_keys(self):
        for key, report in REPORT_REGISTRY.items():
            assert "name" in report, f"Report '{key}' missing 'name'"
            assert "description" in report, f"Report '{key}' missing 'description'"
            assert "fn" in report, f"Report '{key}' missing 'fn'"
            assert callable(report["fn"]), f"Report '{key}' fn is not callable"

    def test_expected_reports_exist(self):
        expected = [
            "gl_detail",
            "trial_balance",
            "journal_register",
            "account_activity",
            "subsidiary_ledger",
            "loan_portfolio",
            "interest_accrual",
            "provision_movement",
            "suspense_aging",
            "audit_trail",
            "reconciliation",
            "financial_statements",
        ]
        for key in expected:
            assert key in REPORT_REGISTRY, f"Missing report: {key}"


# ===================================================================
# NL Query patterns
# ===================================================================


class TestNLQueryPatterns:
    def test_patterns_count(self):
        """Should have at least 8 patterns."""
        assert len(PATTERNS) >= 8

    def test_balance_query_matches(self):
        import re
        question = "What is the balance of Performing Loans?"
        matched = False
        for pattern, handler in PATTERNS:
            if re.match(pattern, question, re.IGNORECASE):
                matched = True
                assert handler == "account_balance"
                break
        assert matched, "Balance query should match"

    def test_count_query_matches(self):
        import re
        question = "How many entries are posted?"
        matched = False
        for pattern, handler in PATTERNS:
            if re.match(pattern, question, re.IGNORECASE):
                matched = True
                assert handler == "entry_count"
                break
        assert matched, "Count query should match"

    def test_net_income_query_matches(self):
        import re
        question = "Show net income"
        matched = False
        for pattern, handler in PATTERNS:
            if re.match(pattern, question, re.IGNORECASE):
                matched = True
                assert handler == "net_income"
                break
        assert matched

    def test_trial_balance_matches(self):
        import re
        question = "Show the trial balance"
        matched = False
        for pattern, handler in PATTERNS:
            if re.match(pattern, question, re.IGNORECASE):
                matched = True
                assert handler == "trial_balance"
                break
        assert matched


# ===================================================================
# Anomaly detection
# ===================================================================


class TestAnomalyResult:
    def test_initial_state(self):
        result = AnomalyResult()
        assert result.risk_score == 0
        assert result.has_anomalies is False
        assert len(result.flags) == 0

    def test_add_flag(self):
        result = AnomalyResult()
        result.add_flag(AnomalyType.AMOUNT, 40, "High amount")
        assert result.risk_score == 40
        assert result.has_anomalies is True
        assert len(result.flags) == 1

    def test_multiple_flags_capped_at_100(self):
        result = AnomalyResult()
        result.add_flag(AnomalyType.AMOUNT, 50, "High amount")
        result.add_flag(AnomalyType.VELOCITY, 40, "High velocity")
        result.add_flag(AnomalyType.PATTERN, 30, "Unusual pattern")
        assert result.risk_score == 100  # Capped

    def test_flag_types(self):
        result = AnomalyResult()
        result.add_flag(AnomalyType.AMOUNT, 10, "x")
        result.add_flag(AnomalyType.PATTERN, 10, "y")
        assert result.flags[0]["type"] == AnomalyType.AMOUNT
        assert result.flags[1]["type"] == AnomalyType.PATTERN


# ===================================================================
# Classifier
# ===================================================================


class TestClassifier:
    def test_disbursement_keywords(self):
        results = _keyword_classify("Loan disbursement for customer A")
        assert len(results) > 0
        assert results[0]["category"] == "asset"

    def test_interest_income_keywords(self):
        results = _keyword_classify("Interest income accrual")
        assert len(results) > 0
        assert any(r["category"] == "revenue" for r in results)

    def test_provision_keywords(self):
        results = _keyword_classify("Provision expense for bad loans")
        assert len(results) > 0
        assert any(r["category"] == "expense" for r in results)

    def test_no_match(self):
        results = _keyword_classify("Random gibberish xyz123")
        assert len(results) == 0

    def test_multiple_matches(self):
        results = _keyword_classify("Late fee income on payment")
        assert len(results) >= 1

    def test_case_insensitive(self):
        results = _keyword_classify("LOAN DISBURSEMENT")
        assert len(results) > 0


# ===================================================================
# Condition evaluator (cross-module)
# ===================================================================


class TestConditionEvaluatorAdvanced:
    def test_nested_multiple_operators(self):
        conds = {
            "amount": {">=": 1000, "<=": 50000},
        }
        assert _evaluate_conditions(conds, {"amount": 25000}) is True
        assert _evaluate_conditions(conds, {"amount": 999}) is False
        assert _evaluate_conditions(conds, {"amount": 50001}) is False

    def test_empty_context(self):
        conds = {"field": {">": 0}}
        assert _evaluate_conditions(conds, {}) is False
