"""AI-powered bank statement analyzer.

Uses OpenAI GPT-5.2 to parse bank statement documents (PDF, CSV, images)
and produce structured analysis: categorized inflows/outflows, volatility
detection, and flagging of gambling or cash-squeeze patterns.
"""

import base64
import csv
import io
import json
import logging
import os
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 15_000  # truncate statement text to stay within token budget


# ── Text extraction helpers ───────────────────────────────────────────────

def _extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF bank statement using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber is required for PDF analysis. Install with: pip install pdfplumber")

    text_parts: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            # Try to extract tables first (more structured)
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if row:
                            text_parts.append("\t".join(str(cell or "") for cell in row))
            else:
                # Fall back to raw text
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_text_from_csv(file_path: str) -> str:
    """Read a CSV bank statement as text."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _encode_image_base64(file_path: str) -> str:
    """Read an image file and return its base64-encoded contents."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_mime_type(file_path: str, stored_mime: str | None = None) -> str:
    """Determine mime type from file extension or stored value."""
    if stored_mime:
        return stored_mime
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "application/octet-stream")


# ── System prompt ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert financial analyst specializing in bank statement analysis for lending decisions. You will analyze bank statement data and produce a comprehensive structured assessment.

## Your task
Analyze the provided bank statement and produce a JSON report with the following structure:

{
  "summary": "A 2-4 sentence narrative summary of the applicant's financial health, spending patterns, and any concerns.",
  "monthly_stats": [
    {
      "month": "YYYY-MM",
      "total_inflow": <number>,
      "total_outflow": <number>,
      "net": <number>,
      "min_balance": <number or null if not determinable>
    }
  ],
  "categories": {
    "inflows": {
      "salary": <total amount>,
      "transfers_in": <total>,
      "business_income": <total>,
      "government_benefits": <total>,
      "other_income": <total>
    },
    "outflows": {
      "rent_mortgage": <total>,
      "utilities": <total>,
      "groceries_food": <total>,
      "transportation": <total>,
      "insurance": <total>,
      "loan_repayments": <total>,
      "entertainment": <total>,
      "gambling_betting": <total>,
      "cash_withdrawals": <total>,
      "transfers_out": <total>,
      "subscriptions": <total>,
      "other_expenses": <total>
    }
  },
  "flags": [
    {
      "type": "gambling|cash_squeeze|high_cash_withdrawals|irregular_income|bounce_nsf|high_debt_service|declining_balance|unexplained_large_transactions",
      "severity": "high|medium|low",
      "detail": "Human-readable explanation of the concern",
      "amount_involved": <total amount related to this flag or null>,
      "occurrences": <number of instances or null>
    }
  ],
  "volatility_score": <0-100, where 0=very stable, 100=extremely volatile>,
  "risk_assessment": "low|moderate|high|very_high",
  "income_stability": "stable|variable|irregular|declining",
  "avg_monthly_inflow": <number>,
  "avg_monthly_outflow": <number>,
  "avg_monthly_net": <number>
}

## Flag detection rules
1. **gambling**: Any transactions to bookmakers, betting sites, casinos, lottery, or gambling-related merchants. Flag as HIGH if total > 5% of income.
2. **cash_squeeze**: Balance drops below 10% of monthly income more than twice, OR negative balance events. Flag as HIGH if frequent.
3. **high_cash_withdrawals**: Cash/ATM withdrawals exceeding 30% of total outflows. Could indicate undocumented expenses.
4. **irregular_income**: Income varies by more than 30% month-to-month without clear seasonal pattern.
5. **bounce_nsf**: Any returned/bounced payments or NSF (non-sufficient funds) fees.
6. **high_debt_service**: Loan repayments and debt service exceeding 40% of income.
7. **declining_balance**: Consistent downward trend in end-of-month balance over 3+ months.
8. **unexplained_large_transactions**: Single transactions exceeding 50% of monthly income without clear purpose.

## Volatility score calculation
- Base on coefficient of variation of monthly net cashflow
- Weight recent months more heavily
- Penalize for bounced payments, negative balance events, and irregular income

