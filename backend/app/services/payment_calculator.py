"""Payment illustration for loan offers.

Calculates monthly payment, total interest, effective rate.
"""

from typing import Optional


def calculate_payment(
    principal: float,
    annual_rate: float,
    term_months: int,
) -> dict:
    """Calculate loan payment schedule summary.

    Uses standard amortization: PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
    """
    if term_months <= 0 or principal <= 0:
        return {
            "monthly_payment": 0,
            "total_interest": 0,
            "total_payable": principal,
            "effective_annual_rate": annual_rate,
        }
    r = annual_rate / 100 / 12
    n = term_months
    if (1 + r) ** n == 1:
        monthly = principal / n
    else:
        monthly = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    total_payable = monthly * n
    total_interest = total_payable - principal
    return {
        "monthly_payment": round(monthly, 2),
        "total_interest": round(total_interest, 2),
        "total_payable": round(total_payable, 2),
        "effective_annual_rate": round(annual_rate, 2),
    }
