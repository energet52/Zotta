"""Add employer_sector column to applicant_profiles.

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applicant_profiles",
        sa.Column("employer_sector", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applicant_profiles", "employer_sector")
