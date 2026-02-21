"""Simulation Engine — replay, trace, and impact analysis for decision strategies.

Supports:
  - Historical replay: rerun N applications through a new tree/strategy
  - Single application trace: step-by-step decision walkthrough
  - Impact comparison: old vs. new decision distribution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.loan import LoanApplication, ApplicantProfile
from app.models.decision import Decision
from app.models.strategy import DecisionTree, DecisionStrategy, TreeStatus
from app.services.decision_engine.tree_router import (
    build_routing_context, route_application, RoutingResult, RoutingContext,
)
from app.services.decision_engine.strategy_executor import (
    execute_strategy, StrategyResult,
)
from app.services.decision_engine.rules import (
    RuleInput, evaluate_rules, DEFAULT_RULES,
)
from app.services.decision_engine.scoring import ScoringInput, calculate_score


@dataclass
class ReplayResult:
    total_applications: int = 0
    results: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


@dataclass
class TraceStep:
    step_type: str  # "routing", "strategy_step"
    label: str
    details: str
    data: dict = field(default_factory=dict)


@dataclass
class TraceResult:
    application_id: int | None = None
    steps: list[TraceStep] = field(default_factory=list)
    final_outcome: str = ""
    final_reasons: list[str] = field(default_factory=list)
    routing_path: list[dict] = field(default_factory=list)
    strategy_used: str | None = None


@dataclass
class ImpactAnalysis:
    total_compared: int = 0
    approvals_old: int = 0
    approvals_new: int = 0
    declines_old: int = 0
    declines_new: int = 0
    refers_old: int = 0
    refers_new: int = 0
    newly_approved: int = 0
    newly_declined: int = 0
    changed_decisions: list[dict] = field(default_factory=list)


async def replay_historical(
    tree_id: int | None,
    strategy_id: int | None,
    application_ids: list[int],
    db: AsyncSession,
    rules_config: dict | None = None,
) -> ReplayResult:
    """Replay a list of historical applications through a new tree/strategy.

    Returns what the new tree/strategy would have decided for each application,
    compared to what was actually decided.
    """
    result = ReplayResult(total_applications=len(application_ids))

    tree = None
    tree_nodes = []
    default_strategy_id = None
    if tree_id:
        tree_result = await db.execute(
            select(DecisionTree)
            .where(DecisionTree.id == tree_id)
            .options(selectinload(DecisionTree.nodes))
        )
        tree = tree_result.scalar_one_or_none()
        if tree:
            tree_nodes = tree.nodes
            default_strategy_id = tree.default_strategy_id

    strategy = None
    if strategy_id:
        strat_result = await db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
        )
        strategy = strat_result.scalar_one_or_none()

    outcomes = {"approve": 0, "decline": 0, "refer": 0}
    original_outcomes = {"approve": 0, "decline": 0, "refer": 0}

    for app_id in application_ids:
        app_result = await db.execute(
            select(LoanApplication)
            .where(LoanApplication.id == app_id)
            .options(selectinload(LoanApplication.credit_product))
        )
        application = app_result.scalar_one_or_none()
        if not application:
            continue

        profile_result = await db.execute(
            select(ApplicantProfile).where(
                ApplicantProfile.user_id == application.applicant_id,
            )
        )
        profile = profile_result.scalar_one_or_none()

        # Get original decision
        dec_result = await db.execute(
            select(Decision)
            .where(Decision.loan_application_id == app_id)
            .order_by(Decision.created_at.desc())
        )
        original_decision = dec_result.scalars().first()

        original_outcome = _normalize_outcome(
            original_decision.final_outcome if original_decision else "unknown"
        )
        original_outcomes[original_outcome] = original_outcomes.get(original_outcome, 0) + 1

        # Build input for simulation
        rule_input = _build_rule_input(application, profile)

        new_outcome = "unknown"
        new_reasons: list[str] = []
        routing_info: dict = {}

        if tree and tree_nodes:
            ctx = build_routing_context(application, profile, {})
            try:
                routing = route_application(ctx, tree_nodes, default_strategy_id)
                routing_info = {
                    "strategy_id": routing.strategy_id,
                    "path": [s.node_key for s in routing.path],
                    "used_default": routing.used_default,
                }

                assigned_strategy = strategy
                if routing.strategy_id != (strategy_id or 0):
                    s_res = await db.execute(
                        select(DecisionStrategy).where(
                            DecisionStrategy.id == routing.strategy_id,
                        )
                    )
                    assigned_strategy = s_res.scalar_one_or_none()

                if assigned_strategy:
                    strat_res = execute_strategy(
                        strategy=assigned_strategy,
                        rule_input=rule_input,
                        rules_config=rules_config,
                        routing_params=routing.strategy_params,
                    )
                    new_outcome = strat_res.outcome
                    new_reasons = strat_res.reasons
            except ValueError:
                new_outcome = "error"
        elif strategy:
            strat_res = execute_strategy(
                strategy=strategy,
                rule_input=rule_input,
                rules_config=rules_config,
            )
            new_outcome = strat_res.outcome
            new_reasons = strat_res.reasons
        else:
            rules_out = evaluate_rules(rule_input, rules_config or DEFAULT_RULES)
            new_outcome = _normalize_outcome(rules_out.outcome)
            new_reasons = rules_out.reasons

        outcomes[new_outcome] = outcomes.get(new_outcome, 0) + 1

        result.results.append({
            "application_id": app_id,
            "original_outcome": original_outcome,
            "new_outcome": new_outcome,
            "changed": original_outcome != new_outcome,
            "new_reasons": new_reasons,
            "routing": routing_info,
        })

    result.summary = {
        "original": original_outcomes,
        "new": outcomes,
        "approval_rate_change": (
            (outcomes.get("approve", 0) - original_outcomes.get("approve", 0))
            / max(len(application_ids), 1) * 100
        ),
        "total_changed": sum(1 for r in result.results if r["changed"]),
    }

    return result


async def trace_application(
    application_id: int,
    tree_id: int | None,
    strategy_id: int | None,
    db: AsyncSession,
    rules_config: dict | None = None,
    overrides: dict | None = None,
) -> TraceResult:
    """Step-by-step trace of a single application through tree + strategy.

    Supports "what-if" via the overrides dict: change any input value
    and rerun instantly.
    """
    trace = TraceResult(application_id=application_id)

    app_result = await db.execute(
        select(LoanApplication)
        .where(LoanApplication.id == application_id)
        .options(selectinload(LoanApplication.credit_product))
    )
    application = app_result.scalar_one_or_none()
    if not application:
        trace.final_outcome = "error"
        trace.final_reasons = ["Application not found"]
        return trace

    profile_result = await db.execute(
        select(ApplicantProfile).where(
            ApplicantProfile.user_id == application.applicant_id,
        )
    )
    profile = profile_result.scalar_one_or_none()

    rule_input = _build_rule_input(application, profile, overrides)

    trace.steps.append(TraceStep(
        step_type="input",
        label="Application Data",
        details=f"App #{application_id}, Amount: {rule_input.loan_amount_requested:,.2f}, "
                f"Income: {rule_input.monthly_income:,.2f}",
        data={
            "credit_score": rule_input.credit_score,
            "risk_band": rule_input.risk_band,
            "dti": round(rule_input.debt_to_income_ratio, 3),
            "age": rule_input.applicant_age,
            "employment_type": rule_input.employment_type,
            "overrides_applied": list(overrides.keys()) if overrides else [],
        },
    ))

    # Tree routing
    if tree_id:
        tree_result = await db.execute(
            select(DecisionTree)
            .where(DecisionTree.id == tree_id)
            .options(selectinload(DecisionTree.nodes))
        )
        tree = tree_result.scalar_one_or_none()

        if tree and tree.nodes:
            ctx = build_routing_context(application, profile, {}, overrides)
            try:
                routing = route_application(ctx, tree.nodes, tree.default_strategy_id)
                for step in routing.path:
                    trace.steps.append(TraceStep(
                        step_type="routing",
                        label=f"Node: {step.node_label or step.node_key}",
                        details=f"Attribute: {step.attribute}, Value: {step.actual_value}, "
                                f"Branch: {step.branch_taken}",
                        data={
                            "node_key": step.node_key,
                            "attribute": step.attribute,
                            "value": str(step.actual_value) if step.actual_value is not None else None,
                            "branch": step.branch_taken,
                        },
                    ))
                trace.routing_path = [
                    {"node": s.node_key, "branch": s.branch_taken}
                    for s in routing.path
                ]

                if routing.strategy_id:
                    strategy_id = routing.strategy_id
            except ValueError as e:
                trace.steps.append(TraceStep(
                    step_type="error",
                    label="Routing Error",
                    details=str(e),
                ))

    # Strategy execution
    if strategy_id:
        strat_result_db = await db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
        )
        strategy = strat_result_db.scalar_one_or_none()
        if strategy:
            trace.strategy_used = strategy.name
            strat_result = execute_strategy(
                strategy=strategy,
                rule_input=rule_input,
                rules_config=rules_config,
            )

            for step in strat_result.evaluation_steps:
                trace.steps.append(TraceStep(
                    step_type="strategy_step",
                    label=f"Step {step.step_number}: {step.step_name}",
                    details=step.details,
                    data={"outcome": step.outcome, **step.data},
                ))

            trace.final_outcome = strat_result.outcome
            trace.final_reasons = strat_result.reasons
        else:
            trace.final_outcome = "error"
            trace.final_reasons = [f"Strategy {strategy_id} not found"]
    else:
        rules_out = evaluate_rules(rule_input, rules_config or DEFAULT_RULES)
        trace.final_outcome = _normalize_outcome(rules_out.outcome)
        trace.final_reasons = rules_out.reasons

        for r in rules_out.results:
            if not r.passed:
                trace.steps.append(TraceStep(
                    step_type="rule",
                    label=f"Rule {r.rule_id}: {r.rule_name}",
                    details=r.message,
                    data={"passed": False, "severity": r.severity},
                ))

    return trace


async def impact_analysis(
    old_tree_id: int | None,
    new_tree_id: int | None,
    old_strategy_id: int | None,
    new_strategy_id: int | None,
    application_ids: list[int],
    db: AsyncSession,
    rules_config: dict | None = None,
) -> ImpactAnalysis:
    """Compare two configurations side by side on the same applications."""
    old_replay = await replay_historical(
        tree_id=old_tree_id,
        strategy_id=old_strategy_id,
        application_ids=application_ids,
        db=db,
        rules_config=rules_config,
    )

    new_replay = await replay_historical(
        tree_id=new_tree_id,
        strategy_id=new_strategy_id,
        application_ids=application_ids,
        db=db,
        rules_config=rules_config,
    )

    analysis = ImpactAnalysis(total_compared=len(application_ids))
    analysis.approvals_old = old_replay.summary.get("new", {}).get("approve", 0)
    analysis.approvals_new = new_replay.summary.get("new", {}).get("approve", 0)
    analysis.declines_old = old_replay.summary.get("new", {}).get("decline", 0)
    analysis.declines_new = new_replay.summary.get("new", {}).get("decline", 0)
    analysis.refers_old = old_replay.summary.get("new", {}).get("refer", 0)
    analysis.refers_new = new_replay.summary.get("new", {}).get("refer", 0)

    old_map = {r["application_id"]: r for r in old_replay.results}
    new_map = {r["application_id"]: r for r in new_replay.results}

    for app_id in application_ids:
        old_r = old_map.get(app_id, {})
        new_r = new_map.get(app_id, {})
        old_out = old_r.get("new_outcome", "unknown")
        new_out = new_r.get("new_outcome", "unknown")

        if old_out != new_out:
            if new_out == "approve" and old_out != "approve":
                analysis.newly_approved += 1
            elif new_out == "decline" and old_out != "decline":
                analysis.newly_declined += 1

            analysis.changed_decisions.append({
                "application_id": app_id,
                "old_outcome": old_out,
                "new_outcome": new_out,
            })

    return analysis


# ── Helpers ────────────────────────────────────────────────────────

def _build_rule_input(
    application,
    profile,
    overrides: dict | None = None,
) -> RuleInput:
    """Build a RuleInput from application data for simulation."""
    from datetime import date

    age = 30
    if profile and profile.date_of_birth:
        today = date.today()
        age = today.year - profile.date_of_birth.year - (
            (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
        )

    monthly_income = float(getattr(profile, "monthly_income", 0) or 0)
    monthly_expenses = float(getattr(profile, "monthly_expenses", 0) or 0)
    existing_debt = float(getattr(profile, "existing_debt", 0) or 0)
    amount_requested = float(getattr(application, "amount_requested", 0) or 0)

    dti = (monthly_expenses + existing_debt) / monthly_income if monthly_income > 0 else 0
    lti = amount_requested / (monthly_income * 12) if monthly_income > 0 else 0

    data = {
        "credit_score": 500,
        "risk_band": "C",
        "debt_to_income_ratio": dti,
        "loan_to_income_ratio": lti,
        "loan_amount_requested": amount_requested,
        "monthly_income": monthly_income,
        "applicant_age": age,
        "years_employed": float(getattr(profile, "years_employed", 0) or 0),
        "national_id": getattr(profile, "national_id", "") or "",
        "is_id_verified": getattr(profile, "id_verified", False) or False,
        "monthly_expenses": monthly_expenses,
        "job_title": getattr(profile, "job_title", "") or "",
        "employment_type": getattr(profile, "employment_type", "") or "",
        "term_months": getattr(application, "term_months", 12) or 12,
    }

    if overrides:
        data.update(overrides)

    return RuleInput(**data)


def _normalize_outcome(outcome: str) -> str:
    mapping = {
        "auto_approve": "approve",
        "auto_decline": "decline",
        "manual_review": "refer",
    }
    return mapping.get(outcome, outcome)
