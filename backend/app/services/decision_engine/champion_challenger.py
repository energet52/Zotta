"""Champion-Challenger Engine — manages parallel strategy testing.

The champion always makes the real decision.  Challengers evaluate silently
and record what they would have decided, building an evidence base for
promotion decisions.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy import (
    ChampionChallengerTest,
    ChallengerTestStatus,
    DecisionStrategy,
    DecisionAuditTrail,
)
from app.services.decision_engine.rules import RuleInput
from app.services.decision_engine.strategy_executor import (
    execute_strategy,
    StrategyResult,
)


async def get_active_challengers(
    strategy_id: int,
    db: AsyncSession,
) -> list[ChampionChallengerTest]:
    """Get all active challenger tests for a champion strategy."""
    result = await db.execute(
        select(ChampionChallengerTest).where(
            ChampionChallengerTest.champion_strategy_id == strategy_id,
            ChampionChallengerTest.status == ChallengerTestStatus.ACTIVE,
        )
    )
    return list(result.scalars().all())


async def run_challenger_evaluation(
    champion_result: StrategyResult,
    rule_input: RuleInput,
    rules_config: dict | None,
    scorecard_score: float | None,
    challengers: list[ChampionChallengerTest],
    db: AsyncSession,
) -> dict:
    """Run challenger strategies silently alongside the champion.

    Returns a dict mapping challenger_test_id → StrategyResult for
    recording in the audit trail.  Never affects the actual decision.
    """
    results: dict[int, dict] = {}

    for test in challengers:
        if not _should_evaluate(test):
            continue

        challenger_strategy = await _load_strategy(test.challenger_strategy_id, db)
        if challenger_strategy is None:
            continue

        challenger_result = execute_strategy(
            strategy=challenger_strategy,
            rule_input=rule_input,
            rules_config=rules_config,
            scorecard_score=scorecard_score,
        )

        agreed = champion_result.outcome == challenger_result.outcome

        test.total_evaluated += 1
        if agreed:
            test.agreement_count += 1
        else:
            test.disagreement_count += 1

        results[test.id] = {
            "test_id": test.id,
            "challenger_strategy_id": test.challenger_strategy_id,
            "challenger_outcome": challenger_result.outcome,
            "champion_outcome": champion_result.outcome,
            "agreed": agreed,
            "challenger_reasons": challenger_result.reasons,
            "challenger_reason_codes": challenger_result.reason_codes,
            "not_applied": True,
        }

    return results


def _should_evaluate(test: ChampionChallengerTest) -> bool:
    """Decide whether this application should be evaluated by the challenger."""
    return random.random() * 100 < test.traffic_pct


async def _load_strategy(
    strategy_id: int,
    db: AsyncSession,
) -> DecisionStrategy | None:
    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    return result.scalar_one_or_none()


async def get_test_comparison(
    test_id: int,
    db: AsyncSession,
) -> dict:
    """Generate a comparison dashboard for a champion-challenger test."""
    result = await db.execute(
        select(ChampionChallengerTest).where(ChampionChallengerTest.id == test_id)
    )
    test = result.scalar_one_or_none()
    if not test:
        return {"error": "Test not found"}

    total = test.total_evaluated or 0
    agreement_rate = (test.agreement_count / total * 100) if total > 0 else 0
    disagreement_rate = (test.disagreement_count / total * 100) if total > 0 else 0

    # Check if we have enough data for reliable conclusions
    now = datetime.now(timezone.utc)
    min_met = total >= test.min_volume

    started = test.started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    duration_met = (
        now - started >= timedelta(days=test.min_duration_days)
    ) if started else False

    days_running = (now - started).days if started else 0

    return {
        "test_id": test.id,
        "champion_strategy_id": test.champion_strategy_id,
        "challenger_strategy_id": test.challenger_strategy_id,
        "status": test.status.value,
        "total_evaluated": total,
        "agreement_count": test.agreement_count,
        "disagreement_count": test.disagreement_count,
        "agreement_rate": round(agreement_rate, 1),
        "disagreement_rate": round(disagreement_rate, 1),
        "traffic_pct": test.traffic_pct,
        "min_volume_met": min_met,
        "min_duration_met": duration_met,
        "ready_for_decision": min_met and duration_met,
        "started_at": test.started_at.isoformat() if test.started_at else None,
        "days_running": days_running,
        "results_detail": test.results,
    }


async def promote_challenger(
    test_id: int,
    db: AsyncSession,
) -> dict:
    """Promote a challenger to champion status.

    Archives the old champion and activates the challenger.
    Creates a new version if needed.
    """
    result = await db.execute(
        select(ChampionChallengerTest).where(ChampionChallengerTest.id == test_id)
    )
    test = result.scalar_one_or_none()
    if not test:
        return {"error": "Test not found"}

    if test.status != ChallengerTestStatus.ACTIVE:
        return {"error": f"Test is {test.status.value}, not active"}

    # Archive the champion
    champ_result = await db.execute(
        select(DecisionStrategy).where(
            DecisionStrategy.id == test.champion_strategy_id,
        )
    )
    champion = champ_result.scalar_one_or_none()
    if champion:
        from app.models.strategy import StrategyStatus
        champion.status = StrategyStatus.ARCHIVED
        champion.archived_at = datetime.now(timezone.utc)

    # Activate the challenger
    challenger_result = await db.execute(
        select(DecisionStrategy).where(
            DecisionStrategy.id == test.challenger_strategy_id,
        )
    )
    challenger = challenger_result.scalar_one_or_none()
    if challenger:
        from app.models.strategy import StrategyStatus
        challenger.status = StrategyStatus.ACTIVE
        challenger.activated_at = datetime.now(timezone.utc)

    # Complete the test
    test.status = ChallengerTestStatus.COMPLETED
    test.completed_at = datetime.now(timezone.utc)

    await db.flush()

    return {
        "promoted": True,
        "new_champion_id": test.challenger_strategy_id,
        "archived_champion_id": test.champion_strategy_id,
    }


async def discard_challenger(
    test_id: int,
    db: AsyncSession,
) -> dict:
    """Discard a challenger test. Champion continues unaffected."""
    result = await db.execute(
        select(ChampionChallengerTest).where(ChampionChallengerTest.id == test_id)
    )
    test = result.scalar_one_or_none()
    if not test:
        return {"error": "Test not found"}

    test.status = ChallengerTestStatus.DISCARDED
    test.completed_at = datetime.now(timezone.utc)

    await db.flush()
    return {"discarded": True, "test_id": test_id}
