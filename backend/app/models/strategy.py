"""Decision Strategy Management models.

DecisionStrategy, DecisionTree, DecisionTreeNode,
ChampionChallengerTest, DecisionAuditTrail.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    String, Integer, Float, Numeric, Boolean,
    Enum, DateTime, ForeignKey, Text, JSON,
    func, UniqueConstraint, Index, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────

class StrategyStatus(str, enum.Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    SIMULATION_TESTING = "simulation_testing"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"


class EvaluationMode(str, enum.Enum):
    SEQUENTIAL = "sequential"
    DUAL_PATH = "dual_path"
    SCORING = "scoring"
    HYBRID = "hybrid"


class TreeStatus(str, enum.Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    SIMULATION_TESTING = "simulation_testing"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"


class NodeType(str, enum.Enum):
    CONDITION = "condition"
    SCORECARD_GATE = "scorecard_gate"
    STRATEGY = "strategy"
    ASSESSMENT = "assessment"
    ANNOTATION = "annotation"


class ConditionType(str, enum.Enum):
    BINARY = "binary"
    CATEGORICAL = "categorical"
    NUMERIC_RANGE = "numeric_range"
    COMPOUND = "compound"


class ChallengerTestStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DISCARDED = "discarded"


# ── Decision Strategy ──────────────────────────────────────────────

class DecisionStrategy(Base):
    __tablename__ = "decision_strategies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluation_mode: Mapped[EvaluationMode] = mapped_column(
        Enum(EvaluationMode), nullable=False, default=EvaluationMode.SEQUENTIAL,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # For sequential mode — reuse existing rules config
    rules_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_rules_config.id"), nullable=True,
    )
    # For dual-path / hybrid modes — scorecard reference
    scorecard_id: Mapped[int | None] = mapped_column(
        ForeignKey("scorecards.id"), nullable=True,
    )

    # Dual-path rule sets (JSON arrays of rule definitions)
    knock_out_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overlay_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Score cutoffs for dual-path: {"approve": 220, "refer": 180, "decline": 0}
    score_cutoffs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Terms matrix: score-band → terms mapping
    terms_matrix: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Reason code mapping
    reason_code_map: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Concentration limits: [{"dimension": "product", "limit": 10000000}, ...]
    concentration_limits: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Lifecycle
    status: Mapped[StrategyStatus] = mapped_column(
        Enum(StrategyStatus), nullable=False, default=StrategyStatus.DRAFT,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Version lineage
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_strategies.id"), nullable=True,
    )
    change_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_emergency_override: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_review_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Embedded decision tree (1:1)
    decision_tree_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_trees.id"), nullable=True,
    )

    # Relationships
    rules_config = relationship("DecisionRulesConfig", foreign_keys=[rules_config_id])
    scorecard = relationship("Scorecard", foreign_keys=[scorecard_id])
    parent_version = relationship("DecisionStrategy", remote_side="DecisionStrategy.id")
    tree_nodes = relationship(
        "DecisionTreeNode", back_populates="strategy",
        foreign_keys="[DecisionTreeNode.strategy_id]",
    )
    decision_tree = relationship("DecisionTree", foreign_keys=[decision_tree_id])
    assessments = relationship(
        "Assessment", back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="Assessment.id",
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_strategy_name_version"),
    )


# ── Decision Tree ──────────────────────────────────────────────────

class DecisionTree(Base):
    __tablename__ = "decision_trees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("credit_products.id"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Full tree graph (redundant with nodes table, for fast loading + immutability)
    tree_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Default/catch-all strategy when no branch matches
    default_strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_strategies.id"), nullable=True,
    )

    # Lifecycle
    status: Mapped[TreeStatus] = mapped_column(
        Enum(TreeStatus), nullable=False, default=TreeStatus.DRAFT,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Version lineage
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_trees.id"), nullable=True,
    )
    change_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    product = relationship("CreditProduct", foreign_keys=[product_id])
    default_strategy = relationship("DecisionStrategy", foreign_keys=[default_strategy_id])
    parent_version = relationship("DecisionTree", remote_side="DecisionTree.id")
    nodes = relationship(
        "DecisionTreeNode", back_populates="tree",
        cascade="all, delete-orphan",
        order_by="DecisionTreeNode.id",
    )

    __table_args__ = (
        UniqueConstraint("product_id", "version", name="uq_tree_product_version"),
    )


# ── Decision Tree Node ─────────────────────────────────────────────

class DecisionTreeNode(Base):
    __tablename__ = "decision_tree_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tree_id: Mapped[int] = mapped_column(
        ForeignKey("decision_trees.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)

    node_type: Mapped[NodeType] = mapped_column(Enum(NodeType), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Condition configuration (for condition / scorecard_gate nodes)
    condition_type: Mapped[ConditionType | None] = mapped_column(
        Enum(ConditionType), nullable=True,
    )
    attribute: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Branches definition: {"Yes": {...}, "No": {...}} or {"0-100": {...}, "100-200": {...}}
    branches: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # For compound conditions: [{"attribute": "...", "operator": "...", "value": ...}, ...]
    compound_conditions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    compound_logic: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "AND" / "OR"

    # Terminal strategy assignment (for strategy nodes)
    strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_strategies.id"), nullable=True,
    )
    # Parameter overrides passed to strategy
    strategy_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Null handling
    null_branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    null_strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_strategies.id"), nullable=True,
    )

    # Terminal assessment assignment (for assessment nodes)
    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessments.id"), nullable=True,
    )

    # For scorecard gate nodes
    scorecard_id: Mapped[int | None] = mapped_column(
        ForeignKey("scorecards.id"), nullable=True,
    )

    # Graph topology
    parent_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_tree_nodes.id"), nullable=True,
    )
    branch_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_root: Mapped[bool] = mapped_column(Boolean, default=False)

    # Canvas position for the visual editor
    position_x: Mapped[float] = mapped_column(Float, default=0)
    position_y: Mapped[float] = mapped_column(Float, default=0)

    # Relationships
    tree = relationship("DecisionTree", back_populates="nodes")
    strategy = relationship("DecisionStrategy", foreign_keys=[strategy_id], back_populates="tree_nodes")
    null_strategy = relationship("DecisionStrategy", foreign_keys=[null_strategy_id])
    assessment = relationship("Assessment", foreign_keys=[assessment_id])
    parent_node = relationship("DecisionTreeNode", remote_side="DecisionTreeNode.id")

    __table_args__ = (
        UniqueConstraint("tree_id", "node_key", name="uq_tree_node_key"),
        Index("ix_tree_nodes_parent", "tree_id", "parent_node_id"),
    )


# ── Assessment ─────────────────────────────────────────────────────

class Assessment(Base):
    """A set of business rules evaluated at a decision tree terminal node.

    Each Assessment belongs to a Strategy and contains an independent
    copy of business rules (JSON array) that can be customized
    per-branch of the decision tree.
    """
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("decision_strategies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    rules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    score_cutoffs: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    strategy = relationship("DecisionStrategy", back_populates="assessments")
    tree_nodes = relationship(
        "DecisionTreeNode", back_populates="assessment",
        foreign_keys="[DecisionTreeNode.assessment_id]",
    )


# ── Champion-Challenger Test ───────────────────────────────────────

class ChampionChallengerTest(Base):
    __tablename__ = "champion_challenger_tests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    champion_strategy_id: Mapped[int] = mapped_column(
        ForeignKey("decision_strategies.id"), nullable=False,
    )
    challenger_strategy_id: Mapped[int] = mapped_column(
        ForeignKey("decision_strategies.id"), nullable=False,
    )
    # Optional tree-level testing
    tree_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_trees.id"), nullable=True,
    )
    tree_node_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

    traffic_pct: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    min_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    min_duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)

    status: Mapped[ChallengerTestStatus] = mapped_column(
        Enum(ChallengerTestStatus), nullable=False, default=ChallengerTestStatus.ACTIVE,
    )

    # Accumulated results
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    agreement_count: Mapped[int] = mapped_column(Integer, default=0)
    disagreement_count: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    champion_strategy = relationship("DecisionStrategy", foreign_keys=[champion_strategy_id])
    challenger_strategy = relationship("DecisionStrategy", foreign_keys=[challenger_strategy_id])
    tree = relationship("DecisionTree", foreign_keys=[tree_id])

    __table_args__ = (
        CheckConstraint("traffic_pct >= 5 AND traffic_pct <= 50", name="ck_traffic_pct_range"),
    )


# ── Decision Audit Trail ──────────────────────────────────────────

class DecisionAuditTrail(Base):
    __tablename__ = "decision_audit_trail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id"), nullable=False, index=True,
    )

    # Tree routing context
    tree_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tree_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    routing_path: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Strategy context
    strategy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_params_applied: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Scorecard context
    scorecard_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scorecard_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scorecard_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full evaluation trace
    rule_evaluations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evaluation_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Champion-challenger shadow results
    challenger_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Generated explanations
    explanation_staff: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_consumer: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Relationships
    decision = relationship("Decision", foreign_keys=[decision_id])

    __table_args__ = (
        Index("ix_audit_trail_tree", "tree_id", "tree_version"),
        Index("ix_audit_trail_strategy", "strategy_id", "strategy_version"),
    )
