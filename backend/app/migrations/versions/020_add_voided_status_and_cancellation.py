"""Add VOIDED loan status and cancellation fields."""

from alembic import op
import sqlalchemy as sa


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    # Add 'voided' to loanstatus enum
    op.execute("ALTER TYPE loanstatus ADD VALUE IF NOT EXISTS 'VOIDED'")

    # Add cancellation fields
    op.add_column("loan_applications", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("loan_applications", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("loan_applications", sa.Column("cancelled_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_loan_applications_cancelled_by",
        "loan_applications", "users",
        ["cancelled_by"], ["id"],
    )


def downgrade():
    op.drop_constraint("fk_loan_applications_cancelled_by", "loan_applications", type_="foreignkey")
    op.drop_column("loan_applications", "cancelled_by")
    op.drop_column("loan_applications", "cancelled_at")
    op.drop_column("loan_applications", "cancellation_reason")
