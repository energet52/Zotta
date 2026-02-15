"""Add sector analysis tables: policies, alerts, snapshots, macro indicators.

Revision ID: 015
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sector_policies ──────────────────────────────────────────
    op.create_table(
        "sector_policies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sector", sa.String(100), nullable=False, index=True),
        sa.Column("exposure_cap_pct", sa.Float, nullable=True),
        sa.Column("exposure_cap_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("origination_paused", sa.Boolean, server_default="false"),
        sa.Column("pause_effective_date", sa.Date, nullable=True),
        sa.Column("pause_expiry_date", sa.Date, nullable=True),
        sa.Column("pause_reason", sa.Text, nullable=True),
        sa.Column("max_loan_amount_override", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_credit_score_override", sa.Integer, nullable=True),
        sa.Column("max_term_months_override", sa.Integer, nullable=True),
        sa.Column("require_collateral", sa.Boolean, server_default="false"),
        sa.Column("require_guarantor", sa.Boolean, server_default="false"),
        sa.Column("risk_rating", sa.String(20), server_default="medium"),
        sa.Column("on_watchlist", sa.Boolean, server_default="false"),
        sa.Column("watchlist_review_frequency", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), server_default="active"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("justification", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── sector_alert_rules ───────────────────────────────────────
    op.create_table(
        "sector_alert_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(10), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("consecutive_months", sa.Integer, server_default="1"),
        sa.Column("severity", sa.String(20), server_default="warning"),
        sa.Column("recommended_action", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── sector_alerts ────────────────────────────────────────────
    op.create_table(
        "sector_alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.Integer, sa.ForeignKey("sector_alert_rules.id"), nullable=True),
        sa.Column("sector", sa.String(100), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metric_name", sa.String(50), nullable=True),
        sa.Column("metric_value", sa.Float, nullable=True),
        sa.Column("threshold_value", sa.Float, nullable=True),
        sa.Column("recommended_action", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="new"),
        sa.Column("acknowledged_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── sector_snapshots ─────────────────────────────────────────
    op.create_table(
        "sector_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_date", sa.Date, nullable=False, index=True),
        sa.Column("sector", sa.String(100), nullable=False, index=True),
        sa.Column("loan_count", sa.Integer, server_default="0"),
        sa.Column("total_outstanding", sa.Numeric(16, 2), server_default="0"),
        sa.Column("total_disbursed", sa.Numeric(16, 2), server_default="0"),
        sa.Column("avg_loan_size", sa.Numeric(14, 2), server_default="0"),
        sa.Column("exposure_pct", sa.Float, server_default="0"),
        sa.Column("current_count", sa.Integer, server_default="0"),
        sa.Column("dpd_30_count", sa.Integer, server_default="0"),
        sa.Column("dpd_60_count", sa.Integer, server_default="0"),
        sa.Column("dpd_90_count", sa.Integer, server_default="0"),
        sa.Column("dpd_30_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("dpd_60_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("dpd_90_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("delinquency_rate", sa.Float, server_default="0"),
        sa.Column("npl_ratio", sa.Float, server_default="0"),
        sa.Column("default_rate", sa.Float, server_default="0"),
        sa.Column("write_off_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("risk_rating", sa.String(20), nullable=True),
        sa.Column("avg_credit_score", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── sector_macro_indicators ──────────────────────────────────
    op.create_table(
        "sector_macro_indicators",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sector", sa.String(100), nullable=False, index=True),
        sa.Column("indicator_name", sa.String(200), nullable=False),
        sa.Column("indicator_value", sa.Float, nullable=False),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sector_macro_indicators")
    op.drop_table("sector_snapshots")
    op.drop_table("sector_alerts")
    op.drop_table("sector_alert_rules")
    op.drop_table("sector_policies")
