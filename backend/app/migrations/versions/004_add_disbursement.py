"""Add disbursement tracking: disbursements table + disbursed_at on loan_applications.

Revision ID: 004_add_disbursement
Revises: 003_categories_per_merchant
Create Date: 2026-02-11

"""

from alembic import op
import sqlalchemy as sa


revision = "004_add_disbursement"
down_revision = "003_categories_per_merchant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add disbursed_at to loan_applications
    op.add_column(
        "loan_applications",
        sa.Column("disbursed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Back-fill existing disbursed loans: use decided_at as disbursed_at
    op.execute("""
        UPDATE loan_applications
        SET disbursed_at = decided_at
        WHERE status::text = 'disbursed' AND disbursed_at IS NULL
    """)

    # Create disbursements table
    op.create_table(
        "disbursements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("loan_application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.Enum("manual", "bank_transfer", "mobile_money", "wallet", "cheque", name="disbursementmethod"), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "failed", "reversed", name="disbursementstatus"), nullable=False),
        sa.Column("reference_number", sa.String(50), unique=True, nullable=True, index=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("provider_reference", sa.String(100), nullable=True),
        sa.Column("provider_response", sa.JSON(), nullable=True),
        sa.Column("recipient_account_name", sa.String(200), nullable=True),
        sa.Column("recipient_account_number", sa.String(50), nullable=True),
        sa.Column("recipient_bank", sa.String(100), nullable=True),
        sa.Column("recipient_bank_branch", sa.String(100), nullable=True),
        sa.Column("disbursed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("disbursed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("disbursements")
    op.execute("DROP TYPE IF EXISTS disbursementstatus")
    op.execute("DROP TYPE IF EXISTS disbursementmethod")
    op.drop_column("loan_applications", "disbursed_at")
