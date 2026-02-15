"""Dynamic document requirements by product, employment type, and amount."""

from typing import Optional

# Employment types
EMPLOYED = "employed"
SELF_EMPLOYED = "self_employed"
CONTRACT = "contract"
RETIRED = "retired"

# Document types
DOC_NATIONAL_ID = "national_id"
DOC_PROOF_OF_ADDRESS = "proof_of_address"
DOC_PAYSLIP = "payslip"
DOC_EMPLOYMENT_LETTER = "employment_letter"
DOC_BANK_STATEMENT = "bank_statement"
DOC_BUSINESS_REGISTRATION = "business_registration"
DOC_FINANCIAL_STATEMENTS = "financial_statements"
DOC_COLLATERAL = "collateral"

EMPLOYED_UNSECURED = [
    {"type": DOC_NATIONAL_ID, "label": "National ID or Passport", "why": "To verify your identity"},
    {"type": DOC_PROOF_OF_ADDRESS, "label": "Utility bill or bank statement", "why": "Proof of address, less than 3 months old"},
    {"type": DOC_PAYSLIP, "label": "Last 2 payslips or salary letter", "why": "To verify your income"},
    {"type": DOC_BANK_STATEMENT, "label": "Last 3 months bank statements", "why": "To verify income deposits and spending patterns"},
]

SELF_EMPLOYED_ADDITIONAL = [
    {"type": DOC_BUSINESS_REGISTRATION, "label": "Business registration documents", "why": "To verify your business"},
    {"type": DOC_FINANCIAL_STATEMENTS, "label": "Last 2 years financial statements", "why": "To assess business income"},
    {"type": DOC_BANK_STATEMENT, "label": "Last 6 months business bank statements", "why": "To verify business cash flow"},
]


def get_required_documents(
    employment_type: Optional[str] = None,
    amount: float = 0,
    is_secured: bool = False,
) -> list[dict]:
    """Return required document list with labels and plain-language explanations."""
    emp = (employment_type or EMPLOYED).lower()
    docs = []
    if emp in (SELF_EMPLOYED, "self employed"):
        docs = list(EMPLOYED_UNSECURED)
        docs.extend(SELF_EMPLOYED_ADDITIONAL)
    else:
        docs = list(EMPLOYED_UNSECURED)

    if is_secured:
        docs.append({"type": DOC_COLLATERAL, "label": "Collateral documentation", "why": "Title, valuation, insurance"})

    return docs
