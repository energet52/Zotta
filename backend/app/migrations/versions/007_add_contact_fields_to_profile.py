"""Add contact fields to applicant_profiles.

Revision ID: 007_contact_fields
Revises: 006_add_disbursement_payment_type
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa


revision = "007_contact_fields"
down_revision = "006_disb_pay_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applicant_profiles", sa.Column("whatsapp_number", sa.String(30), nullable=True))
    op.add_column("applicant_profiles", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column("applicant_profiles", sa.Column("mobile_phone", sa.String(30), nullable=True))
    op.add_column("applicant_profiles", sa.Column("home_phone", sa.String(30), nullable=True))
    op.add_column("applicant_profiles", sa.Column("employer_phone", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("applicant_profiles", "employer_phone")
    op.drop_column("applicant_profiles", "home_phone")
    op.drop_column("applicant_profiles", "mobile_phone")
    op.drop_column("applicant_profiles", "contact_email")
    op.drop_column("applicant_profiles", "whatsapp_number")
