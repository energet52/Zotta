"""Collections module upgrade — cases, PTP, settlements, compliance, SLAs, snapshots.

Revision ID: 017
Revises: 016
"""

from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Collection Cases ──────────────────────────────────────
    op.create_table(
        "collection_cases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("loan_application_id", sa.Integer, sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("assigned_agent_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("delinquency_stage", sa.String(30), nullable=False, server_default="early_1_30"),
        sa.Column("priority_score", sa.Float, server_default="0"),
        sa.Column("dpd", sa.Integer, server_default="0"),
        sa.Column("total_overdue", sa.Numeric(14, 2), server_default="0"),
        sa.Column("dispute_active", sa.Boolean, server_default="false"),
        sa.Column("vulnerability_flag", sa.Boolean, server_default="false"),
        sa.Column("do_not_contact", sa.Boolean, server_default="false"),
        sa.Column("hardship_flag", sa.Boolean, server_default="false"),
        sa.Column("next_best_action", sa.String(100), nullable=True),
        sa.Column("nba_confidence", sa.Float, server_default="0"),
        sa.Column("nba_reasoning", sa.Text, nullable=True),
        sa.Column("first_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_first_contact_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_next_contact_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("jurisdiction", sa.String(5), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_collection_cases_loan_application_id", "collection_cases", ["loan_application_id"], unique=True)
    op.create_index("ix_collection_cases_assigned_agent_id", "collection_cases", ["assigned_agent_id"])

    # ── Promises to Pay ───────────────────────────────────────
    op.create_table(
        "promises_to_pay",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("collection_case_id", sa.Integer, sa.ForeignKey("collection_cases.id"), nullable=False),
        sa.Column("loan_application_id", sa.Integer, sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("agent_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount_promised", sa.Numeric(14, 2), nullable=False),
        sa.Column("promise_date", sa.Date, nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("amount_received", sa.Numeric(14, 2), server_default="0"),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("broken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ptp_collection_case_id", "promises_to_pay", ["collection_case_id"])
    op.create_index("ix_ptp_loan_application_id", "promises_to_pay", ["loan_application_id"])

    # ── Settlement Offers ─────────────────────────────────────
    op.create_table(
        "settlement_offers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("collection_case_id", sa.Integer, sa.ForeignKey("collection_cases.id"), nullable=False),
        sa.Column("loan_application_id", sa.Integer, sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("offer_type", sa.String(30), nullable=False),
        sa.Column("original_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("settlement_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_pct", sa.Float, server_default="0"),
        sa.Column("plan_months", sa.Integer, nullable=True),
        sa.Column("plan_monthly_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("lump_sum", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("offered_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approval_required", sa.Boolean, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_settlement_collection_case_id", "settlement_offers", ["collection_case_id"])
    op.create_index("ix_settlement_loan_application_id", "settlement_offers", ["loan_application_id"])

    # ── Compliance Rules ──────────────────────────────────────
    op.create_table(
        "compliance_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("jurisdiction", sa.String(10), nullable=False),
        sa.Column("contact_start_hour", sa.Integer, server_default="8"),
        sa.Column("contact_end_hour", sa.Integer, server_default="20"),
        sa.Column("max_contacts_per_day", sa.Integer, server_default="3"),
        sa.Column("max_contacts_per_week", sa.Integer, server_default="10"),
        sa.Column("cooling_off_hours", sa.Integer, server_default="4"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_compliance_rules_jurisdiction", "compliance_rules", ["jurisdiction"])

    # ── SLA Configs ───────────────────────────────────────────
    op.create_table(
        "sla_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("delinquency_stage", sa.String(50), nullable=False),
        sa.Column("hours_allowed", sa.Integer, nullable=False),
        sa.Column("escalation_action", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )

    # ── Collections Dashboard Snapshots ───────────────────────
    op.create_table(
        "collections_dashboard_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_date", sa.Date, nullable=False, unique=True),
        sa.Column("total_delinquent_accounts", sa.Integer, server_default="0"),
        sa.Column("total_overdue_amount", sa.Numeric(16, 2), server_default="0"),
        sa.Column("by_stage", sa.JSON, nullable=True),
        sa.Column("by_outcome", sa.JSON, nullable=True),
        sa.Column("cure_rate", sa.Float, server_default="0"),
        sa.Column("ptp_rate", sa.Float, server_default="0"),
        sa.Column("ptp_kept_rate", sa.Float, server_default="0"),
        sa.Column("avg_days_to_collect", sa.Float, server_default="0"),
        sa.Column("total_recovered_mtd", sa.Numeric(16, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cds_snapshot_date", "collections_dashboard_snapshots", ["snapshot_date"])

    # ── Add collection_case_id FK to existing CollectionRecord ─
    op.add_column(
        "collection_records",
        sa.Column("collection_case_id", sa.Integer, sa.ForeignKey("collection_cases.id"), nullable=True),
    )
    op.create_index("ix_collection_records_case_id", "collection_records", ["collection_case_id"])


def downgrade() -> None:
    op.drop_index("ix_collection_records_case_id", table_name="collection_records")
    op.drop_column("collection_records", "collection_case_id")
    op.drop_table("collections_dashboard_snapshots")
    op.drop_table("sla_configs")
    op.drop_table("compliance_rules")
    op.drop_table("settlement_offers")
    op.drop_table("promises_to_pay")
    op.drop_table("collection_cases")
