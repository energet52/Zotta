"""Decision Engine Orchestrator.

Coordinates the scoring and rules evaluation for a loan application,
pulling credit bureau data and producing a final Decision record.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.decision import Decision, DecisionOutcome, DecisionRulesConfig
from app.models.credit_report import CreditReport
from app.models.audit import AuditLog
from app.services.decision_engine.scoring import ScoringInput, calculate_score
from app.services.decision_engine.rules import RuleInput, evaluate_rules, DEFAULT_RULES
from app.services.credit_bureau.adapter import get_credit_bureau


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
    # 1. Load application
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
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
    rules_config = {"rules": active_rules.rules} if active_rules else DEFAULT_RULES
    rules_version = active_rules.version if active_rules else 1

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
    )

    rules_output = evaluate_rules(rule_input, rules_config)

    # 5. Create Decision record
    outcome_map = {
        "auto_approve": DecisionOutcome.AUTO_APPROVE,
        "auto_decline": DecisionOutcome.AUTO_DECLINE,
        "manual_review": DecisionOutcome.MANUAL_REVIEW,
    }

    decision = Decision(
        loan_application_id=application_id,
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
                {"name": r.rule_name, "passed": r.passed, "message": r.message, "severity": r.severity}
                for r in rules_output.results
            ]
        },
        suggested_rate=rules_output.suggested_rate,
        suggested_amount=rules_output.max_eligible_amount,
        final_outcome=rules_output.outcome,
        rules_version=rules_version,
    )
    db.add(decision)

    # 6. Update application status based on outcome
    if rules_output.outcome == "auto_approve":
        application.status = LoanStatus.APPROVED
        application.interest_rate = rules_output.suggested_rate
        application.amount_approved = float(application.amount_requested)
        # Calculate monthly payment (simple amortization)
        if rules_output.suggested_rate and application.term_months:
            r = rules_output.suggested_rate / 100 / 12
            n = application.term_months
            pmt = float(application.amount_requested) * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
            application.monthly_payment = round(pmt, 2)
        application.decided_at = datetime.utcnow()
    elif rules_output.outcome == "auto_decline":
        application.status = LoanStatus.DECLINED
        application.decided_at = datetime.utcnow()
    else:
        application.status = LoanStatus.DECISION_PENDING

    # Audit log
    audit = AuditLog(
        entity_type="loan_application",
        entity_id=application_id,
        action="decision_engine_run",
        new_values={
            "score": scoring_result.total_score,
            "risk_band": scoring_result.risk_band,
            "outcome": rules_output.outcome,
        },
    )
    db.add(audit)

    await db.flush()
    await db.refresh(decision)
    return decision
