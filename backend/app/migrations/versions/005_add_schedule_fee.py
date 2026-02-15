"""Add fee column to payment_schedules.

Revision ID: 005_add_schedule_fee
Revises: 004_add_disbursement
Create Date: 2026-02-11

"""

from alembic import op
import sqlalchemy as sa


revision = "005_add_schedule_fee"
down_revision = "004_add_disbursement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_schedules",
        sa.Column("fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("payment_schedules", "fee")
