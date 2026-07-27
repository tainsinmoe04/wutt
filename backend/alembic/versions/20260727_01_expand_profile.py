"""Expand profiles to match the current UI.

Revision ID: 20260727_01
Revises:
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROFILE_COLUMNS = (
    sa.Column("name", sa.String(length=100), nullable=True),
    sa.Column("gender", sa.String(length=30), nullable=True),
    sa.Column("top_size", sa.String(length=20), nullable=True),
    sa.Column("bottom_size", sa.String(length=20), nullable=True),
    sa.Column("shoe_size", sa.String(length=30), nullable=True),
    sa.Column("location_area", sa.String(length=100), nullable=True),
    sa.Column("fit_preference", sa.String(length=50), nullable=True),
    sa.Column("outfit_vibe", sa.String(length=50), nullable=True),
    sa.Column("preferred_colors", sa.String(length=200), nullable=True),
    sa.Column("shopping_style", sa.String(length=50), nullable=True),
)


def upgrade() -> None:
    """Add nullable columns without rewriting or deleting existing profile data."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "profiles" not in inspector.get_table_names():
        raise RuntimeError(
            "The profiles table does not exist. Initialize the existing WUTT schema "
            "before applying this additive migration."
        )

    existing = {column["name"] for column in inspector.get_columns("profiles")}
    for column in PROFILE_COLUMNS:
        if column.name not in existing:
            op.add_column("profiles", column)


def downgrade() -> None:
    """Remove only the columns introduced by this revision."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "profiles" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("profiles")}
    for column in reversed(PROFILE_COLUMNS):
        if column.name in existing:
            op.drop_column("profiles", column.name)
