"""Pre-qualification check without credit bureau pull.

Uses DTI and basic rules to give indicative outcome.
"""

# Max DTI thresholds (as fraction)
MAX_DTI_UNSECURED = 0.40
MAX_DTI_SECURED = 0.50
MIN_INCOME = 3000.0
MIN_AGE = 18
MAX_AGE_AT_MATURITY = 75


def pre_qualify(
    monthly_income: float,
    monthly_expenses: float,
    existing_debt: float,
    loan_amount: float,
    term_months: int,
    age: int | None,
    monthly_payment: float | None = None,
) -> dict:
    """Run pre-qualification check.

    Returns dict with:
      outcome: pre_qualified | conditionally_pre_qualified | likely_decline | referral_required
      dti_ratio: float
      message: str
      suggestions: list[str]
    """
    if monthly_income < MIN_INCOME:
        return {
            "outcome": "likely_decline",
            "dti_ratio": 0,
            "message": f"Monthly income of TTD {monthly_income:,.0f} is below our minimum of TTD {MIN_INCOME:,.0f}.",
            "suggestions": ["Consider adding a co-borrower with income", "Reapply when income meets minimum"],
        }

    if age is not None:
        if age < MIN_AGE:
            return {
                "outcome": "likely_decline",
                "dti_ratio": 0,
                "message": f"Applicants must be at least {MIN_AGE} years old.",
                "suggestions": [],
            }
        years_to_maturity = term_months / 12
        age_at_maturity = age + years_to_maturity
        if age_at_maturity > MAX_AGE_AT_MATURITY:
            return {
                "outcome": "likely_decline",
                "dti_ratio": 0,
                "message": f"Loan term would extend past age {MAX_AGE_AT_MATURITY}. Consider a shorter term.",
                "suggestions": [f"Shorten term to mature before age {MAX_AGE_AT_MATURITY}"],
            }

    # Calculate proposed payment if not provided (approx)
    if monthly_payment is None and term_months > 0:
        # Assume ~15% rate for rough calc
        r = 0.15 / 12
        n = term_months
        monthly_payment = loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)

    total_debt = monthly_expenses + existing_debt + (monthly_payment or 0)
    dti = total_debt / monthly_income if monthly_income > 0 else 1.0

    if dti <= MAX_DTI_UNSECURED:
        return {
            "outcome": "pre_qualified",
            "dti_ratio": round(dti, 3),
            "message": f"Based on what you've told me, you're looking good. DTI is {dti*100:.0f}% (our max is {MAX_DTI_UNSECURED*100:.0f}% for unsecured).",
            "suggestions": [],
        }
    elif dti <= MAX_DTI_SECURED:
        return {
            "outcome": "conditionally_pre_qualified",
            "dti_ratio": round(dti, 3),
            "message": f"Your DTI is {dti*100:.0f}%. We may need to verify a few things. Consider a smaller amount or longer term to improve affordability.",
            "suggestions": ["Provide additional documentation", "Consider a smaller loan amount"],
        }
    else:
        suggested_payment = monthly_income * MAX_DTI_UNSECURED - monthly_expenses - existing_debt
        return {
            "outcome": "likely_decline",
            "dti_ratio": round(dti, 3),
            "message": f"At this amount, your DTI would be {dti*100:.0f}%, which exceeds our limit of {MAX_DTI_UNSECURED*100:.0f}%.",
            "suggestions": [
                f"Consider a smaller amount (max payment ~TTD {suggested_payment:,.0f}/month)",
                "Add a co-borrower to increase qualifying income",
                "Extend the term to lower the payment",
            ],
        }
