"""Add read_at column to application_comments for notification tracking.

Revision ID: 009_read_at_comments
Revises: 008_add_id_type
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa


revision = "009_read_at_comments"
down_revision = "008_add_id_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "application_comments",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application_comments", "read_at")
