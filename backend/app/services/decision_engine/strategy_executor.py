"""Strategy Executor — evaluates an application against a decision strategy.

Supports four evaluation modes:
  - sequential: delegates to existing evaluate_rules() (backward compat)
  - dual_path: 7-step pipeline (knock-outs → data check → scorecard → score
                decision → overlays → terms → output)
  - scoring: weighted points system
  - hybrid: sequential knock-outs then scoring for remainder
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.strategy import DecisionStrategy, EvaluationMode
from app.services.decision_engine.rules import (
    RuleInput, RulesOutput, RuleResult, evaluate_rules, get_active_registry,
    DEFAULT_RULES, _compare, _get_field_value,
)


# ── Result types ───────────────────────────────────────────────────

@dataclass
class TermsAssignment:
    approved_amount: float | None = None
    interest_rate: float | None = None
    pricing_tier: str | None = None
    down_payment_pct: float | None = None
    max_tenure_months: int | None = None
    conditions: list[str] = field(default_factory=list)
    condition_codes: list[str] = field(default_factory=list)


@dataclass
class EvaluationStep:
    step_name: str
    step_number: int
    outcome: str  # "pass", "decline", "refer", "approve", "skip"
    details: str
    rules_fired: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)


@dataclass
class StrategyResult:
    outcome: str  # "approve", "decline", "refer"
    outcome_detail: str = ""  # "approved_standard", "approved_with_conditions", "approved_reduced", etc.
    reason_codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    terms: TermsAssignment | None = None
    evaluation_steps: list[EvaluationStep] = field(default_factory=list)
    scorecard_score: float | None = None
    suggested_rate: float | None = None
    suggested_amount: float | None = None
    # For compatibility with existing RulesOutput
    rules_output: RulesOutput | None = None
    recommendation: str | None = None


# ── Main executor ──────────────────────────────────────────────────

def execute_strategy(
    strategy: DecisionStrategy,
    rule_input: RuleInput,
    rules_config: dict | None = None,
    routing_params: dict | None = None,
    scorecard_score: float | None = None,
    portfolio_data: dict | None = None,
) -> StrategyResult:
    """Execute a decision strategy against prepared rule input.

    Args:
        strategy: The DecisionStrategy to execute
        rule_input: Prepared RuleInput with application data
        rules_config: Optional rules config override (for sequential mode)
        routing_params: Parameter overrides from the tree terminal node
        scorecard_score: Pre-computed scorecard score (if available)
        portfolio_data: Current portfolio state for concentration checks
    """
    mode = strategy.evaluation_mode

    if mode == EvaluationMode.SEQUENTIAL:
        return _execute_sequential(strategy, rule_input, rules_config, routing_params)
    elif mode == EvaluationMode.DUAL_PATH:
        return _execute_dual_path(
            strategy, rule_input, scorecard_score, routing_params, portfolio_data,
        )
    elif mode == EvaluationMode.SCORING:
        return _execute_scoring(strategy, rule_input, routing_params)
    elif mode == EvaluationMode.HYBRID:
        return _execute_hybrid(strategy, rule_input, scorecard_score, routing_params)
    else:
        return _execute_sequential(strategy, rule_input, rules_config, routing_params)


# ── Sequential mode (backward compatible) ──────────────────────────

def _execute_sequential(
    strategy: DecisionStrategy,
    rule_input: RuleInput,
    rules_config: dict | None,
    routing_params: dict | None,
) -> StrategyResult:
    """Delegate to existing evaluate_rules() — the existing single-strategy path."""
    config = rules_config or DEFAULT_RULES
    rules_output = evaluate_rules(rule_input, config)

    result = StrategyResult(
        outcome=_map_outcome(rules_output.outcome),
        reasons=rules_output.reasons,
        suggested_rate=rules_output.suggested_rate,
        suggested_amount=rules_output.max_eligible_amount,
        rules_output=rules_output,
    )

    _apply_routing_params(result, routing_params, rule_input)

    result.evaluation_steps.append(EvaluationStep(
        step_name="Sequential Rules Evaluation",
        step_number=1,
        outcome=rules_output.outcome,
        details=f"Evaluated {len(rules_output.results)} rules",
        rules_fired=[
            {"id": r.rule_id, "name": r.rule_name, "passed": r.passed, "message": r.message}
            for r in rules_output.results if not r.passed
        ],
    ))

    return result


# ── Dual-path mode (industry-standard) ─────────────────────────────

def _execute_dual_path(
    strategy: DecisionStrategy,
    rule_input: RuleInput,
    scorecard_score: float | None,
    routing_params: dict | None,
    portfolio_data: dict | None,
) -> StrategyResult:
    """7-step dual-path evaluation pipeline."""
    steps: list[EvaluationStep] = []
    result = StrategyResult(outcome="approve", evaluation_steps=steps)

    # Step 1: Policy Knock-Outs
    knock_outs = strategy.knock_out_rules or []
    ko_failures = _evaluate_rule_set(knock_outs, rule_input, "hard")

    steps.append(EvaluationStep(
        step_name="Policy Knock-Outs",
        step_number=1,
        outcome="decline" if ko_failures else "pass",
        details=f"Evaluated {len(knock_outs)} knock-out rules, {len(ko_failures)} failed",
        rules_fired=ko_failures,
    ))

    if ko_failures:
        result.outcome = "decline"
        result.reasons = [f["message"] for f in ko_failures]
        result.reason_codes = [f.get("reason_code", f["rule_id"]) for f in ko_failures]
        return result

    # Step 2: Data Sufficiency Check
    data_issues = _check_data_sufficiency(rule_input, scorecard_score)
    steps.append(EvaluationStep(
        step_name="Data Sufficiency Check",
        step_number=2,
        outcome="refer" if data_issues else "pass",
        details="Insufficient data for automated decision" if data_issues else "Data sufficient",
        data={"issues": data_issues} if data_issues else {},
    ))

    if data_issues:
        result.outcome = "refer"
        result.reasons = data_issues
        result.reason_codes = ["DATA_INSUFFICIENT"]
        result.recommendation = "Manual review required due to insufficient data"
        return result

    # Step 3: Scorecard Evaluation
    cutoffs = strategy.score_cutoffs or {}
    score = scorecard_score

    if score is not None:
        result.scorecard_score = score
        steps.append(EvaluationStep(
            step_name="Scorecard Evaluation",
            step_number=3,
            outcome="pass",
            details=f"Scorecard score: {score:.0f}",
            data={"score": score, "cutoffs": cutoffs},
        ))
    else:
        steps.append(EvaluationStep(
            step_name="Scorecard Evaluation",
            step_number=3,
            outcome="skip",
            details="No scorecard configured or score unavailable",
        ))

    # Step 4: Score-Based Decision
    pre_decision = "approve"
    if score is not None and cutoffs:
        decline_cutoff = cutoffs.get("decline", 0)
        refer_cutoff = cutoffs.get("refer", 0)
        approve_cutoff = cutoffs.get("approve", 0)

        if score < decline_cutoff:
            pre_decision = "decline"
        elif score < refer_cutoff:
            pre_decision = "refer"
        elif score >= approve_cutoff:
            pre_decision = "approve"
        else:
            pre_decision = "refer"

        steps.append(EvaluationStep(
            step_name="Score-Based Decision",
            step_number=4,
            outcome=pre_decision,
            details=f"Score {score:.0f}: {'below decline' if pre_decision == 'decline' else 'in refer band' if pre_decision == 'refer' else 'above approve'} cutoff",
            data={"pre_decision": pre_decision, "score": score},
        ))

        if pre_decision == "decline":
            result.outcome = "decline"
            result.reasons = [f"Score {score:.0f} below decline cutoff {decline_cutoff}"]
            result.reason_codes = ["SCORE_BELOW_CUTOFF"]
            return result
    else:
        steps.append(EvaluationStep(
            step_name="Score-Based Decision",
            step_number=4,
            outcome="skip",
            details="No score-based routing (rules-only path)",
        ))

    # Step 5: Policy Overlays
    overlays = strategy.overlay_rules or []
    overlay_failures = _evaluate_rule_set(overlays, rule_input, "refer")
    overlay_upgrades = [
        f for f in overlay_failures if f.get("action") == "upgrade"
    ]
    overlay_downgrades = [
        f for f in overlay_failures if f.get("action") != "upgrade"
    ]

    current_decision = pre_decision
    if overlay_downgrades and current_decision == "approve":
        severity_map = {f.get("severity", "refer") for f in overlay_downgrades}
        if "hard" in severity_map:
            current_decision = "decline"
        else:
            current_decision = "refer"

    if overlay_upgrades and current_decision == "refer":
        current_decision = "approve"

    steps.append(EvaluationStep(
        step_name="Policy Overlays",
        step_number=5,
        outcome=current_decision,
        details=f"{len(overlay_downgrades)} restrictions, {len(overlay_upgrades)} upgrades applied",
        rules_fired=overlay_failures,
        data={"pre_overlay": pre_decision, "post_overlay": current_decision},
    ))

    # Step 5b: Concentration Limits
    concentration_alerts = _check_concentration_limits(
        strategy.concentration_limits, rule_input, portfolio_data,
    )
    if concentration_alerts and current_decision == "approve":
        current_decision = "refer"
        steps.append(EvaluationStep(
            step_name="Concentration Check",
            step_number=5,
            outcome="refer",
            details="Concentration limit would be breached",
            data={"alerts": concentration_alerts},
        ))

    result.outcome = current_decision
    if current_decision in ("decline", "refer"):
        result.reasons = (
            [f["message"] for f in overlay_downgrades]
            + concentration_alerts
        )
        result.reason_codes = [f.get("reason_code", f["rule_id"]) for f in overlay_downgrades]
        if overlay_upgrades:
            result.recommendation = "Upgraded by overlay: " + "; ".join(
                f["message"] for f in overlay_upgrades
            )
        return result

    # Step 6: Terms Assignment
    terms = _assign_terms(strategy, rule_input, score, routing_params)
    result.terms = terms
    result.suggested_rate = terms.interest_rate
    result.suggested_amount = terms.approved_amount

    steps.append(EvaluationStep(
        step_name="Terms Assignment",
        step_number=6,
        outcome="approve",
        details=f"Amount: {terms.approved_amount}, Rate: {terms.interest_rate}, Conditions: {len(terms.conditions)}",
        data={
            "amount": terms.approved_amount,
            "rate": terms.interest_rate,
            "tier": terms.pricing_tier,
            "down_payment": terms.down_payment_pct,
            "conditions": terms.conditions,
        },
    ))

    # Step 7: Final output
    if terms.conditions:
        result.outcome_detail = "approved_with_conditions"
    elif terms.approved_amount and terms.approved_amount < rule_input.loan_amount_requested:
        result.outcome_detail = "approved_reduced"
    else:
        result.outcome_detail = "approved_standard"

    result.outcome = "approve"
    result.reasons = ["All criteria met"]
    _apply_routing_params(result, routing_params, rule_input)

    return result


# ── Scoring mode ───────────────────────────────────────────────────

def _execute_scoring(
    strategy: DecisionStrategy,
    rule_input: RuleInput,
    routing_params: dict | None,
) -> StrategyResult:
    """Points-based evaluation: all rules contribute weighted points."""
    steps: list[EvaluationStep] = []
    all_rules = (strategy.knock_out_rules or []) + (strategy.overlay_rules or [])

    total_points = 0.0
    rule_scores: list[dict] = []

    for rule in all_rules:
        weight = float(rule.get("weight", 1.0))
        field_name = rule.get("field", "")
        operator = rule.get("operator", "gte")
        threshold = rule.get("threshold")
        value = _get_field_value(rule_input, field_name)

        if value is None or threshold is None:
            rule_scores.append({
                "rule_id": rule.get("rule_id", ""),
                "name": rule.get("name", ""),
                "points": 0,
                "reason": "skipped (no data)",
            })
            continue

        passed = _compare(value, operator, threshold)
        points = weight if passed else -weight
        total_points += points
        rule_scores.append({
            "rule_id": rule.get("rule_id", ""),
            "name": rule.get("name", ""),
            "points": points,
            "passed": passed,
            "value": str(value),
        })

    cutoffs = strategy.score_cutoffs or {"approve": 5, "refer": 0, "decline": -5}
    approve_threshold = float(cutoffs.get("approve", 5))
    decline_threshold = float(cutoffs.get("decline", -5))

    if total_points >= approve_threshold:
        outcome = "approve"
    elif total_points <= decline_threshold:
        outcome = "decline"
    else:
        outcome = "refer"

    steps.append(EvaluationStep(
        step_name="Points-Based Scoring",
        step_number=1,
        outcome=outcome,
        details=f"Total points: {total_points:.1f} (approve >= {approve_threshold}, decline <= {decline_threshold})",
        rules_fired=rule_scores,
        data={"total_points": total_points},
    ))

    result = StrategyResult(
        outcome=outcome,
        reasons=[f"Total score: {total_points:.1f}"],
        evaluation_steps=steps,
    )
    _apply_routing_params(result, routing_params, rule_input)
    return result


# ── Hybrid mode ────────────────────────────────────────────────────

def _execute_hybrid(
    strategy: DecisionStrategy,
    rule_input: RuleInput,
    scorecard_score: float | None,
    routing_params: dict | None,
) -> StrategyResult:
    """Sequential knock-outs, then scoring for the remainder."""
    steps: list[EvaluationStep] = []

    # Phase 1: Knock-outs (hard rules)
    knock_outs = strategy.knock_out_rules or []
    ko_failures = _evaluate_rule_set(knock_outs, rule_input, "hard")

    steps.append(EvaluationStep(
        step_name="Knock-Out Rules",
        step_number=1,
        outcome="decline" if ko_failures else "pass",
        details=f"{len(ko_failures)} knock-out failures" if ko_failures else "All knock-outs passed",
        rules_fired=ko_failures,
    ))

    if ko_failures:
        return StrategyResult(
            outcome="decline",
            reasons=[f["message"] for f in ko_failures],
            reason_codes=[f.get("reason_code", f["rule_id"]) for f in ko_failures],
            evaluation_steps=steps,
        )

    # Phase 2: Scoring
    overlay_rules = strategy.overlay_rules or []
    total_points = 0.0
    rule_scores: list[dict] = []

    for rule in overlay_rules:
        weight = float(rule.get("weight", 1.0))
        field_name = rule.get("field", "")
        operator = rule.get("operator", "gte")
        threshold = rule.get("threshold")
        value = _get_field_value(rule_input, field_name)

        if value is None or threshold is None:
            continue
        passed = _compare(value, operator, threshold)
        points = weight if passed else -weight
        total_points += points
        rule_scores.append({
            "rule_id": rule.get("rule_id", ""),
            "name": rule.get("name", ""),
            "points": points,
            "passed": passed,
        })

    if scorecard_score is not None:
        total_points += scorecard_score / 100.0

    cutoffs = strategy.score_cutoffs or {"approve": 5, "refer": 0, "decline": -5}
    approve_threshold = float(cutoffs.get("approve", 5))
    decline_threshold = float(cutoffs.get("decline", -5))

    if total_points >= approve_threshold:
        outcome = "approve"
    elif total_points <= decline_threshold:
        outcome = "decline"
    else:
        outcome = "refer"

    steps.append(EvaluationStep(
        step_name="Weighted Scoring",
        step_number=2,
        outcome=outcome,
        details=f"Total: {total_points:.1f} (approve >= {approve_threshold}, decline <= {decline_threshold})",
        rules_fired=rule_scores,
        data={"total_points": total_points, "scorecard_score": scorecard_score},
    ))

    result = StrategyResult(
        outcome=outcome,
        reasons=[f"Hybrid score: {total_points:.1f}"],
        evaluation_steps=steps,
        scorecard_score=scorecard_score,
    )
    _apply_routing_params(result, routing_params, rule_input)
    return result


# ── Helper functions ───────────────────────────────────────────────

def _evaluate_rule_set(
    rules: list[dict],
    rule_input: RuleInput,
    default_severity: str,
) -> list[dict]:
    """Evaluate a list of rule definitions against the input. Returns failures."""
    failures = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        field_name = rule.get("field", "")
        operator = rule.get("operator", "gte")
        threshold = rule.get("threshold")
        value = _get_field_value(rule_input, field_name)

        if value is None:
            if rule.get("fail_on_null", False):
                failures.append({
                    "rule_id": rule.get("rule_id", ""),
                    "name": rule.get("name", ""),
                    "message": f"{field_name} not available",
                    "severity": rule.get("severity", default_severity),
                    "reason_code": rule.get("reason_code", rule.get("rule_id", "")),
                    "action": rule.get("action", "restrict"),
                })
            continue

        if threshold is None:
            continue

        matched = _compare(value, operator, threshold)

        trigger_mode = rule.get("trigger_mode", False)
        failed = matched if trigger_mode else not matched

        if failed:
            if trigger_mode:
                msg = rule.get("message", f"{field_name} ({value}) matched {operator} {threshold} — rule triggered")
            else:
                msg = rule.get("message", f"{field_name} ({value}) fails {operator} {threshold}")
            failures.append({
                "rule_id": rule.get("rule_id", ""),
                "name": rule.get("name", ""),
                "message": msg,
                "severity": rule.get("severity", default_severity),
                "reason_code": rule.get("reason_code", rule.get("rule_id", "")),
                "value": value,
                "threshold": threshold,
                "action": rule.get("action", "restrict"),
            })

    return failures


def _check_data_sufficiency(
    rule_input: RuleInput,
    scorecard_score: float | None,
) -> list[str]:
    """Check if there is enough data for an automated decision."""
    issues = []
    if rule_input.monthly_income <= 0:
        issues.append("Income data missing or zero")
    if rule_input.credit_score <= 0 and scorecard_score is None:
        issues.append("No credit score or scorecard score available")
    return issues


def _check_concentration_limits(
    limits: list[dict] | None,
    rule_input: RuleInput,
    portfolio_data: dict | None,
) -> list[str]:
    """Check portfolio concentration limits."""
    if not limits or not portfolio_data:
        return []

    alerts = []
    for limit in limits:
        dimension = limit.get("dimension", "")
        max_exposure = float(limit.get("limit", float("inf")))
        current = float(portfolio_data.get(f"current_{dimension}_exposure", 0))
        proposed = float(rule_input.loan_amount_requested)

        if current + proposed > max_exposure:
            alerts.append(
                f"Concentration limit for {dimension}: current {current:,.0f} + "
                f"proposed {proposed:,.0f} = {current + proposed:,.0f} exceeds limit {max_exposure:,.0f}"
            )

    return alerts


def _assign_terms(
    strategy: DecisionStrategy,
    rule_input: RuleInput,
    score: float | None,
    routing_params: dict | None,
) -> TermsAssignment:
    """Assign loan terms based on risk tier and strategy configuration."""
    terms = TermsAssignment()
    terms.approved_amount = rule_input.loan_amount_requested

    matrix = strategy.terms_matrix or {}
    score_bands = matrix.get("score_bands", [])

    if score is not None and score_bands:
        for band in score_bands:
            band_min = float(band.get("min", 0))
            band_max = float(band.get("max", float("inf")))
            if band_min <= score < band_max:
                terms.interest_rate = band.get("rate")
                terms.pricing_tier = band.get("tier")
                terms.down_payment_pct = band.get("down_payment_pct")
                terms.max_tenure_months = band.get("max_tenure")
                break

    if routing_params:
        max_amount = routing_params.get("max_approval_amount")
        if max_amount is not None and terms.approved_amount > float(max_amount):
            terms.approved_amount = float(max_amount)

        if routing_params.get("min_down_payment_pct") is not None:
            terms.down_payment_pct = float(routing_params["min_down_payment_pct"])

        if routing_params.get("pricing_tier") is not None:
            terms.pricing_tier = routing_params["pricing_tier"]

    # Conditions from strategy
    conditions = matrix.get("conditions", [])
    for cond in conditions:
        trigger_field = cond.get("trigger_field")
        trigger_op = cond.get("trigger_operator", "gte")
        trigger_val = cond.get("trigger_value")
        if trigger_field:
            val = _get_field_value(rule_input, trigger_field)
            if val is not None and trigger_val is not None:
                if not _compare(val, trigger_op, trigger_val):
                    terms.conditions.append(cond.get("description", "Condition required"))
                    terms.condition_codes.append(cond.get("code", "CONDITION"))

    return terms


def _apply_routing_params(
    result: StrategyResult,
    routing_params: dict | None,
    rule_input: RuleInput,
) -> None:
    """Apply routing parameter overrides from the tree terminal node."""
    if not routing_params:
        return

    max_amount = routing_params.get("max_approval_amount")
    if max_amount is not None and result.suggested_amount is not None:
        if result.suggested_amount > float(max_amount):
            result.suggested_amount = float(max_amount)

    if routing_params.get("auto_approve_allowed") is False and result.outcome == "approve":
        result.outcome = "refer"
        result.reasons.append("Auto-approval not permitted for this segment")
        result.reason_codes.append("AUTO_APPROVE_BLOCKED")


def _map_outcome(engine_outcome: str) -> str:
    """Map existing engine outcome strings to strategy outcome strings."""
    mapping = {
        "auto_approve": "approve",
        "auto_decline": "decline",
        "manual_review": "refer",
    }
    return mapping.get(engine_outcome, engine_outcome)


# ── Assessment execution ───────────────────────────────────────────

def execute_assessment(
    assessment_rules: list[dict],
    rule_input: RuleInput,
    score_cutoffs: dict | None = None,
) -> StrategyResult:
    """Execute an Assessment's rules against the input data.

    Assessment rules use TRIGGER mode: the rule fires (causes decline/refer)
    when the condition IS true. E.g. "job_title eq janitor" means
    "decline when job_title is janitor".

    This is opposite to the legacy requirement mode where rules define what
    must be true to pass.
    """
    steps: list[EvaluationStep] = []

    trigger_rules = [
        {**r, "trigger_mode": True}
        for r in assessment_rules
        if r.get("enabled", True)
    ]
    hard_rules = [r for r in trigger_rules if r.get("severity") == "hard"]
    refer_rules = [r for r in trigger_rules if r.get("severity") != "hard"]

    hard_failures = _evaluate_rule_set(hard_rules, rule_input, "hard")
    steps.append(EvaluationStep(
        step_name="Hard Rules (Knock-Outs)",
        step_number=1,
        outcome="decline" if hard_failures else "pass",
        details=f"Evaluated {len(hard_rules)} hard rules, {len(hard_failures)} failed",
        rules_fired=hard_failures,
    ))

    if hard_failures:
        return StrategyResult(
            outcome="decline",
            reasons=[f["message"] for f in hard_failures],
            reason_codes=[f.get("reason_code", f["rule_id"]) for f in hard_failures],
            evaluation_steps=steps,
        )

    refer_failures = _evaluate_rule_set(refer_rules, rule_input, "refer")
    steps.append(EvaluationStep(
        step_name="Refer Rules (Policy Overlays)",
        step_number=2,
        outcome="refer" if refer_failures else "pass",
        details=f"Evaluated {len(refer_rules)} refer rules, {len(refer_failures)} failed",
        rules_fired=refer_failures,
    ))

    if refer_failures:
        return StrategyResult(
            outcome="refer",
            reasons=[f["message"] for f in refer_failures],
            reason_codes=[f.get("reason_code", f["rule_id"]) for f in refer_failures],
            evaluation_steps=steps,
        )

    return StrategyResult(
        outcome="approve",
        reasons=["All assessment rules passed"],
        evaluation_steps=steps,
    )
