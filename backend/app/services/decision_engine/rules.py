"""Business rules engine - configurable rule evaluation.

Rules are defined as JSON config and evaluated against application + scoring data.
Implements R01-R13, R20 from the business rules specification.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.services.occupation_benchmarks import (
    check_income_benchmark,
    check_expense_benchmark,
)


# Default business rules (can be overridden from DB)
DEFAULT_RULES = {
    "version": 2,
    "name": "Standard Personal Loan Rules v2",
    "rules": {
        "min_age": 18,
        "max_maturity_age": 75,
        "min_monthly_income": 3000.00,  # TTD
        "max_dsr": 0.40,  # 40% soft limit (refer)
        "extreme_dsr": 1.00,  # 100% hard limit (decline)
        "max_loan_to_income_ratio": 5.0,
        "min_employment_months": 3,
        "min_monthly_expenses": 1500.00,  # TTD
        "auto_approve_score": 551,
        "auto_decline_score": 400,
        "refer_score_min": 400,
        "refer_score_max": 550,
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
    monthly_expenses: float = 0.0
    job_title: str = ""
    employment_type: str = ""
    term_months: int = 12
    # Credit bureau data
    has_active_debt_bureau: bool = False
    has_court_judgment: bool = False
    has_duplicate_within_30_days: bool = False


@dataclass
class RuleResult:
    """A single rule evaluation result."""
    rule_id: str
    rule_name: str
    passed: bool
    message: str
    severity: str = "hard"  # "hard" = blocks, "soft" = warning only, "refer" = refers


@dataclass
class RulesOutput:
    """Complete output from rules engine evaluation."""
    outcome: str  # auto_approve, auto_decline, manual_review
    results: list[RuleResult] = field(default_factory=list)
    suggested_rate: Optional[float] = None
    max_eligible_amount: Optional[float] = None
    reasons: list[str] = field(default_factory=list)
    income_benchmark: Optional[dict] = None
    expense_benchmark: Optional[dict] = None


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
    refer_reasons: list[str] = []

    # R01: Minimum Age
    if input_data.applicant_age < config["min_age"]:
        r = RuleResult("R01", "Minimum Age", False,
                        f"Applicant age {input_data.applicant_age} is below minimum {config['min_age']}", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R01", "Minimum Age", True, "Age meets minimum requirement")
    results.append(r)

    # R02: Max Age at Maturity
    maturity_age = input_data.applicant_age + input_data.term_months / 12
    max_maturity = config.get("max_maturity_age", 75)
    if maturity_age > max_maturity:
        r = RuleResult("R02", "Max Age at Maturity", False,
                        f"Age at loan maturity ({maturity_age:.0f}) exceeds maximum {max_maturity}", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R02", "Max Age at Maturity", True,
                        f"Age at maturity ({maturity_age:.0f}) within limit")
    results.append(r)

    # R03: Minimum Income
    if input_data.monthly_income < config["min_monthly_income"]:
        r = RuleResult("R03", "Minimum Income", False,
                        f"Monthly income TTD {input_data.monthly_income:,.2f} below minimum TTD {config['min_monthly_income']:,.2f}",
                        "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R03", "Minimum Income", True, "Income meets minimum requirement")
    results.append(r)

    # R04: Not Employed
    emp_type = (input_data.employment_type or "").lower()
    if emp_type in ("not_employed", "unemployed", "not employed"):
        r = RuleResult("R04", "Not Employed", False,
                        "Applicant is not employed", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R04", "Not Employed", True, "Employment status acceptable")
    results.append(r)

    # R05: AVK Outstanding Debt (active debt on bureau)
    if input_data.has_active_debt_bureau:
        r = RuleResult("R05", "AVK Outstanding Debt", False,
                        "Active outstanding debt found on credit bureau", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R05", "AVK Outstanding Debt", True, "No problematic bureau debt")
    results.append(r)

    # R06: AVK Judgment (court judgment on record)
    if input_data.has_court_judgment:
        r = RuleResult("R06", "AVK Judgment", False,
                        "Court judgment found on record", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R06", "AVK Judgment", True, "No court judgments")
    results.append(r)

    # R07: Duplicate Application (within 30 days)
    if input_data.has_duplicate_within_30_days:
        r = RuleResult("R07", "Duplicate Application", False,
                        "Duplicate application found within 30 days", "refer")
        refer_reasons.append(r.message)
    else:
        r = RuleResult("R07", "Duplicate Application", True, "No duplicate applications")
    results.append(r)

    # R08: Extreme DSR (>100%)
    extreme_dsr = config.get("extreme_dsr", 1.0)
    if input_data.debt_to_income_ratio > extreme_dsr:
        r = RuleResult("R08", "Extreme DSR", False,
                        f"Debt service ratio {input_data.debt_to_income_ratio:.1%} exceeds {extreme_dsr:.0%}", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R08", "Extreme DSR", True, "DSR within extreme limit")
    results.append(r)

    # R09: Short Employment (<3 months)
    min_emp_months = config.get("min_employment_months", 3)
    employment_months = input_data.years_employed * 12
    if employment_months < min_emp_months:
        r = RuleResult("R09", "Short Employment", False,
                        f"Employment tenure {employment_months:.0f} months below minimum {min_emp_months} months",
                        "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R09", "Short Employment", True, "Employment tenure sufficient")
    results.append(r)

    # R11: Self-Employed (refer)
    if emp_type in ("self_employed", "self-employed", "self employed"):
        r = RuleResult("R11", "Self-Employed", False,
                        "Self-employed applicant requires manual review", "refer")
        refer_reasons.append(r.message)
    else:
        r = RuleResult("R11", "Self-Employed", True, "Not self-employed")
    results.append(r)

    # R12: High DSR (40-100% is refer)
    max_dsr = config.get("max_dsr", 0.40)
    if not input_data.debt_to_income_ratio > extreme_dsr:  # Only if R08 didn't trigger
        if input_data.debt_to_income_ratio > max_dsr:
            r = RuleResult("R12", "High DSR", False,
                            f"Debt service ratio {input_data.debt_to_income_ratio:.1%} exceeds {max_dsr:.0%} (refer threshold)",
                            "refer")
            refer_reasons.append(r.message)
        else:
            r = RuleResult("R12", "High DSR", True, "DSR within acceptable range")
        results.append(r)

    # R13: Too Low Expenses
    min_expenses = config.get("min_monthly_expenses", 1500.0)
    if input_data.monthly_expenses < min_expenses:
        r = RuleResult("R13", "Too Low Expenses", False,
                        f"Monthly expenses TTD {input_data.monthly_expenses:,.2f} below minimum TTD {min_expenses:,.2f}",
                        "refer")
        refer_reasons.append(r.message)
    else:
        r = RuleResult("R13", "Too Low Expenses", True, "Expenses within expected range")
    results.append(r)

    # Loan amount vs risk band max
    max_for_band = config["max_loan_by_risk_band"].get(input_data.risk_band, 0)
    if input_data.loan_amount_requested > max_for_band:
        r = RuleResult("R14", "Max Loan Amount", False,
                        f"Requested TTD {input_data.loan_amount_requested:,.2f} exceeds max TTD {max_for_band:,.2f} for risk band {input_data.risk_band}",
                        "hard" if max_for_band == 0 else "refer")
        if max_for_band == 0:
            hard_fails.append(r.message)
        else:
            refer_reasons.append(r.message)
    else:
        r = RuleResult("R14", "Max Loan Amount", True,
                        f"Amount within limit for risk band {input_data.risk_band}")
    results.append(r)

    # Blacklist check
    if input_data.national_id in config.get("blacklisted_national_ids", []):
        r = RuleResult("R15", "Blacklist", False, "Applicant is on the blacklist", "hard")
        hard_fails.append(r.message)
    else:
        r = RuleResult("R15", "Blacklist", True, "Not on blacklist")
    results.append(r)

    # ID verification
    if not input_data.is_id_verified:
        r = RuleResult("R16", "ID Verification", False, "ID not yet verified", "soft")
        soft_fails.append(r.message)
    else:
        r = RuleResult("R16", "ID Verification", True, "ID verified")
    results.append(r)

    # Suspicious income (benchmark check) - kept as additional soft check
    income_check = check_income_benchmark(input_data.monthly_income, input_data.job_title)
    if income_check["flagged"]:
        r = RuleResult("R17", "Income Benchmark", False, income_check["message"], "soft")
        soft_fails.append(r.message)
    else:
        r = RuleResult("R17", "Income Benchmark", True, income_check["message"])
    results.append(r)

    # Understated expenses (benchmark check) - kept as additional soft check
    expense_check = check_expense_benchmark(input_data.monthly_expenses, input_data.job_title)
    if expense_check["flagged"]:
        r = RuleResult("R18", "Expense Benchmark", False, expense_check["message"], "soft")
        soft_fails.append(r.message)
    else:
        r = RuleResult("R18", "Expense Benchmark", True, expense_check["message"])
    results.append(r)

    # R20: Credit Score
    auto_decline = config.get("auto_decline_score", 400)
    refer_max = config.get("refer_score_max", 550)
    auto_approve = config.get("auto_approve_score", 551)
    if input_data.credit_score < auto_decline:
        r = RuleResult("R20", "Credit Score", False,
                        f"Credit score {input_data.credit_score} below decline threshold {auto_decline}", "hard")
        hard_fails.append(r.message)
    elif input_data.credit_score <= refer_max:
        r = RuleResult("R20", "Credit Score", False,
                        f"Credit score {input_data.credit_score} in refer range ({auto_decline}-{refer_max})", "refer")
        refer_reasons.append(r.message)
    else:
        r = RuleResult("R20", "Credit Score", True,
                        f"Credit score {input_data.credit_score} above approval threshold")
    results.append(r)

    # Determine outcome
    suggested_rate = config["interest_rate_by_risk_band"].get(input_data.risk_band, 0)

    if hard_fails:
        outcome = "auto_decline"
        reasons = hard_fails
    elif refer_reasons:
        outcome = "manual_review"
        reasons = refer_reasons + soft_fails
    elif input_data.credit_score >= auto_approve and not soft_fails:
        outcome = "auto_approve"
        reasons = ["All criteria met, score above auto-approve threshold"]
    else:
        outcome = "manual_review"
        reasons = soft_fails or ["Score in manual review range"]

    return RulesOutput(
        outcome=outcome,
        results=results,
        suggested_rate=suggested_rate if outcome != "auto_decline" else None,
        max_eligible_amount=max_for_band if outcome != "auto_decline" else None,
        reasons=reasons,
        income_benchmark=income_check,
        expense_benchmark=expense_check,
    )
