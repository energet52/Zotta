"""Add credit_bureau_alerts table.

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    alert_type = postgresql.ENUM(
        "new_inquiry", "new_loan", "new_delinquency",
        "default_elsewhere", "collection_payment_elsewhere",
        name="alerttype", create_type=True,
    )
    alert_severity = postgresql.ENUM(
        "low", "medium", "high", "critical",
        name="alertseverity", create_type=True,
    )
    alert_status = postgresql.ENUM(
        "new", "acknowledged", "action_taken", "dismissed",
        name="alertstatus", create_type=True,
    )

    op.create_table(
        "credit_bureau_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("alert_type", alert_type, nullable=False, index=True),
        sa.Column("severity", alert_severity, nullable=False),
        sa.Column("status", alert_status, nullable=False, server_default="new"),
        sa.Column("bureau_name", sa.String(100), nullable=False),
        sa.Column("bureau_reference", sa.String(100), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("other_institution", sa.String(200), nullable=True),
        sa.Column("other_product_type", sa.String(100), nullable=True),
        sa.Column("other_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("other_delinquency_days", sa.Integer(), nullable=True),
        sa.Column("other_delinquency_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("action_taken", sa.String(100), nullable=True),
        sa.Column("action_notes", sa.Text(), nullable=True),
        sa.Column("acted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("credit_bureau_alerts")
    op.execute("DROP TYPE IF EXISTS alerttype")
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS alertstatus")
