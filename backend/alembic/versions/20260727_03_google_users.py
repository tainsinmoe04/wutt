"""Allow users authenticated exclusively by an external identity.

Revision ID: 20260727_03
Revises: 20260727_02
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_03"
down_revision: str | None = "20260727_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Support Google-only users and one identity per provider per user."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=True,
        )
    with op.batch_alter_table("auth_identities") as batch_op:
        batch_op.create_unique_constraint(
            "uq_auth_identity_user_provider",
            ["user_id", "provider"],
        )


def downgrade() -> None:
    """Restore the original password requirement when all users have hashes."""
    bind = op.get_bind()
    null_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE password_hash IS NULL")
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            "Cannot require password_hash while externally authenticated users exist."
        )
    with op.batch_alter_table("auth_identities") as batch_op:
        batch_op.drop_constraint(
            "uq_auth_identity_user_provider",
            type_="unique",
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=False,
        )
