"""Decision Strategy Management API routes.

Strategies, Decision Trees, Champion-Challenger, Simulation, Explanation.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.strategy import (
    DecisionStrategy, StrategyStatus, EvaluationMode,
    DecisionTree, TreeStatus, DecisionTreeNode, NodeType, ConditionType,
    Assessment,
    ChampionChallengerTest, ChallengerTestStatus,
    DecisionAuditTrail,
)
from app.models.decision import Decision
from app.models.loan import LoanApplication
from app.models.catalog import CreditProduct
from app.schemas import (
    DecisionStrategyCreate, DecisionStrategyUpdate, DecisionStrategyResponse,
    DecisionTreeCreate, DecisionTreeUpdate, DecisionTreeResponse,
    TreeNodeCreate, TreeNodeResponse, TreeValidationResponse, ValidationErrorSchema,
    AssessmentCreate, AssessmentUpdate, AssessmentResponse,
    ChampionChallengerCreate, ChampionChallengerResponse,
    SimulationReplayRequest, SimulationTraceRequest, SimulationImpactRequest,
    DecisionExplanationResponse,
)
from app.services.decision_engine.tree_validator import validate_tree
from app.services.decision_engine.champion_challenger import (
    get_test_comparison, promote_challenger, discard_challenger,
)
from app.services.decision_engine.simulation import (
    replay_historical, trace_application, impact_analysis,
)

router = APIRouter()


async def _reload_strategy(db: AsyncSession, strategy_id: int) -> DecisionStrategy:
    result = await db.execute(
        select(DecisionStrategy)
        .where(DecisionStrategy.id == strategy_id)
        .options(selectinload(DecisionStrategy.assessments))
    )
    return result.scalar_one()


# ── Decision Strategies ────────────────────────────────────────────

@router.get("/strategies", response_model=list[DecisionStrategyResponse])
async def list_strategies(
    status: Optional[str] = None,
    evaluation_mode: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(DecisionStrategy)
        .options(selectinload(DecisionStrategy.assessments))
        .order_by(DecisionStrategy.updated_at.desc())
    )
    if status:
        query = query.where(DecisionStrategy.status == status)
    if evaluation_mode:
        query = query.where(DecisionStrategy.evaluation_mode == evaluation_mode)
    result = await db.execute(query)
    return result.scalars().unique().all()


@router.post("/strategies", response_model=DecisionStrategyResponse, status_code=201)
async def create_strategy(
    data: DecisionStrategyCreate,
    db: AsyncSession = Depends(get_db),
):
    max_ver_result = await db.execute(
        select(func.max(DecisionStrategy.version)).where(
            DecisionStrategy.name == data.name,
        )
    )
    next_version = (max_ver_result.scalar() or 0) + 1

    strategy = DecisionStrategy(
        name=data.name,
        description=data.description,
        evaluation_mode=EvaluationMode(data.evaluation_mode),
        rules_config_id=data.rules_config_id,
        scorecard_id=data.scorecard_id,
        knock_out_rules=data.knock_out_rules,
        overlay_rules=data.overlay_rules,
        score_cutoffs=data.score_cutoffs,
        terms_matrix=data.terms_matrix,
        reason_code_map=data.reason_code_map,
        concentration_limits=data.concentration_limits,
        status=StrategyStatus.DRAFT,
        version=next_version,
    )
    db.add(strategy)
    try:
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(409, f"Strategy '{data.name}' version {next_version} already exists")

    try:
        products_q = await db.execute(select(func.min(CreditProduct.id)))
        default_product_id = products_q.scalar() or 1

        tree_ver_q = await db.execute(
            select(func.max(DecisionTree.version)).where(DecisionTree.product_id == default_product_id)
        )
        tree_version = (tree_ver_q.scalar() or 0) + 1

        tree = DecisionTree(
            product_id=default_product_id,
            name=f"{data.name} - Decision Tree",
            description="Auto-created with strategy",
            version=tree_version,
            status=TreeStatus.DRAFT,
        )
        db.add(tree)
        await db.flush()
        strategy.decision_tree_id = tree.id
        await db.flush()
    except Exception:
        pass

    result = await db.execute(
        select(DecisionStrategy)
        .where(DecisionStrategy.id == strategy.id)
        .options(selectinload(DecisionStrategy.assessments))
    )
    return result.scalar_one()


@router.get("/strategies/{strategy_id}", response_model=DecisionStrategyResponse)
async def get_strategy(strategy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionStrategy)
        .where(DecisionStrategy.id == strategy_id)
        .options(selectinload(DecisionStrategy.assessments))
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    return strategy


@router.put("/strategies/{strategy_id}", response_model=DecisionStrategyResponse)
async def update_strategy(
    strategy_id: int,
    data: DecisionStrategyUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    if strategy.status == StrategyStatus.ARCHIVED:
        raise HTTPException(400, "Archived strategies cannot be edited. Create a new version instead.")

    update_data = data.model_dump(exclude_unset=True)

    # If name is changing, check for conflicts
    new_name = update_data.get("name")
    if new_name and new_name != strategy.name:
        conflict = await db.execute(
            select(DecisionStrategy).where(
                DecisionStrategy.name == new_name,
                DecisionStrategy.version == strategy.version,
                DecisionStrategy.id != strategy_id,
            )
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(
                400,
                f"Strategy name '{new_name}' already exists at version {strategy.version}",
            )

    for field_name, value in update_data.items():
        if field_name == "evaluation_mode" and value:
            setattr(strategy, field_name, EvaluationMode(value))
        else:
            setattr(strategy, field_name, value)

    try:
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(400, "Update failed — possible name/version conflict")
    return await _reload_strategy(db, strategy.id)


@router.post("/strategies/{strategy_id}/activate", response_model=DecisionStrategyResponse)
async def activate_strategy(
    strategy_id: int,
    emergency: bool = False,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    strategy.status = StrategyStatus.ACTIVE
    strategy.activated_at = datetime.utcnow()

    if emergency:
        from datetime import timedelta
        strategy.is_emergency_override = True
        strategy.emergency_review_deadline = datetime.utcnow() + timedelta(days=5)

    await db.flush()
    return await _reload_strategy(db, strategy.id)


@router.post("/strategies/{strategy_id}/deactivate", response_model=DecisionStrategyResponse)
async def deactivate_strategy(strategy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    if strategy.status != StrategyStatus.ACTIVE:
        raise HTTPException(400, "Only active strategies can be deactivated")

    strategy.status = StrategyStatus.DRAFT
    await db.flush()
    return await _reload_strategy(db, strategy.id)


@router.post("/strategies/{strategy_id}/archive", response_model=DecisionStrategyResponse)
async def archive_strategy(strategy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    strategy.status = StrategyStatus.ARCHIVED
    strategy.archived_at = datetime.utcnow()
    await db.flush()
    return await _reload_strategy(db, strategy.id)


@router.post("/strategies/{strategy_id}/unarchive", response_model=DecisionStrategyResponse)
async def unarchive_strategy(strategy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    if strategy.status != StrategyStatus.ARCHIVED:
        raise HTTPException(400, "Only archived strategies can be unarchived")

    strategy.status = StrategyStatus.DRAFT
    strategy.archived_at = None
    await db.flush()
    return await _reload_strategy(db, strategy.id)


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete as sa_delete

    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    await db.execute(
        sa_delete(ChampionChallengerTest).where(
            (ChampionChallengerTest.champion_strategy_id == strategy_id) |
            (ChampionChallengerTest.challenger_strategy_id == strategy_id)
        )
    )

    await db.execute(
        DecisionTreeNode.__table__.update()
        .where(DecisionTreeNode.strategy_id == strategy_id)
        .values(strategy_id=None)
    )
    await db.execute(
        DecisionTreeNode.__table__.update()
        .where(DecisionTreeNode.null_strategy_id == strategy_id)
        .values(null_strategy_id=None)
    )

    await db.execute(
        DecisionTree.__table__.update()
        .where(DecisionTree.default_strategy_id == strategy_id)
        .values(default_strategy_id=None)
    )

    await db.execute(
        sa_delete(DecisionAuditTrail).where(DecisionAuditTrail.strategy_id == strategy_id)
    )

    if strategy.decision_tree_id:
        await db.execute(
            sa_delete(DecisionTreeNode).where(DecisionTreeNode.tree_id == strategy.decision_tree_id)
        )
        strategy_ref = strategy.decision_tree_id
        strategy.decision_tree_id = None
        await db.flush()
        await db.execute(sa_delete(DecisionTree).where(DecisionTree.id == strategy_ref))

    await db.execute(
        sa_delete(DecisionTreeNode).where(DecisionTreeNode.assessment_id.in_(
            select(Assessment.id).where(Assessment.strategy_id == strategy_id)
        ))
    )
    await db.execute(sa_delete(Assessment).where(Assessment.strategy_id == strategy_id))

    await db.delete(strategy)
    await db.flush()
    return {"deleted": True, "id": strategy_id}


@router.get("/strategies/{strategy_id}/versions", response_model=list[DecisionStrategyResponse])
async def strategy_versions(strategy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionStrategy).where(DecisionStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    versions_result = await db.execute(
        select(DecisionStrategy)
        .where(DecisionStrategy.name == strategy.name)
        .options(selectinload(DecisionStrategy.assessments))
        .order_by(DecisionStrategy.version.desc())
    )
    return versions_result.scalars().unique().all()


# ── Assessments ────────────────────────────────────────────────────

@router.get("/strategies/{strategy_id}/assessments", response_model=list[AssessmentResponse])
async def list_assessments(strategy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Assessment)
        .where(Assessment.strategy_id == strategy_id)
        .order_by(Assessment.id)
    )
    return result.scalars().all()


@router.post("/strategies/{strategy_id}/assessments", response_model=AssessmentResponse, status_code=201)
async def create_assessment(
    strategy_id: int,
    data: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
):
    strat = await db.execute(select(DecisionStrategy).where(DecisionStrategy.id == strategy_id))
    if not strat.scalar_one_or_none():
        raise HTTPException(404, "Strategy not found")

    assessment = Assessment(
        strategy_id=strategy_id,
        name=data.name,
        description=data.description,
        rules=data.rules,
        score_cutoffs=data.score_cutoffs,
    )
    db.add(assessment)
    await db.flush()
    await db.refresh(assessment)
    return assessment


@router.post("/assessments/from-template", response_model=AssessmentResponse, status_code=201)
async def create_assessment_from_template(
    strategy_id: int,
    name: str = "Assessment from Template",
    db: AsyncSession = Depends(get_db),
):
    """Create an assessment pre-filled with the standard business rules (R01-R21)."""
    from app.services.decision_engine.rules import RULES_REGISTRY

    strat = await db.execute(select(DecisionStrategy).where(DecisionStrategy.id == strategy_id))
    if not strat.scalar_one_or_none():
        raise HTTPException(404, "Strategy not found")

    template_rules = []
    for rule_id, rule_def in RULES_REGISTRY.items():
        template_rules.append({
            "rule_id": rule_id,
            "name": rule_def.get("name", ""),
            "field": rule_def.get("field", ""),
            "operator": rule_def.get("operator", "gte"),
            "threshold": rule_def.get("threshold"),
            "severity": rule_def.get("severity", "hard"),
            "outcome": rule_def.get("outcome", "decline"),
            "reason_code": rule_id,
            "enabled": rule_def.get("enabled", True),
        })

    assessment = Assessment(
        strategy_id=strategy_id,
        name=name,
        description="Created from standard business rules template",
        rules=template_rules,
    )
    db.add(assessment)
    await db.flush()
    await db.refresh(assessment)
    return assessment


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(assessment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    return assessment


@router.put("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: int,
    data: AssessmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    update_data = data.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(assessment, field_name, value)

    await db.flush()
    await db.refresh(assessment)
    return assessment


@router.delete("/assessments/{assessment_id}")
async def delete_assessment(assessment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    await db.delete(assessment)
    await db.flush()
    return {"deleted": True, "id": assessment_id}


# ── Decision Trees ─────────────────────────────────────────────────

@router.get("/decision-trees", response_model=list[DecisionTreeResponse])
async def list_trees(
    product_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(DecisionTree).options(
        selectinload(DecisionTree.nodes)
    ).order_by(DecisionTree.updated_at.desc())
    if product_id:
        query = query.where(DecisionTree.product_id == product_id)
    if status:
        query = query.where(DecisionTree.status == status)
    result = await db.execute(query)
    return result.scalars().unique().all()


@router.post("/decision-trees", response_model=DecisionTreeResponse, status_code=201)
async def create_tree(data: DecisionTreeCreate, db: AsyncSession = Depends(get_db)):
    max_ver_result = await db.execute(
        select(func.max(DecisionTree.version)).where(
            DecisionTree.product_id == data.product_id,
        )
    )
    next_version = (max_ver_result.scalar() or 0) + 1

    tree = DecisionTree(
        product_id=data.product_id,
        name=data.name,
        description=data.description,
        default_strategy_id=data.default_strategy_id,
        version=next_version,
        status=TreeStatus.DRAFT,
    )
    db.add(tree)
    try:
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(
            409,
            f"Decision tree for product {data.product_id} version {next_version} already exists",
        )

    node_key_to_id: dict[str, int] = {}
    for node_data in data.nodes:
        node = DecisionTreeNode(
            tree_id=tree.id,
            node_key=node_data.node_key,
            node_type=NodeType(node_data.node_type),
            label=node_data.label,
            condition_type=ConditionType(node_data.condition_type) if node_data.condition_type else None,
            attribute=node_data.attribute,
            operator=node_data.operator,
            branches=node_data.branches,
            compound_conditions=node_data.compound_conditions,
            compound_logic=node_data.compound_logic,
            strategy_id=node_data.strategy_id,
            strategy_params=node_data.strategy_params,
            assessment_id=node_data.assessment_id,
            null_branch=node_data.null_branch,
            null_strategy_id=node_data.null_strategy_id,
            scorecard_id=node_data.scorecard_id,
            branch_label=node_data.branch_label,
            is_root=node_data.is_root,
            position_x=node_data.position_x,
            position_y=node_data.position_y,
        )
        db.add(node)
        await db.flush()
        node_key_to_id[node_data.node_key] = node.id

    # Second pass: wire parent_node_id
    for node_data in data.nodes:
        if node_data.parent_node_key and node_data.parent_node_key in node_key_to_id:
            parent_id = node_key_to_id[node_data.parent_node_key]
            node_id = node_key_to_id[node_data.node_key]
            node_result = await db.execute(
                select(DecisionTreeNode).where(DecisionTreeNode.id == node_id)
            )
            node = node_result.scalar_one()
            node.parent_node_id = parent_id

    # Snapshot tree_data
    tree.tree_data = _serialize_tree_data(data.nodes)

    await db.flush()
    result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == tree.id)
        .options(selectinload(DecisionTree.nodes))
    )
    return result.scalar_one()


@router.get("/decision-trees/{tree_id}", response_model=DecisionTreeResponse)
async def get_tree(tree_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == tree_id)
        .options(selectinload(DecisionTree.nodes))
    )
    tree = result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "Decision tree not found")
    return tree


@router.put("/decision-trees/{tree_id}", response_model=DecisionTreeResponse)
async def update_tree(
    tree_id: int,
    data: DecisionTreeUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == tree_id)
        .options(selectinload(DecisionTree.nodes))
    )
    tree = result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "Decision tree not found")

    if tree.status == TreeStatus.ACTIVE:
        # Create new version instead of modifying active
        return await _create_new_tree_version(tree, data, db)

    if data.name is not None:
        tree.name = data.name
    if data.description is not None:
        tree.description = data.description
    if data.default_strategy_id is not None:
        tree.default_strategy_id = data.default_strategy_id
    if data.change_description is not None:
        tree.change_description = data.change_description

    if data.nodes is not None:
        # Replace all nodes
        for old_node in tree.nodes:
            await db.delete(old_node)
        await db.flush()

        node_key_to_id: dict[str, int] = {}
        for node_data in data.nodes:
            node = DecisionTreeNode(
                tree_id=tree.id,
                node_key=node_data.node_key,
                node_type=NodeType(node_data.node_type),
                label=node_data.label,
                condition_type=ConditionType(node_data.condition_type) if node_data.condition_type else None,
                attribute=node_data.attribute,
                operator=node_data.operator,
                branches=node_data.branches,
                compound_conditions=node_data.compound_conditions,
                compound_logic=node_data.compound_logic,
                strategy_id=node_data.strategy_id,
                strategy_params=node_data.strategy_params,
                assessment_id=node_data.assessment_id,
                null_branch=node_data.null_branch,
                null_strategy_id=node_data.null_strategy_id,
                scorecard_id=node_data.scorecard_id,
                branch_label=node_data.branch_label,
                is_root=node_data.is_root,
                position_x=node_data.position_x,
                position_y=node_data.position_y,
            )
            db.add(node)
            await db.flush()
            node_key_to_id[node_data.node_key] = node.id

        for node_data in data.nodes:
            if node_data.parent_node_key and node_data.parent_node_key in node_key_to_id:
                parent_id = node_key_to_id[node_data.parent_node_key]
                node_id = node_key_to_id[node_data.node_key]
                nr = await db.execute(
                    select(DecisionTreeNode).where(DecisionTreeNode.id == node_id)
                )
                n = nr.scalar_one()
                n.parent_node_id = parent_id

        tree.tree_data = _serialize_tree_data(data.nodes)

    await db.flush()
    result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == tree.id)
        .options(selectinload(DecisionTree.nodes))
    )
    return result.scalar_one()


@router.post("/decision-trees/{tree_id}/validate", response_model=TreeValidationResponse)
async def validate_tree_endpoint(tree_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == tree_id)
        .options(selectinload(DecisionTree.nodes))
    )
    tree = result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "Decision tree not found")

    # Gather valid strategy IDs
    strats = await db.execute(
        select(DecisionStrategy.id).where(
            DecisionStrategy.status.not_in([StrategyStatus.ARCHIVED])
        )
    )
    valid_ids = {s[0] for s in strats.all()}

    validation = validate_tree(tree.nodes, valid_ids)
    return TreeValidationResponse(
        valid=validation.valid,
        errors=[
            ValidationErrorSchema(
                severity=e.severity, node_key=e.node_key, code=e.code, message=e.message
            )
            for e in validation.errors
        ],
        warnings=[
            ValidationErrorSchema(
                severity=w.severity, node_key=w.node_key, code=w.code, message=w.message
            )
            for w in validation.warnings
        ],
        stats=validation.stats,
    )


@router.post("/decision-trees/{tree_id}/activate", response_model=DecisionTreeResponse)
async def activate_tree(tree_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == tree_id)
        .options(selectinload(DecisionTree.nodes))
    )
    tree = result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "Decision tree not found")

    # Validate before activation
    strats = await db.execute(
        select(DecisionStrategy.id).where(
            DecisionStrategy.status.not_in([StrategyStatus.ARCHIVED])
        )
    )
    valid_ids = {s[0] for s in strats.all()}
    validation = validate_tree(tree.nodes, valid_ids)
    if not validation.valid:
        raise HTTPException(400, f"Tree validation failed: {[e.message for e in validation.errors]}")

    # Archive any currently active tree for this product
    active_result = await db.execute(
        select(DecisionTree).where(
            DecisionTree.product_id == tree.product_id,
            DecisionTree.status == TreeStatus.ACTIVE,
            DecisionTree.id != tree.id,
        )
    )
    for active_tree in active_result.scalars().all():
        active_tree.status = TreeStatus.ARCHIVED
        active_tree.archived_at = datetime.utcnow()

    tree.status = TreeStatus.ACTIVE
    tree.activated_at = datetime.utcnow()

    # Update the product's decision_tree_id
    from app.models.catalog import CreditProduct
    product_result = await db.execute(
        select(CreditProduct).where(CreditProduct.id == tree.product_id)
    )
    product = product_result.scalar_one_or_none()
    if product:
        product.decision_tree_id = tree.id

    await db.flush()
    await db.refresh(tree)
    return tree


@router.get("/decision-trees/{tree_id}/versions", response_model=list[DecisionTreeResponse])
async def tree_versions(tree_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DecisionTree).where(DecisionTree.id == tree_id)
    )
    tree = result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "Decision tree not found")

    versions_result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.product_id == tree.product_id)
        .options(selectinload(DecisionTree.nodes))
        .order_by(DecisionTree.version.desc())
    )
    return versions_result.scalars().unique().all()


# ── Champion-Challenger ────────────────────────────────────────────

@router.post("/champion-challenger", response_model=ChampionChallengerResponse, status_code=201)
async def start_challenger_test(
    data: ChampionChallengerCreate,
    db: AsyncSession = Depends(get_db),
):
    test = ChampionChallengerTest(
        champion_strategy_id=data.champion_strategy_id,
        challenger_strategy_id=data.challenger_strategy_id,
        tree_id=data.tree_id,
        tree_node_key=data.tree_node_key,
        traffic_pct=data.traffic_pct,
        min_volume=data.min_volume,
        min_duration_days=data.min_duration_days,
        status=ChallengerTestStatus.ACTIVE,
    )
    db.add(test)
    await db.flush()
    await db.refresh(test)
    return test


@router.get("/champion-challenger/{test_id}")
async def get_challenger_test(test_id: int, db: AsyncSession = Depends(get_db)):
    return await get_test_comparison(test_id, db)


@router.post("/champion-challenger/{test_id}/promote")
async def promote_challenger_endpoint(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await promote_challenger(test_id, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/champion-challenger/{test_id}")
async def discard_challenger_endpoint(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await discard_challenger(test_id, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ── Simulation ─────────────────────────────────────────────────────

@router.post("/simulation/replay")
async def simulation_replay(
    data: SimulationReplayRequest,
    db: AsyncSession = Depends(get_db),
):
    app_ids = data.application_ids
    if not app_ids and data.time_period_start:
        query = select(LoanApplication.id).order_by(LoanApplication.created_at.desc())
        if data.time_period_start:
            query = query.where(LoanApplication.created_at >= data.time_period_start)
        if data.time_period_end:
            query = query.where(LoanApplication.created_at <= data.time_period_end)
        query = query.limit(data.max_applications)
        result = await db.execute(query)
        app_ids = [r[0] for r in result.all()]

    if not app_ids:
        return {"total_applications": 0, "results": [], "summary": {}}

    return await replay_historical(
        tree_id=data.tree_id,
        strategy_id=data.strategy_id,
        application_ids=app_ids,
        db=db,
    )


@router.post("/simulation/trace")
async def simulation_trace(
    data: SimulationTraceRequest,
    db: AsyncSession = Depends(get_db),
):
    return await trace_application(
        application_id=data.application_id,
        tree_id=data.tree_id,
        strategy_id=data.strategy_id,
        db=db,
        overrides=data.overrides,
    )


@router.post("/simulation/impact")
async def simulation_impact(
    data: SimulationImpactRequest,
    db: AsyncSession = Depends(get_db),
):
    if not data.application_ids:
        return {"total_compared": 0}

    return await impact_analysis(
        old_tree_id=data.old_tree_id,
        new_tree_id=data.new_tree_id,
        old_strategy_id=data.old_strategy_id,
        new_strategy_id=data.new_strategy_id,
        application_ids=data.application_ids,
        db=db,
    )


# ── Decision Explanation ───────────────────────────────────────────

@router.get("/decisions/{decision_id}/explanation", response_model=DecisionExplanationResponse)
async def get_decision_explanation(decision_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Decision).where(Decision.id == decision_id)
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(404, "Decision not found")

    # Check for extended audit trail
    audit_result = await db.execute(
        select(DecisionAuditTrail).where(DecisionAuditTrail.decision_id == decision_id)
    )
    audit = audit_result.scalar_one_or_none()

    strategy_name = None
    strategy_version = None
    if audit and audit.strategy_id:
        strat_result = await db.execute(
            select(DecisionStrategy).where(DecisionStrategy.id == audit.strategy_id)
        )
        strat = strat_result.scalar_one_or_none()
        if strat:
            strategy_name = strat.name
            strategy_version = strat.version

    return DecisionExplanationResponse(
        application_id=decision.loan_application_id,
        tree_path=audit.routing_path if audit else (
            decision.routing_path.get("path") if decision.routing_path else None
        ),
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        evaluation_steps=audit.evaluation_steps if audit else [],
        final_outcome=decision.final_outcome or "",
        reason_codes=(decision.engine_reasons or {}).get("reason_codes", []),
        reasons=(decision.engine_reasons or {}).get("reasons", []),
        terms=None,
        explanation_staff=audit.explanation_staff if audit else None,
        explanation_consumer=audit.explanation_consumer if audit else None,
    )


# ── Helpers ────────────────────────────────────────────────────────

def _serialize_tree_data(nodes: list[TreeNodeCreate]) -> dict:
    return {
        "nodes": [n.model_dump() for n in nodes],
    }


async def _create_new_tree_version(
    old_tree: DecisionTree,
    data: DecisionTreeUpdate,
    db: AsyncSession,
) -> DecisionTreeResponse:
    """Create a new version of an active tree."""
    max_version = await db.execute(
        select(func.max(DecisionTree.version)).where(
            DecisionTree.product_id == old_tree.product_id,
        )
    )
    new_version = (max_version.scalar() or 0) + 1

    new_tree = DecisionTree(
        product_id=old_tree.product_id,
        name=data.name or old_tree.name,
        description=data.description if data.description is not None else old_tree.description,
        default_strategy_id=data.default_strategy_id or old_tree.default_strategy_id,
        version=new_version,
        status=TreeStatus.DRAFT,
        parent_version_id=old_tree.id,
        change_description=data.change_description,
    )
    db.add(new_tree)
    await db.flush()

    if data.nodes is not None:
        node_key_to_id: dict[str, int] = {}
        for nd in data.nodes:
            node = DecisionTreeNode(
                tree_id=new_tree.id,
                node_key=nd.node_key,
                node_type=NodeType(nd.node_type),
                label=nd.label,
                condition_type=ConditionType(nd.condition_type) if nd.condition_type else None,
                attribute=nd.attribute,
                operator=nd.operator,
                branches=nd.branches,
                compound_conditions=nd.compound_conditions,
                compound_logic=nd.compound_logic,
                strategy_id=nd.strategy_id,
                strategy_params=nd.strategy_params,
                assessment_id=nd.assessment_id,
                null_branch=nd.null_branch,
                null_strategy_id=nd.null_strategy_id,
                scorecard_id=nd.scorecard_id,
                branch_label=nd.branch_label,
                is_root=nd.is_root,
                position_x=nd.position_x,
                position_y=nd.position_y,
            )
            db.add(node)
            await db.flush()
            node_key_to_id[nd.node_key] = node.id

        for nd in data.nodes:
            if nd.parent_node_key and nd.parent_node_key in node_key_to_id:
                parent_id = node_key_to_id[nd.parent_node_key]
                node_id = node_key_to_id[nd.node_key]
                nr = await db.execute(
                    select(DecisionTreeNode).where(DecisionTreeNode.id == node_id)
                )
                n = nr.scalar_one()
                n.parent_node_id = parent_id

        new_tree.tree_data = _serialize_tree_data(data.nodes)
    else:
        # Copy nodes from old tree
        for old_node in old_tree.nodes:
            new_node = DecisionTreeNode(
                tree_id=new_tree.id,
                node_key=old_node.node_key,
                node_type=old_node.node_type,
                label=old_node.label,
                condition_type=old_node.condition_type,
                attribute=old_node.attribute,
                operator=old_node.operator,
                branches=old_node.branches,
                compound_conditions=old_node.compound_conditions,
                compound_logic=old_node.compound_logic,
                strategy_id=old_node.strategy_id,
                strategy_params=old_node.strategy_params,
                assessment_id=old_node.assessment_id,
                null_branch=old_node.null_branch,
                null_strategy_id=old_node.null_strategy_id,
                scorecard_id=old_node.scorecard_id,
                branch_label=old_node.branch_label,
                is_root=old_node.is_root,
                position_x=old_node.position_x,
                position_y=old_node.position_y,
            )
            db.add(new_node)

    await db.flush()
    result = await db.execute(
        select(DecisionTree)
        .where(DecisionTree.id == new_tree.id)
        .options(selectinload(DecisionTree.nodes))
    )
    return result.scalar_one()
