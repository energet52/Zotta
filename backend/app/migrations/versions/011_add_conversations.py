"""Add conversations and conversation_messages tables.

Revision ID: 011_add_conversations
Revises: 010_app_references
Create Date: 2026-02-13

"""
from alembic import op
import sqlalchemy as sa


revision = "011_add_conversations"
down_revision = "010_app_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="web"),
        sa.Column("participant_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("participant_phone", sa.String(30), nullable=True, index=True),
        sa.Column("current_state", sa.String(50), nullable=False, server_default="initiated"),
        sa.Column("loan_application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=True, index=True),
        sa.Column("entry_point", sa.String(30), nullable=True),
        sa.Column("entry_context", sa.JSON(), nullable=True),
        sa.Column("assigned_agent_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_reason", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column(
        "loan_applications",
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("loan_applications", "conversation_id")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
