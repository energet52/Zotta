"""Decision Engine Orchestrator.

Coordinates the scoring and rules evaluation for a loan application,
pulling credit bureau data and producing a final Decision record.

Supports two paths:
  - TREE PATH: when a product has a decision_tree_id, the application is
    routed through the tree and evaluated by the assigned strategy.
  - LEGACY PATH: when no tree is configured, the existing single-strategy
    evaluation runs exactly as before.
"""

from datetime import date, datetime
from typing import Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.decision import Decision, DecisionOutcome, DecisionRulesConfig
from app.models.credit_report import CreditReport
from app.models.audit import AuditLog
from app.models.strategy import (
    DecisionStrategy, DecisionTree, DecisionTreeNode,
    Assessment,
    DecisionAuditTrail, TreeStatus, StrategyStatus,
)
from app.services.decision_engine.scoring import ScoringInput, calculate_score
from app.services.decision_engine.rules import RuleInput, evaluate_rules, DEFAULT_RULES
from app.services.decision_engine.tree_router import (
    build_routing_context, route_application as tree_route,
)
from app.services.decision_engine.strategy_executor import (
    execute_strategy as exec_strategy,
    execute_assessment as exec_assessment,
)
from app.services.credit_bureau.adapter import get_credit_bureau
from app.services.scorecard_engine import (
    score_all_models, extract_applicant_data, get_active_scorecards,
)

logger = logging.getLogger(__name__)


