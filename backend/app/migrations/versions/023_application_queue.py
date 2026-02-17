"""Application Queue Management.

Creates: queue_config, queue_stages, queue_entries,
         staff_queue_profiles, queue_events, queue_exceptions
"""

from alembic import op
import sqlalchemy as sa


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── queue_config (singleton) ─────────────────────────────
    op.create_table(
        "queue_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("assignment_mode", sa.String(20), nullable=False, server_default="pull"),
        sa.Column("stages_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sla_mode", sa.String(10), nullable=False, server_default="none"),
        sa.Column("authority_limits_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("skills_routing_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("exceptions_formal", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("segregation_of_duties", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("target_turnaround_hours", sa.Integer, nullable=True),
        sa.Column("business_hours_start", sa.Time, nullable=False, server_default="08:00:00"),
        sa.Column("business_hours_end", sa.Time, nullable=False, server_default="17:00:00"),
        sa.Column("business_days", sa.JSON, nullable=False, server_default="[1,2,3,4,5]"),
        sa.Column("holidays", sa.JSON, nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="America/Port_of_Spain"),
        sa.Column("auto_expire_days", sa.Integer, nullable=False, server_default="14"),
        sa.Column("follow_up_days", sa.JSON, nullable=False, server_default="[1,3,7]"),
        sa.Column("ai_config", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── queue_stages ─────────────────────────────────────────
    op.create_table(
        "queue_stages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("assignment_mode", sa.String(20), nullable=True),
        sa.Column("allowed_roles", sa.JSON, nullable=True),
        sa.Column("skip_conditions", sa.JSON, nullable=True),
        sa.Column("can_parallel_with", sa.JSON, nullable=True),
        sa.Column("sla_target_hours", sa.Integer, nullable=True),
        sa.Column("sla_warning_hours", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── queue_entries ────────────────────────────────────────
    op.create_table(
        "queue_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("loan_applications.id"), nullable=False, unique=True),
        sa.Column("priority_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("priority_factors", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("queue_stage_id", sa.Integer, sa.ForeignKey("queue_stages.id"), nullable=True),
        sa.Column("assigned_to_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("suggested_for_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("waiting_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waiting_reason", sa.Text, nullable=True),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_warning_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_elapsed_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_stuck", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_flagged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("flag_reasons", sa.JSON, nullable=True),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("completeness_score", sa.Float, nullable=True),
        sa.Column("complexity_estimate_hours", sa.Float, nullable=True),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_queue_entries_status", "queue_entries", ["status"])
    op.create_index("ix_queue_entries_assigned_to_id", "queue_entries", ["assigned_to_id"])
    op.create_index("ix_queue_entries_priority", "queue_entries", ["priority_score"])

    # ── staff_queue_profiles ─────────────────────────────────
    op.create_table(
        "staff_queue_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("max_concurrent", sa.Integer, nullable=False, server_default="10"),
        sa.Column("skills", sa.JSON, nullable=True),
        sa.Column("authority_max_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("authority_risk_grades", sa.JSON, nullable=True),
        sa.Column("authority_products", sa.JSON, nullable=True),
        sa.Column("shift_start", sa.Time, nullable=True),
        sa.Column("shift_end", sa.Time, nullable=True),
        sa.Column("current_load_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_processing_hours", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── queue_events ─────────────────────────────────────────
    op.create_table(
        "queue_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("queue_entry_id", sa.Integer, sa.ForeignKey("queue_entries.id"), nullable=False),
        sa.Column("application_id", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("from_value", sa.JSON, nullable=True),
        sa.Column("to_value", sa.JSON, nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_queue_events_entry", "queue_events", ["queue_entry_id"])
    op.create_index("ix_queue_events_app", "queue_events", ["application_id"])
    op.create_index("ix_queue_events_type", "queue_events", ["event_type"])

    # ── queue_exceptions ─────────────────────────────────────
    op.create_table(
        "queue_exceptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("queue_entry_id", sa.Integer, sa.ForeignKey("queue_entries.id"), nullable=False),
        sa.Column("application_id", sa.Integer, nullable=False),
        sa.Column("exception_type", sa.String(40), nullable=False),
        sa.Column("raised_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_approver_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("approver_notes", sa.Text, nullable=True),
        sa.Column("ai_precedent", sa.JSON, nullable=True),
        sa.Column("escalation_level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_queue_exceptions_entry", "queue_exceptions", ["queue_entry_id"])
    op.create_index("ix_queue_exceptions_status", "queue_exceptions", ["status"])


def downgrade() -> None:
    op.drop_table("queue_exceptions")
    op.drop_table("queue_events")
    op.drop_table("staff_queue_profiles")
    op.drop_table("queue_entries")
    op.drop_table("queue_stages")
    op.drop_table("queue_config")
