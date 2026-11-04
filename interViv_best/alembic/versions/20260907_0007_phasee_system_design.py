"""Phase E: system-design attempts (self-assessment rubric results).

Revision ID: 20260907_0007
Revises: 20260907_0006
Create Date: 2026-09-07 20:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0007"
down_revision = "20260907_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_design_attempts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("prompt_id", sa.String(length=64), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("rubric_json", sa.JSON(), nullable=False),
        sa.Column("evaluation_mode", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("incomplete", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_system_design_attempts_user_id",
        "system_design_attempts",
        ["user_id"],
    )
    op.create_index(
        "ix_system_design_attempts_session_id",
        "system_design_attempts",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_system_design_attempts_session_id",
        table_name="system_design_attempts",
    )
    op.drop_index(
        "ix_system_design_attempts_user_id",
        table_name="system_design_attempts",
    )
    op.drop_table("system_design_attempts")
