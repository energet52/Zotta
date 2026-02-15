"""Tests for the bank statement analyzer service.

Tests the text extraction, validation logic, and error handling
WITHOUT calling the OpenAI API.  Where we need to test the full
analyze_bank_statement() path we mock the OpenAI client.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.services.bank_statement_analyzer import (
    _extract_text_from_csv,
    _get_mime_type,
    _encode_image_base64,
    analyze_bank_statement,
    MAX_TEXT_CHARS,
    SYSTEM_PROMPT,
)

TESTS_DIR = Path(__file__).parent


# ═══════════════════════════════════════════════════════════════════════════
# Helper fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def good_csv_path():
    return str(TESTS_DIR / "bank_statement_ttd_good.csv")


@pytest.fixture
def risky_csv_path():
    return str(TESTS_DIR / "bank_statement_ttd_risky.csv")


@pytest.fixture
def corrupt_csv_path():
    return str(TESTS_DIR / "bank_statement_corrupt.csv")


def _mock_openai_response(content_dict: dict):
    """Create a mock OpenAI response object."""
    mock_message = MagicMock()
    mock_message.content = json.dumps(content_dict)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


VALID_ANALYSIS_RESULT = {
    "summary": "The applicant shows stable income from Petrotrin Energy with regular salary deposits of TTD 8,500. Spending is disciplined with standard living costs.",
    "monthly_stats": [
        {"month": "2025-10", "total_inflow": 8502.35, "total_outflow": 6747.50, "net": 1754.85, "min_balance": 14223.50},
        {"month": "2025-11", "total_inflow": 8702.15, "total_outflow": 7724.85, "net": 977.30, "min_balance": 13678.85},
        {"month": "2025-12", "total_inflow": 12753.10, "total_outflow": 10514.00, "net": 2239.10, "min_balance": 14717.00},
    ],
    "categories": {
        "inflows": {"salary": 25500.00, "transfers_in": 0, "other_income": 7.60},
        "outflows": {
            "rent_mortgage": 8400.00,
            "utilities": 3015.00,
            "groceries_food": 3059.50,
            "transportation": 430.00,
            "insurance": 1875.00,
            "loan_repayments": 2400.00,
            "entertainment": 330.00,
            "gambling_betting": 0,
            "cash_withdrawals": 3700.00,
            "transfers_out": 1500.00,
            "subscriptions": 567.00,
            "other_expenses": 1710.00,
        },
    },
    "flags": [],
    "volatility_score": 18,
    "risk_assessment": "low",
    "income_stability": "stable",
    "avg_monthly_inflow": 9985.87,
    "avg_monthly_outflow": 8328.78,
    "avg_monthly_net": 1657.08,
}

RISKY_ANALYSIS_RESULT = {
    "summary": "HIGH RISK: Applicant shows heavy gambling activity (BetPlay, CaribBet, NLCB), declining income, multiple NSF/bounce fees, and reliance on emergency borrowing. Balance frequently drops to near-zero or negative.",
    "monthly_stats": [
        {"month": "2025-10", "total_inflow": 5920.00, "total_outflow": 8044.00, "net": -2124.00, "min_balance": 65.00},
        {"month": "2025-11", "total_inflow": 7185.00, "total_outflow": 7761.00, "net": -576.00, "min_balance": -564.00},
        {"month": "2025-12", "total_inflow": 7600.00, "total_outflow": 7407.00, "net": 193.00, "min_balance": -870.00},
    ],
    "categories": {
        "inflows": {"salary": 12500.00, "transfers_in": 5700.00, "other_income": 405.00},
        "outflows": {
            "rent_mortgage": 6600.00,
            "utilities": 2095.00,
            "groceries_food": 1195.00,
            "gambling_betting": 4750.00,
            "cash_withdrawals": 4500.00,
            "loan_repayments": 1950.00,
            "entertainment": 0,
            "subscriptions": 567.00,
            "other_expenses": 555.00,
        },
    },
    "flags": [
        {"type": "gambling", "severity": "high", "detail": "Multiple betting transactions (BetPlay, CaribBet, NLCB) totalling TTD 4,750 over 3 months — 38% of income.", "amount_involved": 4750, "occurrences": 18},
        {"type": "cash_squeeze", "severity": "high", "detail": "Balance dropped below TTD 100 on 8 occasions. Negative balance events in Nov and Dec.", "amount_involved": None, "occurrences": 8},
        {"type": "bounce_nsf", "severity": "high", "detail": "Two NSF fees and one returned payment indicating insufficient funds.", "amount_involved": 100, "occurrences": 2},
        {"type": "declining_balance", "severity": "medium", "detail": "End-of-month balance declining from TTD 676 to TTD 298 over three months.", "amount_involved": None, "occurrences": None},
        {"type": "irregular_income", "severity": "medium", "detail": "Income varies: TTD 4,500 to TTD 3,800 (15% drop). Multiple emergency loans suggest cash flow issues.", "amount_involved": None, "occurrences": None},
    ],
    "volatility_score": 82,
    "risk_assessment": "very_high",
    "income_stability": "declining",
    "avg_monthly_inflow": 6901.67,
    "avg_monthly_outflow": 7737.33,
    "avg_monthly_net": -835.67,
}


# ═══════════════════════════════════════════════════════════════════════════
# Text extraction tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTextExtraction:
    def test_csv_extraction_good_statement(self, good_csv_path):
        text = _extract_text_from_csv(good_csv_path)
        assert len(text) > 100
        assert "PETROTRIN" in text
        assert "SALARY" in text
        assert "TTD" in text or "Balance" in text

    def test_csv_extraction_risky_statement(self, risky_csv_path):
        text = _extract_text_from_csv(risky_csv_path)
        assert len(text) > 100
        assert "BETPLAY" in text
        assert "CARIBBET" in text
        assert "NLCB" in text

    def test_csv_extraction_empty_file(self, corrupt_csv_path):
        text = _extract_text_from_csv(corrupt_csv_path)
        assert text.strip() == ""

    def test_csv_extraction_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            _extract_text_from_csv("/nonexistent/path/statement.csv")


class TestMimeDetection:
    def test_csv_detection(self):
        assert _get_mime_type("statement.csv") == "text/csv"

    def test_pdf_detection(self):
        assert _get_mime_type("statement.pdf") == "application/pdf"

    def test_jpg_detection(self):
        assert _get_mime_type("scan.jpg") == "image/jpeg"

    def test_jpeg_detection(self):
        assert _get_mime_type("scan.jpeg") == "image/jpeg"

    def test_png_detection(self):
        assert _get_mime_type("scan.png") == "image/png"

    def test_unknown_extension(self):
        assert _get_mime_type("file.xyz") == "application/octet-stream"

    def test_stored_mime_takes_precedence(self):
        assert _get_mime_type("file.xyz", "application/pdf") == "application/pdf"


class TestBase64Encoding:
    def test_encode_small_file(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
            f.flush()
            encoded = _encode_image_base64(f.name)
            assert len(encoded) > 0
            # Should be valid base64
            import base64
            decoded = base64.b64decode(encoded)
            assert decoded.startswith(b"\x89PNG")
        os.unlink(f.name)


# ═══════════════════════════════════════════════════════════════════════════
# System prompt tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSystemPrompt:
    def test_prompt_mentions_gambling(self):
        assert "gambling" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_cash_squeeze(self):
        assert "cash_squeeze" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_volatility(self):
        assert "volatility" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_json_format(self):
        assert "json" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_bounce_nsf(self):
        assert "bounce" in SYSTEM_PROMPT.lower() or "nsf" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_declining_balance(self):
        assert "declining_balance" in SYSTEM_PROMPT.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Full analysis – happy path (mocked OpenAI)
# ═══════════════════════════════════════════════════════════════════════════

class TestAnalyzeHappyPath:
    """Test analyze_bank_statement with mocked OpenAI calls."""

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_good_statement_returns_completed(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(VALID_ANALYSIS_RESULT)

        result = analyze_bank_statement(good_csv_path, "text/csv")

        assert result["status"] == "completed"
        assert result["summary"] is not None
        assert "Petrotrin" in result["summary"]
        assert result["volatility_score"] == 18
        assert result["risk_assessment"] == "low"
        assert result["income_stability"] == "stable"
        assert len(result["monthly_stats"]) == 3
        assert len(result["flags"]) == 0

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_risky_statement_has_flags(self, mock_settings, mock_openai_cls, risky_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(RISKY_ANALYSIS_RESULT)

        result = analyze_bank_statement(risky_csv_path, "text/csv")

        assert result["status"] == "completed"
        assert result["risk_assessment"] == "very_high"
        assert result["volatility_score"] == 82
        assert len(result["flags"]) >= 3

        flag_types = [f["type"] for f in result["flags"]]
        assert "gambling" in flag_types
        assert "cash_squeeze" in flag_types
        assert "bounce_nsf" in flag_types

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_monthly_stats_structure(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(VALID_ANALYSIS_RESULT)

        result = analyze_bank_statement(good_csv_path, "text/csv")

        for stat in result["monthly_stats"]:
            assert "month" in stat
            assert "total_inflow" in stat
            assert "total_outflow" in stat
            assert "net" in stat

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_categories_have_inflows_and_outflows(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(VALID_ANALYSIS_RESULT)

        result = analyze_bank_statement(good_csv_path, "text/csv")

        categories = result["categories"]
        assert "inflows" in categories
        assert "outflows" in categories
        assert "salary" in categories["inflows"]
        assert "rent_mortgage" in categories["outflows"]

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_openai_called_with_correct_model(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(VALID_ANALYSIS_RESULT)

        analyze_bank_statement(good_csv_path, "text/csv")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-5.2"
        assert call_args.kwargs["temperature"] == 0.1
        assert call_args.kwargs["max_completion_tokens"] == 4000

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_text_passed_to_openai_contains_statement_data(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(VALID_ANALYSIS_RESULT)

        analyze_bank_statement(good_csv_path, "text/csv")

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        # The user message should contain bank statement data
        user_content = messages[1]["content"]
        assert "PETROTRIN" in user_content or "BANK STATEMENT" in user_content


# ═══════════════════════════════════════════════════════════════════════════
# Broken / error paths
# ═══════════════════════════════════════════════════════════════════════════

class TestAnalyzeErrorPaths:
    """Test error handling: missing files, empty files, bad API key, etc."""

    def test_no_api_key(self, good_csv_path):
        """Without API key, should return error status."""
        with patch("app.services.bank_statement_analyzer.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            result = analyze_bank_statement(good_csv_path, "text/csv")
            assert result["status"] == "error"
            assert "API key" in result["error"]

    def test_placeholder_api_key(self, good_csv_path):
        """With placeholder API key, should return error status."""
        with patch("app.services.bank_statement_analyzer.settings") as mock_settings:
            mock_settings.openai_api_key = "your-openai-api-key"
            result = analyze_bank_statement(good_csv_path, "text/csv")
            assert result["status"] == "error"
            assert "API key" in result["error"]

    def test_file_not_found(self):
        """Non-existent file should return error."""
        with patch("app.services.bank_statement_analyzer.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            result = analyze_bank_statement("/nonexistent/file.csv", "text/csv")
            assert result["status"] == "error"
            assert "not found" in result["error"].lower()

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_empty_file_returns_error(self, mock_settings, mock_openai_cls, corrupt_csv_path):
        """Empty CSV file should return error (no text to analyse)."""
        mock_settings.openai_api_key = "test-key-123"
        result = analyze_bank_statement(corrupt_csv_path, "text/csv")
        assert result["status"] == "error"
        assert "empty" in result["error"].lower() or "unreadable" in result["error"].lower()

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_openai_json_parse_failure(self, mock_settings, mock_openai_cls, good_csv_path):
        """If OpenAI returns unparseable JSON, should return error."""
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Return invalid JSON
        mock_message = MagicMock()
        mock_message.content = "This is not valid JSON {{{{"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        result = analyze_bank_statement(good_csv_path, "text/csv")
        assert result["status"] == "error"
        assert "parse" in result["error"].lower() or "format" in result["error"].lower()

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_openai_api_exception(self, mock_settings, mock_openai_cls, good_csv_path):
        """If OpenAI API throws an exception, should return error."""
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")

        result = analyze_bank_statement(good_csv_path, "text/csv")
        assert result["status"] == "error"
        assert "rate limit" in result["error"].lower() or "service error" in result["error"].lower()

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_openai_returns_empty_response(self, mock_settings, mock_openai_cls, good_csv_path):
        """If OpenAI returns empty content, should handle gracefully."""
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response({})

        result = analyze_bank_statement(good_csv_path, "text/csv")
        # Should still return completed with defaults
        assert result["status"] == "completed"
        assert result["summary"] is not None  # has default
        assert result["volatility_score"] == 0
        assert result["flags"] == []

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_corrupt_binary_content(self, mock_settings, mock_openai_cls):
        """Binary garbage file should return error."""
        mock_settings.openai_api_key = "test-key-123"

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(b"\x00\x01\x02\x03\xff\xfe\xfd" * 100)
            f.flush()
            path = f.name

        try:
            # The binary garbage may still be "read" as text but won't be meaningful
            # Since it's not empty, it will be sent to OpenAI mock
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value = _mock_openai_response({
                "summary": "Unable to parse meaningful financial data from this file.",
                "flags": [],
                "monthly_stats": [],
                "volatility_score": 0,
                "risk_assessment": "moderate",
            })

            result = analyze_bank_statement(path, "text/csv")
            # Should not crash — either error or completed with minimal data
            assert result["status"] in ("completed", "error")
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# Volatility score clamping
# ═══════════════════════════════════════════════════════════════════════════

class TestVolatilityScoreClamping:
    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_volatility_clamped_to_100(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        bad_result = dict(VALID_ANALYSIS_RESULT)
        bad_result["volatility_score"] = 150  # out of range
        mock_client.chat.completions.create.return_value = _mock_openai_response(bad_result)

        result = analyze_bank_statement(good_csv_path, "text/csv")
        assert result["volatility_score"] == 100

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_volatility_clamped_to_0(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        bad_result = dict(VALID_ANALYSIS_RESULT)
        bad_result["volatility_score"] = -20  # out of range
        mock_client.chat.completions.create.return_value = _mock_openai_response(bad_result)

        result = analyze_bank_statement(good_csv_path, "text/csv")
        assert result["volatility_score"] == 0

    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_volatility_non_numeric_defaults_to_50(self, mock_settings, mock_openai_cls, good_csv_path):
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        bad_result = dict(VALID_ANALYSIS_RESULT)
        bad_result["volatility_score"] = "not-a-number"
        mock_client.chat.completions.create.return_value = _mock_openai_response(bad_result)

        result = analyze_bank_statement(good_csv_path, "text/csv")
        assert result["volatility_score"] == 50


# ═══════════════════════════════════════════════════════════════════════════
# Text truncation
# ═══════════════════════════════════════════════════════════════════════════

class TestTextTruncation:
    @patch("app.services.bank_statement_analyzer.OpenAI")
    @patch("app.services.bank_statement_analyzer.settings")
    def test_very_large_file_is_truncated(self, mock_settings, mock_openai_cls):
        """A very large CSV should be truncated before sending to OpenAI."""
        mock_settings.openai_api_key = "test-key-123"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(VALID_ANALYSIS_RESULT)

        # Create a large temporary CSV
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("Date,Description,Debit,Credit,Balance\n")
            for i in range(5000):
                f.write(f"2025-01-{(i % 28) + 1:02d},TRANSACTION {i},{100.00},,{50000 - i * 10}.00\n")
            f.flush()
            path = f.name

        try:
            analyze_bank_statement(path, "text/csv")

            call_args = mock_client.chat.completions.create.call_args
            user_content = call_args.kwargs["messages"][1]["content"]
            # Should contain truncation marker
            assert "truncated" in user_content.lower()
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# Model / schema tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBankAnalysisModel:
    def test_model_imports(self):
        from app.models.bank_analysis import BankStatementAnalysis, AnalysisStatus
        assert BankStatementAnalysis.__tablename__ == "bank_statement_analyses"
        assert AnalysisStatus.PENDING.value == "pending"
        assert AnalysisStatus.COMPLETED.value == "completed"
        assert AnalysisStatus.FAILED.value == "failed"

    def test_schema_imports(self):
        from app.schemas import BankAnalysisResponse, BankAnalysisFlag, BankAnalysisMonthlyStat
        assert BankAnalysisResponse is not None
        assert BankAnalysisFlag is not None
        assert BankAnalysisMonthlyStat is not None

    def test_model_in_init(self):
        from app.models import BankStatementAnalysis
        assert BankStatementAnalysis is not None
