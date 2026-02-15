"""Add application_references table.

Revision ID: 010_app_references
Revises: 009_read_at_comments
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa


revision = "010_app_references"
down_revision = "009_read_at_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_references",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("directions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("application_references")
