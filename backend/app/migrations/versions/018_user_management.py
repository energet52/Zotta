"""018 – User management: roles, permissions, MFA, sessions, login attempts, pending actions.

Adds tables for the RBAC system and extends the users table with
profile, security, and status fields.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extended User columns ────────────────────────────────
    op.add_column("users", sa.Column("middle_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("display_name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("employee_id", sa.String(50), nullable=True, unique=True))
    op.add_column("users", sa.Column("department", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(150), nullable=True))
    op.add_column("users", sa.Column("reporting_manager_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.String(50), server_default="America/Port_of_Spain", nullable=False))
    op.add_column("users", sa.Column("language", sa.String(10), server_default="en", nullable=False))
    op.add_column("users", sa.Column("profile_photo_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("status", sa.String(30), server_default="active", nullable=False))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer, server_default="0", nullable=False))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean, server_default="false", nullable=False))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean, server_default="false", nullable=False))

    op.create_index("ix_users_status", "users", ["status"])

    # ── Roles ────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("parent_role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("is_system", sa.Boolean, default=False, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Permissions ──────────────────────────────────────────
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(150), unique=True, nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("object", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("scope_levels", JSON, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    # ── Role-Permission join ─────────────────────────────────
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.Integer, sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(30), server_default="all", nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_perm"),
    )

    # ── User-Role assignments ────────────────────────────────
    op.create_table(
        "user_role_assignments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("granted_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_primary", sa.Boolean, default=False, nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index("ix_ura_user", "user_role_assignments", ["user_id"])
    op.create_index("ix_ura_role", "user_role_assignments", ["role_id"])

    # ── MFA Devices ──────────────────────────────────────────
    op.create_table(
        "mfa_devices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("device_name", sa.String(100), nullable=True),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("is_verified", sa.Boolean, default=False, nullable=False),
        sa.Column("is_primary", sa.Boolean, default=False, nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mfa_user", "mfa_devices", ["user_id"])

    # ── User Sessions ────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_jti", sa.String(64), unique=True, nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("location", sa.String(150), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user", "user_sessions", ["user_id"])
    op.create_index("ix_sessions_jti", "user_sessions", ["token_jti"])

    # ── Login Attempts ───────────────────────────────────────
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("location", sa.String(150), nullable=True),
        sa.Column("success", sa.Boolean, default=False, nullable=False),
        sa.Column("failure_reason", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_login_attempts_user", "login_attempts", ["user_id"])

    # ── Pending Actions (Maker-Checker) ──────────────────────
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("target_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("requested_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("pending_actions")
    op.drop_table("login_attempts")
    op.drop_table("user_sessions")
    op.drop_table("mfa_devices")
    op.drop_table("user_role_assignments")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")

    for col in [
        "middle_name", "display_name", "employee_id", "department",
        "job_title", "reporting_manager_id", "timezone", "language",
        "profile_photo_url", "status", "last_login_at",
        "failed_login_attempts", "locked_until", "password_changed_at",
        "must_change_password", "mfa_enabled",
    ]:
        op.drop_column("users", col)
    op.drop_index("ix_users_status", "users")
