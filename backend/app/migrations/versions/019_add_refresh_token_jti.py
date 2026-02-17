"""Add refresh_token_jti to user_sessions for refresh token rotation.

Revision ID: 019
"""

from alembic import op
import sqlalchemy as sa


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_sessions",
        sa.Column("refresh_token_jti", sa.String(64), unique=True, nullable=True),
    )
    op.create_index(
        "ix_user_sessions_refresh_token_jti",
        "user_sessions",
        ["refresh_token_jti"],
    )


def downgrade():
    op.drop_index("ix_user_sessions_refresh_token_jti", table_name="user_sessions")
    op.drop_column("user_sessions", "refresh_token_jti")
