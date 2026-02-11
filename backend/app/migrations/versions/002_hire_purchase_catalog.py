"""Add hire-purchase catalog and application item tables.

Revision ID: 002_hire_purchase_catalog
Revises: 001_counterproposal_contract
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002_hire_purchase_catalog"
down_revision = "001_counterproposal_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_merchants_name", "merchants", ["name"], unique=True)

    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_product_categories_name", "product_categories", ["name"], unique=True)

    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "name", name="uq_branch_name_per_merchant"),
    )
    op.create_index("ix_branches_merchant_id", "branches", ["merchant_id"], unique=False)

    op.create_table(
        "credit_products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("merchant_id", sa.Integer(), nullable=True),
        sa.Column("min_term_months", sa.Integer(), nullable=False),
        sa.Column("max_term_months", sa.Integer(), nullable=False),
        sa.Column("min_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("repayment_scheme", sa.String(length=200), nullable=False),
        sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_products_name", "credit_products", ["name"], unique=False)
    op.create_index("ix_credit_products_merchant_id", "credit_products", ["merchant_id"], unique=False)

    op.create_table(
        "product_score_ranges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("credit_product_id", sa.Integer(), nullable=False),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["credit_product_id"], ["credit_products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_score_ranges_credit_product_id", "product_score_ranges", ["credit_product_id"], unique=False)

    op.create_table(
        "product_fees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("credit_product_id", sa.Integer(), nullable=False),
        sa.Column("fee_type", sa.String(length=60), nullable=False),
        sa.Column("fee_base", sa.String(length=60), nullable=False),
        sa.Column("fee_amount", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["credit_product_id"], ["credit_products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_fees_credit_product_id", "product_fees", ["credit_product_id"], unique=False)

    op.add_column("loan_applications", sa.Column("merchant_id", sa.Integer(), nullable=True))
    op.add_column("loan_applications", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column("loan_applications", sa.Column("credit_product_id", sa.Integer(), nullable=True))
    op.add_column("loan_applications", sa.Column("downpayment", sa.Numeric(12, 2), nullable=True))
    op.add_column("loan_applications", sa.Column("total_financed", sa.Numeric(12, 2), nullable=True))
    op.create_index("ix_loan_applications_merchant_id", "loan_applications", ["merchant_id"], unique=False)
    op.create_index("ix_loan_applications_branch_id", "loan_applications", ["branch_id"], unique=False)
    op.create_index("ix_loan_applications_credit_product_id", "loan_applications", ["credit_product_id"], unique=False)
    op.create_foreign_key(
        "fk_loan_applications_merchant_id_merchants",
        "loan_applications",
        "merchants",
        ["merchant_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_loan_applications_branch_id_branches",
        "loan_applications",
        "branches",
        ["branch_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_loan_applications_credit_product_id_credit_products",
        "loan_applications",
        "credit_products",
        ["credit_product_id"],
        ["id"],
    )

    op.create_table(
        "application_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("loan_application_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"]),
        sa.ForeignKeyConstraint(["loan_application_id"], ["loan_applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_items_loan_application_id", "application_items", ["loan_application_id"], unique=False)
    op.create_index("ix_application_items_category_id", "application_items", ["category_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_application_items_category_id", table_name="application_items")
    op.drop_index("ix_application_items_loan_application_id", table_name="application_items")
    op.drop_table("application_items")

    op.drop_constraint("fk_loan_applications_credit_product_id_credit_products", "loan_applications", type_="foreignkey")
    op.drop_constraint("fk_loan_applications_branch_id_branches", "loan_applications", type_="foreignkey")
    op.drop_constraint("fk_loan_applications_merchant_id_merchants", "loan_applications", type_="foreignkey")
    op.drop_index("ix_loan_applications_credit_product_id", table_name="loan_applications")
    op.drop_index("ix_loan_applications_branch_id", table_name="loan_applications")
    op.drop_index("ix_loan_applications_merchant_id", table_name="loan_applications")
    op.drop_column("loan_applications", "total_financed")
    op.drop_column("loan_applications", "downpayment")
    op.drop_column("loan_applications", "credit_product_id")
    op.drop_column("loan_applications", "branch_id")
    op.drop_column("loan_applications", "merchant_id")

    op.drop_index("ix_product_fees_credit_product_id", table_name="product_fees")
    op.drop_table("product_fees")
    op.drop_index("ix_product_score_ranges_credit_product_id", table_name="product_score_ranges")
    op.drop_table("product_score_ranges")
    op.drop_index("ix_credit_products_merchant_id", table_name="credit_products")
    op.drop_index("ix_credit_products_name", table_name="credit_products")
    op.drop_table("credit_products")
    op.drop_index("ix_branches_merchant_id", table_name="branches")
    op.drop_table("branches")
    op.drop_index("ix_product_categories_name", table_name="product_categories")
    op.drop_table("product_categories")
    op.drop_index("ix_merchants_name", table_name="merchants")
    op.drop_table("merchants")
