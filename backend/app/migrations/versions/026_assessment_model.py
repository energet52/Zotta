"""Assessment model and strategy-tree embedding.

Creates: assessments table.
Adds columns: decision_strategies.decision_tree_id, decision_tree_nodes.assessment_id.
Adds 'assessment' to node_type enum.
"""

from alembic import op
import sqlalchemy as sa


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'assessment'")
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'ASSESSMENT'")

    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("decision_strategies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("rules", sa.JSON, nullable=True),
        sa.Column("score_cutoffs", sa.JSON, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    with op.batch_alter_table("decision_strategies") as batch_op:
        batch_op.add_column(sa.Column("decision_tree_id", sa.Integer, sa.ForeignKey("decision_trees.id"), nullable=True))

    with op.batch_alter_table("decision_tree_nodes") as batch_op:
        batch_op.add_column(sa.Column("assessment_id", sa.Integer, sa.ForeignKey("assessments.id"), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("decision_tree_nodes") as batch_op:
        batch_op.drop_column("assessment_id")

    with op.batch_alter_table("decision_strategies") as batch_op:
        batch_op.drop_column("decision_tree_id")

    op.drop_table("assessments")
