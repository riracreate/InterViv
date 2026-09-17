"""Phase 3B: persist progression_blocked_reason on sessions.

Revision ID: 20260915_0013
Revises: 20260914_0012
"""

from alembic import op
import sqlalchemy as sa


revision = "20260915_0013"
down_revision = "20260914_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("progression_blocked_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "progression_blocked_reason")
