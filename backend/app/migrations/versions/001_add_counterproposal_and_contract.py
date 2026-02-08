"""Add counterproposal and contract fields to loan_applications.

Revision ID: 001_counterproposal_contract
Revises:
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_counterproposal_contract'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Counterproposal fields
    op.add_column('loan_applications', sa.Column('proposed_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('loan_applications', sa.Column('proposed_rate', sa.Numeric(5, 2), nullable=True))
    op.add_column('loan_applications', sa.Column('proposed_term', sa.Integer(), nullable=True))
    op.add_column('loan_applications', sa.Column('counterproposal_reason', sa.Text(), nullable=True))

    # Contract fields
    op.add_column('loan_applications', sa.Column('contract_signed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('loan_applications', sa.Column('contract_signature_data', sa.Text(), nullable=True))
    op.add_column('loan_applications', sa.Column('contract_typed_name', sa.String(200), nullable=True))

    # Note: COUNTER_PROPOSED enum value needs to be added to the LoanStatus enum.
    # PostgreSQL requires ALTER TYPE to add enum values.
    op.execute("ALTER TYPE loanstatus ADD VALUE IF NOT EXISTS 'counter_proposed'")


def downgrade() -> None:
    op.drop_column('loan_applications', 'contract_typed_name')
    op.drop_column('loan_applications', 'contract_signature_data')
    op.drop_column('loan_applications', 'contract_signed_at')
    op.drop_column('loan_applications', 'counterproposal_reason')
    op.drop_column('loan_applications', 'proposed_term')
    op.drop_column('loan_applications', 'proposed_rate')
    op.drop_column('loan_applications', 'proposed_amount')
    # Note: PostgreSQL does not support removing enum values easily
