"""Add external identities and revocable browser sessions.

Revision ID: 20260727_02
Revises: 20260727_01
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_02"
down_revision: str | None = "20260727_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create additive authentication infrastructure tables."""
    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_auth_identity_provider_subject",
        ),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_token_hash",
        "auth_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade() -> None:
    """Remove only the Phase 2.1 authentication infrastructure."""
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_table("auth_identities")