## Important notes
- All monetary amounts should be numbers (not strings)
- Use the currency as shown in the statement (typically TTD for Trinidad & Tobago)
- If data for a category is zero or not present, use 0
- If monthly data cannot be determined, provide best estimates with what's available
- If the statement is too short (less than 1 month), note this in the summary
- Sort monthly_stats chronologically (oldest first)
- Include ALL flags that apply, even minor ones (set severity accordingly)
"""


# ── Main analysis function ────────────────────────────────────────────────

def analyze_bank_statement(
    file_path: str,
    mime_type: str | None = None,
) -> dict[str, Any]:
    """Analyze a bank statement file with OpenAI GPT-5.2.

    Parameters
    ----------
    file_path : str
        Path to the bank statement file on disk.
    mime_type : str | None
        MIME type of the file.  Auto-detected from extension if not given.

    Returns
    -------
    dict  with keys matching the JSON schema above, plus a "status" key.
    """

    api_key = settings.openai_api_key
    if not api_key or api_key == "your-openai-api-key":
        return {
            "status": "error",
            "error": "OpenAI API key is not configured. Please set OPENAI_API_KEY.",
        }

    if not os.path.exists(file_path):
        return {
            "status": "error",
            "error": f"File not found: {file_path}",
        }

    detected_mime = _get_mime_type(file_path, mime_type)
    is_image = detected_mime.startswith("image/")

    # ── Build user message content ────────────────────────────────────
    if is_image:
        # Use Vision: send the image directly
        image_b64 = _encode_image_base64(file_path)
        user_content: list[dict] | str = [
            {
                "type": "text",
                "text": (
                    "Please analyze the following bank statement image and produce "
                    "the structured JSON analysis as described in your instructions."
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{detected_mime};base64,{image_b64}",
                    "detail": "high",
                },
            },
        ]
    else:
        # Extract text from PDF or CSV
        try:
            if detected_mime == "application/pdf":
                raw_text = _extract_text_from_pdf(file_path)
            elif detected_mime in ("text/csv", "text/plain"):
                raw_text = _extract_text_from_csv(file_path)
            else:
                # Try PDF first, fall back to plain text
                try:
                    raw_text = _extract_text_from_pdf(file_path)
                except Exception:
                    raw_text = _extract_text_from_csv(file_path)
        except Exception as e:
            logger.error("Failed to extract text from %s: %s", file_path, e)
            return {
                "status": "error",
                "error": f"Failed to read the bank statement file: {str(e)}",
            }

        if not raw_text or not raw_text.strip():
            return {
                "status": "error",
                "error": "The bank statement file appears to be empty or unreadable.",
            }

        # Truncate to stay within token limits
        if len(raw_text) > MAX_TEXT_CHARS:
            raw_text = raw_text[:MAX_TEXT_CHARS] + "\n\n[... statement truncated for analysis ...]"

        user_content = (
            "Please analyze the following bank statement text and produce "
            "the structured JSON analysis as described in your instructions.\n\n"
            "--- BANK STATEMENT START ---\n"
            f"{raw_text}\n"
            "--- BANK STATEMENT END ---"
        )

    # ── Call OpenAI ───────────────────────────────────────────────────
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_completion_tokens=4000,
        )
        raw_response = response.choices[0].message.content or "{}"
        result = json.loads(raw_response)
    except json.JSONDecodeError:
        logger.error("Failed to parse OpenAI bank analysis response")
        return {
            "status": "error",
            "error": "Failed to parse AI analysis response. The statement may be in an unsupported format.",
        }
    except Exception as e:
        logger.error("OpenAI bank statement analysis failed: %s", e)
        return {
            "status": "error",
            "error": f"AI analysis service error: {str(e)}",
        }

    # ── Validate / normalise the result ───────────────────────────────
    result["status"] = "completed"

    # Ensure required keys have sensible defaults
    result.setdefault("summary", "Analysis completed but no summary was generated.")
    result.setdefault("monthly_stats", [])
    result.setdefault("categories", {"inflows": {}, "outflows": {}})
    result.setdefault("flags", [])
    result.setdefault("volatility_score", 0)
    result.setdefault("risk_assessment", "moderate")
    result.setdefault("income_stability", "variable")
    result.setdefault("avg_monthly_inflow", 0)
    result.setdefault("avg_monthly_outflow", 0)
    result.setdefault("avg_monthly_net", 0)

    # Clamp volatility score
    try:
        result["volatility_score"] = max(0, min(100, float(result["volatility_score"])))
    except (TypeError, ValueError):
        result["volatility_score"] = 50

    return result
