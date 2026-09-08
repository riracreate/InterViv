"""Phase X: persist unevaluated ML primitive attempts.

Revision ID: 20260908_0009
Revises: 20260907_0008
"""

from alembic import op
import sqlalchemy as sa

revision = "20260908_0009"
down_revision = "20260907_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ml_primitives_attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("block_id", sa.String(64), nullable=False),
        sa.Column("problem_id", sa.String(64), nullable=False),
        sa.Column("problem_version", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("user_id", "session_id"):
        op.create_index(f"ix_ml_primitives_attempts_{column}", "ml_primitives_attempts", [column])


def downgrade():
    for column in ("session_id", "user_id"):
        op.drop_index(f"ix_ml_primitives_attempts_{column}", table_name="ml_primitives_attempts")
    op.drop_table("ml_primitives_attempts")
