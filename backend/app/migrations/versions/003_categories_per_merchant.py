"""Add merchant_id to product_categories - categories per merchant.

Revision ID: 003_categories_per_merchant
Revises: 002_hire_purchase_catalog
Create Date: 2026-02-11

"""

from alembic import op
import sqlalchemy as sa


revision = "003_categories_per_merchant"
down_revision = "002_hire_purchase_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_categories", sa.Column("merchant_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_product_categories_merchant_id_merchants",
        "product_categories",
        "merchants",
        ["merchant_id"],
        ["id"],
    )
    op.create_index("ix_product_categories_merchant_id", "product_categories", ["merchant_id"], unique=False)

    # Assign existing categories to first merchant
    op.execute("""
        UPDATE product_categories
        SET merchant_id = (SELECT id FROM merchants ORDER BY id LIMIT 1)
        WHERE merchant_id IS NULL
    """)

    op.alter_column("product_categories", "merchant_id", nullable=False)

    op.drop_index("ix_product_categories_name", table_name="product_categories")
    op.create_unique_constraint("uq_category_name_per_merchant", "product_categories", ["merchant_id", "name"])
    op.create_index("ix_product_categories_name", "product_categories", ["name"], unique=False)


def downgrade() -> None:
    op.drop_constraint("uq_category_name_per_merchant", "product_categories", type_="unique")
    op.drop_index("ix_product_categories_name", table_name="product_categories")
    op.create_index("ix_product_categories_name", "product_categories", ["name"], unique=True)

    op.drop_index("ix_product_categories_merchant_id", table_name="product_categories")
    op.drop_constraint("fk_product_categories_merchant_id_merchants", "product_categories", type_="foreignkey")
    op.drop_column("product_categories", "merchant_id")
