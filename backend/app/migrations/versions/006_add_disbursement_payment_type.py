"""Add disbursement value to paymenttype enum.

Revision ID: 006_add_disbursement_payment_type
Revises: 005_add_schedule_fee
Create Date: 2026-02-11

"""

from alembic import op


revision = "006_disb_pay_type"
down_revision = "005_add_schedule_fee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE paymenttype ADD VALUE IF NOT EXISTS 'DISBURSEMENT'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL; safe to leave
    pass
