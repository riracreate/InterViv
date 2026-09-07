"""Phase C: persist coding submit attempts (source plus outcome counts).

Revision ID: 20260907_0005
Revises: 20260907_0004
Create Date: 2026-09-07 18:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0005"
down_revision = "20260907_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coding_submissions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("visible_passed", sa.Integer(), nullable=True),
        sa.Column("visible_total", sa.Integer(), nullable=True),
        sa.Column("hidden_passed", sa.Integer(), nullable=True),
        sa.Column("hidden_total", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_coding_submissions_user_id", "coding_submissions", ["user_id"]
    )
    op.create_index(
        "ix_coding_submissions_session_id", "coding_submissions", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_coding_submissions_session_id",
                  table_name="coding_submissions")
    op.drop_index("ix_coding_submissions_user_id",
                  table_name="coding_submissions")
    op.drop_table("coding_submissions")
