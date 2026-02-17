"""Add product intelligence columns and rate tiers table.

New columns on credit_products:
  - interest_rate, eligibility_criteria, lifecycle_status, version,
    channels, target_segments, internal_notes, regulatory_code, ai_summary

New table: product_rate_tiers (risk-based pricing)
"""

from alembic import op
import sqlalchemy as sa


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to credit_products
    op.add_column("credit_products", sa.Column("interest_rate", sa.Numeric(6, 4), nullable=True))
    op.add_column("credit_products", sa.Column("eligibility_criteria", sa.JSON(), nullable=True))
    op.add_column("credit_products", sa.Column("lifecycle_status", sa.String(20), nullable=False, server_default="active"))
    op.add_column("credit_products", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("credit_products", sa.Column("channels", sa.JSON(), nullable=True))
    op.add_column("credit_products", sa.Column("target_segments", sa.JSON(), nullable=True))
    op.add_column("credit_products", sa.Column("internal_notes", sa.Text(), nullable=True))
    op.add_column("credit_products", sa.Column("regulatory_code", sa.String(50), nullable=True))
    op.add_column("credit_products", sa.Column("ai_summary", sa.Text(), nullable=True))

    # Create product_rate_tiers table
    op.create_table(
        "product_rate_tiers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("credit_product_id", sa.Integer(), sa.ForeignKey("credit_products.id"), nullable=False, index=True),
        sa.Column("tier_name", sa.String(100), nullable=False),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("interest_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("max_ltv_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("max_dti_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("product_rate_tiers")
    op.drop_column("credit_products", "ai_summary")
    op.drop_column("credit_products", "regulatory_code")
    op.drop_column("credit_products", "internal_notes")
    op.drop_column("credit_products", "target_segments")
    op.drop_column("credit_products", "channels")
    op.drop_column("credit_products", "version")
    op.drop_column("credit_products", "lifecycle_status")
    op.drop_column("credit_products", "eligibility_criteria")
    op.drop_column("credit_products", "interest_rate")
