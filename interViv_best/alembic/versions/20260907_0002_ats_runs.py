"""Ticket C: ats_runs table for ATS score history.

Revision ID: 20260907_0002
Revises: 20260907_0001
Create Date: 2026-09-07 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0002"
down_revision = "20260907_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ats_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("resume_id", sa.String(length=64), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=True),
        sa.Column("jd_hash", sa.String(length=64), nullable=True),
        sa.Column("parse_score", sa.Float(), nullable=False),
        sa.Column("section_score", sa.Float(), nullable=False),
        sa.Column("keyword_score", sa.Float(), nullable=False),
        sa.Column("heuristic_score", sa.Float(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("present_skills", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ats_runs_user_id", "ats_runs", ["user_id"])
    op.create_index("ix_ats_runs_resume_id", "ats_runs", ["resume_id"])
    op.create_index("ix_ats_runs_role_id", "ats_runs", ["role_id"])


def downgrade() -> None:
    op.drop_index("ix_ats_runs_role_id", table_name="ats_runs")
    op.drop_index("ix_ats_runs_resume_id", table_name="ats_runs")
    op.drop_index("ix_ats_runs_user_id", table_name="ats_runs")
    op.drop_table("ats_runs")
