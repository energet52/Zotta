"""Business rules engine - configurable rule evaluation.

Rules are defined as JSON config and evaluated against application + scoring data.
"""

from dataclasses import dataclass, field
from typing import Optional


# Default business rules (can be overridden from DB)
DEFAULT_RULES = {
    "version": 1,
    "name": "Standard Personal Loan Rules v1",
    "rules": {
        "min_age": 18,
        "max_age": 65,
        "min_monthly_income": 3000.00,  # TTD
        "max_debt_to_income_ratio": 0.50,
        "max_loan_to_income_ratio": 5.0,
        "min_employment_years": 0.5,
        "auto_approve_score": 750,
        "auto_decline_score": 450,
        "max_loan_by_risk_band": {
            "A": 500000,
            "B": 300000,
            "C": 150000,
            "D": 50000,
            "E": 0,
        },
        "interest_rate_by_risk_band": {
            "A": 8.5,
            "B": 12.0,
            "C": 16.5,
            "D": 22.0,
            "E": 0,  # Not eligible
        },
        "blacklisted_national_ids": [],
    },
}


@dataclass
class RuleInput:
    """Input data for rules evaluation."""
    credit_score: int
    risk_band: str
    debt_to_income_ratio: float
    loan_to_income_ratio: float
    loan_amount_requested: float
    monthly_income: float
    applicant_age: int
    years_employed: float
    national_id: str = ""
    is_id_verified: bool = False


@dataclass
class RuleResult:
    """A single rule evaluation result."""
    rule_name: str
    passed: bool
    message: str
    severity: str = "hard"  # "hard" = blocks, "soft" = warning only


@dataclass
class RulesOutput:
    """Complete output from rules engine evaluation."""
    outcome: str  # auto_approve, auto_decline, manual_review
    results: list[RuleResult] = field(default_factory=list)
    suggested_rate: Optional[float] = None
    max_eligible_amount: Optional[float] = None
    reasons: list[str] = field(default_factory=list)


def evaluate_rules(
    input_data: RuleInput,
    rules_config: Optional[dict] = None,
) -> RulesOutput:
    """Evaluate all business rules against the application data.

    Returns an outcome (auto_approve / auto_decline / manual_review)
    along with detailed rule-by-rule results.
    """
    config = (rules_config or DEFAULT_RULES)["rules"]
    results: list[RuleResult] = []
    hard_fails: list[str] = []
    soft_fails: list[str] = []

    # Rule 1: Age check
    if input_data.applicant_age < config["min_age"]:
        r = RuleResult("min_age", False, f"Applicant must be at least {config['min_age']} years old", "hard")
        hard_fails.append(r.message)
    elif input_data.applicant_age > config["max_age"]:
        r = RuleResult("max_age", False, f"Applicant must be under {config['max_age']} years old", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("age_check", True, "Age within acceptable range")
    results.append(r)

    # Rule 2: Minimum income
    if input_data.monthly_income < config["min_monthly_income"]:
        r = RuleResult(
            "min_income", False,
            f"Monthly income TTD {input_data.monthly_income:,.2f} below minimum TTD {config['min_monthly_income']:,.2f}",
            "hard",
        )
        hard_fails.append(r.message)
    else:
        r = RuleResult("min_income", True, "Income meets minimum requirement")
    results.append(r)

    # Rule 3: Debt-to-income ratio
    if input_data.debt_to_income_ratio > config["max_debt_to_income_ratio"]:
        r = RuleResult(
            "dti_ratio", False,
            f"Debt-to-income ratio {input_data.debt_to_income_ratio:.1%} exceeds maximum {config['max_debt_to_income_ratio']:.0%}",
            "hard",
        )
        hard_fails.append(r.message)
    else:
        r = RuleResult("dti_ratio", True, "Debt-to-income ratio acceptable")
    results.append(r)

    # Rule 4: Loan-to-income ratio
    if input_data.loan_to_income_ratio > config["max_loan_to_income_ratio"]:
        r = RuleResult(
            "lti_ratio", False,
            f"Loan-to-income ratio {input_data.loan_to_income_ratio:.1f}x exceeds maximum {config['max_loan_to_income_ratio']}x",
            "soft",
        )
        soft_fails.append(r.message)
    else:
        r = RuleResult("lti_ratio", True, "Loan-to-income ratio acceptable")
    results.append(r)

    # Rule 5: Employment tenure
    if input_data.years_employed < config["min_employment_years"]:
        r = RuleResult(
            "employment_tenure", False,
            f"Employment tenure {input_data.years_employed:.1f} years below minimum {config['min_employment_years']} years",
            "soft",
        )
        soft_fails.append(r.message)
    else:
        r = RuleResult("employment_tenure", True, "Employment tenure sufficient")
    results.append(r)

    # Rule 6: Loan amount vs risk band max
    max_for_band = config["max_loan_by_risk_band"].get(input_data.risk_band, 0)
    if input_data.loan_amount_requested > max_for_band:
        r = RuleResult(
            "max_loan_amount", False,
            f"Requested TTD {input_data.loan_amount_requested:,.2f} exceeds max TTD {max_for_band:,.2f} for risk band {input_data.risk_band}",
            "hard" if max_for_band == 0 else "soft",
        )
        if max_for_band == 0:
            hard_fails.append(r.message)
        else:
            soft_fails.append(r.message)
    else:
        r = RuleResult("max_loan_amount", True, f"Amount within limit for risk band {input_data.risk_band}")
    results.append(r)

    # Rule 7: Blacklist check
    if input_data.national_id in config.get("blacklisted_national_ids", []):
        r = RuleResult("blacklist", False, "Applicant is on the blacklist", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("blacklist", True, "Not on blacklist")
    results.append(r)

    # Rule 8: ID verification
    if not input_data.is_id_verified:
        r = RuleResult("id_verification", False, "ID not yet verified", "soft")
        soft_fails.append(r.message)
    else:
        r = RuleResult("id_verification", True, "ID verified")
    results.append(r)

    # Determine outcome
    suggested_rate = config["interest_rate_by_risk_band"].get(input_data.risk_band, 0)

    if hard_fails:
        outcome = "auto_decline"
        reasons = hard_fails
    elif input_data.credit_score >= config["auto_approve_score"] and not soft_fails:
        outcome = "auto_approve"
        reasons = ["All criteria met, score above auto-approve threshold"]
    elif input_data.credit_score <= config["auto_decline_score"]:
        outcome = "auto_decline"
        reasons = [f"Credit score {input_data.credit_score} below auto-decline threshold"]
    else:
        outcome = "manual_review"
        reasons = soft_fails or ["Score in manual review range"]

    return RulesOutput(
        outcome=outcome,
        results=results,
        suggested_rate=suggested_rate if outcome != "auto_decline" else None,
        max_eligible_amount=max_for_band if outcome != "auto_decline" else None,
        reasons=reasons,
    )
