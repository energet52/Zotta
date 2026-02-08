"""Credit scoring module - weighted scorecard model.

Produces a numeric score (300-850) and maps it to a risk band (A-E).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScoringInput:
    """Input data for credit scoring."""
    # Credit bureau data
    bureau_score: Optional[int] = None
    payment_history_score: float = 0.5  # 0-1, higher = better
    outstanding_debt: float = 0
    num_inquiries: int = 0
    credit_history_years: float = 0

    # Applicant financials
    monthly_income: float = 0
    monthly_expenses: float = 0
    existing_debt: float = 0
    loan_amount_requested: float = 0
    years_employed: int = 0
    employment_type: str = "employed"  # employed, self_employed, contract, unemployed


@dataclass
class ScoringResult:
    """Output from credit scoring."""
    total_score: int
    risk_band: str
    breakdown: dict
    debt_to_income_ratio: float
    loan_to_income_ratio: float


# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "payment_history": 0.25,
    "outstanding_debt": 0.15,
    "credit_history": 0.10,
    "inquiries": 0.05,
    "debt_to_income": 0.20,
    "employment": 0.10,
    "loan_to_income": 0.15,
}

# Risk band thresholds
RISK_BANDS = {
    "A": (750, 850),  # Excellent
    "B": (680, 749),  # Good
    "C": (600, 679),  # Fair
    "D": (500, 599),  # Poor
    "E": (300, 499),  # Very Poor
}


def calculate_score(input_data: ScoringInput) -> ScoringResult:
    """Calculate a credit score based on the weighted scorecard model.

    Each factor produces a sub-score in range 0-100, then the weighted
    sum is mapped to the 300-850 range.
    """
    breakdown = {}

    # 1. Payment history (0-100)
    payment_score = input_data.payment_history_score * 100
    breakdown["payment_history"] = round(payment_score, 1)

    # 2. Outstanding debt ratio (lower is better)
    if input_data.monthly_income > 0:
        debt_ratio = input_data.outstanding_debt / (input_data.monthly_income * 12)
        debt_score = max(0, 100 - (debt_ratio * 100))
    else:
        debt_score = 20
    breakdown["outstanding_debt"] = round(debt_score, 1)

    # 3. Credit history length
    years = input_data.credit_history_years
    if years >= 10:
        history_score = 100
    elif years >= 5:
        history_score = 75
    elif years >= 2:
        history_score = 50
    elif years >= 1:
        history_score = 30
    else:
        history_score = 10
    breakdown["credit_history"] = history_score

    # 4. Number of inquiries (fewer is better)
    inq = input_data.num_inquiries
    if inq == 0:
        inq_score = 100
    elif inq <= 2:
        inq_score = 80
    elif inq <= 5:
        inq_score = 50
    else:
        inq_score = max(0, 100 - inq * 10)
    breakdown["inquiries"] = inq_score

    # 5. Debt-to-income ratio
    if input_data.monthly_income > 0:
        dti = (input_data.monthly_expenses + input_data.existing_debt) / input_data.monthly_income
    else:
        dti = 1.0
    dti_score = max(0, 100 - (dti * 100))
    breakdown["debt_to_income"] = round(dti_score, 1)

    # 6. Employment stability
    emp_scores = {
        "employed": 70,
        "self_employed": 55,
        "contract": 40,
        "unemployed": 10,
    }
    base_emp = emp_scores.get(input_data.employment_type, 40)
    years_bonus = min(30, input_data.years_employed * 5)
    emp_score = min(100, base_emp + years_bonus)
    breakdown["employment"] = emp_score

    # 7. Loan-to-income ratio
    if input_data.monthly_income > 0:
        lti = input_data.loan_amount_requested / (input_data.monthly_income * 12)
    else:
        lti = 5.0
    lti_score = max(0, 100 - (lti * 50))
    breakdown["loan_to_income"] = round(lti_score, 1)

    # Weighted sum -> 0-100
    weighted_sum = sum(
        breakdown[key] * WEIGHTS[key] for key in WEIGHTS
    )

    # Map 0-100 to 300-850
    total_score = int(300 + (weighted_sum / 100) * 550)
    total_score = max(300, min(850, total_score))

    # If we have a bureau score, blend it (60% our score, 40% bureau)
    if input_data.bureau_score and input_data.bureau_score > 0:
        total_score = int(total_score * 0.6 + input_data.bureau_score * 0.4)
        total_score = max(300, min(850, total_score))

    # Determine risk band
    risk_band = "E"
    for band, (low, high) in RISK_BANDS.items():
        if low <= total_score <= high:
            risk_band = band
            break

    # Calculate ratios for output
    dti_ratio = dti if input_data.monthly_income > 0 else 0
    lti_ratio = lti if input_data.monthly_income > 0 else 0

    return ScoringResult(
        total_score=total_score,
        risk_band=risk_band,
        breakdown=breakdown,
        debt_to_income_ratio=round(dti_ratio, 3),
        loan_to_income_ratio=round(lti_ratio, 3),
    )
