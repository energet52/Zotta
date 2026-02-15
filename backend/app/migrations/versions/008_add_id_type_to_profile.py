"""Add id_type field to applicant_profiles.

Revision ID: 008_add_id_type
Revises: 007_contact_fields
Create Date: 2026-02-12

"""
from alembic import op
import sqlalchemy as sa


revision = "008_add_id_type"
down_revision = "007_contact_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applicant_profiles",
        sa.Column("id_type", sa.String(30), nullable=True),
    )
    # Also widen national_id from String(20) to String(50) to support longer IDs
    op.alter_column(
        "applicant_profiles",
        "national_id",
        type_=sa.String(50),
        existing_type=sa.String(20),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "applicant_profiles",
        "national_id",
        type_=sa.String(20),
        existing_type=sa.String(50),
        existing_nullable=True,
    )
    op.drop_column("applicant_profiles", "id_type")
