"""Business rules engine - configurable rule evaluation.

Rules are defined as a declarative registry and evaluated against
application + scoring data.  Each rule has an editable threshold,
a togglable outcome (decline / refer / pass / disable) and can be
enabled or disabled independently.

The registry is stored in DecisionRulesConfig.rules JSON column.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.services.occupation_benchmarks import (
    check_income_benchmark,
    check_expense_benchmark,
)


# ── Declarative rules registry ──────────────────────────────────────────
# Each entry maps a rule_id to its metadata.  "type" is either:
#   "threshold" — simple comparison evaluated generically
#   "complex"   — requires bespoke Python logic (still togglable)
#
# The registry below is the DEFAULT.  When an admin saves edits, a copy
# (with modified thresholds / outcomes / enabled flags) is stored in the
# DecisionRulesConfig table and loaded at evaluation time.

RULES_REGISTRY: dict[str, dict] = {
    "R01": {
        "name": "Minimum Age",
        "description": "Applicant must be at least {threshold} years old",
        "field": "applicant_age",
        "operator": "gte",
        "threshold": 18,
        "outcome": "decline",
        "severity": "hard",
        "type": "threshold",
        "is_custom": False,
        "enabled": True,
    },
    "R02": {
        "name": "Max Age at Maturity",
        "description": "Age at loan maturity must not exceed {threshold}",
        "field": "maturity_age",
        "operator": "lte",
        "threshold": 75,
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R03": {
        "name": "Minimum Income",
        "description": "Monthly income must be at least TTD {threshold}",
        "field": "monthly_income",
        "operator": "gte",
        "threshold": 3000.00,
        "outcome": "decline",
        "severity": "hard",
        "type": "threshold",
        "is_custom": False,
        "enabled": True,
    },
    "R04": {
        "name": "Not Employed",
        "description": "Applicant must not be unemployed",
        "field": "employment_type",
        "operator": "not_in",
        "threshold": ["not_employed", "unemployed", "not employed"],
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R05": {
        "name": "AVK Outstanding Debt",
        "description": "No active outstanding debt on credit bureau",
        "field": "has_active_debt_bureau",
        "operator": "eq",
        "threshold": False,
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R06": {
        "name": "AVK Judgment",
        "description": "No court judgment on record",
        "field": "has_court_judgment",
        "operator": "eq",
        "threshold": False,
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R07": {
        "name": "Duplicate Application",
        "description": "No duplicate application within 30 days",
        "field": "has_duplicate_within_30_days",
        "operator": "eq",
        "threshold": False,
        "outcome": "refer",
        "severity": "refer",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R08": {
        "name": "Extreme DSR",
        "description": "Debt service ratio must not exceed {threshold}%",
        "field": "debt_to_income_ratio",
        "operator": "lte",
        "threshold": 1.00,
        "outcome": "decline",
        "severity": "hard",
        "type": "threshold",
        "is_custom": False,
        "enabled": True,
    },
    "R09": {
        "name": "Short Employment",
        "description": "Employment tenure must be at least {threshold} months",
        "field": "employment_months",
        "operator": "gte",
        "threshold": 3,
        "outcome": "decline",
        "severity": "hard",
        "type": "threshold",
        "is_custom": False,
        "enabled": True,
    },
    "R11": {
        "name": "Self-Employed",
        "description": "Self-employed applicants require manual review",
        "field": "employment_type",
        "operator": "not_in",
        "threshold": ["self_employed", "self-employed", "self employed"],
        "outcome": "refer",
        "severity": "refer",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R12": {
        "name": "High DSR",
        "description": "Debt service ratio above {threshold}% requires review",
        "field": "debt_to_income_ratio",
        "operator": "lte",
        "threshold": 0.40,
        "outcome": "refer",
        "severity": "refer",
        "type": "threshold",
        "is_custom": False,
        "enabled": True,
    },
    "R13": {
        "name": "Too Low Expenses",
        "description": "Monthly expenses must be at least TTD {threshold}",
        "field": "monthly_expenses",
        "operator": "gte",
        "threshold": 1500.00,
        "outcome": "refer",
        "severity": "refer",
        "type": "threshold",
        "is_custom": False,
        "enabled": True,
    },
    "R14": {
        "name": "Max Loan Amount",
        "description": "Requested amount must not exceed risk band limit",
        "field": "loan_amount_requested",
        "operator": "lte",
        "threshold": None,  # dynamic — from risk band table
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R15": {
        "name": "Blacklist",
        "description": "Applicant must not be on the blacklist",
        "field": "national_id",
        "operator": "not_in",
        "threshold": [],
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R16": {
        "name": "ID Verification",
        "description": "ID should be verified",
        "field": "is_id_verified",
        "operator": "eq",
        "threshold": True,
        "outcome": "pass",
        "severity": "soft",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R17": {
        "name": "Income Benchmark",
        "description": "Income should be within expected range for occupation",
        "field": "monthly_income",
        "operator": "benchmark",
        "threshold": None,
        "outcome": "pass",
        "severity": "soft",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R18": {
        "name": "Expense Benchmark",
        "description": "Expenses should be within expected range for occupation",
        "field": "monthly_expenses",
        "operator": "benchmark",
        "threshold": None,
        "outcome": "pass",
        "severity": "soft",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R20": {
        "name": "Credit Score",
        "description": "Credit score thresholds for auto-decline/refer/approve",
        "field": "credit_score",
        "operator": "gte",
        "threshold": {
            "auto_decline_score": 400,
            "refer_score_max": 550,
            "auto_approve_score": 551,
        },
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
    "R21": {
        "name": "Scorecard Score",
        "description": "Scorecard score thresholds: auto-decline below {threshold[auto_decline]}, manual review up to {threshold[auto_approve]}, auto-approve above",
        "field": "scorecard_score",
        "operator": "gte",
        "threshold": {
            "auto_decline": 480,
            "auto_approve": 650,
        },
        "outcome": "decline",
        "severity": "hard",
        "type": "complex",
        "is_custom": False,
        "enabled": True,
    },
}


# Legacy thresholds kept for backward-compat with existing DB configs
DEFAULT_RULES = {
    "version": 2,
    "name": "Standard Personal Loan Rules v2",
    "rules": {
        "min_age": 18,
        "max_maturity_age": 75,
        "min_monthly_income": 3000.00,
        "max_dsr": 0.40,
        "extreme_dsr": 1.00,
        "max_loan_to_income_ratio": 5.0,
        "min_employment_months": 3,
        "min_monthly_expenses": 1500.00,
        "auto_approve_score": 551,
        "auto_decline_score": 400,
        "refer_score_min": 400,
        "refer_score_max": 550,
        "max_loan_by_risk_band": {
            "A": 500000, "B": 300000, "C": 150000, "D": 50000, "E": 0,
        },
        "interest_rate_by_risk_band": {
            "A": 8.5, "B": 12.0, "C": 16.5, "D": 22.0, "E": 0,
        },
        "blacklisted_national_ids": [],
    },
    # The new registry format is stored here when saved by the admin UI
    "rules_registry": None,  # will be populated on first admin save
}


# ── Data classes ─────────────────────────────────────────────────────────

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
    has_active_debt_bureau: bool = False
    has_court_judgment: bool = False
    has_duplicate_within_30_days: bool = False
    scorecard_score: Optional[float] = None


@dataclass
class RuleResult:
    """A single rule evaluation result."""
    rule_id: str
    rule_name: str
    passed: bool
    message: str
    severity: str = "hard"


@dataclass
class RulesOutput:
    """Complete output from rules engine evaluation."""
    outcome: str
    results: list[RuleResult] = field(default_factory=list)
    suggested_rate: Optional[float] = None
    max_eligible_amount: Optional[float] = None
    reasons: list[str] = field(default_factory=list)
    income_benchmark: Optional[dict] = None
    expense_benchmark: Optional[dict] = None


# ── Helpers ──────────────────────────────────────────────────────────────

def get_active_registry(rules_config: Optional[dict] = None) -> dict[str, dict]:
    """Return the rules registry, merging DB overrides on top of defaults."""
    registry = {k: dict(v) for k, v in RULES_REGISTRY.items()}  # deep copy

    if rules_config:
        # If the new-format registry is stored, overlay it
        saved = rules_config.get("rules_registry")
        if saved and isinstance(saved, dict):
            for rid, overrides in saved.items():
                if rid in registry:
                    registry[rid].update(overrides)
                else:
                    # custom rule added by admin
                    registry[rid] = overrides

    return registry


def _compare(value, operator: str, threshold) -> bool:
    """Generic comparison for simple threshold rules."""
    # Normalise strings for case-insensitive comparison
    v = value.strip().lower() if isinstance(value, str) else value
    t = threshold.strip().lower() if isinstance(threshold, str) else threshold

    if operator == "gte":
        return v >= t
    elif operator == "lte":
        return v <= t
    elif operator == "gt":
        return v > t
    elif operator == "lt":
        return v < t
    elif operator == "eq":
        return v == t
    elif operator == "neq":
        return v != t
    elif operator == "in":
        if isinstance(threshold, list):
            normed = [x.strip().lower() if isinstance(x, str) else x for x in threshold]
            return v in normed
        return v in t
    elif operator == "not_in":
        if isinstance(threshold, list):
            normed = [x.strip().lower() if isinstance(x, str) else x for x in threshold]
            return v not in normed
        return v not in t
    elif operator == "between":
        return t[0] <= v <= t[1]
    return True


def _get_field_value(input_data: RuleInput, field_name: str):
    """Retrieve a field value from RuleInput, including computed fields."""
    if field_name == "employment_months":
        return input_data.years_employed * 12
    if field_name == "maturity_age":
        return input_data.applicant_age + input_data.term_months / 12
    if field_name == "scorecard_score":
        return input_data.scorecard_score
    return getattr(input_data, field_name, None)


# ── Main evaluator ──────────────────────────────────────────────────────

def evaluate_rules(
    input_data: RuleInput,
    rules_config: Optional[dict] = None,
) -> RulesOutput:
    """Evaluate all business rules against the application data."""
    config = (rules_config or DEFAULT_RULES).get("rules", DEFAULT_RULES["rules"])
    registry = get_active_registry(rules_config)

    results: list[RuleResult] = []
    hard_fails: list[str] = []
    soft_fails: list[str] = []
    refer_reasons: list[str] = []

    def _record(r: RuleResult):
        results.append(r)
        if not r.passed:
            if r.severity == "hard":
                hard_fails.append(r.message)
            elif r.severity == "refer":
                refer_reasons.append(r.message)
            elif r.severity == "soft":
                soft_fails.append(r.message)

    # Map outcome string to severity
    def _outcome_to_severity(outcome: str, default: str) -> str:
        return {"decline": "hard", "refer": "refer", "pass": "soft"}.get(outcome, default)

    for rule_id in sorted(registry.keys()):
        rule = registry[rule_id]
        if not rule.get("enabled", True):
            results.append(RuleResult(rule_id, rule["name"], True, "Rule disabled", "soft"))
            continue

        outcome = rule.get("outcome", "decline")
        if outcome == "disable":
            results.append(RuleResult(rule_id, rule["name"], True, "Rule disabled", "soft"))
            continue

        severity = _outcome_to_severity(outcome, rule.get("severity", "hard"))
        rtype = rule.get("type", "threshold")

        # ── Custom / threshold rules (data-driven) ───────────────────
        if rtype == "threshold" or rule.get("is_custom"):
            _evaluate_threshold_rule(rule_id, rule, input_data, severity, _record)
            continue

        # ── Complex built-in rules (bespoke logic) ───────────────────
        if rule_id == "R01":
            val = input_data.applicant_age
            thresh = rule.get("threshold", config.get("min_age", 18))
            if val < thresh:
                _record(RuleResult(rule_id, rule["name"], False,
                    f"Applicant age {val} is below minimum {thresh}", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "Age meets minimum requirement"))

        elif rule_id == "R02":
            maturity_age = input_data.applicant_age + input_data.term_months / 12
            max_mat = rule.get("threshold", config.get("max_maturity_age", 75))
            if maturity_age > max_mat:
                _record(RuleResult(rule_id, rule["name"], False,
                    f"Age at loan maturity ({maturity_age:.0f}) exceeds maximum {max_mat}", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True,
                    f"Age at maturity ({maturity_age:.0f}) within limit"))

        elif rule_id == "R04":
            emp = (input_data.employment_type or "").lower()
            if emp in ("not_employed", "unemployed", "not employed"):
                _record(RuleResult(rule_id, rule["name"], False,
                    "Applicant is not employed", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "Employment status acceptable"))

        elif rule_id == "R05":
            if input_data.has_active_debt_bureau:
                _record(RuleResult(rule_id, rule["name"], False,
                    "Active outstanding debt found on credit bureau", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "No problematic bureau debt"))

        elif rule_id == "R06":
            if input_data.has_court_judgment:
                _record(RuleResult(rule_id, rule["name"], False,
                    "Court judgment found on record", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "No court judgments"))

        elif rule_id == "R07":
            if input_data.has_duplicate_within_30_days:
                _record(RuleResult(rule_id, rule["name"], False,
                    "Duplicate application found within 30 days", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "No duplicate applications"))

        elif rule_id == "R11":
            emp = (input_data.employment_type or "").lower()
            if emp in ("self_employed", "self-employed", "self employed"):
                _record(RuleResult(rule_id, rule["name"], False,
                    "Self-employed applicant requires manual review", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "Not self-employed"))

        elif rule_id == "R12":
            max_dsr = rule.get("threshold", config.get("max_dsr", 0.40))
            extreme_dsr = registry.get("R08", {}).get("threshold", config.get("extreme_dsr", 1.0))
            if input_data.debt_to_income_ratio <= extreme_dsr:
                if input_data.debt_to_income_ratio > max_dsr:
                    _record(RuleResult(rule_id, rule["name"], False,
                        f"Debt service ratio {input_data.debt_to_income_ratio:.1%} exceeds {max_dsr:.0%}", severity))
                else:
                    _record(RuleResult(rule_id, rule["name"], True, "DSR within acceptable range"))

        elif rule_id == "R14":
            band_limits = config.get("max_loan_by_risk_band", {})
            max_for_band = band_limits.get(input_data.risk_band, 999_999_999) if band_limits else 999_999_999
            if input_data.loan_amount_requested > max_for_band:
                sev = severity if max_for_band > 0 else "hard"
                _record(RuleResult(rule_id, rule["name"], False,
                    f"Requested TTD {input_data.loan_amount_requested:,.2f} exceeds max TTD {max_for_band:,.2f} for risk band {input_data.risk_band}",
                    sev))
            else:
                _record(RuleResult(rule_id, rule["name"], True,
                    f"Amount within limit for risk band {input_data.risk_band}"))

        elif rule_id == "R15":
            blacklist = rule.get("threshold", config.get("blacklisted_national_ids", []))
            if isinstance(blacklist, list) and input_data.national_id in blacklist:
                _record(RuleResult(rule_id, rule["name"], False,
                    "Applicant is on the blacklist", severity))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "Not on blacklist"))

        elif rule_id == "R16":
            if not input_data.is_id_verified:
                _record(RuleResult(rule_id, rule["name"], False, "ID not yet verified", "soft"))
            else:
                _record(RuleResult(rule_id, rule["name"], True, "ID verified"))

        elif rule_id == "R17":
            income_check = check_income_benchmark(input_data.monthly_income, input_data.job_title)
            if income_check["flagged"]:
                _record(RuleResult(rule_id, rule["name"], False, income_check["message"], "soft"))
            else:
                _record(RuleResult(rule_id, rule["name"], True, income_check["message"]))

        elif rule_id == "R18":
            expense_check = check_expense_benchmark(input_data.monthly_expenses, input_data.job_title)
            if expense_check["flagged"]:
                _record(RuleResult(rule_id, rule["name"], False, expense_check["message"], "soft"))
            else:
                _record(RuleResult(rule_id, rule["name"], True, expense_check["message"]))

        elif rule_id == "R20":
            thresholds = rule.get("threshold", {})
            if isinstance(thresholds, dict):
                auto_decline = thresholds.get("auto_decline_score", config.get("auto_decline_score", 400))
                refer_max = thresholds.get("refer_score_max", config.get("refer_score_max", 550))
            else:
                auto_decline = config.get("auto_decline_score", 400)
                refer_max = config.get("refer_score_max", 550)

            if input_data.credit_score < auto_decline:
                _record(RuleResult(rule_id, rule["name"], False,
                    f"Credit score {input_data.credit_score} below decline threshold {auto_decline}", "hard"))
            elif input_data.credit_score <= refer_max:
                _record(RuleResult(rule_id, rule["name"], False,
                    f"Credit score {input_data.credit_score} in refer range ({auto_decline}-{refer_max})", "refer"))
            else:
                _record(RuleResult(rule_id, rule["name"], True,
                    f"Credit score {input_data.credit_score} above approval threshold"))

        elif rule_id == "R21":
            # Scorecard score rule — uses the score from the scorecard engine
            if input_data.scorecard_score is None:
                _record(RuleResult(rule_id, rule["name"], True,
                    "No scorecard score available — rule skipped", "soft"))
            else:
                thresholds = rule.get("threshold", {})
                if isinstance(thresholds, dict):
                    sc_decline = thresholds.get("auto_decline", 480)
                    sc_approve = thresholds.get("auto_approve", 650)
                else:
                    sc_decline = 480
                    sc_approve = 650

                score = input_data.scorecard_score
                if score < sc_decline:
                    _record(RuleResult(rule_id, rule["name"], False,
                        f"Scorecard score {score:.0f} below decline threshold {sc_decline}", severity))
                elif score < sc_approve:
                    _record(RuleResult(rule_id, rule["name"], False,
                        f"Scorecard score {score:.0f} in manual review range ({sc_decline}-{sc_approve})", "refer"))
                else:
                    _record(RuleResult(rule_id, rule["name"], True,
                        f"Scorecard score {score:.0f} above auto-approve threshold {sc_approve}"))

        else:
            # Unknown complex rule — skip
            _record(RuleResult(rule_id, rule["name"], True, "Rule not evaluated (unknown complex type)"))

    # ── Determine outcome ────────────────────────────────────────────────
    rate_table = config.get("interest_rate_by_risk_band", {})
    suggested_rate = rate_table.get(input_data.risk_band, 12.0) if rate_table else 12.0
    band_limits_final = config.get("max_loan_by_risk_band", {})
    max_for_band = band_limits_final.get(input_data.risk_band, input_data.loan_amount_requested) if band_limits_final else input_data.loan_amount_requested
    auto_approve_score = config.get("auto_approve_score", 551)

    # Benchmarks for the response
    income_check = check_income_benchmark(input_data.monthly_income, input_data.job_title)
    expense_check = check_expense_benchmark(input_data.monthly_expenses, input_data.job_title)

    if hard_fails:
        outcome = "auto_decline"
        reasons = hard_fails
    elif refer_reasons:
        outcome = "manual_review"
        reasons = refer_reasons + soft_fails
    elif input_data.credit_score >= auto_approve_score and not soft_fails:
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


def _evaluate_threshold_rule(
    rule_id: str,
    rule: dict,
    input_data: RuleInput,
    severity: str,
    record_fn,
):
    """Evaluate a simple data-driven threshold rule (including AI-generated custom rules)."""
    field_name = rule.get("field", "")
    operator = rule.get("operator", "gte")
    threshold = rule.get("threshold")
    name = rule.get("name", rule_id)

    value = _get_field_value(input_data, field_name)
    if value is None:
        record_fn(RuleResult(rule_id, name, True,
            f"Field '{field_name}' not available — rule skipped", "soft"))
        return

    if threshold is None:
        record_fn(RuleResult(rule_id, name, True,
            f"No threshold configured — rule skipped", "soft"))
        return

    comparison = _compare(value, operator, threshold)

    # Custom (AI-generated) rules express the BLOCKING condition:
    #   "decline when job_title eq Managerial" → match triggers failure.
    # Built-in threshold rules express the ACCEPTABLE condition:
    #   "age gte 18" → match means the applicant passes.
    if rule.get("is_custom"):
        passed = not comparison
    else:
        passed = comparison

    if passed:
        record_fn(RuleResult(rule_id, name, True,
            f"{field_name} ({value}) meets requirement"))
    else:
        record_fn(RuleResult(rule_id, name, False,
            f"{field_name} ({value}) fails check ({operator} {threshold})", severity))
