"""Phase 3A: immutable attempt snapshot per round.

Revision ID: 20260914_0011
Revises: 20260913_0010
"""

from alembic import op
import sqlalchemy as sa

revision = "20260914_0011"
down_revision = "20260913_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable: pre-snapshot rounds stay valid; new scored rounds freeze one.
    op.add_column("rounds", sa.Column("attempt_snapshot_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("rounds", "attempt_snapshot_json")
