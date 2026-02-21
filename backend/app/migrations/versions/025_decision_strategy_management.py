"""Decision Strategy Management.

Creates: decision_strategies, decision_trees, decision_tree_nodes,
         champion_challenger_tests, decision_audit_trail.
Adds columns to: credit_products, decisions.
"""

from alembic import op
import sqlalchemy as sa


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── decision_strategies ────────────────────────────────────────
    op.create_table(
        "decision_strategies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "evaluation_mode",
            sa.Enum("sequential", "dual_path", "scoring", "hybrid", name="evaluation_mode_enum"),
            nullable=False,
            server_default="sequential",
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("rules_config_id", sa.Integer, sa.ForeignKey("decision_rules_config.id"), nullable=True),
        sa.Column("scorecard_id", sa.Integer, sa.ForeignKey("scorecards.id"), nullable=True),
        sa.Column("knock_out_rules", sa.JSON, nullable=True),
        sa.Column("overlay_rules", sa.JSON, nullable=True),
        sa.Column("score_cutoffs", sa.JSON, nullable=True),
        sa.Column("terms_matrix", sa.JSON, nullable=True),
        sa.Column("reason_code_map", sa.JSON, nullable=True),
        sa.Column("concentration_limits", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "under_review", "simulation_testing", "approved", "active", "archived",
                    name="strategy_status_enum"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_version_id", sa.Integer, sa.ForeignKey("decision_strategies.id"), nullable=True),
        sa.Column("change_description", sa.Text, nullable=True),
        sa.Column("is_emergency_override", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("emergency_review_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", "version", name="uq_strategy_name_version"),
    )

    # ── decision_trees ─────────────────────────────────────────────
    op.create_table(
        "decision_trees",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("credit_products.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("tree_data", sa.JSON, nullable=True),
        sa.Column("default_strategy_id", sa.Integer, sa.ForeignKey("decision_strategies.id"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "under_review", "simulation_testing", "approved", "active", "archived",
                    name="tree_status_enum"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_version_id", sa.Integer, sa.ForeignKey("decision_trees.id"), nullable=True),
        sa.Column("change_description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("product_id", "version", name="uq_tree_product_version"),
    )

    # ── decision_tree_nodes ────────────────────────────────────────
    op.create_table(
        "decision_tree_nodes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tree_id", sa.Integer, sa.ForeignKey("decision_trees.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("node_key", sa.String(100), nullable=False),
        sa.Column(
            "node_type",
            sa.Enum("condition", "scorecard_gate", "strategy", "annotation", name="node_type_enum"),
            nullable=False,
        ),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column(
            "condition_type",
            sa.Enum("binary", "categorical", "numeric_range", "compound", name="condition_type_enum"),
            nullable=True,
        ),
        sa.Column("attribute", sa.String(100), nullable=True),
        sa.Column("operator", sa.String(30), nullable=True),
        sa.Column("branches", sa.JSON, nullable=True),
        sa.Column("compound_conditions", sa.JSON, nullable=True),
        sa.Column("compound_logic", sa.String(10), nullable=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("decision_strategies.id"), nullable=True),
        sa.Column("strategy_params", sa.JSON, nullable=True),
        sa.Column("null_branch", sa.String(100), nullable=True),
        sa.Column("null_strategy_id", sa.Integer, sa.ForeignKey("decision_strategies.id"), nullable=True),
        sa.Column("scorecard_id", sa.Integer, sa.ForeignKey("scorecards.id"), nullable=True),
        sa.Column("parent_node_id", sa.Integer, sa.ForeignKey("decision_tree_nodes.id"), nullable=True),
        sa.Column("branch_label", sa.String(100), nullable=True),
        sa.Column("is_root", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("position_x", sa.Float, nullable=False, server_default="0"),
        sa.Column("position_y", sa.Float, nullable=False, server_default="0"),
        sa.UniqueConstraint("tree_id", "node_key", name="uq_tree_node_key"),
        sa.Index("ix_tree_nodes_parent", "tree_id", "parent_node_id"),
    )

    # ── champion_challenger_tests ──────────────────────────────────
    op.create_table(
        "champion_challenger_tests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("champion_strategy_id", sa.Integer,
                  sa.ForeignKey("decision_strategies.id"), nullable=False),
        sa.Column("challenger_strategy_id", sa.Integer,
                  sa.ForeignKey("decision_strategies.id"), nullable=False),
        sa.Column("tree_id", sa.Integer, sa.ForeignKey("decision_trees.id"), nullable=True),
        sa.Column("tree_node_key", sa.String(100), nullable=True),
        sa.Column("traffic_pct", sa.Float, nullable=False, server_default="10"),
        sa.Column("min_volume", sa.Integer, nullable=False, server_default="500"),
        sa.Column("min_duration_days", sa.Integer, nullable=False, server_default="90"),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "discarded", name="challenger_test_status_enum"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("results", sa.JSON, nullable=True),
        sa.Column("total_evaluated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("agreement_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("disagreement_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("traffic_pct >= 5 AND traffic_pct <= 50", name="ck_traffic_pct_range"),
    )

    # ── decision_audit_trail ───────────────────────────────────────
    op.create_table(
        "decision_audit_trail",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.Integer, sa.ForeignKey("decisions.id"), nullable=False, index=True),
        sa.Column("tree_id", sa.Integer, nullable=True),
        sa.Column("tree_version", sa.Integer, nullable=True),
        sa.Column("routing_path", sa.JSON, nullable=True),
        sa.Column("strategy_id", sa.Integer, nullable=True),
        sa.Column("strategy_version", sa.Integer, nullable=True),
        sa.Column("strategy_params_applied", sa.JSON, nullable=True),
        sa.Column("scorecard_id", sa.Integer, nullable=True),
        sa.Column("scorecard_version", sa.Integer, nullable=True),
        sa.Column("scorecard_score", sa.Float, nullable=True),
        sa.Column("rule_evaluations", sa.JSON, nullable=True),
        sa.Column("evaluation_steps", sa.JSON, nullable=True),
        sa.Column("challenger_results", sa.JSON, nullable=True),
        sa.Column("explanation_staff", sa.Text, nullable=True),
        sa.Column("explanation_consumer", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Index("ix_audit_trail_tree", "tree_id", "tree_version"),
        sa.Index("ix_audit_trail_strategy", "strategy_id", "strategy_version"),
    )

    # ── Add columns to existing tables ─────────────────────────────

    # credit_products: optional tree/strategy references
    op.add_column("credit_products", sa.Column(
        "decision_tree_id", sa.Integer,
        sa.ForeignKey("decision_trees.id"), nullable=True,
    ))
    op.add_column("credit_products", sa.Column(
        "default_strategy_id", sa.Integer,
        sa.ForeignKey("decision_strategies.id"), nullable=True,
    ))

    # decisions: strategy routing metadata
    op.add_column("decisions", sa.Column(
        "strategy_id", sa.Integer,
        sa.ForeignKey("decision_strategies.id"), nullable=True,
    ))
    op.add_column("decisions", sa.Column(
        "tree_version", sa.Integer, nullable=True,
    ))
    op.add_column("decisions", sa.Column(
        "routing_path", sa.JSON, nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("decisions", "routing_path")
    op.drop_column("decisions", "tree_version")
    op.drop_column("decisions", "strategy_id")
    op.drop_column("credit_products", "default_strategy_id")
    op.drop_column("credit_products", "decision_tree_id")

    op.drop_table("decision_audit_trail")
    op.drop_table("champion_challenger_tests")
    op.drop_table("decision_tree_nodes")
    op.drop_table("decision_trees")
    op.drop_table("decision_strategies")

    for enum_name in [
        "evaluation_mode_enum", "strategy_status_enum", "tree_status_enum",
        "node_type_enum", "condition_type_enum", "challenger_test_status_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
