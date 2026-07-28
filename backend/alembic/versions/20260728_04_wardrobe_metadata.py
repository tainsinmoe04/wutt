"""Add optional wardrobe metadata used by the stylist.

Revision ID: 20260728_04
Revises: 20260727_03
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260728_04"
down_revision: str | None = "20260727_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable fields so existing wardrobe rows remain valid."""
    with op.batch_alter_table("wardrobes") as batch_op:
        batch_op.add_column(sa.Column("brand", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("formality_level", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("season_suitability", sa.String(length=100), nullable=True)
        )


def downgrade() -> None:
    """Remove the optional wardrobe metadata fields."""
    with op.batch_alter_table("wardrobes") as batch_op:
        batch_op.drop_column("season_suitability")
        batch_op.drop_column("formality_level")
        batch_op.drop_column("brand")