async def run_decision_engine(
    application_id: int,
    db: AsyncSession,
) -> Decision:
    """Run the full decision engine pipeline for a loan application.

    Steps:
    1. Load application and profile data
    2. Pull credit bureau report
    3. Run credit scoring
    4. Evaluate business rules
    5. Create and save Decision record
    6. Update application status
    """
    # 1. Load application (with credit product for rate)
    result = await db.execute(
        select(LoanApplication)
        .where(LoanApplication.id == application_id)
        .options(
            selectinload(LoanApplication.credit_product),
            selectinload(LoanApplication.merchant),
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise ValueError(f"Application {application_id} not found")

    # Load applicant profile
    profile_result = await db.execute(
        select(ApplicantProfile).where(ApplicantProfile.user_id == application.applicant_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise ValueError("Applicant profile not found")

    # 2. Pull credit bureau report
    bureau = get_credit_bureau()
    national_id = profile.national_id or ""
    bureau_data = await bureau.pull_credit_report(national_id)

    # Save credit report
    credit_report = CreditReport(
        loan_application_id=application_id,
        provider=bureau.provider_name,
        national_id=national_id,
        bureau_score=bureau_data.get("score"),
        report_data=bureau_data,
        tradelines=bureau_data.get("tradelines"),
        inquiries=bureau_data.get("inquiries"),
        public_records=bureau_data.get("public_records"),
        status="success",
    )
    db.add(credit_report)

    # Update status
    application.status = LoanStatus.CREDIT_CHECK

    # 3. Run credit scoring
    # Calculate applicant age
    age = 30  # default
    if profile.date_of_birth:
        today = date.today()
        age = today.year - profile.date_of_birth.year - (
            (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
        )

    scoring_input = ScoringInput(
        bureau_score=bureau_data.get("score"),
        payment_history_score=bureau_data.get("payment_history_score", 0.5),
        outstanding_debt=bureau_data.get("total_outstanding_debt", 0),
        num_inquiries=bureau_data.get("num_inquiries", 0),
        credit_history_years=bureau_data.get("credit_history_years", 0),
        monthly_income=float(profile.monthly_income or 0),
        monthly_expenses=float(profile.monthly_expenses or 0),
        existing_debt=float(profile.existing_debt or 0),
        loan_amount_requested=float(application.amount_requested),
        years_employed=profile.years_employed or 0,
        employment_type=profile.employment_type or "employed",
    )

    scoring_result = calculate_score(scoring_input)

    # 4. Evaluate business rules
    # Load active rules from DB or use defaults
    rules_result_db = await db.execute(
        select(DecisionRulesConfig)
        .where(DecisionRulesConfig.is_active == True)
        .order_by(DecisionRulesConfig.version.desc())
    )
    active_rules = rules_result_db.scalars().first()
    rules_config = (active_rules.rules if active_rules and active_rules.rules else DEFAULT_RULES)
    rules_version = active_rules.version if active_rules else 1

    # Check bureau data for active judgments / problematic debt
    has_court_judgment = False
    has_active_debt = False
    public_records = bureau_data.get("public_records", [])
    for rec in public_records:
        if rec.get("type") == "Judgment" and rec.get("status") == "active":
            has_court_judgment = True
        if rec.get("status") == "active":
            has_active_debt = True

    # Check for duplicate applications within 30 days
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    dup_result = await db.execute(
        select(func.count(LoanApplication.id)).where(
            LoanApplication.applicant_id == application.applicant_id,
            LoanApplication.id != application_id,
            LoanApplication.created_at >= thirty_days_ago,
        )
    )
    has_duplicate = (dup_result.scalar() or 0) > 0

    # ── Scorecard parallel scoring (champion-challenger) ──
    # Run BEFORE rules so scorecard score is available to R21
    scorecard_score_for_rules = None
    scorecard_results = []
    try:
        applicant_data = extract_applicant_data(profile, application, {
            "bureau_score": bureau_data.get("score"),
        })
        scorecard_results = await score_all_models(application_id, applicant_data, db)
        if scorecard_results:
            for sr in scorecard_results:
                if sr.is_decisioning:
                    scorecard_score_for_rules = sr.total_score
                    break
    except Exception as e:
        logger.warning("Scorecard parallel scoring failed: %s", e)

    rule_input = RuleInput(
        credit_score=scoring_result.total_score,
        risk_band=scoring_result.risk_band,
        debt_to_income_ratio=scoring_result.debt_to_income_ratio,
        loan_to_income_ratio=scoring_result.loan_to_income_ratio,
        loan_amount_requested=float(application.amount_requested),
        monthly_income=float(profile.monthly_income or 0),
        applicant_age=age,
        years_employed=float(profile.years_employed or 0),
        national_id=national_id,
        is_id_verified=profile.id_verified or False,
        monthly_expenses=float(profile.monthly_expenses or 0),
        job_title=profile.job_title or "",
        employment_type=profile.employment_type or "",
        term_months=application.term_months,
        has_active_debt_bureau=has_active_debt,
        has_court_judgment=has_court_judgment,
        has_duplicate_within_30_days=has_duplicate,
        scorecard_score=scorecard_score_for_rules,
    )

    # ── Routing: tree path vs. legacy path ─────────────────────────
    product = application.credit_product
    has_tree = product and getattr(product, "decision_tree_id", None)

    if has_tree:
        decision = await _run_tree_path(
            application=application,
            profile=profile,
            bureau_data=bureau_data,
            scoring_result=scoring_result,
            rule_input=rule_input,
            scorecard_score_for_rules=scorecard_score_for_rules,
            scorecard_results=scorecard_results,
            rules_config=rules_config,
            rules_version=rules_version,
            db=db,
        )
    else:
        # ── LEGACY PATH: unchanged single-strategy behavior ────────
        decision = await _run_legacy_path(
            application=application,
            scoring_result=scoring_result,
            rule_input=rule_input,
            rules_config=rules_config,
            rules_version=rules_version,
            scorecard_results=scorecard_results,
            db=db,
        )

    # Audit log (common to both paths)
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="decision_engine_run",
        new_values={
            "score": scoring_result.total_score,
            "risk_band": scoring_result.risk_band,
            "outcome": decision.final_outcome,
            "tree_routed": bool(has_tree),
        },
    )
    db.add(audit)

    await db.flush()
    await db.refresh(decision)
    return decision


async def _run_legacy_path(
    application,
    scoring_result,
    rule_input: RuleInput,
    rules_config: dict,
    rules_version: int,
    scorecard_results: list,
    db: AsyncSession,
) -> Decision:
    """The existing single-strategy evaluation — preserved verbatim."""
    rules_output = evaluate_rules(rule_input, rules_config)

    outcome_map = {
        "auto_approve": DecisionOutcome.AUTO_APPROVE,
        "auto_decline": DecisionOutcome.AUTO_DECLINE,
        "manual_review": DecisionOutcome.MANUAL_REVIEW,
    }

    decision = Decision(
        loan_application_id=application.id,
        credit_score=scoring_result.total_score,
        risk_band=scoring_result.risk_band,
        engine_outcome=outcome_map[rules_output.outcome],
        engine_reasons={
            "reasons": rules_output.reasons,
            "dti_ratio": scoring_result.debt_to_income_ratio,
            "lti_ratio": scoring_result.loan_to_income_ratio,
        },
        scoring_breakdown=scoring_result.breakdown,
        rules_results={
            "rules": [
                {"id": r.rule_id, "name": r.rule_name, "passed": r.passed, "message": r.message, "severity": r.severity}
                for r in rules_output.results
            ],
            "income_benchmark": rules_output.income_benchmark,
            "expense_benchmark": rules_output.expense_benchmark,
        },
        suggested_rate=rules_output.suggested_rate,
        suggested_amount=rules_output.max_eligible_amount,
        final_outcome=rules_output.outcome,
        rules_version=rules_version,
    )
    db.add(decision)

    if rules_output.outcome == "auto_approve":
        application.status = LoanStatus.APPROVED
        cp = application.credit_product
        if cp and cp.interest_rate is not None:
            application.interest_rate = float(cp.interest_rate)
        elif rules_output.suggested_rate is not None:
            application.interest_rate = rules_output.suggested_rate
        application.amount_approved = float(application.amount_requested)
        effective_rate = float(application.interest_rate) if application.interest_rate else None
        if effective_rate and application.term_months:
            r = effective_rate / 100 / 12
            n = application.term_months
            pmt = float(application.amount_requested) * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
            application.monthly_payment = round(pmt, 2)
        application.decided_at = datetime.utcnow()
    elif rules_output.outcome == "auto_decline":
        application.status = LoanStatus.DECLINED
        application.decided_at = datetime.utcnow()
    else:
        application.status = LoanStatus.DECISION_PENDING

    if scorecard_results:
        for sr in scorecard_results:
            if sr.is_decisioning:
                decision.scoring_breakdown = decision.scoring_breakdown or {}
                decision.scoring_breakdown["scorecard_score"] = sr.total_score
                decision.scoring_breakdown["scorecard_name"] = sr.scorecard_name
                decision.scoring_breakdown["scorecard_decision"] = sr.decision
                break

    return decision


async def _run_tree_path(
    application,
    profile,
    bureau_data: dict,
    scoring_result,
    rule_input: RuleInput,
    scorecard_score_for_rules: float | None,
    scorecard_results: list,
    rules_config: dict,
    rules_version: int,
    db: AsyncSession,
) -> Decision:
    """Route through the decision tree and execute the assigned strategy."""
    product = application.credit_product

    tree_result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == product.decision_tree_id)
        .options(selectinload(DecisionTree.nodes))
    )
    tree = tree_result.scalar_one_or_none()

    if tree is None:
        logger.warning(
            "Product %s has decision_tree_id=%s but tree not found; falling back to legacy",
            product.id, product.decision_tree_id,
        )
        return await _run_legacy_path(
            application, scoring_result, rule_input,
            rules_config, rules_version, scorecard_results, db,
        )

    # Build routing context
    routing_context = build_routing_context(application, profile, bureau_data)

    # Route through tree
    default_strategy_id = tree.default_strategy_id or getattr(product, "default_strategy_id", None)
    try:
        routing_result = tree_route(routing_context, tree.nodes, default_strategy_id)
    except ValueError as e:
        logger.error("Tree routing failed for app %s: %s", application.id, e)
        return await _run_legacy_path(
            application, scoring_result, rule_input,
            rules_config, rules_version, scorecard_results, db,
        )

    # Check if terminal node is an assessment or a strategy
    if routing_result.assessment_id:
        assessment_result = await db.execute(
            select(Assessment).where(Assessment.id == routing_result.assessment_id)
        )
        assessment_obj = assessment_result.scalar_one_or_none()
        if assessment_obj is None:
            logger.error("Assessment %s not found; falling back to legacy", routing_result.assessment_id)
            return await _run_legacy_path(
                application, scoring_result, rule_input,
                rules_config, rules_version, scorecard_results, db,
            )
        strat_result = exec_assessment(
            assessment_rules=assessment_obj.rules or [],
            rule_input=rule_input,
            score_cutoffs=assessment_obj.score_cutoffs,
        )
        strategy = None
    else:
        # Load the assigned strategy
        strategy_result = await db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == routing_result.strategy_id)
        )
        strategy = strategy_result.scalar_one_or_none()

        if strategy is None:
            logger.error("Strategy %s not found; falling back to legacy", routing_result.strategy_id)
            return await _run_legacy_path(
                application, scoring_result, rule_input,
                rules_config, rules_version, scorecard_results, db,
            )

        strat_result = exec_strategy(
            strategy=strategy,
            rule_input=rule_input,
            rules_config=rules_config,
            routing_params=routing_result.strategy_params,
            scorecard_score=scorecard_score_for_rules,
        )

    # Map strategy outcome to Decision
    outcome_map = {
        "approve": DecisionOutcome.AUTO_APPROVE,
        "decline": DecisionOutcome.AUTO_DECLINE,
        "refer": DecisionOutcome.MANUAL_REVIEW,
    }
    engine_outcome = outcome_map.get(strat_result.outcome, DecisionOutcome.MANUAL_REVIEW)

    # Build rules_results from strategy evaluation steps
    step_rules = []
    for step in strat_result.evaluation_steps:
        step_data = step.data or {}
        all_rules_in_step = step_data.get("all_rules", [])
        if all_rules_in_step:
            step_rules.extend(all_rules_in_step)
        else:
            for rf in step.rules_fired:
                step_rules.append(rf)

    decision = Decision(
        loan_application_id=application.id,
        credit_score=scoring_result.total_score,
        risk_band=scoring_result.risk_band,
        engine_outcome=engine_outcome,
        engine_reasons={
            "reasons": strat_result.reasons,
            "reason_codes": strat_result.reason_codes,
            "dti_ratio": scoring_result.debt_to_income_ratio,
            "lti_ratio": scoring_result.loan_to_income_ratio,
        },
        scoring_breakdown=scoring_result.breakdown,
        rules_results={
            "rules": step_rules,
            "evaluation_steps": [
                {
                    "step": s.step_name,
                    "number": s.step_number,
                    "outcome": s.outcome,
                    "details": s.details,
                }
                for s in strat_result.evaluation_steps
            ],
        },
        suggested_rate=strat_result.suggested_rate,
        suggested_amount=strat_result.suggested_amount,
        final_outcome=strat_result.outcome,
        rules_version=rules_version,
        strategy_id=strategy.id if strategy else None,
        tree_version=tree.version,
        routing_path={
            "tree_id": tree.id,
            "tree_name": tree.name,
            "path": [
                {
                    "node_key": step.node_key,
                    "label": step.node_label,
                    "attribute": step.attribute,
                    "value": _serialize_value(step.actual_value),
                    "branch": step.branch_taken,
                    "type": step.node_type,
                }
                for step in routing_result.path
            ],
            "strategy_id": strategy.id if strategy else None,
            "strategy_name": strategy.name if strategy else None,
            "assessment_id": routing_result.assessment_id,
            "used_default": routing_result.used_default,
        },
    )
    db.add(decision)

    # Update application status
    if strat_result.outcome == "approve":
        application.status = LoanStatus.APPROVED
        cp = application.credit_product
        if strat_result.suggested_rate is not None:
            application.interest_rate = strat_result.suggested_rate
        elif cp and cp.interest_rate is not None:
            application.interest_rate = float(cp.interest_rate)

        approved_amount = strat_result.suggested_amount or float(application.amount_requested)
        application.amount_approved = approved_amount

        effective_rate = float(application.interest_rate) if application.interest_rate else None
        if effective_rate and application.term_months:
            r = effective_rate / 100 / 12
            n = application.term_months
            pmt = approved_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
            application.monthly_payment = round(pmt, 2)
        application.decided_at = datetime.utcnow()
    elif strat_result.outcome == "decline":
        application.status = LoanStatus.DECLINED
        application.decided_at = datetime.utcnow()
    else:
        application.status = LoanStatus.DECISION_PENDING

    # Store scorecard scores
    if scorecard_results:
        for sr in scorecard_results:
            if sr.is_decisioning:
                decision.scoring_breakdown = decision.scoring_breakdown or {}
                decision.scoring_breakdown["scorecard_score"] = sr.total_score
                decision.scoring_breakdown["scorecard_name"] = sr.scorecard_name
                decision.scoring_breakdown["scorecard_decision"] = sr.decision
                break

    # Create detailed audit trail
    await db.flush()
    audit_trail = DecisionAuditTrail(
        decision_id=decision.id,
        tree_id=tree.id,
        tree_version=tree.version,
        routing_path=[
            {
                "node_key": step.node_key,
                "label": step.node_label,
                "attribute": step.attribute,
                "value": _serialize_value(step.actual_value),
                "branch": step.branch_taken,
            }
            for step in routing_result.path
        ],
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        strategy_params_applied=routing_result.strategy_params,
        scorecard_score=scorecard_score_for_rules,
        rule_evaluations=step_rules,
        evaluation_steps=[
            {
                "step": s.step_name,
                "number": s.step_number,
                "outcome": s.outcome,
                "details": s.details,
                "data": s.data,
            }
            for s in strat_result.evaluation_steps
        ],
    )
    db.add(audit_trail)

    return decision


def _serialize_value(value) -> str | None:
    """Safely serialize a routing value for JSON storage."""
    if value is None:
        return None
    if isinstance(value, dict):
        return str(value)
    return str(value)
