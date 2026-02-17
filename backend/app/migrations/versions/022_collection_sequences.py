"""Collection sequences -- multi-step automated notification workflows.

Creates: collection_sequences, sequence_steps, message_templates,
         sequence_enrollments, step_executions
"""

from alembic import op
import sqlalchemy as sa


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Message templates (must come before sequence_steps FK)
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="whatsapp"),
        sa.Column("tone", sa.String(20), nullable=False, server_default="friendly"),
        sa.Column("category", sa.String(30), nullable=False, server_default="reminder"),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("variables", sa.JSON, nullable=True),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("response_rate", sa.Float, nullable=True),
        sa.Column("payment_rate", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Collection sequences
    op.create_table(
        "collection_sequences",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("delinquency_stage", sa.String(30), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("channels", sa.JSON, nullable=True),
        sa.Column("ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Sequence steps
    op.create_table(
        "sequence_steps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sequence_id", sa.Integer, sa.ForeignKey("collection_sequences.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("day_offset", sa.Integer, nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="whatsapp"),
        sa.Column("action_type", sa.String(30), nullable=False, server_default="send_message"),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("message_templates.id"), nullable=True),
        sa.Column("custom_message", sa.Text, nullable=True),
        sa.Column("condition_json", sa.JSON, nullable=True),
        sa.Column("send_time", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("wait_for_response_hours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_effectiveness_score", sa.Float, nullable=True),
    )

    # Sequence enrollments
    op.create_table(
        "sequence_enrollments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("collection_cases.id"), nullable=False, index=True),
        sa.Column("sequence_id", sa.Integer, sa.ForeignKey("collection_sequences.id"), nullable=False, index=True),
        sa.Column("current_step_number", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("paused_reason", sa.Text, nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Step executions
    op.create_table(
        "step_executions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("enrollment_id", sa.Integer, sa.ForeignKey("sequence_enrollments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_id", sa.Integer, sa.ForeignKey("sequence_steps.id"), nullable=False, index=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("message_sent", sa.Text, nullable=True),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("borrower_responded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_after", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("step_executions")
    op.drop_table("sequence_enrollments")
    op.drop_table("sequence_steps")
    op.drop_table("collection_sequences")
    op.drop_table("message_templates")
