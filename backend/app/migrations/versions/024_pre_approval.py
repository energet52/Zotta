"""Pre-Approval module.

Creates: pre_approvals, pre_approval_otps
"""

from alembic import op
import sqlalchemy as sa


revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pre_approvals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("reference_code", sa.String(12), unique=True, nullable=False, index=True),
        # Consumer identity
        sa.Column("phone", sa.String(30), nullable=False, index=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("national_id", sa.String(50), nullable=True, index=True),
        # Item & merchant
        sa.Column("merchant_id", sa.Integer, sa.ForeignKey("merchants.id"), nullable=True, index=True),
        sa.Column("merchant_name_manual", sa.String(200), nullable=True),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("item_description", sa.Text, nullable=True),
        sa.Column("goods_category", sa.String(100), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False, server_default="TTD"),
        sa.Column("downpayment", sa.Numeric(12, 2), nullable=False, server_default="0"),
        # Financial info
        sa.Column("monthly_income", sa.Numeric(12, 2), nullable=False),
        sa.Column("income_frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("employment_status", sa.String(50), nullable=False),
        sa.Column("employment_tenure", sa.String(30), nullable=True),
        sa.Column("employer_name", sa.String(200), nullable=True),
        sa.Column("monthly_expenses", sa.Numeric(12, 2), nullable=False),
        sa.Column("existing_loan_payments", sa.Numeric(12, 2), nullable=False, server_default="0"),
        # Computed / result
        sa.Column("financing_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_monthly_payment", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_tenure_months", sa.Integer, nullable=True),
        sa.Column("estimated_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("credit_product_id", sa.Integer, sa.ForeignKey("credit_products.id"), nullable=True),
        # Decision
        sa.Column("outcome", sa.String(30), nullable=True),
        sa.Column("outcome_details", sa.JSON, nullable=True),
        sa.Column("dti_ratio", sa.Numeric(6, 4), nullable=True),
        sa.Column("ndi_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("bureau_data_cached", sa.JSON, nullable=True),
        sa.Column("decision_strategy_version", sa.String(20), nullable=True),
        # Consent
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_soft_inquiry", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("consent_data_processing", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=True),
        # Photo
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("photo_extraction_data", sa.JSON, nullable=True),
        # Lifecycle
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linked_application_id", sa.Integer, sa.ForeignKey("loan_applications.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "pre_approval_otps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(30), nullable=False, index=True),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pre_approval_otps")
    op.drop_table("pre_approvals")
